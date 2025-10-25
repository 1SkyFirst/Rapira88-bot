import telebot
import json
import os

# === Настройки ===
TOKEN = os.getenv("TOKEN")
ADMINS = [1088460844, 328477968]  # Список ID администраторов (узнать у @userinfobot)
DATA_FILE = "data.json"

bot = telebot.TeleBot(TOKEN)

# === Загрузка/инициализация меню ===
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        menu_items = json.load(f)
else:
    menu_items = {
        "🧠 СОЛЕДАР": "ДОЖДЬ",
        "📅 ВЛАДИМИРОВКА": "ЛИВЕНЬ",
        "📞 ПОПАСНАЯ": "СУХО",
        "💬 ЯКОВЛЕВКА": "Пока новостей нет 😊"
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(menu_items, f, ensure_ascii=False, indent=2)


# === /start ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for item in menu_items.keys():
        markup.add(telebot.types.KeyboardButton(item))
    bot.send_message(message.chat.id, "👋 Привет! Выбери пункт меню:", reply_markup=markup)


# === Вывод значений ===
@bot.message_handler(func=lambda message: message.text in menu_items.keys())
def show_info(message):
    bot.send_message(message.chat.id, menu_items[message.text])


# === Проверка прав администратора ===
def is_admin(user_id):
    return user_id in ADMINS


# === /set: изменить текст существующей кнопки ===
@bot.message_handler(commands=['set'])
def set_value(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 У вас нет прав для изменения.")
        return

    parts = message.text.split(" ", 2)
    if len(parts) < 3:
        bot.send_message(message.chat.id, "❗ Формат: /set <название_кнопки> <новый_текст>")
        return

    key, value = parts[1], parts[2]
    if key not in menu_items:
        bot.send_message(message.chat.id, "❗ Такой кнопки нет. Используйте /add для создания новой.")
        return

    menu_items[key] = value
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(menu_items, f, ensure_ascii=False, indent=2)

    bot.send_message(message.chat.id, f"✅ Текст для '{key}' обновлён.")


# === /add: добавить новую кнопку ===
@bot.message_handler(commands=['add'])
def add_button(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "🚫 У вас нет прав для добавления.")
        return

    parts = message.text.split(" ", 2)
    if len(parts) < 3:
        bot.send_message(message.chat.id, "❗ Формат: /add <название_кнопки> <текст>")
        return

    key, value = parts[1], parts[2]
    if key in menu_items:
        bot.send_message(message.chat.id, "⚠️ Такая кнопка уже существует. Используйте /set для изменения.")
        return

    menu_items[key] = value
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(menu_items, f, ensure_ascii=False, indent=2)

    bot.send_message(message.chat.id, f"✅ Добавлена новая кнопка '{key}'.")

# === /list: показать все кнопки (для админов) ===
@bot.message_handler(commands=['list'])
def list_buttons(message):
    if not is_admin(message.from_user.id):
        return
    text = "📋 Текущие кнопки:\n\n" + "\n".join([f"{k}: {v}" for k, v in menu_items.items()])
    bot.send_message(message.chat.id, text)


# === Обработка прочего ===
@bot.message_handler(func=lambda message: True)
def unknown(message):
    bot.send_message(message.chat.id, "❓ Не понимаю. Используй кнопки меню.")


# === Запуск ===
print("✅ Бот запущен.")
bot.infinity_polling()
