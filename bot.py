import telebot

# === Настройки ===
import os
TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)

# === Список элементов ===
menu_items = {
    "🧠 Информация": "Этот бот создан для демонстрации меню с кнопками.",
    "📅 Расписание": "Пн–Пт: 10:00–19:00\nСб: 11:00–17:00\nВс: выходной.",
    "📞 Контакты": "Телефон: +7 999 123-45-67\nTelegram: @admin",
    "💬 Новости": "Пока новостей нет 😊"
}

# === Команда /start ===
@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for item in menu_items.keys():
        markup.add(telebot.types.KeyboardButton(item))
    bot.send_message(
        message.chat.id,
        "👋 Привет! Выбери пункт меню:",
        reply_markup=markup
    )

# === Обработка нажатий ===
@bot.message_handler(func=lambda message: message.text in menu_items.keys())
def show_info(message):
    bot.send_message(message.chat.id, menu_items[message.text])

# === Обработка прочих сообщений ===
@bot.message_handler(func=lambda message: True)
def unknown(message):
    bot.send_message(message.chat.id, "❓ Не понимаю. Используй кнопки меню.")

# === Запуск ===
print("✅ Бот запущен.")
bot.infinity_polling()
