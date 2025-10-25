import os
import json
import threading
import psutil
import sys
from http.server import SimpleHTTPRequestHandler, HTTPServer
import telebot
from telebot import types

# ====== НАСТРОЙКИ ======
TOKEN = os.getenv("TOKEN")
DATA_FILE = "data.json"
PORT = int(os.getenv("PORT", 8000))
ADMINS = [1088460844, 328477968, 7028005668]  # 👑 Администраторы

bot = telebot.TeleBot(TOKEN)
admin_sessions = {}

# ====== ПРОВЕРКА ДУБЛИКАТОВ ======
def already_running():
    current = psutil.Process().pid
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if proc.pid != current and 'python' in proc.name() and 'bot.py' in str(proc.cmdline()):
            return True
    return False

if already_running():
    print("⚠️ Bot already running, exiting duplicate instance.")
    sys.exit(0)

# ====== KEEPALIVE ======
def keepalive():
    server = HTTPServer(("0.0.0.0", PORT), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=keepalive, daemon=True).start()

# ====== ДАННЫЕ ======
def load_data():
    default_items = {
        "СОЛЕДАР": "не задано",
        "ВЛАДИМИРОВКА": "не задано",
        "ПОКРОВСКОЕ": "не задано",
        "БЕЛГОРОВКА": "не задано",
        "ЯКОВЛЕВКА": "не задано",
        "ПОПАСНАЯ": "не задано",
        "КАМЫШЕВАХА": "не задано",
        "БЕРЕСТОВОЕ": "не задано",
        "ТРИПОЛЬЕ": "не задано"
    }
    if not os.path.exists(DATA_FILE):
        print("🆕 Создаю data.json с шаблоном.")
        save_data(default_items)
        return default_items
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # добавляем новые пункты, если их не было
            for k, v in default_items.items():
                if k not in data:
                    data[k] = v
            save_data(data)
            return data
    except Exception as e:
        print("⚠️ Ошибка чтения data.json:", e)
        save_data(default_items)
        return default_items

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

menu_items = load_data()

# ====== ВСПОМОГАТЕЛЬНЫЕ ======
def is_admin(uid): return uid in ADMINS

def send_menu(chat_id, uid=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for k in menu_items.keys():
        markup.add(types.KeyboardButton(k))
    if is_admin(uid):
        markup.add(types.KeyboardButton("⚙️ Админ-панель"))
    bot.send_message(chat_id, "📋 Выберите пункт:", reply_markup=markup)

# ====== СТАРТ ======
@bot.message_handler(commands=['start'])
def start(m):
    send_menu(m.chat.id, m.from_user.id)

# ====== ПРОСМОТР ======
@bot.message_handler(func=lambda m: m.text in menu_items)
def show_item(m):
    text = f"{m.text}: <b>{menu_items[m.text]}</b>"
    bot.send_message(m.chat.id, text, parse_mode="HTML")

# ====== АДМИН-ПАНЕЛЬ ======
@bot.message_handler(func=lambda m: m.text == "⚙️ Админ-панель")
def admin_panel(m):
    if not is_admin(m.from_user.id):
        return bot.send_message(m.chat.id, "🚫 Нет прав.")
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Добавить", "✏️ Изменить")
    kb.add("⬅️ Назад")
    bot.send_message(m.chat.id, "🔧 Админ-панель:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "⬅️ Назад")
def back(m):
    send_menu(m.chat.id, m.from_user.id)

# ====== ДОБАВЛЕНИЕ ======
@bot.message_handler(func=lambda m: m.text == "➕ Добавить")
def add_prompt(m):
    if not is_admin(m.from_user.id): return
    admin_sessions[m.from_user.id] = {"mode": "add"}
    bot.send_message(m.chat.id, "Введите название новой кнопки:")

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_sessions.get(m.from_user.id, {}).get("mode") == "add")
def add_new(m):
    key = m.text.strip()
    if key in menu_items:
        bot.send_message(m.chat.id, "⚠️ Такая кнопка уже есть.")
    else:
        menu_items[key] = "не задано"
        save_data(menu_items)
        bot.send_message(m.chat.id, f"✅ Добавлена кнопка '{key}'.")
    admin_sessions.pop(m.from_user.id, None)
    send_menu(m.chat.id, m.from_user.id)

# ====== ИЗМЕНЕНИЕ ======
@bot.message_handler(func=lambda m: m.text == "✏️ Изменить")
def edit_prompt(m):
    if not is_admin(m.from_user.id): return
    admin_sessions[m.from_user.id] = {"mode": "edit"}
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for k in menu_items.keys():
        kb.add(types.KeyboardButton(k))
    kb.add("⬅️ Назад")
    bot.send_message(m.chat.id, "Выберите, что изменить:", reply_markup=kb)

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_sessions.get(m.from_user.id, {}).get("mode") == "edit")
def edit_item(m):
    key = m.text.strip()
    if key not in menu_items:
        return bot.send_message(m.chat.id, "❗ Такой кнопки нет.")
    ikb = types.InlineKeyboardMarkup()
    ikb.row(
        types.InlineKeyboardButton("✅ ЧИСТО", callback_data=f"set|{key}|ЧИСТО"),
        types.InlineKeyboardButton("💦 ГРЯЗНО", callback_data=f"set|{key}|ГРЯЗНО")
    )
    bot.send_message(
        m.chat.id,
        f"Изменяем <b>{key}</b>:\nТекущее значение — <b>{menu_items[key]}</b>",
        parse_mode="HTML",
        reply_markup=ikb
    )

# ====== INLINE CALLBACK ======
@bot.callback_query_handler(func=lambda c: c.data.startswith("set|"))
def on_set(c):
    try:
        _, key, val = c.data.split("|", 2)
        if key not in menu_items:
            return bot.answer_callback_query(c.id, "Кнопка не найдена.")
        menu_items[key] = val
        save_data(menu_items)
        bot.answer_callback_query(c.id, f"{key} → {val}")
        bot.send_message(c.message.chat.id, f"✅ {key}: {val}")
        send_menu(c.message.chat.id, c.from_user.id)
        admin_sessions.pop(c.from_user.id, None)
    except Exception as e:
        bot.answer_callback_query(c.id, f"Ошибка: {e}")

# ====== ПРОЧЕЕ ======
@bot.message_handler(func=lambda m: True)
def fallback(m):
    bot.send_message(m.chat.id, "Не понимаю. Используйте кнопки меню.")
    send_menu(m.chat.id, m.from_user.id)

print("✅ Бот запущен.")
bot.infinity_polling(skip_pending=True)
