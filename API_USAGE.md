# Verte IMAPPS API — Usage Notes

## 1. API Endpoint

POST https://api-imapps.luenthai.com/GenAPI_VERTE/LTQC/VerteDB/

______________

## 2. Request Format

The API accepts a JSON body request.

### Sample Request Body for Manufacturing Orders

```json
{
  "cmd": "MfgOrders",
  "pAccessKey": "YOUR_ACCESS_KEY_HERE"
}
```

### Sample Request Body for Production Planning

```json
{
  "cmd": "ProdPlan",
  "pAccessKey": "YOUR_ACCESS_KEY_HERE"
}
```

### Sample Request Body for Operations Bulletin

```json
{
  "cmd": "OperBull",
  "pAccessKey": "YOUR_ACCESS_KEY_HERE",
  "pMONo": "7808117004"
}
```

| Command     | Description           | Required parameters        |
|-------------|-----------------------|----------------------------|
| `MfgOrders` | Manufacturing Orders  | `cmd`, `pAccessKey`        |
| `ProdPlan`  | Production Planning   | `cmd`, `pAccessKey`        |
| `OperBull`  | Operations Bulletin   | `cmd`, `pAccessKey`, `pMONo` |

### OperBull notes

- `pMONo` is the manufacturing order number (exact match).
- The response includes an `OperDesc` field (operation description) per row.
- `OperDesc` is returned in the response only — it is **not** sent as a request parameter.

______________

## 3. Required Headers

Please ensure the following headers are included:

```
Content-Type: application/json
Accept: application/json
```

______________

## 4. How to Call (Example — Postman)

- **Method:** POST
- **URL:** https://api-imapps.luenthai.com/GenAPI_VERTE/LTQC/VerteDB/
- **Headers:** `Content-Type: application/json`
- **Body:** Raw → JSON
- **Paste** one of the JSON payloads above
- **Click** Send

### OperBull example (Postman body)

```json
{
  "cmd": "OperBull",
  "pAccessKey": "YOUR_ACCESS_KEY_HERE",
  "pMONo": "7807630001"
}
```

______________

## 5. Notes

- Ensure the `pAccessKey` is kept secure and not exposed in public repositories or client-side applications.
- Only authorized systems should be allowed to call this endpoint.
- If you receive an authentication or access error, verify the access key or coordinate with the system administrator.
- **MfgOrders** returns a large dataset (~37k records) and may take several minutes to respond.
- **OperBull** is scoped to a single MONo via `pMONo`; each MONo requires its own request.
- Passing extra parameters (e.g. `OperDesc`) to **OperBull** will return an error: *"Procedure or function OperBull has too many arguments specified."*

______________

## 6. Using this repository (optional)

This project wraps the same API with a web UI and CLI:

```bash
# Web UI
python app.py

# CLI examples
python cli.py MfgOrders
python cli.py ProdPlan
python cli.py OperBull --MONo=7808117004
python cli.py OperBull --MONo=7808117004 --OperDesc=FINISHING
python cli.py OperBull --MONo=7808117004 --refresh
```

Repository: [github.com/verteai/verte-imapps-api-ext](https://github.com/verteai/verte-imapps-api-ext)
