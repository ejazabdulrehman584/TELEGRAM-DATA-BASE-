#!/usr/bin/env python3
"""
server.py -- PREMIUM Telegram OSINT API  (Render-ready, drop-in like felix-info-x-bot)

Response format (exactly as requested):
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
      "country": "Russia",
      "country_code": "+7",
      "iso2": "RU",
      "source": "...",
      "matched_by": "id"
  }
}

Endpoints (all return the SAME json shape):
  GET /key=YOURKEY&tg=7543806069          (felix path style)
  GET /api?key=YOURKEY&tg=@durov
  GET /tg/+79647416479?key=YOURKEY
  GET /v1/lookup?key=YOURKEY&tg=551348190

SECURITY: there is NO endpoint that can dump / list / export the database.
Only single lookups are possible. /health returns a minimal ping.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Optional

import duckdb
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

import country as country_mod

# --------------------------------------------------------------------------- config
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PARQUET = os.environ.get("TGDATA_PARQUET", os.path.join(ROOT, "data", "tgdata.parquet"))
KEYS_FILE = os.environ.get("API_KEYS_FILE", os.path.join(HERE, "keys.json"))

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8830055380:AAGdtxtpmRSp--Eoiph98TEa617IpFuS39s")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "cloud_computings_bot")
DEVELOPER = os.environ.get("DEVELOPER", "@" + BOT_USERNAME)
MASTER_KEY = os.environ.get("MASTER_KEY", "")

DEFAULT_KEYS = ["premium", "cloud", "osint", "vip"]


def _load_keys() -> dict:
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "keys" in data:
            return data
        if isinstance(data, list):
            return {"keys": {k: {"plan": "premium"} for k in data}}
    except Exception:
        pass
    return {"keys": {k: {"plan": "premium"} for k in DEFAULT_KEYS}}


KEYS = _load_keys()

# --------------------------------------------------------------------------- db
_lock = threading.Lock()
_con = duckdb.connect()
_con.execute("PRAGMA threads=2")
_con.execute("PRAGMA memory_limit='1800MB'")
_SRC = f"read_parquet('{PARQUET}')"


def _query(sql: str, args=None):
    with _lock:
        return _con.execute(sql, args or []).fetchall()


# --------------------------------------------------------------------------- lookup
def _norm_user(q: str) -> str:
    return q.strip().lstrip("@").lower()


def _pick_row(rows):
    if not rows:
        return None
    def score(r):
        return (1 if r[4] else 0, 1 if r[1] else 0, 1 if r[2] else 0)
    return sorted(rows, key=score, reverse=True)[0]


def _sel():
    return ("SELECT tg_id,username,first_name,last_name,phone,email,source "
            f"FROM {_SRC} WHERE ")


def _by_phone(d):
    return _pick_row(_query(_sel() + "phone = ? LIMIT 20", [d]))


def _by_username(u):
    return _pick_row(_query(_sel() + "username = ? LIMIT 20", [u]))


def _by_id(i):
    return _pick_row(_query(_sel() + "tg_id = ? LIMIT 20", [i]))


def lookup(tg: str):
    q = (tg or "").strip()
    if not q:
        return None
    digits = "".join(c for c in q if c.isdigit())
    if q.startswith("+") and len(digits) >= 8:
        r = _by_phone(digits)
        if r:
            return _row(r, q, "phone")
    if q.startswith("@") or (not q.isdigit()):
        r = _by_username(_norm_user(q))
        if r:
            return _row(r, q, "username")
    if q.isdigit():
        r = _by_id(int(q))
        if r:
            return _row(r, q, "id")
        if len(digits) >= 11:
            r = _by_phone(digits)
            if r:
                return _row(r, q, "phone")
    return None


def _row(r, query, match) -> dict:
    tg_id, username, first_name, last_name, phone, email, source = (
        r[0], r[1] or "", r[2] or "", r[3] or "", r[4] or "", r[5] or "", r[6] or "")
    c = country_mod.detect(phone)
    return {
        "tg_id": tg_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "phone": c["e164"],
        "national": c["national"],
        "country": c["country"],
        "country_code": c["country_code"],
        "iso2": c["iso2"],
        "flag": c["flag"],
        "source": source,
        "matched_by": match,
        "query": query,
    }


# --------------------------------------------------------------------------- app
app = FastAPI(title="Telegram OSINT API", version="1.0.0", docs_url=None,
              redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


def _key_ok(key: Optional[str]):
    if not key:
        return False
    k = str(key).strip()
    if k in KEYS.get("keys", {}):
        return True
    if MASTER_KEY and k == MASTER_KEY:
        return True
    return False


def _resp(success: bool, data, took: float, message: Optional[str] = None):
    body = {"success": success, "developer": DEVELOPER, "took_ms": round(took, 2)}
    if success:
        body["data"] = data
    else:
        body["message"] = message or "Not found"
        body["data"] = None
    return JSONResponse(body)


def _do(key, tg):
    if not _key_ok(key):
        return _resp(False, None, 0.0, "Access denied: invalid API key")
    if not tg:
        return _resp(False, None, 0.0, "Missing 'tg'. Use /key=KEY&tg=<id|@username|+phone>")
    t0 = time.time()
    try:
        res = lookup(tg)
    except Exception as e:
        return _resp(False, None, (time.time() - t0) * 1000, f"lookup error: {e}")
    if not res:
        return _resp(False, None, (time.time() - t0) * 1000, "Not found")
    return _resp(True, res, (time.time() - t0) * 1000)


def _parse_felix_path(path: str):
    out = {}
    p = path.strip("/")
    if not p:
        return out
    for part in p.replace("?", "&").split("&"):
        if "=" in part:
            k, _, v = part.partition("=")
            out[k.strip().lower()] = v
    return out


@app.get("/health")
def health():
    # minimal ping only -- reveals NOTHING about the database
    return {"status": "ok"}


@app.get("/api")
def api_qs(request: Request, key: str = "", tg: str = ""):
    return _do(key, tg)


@app.get("/v1/lookup")
def api_v1(request: Request, key: str = "", tg: str = ""):
    return _do(key, tg)


@app.get("/tg/{q:path}")
def api_tg(q: str, request: Request, key: str = ""):
    return _do(key, q)


@app.get("/", response_class=HTMLResponse)
def index():
    return LANDING_HTML


@app.get("/{path:path}")
def catch_all(path: str, request: Request):
    params = _parse_felix_path(path)
    for k, v in request.query_params.items():
        params.setdefault(k.lower(), v)
    if "tg" in params or "key" in params:
        return _do(params.get("key", ""), params.get("tg", ""))
    if not path:
        return HTMLResponse(LANDING_HTML)
    return _resp(False, None, 0.0, "Unknown endpoint")


LANDING_HTML = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Telegram OSINT API — {DEVELOPER}</title>
<style>
:root{{--bg:#0a0e17;--acc:#22d3ee;--acc2:#a855f7;--txt:#e5e7eb;--mut:#94a3b8}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:radial-gradient(1200px 600px at 20% -10%,#1e293b,var(--bg));color:var(--txt);min-height:100vh;padding:40px 18px}}
.wrap{{max-width:900px;margin:0 auto}}
.hero{{text-align:center;padding:36px 0 20px}}
.badge{{display:inline-block;padding:6px 16px;border-radius:999px;background:linear-gradient(90deg,var(--acc),var(--acc2));color:#04121a;font-weight:700;font-size:12px;letter-spacing:1px;text-transform:uppercase}}
h1{{font-size:40px;margin:16px 0 8px;background:linear-gradient(90deg,#fff,var(--acc));-webkit-background-clip:text;background-clip:text;color:transparent}}
.sub{{color:var(--mut)}}
.card{{background:linear-gradient(180deg,rgba(255,255,255,.04),rgba(255,255,255,.01));border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:22px;margin:16px 0}}
h2{{font-size:17px;margin-bottom:12px;color:var(--acc)}}
.endpoint{{padding:11px 14px;background:#0b1220;border:1px solid rgba(255,255,255,.07);border-radius:12px;margin:8px 0;font-size:14px;font-family:ui-monospace,Consolas,monospace;color:#7dd3fc;word-break:break-all}}
.method{{background:var(--acc);color:#04121a;font-weight:700;border-radius:6px;padding:2px 9px;font-size:12px;margin-right:8px}}
pre{{background:#0b1220;border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:16px;overflow:auto;font-size:13px;color:#a5f3fc}}
.try{{display:flex;gap:10px;flex-wrap:wrap;margin-top:8px}}
input{{flex:1;min-width:180px;padding:12px 14px;border-radius:10px;border:1px solid rgba(255,255,255,.12);background:#0b1220;color:#fff}}
button{{padding:12px 22px;border-radius:10px;border:none;background:linear-gradient(90deg,var(--acc),var(--acc2));color:#04121a;font-weight:700;cursor:pointer}}
.foot{{text-align:center;color:var(--mut);font-size:13px;padding:24px 0}}
</style></head><body><div class="wrap">
<div class="hero"><span class="badge">● Premium OSINT API</span>
<h1>Telegram Lookup API</h1>
<p class="sub">ID · Username · Phone → Country &amp; Identity &nbsp;|&nbsp; {DEVELOPER}</p></div>
<div class="card"><h2>Endpoints</h2>
<div class="endpoint"><span class="method">GET</span>/key=YOURKEY&amp;tg=7543806069</div>
<div class="endpoint"><span class="method">GET</span>/api?key=YOURKEY&amp;tg=@durov</div>
<div class="endpoint"><span class="method">GET</span>/tg/+79647416479?key=YOURKEY</div>
<div class="endpoint"><span class="method">GET</span>/v1/lookup?key=YOURKEY&amp;tg=551348190</div></div>
<div class="card"><h2>Try it</h2>
<div class="try"><input id="k" value="premium"><input id="q" value="551348190"><button onclick="run()">Lookup</button></div>
<pre id="out" style="margin-top:12px">// response appears here</pre></div>
<div class="foot">© {DEVELOPER} — Premium Telegram OSINT API</div></div>
<script>
async function run(){{const k=document.getElementById('k').value.trim(),q=document.getElementById('q').value.trim();const o=document.getElementById('out');o.textContent='// querying...';
try{{const r=await fetch('/key='+encodeURIComponent(k)+'&tg='+encodeURIComponent(q));o.textContent=JSON.stringify(await r.json(),null,2);}}catch(e){{o.textContent='// '+e;}}}}
</script></body></html>"""


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8090"))
    uvicorn.run(app, host="0.0.0.0", port=port)
