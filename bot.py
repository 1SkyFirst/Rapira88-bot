import telebot
from telebot import types
import json, os
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

# === Настройки ===
TOKEN = os.getenv("TOKEN")
ADMINS = [1088460844, 328477968, 7028005668]  # Список ID администраторов (узнать у @userinfobot)
DATA_FILE = "data.json"
ADMIN_BUTTON = "⚙️ Админ-панель"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ====== ХРАНИЛКА ======
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    data = {
        "🧠 СОЛЕДАР": "ДОЖДЬ",
        "📅 ВЛАДИМИРОВКА": "ЛИВЕНЬ",
        "📞 ПОКРОВСКОЕ": "СУХО",
        "📞 БЕЛОГОРЛОВКА": "СУХО",
        "📞 ЯКОВЛЕВКА": "СУХО",
        "📞 ПОПАСНАЯ": "СУХО",
        "📞 КАМЫШЕВАХА": "СУХО",
        "📞 БЕРЕСТОВОЕ": "СУХО",
        "💬 ТРИПОЛЬЕ": "Пока новостей нет"
    }
    save_data(data)
    return data

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

menu_items = load_data()

def is_admin(uid: int) -> bool:
    return uid in ADMINS

# Небольшая сессия для “мастера” действий админа
admin_sessions = {}  # uid -> {"mode": "add"/"edit"/"del", "key": str|None}

# ====== UI ======
def build_user_keyboard(is_admin_user: bool) -> types.ReplyKeyboardMarkup:
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for i, name in enumerate(menu_items.keys(), start=1):
        row.append(types.KeyboardButton(name))
        if i % 2 == 0:
            kb.row(*row); row = []
    if row:
        kb.row(*row)
    if is_admin_user:
        kb.row(types.KeyboardButton(ADMIN_BUTTON))
    return kb

def send_menu(chat_id: int, user_id: int):
    kb = build_user_keyboard(is_admin(user_id))
    bot.send_message(chat_id, "👋 Привет! Выбери пункт меню:", reply_markup=kb)

def admin_panel(chat_id: int):
    ikb = types.InlineKeyboardMarkup()
    ikb.row(
        types.InlineKeyboardButton("✏️ Изменить", callback_data="admin_edit"),
        types.InlineKeyboardButton("➕ Добавить", callback_data="admin_add"),
    )
    ikb.row(
        types.InlineKeyboardButton("🗑 Удалить", callback_data="admin_del"),
        types.InlineKeyboardButton("📋 Список", callback_data="admin_list"),
    )
    ikb.row(types.InlineKeyboardButton("🔄 Обновить меню", callback_data="admin_refresh"))
    bot.send_message(chat_id, "<b>Админ-панель</b> — выберите действие:", reply_markup=ikb)

def show_list(chat_id: int):
    lines = [f"• <b>{k}</b>: {v}" for k, v in menu_items.items()]
    text = "📋 <b>Текущие кнопки</b>:\n\n" + ("\n".join(lines) if lines else "пусто")
    bot.send_message(chat_id, text)

def ask_key_from_existing(chat_id: int, mode: str):
    # Показываем клавиатуру с существующими ключами, чтобы не ошибиться с эмодзи/пробелами
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    row = []
    for i, name in enumerate(menu_items.keys(), start=1):
        row.append(types.KeyboardButton(name))
        if i % 3 == 0:
            kb.row(*row); row = []
    if row: kb.row(*row)
    bot.send_message(chat_id, f"Выберите <b>название кнопки</b> для операции «{mode}».", reply_markup=kb)

# ====== ОБРАБОТЧИКИ ======
@bot.message_handler(commands=["start", "menu"])
def on_start(m: types.Message):
    send_menu(m.chat.id, m.from_user.id)

@bot.message_handler(commands=["admin"])
def on_admin_cmd(m: types.Message):
    if not is_admin(m.from_user.id):
        return bot.send_message(m.chat.id, "🚫 У вас нет прав.")
    admin_panel(m.chat.id)

@bot.message_handler(func=lambda m: m.text == ADMIN_BUTTON)
def on_admin_button(m: types.Message):
    if not is_admin(m.from_user.id):
        return bot.send_message(m.chat.id, "🚫 У вас нет прав.")
    admin_panel(m.chat.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("admin_"))
def on_admin_callbacks(c: types.CallbackQuery):
    uid = c.from_user.id
    if not is_admin(uid):
        bot.answer_callback_query(c.id, "Нет прав.")
        return

    action = c.data[6:]
    if action == "list":
        bot.answer_callback_query(c.id)
        show_list(c.message.chat.id)

    elif action == "refresh":
        bot.answer_callback_query(c.id, "Меню обновлено")
        # просто отправим свежую клавиатуру
        send_menu(c.message.chat.id, uid)

    elif action == "add":
        bot.answer_callback_query(c.id)
        admin_sessions[uid] = {"mode": "add", "key": None}
        bot.send_message(
            c.message.chat.id,
            "➕ Отправьте <b>название новой кнопки</b>.\n"
            "Пример: <code>🗺 Карта</code>"
        )
        bot.register_next_step_handler(c.message, step_add_key)

    elif action == "edit":
        bot.answer_callback_query(c.id)
        admin_sessions[uid] = {"mode": "edit", "key": None}
        ask_key_from_existing(c.message.chat.id, "✏️ Изменить")
        bot.register_next_step_handler(c.message, step_edit_pick_key)

    elif action == "del":
        bot.answer_callback_query(c.id)
        admin_sessions[uid] = {"mode": "del", "key": None}
        ask_key_from_existing(c.message.chat.id, "🗑 Удалить")
        bot.register_next_step_handler(c.message, step_del_pick_key)

# ====== МАСТЕР: ДОБАВЛЕНИЕ ======
def step_add_key(m: types.Message):
    uid = m.from_user.id
    sess = admin_sessions.get(uid)
    if not sess or sess.get("mode") != "add":
        return
    key = (m.text or "").strip()
    if not key:
        bot.send_message(m.chat.id, "❗ Название не должно быть пустым. Повторите /admin → «Добавить».")
        return
    if key in menu_items:
        bot.send_message(m.chat.id, "⚠️ Такая кнопка уже есть. Выберите другое название или используйте «Изменить».")
        return
    sess["key"] = key
    bot.send_message(m.chat.id, f"Теперь отправьте <b>текст для кнопки</b> «{key}».")
    bot.register_next_step_handler(m, step_add_value)

def step_add_value(m: types.Message):
    uid = m.from_user.id
    sess = admin_sessions.get(uid)
    if not sess or sess.get("mode") != "add" or not sess.get("key"):
        return
    value = (m.text or "").strip()
    if not value:
        bot.send_message(m.chat.id, "❗ Текст не должен быть пустым. Операция отменена.")
        return
    menu_items[sess["key"]] = value
    save_data(menu_items)
    bot.send_message(m.chat.id, f"✅ Добавлена новая кнопка <b>{sess['key']}</b>.")
    send_menu(m.chat.id, uid)
    admin_sessions.pop(uid, None)

# ====== МАСТЕР: ИЗМЕНЕНИЕ ======
def step_edit_pick_key(m: types.Message):
    uid = m.from_user.id
    sess = admin_sessions.get(uid)
    if not sess or sess.get("mode") != "edit":
        return

    key = (m.text or "").strip()
    if key not in menu_items:
        bot.send_message(m.chat.id, "❗ Такой кнопки нет. Повторите /admin → «Изменить».")
        return

    sess["key"] = key

    # показываем выбор статуса
    ikb = types.InlineKeyboardMarkup()
    ikb.row(
        types.InlineKeyboardButton("✅ ЧИСТО", callback_data=f"edit_clean|{key}"),
        types.InlineKeyboardButton("💦 ГРЯЗНО", callback_data=f"edit_dirty|{key}")
    )

    bot.send_message(
        m.chat.id,
        f"Текущий текст для <b>{key}</b>:\n\n<code>{menu_items[key]}</code>\n\n"
        f"Выберите новый статус:",
        reply_markup=ikb
    )

# ====== CALLBACK: выбор ЧИСТО / ГРЯЗНО ======
@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_"))
def on_edit_choice(c: types.CallbackQuery):
    uid = c.from_user.id
    if not is_admin(uid):
        bot.answer_callback_query(c.id, "Нет прав.")
        return

    action, key = c.data.split("|", 1)
    if key not in menu_items:
        bot.answer_callback_query(c.id, "Кнопка не найдена.")
        return

    if action == "edit_clean":
        new_value = "ЧИСТО"
    elif action == "edit_dirty":
        new_value = "ГРЯЗНО"
    else:
        bot.answer_callback_query(c.id, "Неизвестное действие.")
        return

    menu_items[key] = new_value
    save_data(menu_items)
    bot.answer_callback_query(c.id, f"Обновлено: {key} = {new_value}")
    bot.send_message(c.message.chat.id, f"✅ Текст для <b>{key}</b> изменён на <b>{new_value}</b>.")

    # вернуть меню пользователю
    send_menu(c.message.chat.id, uid)
    admin_sessions.pop(uid, None)


# ====== МАСТЕР: УДАЛЕНИЕ ======
def step_del_pick_key(m: types.Message):
    uid = m.from_user.id
    sess = admin_sessions.get(uid)
    if not sess or sess.get("mode") != "del":
        return
    key = (m.text or "").strip()
    if key not in menu_items:
        bot.send_message(m.chat.id, "❗ Такой кнопки нет. Повторите /admin → «Удалить».")
        return
    del menu_items[key]
    save_data(menu_items)
    bot.send_message(m.chat.id, f"🗑 Кнопка <b>{key}</b> удалена.")
    send_menu(m.chat.id, uid)
    admin_sessions.pop(uid, None)

# ====== ОБЫЧНЫЕ КНОПКИ ПОЛЬЗОВАТЕЛЯ ======
@bot.message_handler(func=lambda m: m.text in menu_items)
def show_value(m: types.Message):
    bot.send_message(m.chat.id, str(menu_items[m.text]))

@bot.message_handler(func=lambda m: True)
def fallback(m: types.Message):
    # на случай произвольного текста — просто заново показать меню
    send_menu(m.chat.id, m.from_user.id)
def keepalive():
    port = int(os.getenv("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)

threading.Thread(target=keepalive, daemon=True).start()

# ====== ЗАПУСК ======
if __name__ == "__main__":
    print("✅ Бот запущен.")
    bot.infinity_polling(skip_pending=True)

