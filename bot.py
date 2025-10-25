import telebot
import json
import os

# === Настройки ===
TOKEN = os.getenv("TOKEN")
ADMINS = [1088460844, 328477968, 7028005668]  # Список ID администраторов (узнать у @userinfobot)
DATA_FILE = "data.json"

bot = telebot.TeleBot(TOKEN)

# === Загрузка меню ===
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        menu_items = json.load(f)
else:
    menu_items = {
        "СОЛЕДАР": "ДОЖДЬ",
        "ВЛАДИМИРОВКА": "ЛИВЕНЬ",
        "ПОПАСНАЯ": "СУХО",
        "ЯКОВЛЕВКА": "Пока новостей нет 😊"
    }

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(menu_items, f, ensure_ascii=False, indent=2)

def is_admin(uid): return uid in ADMINS

@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for name in menu_items.keys():
        markup.add(telebot.types.KeyboardButton(name))
    bot.send_message(message.chat.id, "👋 Привет! Выбери пункт меню:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in menu_items)
def show(m): bot.send_message(m.chat.id, menu_items[m.text])

# === /set поддерживает пробелы и эмодзи ===
@bot.message_handler(commands=['set'])
def set_item(message):
    if not is_admin(message.from_user.id):
        return bot.send_message(message.chat.id, "🚫 Нет прав.")

    try:
        _, rest = message.text.split(" ", 1)
    except ValueError:
        return bot.send_message(message.chat.id, "❗ Формат: /set <название> <новый текст>")

    # находим первую часть (название кнопки)
    found = None
    for key in menu_items.keys():
        if rest.startswith(key):
            found = key
            break

    if not found:
        return bot.send_message(message.chat.id, "❗ Такой кнопки нет. Используйте /add для новой.")

    new_text = rest[len(found):].strip()
    if not new_text:
        return bot.send_message(message.chat.id, "❗ Укажите новый текст после названия кнопки.")

    menu_items[found] = new_text
    save_data()
    bot.send_message(message.chat.id, f"✅ Текст для '{found}' обновлён.")

# === /add также поддерживает пробелы ===
@bot.message_handler(commands=['add'])
def add_item(message):
    if not is_admin(message.from_user.id):
        return bot.send_message(message.chat.id, "🚫 Нет прав.")

    try:
        _, rest = message.text.split(" ", 1)
    except ValueError:
        return bot.send_message(message.chat.id, "❗ Формат: /add <название> <текст>")
    
    parts = rest.strip().split(" ", 1)
    if len(parts) < 2:
        return bot.send_message(message.chat.id, "❗ Формат: /add <название> <текст>")

    key, text = parts[0], parts[1]
    if key in menu_items:
        return bot.send_message(message.chat.id, "⚠️ Такая кнопка уже есть. Используйте /set для изменения.")

    menu_items[key] = text
    save_data()
    bot.send_message(message.chat.id, f"✅ Добавлена новая кнопка '{key}'.")

bot.infinity_polling()
