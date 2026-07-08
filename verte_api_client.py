"""Verte API client with response caching."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import requests

RETRYABLE_ERRORS = (
    "Connection was reset",
    "Recv failure",
    "Empty reply from server",
    "Operation timed out",
    "SSL connection timeout",
)


class VerteApiClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.api_url = config["api_url"].rstrip("/") + "/"
        self.access_key = config["p_access_key"]
        self.timeout = int(config.get("timeout", 300))
        self.max_retries = int(config.get("retries", 2))
        self.default_params = config.get("request_params") or {}
        self.cache_enabled = bool(config.get("cache_enabled", True))
        self.cache_ttl = int(config.get("cache_ttl", 3600))
        self.cache_ttl_by_cmd = config.get("cache_ttl_by_cmd") or {}
        cache_dir = config.get("cache_dir")
        self.cache_dir = Path(cache_dir) if cache_dir else Path(__file__).resolve().parent / "cache"

    def call(
        self, cmd: str, params: dict[str, Any] | None = None, force_refresh: bool = False
    ) -> dict[str, Any]:
        params = params or {}
        cache_key = self._cache_key(cmd, params)

        if self.cache_enabled and not force_refresh:
            cached = self._read_cache(cache_key, cmd)
            if cached is not None:
                cached["attempts"] = 0
                cached["from_cache"] = True
                cached.setdefault("cached_at", None)
                return cached

        payload = json.dumps(
            {"cmd": cmd, "pAccessKey": self.access_key, **self.default_params, **params}
        )

        attempts = 0
        last: dict[str, Any] | None = None

        for try_num in range(self.max_retries + 1):
            attempts = try_num + 1
            last = self._execute_request(payload)
            if last["error"] is None or not self._should_retry(last["error"], try_num):
                break
            time.sleep(0.5 * (try_num + 1))

        assert last is not None
        last["attempts"] = attempts
        last["from_cache"] = False
        last["cached_at"] = None

        if self.cache_enabled and last["ok"] and last["raw"]:
            self._write_cache(cache_key, last)
            last["cached_at"] = int(time.time())

        return last

    def get_cache_age(self, cmd: str, params: dict[str, Any] | None = None) -> int | None:
        meta = self._read_meta(self._cache_key(cmd, params or {}))
        if meta is None:
            return None
        return int(time.time()) - int(meta["cached_at"])

    def get_cached_summary(
        self, cmd: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        params = params or {}
        cache_key = self._cache_key(cmd, params)
        paths = self._cache_paths(cache_key)
        meta = self._read_meta(cache_key)

        if meta is None or not paths["body"].is_file():
            return None

        cached_at = int(meta.get("cached_at") or 0)
        if cached_at <= 0 or (time.time() - cached_at) > self._ttl_for_cmd(cmd):
            return None

        size = paths["body"].stat().st_size

        return {
            "ok": True,
            "http_code": int(meta.get("http_code") or 200),
            "body": None,
            "raw": "",
            "error": None,
            "record_count": int(meta["record_count"]) if "record_count" in meta else None,
            "from_cache": True,
            "cached_at": cached_at,
            "raw_size": size,
        }

    def get_cached_file_path(self, cmd: str, params: dict[str, Any] | None = None) -> Path | None:
        params = params or {}
        cache_key = self._cache_key(cmd, params)
        paths = self._cache_paths(cache_key)
        meta = self._read_meta(cache_key)

        if meta is None or not paths["body"].is_file():
            return None

        cached_at = int(meta.get("cached_at") or 0)
        if cached_at <= 0 or (time.time() - cached_at) > self._ttl_for_cmd(cmd):
            return None

        return paths["body"]

    def is_cache_valid(self, cmd: str, params: dict[str, Any] | None = None) -> bool:
        return self._read_cache(self._cache_key(cmd, params or {}), cmd) is not None

    def get_mfg_orders(
        self, params: dict[str, Any] | None = None, force_refresh: bool = False
    ) -> dict[str, Any]:
        return self.call("MfgOrders", params, force_refresh)

    def get_prod_plan(
        self, params: dict[str, Any] | None = None, force_refresh: bool = False
    ) -> dict[str, Any]:
        return self.call("ProdPlan", params, force_refresh)

    def get_oper_bull(
        self, mo_no: str, force_refresh: bool = False
    ) -> dict[str, Any]:
        return self.call("OperBull", {"pMONo": mo_no}, force_refresh)

    def _ttl_for_cmd(self, cmd: str) -> int:
        return int(self.cache_ttl_by_cmd.get(cmd, self.cache_ttl))

    def _execute_request(self, payload: str) -> dict[str, Any]:
        try:
            response = requests.post(
                self.api_url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=self.timeout,
            )
            raw = response.text
            return self._build_result(response.status_code, raw)
        except requests.RequestException as exc:
            return self._failure(0, None, "", str(exc) or "Unknown request error.")

    def _build_result(self, http_code: int, raw: str) -> dict[str, Any]:
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = raw

        api_err = self._extract_api_error(http_code, body, raw)

        return {
            "ok": 200 <= http_code < 300 and api_err is None,
            "http_code": http_code,
            "body": body,
            "raw": raw,
            "error": api_err,
            "record_count": self._count_records(body),
        }

    def _cache_key(self, cmd: str, params: dict[str, Any]) -> str:
        if not params:
            return cmd
        digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]
        return f"{cmd}_{digest}"

    def _cache_paths(self, cache_key: str) -> dict[str, Path]:
        return {
            "body": self.cache_dir / f"{cache_key}.json",
            "meta": self.cache_dir / f"{cache_key}.meta.json",
        }

    def _read_meta(self, cache_key: str) -> dict[str, Any] | None:
        meta_file = self._cache_paths(cache_key)["meta"]
        if not meta_file.is_file():
            return None
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return meta if isinstance(meta, dict) else None

    def _read_cache(self, cache_key: str, cmd: str) -> dict[str, Any] | None:
        paths = self._cache_paths(cache_key)
        if not paths["body"].is_file() or not paths["meta"].is_file():
            return None

        meta = self._read_meta(cache_key)
        if meta is None:
            return None

        cached_at = int(meta.get("cached_at") or 0)
        if cached_at <= 0 or (time.time() - cached_at) > self._ttl_for_cmd(cmd):
            return None

        try:
            raw = paths["body"].read_text(encoding="utf-8")
        except OSError:
            return None

        if not raw:
            return None

        result = self._build_result(int(meta.get("http_code") or 200), raw)
        result["from_cache"] = True
        result["cached_at"] = cached_at
        if "record_count" in meta:
            result["record_count"] = int(meta["record_count"])
        return result

    def _write_cache(self, cache_key: str, result: dict[str, Any]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        paths = self._cache_paths(cache_key)
        paths["body"].write_text(result["raw"], encoding="utf-8")
        paths["meta"].write_text(
            json.dumps(
                {
                    "cached_at": int(time.time()),
                    "http_code": result["http_code"],
                    "record_count": result["record_count"],
                    "size": len(result["raw"]),
                }
            ),
            encoding="utf-8",
        )

    def _failure(
        self, http_code: int, body: Any, raw: str, error: str
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "http_code": http_code,
            "body": body,
            "raw": raw,
            "error": error,
            "record_count": None,
        }

    def _should_retry(self, error: str, try_num: int) -> bool:
        if try_num >= self.max_retries:
            return False
        error_lower = error.lower()
        return any(needle.lower() in error_lower for needle in RETRYABLE_ERRORS)

    def _extract_api_error(self, http_code: int, body: Any, raw: str) -> str | None:
        if http_code >= 400:
            if isinstance(body, str) and body:
                return body
            if isinstance(body, dict):
                for key in ("message", "error", "Error", "Message"):
                    value = body.get(key)
                    if isinstance(value, str) and value:
                        return value
            return raw if raw else f"HTTP {http_code} error from API."

        if isinstance(body, str) and self._looks_like_api_error(body):
            return body
        return None

    def _looks_like_api_error(self, text: str) -> bool:
        import re

        return bool(
            re.search(
                r"expects parameter|not supplied|invalid|unauthorized|denied",
                text,
                re.IGNORECASE,
            )
        )

    def _count_records(self, body: Any) -> int | None:
        if not isinstance(body, list):
            return None
        count = sum(len(group) for group in body if isinstance(group, list))
        return count if count > 0 else None
