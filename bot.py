import os
import json
import threading
import psutil
import sys
import pytz
from datetime import datetime
import telebot
from telebot import types

# 🕒 Московский часовой пояс
MSK = pytz.timezone("Europe/Moscow")

# === НАСТРОЙКИ ===
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN не задан в переменных окружения")
    sys.exit(1)

os.makedirs("/data", exist_ok=True)
DATA_FILE = "/data/data.json" if os.path.exists("/data") else "data.json"
USERS_FILE = "/data/users.json" if os.path.exists("/data") else "users.json"
PORT = int(os.getenv("PORT", 8000))
ADMINS = [1088460844, 328477968, 7028005668]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# === ЗАЩИТА ОТ ДУБЛИКАТОВ ===
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
    print("⚠️ Duplicate instance, exiting.")
    sys.exit(0)

# === KEEPALIVE для Timeweb ===
def keepalive():
    from flask import Flask
    app = Flask(__name__)

    @app.route("/")
    def index():
        return "Bot is alive!", 200

    app.run(host="0.0.0.0", port=PORT)

threading.Thread(target=keepalive, daemon=True).start()

# === ДАННЫЕ ===
DEFAULT_ITEMS = {
    "СОЛЕДАР": {"value": "не задано", "updated": None},
    "ВЛАДИМИРОВКА": {"value": "не задано", "updated": None},
    "ПОКРОВСКОЕ": {"value": "не задано", "updated": None},
    "БЕЛГОРОВКА": {"value": "не задано", "updated": None},
    "ЯКОВЛЕВКА": {"value": "не задано", "updated": None},
    "ПОПАСНАЯ": {"value": "не задано", "updated": None},
    "КАМЫШЕВАХА": {"value": "не задано", "updated": None},
    "БЕРЕСТОВОЕ": {"value": "не задано", "updated": None},
    "ТРИПОЛЬЕ": {"value": "не задано", "updated": None}
}

def load_json(path, default):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
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
users = load_json(USERS_FILE, {})

# === ВСПОМОГАТЕЛЬНЫЕ ===
def now_str():
    return datetime.now(MSK).strftime("%d.%m.%Y %H:%M")

def is_admin(uid): return uid in ADMINS

def make_panel(uid=None):
    """Создает inline-панель для пользователя"""
    kb = types.InlineKeyboardMarkup(row_width=2)
    for name, item in menu_items.items():
        val = item["value"]
        emoji = "🟩" if val == "ЧИСТО" else "🟥" if val == "ГРЯЗНО" else "⬜"
        if is_admin(uid):
            kb.add(types.InlineKeyboardButton(f"{emoji} {name}", callback_data=f"edit|{name}"))
        else:
            kb.add(types.InlineKeyboardButton(f"{emoji} {name}", callback_data=f"view|{name}"))
    if is_admin(uid):
        kb.add(types.InlineKeyboardButton("➕ Добавить", callback_data="add_new"))
    return kb

def save_state():
    save_json(DATA_FILE, menu_items)
    save_json(USERS_FILE, users)

def update_all_panels():
    """Редактирует панели у всех пользователей"""
    for uid, data in list(users.items()):
        try:
            bot.edit_message_reply_markup(uid, data["msg_id"], reply_markup=make_panel(uid))
        except Exception as e:
            if "message to edit not found" in str(e).lower():
                continue
            elif "forbidden" in str(e).lower():
                users.pop(uid)
                save_json(USERS_FILE, users)

# === СТАРТ ===
@bot.message_handler(commands=['start'])
def start(m):
    uid = m.from_user.id
    msg = bot.send_message(m.chat.id, "📋 Текущие статусы:", reply_markup=make_panel(uid))
    users[uid] = {"msg_id": msg.id}
    save_json(USERS_FILE, users)

# === ПРОСМОТР (для обычных пользователей) ===
@bot.callback_query_handler(func=lambda c: c.data.startswith("view|"))
def view_item(c):
    _, name = c.data.split("|", 1)
    val = menu_items[name]["value"]
    updated = menu_items[name]["updated"] or "—"
    emoji = "🟩" if val == "ЧИСТО" else "🟥" if val == "ГРЯЗНО" else "⬜"
    bot.answer_callback_query(c.id, f"{emoji} {name}: {val} ({updated})")

# === ДОБАВЛЕНИЕ ПУНКТА ===
@bot.callback_query_handler(func=lambda c: c.data == "add_new")
def add_prompt(c):
    if not is_admin(c.from_user.id): return
    bot.answer_callback_query(c.id)
    bot.send_message(c.message.chat.id, "Введите название нового пункта:")
    users[c.from_user.id]["mode"] = "add"

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and users.get(m.from_user.id, {}).get("mode") == "add")
def add_new_item(m):
    name = (m.text or "").strip()
    if not name:
        bot.send_message(m.chat.id, "❗ Пустое название.")
        return
    if name in menu_items:
        bot.send_message(m.chat.id, "⚠️ Уже существует.")
        return
    menu_items[name] = {"value": "не задано", "updated": None}
    users[m.from_user.id].pop("mode", None)
    save_state()
    update_all_panels()
    bot.send_message(m.chat.id, f"✅ Добавлен пункт <b>{name}</b>.", parse_mode="HTML")

# === ИЗМЕНЕНИЕ ===
@bot.callback_query_handler(func=lambda c: c.data.startswith("edit|"))
def edit_item(c):
    if not is_admin(c.from_user.id): return
    _, name = c.data.split("|", 1)
    ikb = types.InlineKeyboardMarkup()
    ikb.row(
        types.InlineKeyboardButton("🟩 ЧИСТО", callback_data=f"s|{name}|C"),
        types.InlineKeyboardButton("🟥 ГРЯЗНО", callback_data=f"s|{name}|D"),
        types.InlineKeyboardButton("⬜ НЕИЗВЕСТНО", callback_data=f"s|{name}|U")
    )
    bot.edit_message_text(
        f"Изменяем <b>{name}</b>\nТекущее: {menu_items[name]['value']}",
        chat_id=c.message.chat.id,
        message_id=c.message.id,
        reply_markup=ikb,
        parse_mode="HTML"
    )

# === УСТАНОВКА СТАТУСА ===
@bot.callback_query_handler(func=lambda c: c.data.startswith("s|"))
def set_status(c):
    _, name, code = c.data.split("|", 2)
    val = "ЧИСТО" if code == "C" else "ГРЯЗНО" if code == "D" else "НЕИЗВЕСТНО"
    emoji = "🟩" if val == "ЧИСТО" else "🟥" if val == "ГРЯЗНО" else "⬜"
    menu_items[name] = {"value": val, "updated": now_str()}
    save_state()
    bot.answer_callback_query(c.id, f"{name}: {val}")
    update_all_panels()

print("✅ Бот с live-панелью запущен (автообновление у всех).")
bot.infinity_polling(skip_pending=True)
