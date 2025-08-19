from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import os
import json

TOKEN = os.getenv("BOT_TOKEN")

DB_FILE = "clients.json"
if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w") as f:
        json.dump({}, f)

def load_clients():
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_clients(clients):
    with open(DB_FILE, "w") as f:
        json.dump(clients, f)

# --- ASOSIY MENYU ---
def main_menu(update, context):
    keyboard = [
        ["🛒 Buyurtma"],
        ["📊 Hisobot"],
        ["📞 Aloqa"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📍 Asosiy menyu:",
        reply_markup=reply_markup
    )

# --- START ---
def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    clients = load_clients()

    if str(chat_id) in clients:
        update.message.reply_text("Siz ro‘yxatdan o‘tib bo‘lgansiz ✅")
        main_menu(update, context)
        return

    button = [[KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(button, resize_keyboard=True, one_time_keyboard=True)

    update.message.reply_text(
        "👋 Salom! Ro‘yxatdan o‘tish uchun telefon raqamingizni yuboring 👇",
        reply_markup=reply_markup
    )

# --- TELEFON RAQAM QABUL QILISH ---
def contact_handler(update, context):
    chat_id = update.message.chat_id
    contact = update.message.contact

    clients = load_clients()
    clients[str(chat_id)] = {
        "phone": contact.phone_number,
        "name": update.message.chat.first_name,
        "debt": 0
    }
    save_clients(clients)

    update.message.reply_text("✅ Siz mijoz sifatida ro‘yxatdan o‘tdingiz!")
    main_menu(update, context)

# --- MENYU BOSILGANDA ---
def menu_handler(update, context):
    text = update.message.text

    if text == "🛒 Buyurtma":
        update.message.reply_text("Siz Buyurtma bo‘limini tanladingiz.")
    elif text == "📊 Hisobot":
        update.message.reply_text("Siz Hisobot bo‘limini tanladingiz.")
    elif text == "📞 Aloqa":
        update.message.reply_text("Siz Aloqa bo‘limini tanladingiz.")
    else:
        update.message.reply_text("❓ Menyu tugmalaridan birini tanlang.")

# --- MAIN ---
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.contact, contact_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, menu_handler))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
