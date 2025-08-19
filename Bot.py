import os
import telebot
from telebot import types
from flask import Flask
import threading

# 🔑 Tokenni shu yerga yozib qo'yamiz
TOKEN = "7518059950:AAHk86-0Qv9jljSh79VB8WRB3sw8BZZHvBg"
bot = telebot.TeleBot(TOKEN)

# ================= Flask APP (Render uchun) =================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running on Render ✅"

# ================== BOT MENYULARI ==================

# Start command
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("📊 Banner")
    btn2 = types.KeyboardButton("🔮 Oracle setka")
    btn3 = types.KeyboardButton("📑 Hisobot")
    btn4 = types.KeyboardButton("⚙️ Admin panel")
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    bot.send_message(message.chat.id, "Salom! Menyudan bo‘lim tanlang 👇", reply_markup=markup)

# Banner
@bot.message_handler(func=lambda m: m.text == "📊 Banner")
def banner_section(message):
    bot.reply_to(message, "📊 Banner bo‘limidasiz. Bu yerda bannerlar bilan ishlash mumkin.")

# Oracle setka
@bot.message_handler(func=lambda m: m.text == "🔮 Oracle setka")
def oracle_section(message):
    bot.reply_to(message, "🔮 Oracle setka bo‘limidasiz. Bu yerda tahlillar chiqadi.")

# Hisobot
@bot.message_handler(func=lambda m: m.text == "📑 Hisobot")
def report_section(message):
    bot.reply_to(message, "📑 Hisobot bo‘limidasiz. Bu yerda hisobotlar tayyorlanadi.")

# Admin panel
@bot.message_handler(func=lambda m: m.text == "⚙️ Admin panel")
def admin_section(message):
    bot.reply_to(message, "⚙️ Admin panelga kirdingiz. Bu yerda faqat adminlar ishlashi mumkin.")

# Unknown command handler
@bot.message_handler(func=lambda m: True)
def echo_all(message):
    bot.reply_to(message, "❓ Noto‘g‘ri buyruq. /start tugmasini bosib menyudan tanlang.")

# ================== BOTNI ISHGA TUSHIRISH ==================

def run_bot():
    bot.polling(none_stop=True)

if __name__ == "__main__":
    # Botni alohida oqimda ishga tushiramiz
    threading.Thread(target=run_bot).start()

    # Flaskni Render portida ishga tushiramiz
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
