import os
import sys
import json
import threading
import psutil
import pytz
from datetime import datetime
import telebot
from telebot import types

# ==== ВРЕМЯ (MSK/pytz) ====
MSK = pytz.timezone("Europe/Moscow")
def now_str():
    return datetime.now(MSK).strftime("%d.%m.%Y %H:%M")

# ==== НАСТРОЙКИ ====
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN не задан")
    sys.exit(1)

os.makedirs("/data", exist_ok=True)
DATA_FILE = "/data/data.json" if os.path.exists("/data") else "data.json"
USERS_FILE = "/data/users.json" if os.path.exists("/data") else "users.json"
PORT = int(os.getenv("PORT", 8000))
ADMINS = [1088460844, 328477968, 7028005668]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ==== АНТИ-ДУБЛИКАТ ====
def already_running():
    me = psutil.Process().pid
    for p in psutil.process_iter(['pid','name','cmdline']):
        try:
            if p.pid != me and 'python' in (p.name() or '').lower() and 'bot.py' in ' '.join(p.info.get('cmdline') or []):
                return True
        except Exception:
            pass
    return False

if already_running():
    print("⚠️ Второй экземпляр — выхожу.")
    sys.exit(0)

# ==== KEEPALIVE ДЛЯ TIMEWEB ====
def keepalive():
    from flask import Flask
    app = Flask(__name__)
    @app.get("/")
    def ok():
        return "Bot is alive!", 200
    app.run(host="0.0.0.0", port=PORT)
threading.Thread(target=keepalive, daemon=True).start()

# ==== ДАННЫЕ ====
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

menu = load_json(DATA_FILE, DEFAULT_ITEMS)
users = load_json(USERS_FILE, {})  # uid -> {"state": "idle"/"adding"/"set", "key": str|None}

# ==== ХЕЛПЕРЫ ====
def is_admin(uid): return uid in ADMINS

def value_emoji(val):
    return "🟩" if val == "ЧИСТО" else "🟥" if val == "ГРЯЗНО" else "⬜"

def build_reply_two_cols(labels, tail_buttons=None):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for text in labels:
        row.append(types.KeyboardButton(text))
        if len(row) == 2:
            kb.row(*row); row = []
    if row: kb.row(*row)
    if tail_buttons and len(tail_buttons):
        kb.row(*[types.KeyboardButton(x) for x in tail_buttons])
    return kb

def admin_live_keyboard():
    # кнопки вида "🟩 СОЛЕДАР", в конце — "➕ Добавить", "⬅️ Назад"
    labels = [f"{value_emoji(v['value'])} {name}" for name, v in menu.items()]
    return build_reply_two_cols(labels, ["➕ Добавить", "⬅️ Назад"])

def user_live_keyboard():
    labels = [f"{value_emoji(v['value'])} {name}" for name, v in menu.items()]
    return build_reply_two_cols(labels, ["⬅️ Назад"])

def status_choice_keyboard():
    return build_reply_two_cols(["🟩 ЧИСТО", "🟥 ГРЯЗНО", "⬜ НЕИЗВЕСТНО"], ["⬅️ Отмена"])

def parse_item_button(text):
    # принимает "🟩 СОЛЕДАР" -> "СОЛЕДАР"
    return text.split(" ", 1)[1] if " " in text else text

def show_root(chat_id, uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("📍 Рапира"))
    bot.send_message(chat_id, "Выберите раздел:", reply_markup=kb)

def show_rapira(chat_id, uid):
    kb = admin_live_keyboard() if is_admin(uid) else user_live_keyboard()
    bot.send_message(chat_id, "📋 Текущие статусы:", reply_markup=kb)

def save_state():
    save_json(DATA_FILE, menu)
    save_json(USERS_FILE, users)

# ==== СТАРТ ====
@bot.message_handler(commands=['start'])
def start(m):
    uid = m.from_user.id
    users.setdefault(uid, {"state": "idle", "key": None})
    save_json(USERS_FILE, users)
    show_root(m.chat.id, uid)

# ==== РУТ-МЕНЮ ====
@bot.message_handler(func=lambda m: m.text == "⚙️ Рапира")
def on_rapira(m):
    show_rapira(m.chat.id, m.from_user.id)

@bot.message_handler(func=lambda m: m.text == "⬅️ Назад")
def on_back(m):
    users[m.from_user.id]["state"] = "idle"
    users[m.from_user.id]["key"] = None
    save_json(USERS_FILE, users)
    show_root(m.chat.id, m.from_user.id)

# ==== ДОБАВИТЬ (только админы, всё через ReplyKeyboard) ====
@bot.message_handler(func=lambda m: m.text == "➕ Добавить")
def on_add(m):
    if not is_admin(m.from_user.id): return
    users[m.from_user.id]["state"] = "adding"
    users[m.from_user.id]["key"] = None
    save_json(USERS_FILE, users)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("⬅️ Отмена"))
    bot.send_message(m.chat.id, "Введите название нового пункта:", reply_markup=kb)

@bot.message_handler(func=lambda m: users.get(m.from_user.id, {}).get("state") == "adding")
def on_add_name(m):
    if m.text == "⬅️ Отмена":
        users[m.from_user.id]["state"] = "idle"
        users[m.from_user.id]["key"] = None
        save_json(USERS_FILE, users)
        show_rapira(m.chat.id, m.from_user.id)
        return
    name = (m.text or "").strip()
    if not name:
        bot.send_message(m.chat.id, "❗ Пустое имя. Введите снова.")
        return
    if name in menu:
        bot.send_message(m.chat.id, "⚠️ Уже существует. Введите другое.")
        return
    menu[name] = {"value": "не задано", "updated": None}
    users[m.from_user.id]["state"] = "idle"
    users[m.from_user.id]["key"] = None
    save_state()
    show_rapira(m.chat.id, m.from_user.id)

# ==== ВЫБОР ПУНКТА ДЛЯ ИЗМЕНЕНИЯ (админ) или ПРОСМОТР (пользователь) ====
@bot.message_handler(func=lambda m: any(m.text.startswith(sym) for sym in ("🟩","🟥","⬜")))
def on_item_click(m):
    uid = m.from_user.id
    name = parse_item_button(m.text)
    if name not in menu:
        # может быть остаток старой клавы — просто перерисуем
        show_rapira(m.chat.id, uid)
        return
    if is_admin(uid):
        # показываем выбор статуса (тоже ReplyKeyboard)
        users[uid]["state"] = "set"
        users[uid]["key"] = name
        save_json(USERS_FILE, users)
        bot.send_message(m.chat.id, f"Изменяем <b>{name}</b> (сейчас: {menu[name]['value']}). Выберите статус:",
                         reply_markup=status_choice_keyboard(), parse_mode="HTML")
    else:
        # у пользователей просто обновим клавиатуру (без текста)
        show_rapira(m.chat.id, uid)

# ==== УСТАНОВКА СТАТУСА (ReplyKeyboard) ====
@bot.message_handler(func=lambda m: users.get(m.from_user.id, {}).get("state") == "set")
def on_set_status(m):
    uid = m.from_user.id
    key = users[uid]["key"]
    if m.text == "⬅️ Отмена":
        users[uid]["state"] = "idle"; users[uid]["key"] = None
        save_json(USERS_FILE, users)
        show_rapira(m.chat.id, uid)
        return

    if m.text not in ("🟩 ЧИСТО", "🟥 ГРЯЗНО", "⬜ НЕИЗВЕСТНО"):
        bot.send_message(m.chat.id, "Выберите один из вариантов на клавиатуре.")
        return

    val = "ЧИСТО" if "ЧИСТО" in m.text else "ГРЯЗНО" if "ГРЯЗНО" in m.text else "НЕИЗВЕСТНО"
    menu[key] = {"value": val, "updated": now_str()}
    users[uid]["state"] = "idle"; users[uid]["key"] = None
    save_state()
    # возвращаемся в живое меню (клавиатура обновится, статусы уже в названиях кнопок)
    show_rapira(m.chat.id, uid)

# ==== ФОЛЛБЭК ====
@bot.message_handler(func=lambda m: True)
def fallback(m):
    show_root(m.chat.id, m.from_user.id)

print("✅ Бот запущен (ReplyKeyboard, live-статусы в кнопках, без инлайна).")
bot.infinity_polling(skip_pending=True)
