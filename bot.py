import os
import json
import threading
import psutil
import sys
from datetime import datetime
import pytz
from flask import Flask
import telebot
from telebot import types

# === Конфигурация ===
TOKEN = os.getenv("TOKEN")
PORT = int(os.getenv("PORT", 8000))
ADMINS = [1088460844, 328477968, 7028005668]

if not TOKEN:
    print("❌ TOKEN не задан в переменных окружения")
    sys.exit(1)

# === Пути хранения (перманентные на Timeweb) ===
os.makedirs("/data", exist_ok=True)
DATA_FILE = "/data/data.json" if os.path.exists("/data") else "data.json"
USERS_FILE = "/data/users.json" if os.path.exists("/data") else "users.json"

# === Flask keepalive (для Timeweb) ===
def keepalive():
    app = Flask(__name__)

    @app.route("/")
    def index():
        return "Bot is alive!", 200

    app.run(host="0.0.0.0", port=PORT)

threading.Thread(target=keepalive, daemon=True).start()

# === Проверка дубликатов ===
def already_running():
    current = psutil.Process().pid
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.pid != current and 'python' in (proc.name() or '').lower() and 'bot.py' in ' '.join(proc.info.get('cmdline') or []):
                return True
        except Exception:
            continue
    return False

if already_running():
    print("⚠️ Bot already running, exiting duplicate instance.")
    sys.exit(0)

# === Работа с файлами ===
DEFAULT_ITEMS = {
    "СОЛЕДАР": {"value": "не задано", "updated": None},
    "ВЛАДИМИРОВКА": {"value": "не задано", "updated": None},
    "ПОКРОВСКОЕ": {"value": "не задано", "updated": None},
    "БЕЛГОРОВКА": {"value": "не задано", "updated": None},
    "ЯКОВЛЕВКА": {"value": "не задано", "updated": None},
    "ПОПАСНАЯ": {"value": "не задано", "updated": None},
    "КАМЫШЕВАХА": {"value": "не задано", "updated": None},
    "БЕРЕСТОВОЕ": {"value": "не задано", "updated": None},
    "ТРИПОЛЬЕ": {"value": "не задано", "updated": None},
}

def load_json(path, default):
    if not os.path.exists(path):
        save_json(path, default)
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

menu_items = load_json(DATA_FILE, DEFAULT_ITEMS)
subscribers = load_json(USERS_FILE, [])

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# === Вспомогательные функции ===
def is_admin(uid):
    return uid in ADMINS

def save_all():
    save_json(DATA_FILE, menu_items)
    save_json(USERS_FILE, subscribers)

def now_msk():
    tz = pytz.timezone("Europe/Moscow")
    return datetime.now(tz).strftime("%d.%m.%Y %H:%M")

def emoji_for(val):
    return "🟩" if val == "ЧИСТО" else "🟥" if val == "ГРЯЗНО" else "⬜"

# === Генерация inline-меню ===
def build_live_menu(is_admin=False):
    kb = types.InlineKeyboardMarkup()
    for key, data in menu_items.items():
        val = data["value"]
        emoji = emoji_for(val)
        text = f"{emoji} {key}: {val}"
        if is_admin:
            kb.row(
                types.InlineKeyboardButton("🟩", callback_data=f"s|{key}|C"),
                types.InlineKeyboardButton("🟥", callback_data=f"s|{key}|D"),
            )
        kb.row(types.InlineKeyboardButton(text, callback_data=f"info|{key}"))
    if is_admin:
        kb.row(types.InlineKeyboardButton("➕ Добавить пункт", callback_data="add"))
    kb.row(types.InlineKeyboardButton("🔄 Обновить", callback_data="refresh"))
    return kb

def get_status_list():
    lines = []
    for key, data in menu_items.items():
        emoji = emoji_for(data["value"])
        upd = f"🕓 {data['updated']}" if data["updated"] else "ещё не изменялось"
        lines.append(f"{emoji} <b>{key}</b>: {data['value']} ({upd})")
    return "\n".join(lines)

# === /start ===
@bot.message_handler(commands=["start"])
def start_cmd(m):
    uid = m.from_user.id
    if uid not in subscribers:
        subscribers.append(uid)
        save_json(USERS_FILE, subscribers)
        print(f"👤 Новый подписчик: {uid}")
    text = "📋 Текущий статус пунктов:\n\n" + get_status_list()
    bot.send_message(
        m.chat.id,
        text,
        reply_markup=build_live_menu(is_admin=is_admin(uid)),
        parse_mode="HTML"
    )

# === Inline-коллбеки ===
@bot.callback_query_handler(func=lambda c: c.data.startswith("s|"))
def change_status(c):
    _, key, flag = c.data.split("|")
    if not is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "Нет прав")
    val = "ЧИСТО" if flag == "C" else "ГРЯЗНО"
    timestamp = now_msk()
    menu_items[key] = {"value": val, "updated": timestamp}
    save_json(DATA_FILE, menu_items)

    # уведомление всем подписчикам
    emoji = emoji_for(val)
    msg = f"{emoji} <b>{key}</b>: {val}\n🕓 {timestamp}"
    for uid in list(subscribers):
        try:
            bot.send_message(uid, msg, parse_mode="HTML")
        except Exception as e:
            if "Forbidden" in str(e):
                subscribers.remove(uid)
    save_json(USERS_FILE, subscribers)

    # обновляем меню
    text = "📋 Текущий статус пунктов:\n\n" + get_status_list()
    bot.edit_message_text(
        chat_id=c.message.chat.id,
        message_id=c.message.message_id,
        text=text,
        reply_markup=build_live_menu(is_admin=is_admin(c.from_user.id)),
        parse_mode="HTML"
    )
    bot.answer_callback_query(c.id, f"{key} → {val}")

@bot.callback_query_handler(func=lambda c: c.data == "add")
def add_item_start(c):
    if not is_admin(c.from_user.id):
        return bot.answer_callback_query(c.id, "Нет прав")
    bot.answer_callback_query(c.id)
    msg = bot.send_message(c.message.chat.id, "Введите название нового пункта:")
    bot.register_next_step_handler(msg, add_item_finish)

def add_item_finish(m):
    key = (m.text or "").strip().upper()
    if not key:
        return bot.send_message(m.chat.id, "❗ Пустое название.")
    if key in menu_items:
        return bot.send_message(m.chat.id, "⚠️ Такой пункт уже существует.")
    menu_items[key] = {"value": "не задано", "updated": None}
    save_json(DATA_FILE, menu_items)
    bot.send_message(m.chat.id, f"✅ Добавлен пункт <b>{key}</b>.", parse_mode="HTML")
    text = "📋 Текущий статус пунктов:\n\n" + get_status_list()
    bot.send_message(
        m.chat.id,
        text,
        reply_markup=build_live_menu(is_admin=is_admin(m.from_user.id)),
        parse_mode="HTML"
    )

@bot.callback_query_handler(func=lambda c: c.data == "refresh")
def refresh(c):
    text = "📋 Текущий статус пунктов:\n\n" + get_status_list()
    bot.edit_message_text(
        chat_id=c.message.chat.id,
        message_id=c.message.message_id,
        text=text,
        reply_markup=build_live_menu(is_admin=is_admin(c.from_user.id)),
        parse_mode="HTML"
    )
    bot.answer_callback_query(c.id, "Обновлено")

@bot.callback_query_handler(func=lambda c: c.data.startswith("info|"))
def info(c):
    key = c.data.split("|")[1]
    data = menu_items.get(key)
    if not data:
        return bot.answer_callback_query(c.id, "Нет данных")
    emoji = emoji_for(data["value"])
    upd = data["updated"] or "ещё не изменялось"
    bot.answer_callback_query(c.id, f"{emoji} {key}: {data['value']} ({upd})", show_alert=True)

# === Запуск ===
print("✅ Бот запущен (MSK через pytz, live-режим, сохранение в /data)")
bot.infinity_polling(skip_pending=True)
