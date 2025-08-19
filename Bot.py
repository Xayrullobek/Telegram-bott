from telegram.ext import Updater, CommandHandler
import os

# Tokenni Render env dan olamiz
TOKEN = os.getenv("BOT_TOKEN")

def start(update, context):
    update.message.reply_text("Salom! Men Render’da 24/7 ishlayapman 🚀")

updater = Updater(TOKEN, use_context=True)
dp = updater.dispatcher
dp.add_handler(CommandHandler("start", start))

# Botni ishga tushirish
updater.start_polling()
updater.idle()
