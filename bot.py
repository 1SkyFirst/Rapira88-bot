import os
import json
import threading
import psutil
import sys
import pytz
from datetime import datetime
import telebot
from telebot import types

# 🕒 Московский часовой пояс через pytz
MSK = pytz.timezone("Europe/Moscow")

# === НАСТРОЙКИ ===
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN не задан в переменных окружения")
    sys.exit(1)

# === Папка для хранения данных (переживает деплой на Timeweb) ===
os.makedirs("/data", exist_ok=True)
DATA_FILE = "/data/data.json" if os.path.exists("/data") else "data.json"
USERS_FILE = "/data/users.json" if os.path.exists("/data") else "users.json"

PORT = int(os.getenv("PORT", 8000))
ADMINS = [1088460844, 328477968, 7028005668]

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
admin_sessions = {}

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
    print("⚠️ Bot already running, exiting duplicate instance.")
    sys.exit(0)

# === HTTP KEEPALIVE для Timeweb (порт 8000) ===
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

def save_data():
    save_json(DATA_FILE, menu_items)

def save_users():
    save_json(USERS_FILE, subscribers)

# === ВСПОМОГАТЕЛЬНЫЕ ===
def is_admin(uid):
    return uid in ADMINS

def get_timestamp():
    return datetime.now(MSK).strftime("%d.%m.%Y %H:%M")

def build_keyboard_two_per_row(labels, extra_last_row=None):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for i, name in enumerate(labels, 1):
        row.append(types.KeyboardButton(name))
        if len(row) == 2:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    if extra_last_row:
        kb.row(*[types.KeyboardButton(x) for x in extra_last_row])
    return kb

def send_menu(chat_id, uid=None):
    kb = build_keyboard_two_per_row(list(menu_items.keys()),
                                    extra_last_row=(["⚙️ Админ-панель"] if is_admin(uid) else None))
    bot.send_message(chat_id, "📋 Выберите пункт:", reply_markup=kb)

# === СТАРТ ===
@bot.message_handler(commands=['start'])
def start(m):
    uid = m.from_user.id
    if uid not in subscribers:
        subscribers.append(uid)
        save_users()
        print(f"👤 Новый подписчик: {uid}")
    send_menu(m.chat.id, uid)

# === АДМИН-ПАНЕЛЬ ===
@bot.message_handler(func=lambda m: m.text == "⚙️ Админ-панель")
def admin_panel(m):
    if not is_admin(m.from_user.id):
        return bot.send_message(m.chat.id, "🚫 Нет прав.")
    kb = build_keyboard_two_per_row(["✏️ Изменить"], extra_last_row=["⬅️ Назад"])
    bot.send_message(m.chat.id, "🔧 Админ-панель:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "⬅️ Назад")
def back(m):
    admin_sessions.pop(m.from_user.id, None)
    send_menu(m.chat.id, m.from_user.id)

# === ИЗМЕНЕНИЕ ВСЕГО СПИСКА ===
@bot.message_handler(func=lambda m: m.text == "✏️ Изменить")
def show_edit_panel(m):
    if not is_admin(m.from_user.id):
        return
    for name, item in menu_items.items():
        val = item["value"]
        updated = item.get("updated") or "—"
        emoji = "🟩" if val == "ЧИСТО" else "🟥" if val == "ГРЯЗНО" else "⬜"
        ikb = types.InlineKeyboardMarkup()
        ikb.row(
            types.InlineKeyboardButton("🟩 ЧИСТО", callback_data=f"s|{name}|C"),
            types.InlineKeyboardButton("🟥 ГРЯЗНО", callback_data=f"s|{name}|D"),
            types.InlineKeyboardButton("⬜ НЕИЗВЕСТНО", callback_data=f"s|{name}|U")
        )
        bot.send_message(
            m.chat.id,
            f"{emoji} <b>{name}</b>: {val}\n🕓 {updated}",
            reply_markup=ikb
        )

    # в конце — кнопка "Добавить"
    ikb_add = types.InlineKeyboardMarkup()
    ikb_add.add(types.InlineKeyboardButton("➕ Добавить новый пункт", callback_data="add_new"))
    bot.send_message(m.chat.id, "—", reply_markup=ikb_add)

# === ДОБАВЛЕНИЕ ===
@bot.callback_query_handler(func=lambda c: c.data == "add_new")
def add_new_prompt(c):
    if not is_admin(c.from_user.id):
        return
    admin_sessions[c.from_user.id] = {"mode": "add"}
    bot.send_message(c.message.chat.id, "Введите <b>название нового пункта</b>:", parse_mode="HTML")

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_sessions.get(m.from_user.id, {}).get("mode") == "add")
def add_new_item(m):
    key = (m.text or "").strip()
    if not key:
        bot.send_message(m.chat.id, "❗ Пустое название.")
        return
    if key in menu_items:
        bot.send_message(m.chat.id, "⚠️ Такая кнопка уже есть.")
        return
    menu_items[key] = {"value": "не задано", "updated": None}
    save_data()
    bot.send_message(m.chat.id, f"✅ Добавлена кнопка <b>{key}</b>.", parse_mode="HTML")
    admin_sessions.pop(m.from_user.id, None)
    show_edit_panel(m)

# === УСТАНОВКА СТАТУСА ===
@bot.callback_query_handler(func=lambda c: c.data.startswith("s|"))
def on_set(c):
    try:
        _, key, flag = c.data.split("|", 2)
        if key not in menu_items:
            return bot.answer_callback_query(c.id, "Кнопка не найдена.")
        val = "ЧИСТО" if flag == "C" else "ГРЯЗНО" if flag == "D" else "НЕИЗВЕСТНО"
        timestamp = get_timestamp()
        menu_items[key] = {"value": val, "updated": timestamp}
        save_data()

        emoji = "🟩" if val == "ЧИСТО" else "🟥" if val == "ГРЯЗНО" else "⬜"
        text = f"{emoji} <b>{key}</b>: {val}\n🕓 {timestamp}"
        for uid in list(subscribers):
            try:
                bot.send_message(uid, text, parse_mode="HTML")
            except Exception as e:
                if "Forbidden" in str(e):
                    subscribers.remove(uid)
                    save_users()

        bot.answer_callback_query(c.id, f"{key} → {val}")
        bot.edit_message_text(
            f"{emoji} <b>{key}</b>: {val}\n🕓 {timestamp}",
            chat_id=c.message.chat.id,
            message_id=c.message.id,
            parse_mode="HTML",
            reply_markup=c.message.reply_markup
        )

    except Exception as e:
        bot.answer_callback_query(c.id, f"Ошибка: {e}")

# === ПРОСМОТР ===
@bot.message_handler(func=lambda m: m.text in menu_items)
def show_item(m):
    item = menu_items[m.text]
    val = item["value"]
    updated = item.get("updated") or "—"
    emoji = "🟩" if val == "ЧИСТО" else "🟥" if val == "ГРЯЗНО" else "⬜"
    bot.send_message(m.chat.id, f"{emoji} {m.text}: <b>{val}</b>\n🕓 {updated}")

# === ПРОЧЕЕ ===
@bot.message_handler(func=lambda m: True)
def fallback(m):
    bot.send_message(m.chat.id, "Не понимаю. Используйте кнопки меню.")
    send_menu(m.chat.id, m.from_user.id)

print("✅ Бот запущен (с pytz, цветами и добавлением в списке).")
bot.infinity_polling(skip_pending=True)
