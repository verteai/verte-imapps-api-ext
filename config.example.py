"""
Copy this file to config.py and set your access key.
"""

CONFIG = {
    "api_url": "https://api-imapps.luenthai.com/GenAPI_VERTE/LTQC/VerteDB/",
    "p_access_key": "YOUR_ACCESS_KEY_HERE",
    "commands": {
        "MfgOrders": "Manufacturing Orders",
        "ProdPlan": "Production Planning",
    },
    "default_command": "ProdPlan",
    "fetch_on_demand": True,
    "timeout": 300,
    "retries": 2,
    "request_params": {},
    "preview_limit": 80_000,
    "preview_row_limit": 500,
    "cache_enabled": True,
    "cache_ttl": 3600,
    "cache_ttl_by_cmd": {
        "MfgOrders": 14_400,
        "ProdPlan": 900,
    },
    "warm_cache_commands": ["MfgOrders"],
}
