#!/usr/bin/env python3
"""
bot_api.py -- PREMIUM Telegram bot front-end for YOUR OWN OSINT API.

The bot talks to your API (api/server.py) and returns rich, premium-formatted
results.  This is the "full premium" client for the API you own.

Run:
    BOT_TOKEN=8830055380:AAGdtxtpmRSp--Eoiph98TEa617IpFuS39s \
    API_BASE=http://127.0.0.1:8090 \
    API_KEY=premium \
    python3 bot_api.py
"""
from __future__ import annotations

import html
import logging
import os

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    LinkPreviewOptions,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters,
)

# --------------------------------------------------------------------------- config
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8830055380:AAGdtxtpmRSp--Eoiph98TEa617IpFuS39s")
API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8090").rstrip("/")
API_KEY = os.environ.get("API_KEY", "premium")
BRAND = os.environ.get("BRAND", "@OSINT_CLONER")
CHANNEL = os.environ.get("CHANNEL", "@premiumscriptsbackup")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",") if x.strip().isdigit()]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

# --------------------------------------------------------------------------- premium emojis
def e(eid: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'

EMO = {
    "search": e("5231012362102487736", "\U0001F50D"),
    "user":   e("5373012449597335010", "\U0001F464"),
    "phone":  e("5373238020301171237", "\U0001F4F1"),
    "globe":  e("5373289296535192315", "\U0001F30D"),
    "id":     e("5373040915083031789", "\U0001F194"),
    "check":  e("5372911337195952965", "\u2705"),
    "cross":  e("5373206748603247232", "\u274C"),
    "fire":   e("5372926611088705163", "\U0001F525"),
    "crown":  e("5372909798593550121", "\U0001F451"),
    "bolt":   e("5373187495384962410", "\u26A1"),
    "stats":  e("5373022998517224111", "\U0001F4CA"),
    "info":   e("5373238020301171237", "\u2139\uFE0F"),
    "shield": e("5372911337195952965", "\U0001F6E1"),
    "megaphone": e("5373238020301171237", "\U0001F4E3"),
}

LINE = "\u2501" * 22


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def fmt_result(q: str, data: dict, took_ms) -> str:
    flag = data.get("flag") or "\U0001F3F3"
    country = data.get("country") or "Unknown"
    cc = data.get("country_code") or "\u2014"
    number = data.get("phone") or "\u2014"
    tg_id = data.get("tg_id") or "\u2014"
    uname = ("@" + data["username"]) if data.get("username") else "\u2014"
    name = " ".join(x for x in [data.get("first_name"), data.get("last_name")] if x) or "\u2014"
    ms = took_ms if took_ms is not None else "?"
    return (
        f"{EMO['fire']} <b>PREMIUM LOOKUP RESULT</b> {EMO['crown']}\n"
        f"{LINE}\n"
        f"{EMO['search']} <b>Query</b> : <code>{esc(q)}</code>\n"
        f"{EMO['id']} <b>TG ID</b> : <code>{esc(tg_id)}</code>\n"
        f"{EMO['user']} <b>Username</b> : <b>{esc(uname)}</b>\n"
        f"{EMO['user']} <b>Name</b> : {esc(name)}\n"
        f"{EMO['phone']} <b>Phone</b> : <code>{esc(number)}</code>\n"
        f"{EMO['globe']} <b>Country</b> : {flag} <b>{esc(country)}</b>  <code>{esc(cc)}</code>\n"
        f"{EMO['bolt']} <b>Speed</b> : <code>{esc(ms)} ms</code>\n"
        f"{LINE}\n"
        f"{EMO['megaphone']} <b>Channel</b> : {CHANNEL}\n"
        f"{EMO['check']} <i>Powered by {BRAND} \u2022 Premium OSINT API</i>"
    )


def fmt_notfound(q: str) -> str:
    return (
        f"{EMO['cross']} <b>NO RESULT FOUND</b>\n"
        f"{LINE}\n"
        f"{EMO['search']} <b>Query</b> : <code>{esc(q)}</code>\n\n"
        f"<i>This target is not in the database. Try another ID / @username / phone.</i>\n"
        f"{EMO['megaphone']} <b>Channel</b> : {CHANNEL}"
    )


START_TEXT = (
    f"{EMO['crown']} <b>PREMIUM OSINT BOT</b> {EMO['fire']}\n"
    f"{LINE}\n"
    f"{EMO['bolt']} Telegram <b>ID</b> \u2192 <b>Phone / Country</b>\n"
    f"{EMO['user']} <b>@username</b> \u2192 identity\n"
    f"{EMO['phone']} <b>phone</b> \u2192 reverse lookup\n\n"
    f"{EMO['search']} <b>Just send me any of these:</b>\n"
    f"  \u2022 <code>7543806069</code>\n"
    f"  \u2022 <code>@durov</code>\n"
    f"  \u2022 <code>+79647416479</code>\n\n"
    f"{EMO['megaphone']} <b>Channel</b> : {CHANNEL}\n"
    f"{EMO['shield']} <i>Powered by {BRAND}</i>"
)


def main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001F50D New Lookup", callback_data="new"),
         InlineKeyboardButton("\U0001F4CA Stats", callback_data="stats")],
        [InlineKeyboardButton("\u2139\uFE0F Help", callback_data="help")],
    ])


# --------------------------------------------------------------------------- handlers
async def cmd_start(update: Update, ctx):
    await update.message.reply_text(
        START_TEXT, parse_mode=ParseMode.HTML,
        reply_markup=main_kb(),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


async def cmd_help(update: Update, ctx):
    await update.message.reply_text(
        START_TEXT, parse_mode=ParseMode.HTML,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


async def cmd_stats(update: Update, ctx):
    await update.message.reply_text(
        f"{EMO['stats']} <b>PREMIUM OSINT API</b>\n"
        f"{LINE}\n"
        f"{EMO['shield']} Brand : <b>{esc(BRAND)}</b>\n"
        f"{EMO['megaphone']} Channel : {CHANNEL}\n"
        f"{EMO['bolt']} Status : <b>online</b>\n"
        f"{EMO['search']} Send any ID / @username / +phone to look up.",
        parse_mode=ParseMode.HTML,
    )


async def on_query(update: Update, ctx):
    q = (update.message.text or "").strip()
    if not q:
        return
    msg = await update.message.reply_text(
        f"{EMO['search']} <i>Searching premium database...</i>",
        parse_mode=ParseMode.HTML,
    )
    import httpx
    try:
        async with httpx.AsyncClient(timeout=40) as c:
            r = await c.get(f"{API_BASE}/api", params={"key": API_KEY, "tg": q})
            j = r.json()
    except Exception as ex:
        await msg.edit_text(f"{EMO['cross']} API error: <code>{esc(ex)}</code>",
                            parse_mode=ParseMode.HTML)
        return
    if j.get("success"):
        await msg.edit_text(fmt_result(q, j.get("data") or {}, j.get("took_ms")),
                            parse_mode=ParseMode.HTML, reply_markup=main_kb())
    else:
        await msg.edit_text(fmt_notfound(q), parse_mode=ParseMode.HTML,
                            reply_markup=main_kb())


async def on_cb(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    if q.data == "new":
        await q.message.reply_text(f"{EMO['search']} Send me an ID, @username or +phone.",
                                   parse_mode=ParseMode.HTML)
    elif q.data == "stats":
        await cmd_stats(q, ctx)
    elif q.data == "help":
        await q.message.reply_text(START_TEXT, parse_mode=ParseMode.HTML)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(on_cb))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_query))
    log.info("Premium OSINT bot started (api=%s)", API_BASE)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
