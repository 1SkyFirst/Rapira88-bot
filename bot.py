import os
import json
import threading
import psutil
import sys
from http.server import SimpleHTTPRequestHandler, HTTPServer
from datetime import datetime
import telebot
from telebot import types

# ====== НАСТРОЙКИ ======
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN не задан в переменных окружения")
    sys.exit(1)

DATA_FILE = "data.json"
USERS_FILE = "users.json"
PORT = int(os.getenv("PORT", 8000))
ADMINS = [1088460844, 328477968, 7028005668]  # 👑 Администраторы

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
admin_sessions = {}

# ====== ПРОВЕРКА ДУБЛИКАТОВ ======
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

# ====== KEEPALIVE ======
def keepalive():
    from flask import Flask
    app = Flask(__name__)

    @app.route("/")
    def index():
        return "Bot is alive!", 200

    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

# ====== ФАЙЛЫ ДАННЫХ ======
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

def load_data():
    if not os.path.exists(DATA_FILE):
        print("🆕 Создаю data.json с шаблоном.")
        save_data(DEFAULT_ITEMS.copy())
        return DEFAULT_ITEMS.copy()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    changed = False
    for k, v in DEFAULT_ITEMS.items():
        if k not in data:
            data[k] = v
            changed = True
        elif isinstance(data[k], str):
            data[k] = {"value": data[k], "updated": None}
            changed = True
    if changed:
        save_data(data)
    return data

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f)

menu_items = load_data()
subscribers = load_users()

# ====== ВСПОМОГАТЕЛЬНЫЕ ======
def is_admin(uid): 
    return uid in ADMINS

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

# ====== СТАРТ ======
@bot.message_handler(commands=['start'])
def start(m):
    uid = m.from_user.id
    if uid not in subscribers:
        subscribers.append(uid)
        save_users(subscribers)
        print(f"👤 Новый подписчик: {uid}")
    send_menu(m.chat.id, uid)

# ====== АДМИН-ПАНЕЛЬ ======
@bot.message_handler(func=lambda m: m.text == "⚙️ Админ-панель")
def admin_panel(m):
    if not is_admin(m.from_user.id):
        return bot.send_message(m.chat.id, "🚫 Нет прав.")
    kb = build_keyboard_two_per_row(["➕ Добавить", "✏️ Изменить"], extra_last_row=["⬅️ Назад"])
    bot.send_message(m.chat.id, "🔧 Админ-панель:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "⬅️ Назад")
def back(m):
    admin_sessions.pop(m.from_user.id, None)
    send_menu(m.chat.id, m.from_user.id)

# ====== ДОБАВЛЕНИЕ ======
@bot.message_handler(func=lambda m: m.text == "➕ Добавить")
def add_prompt(m):
    if not is_admin(m.from_user.id): 
        return
    admin_sessions[m.from_user.id] = {"mode": "add"}
    bot.send_message(m.chat.id, "Введите <b>название новой кнопки</b>:", parse_mode="HTML")

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_sessions.get(m.from_user.id, {}).get("mode") == "add")
def add_new(m):
    key = (m.text or "").strip()
    if not key:
        bot.send_message(m.chat.id, "❗ Пустое название. Операция отменена.")
    elif key in menu_items:
        bot.send_message(m.chat.id, "⚠️ Такая кнопка уже есть.")
    else:
        menu_items[key] = {"value": "не задано", "updated": None}
        save_data(menu_items)
        bot.send_message(m.chat.id, f"✅ Добавлена кнопка '<b>{key}</b>'.", parse_mode="HTML")
    admin_sessions.pop(m.from_user.id, None)
    send_menu(m.chat.id, m.from_user.id)

# ====== ИЗМЕНЕНИЕ ======
@bot.message_handler(func=lambda m: m.text == "✏️ Изменить")
def edit_prompt(m):
    if not is_admin(m.from_user.id): 
        return
    admin_sessions[m.from_user.id] = {"mode": "edit"}
    kb = build_keyboard_two_per_row(list(menu_items.keys()), extra_last_row=["⬅️ Назад"])
    bot.send_message(m.chat.id, "Выберите пункт для изменения:", reply_markup=kb)

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_sessions.get(m.from_user.id, {}).get("mode") == "edit")
def edit_item(m):
    key = (m.text or "").strip()
    if key not in menu_items:
        return bot.send_message(m.chat.id, "❗ Такой кнопки нет. Вернитесь и выберите из списка.")
    admin_sessions[m.from_user.id] = {"mode": "set", "key": key}
    ikb = types.InlineKeyboardMarkup()
    ikb.row(
        types.InlineKeyboardButton("✅ ЧИСТО", callback_data=f"s|{key}|C"),
        types.InlineKeyboardButton("💦 ГРЯЗНО", callback_data=f"s|{key}|D"),
        types.InlineKeyboardButton("❔ НЕИЗВЕСТНО", callback_data=f"s|{key}|U")
    )
    current = menu_items[key]["value"]
    updated = menu_items[key]["updated"]
    updated_text = f"\n🕓 Последнее изменение: {updated}" if updated else ""
    bot.send_message(
        m.chat.id,
        f"Изменяем <b>{key}</b>.\nТекущее значение: <b>{current}</b>{updated_text}\n\nВыберите новое:",
        reply_markup=ikb
    )

# ====== CALLBACK: установка и рассылка ======
@bot.callback_query_handler(func=lambda c: c.data.startswith("s|"))
def on_set(c):
    try:
        _, key, flag = c.data.split("|", 2)
        if key not in menu_items:
            return bot.answer_callback_query(c.id, "Кнопка не найдена.")
        val = "ЧИСТО" if flag == "C" else "ГРЯЗНО" if flag == "D" else "НЕИЗВЕСТНО"
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        menu_items[key] = {"value": val, "updated": timestamp}
        save_data(menu_items)

        # Отправляем уведомление всем подписчикам
        text = f"⚠️ <b>Внимание!</b>\n{key}: <b>{val}</b>\n🕓 {timestamp}"
        for uid in list(subscribers):
            try:
                bot.send_message(uid, text, parse_mode="HTML")
            except Exception as e:
                if "Forbidden" in str(e) or "bot was blocked" in str(e):
                    subscribers.remove(uid)
                    save_users(subscribers)

        bot.answer_callback_query(c.id, f"{key} → {val}")
        bot.send_message(c.message.chat.id, f"✅ {key}: <b>{val}</b>", parse_mode="HTML")
        admin_sessions.pop(c.from_user.id, None)
        send_menu(c.message.chat.id, c.from_user.id)

    except Exception as e:
        bot.answer_callback_query(c.id, f"Ошибка: {e}")

# ====== ПРОСМОТР ======
@bot.message_handler(func=lambda m: (m.text in menu_items) and not (is_admin(m.from_user.id) and admin_sessions.get(m.from_user.id, {}).get("mode") in ("edit","set")))
def show_item(m):
    item = menu_items[m.text]
    val = item["value"]
    updated = item.get("updated")
    if updated:
        bot.send_message(m.chat.id, f"{m.text}: <b>{val}</b>\n🕓 Последнее изменение: {updated}")
    else:
        bot.send_message(m.chat.id, f"{m.text}: <b>{val}</b>\n🕓 Ещё не изменялось")

# ====== ПРОЧЕЕ ======
@bot.message_handler(func=lambda m: True)
def fallback(m):
    bot.send_message(m.chat.id, "Не понимаю. Используйте кнопки меню.")
    send_menu(m.chat.id, m.from_user.id)

print("✅ Бот запущен.")
bot.infinity_polling(skip_pending=True)
