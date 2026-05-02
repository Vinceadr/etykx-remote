"""
Bot Telegram pour contrôler le PC via langage naturel.
IA : GitHub Models API (GPT-4o) — inclus dans l'abonnement GitHub Copilot.
"""

import asyncio
import json
import io
import os
import subprocess
import sys
import time
import logging
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)
from openai import AsyncOpenAI
import mss
from PIL import Image
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController

# ── Config ─────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN", "")
ALLOWED_USER_ID  = int(os.getenv("ALLOWED_USER_ID", "0"))
AI_MODEL         = os.getenv("AI_MODEL", "gpt-4o-mini")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

if not TELEGRAM_TOKEN or not GITHUB_TOKEN:
    log.error("TELEGRAM_TOKEN et GITHUB_TOKEN doivent être définis dans .env !")
    sys.exit(1)

# ── PC controllers ─────────────────────────────────────────────────────
mouse_ctrl    = MouseController()
keyboard_ctrl = KeyboardController()

with mss.mss() as _sct:
    _mon      = _sct.monitors[1]
    SCREEN_W  = _mon["width"]
    SCREEN_H  = _mon["height"]

# ── GitHub Models AI client ─────────────────────────────────────────────
ai_client = AsyncOpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=GITHUB_TOKEN,
)

# ── Conversation memory (per user) ─────────────────────────────────────
_conversations: dict[int, list[dict]] = {}

SYSTEM_PROMPT = f"""Tu es Interception, un assistant IA personnel connecté au PC Windows de ton propriétaire.
Tu as DEUX rôles fusionnés en un :

1. ASSISTANT COPILOT — comme GitHub Copilot : tu réponds aux questions de code, d'architecture,
   d'informatique, de cybersécurité, de scripts, et à toute question générale. Tu es expert,
   précis, et tu donnes des exemples concrets avec du code si besoin.

2. CONTRÔLEUR PC — tu peux exécuter des actions sur le PC (résolution : {SCREEN_W}x{SCREEN_H}).

Tu réponds TOUJOURS avec du JSON valide UNIQUEMENT, structure :
{{
  "thought": "raisonnement : est-ce une question/conversation OU une action PC ?",
  "action": "nom_action",
  "params": {{}},
  "confirm": false,
  "confirm_message": "",
  "response": "réponse complète pour l'utilisateur (markdown Telegram autorisé)"
}}

═══ ACTIONS PC ═══
- "screenshot"    : capture d'écran          | params: {{}}
- "type_text"     : tape du texte             | params: {{"text": "..."}}
- "key_combo"     : raccourci clavier         | params: {{"combo": "ctrl+c"}}
- "launch_app"    : ouvre une application     | params: {{"cmd": "..."}}  → confirm=true
- "media"         : contrôle médias           | params: {{"action": "play_pause|next|prev|mute|vol_up|vol_down"}}
- "shell_command" : commande shell Windows    | params: {{"cmd": "..."}}  → confirm=true OBLIGATOIRE
- "chat"          : répondre sans action PC   | params: {{}}

═══ APPLICATIONS CONNUES ═══
- CyberWatch  : cyberwatch/dist/CyberWatch/CyberWatch.exe
- Chrome      : start chrome
- Firefox     : start firefox
- Notepad     : notepad
- Explorateur : explorer
- Calculatrice: calc
- Gestionnaire des taches : taskmgr

═══ DÉTECTION D'INTENTION ═══
• Message = question/conversation/code/conseil → action "chat", réponds en détail dans "response"
• Message = demande d'action sur le PC → action PC correspondante
• En cas de doute → action "chat" et demande des précisions

═══ RÈGLES ═══
• "launch_app" et "shell_command" → confirm=true avec confirm_message clair
• Actions simples (media, screenshot, type_text) → confirm=false
• Pour "chat" : réponds en markdown Telegram (*gras*, `code`, ```bloc```)
• Parle toujours en français sauf si l'utilisateur écrit dans une autre langue
• Sois expert, précis et concis
• Pour les apps connues, utilise TOUJOURS le chemin exact ci-dessus
"""

# ── Pending confirmations store ─────────────────────────────────────────
_pending: dict[str, dict] = {}   # callback_data -> action_dict


# ── PC action executor ──────────────────────────────────────────────────
SPECIAL_KEYS = {
    "enter": Key.enter, "backspace": Key.backspace, "tab": Key.tab,
    "escape": Key.esc, "esc": Key.esc, "delete": Key.delete,
    "home": Key.home, "end": Key.end, "pageup": Key.page_up,
    "pagedown": Key.page_down, "up": Key.up, "down": Key.down,
    "left": Key.left, "right": Key.right, "space": Key.space,
    "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
    "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
    "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
    "win": Key.cmd, "cmd": Key.cmd,
}

MEDIA_KEYS = {
    "play_pause": Key.media_play_pause,
    "next":       Key.media_next,
    "prev":       Key.media_previous,
    "mute":       Key.media_volume_mute,
    "vol_up":     Key.media_volume_up,
    "vol_down":   Key.media_volume_down,
}


def take_screenshot(quality: int = 60) -> bytes:
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()


def press_combo(combo: str):
    parts = [p.strip().lower() for p in combo.split("+")]
    modifiers = []
    for part in parts[:-1]:
        if part == "ctrl":  modifiers.append(Key.ctrl)
        elif part == "alt": modifiers.append(Key.alt)
        elif part == "shift": modifiers.append(Key.shift)
        elif part in ("win", "cmd"): modifiers.append(Key.cmd)
    final = parts[-1]
    for m in modifiers:
        keyboard_ctrl.press(m)
    if final in SPECIAL_KEYS:
        keyboard_ctrl.press(SPECIAL_KEYS[final])
        keyboard_ctrl.release(SPECIAL_KEYS[final])
    else:
        keyboard_ctrl.press(final)
        keyboard_ctrl.release(final)
    for m in reversed(modifiers):
        keyboard_ctrl.release(m)


async def execute_action(action: dict) -> tuple[str, bytes | None]:
    """Execute an action and return (text_result, optional_image_bytes)."""
    name   = action.get("action", "none")
    params = action.get("params", {})

    if name == "screenshot":
        img = take_screenshot()
        return "📸 Capture d'écran :", img

    elif name == "type_text":
        text = params.get("text", "")
        keyboard_ctrl.type(text)
        return f"⌨️ Texte tapé : `{text}`", None

    elif name == "key_combo":
        combo = params.get("combo", "")
        press_combo(combo)
        return f"⌨️ Raccourci exécuté : `{combo}`", None

    elif name == "launch_app":
        cmd = params.get("cmd", "")
        subprocess.Popen(cmd, shell=True)
        return f"🚀 Lancé : `{cmd}`", None

    elif name == "media":
        media_action = params.get("action", "play_pause")
        key = MEDIA_KEYS.get(media_action)
        if key:
            keyboard_ctrl.press(key)
            keyboard_ctrl.release(key)
        emojis = {"play_pause":"⏯","next":"⏭","prev":"⏮","mute":"🔇","vol_up":"🔊","vol_down":"🔉"}
        return f"{emojis.get(media_action,'🎵')} Média : {media_action}", None

    elif name == "shell_command":
        cmd = params.get("cmd", "")
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            output = (result.stdout + result.stderr).strip()
            return f"💻 `{cmd}`\n\n```\n{output[:1500]}\n```", None
        except subprocess.TimeoutExpired:
            return f"⚠️ Timeout : `{cmd}`", None

    elif name in ("none", "chat"):
        return action.get("response", "✅ Ok"), None

    return f"❓ Action inconnue : {name}", None


# ── AI query ─────────────────────────────────────────────────────────────
async def query_ai(user_id: int, message: str) -> dict:
    history = _conversations.setdefault(user_id, [])
    history.append({"role": "user", "content": message})

    # Keep last 20 messages
    if len(history) > 20:
        history[:] = history[-20:]

    try:
        resp = await ai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        action = json.loads(raw)
        history.append({"role": "assistant", "content": raw})
        return action
    except json.JSONDecodeError as e:
        log.error("JSON decode error: %s", e)
        return {"action": "none", "params": {}, "confirm": False,
                "response": "❌ Erreur interne (réponse IA invalide)."}
    except Exception as e:
        log.error("AI error: %s", e)
        return {"action": "none", "params": {}, "confirm": False,
                "response": f"❌ Erreur IA : {e}"}


# ── Auth guard ──────────────────────────────────────────────────────────
def is_authorized(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else 0
    if ALLOWED_USER_ID == 0:
        # First run — print the user ID so they can configure it
        log.warning("⚠️  ALLOWED_USER_ID non configuré. User ID: %d", uid)
        return True
    return uid == ALLOWED_USER_ID


# ── Telegram handlers ───────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    uid = update.effective_user.id
    await update.message.reply_text(
        f"👋 Bonjour ! Je suis ton assistant PC.\n\n"
        f"💡 Parle-moi naturellement :\n"
        f"  • *Ouvre Chrome*\n"
        f"  • *Prends un screenshot*\n"
        f"  • *Lance Spotify et mets de la musique*\n"
        f"  • *Tape 'Bonjour' dans la fenêtre active*\n"
        f"  • *Appuie sur Ctrl+Z*\n\n"
        f"🔑 Ton Telegram ID : `{uid}`\n"
        f"  _(à mettre dans .env → ALLOWED_USER_ID)_",
        parse_mode="Markdown",
    )


async def cmd_screenshot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    msg = await update.message.reply_text("📸 Capture en cours…")
    img = take_screenshot()
    await update.message.reply_photo(photo=img, caption="Voici ton écran !")
    await msg.delete()


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    await update.message.reply_text(
        "🤖 *Interception — Ton assistant PC*\n\n"
        "*Commandes :*\n"
        "/screenshot — Capture d'écran\n"
        "/clear — Effacer l'historique\n"
        "/help — Aide\n\n"
        "*Contrôle PC :*\n"
        "• _Ouvre CyberWatch_\n"
        "• _Prends un screenshot_\n"
        "• _Monte le volume_\n"
        "• _Appuie sur Ctrl+Z_\n\n"
        "*Assistant Copilot :*\n"
        "• _Comment faire un loop en Python ?_\n"
        "• _Explique-moi les injections SQL_\n"
        "• _Écris-moi un script PowerShell pour..._\n"
        "• _C'est quoi un buffer overflow ?_\n\n"
        "Je détecte automatiquement si c'est une question ou une action PC 🧠",
        parse_mode="Markdown",
    )


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    uid = update.effective_user.id
    _conversations.pop(uid, None)
    await update.message.reply_text("🗑️ Historique effacé !")


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("⛔ Accès refusé.")
        return

    user_id = update.effective_user.id
    text = update.message.text or ""

    # Typing indicator
    await ctx.bot.send_chat_action(update.effective_chat.id, "typing")

    action = await query_ai(user_id, text)
    log.info("Action: %s | Confirm: %s", action.get("action"), action.get("confirm"))

    # Send AI thought/response first if any
    ai_response = action.get("response", "")

    if action.get("confirm"):
        # Ask for confirmation with inline buttons
        confirm_msg = action.get("confirm_message") or f"Exécuter : *{action.get('action')}* ?"
        key = f"conf_{user_id}_{int(time.time())}"
        _pending[key] = action

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Oui, exécute", callback_data=f"yes:{key}"),
            InlineKeyboardButton("❌ Non, annule",  callback_data=f"no:{key}"),
        ]])
        full_msg = (f"{ai_response}\n\n" if ai_response else "") + f"⚠️ {confirm_msg}"
        await update.message.reply_text(full_msg, reply_markup=keyboard, parse_mode="Markdown")

    else:
        action_name = action.get("action", "none")
        # Chat/conversational response — send with Markdown formatting
        if action_name in ("chat", "none"):
            await update.message.reply_text(
                ai_response or "...",
                parse_mode="Markdown",
            )
        else:
            # PC action — execute and report
            if ai_response:
                await update.message.reply_text(ai_response, parse_mode="Markdown")
            result_text, result_img = await execute_action(action)
            if result_img:
                await update.message.reply_photo(photo=result_img, caption=result_text)
            elif result_text and result_text != ai_response:
                await update.message.reply_text(result_text, parse_mode="Markdown")


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    if ":" not in data:
        return

    decision, key = data.split(":", 1)

    if decision == "no":
        _pending.pop(key, None)
        await query.edit_message_text("❌ Action annulée.")
        return

    action = _pending.pop(key, None)
    if not action:
        await query.edit_message_text("⚠️ Action expirée ou déjà traitée.")
        return

    await query.edit_message_text("⏳ Exécution en cours…")
    result_text, result_img = await execute_action(action)

    if result_img:
        await ctx.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=result_img,
            caption=result_text,
        )
    else:
        await ctx.bot.send_message(
            chat_id=query.message.chat_id,
            text=result_text,
            parse_mode="Markdown",
        )


# ── Main ────────────────────────────────────────────────────────────────
def main():
    log.info("Démarrage du bot Telegram RemoteControl…")

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("screenshot", cmd_screenshot))
    app.add_handler(CommandHandler("help",       cmd_help))
    app.add_handler(CommandHandler("clear",      cmd_clear))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Bot en attente de messages…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()






