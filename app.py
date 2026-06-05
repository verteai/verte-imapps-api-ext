#!/usr/bin/env python3
"""Flask web UI for the Verte API client."""

from __future__ import annotations

import re
import time
from datetime import datetime
from urllib.parse import urlencode

from flask import Flask, Response, redirect, render_template_string, request, session

from config_loader import load_config
from response_filter import ResponseFilter
from table_renderer import TableRenderer
from verte_api_client import VerteApiClient

try:
    CONFIG = load_config()
except FileNotFoundError:
    CONFIG = None

app = Flask(__name__)
app.secret_key = "verte-imapps-change-me-in-production"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IMAPPS — Verte API</title>
    <style>
        body { font-family: system-ui, sans-serif; max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }
        nav a { margin-right: 1rem; }
        nav a.active { font-weight: bold; }
        .tabs { display: flex; gap: 0; border-bottom: 2px solid #ddd; margin: 1.5rem 0 0; }
        .tabs a { padding: 0.65rem 1.25rem; text-decoration: none; color: #555; border-bottom: 2px solid transparent; margin-bottom: -2px; }
        .tabs a:hover { color: #1565c0; background: #f5f5f5; }
        .tabs a.active { color: #1565c0; border-bottom-color: #1565c0; font-weight: bold; }
        .tab-panel { display: none; }
        .tab-panel.active { display: block; }
        pre { background: #f4f4f4; padding: 1rem; overflow: auto; border-radius: 6px; }
        .table-wrap { overflow: auto; max-height: 70vh; border: 1px solid #ddd; border-radius: 6px; }
        .data-table { border-collapse: collapse; width: 100%; font-size: 0.85rem; }
        .data-table th, .data-table td { border: 1px solid #ddd; padding: 0.35rem 0.5rem; text-align: left; white-space: nowrap; }
        .data-table th { background: #e8eaf6; position: sticky; top: 0; z-index: 1; }
        .data-table tbody tr:nth-child(even) { background: #fafafa; }
        .data-table tbody tr:hover { background: #f0f4ff; }
        .meta { color: #555; margin-bottom: 1rem; }
        .error { color: #b00020; }
        .actions { margin: 1rem 0; }
        .actions a, .actions button { margin-right: 1rem; }
        .btn { display: inline-block; padding: 0.4rem 0.9rem; background: #1565c0; color: #fff; text-decoration: none; border-radius: 4px; border: none; font-size: 1rem; cursor: pointer; }
        .btn-secondary { background: #555; }
        .notice { background: #fff8e1; border: 1px solid #ffe082; padding: 1rem; border-radius: 6px; margin: 1rem 0; }
        .cache-hit { color: #2e7d32; }
        .filter-form { display: flex; flex-wrap: wrap; gap: 0.75rem 1.5rem; align-items: flex-end; margin: 1rem 0; padding: 1rem; background: #f8f9fa; border-radius: 6px; }
        .filter-form label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.9rem; }
        .filter-form input { padding: 0.35rem 0.5rem; min-width: 10rem; }
        .filter-hint { font-size: 0.85rem; color: #666; margin: 0 0 0.75rem; }
    </style>
</head>
<body>
    <h1>Verte API Client</h1>
    <p class="meta">
        Endpoint: <code>{{ config.api_url }}</code><br>
        Command: <code>{{ cmd }}</code>
    </p>

    <nav class="tabs">
        {% for command, label in commands.items() %}
            <a href="{{ build_tab_href(command) }}"
               class="{{ 'active' if command == cmd else '' }}"
               title="{{ label }}">
                {{ command }}
            </a>
        {% endfor %}
    </nav>

    <div class="tab-panel active">
        {% if cmd == 'MfgOrders' %}
            <p class="filter-hint">Partial match on IONo or MONo (contains).</p>
            <form class="filter-form" method="get" action="">
                <input type="hidden" name="cmd" value="MfgOrders">
                <input type="hidden" name="fetch" value="1">
                <label>
                    IONo
                    <input type="text" name="IONo" value="{{ filters.IONo or '' }}" placeholder="e.g. 780763">
                </label>
                <label>
                    MONo
                    <input type="text" name="MONo" value="{{ filters.MONo or '' }}" placeholder="e.g. 7807630001">
                </label>
                <button type="submit" class="btn">Search</button>
                {% if has_filters %}
                    <a class="btn btn-secondary" href="?cmd=MfgOrders&amp;clear=1">Clear</a>
                {% endif %}
            </form>
        {% elif cmd == 'ProdPlan' %}
            <p class="filter-hint">Partial match on MONo (contains).</p>
            <form class="filter-form" method="get" action="">
                <input type="hidden" name="cmd" value="ProdPlan">
                <input type="hidden" name="fetch" value="1">
                <label>
                    MONo
                    <input type="text" name="MONo" value="{{ filters.MONo or '' }}" placeholder="e.g. 630016">
                </label>
                <button type="submit" class="btn">Search</button>
                {% if has_filters %}
                    <a class="btn btn-secondary" href="?cmd=ProdPlan&amp;clear=1">Clear</a>
                {% endif %}
            </form>
        {% endif %}
    </div>

    {% if has_filters %}
        <p class="meta">Filtering client-side (partial match)
            {% if cmd == 'MfgOrders' and filters.IONo %} · IONo contains <code>{{ filters.IONo }}</code>{% endif %}
            {% if filters.MONo %} · MONo contains <code>{{ filters.MONo }}</code>{% endif %}
        </p>
    {% endif %}

    {% if result is none and cmd == 'MfgOrders' and fetch_on_demand and not has_filters %}
        <div class="notice">
            <p><strong>MfgOrders</strong> returns ~37k records (~30 MB) and takes 2+ minutes from the API.</p>
            <p>Tip: use <strong>IONo</strong> or <strong>MONo</strong> above to search quickly (partial match, uses cache when available).</p>
            {% if cache_valid %}
                <p class="cache-hit">Cached copy available ({{ cache_age_min }} min old).</p>
                <p class="actions">
                    <a class="btn" href="?cmd=MfgOrders&amp;fetch=1">Load from cache (instant)</a>
                    <a class="btn btn-secondary" href="?cmd=MfgOrders&amp;fetch=1&amp;refresh=1">Refresh from API (slow)</a>
                    <a href="?cmd=MfgOrders&amp;fetch=1&amp;download=1">Download cached JSON</a>
                </p>
            {% else %}
                <p>No cache yet. First load will call the API (slow). Run overnight:
                    <code>python warm_cache.py MfgOrders</code>
                </p>
                <p class="actions">
                    <a class="btn" href="?cmd=MfgOrders&amp;fetch=1">Fetch now (slow)</a>
                </p>
            {% endif %}
        </div>
    {% elif result is not none %}
        <p class="meta">
            HTTP status: <strong>{{ result.http_code }}</strong>
            {% if result.from_cache and not result.filtered %}
                <span class="cache-hit">· from cache ({{ cache_minutes_old }} min old)</span>
            {% elif result.filtered %}
                <span class="cache-hit">· filtered</span>
            {% elif result.attempts > 1 %}
                ({{ result.attempts }} attempts)
            {% endif %}
            {% if result.record_count is not none %}
                · Records: <strong>{{ result.record_count }}</strong>
            {% endif %}
            {% if not result.ok %}<span class="error">(request failed)</span>{% endif %}
        </p>

        <p class="actions">
            <a href="?cmd={{ cmd }}&amp;fetch=1&amp;download=1{{ filter_query }}">Download JSON</a>
            {% if cmd == 'MfgOrders' and not has_filters %}
                <a href="?cmd=MfgOrders&amp;fetch=1&amp;refresh=1">Refresh from API</a>
            {% endif %}
        </p>

        {% if result.error %}
            <p class="error">{{ result.error }}</p>
        {% endif %}

        {% if display_table and table_meta.truncated %}
            <p class="meta">Showing first {{ "{:,}".format(table_meta.shown) }} of {{ "{:,}".format(table_meta.total) }} rows. Use Download JSON for the full dataset.</p>
        {% endif %}

        {% if has_filters and result.ok and result.record_count == 0 %}
            <p class="notice">No records matched your filter. Try a shorter value or refresh the cache.</p>
        {% endif %}

        <h2>Response</h2>
        {% if display_table %}
            {{ display_table | safe }}
        {% else %}
            <pre>{{ display_fallback }}</pre>
        {% endif %}
    {% endif %}
</body>
</html>
"""

MISSING_CONFIG_HTML = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Configuration required</title></head>
<body>
<h1>Configuration required</h1>
<p>Copy <code>config.example.py</code> to <code>config.py</code> and set your <code>p_access_key</code>.</p>
</body>
</html>
"""


def _build_tab_href(command: str) -> str:
    tab_view = session.get("tab_view") or {}
    params: dict[str, str] = {"cmd": command}
    saved = tab_view.get(command)

    if saved is not None:
        params["fetch"] = "1"
        if command == "MfgOrders":
            if saved.get("IONo"):
                params["IONo"] = saved["IONo"]
            if saved.get("MONo"):
                params["MONo"] = saved["MONo"]
        elif command == "ProdPlan" and saved.get("MONo"):
            params["MONo"] = saved["MONo"]
    elif command != "MfgOrders":
        params["fetch"] = "1"

    return "?" + urlencode(params)


def _filter_query(filters: dict, cmd: str) -> str:
    params: dict[str, str] = {}
    if cmd == "MfgOrders":
        if filters.get("IONo"):
            params["IONo"] = filters["IONo"]
        if filters.get("MONo"):
            params["MONo"] = filters["MONo"]
    elif cmd == "ProdPlan" and filters.get("MONo"):
        params["MONo"] = filters["MONo"]

    if not params:
        return ""
    return "&" + urlencode(params)


@app.route("/")
def index() -> Response | str:
    if CONFIG is None:
        return MISSING_CONFIG_HTML, 500

    commands = CONFIG.get("commands") or {"MfgOrders": "MfgOrders", "ProdPlan": "ProdPlan"}
    cmd_keys = list(commands.keys())
    default_cmd = CONFIG.get("default_command", "ProdPlan")
    fetch_on_demand = bool(CONFIG.get("fetch_on_demand", True))

    cmd = request.args.get("cmd", default_cmd)
    if cmd not in cmd_keys:
        cmd = default_cmd if default_cmd in cmd_keys else cmd_keys[0]

    if "clear" in request.args:
        tab_view = session.get("tab_view") or {}
        tab_view.pop(cmd, None)
        session["tab_view"] = tab_view
        redirect_params: dict[str, str] = {"cmd": cmd}
        if cmd != "MfgOrders":
            redirect_params["fetch"] = "1"
        return redirect("?" + urlencode(redirect_params))

    filters = ResponseFilter.from_request(dict(request.args))
    has_filters = ResponseFilter.has_filters_for_command(cmd, filters["IONo"], filters["MONo"])

    force_refresh = "refresh" in request.args
    should_fetch = (
        "fetch" in request.args
        or force_refresh
        or has_filters
        or not fetch_on_demand
        or cmd != "MfgOrders"
    )

    client = VerteApiClient(CONFIG)
    result = None
    cache_valid = False
    cache_age_min = 0

    if should_fetch:
        if has_filters or force_refresh:
            result = client.call(cmd, {}, force_refresh)
        elif cmd == "MfgOrders":
            result = client.get_cached_summary(cmd)
        if result is None:
            result = client.call(cmd, {}, force_refresh)
        if has_filters:
            result = ResponseFilter.apply_to_result(result, cmd, filters["IONo"], filters["MONo"])

        if result is not None:
            tab_view = session.get("tab_view") or {}
            tab_view[cmd] = {"IONo": filters["IONo"], "MONo": filters["MONo"]}
            session["tab_view"] = tab_view
    else:
        cache_valid = client.is_cache_valid(cmd)
        cache_age = client.get_cache_age(cmd)
        cache_age_min = int((cache_age or 0) // 60)

    if "download" in request.args and should_fetch and result is not None:
        raw_payload = result.get("raw") or ""
        if not raw_payload and not has_filters:
            cache_file = client.get_cached_file_path(cmd)
            if cache_file is not None:
                raw_payload = cache_file.read_text(encoding="utf-8")

        if raw_payload:
            suffix = ""
            if filters.get("IONo"):
                suffix += "-IO" + re.sub(r"[^A-Za-z0-9_-]", "", filters["IONo"])
            if filters.get("MONo"):
                suffix += "-MO" + re.sub(r"[^A-Za-z0-9_-]", "", filters["MONo"])
            filename = f"{cmd}{suffix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
            return Response(
                raw_payload,
                mimetype="application/json; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )

    preview_row_limit = int(CONFIG.get("preview_row_limit", 500))
    display_table = None
    display_fallback = ""
    table_meta = {"total": 0, "shown": 0, "truncated": False}

    if result is not None:
        raw_size = int(result.get("raw_size") or len(result.get("raw") or ""))
        if cmd == "MfgOrders" and not has_filters and raw_size > int(CONFIG.get("preview_limit", 80_000)):
            display_fallback = (
                f"Cached manufacturing orders ({result.get('record_count', 0):,} records, {raw_size:,} bytes).\n\n"
                "Preview skipped — dataset is too large to render in the browser.\n"
                "Use Download JSON, or filter by IONo / MONo above for a smaller result."
            )
        elif TableRenderer.can_render(result.get("body")):
            table_meta = TableRenderer.render_html(result["body"], preview_row_limit)
            display_table = table_meta["html"]
        else:
            body = result.get("body")
            if isinstance(body, str):
                display_fallback = body
            else:
                import json

                display_fallback = json.dumps(body, indent=2, ensure_ascii=False)

    cache_minutes_old = 0
    if result and result.get("cached_at"):
        cache_minutes_old = int((time.time() - int(result["cached_at"])) // 60)

    return render_template_string(
        HTML_TEMPLATE,
        config=CONFIG,
        commands=commands,
        cmd=cmd,
        filters=filters,
        has_filters=has_filters,
        fetch_on_demand=fetch_on_demand,
        result=result,
        cache_valid=cache_valid,
        cache_age_min=cache_age_min,
        cache_minutes_old=cache_minutes_old,
        display_table=display_table,
        display_fallback=display_fallback,
        table_meta=table_meta,
        filter_query=_filter_query(filters, cmd),
        build_tab_href=_build_tab_href,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
