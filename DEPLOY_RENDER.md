# 🚀 Render pe Deploy Karne ka Poora Tareeqa (Step-by-Step)

Ye guide aap ko **zero se live API tak** le jayegi. Har step clearly likha hai.

Repo: `https://github.com/ejazabdulrehman584/TELEGRAM-DATA-BASE-`
Repo layout jo Render ko chahiye:

```
TELEGRAM-DATA-BASE-/
├── render.yaml            ← Render blueprint (root pe)
├── api/
│   ├── server.py          ← FastAPI app
│   ├── country.py
│   ├── keys.json
│   ├── gen_key.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── render.yaml
└── data/
    └── tgdata.parquet     ← 90.8 MB database
```

---

## ✅ Step 0 — Pehle ye check karein

1. Aap ka GitHub repo ready hai (files push ho chuki hain). ✅
2. Render account banayein (free): **https://dashboard.render.com/register**
   - "Sign up with GitHub" karein (asaan rahega).
3. GitHub pe Render ko repo access dein (jab Render poochega, "Only select repositories" me `TELEGRAM-DATA-BASE-` tick karein).

---

## 🅰️ TAREEQA A — Blueprint (SABSE ASAAN, 1 click)

`render.yaml` pehle se repo me hai, isliye Render sab kuch khud set kar dega.

### Step A1
Kholein: **https://dashboard.render.com**

### Step A2
Upar daayein **`New +`** button → **`Blueprint`** select karein.

### Step A3
GitHub connect karein (agar pehli baar hai) → repo list me se
**`ejazabdulrehman584/TELEGRAM-DATA-BASE-`** select karein → **`Connect`**.

### Step A4
Render `render.yaml` khud padh lega aur ek service dikhayega:
- **Name:** `tg-osint-api`
- **Root Directory:** `api`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`

### Step A5
Neeche **Blueprint Name** kuch bhi likhein (jaise `tg-osint`) →
**`Apply`** / **`Create`** dabayein.

### Step A6
Deploy shuru ho jayega. **Logs** me dekhein jab tak
`Uvicorn running on http://0.0.0.0:...` na aa jaye (2–4 minute).

### Step A7
Live URL milega, jaise:
```
https://tg-osint-api.onrender.com
```
Test karein:
```
https://tg-osint-api.onrender.com/key=trial10&tg=551348190
```

> ⚠️ Agar Render "MASTER_KEY generateValue" pe pooche to auto-generate kar dega — kuch karne ki zaroorat nahi.

---

## 🅱️ TAREEQA B — Manual Web Service (agar Blueprint na chale)

### Step B1
**https://dashboard.render.com** → **`New +`** → **`Web Service`**.

### Step B2
Repo **`ejazabdulrehman584/TELEGRAM-DATA-BASE-`** connect karein.

### Step B3 — Ye settings bharein (exactly):

| Field | Value |
|-------|-------|
| **Name** | `tg-osint-api` |
| **Region** | jo bhi nazdeek ho (Singapore/Frankfurt) |
| **Branch** | `main` |
| **Root Directory** | `api` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn server:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | `Free` (ya `Starter` for always-on) |
| **Health Check Path** | `/health` |

### Step B4 — Environment Variables add karein
**`Advanced`** → **`Add Environment Variable`** → ye ek-ek karke daalein:

| Key | Value |
|-----|-------|
| `PYTHON_VERSION` | `3.11.9` |
| `TGDATA_PARQUET` | `/opt/render/project/src/data/tgdata.parquet` |
| `DEVELOPER` | `@OSINT_CLONER` |
| `CHANNEL` | `@premiumscriptsbackup` |
| `DUCKDB_MEM` | `400MB` |
| `MASTER_KEY` | koi strong secret (jaise `my-super-secret-123`) |

> `TGDATA_PARQUET` ka path zaroori hai — Render repo ko
> `/opt/render/project/src` me checkout karta hai, isliye parquet
> `/opt/render/project/src/data/tgdata.parquet` pe hota hai.

### Step B5
**`Create Web Service`** dabayein. Build + deploy ~3 minute.

### Step B6
Deploy hone ke baad URL milega: `https://tg-osint-api.onrender.com`
Test karein:
```
https://tg-osint-api.onrender.com/key=trial10&tg=551348190
```

---

## 🐳 TAREEQA C — Docker (optional)

1. **`New +`** → **`Web Service`** → repo connect.
2. **Runtime:** `Docker`.
3. **Root Directory:** `api`
4. **Dockerfile Path:** `api/Dockerfile` (ya `Dockerfile` agar root dir `api` hai).
5. Env vars wahi jo Method B me (TGDATA_PARQUET, DEVELOPER, CHANNEL, DUCKDB_MEM).
6. **Create Web Service**.

---

## 🧪 Deploy ke baad — Test karein

```bash
# ID se
curl "https://tg-osint-api.onrender.com/key=trial10&tg=551348190"

# Username se
curl "https://tg-osint-api.onrender.com/key=premium&tg=@rozagjabrailova22"

# Phone se (reverse)
curl "https://tg-osint-api.onrender.com/key=premium&tg=+79647416479"

# Health
curl "https://tg-osint-api.onrender.com/health"
```

Sahi response aisa aayega:
```json
{
  "success": true,
  "took_ms": 9.5,
  "data": {
    "tg_id": 551348190,
    "phone": "+79647416479",
    "national": "9647416479",
    "country": "Russia",
    "country_code": "+7",
    "iso2": "RU",
    "flag": "🇷🇺",
    "matched_by": "id",
    "query": "551348190"
  },
  "channel": "@premiumscriptsbackup",
  "developer": "@OSINT_CLONER"
}
```

---

## 🔑 Nayi key banane ke liye (expiry ke saath)

Render shell me (Dashboard → service → **Shell** tab) ya locally:

```bash
cd api
python3 gen_key.py --days 10 --name trial10     # 10 din
python3 gen_key.py --days 30 --name vip30       # 30 din
python3 gen_key.py --list                        # saari keys + bache din
python3 gen_key.py --revoke trial10              # delete
```

> **Note:** Render free disk ephemeral hai. `keys.json` me change karne ke
> baad woh restart pe reset ho sakta hai. **Permanent** keys ke liye:
> keys.json ko repo me edit karke push karein, ya `MASTER_KEY` env var use karein.

---

## ⚠️ Zaroori baatein (Common Issues)

| Masla | Hal |
|-------|-----|
| **Free plan pe pehli request slow (~30s)** | Free instances 15 min inactivity ke baad "sleep" ho jate hain. Pehli request cold-start leti hai. Always-on chahiye to **Starter** plan ($7/mo). |
| **"Out of memory" / crash** | Free = 512MB. `DUCKDB_MEM=400MB` set karein (already default). |
| **Database not found error** | `TGDATA_PARQUET` galat path. Sahi: `/opt/render/project/src/data/tgdata.parquet` |
| **Build fail: file too large** | Parquet 90.8MB hai (< GitHub 100MB limit). Agar future me 100MB+ ho jaye to Git LFS ya S3 use karein. |
| **Root "/" pe web page nahi** | Ye jaan-boojh kar hai — API-only hai. Root plain JSON deta hai. |
| **Auto-deploy** | `render.yaml` me `autoDeploy: true` hai — GitHub pe push karte hi Render khud redeploy karega. |

---

## 📌 Aap ka live endpoint (deploy ke baad)

```
https://<aap-ka-service>.onrender.com/key=YOURKEY&tg=<id|@username|+phone>
```

Bas! Deploy ho gaya. 🎉
