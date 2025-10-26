import os
import json
import threading
import psutil
import sys
import time
from datetime import datetime
import telebot
from telebot import types

# 🕒 Московское время
os.environ['TZ'] = 'Europe/Moscow'
try:
    time.tzset()
except Exception:
    pass

# === НАСТРОЙКИ ===
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN не задан в переменных окружения")
    sys.exit(1)

# === /data для постоянного хранения (Timeweb Apps) ===
os.makedirs("/data", exist_ok=True)
DATA_FILE = "/data/data.json" if os.path.exists("/data") else "data.json"
USERS_FILE = "/data/users.json" if os.path.exists("/data") else "users.json"
PORT = int(os.getenv("PORT", 8000))
ADMINS = [1088460844, 328477968, 7028005668]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
admin_sessions = {}

# === KEEPALIVE для Timeweb ===
def keepalive():
    from flask import Flask
    app = Flask(__name__)
    @app.route("/")
    def index(): return "Bot is alive!", 200
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

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
def load_json(path, default):
    if not os.path.exists(path):
        save_json(path, default)
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

menu_items = load_json(DATA_FILE, DEFAULT_ITEMS)
subscribers = load_json(USERS_FILE, [])

# === АВТОВОССТАНОВЛЕНИЕ ПОДПИСЧИКОВ ===
def ensure_subscribers_persistent():
    if not subscribers and os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                if old_data:
                    subscribers.extend(old_data)
                    print("♻️ Восстановлены подписчики из существующего файла.")
        except Exception:
            pass
    for admin in ADMINS:
        if admin not in subscribers:
            subscribers.append(admin)
    save_json(USERS_FILE, subscribers)
    print(f"👥 Активных подписчиков: {len(subscribers)}")

ensure_subscribers_persistent()

def save_data(): save_json(DATA_FILE, menu_items)
def save_users(): save_json(USERS_FILE, subscribers)

# === ВСПОМОГАТЕЛЬНЫЕ ===
def is_admin(uid): return uid in ADMINS

def emoji_for(val):
    if val == "ЧИСТО": return "🟩"
    if val == "ГРЯЗНО": return "🟥"
    return "⬜"

def auto_subscribe(user_id):
    """Автоматически подписывает пользователя, если его нет в базе"""
    if user_id not in subscribers:
        subscribers.append(user_id)
        save_users()
        print(f"➕ Автоподписка: {user_id}")

def send_menu(chat_id, uid=None):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for i, name in enumerate(menu_items.keys(), 1):
        row.append(types.KeyboardButton(name))
        if len(row) == 2: kb.row(*row); row = []
    if row: kb.row(*row)
    if is_admin(uid): kb.row(types.KeyboardButton("⚙️ Рапира"))
    bot.send_message(chat_id, "📋 Выберите пункт:", reply_markup=kb)

# === СТАРТ ===
@bot.message_handler(commands=['start'])
def start(m):
    auto_subscribe(m.from_user.id)
    send_menu(m.chat.id, m.from_user.id)

# === АДМИН-ПАНЕЛЬ ===
@bot.message_handler(func=lambda m: m.text == "⚙️ Рапира")
def admin_panel(m):
    auto_subscribe(m.from_user.id)
    if not is_admin(m.from_user.id):
        return bot.send_message(m.chat.id, "🚫 Нет прав.")
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton("✏️ Изменить"))
    kb.row(types.KeyboardButton("⬅️ Назад"))
    bot.send_message(m.chat.id, "🛠️ Панель управления Рапира:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "⬅️ Назад")
def back(m):
    admin_sessions.pop(m.from_user.id, None)
    send_menu(m.chat.id, m.from_user.id)

# === ИЗМЕНЕНИЕ (список с цветами) ===
@bot.message_handler(func=lambda m: m.text == "✏️ Изменить")
def edit_list(m):
    auto_subscribe(m.from_user.id)
    if not is_admin(m.from_user.id): return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for i, (name, info) in enumerate(menu_items.items(), 1):
        label = f"{emoji_for(info['value'])} {name}"
        row.append(types.KeyboardButton(label))
        if len(row) == 2: kb.row(*row); row = []
    if row: kb.row(*row)
    kb.row(types.KeyboardButton("⬅️ Назад"))
    bot.send_message(m.chat.id, "🧩 Нажмите на пункт, чтобы переключить статус:", reply_markup=kb)
    admin_sessions[m.from_user.id] = {"mode": "toggle"}

# === ПЕРЕКЛЮЧЕНИЕ СТАТУСА (только ЧИСТО/ГРЯЗНО) ===
@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_sessions.get(m.from_user.id, {}).get("mode") == "toggle")
def toggle_status(m):
    auto_subscribe(m.from_user.id)
    text = m.text.strip()
    name = text.replace("🟩","").replace("🟥","").replace("⬜","").strip()
    if name not in menu_items:
        return bot.send_message(m.chat.id, "❗ Неизвестный пункт.")
    current = menu_items[name]["value"]

    # если "не задано" — ставим по умолчанию "ЧИСТО"
    if current == "не задано":
        new_val = "ЧИСТО"
    else:
        new_val = "ГРЯЗНО" if current == "ЧИСТО" else "ЧИСТО"

    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    menu_items[name] = {"value": new_val, "updated": timestamp}
    save_data()

    emoji = emoji_for(new_val)
    text_msg = f"{emoji} <b>{name}</b>: {new_val}\n🕓 {timestamp}"
    for uid in list(subscribers):
        try:
            bot.send_message(uid, text_msg, parse_mode="HTML")
        except Exception as e:
            if "Forbidden" in str(e):
                subscribers.remove(uid)
                save_users()

    bot.send_message(m.chat.id, f"✅ Обновлено: {emoji} <b>{name}</b> → {new_val}", parse_mode="HTML")
    edit_list(m)

# === ПРОСМОТР ===
@bot.message_handler(func=lambda m: m.text.replace("🟩","").replace("🟥","").replace("⬜","").strip() in menu_items)
def show_item(m):
    auto_subscribe(m.from_user.id)
    key = m.text.replace("🟩","").replace("🟥","").replace("⬜","").strip()
    item = menu_items[key]
    val, updated = item["value"], item["updated"]
    emoji = emoji_for(val)
    if updated:
        bot.send_message(m.chat.id, f"{emoji} {key}: <b>{val}</b>\n🕓 Последнее изменение: {updated}")
    else:
        bot.send_message(m.chat.id, f"{emoji} {key}: <b>{val}</b>\n🕓 Ещё не изменялось")

# === ПРОЧЕЕ ===
@bot.message_handler(func=lambda m: True)
def fallback(m):
    auto_subscribe(m.from_user.id)
    bot.send_message(m.chat.id, "Не понимаю. Используйте кнопки меню.")
    send_menu(m.chat.id, m.from_user.id)

print("✅ Бот запущен (⚙️ Рапира, автоподписка всех, только ЧИСТО/ГРЯЗНО, данные в /data).")
bot.infinity_polling(skip_pending=True)
