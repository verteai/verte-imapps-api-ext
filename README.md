# verte-imapps-api-ext

Python client and browser UI for the Luenthai **IMAPPS / Verte API** — **MfgOrders**, **ProdPlan**, and **OperBull** with response caching, tabbed filtering, and scrollable table preview.

Repository: [github.com/verteai/verte-imapps-api-ext](https://github.com/verteai/verte-imapps-api-ext)

## Features

- **Web UI** (Flask) — tabbed MfgOrders / ProdPlan / OperBull browser with filters and JSON download
- **CLI** — fetch, filter, and export responses from the terminal
- **Caching** — disk cache with per-command TTLs and optional scheduled warm-up
- **Filters** — partial-match search on IONo / MONo (command-specific)

## Requirements

- Python 3.10+
- Network access to `api-imapps.luenthai.com`
- A valid Verte API `p_access_key`

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/verteai/verte-imapps-api-ext.git
cd verte-imapps-api-ext
python -m venv .venv
```

**Windows (PowerShell)**

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.py config.py
```

**macOS / Linux**

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.py config.py
```

### 2. Configure

Edit `config.py` and set your `p_access_key` if needed (a default `config.py` is included in the repository).

The `cache/` directory is created automatically when responses are cached.

### 3. Run the web UI

```bash
python app.py
```

Open [http://127.0.0.1:5000/](http://127.0.0.1:5000/)

| What | URL |
|------|-----|
| Web UI (default tab: ProdPlan) | http://127.0.0.1:5000/ |
| MfgOrders tab | http://127.0.0.1:5000/?cmd=MfgOrders |
| ProdPlan tab | http://127.0.0.1:5000/?cmd=ProdPlan&fetch=1 |
| OperBull tab | http://127.0.0.1:5000/?cmd=OperBull |

#### Web UI behavior

- **MfgOrders** and **ProdPlan** are separate tabs; each tab remembers its last search when you switch.
- Results render in a scrollable **table**; raw JSON download remains available.
- **MfgOrders** — filter by **IONo** and/or **MONo** (partial match, contains).
- **ProdPlan** — filter by **MONo** only (partial match).
- **OperBull** — operations bulletin for a single **MONo** (sent to the API as `pMONo`), with optional **OperDesc** filter (partial match). Load from cache or **Refresh from API** per MONo.
- **MfgOrders** is large (~37k records). Use filters for a quick preview, or **Load from cache** when a cached copy exists.

## Command line

```bash
python cli.py ProdPlan
python cli.py MfgOrders --IONo=702066
python cli.py MfgOrders --MONo=7020666001
python cli.py OperBull --MONo=7808117004
python cli.py OperBull --MONo=7808117004 --OperDesc=FINISHING
python cli.py OperBull --MONo=7808117004 --refresh
python cli.py MfgOrders --refresh
python cli.py MfgOrders --out=orders.json
```

Small responses print as a text table. Large ones should be saved with `--out=file.json`.

## Warm the cache

**MfgOrders** can take several minutes from the API. Prefetch it overnight or on a schedule:

```bash
python warm_cache.py
python warm_cache.py MfgOrders
```

Cached files are written to `cache/`. TTLs are configurable in `config.py` (`cache_ttl` and `cache_ttl_by_cmd`).

## Project layout

```
verte-imapps-api-ext/
├── app.py              # Web UI (Flask)
├── cli.py              # CLI client
├── warm_cache.py       # Cache prefetch script
├── verte_api_client.py # API + cache layer
├── response_filter.py  # Tab-specific LIKE filters
├── table_renderer.py   # HTML / text table output
├── config_loader.py    # Loads config.py
├── config.example.py   # Sample configuration template
├── config.py           # Active configuration (included in repo)
├── requirements.txt
└── cache/              # Cached API responses (gitignored)
```

## Configuration

| Setting | Purpose |
|---------|---------|
| `p_access_key` | Verte API access key |
| `fetch_on_demand` | When `True`, MfgOrders is not auto-loaded until you fetch or search |
| `preview_row_limit` | Max rows shown in the web table (default 500) |
| `cache_enabled` | Toggle response caching |
| `warm_cache_commands` | Commands warmed by `warm_cache.py` |

Copy `config.example.py` to `config.py` and adjust values for your environment.

## PHP original

This project is a Python port of the Luenthai Verte IMAPPS API client. Behavior and configuration options follow the original PHP implementation.
