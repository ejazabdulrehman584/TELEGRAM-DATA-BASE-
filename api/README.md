# 🚀 Premium Telegram OSINT API — Full Render Deployment Guide

A **direct** Telegram ID / Username / Phone → Country & Identity API.
Response format is identical in spirit to `felix-info-x-bot`:

```json
{
  "success": true,
  "developer": "@cloud_computings_bot",
  "took_ms": 0.38,
  "data": {
    "tg_id": 551348190,
    "username": "",
    "first_name": "",
    "last_name": "",
    "phone": "+79647416479",
    "national": "9647416479",
    "country": "Russia",
    "country_code": "+7",
    "iso2": "RU",
    "flag": "🇷🇺",
    "source": "iraq_extracted_pipe",
    "matched_by": "id",
    "query": "551348190"
  }
}
```

Not found / errors:

```json
{ "success": false, "developer": "@cloud_computings_bot", "took_ms": 4.87,
  "message": "Not found", "data": null }
```

---

## 🔒 Security model (no DB can be found)

* **No** `/db`, `/dump`, `/list`, `/export`, `/stats`, `/openapi.json`, `/docs`, `/redoc`.
* OpenAPI/Swagger **disabled** (`openapi_url=None`, `docs_url=None`, `redoc_url=None`).
* Only **single-value lookups** are possible — there is no way to enumerate the database.
* `/health` returns only `{"status":"ok"}` (nothing about the data).
* Every lookup requires a valid **API key**.

---

## 📦 What is in this folder

| File | Purpose |
|------|---------|
| `server.py` | The FastAPI app (all endpoints + premium landing page) |
| `country.py` | Phone → country detection (E.164 calling-code table) |
| `keys.json` | Your API keys (edit to add/remove) |
| `requirements.txt` | Python deps |
| `Dockerfile` | For Docker-based hosting |
| `render.yaml` | One-click Render blueprint |
| `data/tgdata.parquet` | The unified database (9.5M rows, ~91 MB) |

---

## ⚡ Deploy on Render — Method A (Blueprint, recommended)

1. Put this whole folder + `data/tgdata.parquet` into a **GitHub repo**.
   ```
   repo/
     api/            <- everything in this folder
     data/tgdata.parquet
   ```
2. Go to **https://dashboard.render.com** → **New +** → **Blueprint**.
3. Connect your repo. Render reads `api/render.yaml` automatically.
4. Set the env vars (Render will prompt):
   | Key | Value |
   |-----|-------|
   | `TGDATA_PARQUET` | `/opt/render/project/src/data/tgdata.parquet` |
   | `BOT_TOKEN` | `8830055380:AAGdtxtpmRSp--Eoiph98TEa617IpFuS39s` |
   | `BOT_USERNAME` | `cloud_computings_bot` |
   | `DEVELOPER` | `@cloud_computings_bot` |
   | `MASTER_KEY` | (any strong secret) |
5. Click **Apply**. Wait ~2 min. Your API is live at
   `https://<your-service>.onrender.com`.

## ⚡ Deploy on Render — Method B (Manual Web Service)

1. **New +** → **Web Service** → connect repo.
2. **Root Directory:** `api`
3. **Runtime:** `Python 3`
4. **Build Command:** `pip install -r requirements.txt`
5. **Start Command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`
6. **Health Check Path:** `/health`
7. Add the same env vars as above → **Create Web Service**.

## ⚡ Deploy on Render — Method C (Docker)

1. **New +** → **Web Service** → **Deploy an existing image / Dockerfile**.
2. Root Directory: `api`, Dockerfile path: `api/Dockerfile`.
3. Add env vars → deploy.

> **Important:** Render's free disk is ephemeral. Keep `data/tgdata.parquet`
> inside the repo (91 MB < GitHub's 100 MB limit) so it is present at build time.
> If you later exceed 100 MB, use a **Render Disk** and set `TGDATA_PARQUET`
> to the disk mount path, or host the parquet on S3 and point `TGDATA_PARQUET`
> to an `https://…` URL (DuckDB can read remote parquet).

---

## 🧪 Test calls (after deploy)

```bash
# by numeric Telegram id  (felix path style)
curl "https://YOUR-APP.onrender.com/key=premium&tg=551348190"

# by username
curl "https://YOUR-APP.onrender.com/api?key=premium&tg=@rozagjabrailova22"

# by phone (reverse lookup)
curl "https://YOUR-APP.onrender.com/tg/+79647416479?key=premium"

# versioned
curl "https://YOUR-APP.onrender.com/v1/lookup?key=premium&tg=551348190"
```

### Verified working test IDs (in this database)

| Query | Result |
|-------|--------|
| `551348190` | 🇷🇺 Russia · +79647416479 |
| `4591522` | 🇧🇷 Brazil · +5547999606822 |
| `@rozagjabrailova22` | 🆔 5286484075 · Роза |
| `+79647416479` | 🆔 551348190 · 🇷🇺 Russia |

---

## 🔑 API keys

Edit `keys.json`:

```json
{ "keys": { "premium": {"plan":"premium"}, "yourkey": {"plan":"premium"} } }
```

Or set `MASTER_KEY` env var for a single master key.

---

## 🗄️ Database schema (`data/tgdata.parquet`)

| Column | Type | Notes |
|--------|------|-------|
| `tg_id` | BIGINT | Telegram numeric id |
| `username` | VARCHAR | lower-case, no `@` |
| `first_name` / `last_name` | VARCHAR | |
| `phone` | VARCHAR | digits only, E.164 |
| `email` | VARCHAR | |
| `linked_id` / `linked_name` | VARCHAR | |
| `source` | VARCHAR | origin tag |

Built from: `TGDATA_BY_DEADLOX_P4.parquet` (107M rows), `master_index.csv`,
`Telegram_Chelabinsk_*.csv`, `Telegram_(2).txt` → de-duplicated to **9,512,929 rows**.

---

## 🛠️ Rebuild the database

```bash
pip install duckdb pandas pyarrow
python3 build_db.py          # writes data/tgdata.parquet
```

---

## 🖥️ Run locally

```bash
cd api
pip install -r requirements.txt
PORT=8090 python3 server.py
# open http://127.0.0.1:8090/
```
