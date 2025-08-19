from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import os
import json

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))  # admin ID ni shu yerga yozasiz

# mijozlar bazasi (oddiy fayl ko‘rinishida)
DB_FILE = "clients.json"

# Fayl mavjud bo‘lmasa, yaratib qo‘yish
if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w") as f:
        json.dump({}, f)

def load_clients():
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_clients(clients):
    with open(DB_FILE, "w") as f:
        json.dump(clients, f)

# /start komandasi
def start(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    clients = load_clients()

    if str(chat_id) in clients:
        update.message.reply_text("Siz ro‘yxatdan o‘tib bo‘lgansiz ✅")
        return

    # Telefon raqamni so‘raymiz
    button = [[KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(button, resize_keyboard=True, one_time_keyboard=True)

    update.message.reply_text(
        "👋 Salom! Bu bot nimalar qila oladi:\n"
        "- Buyurtmalar berish\n"
        "- Hisobot olish\n"
        "- Admin bilan aloqa qilish\n\n"
        "📌 Eslatma: (keyin yoziladi)\n\n"
        "Ro‘yxatdan o‘tish uchun telefon raqamingizni yuboring 👇",
        reply_markup=reply_markup
    )

# Telefon raqamni qabul qilish
def contact_handler(update: Update, context: CallbackContext):
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

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.contact, contact_handler))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
