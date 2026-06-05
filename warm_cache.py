#!/usr/bin/env python3
"""
Prefetch slow endpoints (run via Task Scheduler / cron).
  python warm_cache.py
  python warm_cache.py MfgOrders
"""

from __future__ import annotations

import sys
import time

from config_loader import load_config
from verte_api_client import VerteApiClient


def main() -> int:
    try:
        config = load_config()
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    to_warm = sys.argv[1] if len(sys.argv) > 1 else None
    cmds = [to_warm] if to_warm else (config.get("warm_cache_commands") or ["MfgOrders"])

    client = VerteApiClient(config)

    for cmd in cmds:
        start = time.perf_counter()
        result = client.call(cmd, {}, force_refresh=True)
        secs = round(time.perf_counter() - start, 1)

        if result.get("error"):
            print(f"{cmd}: failed — {result['error']}", file=sys.stderr)
            continue

        print(f"{cmd}: cached {result.get('record_count')} records in {secs}s")

    return 0


if __name__ == "__main__":
    sys.exit(main())
