import os
import json
import threading
import psutil
import sys
from http.server import SimpleHTTPRequestHandler, HTTPServer
import telebot
from telebot import types

# ==================== НАСТРОЙКИ ====================
TOKEN = os.getenv("TOKEN")
DATA_FILE = "data.json"
ADMINS = [1088460844, 328477968, 7028005668]  # Список ID администраторов (узнать у @userinfobot)
PORT = int(os.getenv("PORT", 8000))

bot = telebot.TeleBot(TOKEN)
admin_sessions = {}

# ==================== ПРОВЕРКА НА ДУБЛИКАТ ====================
def already_running():
    current = psutil.Process().pid
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if proc.pid != current and 'python' in proc.name() and 'bot.py' in str(proc.cmdline()):
            return True
    return False

if already_running():
    print("⚠️ Bot already running, exiting duplicate instance.")
    sys.exit(0)

# ==================== KEEPALIVE ====================
def keepalive():
    server = HTTPServer(("0.0.0.0", PORT), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=keepalive, daemon=True).start()

# ==================== ЗАГРУЗКА/СОХРАНЕНИЕ ====================
def load_data():
    if not os.path.exists(DATA_FILE):
        print("🆕 data.json не найден — создаю с пустыми значениями.")
        data = {}
        save_data(data)
        return data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            print("⚠️ Ошибка JSON, создаю новый файл.")
            return {}
        
def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

menu_items = load_data()

# ==================== УТИЛИТЫ ====================
def is_admin(uid):
    return uid in ADMINS

def send_menu(chat_id, uid=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for name in menu_items.keys():
        markup.add(types.KeyboardButton(name))
    if is_admin(uid):
        markup.add(types.KeyboardButton("⚙️ Админ-панель"))
    bot.send_message(chat_id, "Выберите пункт:", reply_markup=markup)

# ==================== СТАРТ ====================
@bot.message_handler(commands=['start'])
def start(message):
    if not menu_items:
        bot.send_message(message.chat.id, "Нет данных. Используйте /add для добавления.")
    send_menu(message.chat.id, message.from_user.id)

# ==================== ОБРАБОТКА МЕНЮ ====================
@bot.message_handler(func=lambda m: m.text in menu_items)
def show_item(m):
    value = menu_items[m.text]
    if not value:
        value = "не задано"
    bot.send_message(m.chat.id, f"{m.text}: <b>{value}</b>", parse_mode="HTML")

# ==================== АДМИН-ПАНЕЛЬ ====================
@bot.message_handler(func=lambda m: m.text == "⚙️ Админ-панель")
def admin_panel(m):
    if not is_admin(m.from_user.id):
        return bot.send_message(m.chat.id, "🚫 Нет прав.")
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Добавить", "✏️ Изменить")
    kb.add("⬅️ Назад")
    bot.send_message(m.chat.id, "🔧 Админ-панель:", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "⬅️ Назад")
def back_to_menu(m):
    send_menu(m.chat.id, m.from_user.id)

# ==================== ДОБАВЛЕНИЕ КНОПОК ====================
@bot.message_handler(func=lambda m: m.text == "➕ Добавить")
def add_prompt(m):
    if not is_admin(m.from_user.id): return
    admin_sessions[m.from_user.id] = {"mode": "add"}
    bot.send_message(m.chat.id, "Введите название новой кнопки:")

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and admin_sessions.get(m.from_user.id, {}).get("mode") == "add")
def add_new_item(m):
    key = m.text.strip()
    if key in menu_items:
        bot.send_message(m.chat.id, "⚠️ Такая кнопка уже есть.")
    else:
        menu_items[key] = "не задано"
        save_data(menu_items)
        bot.send_message(m.chat.id, f"✅ Добавлена кнопка '{key}'.")
    admin_sessions.pop(m.from_user.id, None)
    send_menu(m.chat.id, m.from_user.id)

# ==================== ИЗМЕНЕНИЕ ЗНАЧЕНИЯ ====================
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
    admin_sessions[m.from_user.id] = {"mode": "set", "key": key}
    ikb = types.InlineKeyboardMarkup()
    ikb.row(
        types.InlineKeyboardButton("✅ ЧИСТО", callback_data=f"set|{key}|ЧИСТО"),
        types.InlineKeyboardButton("💦 ГРЯЗНО", callback_data=f"set|{key}|ГРЯЗНО")
    )
    bot.send_message(m.chat.id, f"Выберите новое значение для <b>{key}</b>:", parse_mode="HTML", reply_markup=ikb)

# ==================== CALLBACK ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("set|"))
def on_set_value(c):
    _, key, value = c.data.split("|", 2)
    menu_items[key] = value
    save_data(menu_items)
    bot.answer_callback_query(c.id, f"{key} → {value}")
    bot.send_message(c.message.chat.id, f"✅ {key}: {value}")
    send_menu(c.message.chat.id, c.from_user.id)
    admin_sessions.pop(c.from_user.id, None)

# ==================== FALLBACK ====================
@bot.message_handler(func=lambda m: True)
def unknown(m):
    bot.send_message(m.chat.id, "Не понимаю. Используйте кнопки меню.")
    send_menu(m.chat.id, m.from_user.id)

# ==================== ЗАПУСК ====================
print("✅ Бот запущен.")
bot.infinity_polling(skip_pending=True)
