"""Client-side filtering for Verte API responses."""

from __future__ import annotations

import json
from typing import Any


class ResponseFilter:
    @staticmethod
    def from_request(source: dict[str, Any]) -> dict[str, str | None]:
        io_no = str(source.get("IONo") or source.get("io_no") or "").strip()
        mo_no = str(source.get("MONo") or source.get("mo_no") or "").strip()
        oper_desc = str(source.get("OperDesc") or source.get("oper_desc") or "").strip()
        return {
            "IONo": io_no if io_no else None,
            "MONo": mo_no if mo_no else None,
            "OperDesc": oper_desc if oper_desc else None,
        }

    @staticmethod
    def has_filters(io_no: str | None, mo_no: str | None) -> bool:
        return bool((io_no or "").strip() or (mo_no or "").strip())

    @staticmethod
    def has_filters_for_command(cmd: str, io_no: str | None, mo_no: str | None) -> bool:
        if cmd in ("ProdPlan", "OperBull"):
            return bool((mo_no or "").strip())
        return ResponseFilter.has_filters(io_no, mo_no)

    @staticmethod
    def uses_client_filter(cmd: str) -> bool:
        return cmd in ("MfgOrders", "ProdPlan")

    @staticmethod
    def should_apply_client_filter(cmd: str, filters: dict[str, str | None]) -> bool:
        if cmd in ("MfgOrders", "ProdPlan"):
            return ResponseFilter.has_filters_for_command(
                cmd, filters.get("IONo"), filters.get("MONo")
            )
        if cmd == "OperBull":
            return bool((filters.get("OperDesc") or "").strip())
        return False

    @staticmethod
    def api_params_for_command(cmd: str, io_no: str | None, mo_no: str | None) -> dict[str, Any]:
        if cmd == "OperBull" and mo_no:
            return {"pMONo": mo_no}
        return {}

    @staticmethod
    def apply_to_result(
        result: dict[str, Any],
        cmd: str,
        io_no: str | None,
        mo_no: str | None,
        oper_desc: str | None = None,
    ) -> dict[str, Any]:
        if cmd == "OperBull":
            if not (oper_desc or "").strip():
                return result
        elif not ResponseFilter.has_filters_for_command(cmd, io_no, mo_no):
            return result
        if not isinstance(result.get("body"), list):
            return result

        filtered = ResponseFilter.filter_body(result["body"], cmd, io_no, mo_no, oper_desc)
        raw = json.dumps(filtered, ensure_ascii=False)

        result = dict(result)
        result["body"] = filtered
        result["raw"] = raw
        result["record_count"] = ResponseFilter.count_records(filtered)
        result["filtered"] = True
        result["filter_IONo"] = io_no if cmd == "MfgOrders" else None
        result["filter_MONo"] = mo_no
        result["filter_OperDesc"] = oper_desc if cmd == "OperBull" else None
        return result

    @staticmethod
    def filter_body(
        body: list[Any], cmd: str, io_no: str | None, mo_no: str | None, oper_desc: str | None = None
    ) -> list[Any]:
        if cmd == "OperBull":
            if not (oper_desc or "").strip():
                return body
        elif not ResponseFilter.has_filters_for_command(cmd, io_no, mo_no):
            return body

        filtered: list[Any] = []
        for group in body:
            if not isinstance(group, list):
                continue
            rows = [
                row
                for row in group
                if isinstance(row, dict)
                and ResponseFilter._row_matches(row, cmd, io_no, mo_no, oper_desc)
            ]
            if rows:
                filtered.append(rows)
        return filtered

    @staticmethod
    def _row_matches(
        row: dict[str, Any],
        cmd: str,
        io_no: str | None,
        mo_no: str | None,
        oper_desc: str | None = None,
    ) -> bool:
        if cmd == "MfgOrders":
            if io_no:
                value = str(row.get("IONo") or row.get("IONO") or "").strip()
                if not ResponseFilter._like_match(value, io_no):
                    return False
            if mo_no:
                value = str(row.get("MONo") or row.get("MONO") or "").strip()
                if not ResponseFilter._like_match(value, mo_no):
                    return False
            return True

        if cmd == "ProdPlan" and mo_no:
            value = str(row.get("MONo") or row.get("MONO") or "").strip()
            return ResponseFilter._like_match(value, mo_no)

        if cmd == "OperBull" and oper_desc:
            value = str(row.get("OperDesc") or "").strip()
            return ResponseFilter._like_match(value, oper_desc)

        return True

    @staticmethod
    def _like_match(value: str, needle: str) -> bool:
        return not needle or needle.lower() in value.lower()

    @staticmethod
    def count_records(body: Any) -> int | None:
        if not isinstance(body, list):
            return None
        count = sum(len(group) for group in body if isinstance(group, list))
        return count if count > 0 else 0
