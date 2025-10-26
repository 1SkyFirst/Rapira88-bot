import os
import json
import threading
import psutil
import sys
from datetime import datetime
import pytz
import telebot
from telebot import types

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
TZ = pytz.timezone("Europe/Moscow")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# === АНТИДУБЛИКАТ ===
def already_running():
    current = psutil.Process().pid
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            if proc.pid != current and 'python' in ' '.join(proc.info.get('cmdline') or []) and 'bot.py' in ' '.join(proc.info.get('cmdline') or []):
                return True
        except Exception:
            continue
    return False

if already_running():
    print("⚠️ Bot already running, exiting duplicate instance.")
    sys.exit(0)

# === KEEPALIVE (для Timeweb) ===
def keepalive():
    from flask import Flask
    app = Flask(__name__)
    @app.route("/")
    def index(): return "Bot alive!", 200
    app.run(host="0.0.0.0", port=PORT)
threading.Thread(target=keepalive, daemon=True).start()

# === ЗАГРУЗКА / СОХРАНЕНИЕ ===
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
        with open(path, "w", encoding="utf-8") as f: json.dump(default, f, ensure_ascii=False, indent=2)
        return default
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

menu_items = load_json(DATA_FILE, DEFAULT_ITEMS)
subscribers = load_json(USERS_FILE, [])

def save_data(): save_json(DATA_FILE, menu_items)
def save_users(): save_json(USERS_FILE, subscribers)
def is_admin(uid): return uid in ADMINS

# === ВСПОМОГАТЕЛЬНЫЕ ===
def status_emoji(val):
    if val == "ЧИСТО": return "🟩"
    elif val == "ГРЯЗНО": return "🟥"
    else: return "⬜"

def build_keyboard(items, uid=None):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for i, (name, info) in enumerate(items.items(), 1):
        label = f"{status_emoji(info['value'])} {name}"
        row.append(types.KeyboardButton(label))
        if len(row) == 2:
            kb.row(*row)
            row = []
    if row: kb.row(*row)
    if is_admin(uid):
        kb.row(types.KeyboardButton("➕ Добавить"), types.KeyboardButton("➖ Удалить"))
        kb.row(types.KeyboardButton("⬅️ Назад"))
    return kb

def send_menu(chat_id, uid=None):
    kb = build_keyboard(menu_items, uid)
    if is_admin(uid):
        bot.send_message(chat_id, "🧰 Панель администратора\n(нажмите пункт для смены статуса):", reply_markup=kb)
    else:
        bot.send_message(chat_id, "📋 Состояние:", reply_markup=kb)

# === СТАРТ ===
@bot.message_handler(commands=["start"])
def start(m):
    uid = m.from_user.id
    if uid not in subscribers:
        subscribers.append(uid)
        save_users()
    send_menu(m.chat.id, uid)

# === ДОБАВЛЕНИЕ ===
@bot.message_handler(func=lambda m: m.text == "➕ Добавить")
def add_prompt(m):
    if not is_admin(m.from_user.id): return
    bot.send_message(m.chat.id, "Введите название нового пункта:")
    bot.register_next_step_handler(m, add_new)

def add_new(m):
    key = m.text.strip().upper()
    if key in menu_items:
        bot.send_message(m.chat.id, "⚠️ Такой пункт уже существует.")
    else:
        menu_items[key] = {"value": "не задано", "updated": None}
        save_data()
        bot.send_message(m.chat.id, f"✅ Добавлен пункт <b>{key}</b>.")
    send_menu(m.chat.id, m.from_user.id)

# === УДАЛЕНИЕ ===
delete_mode = {}

@bot.message_handler(func=lambda m: m.text == "➖ Удалить")
def delete_prompt(m):
    if not is_admin(m.from_user.id): return
    delete_mode[m.from_user.id] = True
    bot.send_message(m.chat.id, "🗑 Выберите пункт для удаления:")
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for i, name in enumerate(menu_items.keys(), 1):
        row.append(types.KeyboardButton(name))
        if len(row) == 2:
            kb.row(*row)
            row = []
    if row: kb.row(*row)
    kb.row(types.KeyboardButton("❌ Отмена"))
    bot.send_message(m.chat.id, "Выберите, что удалить:", reply_markup=kb)

@bot.message_handler(func=lambda m: delete_mode.get(m.from_user.id, False))
def delete_item(m):
    uid = m.from_user.id
    if m.text == "❌ Отмена":
        delete_mode[uid] = False
        bot.send_message(m.chat.id, "🚫 Отменено.")
        return send_menu(m.chat.id, uid)

    key = m.text.strip().upper()
    if key not in menu_items:
        bot.send_message(m.chat.id, "❗ Такого пункта нет.")
    else:
        del menu_items[key]
        save_data()
        bot.send_message(m.chat.id, f"🗑 Удалён пункт <b>{key}</b>.")
    delete_mode[uid] = False
    send_menu(m.chat.id, uid)

# === НАЗАД ===
@bot.message_handler(func=lambda m: m.text == "⬅️ Назад")
def back(m):
    bot.send_message(m.chat.id, "↩️ Возврат в обычное меню.")
    send_menu(m.chat.id, m.from_user.id)

# === ПЕРЕКЛЮЧЕНИЕ / ПРОСМОТР ===
@bot.message_handler(func=lambda m: any(name in m.text for name in menu_items.keys()))
def toggle_status(m):
    uid = m.from_user.id
    key = next((name for name in menu_items if name in m.text), None)
    if not key: return

    if is_admin(uid):
        # Переключение статуса
        current = menu_items[key]["value"]
        new_val = "ЧИСТО" if current != "ЧИСТО" else "ГРЯЗНО"
        ts = datetime.now(TZ).strftime("%d.%m.%Y %H:%M")
        menu_items[key] = {"value": new_val, "updated": ts}
        save_data()

        emoji = status_emoji(new_val)
        text = f"{emoji} <b>{key}</b>: {new_val}\n🕓 {ts}"
        for uid2 in list(subscribers):
            try:
                bot.send_message(uid2, text, parse_mode="HTML")
            except Exception as e:
                if "Forbidden" in str(e) or "bot was blocked" in str(e):
                    subscribers.remove(uid2)
                    save_users()

        bot.send_message(m.chat.id, f"⚠️ {key}: {emoji} {new_val}")
        send_menu(m.chat.id, uid)

    else:
        # Только просмотр
        item = menu_items[key]
        val = item["value"]
        updated = item.get("updated")
        emoji = status_emoji(val)
        ts = f"\n🕓 Последнее изменение: {updated}" if updated else ""
        bot.send_message(m.chat.id, f"{emoji} {key}: <b>{val}</b>{ts}")

# === ПРОЧЕЕ ===
@bot.message_handler(func=lambda m: True)
def fallback(m):
    send_menu(m.chat.id, m.from_user.id)

print("⚠️ Бот запущен с цветными статусами и удалением.")
bot.infinity_polling(skip_pending=True)
