#!/usr/bin/env python3
"""
Command-line usage:
  python cli.py ProdPlan
  python cli.py MfgOrders --IONo=7807630
  python cli.py MfgOrders --MONo=7807630001 --IONo=7807630
  python cli.py OperBull --MONo=7808117004
  python cli.py OperBull --MONo=7808117004 --OperDesc=FINISHING
  python cli.py OperBull --MONo=7808117004 --refresh
  python cli.py MfgOrders --refresh
  python cli.py MfgOrders --out=orders.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from config_loader import load_config
from response_filter import ResponseFilter
from table_renderer import TableRenderer
from verte_api_client import VerteApiClient


def parse_args() -> argparse.Namespace:
    try:
        config = load_config()
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    commands = list((config.get("commands") or {"MfgOrders": "", "ProdPlan": ""}).keys())
    default_cmd = config.get("default_command", "ProdPlan")

    parser = argparse.ArgumentParser(description="Verte API CLI client")
    parser.add_argument(
        "command",
        nargs="?",
        default=default_cmd,
        choices=commands,
        help=f"API command ({'|'.join(commands)})",
    )
    parser.add_argument("--IONo", dest="io_no", default=None, help="Filter by IONo (partial match)")
    parser.add_argument("--MONo", dest="mo_no", default=None, help="Filter by MONo (partial match)")
    parser.add_argument(
        "--OperDesc",
        dest="oper_desc",
        default=None,
        help="Filter by OperDesc (partial match, OperBull)",
    )
    parser.add_argument("--refresh", action="store_true", help="Bypass cache and call the API")
    parser.add_argument("--out", dest="out_file", default=None, help="Save JSON response to file")

    args = parser.parse_args()
    args.config = config
    return args


def main() -> int:
    args = parse_args()
    config = args.config
    cmd = args.command

    filters = ResponseFilter.from_request(
        {"IONo": args.io_no, "MONo": args.mo_no, "OperDesc": args.oper_desc}
    )
    has_filters = ResponseFilter.has_filters_for_command(cmd, filters["IONo"], filters["MONo"])
    api_params = ResponseFilter.api_params_for_command(cmd, filters["IONo"], filters["MONo"])

    if cmd == "OperBull" and not filters["MONo"]:
        print("Error: OperBull requires --MONo", file=sys.stderr)
        return 1

    client = VerteApiClient(config)
    start = time.perf_counter()

    use_cache_copy = (
        not args.refresh
        and not has_filters
        and args.out_file
        and (cache_file := client.get_cached_file_path(cmd, api_params)) is not None
    )

    if use_cache_copy:
        out_path = Path(args.out_file)
        try:
            shutil.copy2(cache_file, out_path)
        except OSError as exc:
            print(f"Error: could not write to {args.out_file}: {exc}", file=sys.stderr)
            return 1

        summary = client.get_cached_summary(cmd, api_params)
        secs = round(time.perf_counter() - start, 2)
        print(f"HTTP 200 in {secs}s (cached)")
        if summary and summary.get("record_count") is not None:
            print(f"Records: {summary['record_count']}")
        print(f"Saved to {args.out_file} ({out_path.stat().st_size:,} bytes)")
        return 0

    if not args.refresh and not has_filters and not args.out_file:
        result = client.get_cached_summary(cmd, api_params)
        if result is None:
            result = client.call(cmd, api_params, args.refresh)
    else:
        result = client.call(cmd, api_params, args.refresh)

    if has_filters and ResponseFilter.should_apply_client_filter(cmd, filters):
        result = ResponseFilter.apply_to_result(
            result, cmd, filters["IONo"], filters["MONo"], filters["OperDesc"]
        )

    secs = round(time.perf_counter() - start, 2)
    status_suffix = ""
    if result.get("from_cache") and not has_filters:
        status_suffix = " (cached)"
    elif ResponseFilter.should_apply_client_filter(cmd, filters):
        status_suffix = " (filtered)"

    print(f"HTTP {result['http_code']} in {secs}s{status_suffix}")

    if result.get("record_count") is not None:
        print(f"Records: {result['record_count']}")

    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    if args.out_file:
        output = result["raw"] if result["raw"] else json.dumps(result["body"], ensure_ascii=False)
        try:
            Path(args.out_file).write_text(output, encoding="utf-8")
        except OSError as exc:
            print(f"Error: could not write to {args.out_file}: {exc}", file=sys.stderr)
            return 1
        print(f"Saved to {args.out_file} ({len(output):,} bytes)")
        return 0 if result["ok"] else 1

    size = int(result.get("raw_size") or len(result.get("raw") or ""))
    if size > 10_000 or result.get("body") is None:
        print(f"Response too large to print ({size:,} bytes). Use --out=file.json")
    elif TableRenderer.can_render(result["body"]):
        priority = TableRenderer.OPER_BULL_COLUMNS if cmd == "OperBull" else None
        print(TableRenderer.render_text(result["body"], priority_columns=priority))
    else:
        output = result["raw"] if result["raw"] else json.dumps(result["body"], indent=2, ensure_ascii=False)
        print(output)

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
