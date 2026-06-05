"""HTML and text table rendering for API responses."""

from __future__ import annotations

import html
import json
from typing import Any


class TableRenderer:
    @staticmethod
    def flatten_body(body: Any) -> list[dict[str, Any]]:
        if not isinstance(body, list) or not body:
            return []

        first = body[0]
        if isinstance(first, dict) and TableRenderer._is_assoc_row(first):
            return [row for row in body if isinstance(row, dict)]

        rows: list[dict[str, Any]] = []
        for group in body:
            if not isinstance(group, list):
                continue
            for row in group:
                if isinstance(row, dict):
                    rows.append(row)
        return rows

    @staticmethod
    def can_render(body: Any) -> bool:
        return bool(TableRenderer.flatten_body(body))

    @staticmethod
    def columns(rows: list[dict[str, Any]]) -> list[str]:
        if not rows:
            return []

        columns = list(rows[0].keys())
        seen = set(columns)

        for row in rows:
            for key in row:
                if key not in seen:
                    columns.append(key)
                    seen.add(key)
        return columns

    @staticmethod
    def render_html(body: Any, limit: int = 500) -> dict[str, Any]:
        rows = TableRenderer.flatten_body(body)
        total = len(rows)
        truncated = total > limit
        shown = limit if truncated else total
        slice_rows = rows[:limit] if truncated else rows
        columns = TableRenderer.columns(slice_rows)

        if not columns:
            return {"html": "", "total": 0, "shown": 0, "truncated": False}

        parts = ['<div class="table-wrap"><table class="data-table"><thead><tr>']
        for col in columns:
            parts.append(f"<th>{html.escape(str(col))}</th>")
        parts.append("</tr></thead><tbody>")

        for row in slice_rows:
            parts.append("<tr>")
            for col in columns:
                cell = TableRenderer._format_cell(row.get(col))
                parts.append(f"<td>{html.escape(cell)}</td>")
            parts.append("</tr>")

        parts.append("</tbody></table></div>")

        return {
            "html": "".join(parts),
            "total": total,
            "shown": shown,
            "truncated": truncated,
        }

    @staticmethod
    def render_text(body: Any, limit: int = 200) -> str:
        rows = TableRenderer.flatten_body(body)
        if not rows:
            return ""

        total = len(rows)
        truncated = total > limit
        slice_rows = rows[:limit] if truncated else rows
        columns = TableRenderer.columns(slice_rows)
        widths = {col: min(24, max(len(col), 4)) for col in columns}

        for row in slice_rows:
            for col in columns:
                cell = TableRenderer._format_cell(row.get(col))
                widths[col] = min(24, max(widths[col], len(cell)))

        lines = [
            TableRenderer._text_row(columns, columns, widths),
            TableRenderer._text_rule(columns, widths),
        ]
        for row in slice_rows:
            values = [TableRenderer._format_cell(row.get(col)) for col in columns]
            lines.append(TableRenderer._text_row(columns, values, widths))

        if truncated:
            lines.extend(["", f"... showing {limit} of {total} rows — use --out=file.json for full data"])

        return "\n".join(lines)

    @staticmethod
    def _text_row(columns: list[str], values: list[str], widths: dict[str, int]) -> str:
        parts = []
        for i, col in enumerate(columns):
            value = values[i] if i < len(values) else ""
            width = widths[col]
            if len(value) > width:
                value = value[: max(0, width - 1)] + "…"
            parts.append(value.ljust(width))
        return "  ".join(parts)

    @staticmethod
    def _text_rule(columns: list[str], widths: dict[str, int]) -> str:
        return "  ".join("-" * widths[col] for col in columns)

    @staticmethod
    def _format_cell(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, (str, int, float)):
            return str(value)
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _is_assoc_row(arr: dict[str, Any]) -> bool:
        return any(isinstance(key, str) for key in arr)
