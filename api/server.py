#!/usr/bin/env python3
"""
server.py -- PREMIUM Telegram OSINT API  (Render-ready, drop-in like felix-info-x-bot)

Response format (exactly as requested):
{
  "success": true,
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
      "flag": "\ud83c\uddf7\ud83c\uddfa",
      "matched_by": "id",
      "query": "551348190"
  },
  "channel": "@premiumscriptsbackup",
  "developer": "@OSINT_CLONER"
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
from fastapi.responses import JSONResponse

import country as country_mod

# --------------------------------------------------------------------------- config
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PARQUET = os.environ.get("TGDATA_PARQUET", os.path.join(ROOT, "data", "tgdata.parquet"))
KEYS_FILE = os.environ.get("API_KEYS_FILE", os.path.join(HERE, "keys.json"))

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8830055380:AAGdtxtpmRSp--Eoiph98TEa617IpFuS39s")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "cloud_computings_bot")
DEVELOPER = os.environ.get("DEVELOPER", "@OSINT_CLONER")
CHANNEL = os.environ.get("CHANNEL", "@premiumscriptsbackup")
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
    body = {"success": success, "took_ms": round(took, 2)}
    if success:
        body["data"] = data
    else:
        body["message"] = message or "Not found"
        body["data"] = None
    body["channel"] = CHANNEL
    body["developer"] = DEVELOPER
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


@app.get("/")
def index():
    # API-ONLY: there is no web page. Root returns a tiny JSON banner.
    return {
        "status": "ok",
        "service": "Telegram OSINT API",
        "developer": DEVELOPER,
        "channel": CHANNEL,
        "usage": "/key=YOURKEY&tg=<id|@username|+phone>",
    }


@app.get("/{path:path}")
def catch_all(path: str, request: Request):
    params = _parse_felix_path(path)
    for k, v in request.query_params.items():
        params.setdefault(k.lower(), v)
    if "tg" in params or "key" in params:
        return _do(params.get("key", ""), params.get("tg", ""))
    return _resp(False, None, 0.0, "Unknown endpoint")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8090"))
    uvicorn.run(app, host="0.0.0.0", port=port)
