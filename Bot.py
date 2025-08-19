import os
import telebot
from telebot import types
from flask import Flask

# 🔑 Tokeningiz
TOKEN = "7518059950:AAHk86-0Qv9jljSh79VB8WRB3sw8BZZHvBg"
bot = telebot.TeleBot(TOKEN)

# === Start komandasi ===
@bot.message_handler(commands=['start'])
def start_message(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("📦 Buyurtma")
    btn2 = types.KeyboardButton("📊 Hisobot")
    btn3 = types.KeyboardButton("📞 Aloqa")
    markup.add(btn1, btn2, btn3)
    bot.send_message(
        message.chat.id,
        "👋 Salom! Botga xush kelibsiz!\nQuyidagi bo‘limlardan birini tanlang 👇",
        reply_markup=markup
    )

# === Buyurtma bo‘limi ===
@bot.message_handler(func=lambda message: message.text == "📦 Buyurtma")
def order_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("🖼 Banner")
    btn2 = types.KeyboardButton("⬛ Qora banner")
    btn3 = types.KeyboardButton("📐 Orakal")
    btn4 = types.KeyboardButton("🌫 Matoviy orakal")
    btn5 = types.KeyboardButton("#️⃣ Setka")
    btn6 = types.KeyboardButton("💡 Beklit")
    back = types.KeyboardButton("🔙 Orqaga")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, back)
    bot.send_message(message.chat.id, "📦 Buyurtma bo‘limi. Kerakli turini tanlang 👇", reply_markup=markup)

# === Hisobot bo‘limi ===
@bot.message_handler(func=lambda message: message.text == "📊 Hisobot")
def report_menu(message):
    bot.send_message(message.chat.id, "📊 Sizning hisobotlaringiz bu yerda chiqadi (hozircha tayyor emas).")

# === Aloqa bo‘limi ===
@bot.message_handler(func=lambda message: message.text == "📞 Aloqa")
def contact_menu(message):
    bot.send_message(message.chat.id, "📞 Admin bilan bog‘lanish uchun: @username")

# === Orqaga tugmasi ===
@bot.message_handler(func=lambda message: message.text == "🔙 Orqaga")
def back_to_main(message):
    start_message(message)

# === Flask server (Render uchun) ===
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot ishlayapti (Render Web Service uchun)."

# === Botni polling qilish ===
def run_bot():
    bot.polling(none_stop=True)

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=run_bot)
    t.start()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
