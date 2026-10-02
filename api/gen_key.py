#!/usr/bin/env python3
"""
gen_key.py -- create time-limited (auto-expiring) API keys for server.py

Usage:
    python3 gen_key.py                      # random key, expires in 10 days
    python3 gen_key.py --days 10            # expires in 10 days
    python3 gen_key.py --days 10 --name trial10
    python3 gen_key.py --days 30 --name vip30 --plan premium
    python3 gen_key.py --list               # show all keys + expiry
    python3 gen_key.py --revoke trial10     # delete a key

Keys are stored in keys.json next to this file:
{
  "keys": {
     "trial10": {"plan": "trial", "expires_at": "2026-10-12T06:00:00+00:00",
                 "created_at": "2026-10-02T06:00:00+00:00", "days": 10}
  }
}
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import string
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS_FILE = os.environ.get("API_KEYS_FILE", os.path.join(HERE, "keys.json"))


def _load():
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and "keys" in d:
            return d
    except Exception:
        pass
    return {"keys": {}}


def _save(d):
    with open(KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _rand(n=16):
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def cmd_new(args):
    d = _load()
    name = args.name or ("key_" + _rand(12))
    if name in d["keys"] and not args.force:
        print(f"! key '{name}' already exists (use --force to overwrite)")
        return
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=args.days)
    d["keys"][name] = {
        "plan": args.plan,
        "created_at": now.isoformat(),
        "expires_at": exp.isoformat(),
        "days": args.days,
    }
    _save(d)
    print("=" * 60)
    print(f"  NEW API KEY      : {name}")
    print(f"  plan             : {args.plan}")
    print(f"  created (UTC)    : {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  EXPIRES (UTC)    : {exp.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  valid for        : {args.days} day(s)")
    print("=" * 60)
    print(f"  test: /key={name}&tg=551348190")


def cmd_list(args):
    d = _load()
    now = datetime.now(timezone.utc)
    print(f"{'KEY':<24} {'PLAN':<10} {'EXPIRES':<22} STATUS")
    print("-" * 72)
    for k, v in d.get("keys", {}).items():
        if isinstance(v, dict):
            exp_s = v.get("expires_at")
            plan = v.get("plan", "-")
        else:
            exp_s, plan = None, "premium"
        if exp_s:
            try:
                exp = datetime.fromisoformat(str(exp_s).replace("Z", "+00:00"))
                status = "EXPIRED" if now > exp else f"active ({int((exp-now).total_seconds()//86400)}d left)"
                exp_disp = exp.strftime("%Y-%m-%d %H:%M")
            except Exception:
                status, exp_disp = "?", str(exp_s)
        else:
            status, exp_disp = "never expires", "-"
        print(f"{k:<24} {plan:<10} {exp_disp:<22} {status}")


def cmd_revoke(args):
    d = _load()
    if args.name in d.get("keys", {}):
        del d["keys"][args.name]
        _save(d)
        print(f"revoked: {args.name}")
    else:
        print(f"not found: {args.name}")


def main():
    p = argparse.ArgumentParser(description="Generate auto-expiring API keys")
    p.add_argument("--days", type=int, default=10, help="days until expiry (default 10)")
    p.add_argument("--name", default=None, help="key name (default: random)")
    p.add_argument("--plan", default="trial", help="plan label (default trial)")
    p.add_argument("--force", action="store_true", help="overwrite if exists")
    p.add_argument("--list", action="store_true", help="list keys")
    p.add_argument("--revoke", metavar="NAME", help="delete a key")
    args = p.parse_args()

    if args.list:
        cmd_list(args)
    elif args.revoke:
        cmd_revoke(args)
    else:
        cmd_new(args)


if __name__ == "__main__":
    main()
