import telebot
from telebot import types
import os
from flask import Flask, request
from openpyxl import Workbook
from datetime import datetime

# === Muhit o'zgaruvchilari (Render .env faylida saqlanadi) ===
BOT_TOKEN = os.environ.get("BOT_TOKEN", "TOKENINGIZNI_QOYING")
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://telegram-bott.onrender.com")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# === Admin va narx sozlamalari ===
admins = [6988170724]  # Sizning ID
prices = {
    "banner": 35000,
    "qora_banner": 36000,
    "orakal": 38000,
    "setka": 30000
}

# Buyurtmalar vaqtincha saqlanadi
user_orders = {}
all_orders = []  # barcha buyurtmalarni umumiy saqlash (hisobot uchun)

# === Asosiy menyu ===
def get_main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📝 Buyurtma berish", callback_data="order"))
    markup.add(types.InlineKeyboardButton("📊 Hisobot", callback_data="report"))
    markup.add(types.InlineKeyboardButton("📞 Aloqa", callback_data="contact"))
    if True:  # adminlar uchun panel
        markup.add(types.InlineKeyboardButton("⚙️ Admin panel", callback_data="admin"))
    return markup

# === Start komandasi ===
@bot.message_handler(commands=["start"])
def start_command(message):
    bot.send_message(
        message.chat.id,
        "Assalomu alaykum! Kerakli bo‘limni tanlang 👇",
        reply_markup=get_main_menu()
    )

# === Tugmalarni boshqarish ===
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "order":
        user_orders[call.from_user.id] = []
        bot.send_message(call.message.chat.id, "📎 Fayllarni yuboring (masalan: 147x150.jpg)")
    elif call.data == "report":
        send_report(call.message.chat.id)
    elif call.data == "contact":
        bot.send_message(call.message.chat.id, "✍️ Xabar yuboring, admin ko‘radi.")
    elif call.data == "admin":
        if call.from_user.id in admins:
            show_admin_panel(call.message.chat.id)
        else:
            bot.send_message(call.message.chat.id, "❌ Siz admin emassiz.")
    elif call.data.startswith("setprice_"):
        material = call.data.split("_")[1]
        msg = bot.send_message(call.message.chat.id, f"💵 Yangi narxni kiriting (1 m² uchun) → {material}")
        bot.register_next_step_handler(msg, set_new_price, material)
    elif call.data == "finish_order":
        finish_order(call)

# === Admin panel ===
def show_admin_panel(chat_id):
    markup = types.InlineKeyboardMarkup()
    for key, val in prices.items():
        markup.add(types.InlineKeyboardButton(f"{key} ({val} so‘m)", callback_data=f"setprice_{key}"))
    bot.send_message(chat_id, "⚙️ Admin panel - narxlarni boshqarish:", reply_markup=markup)

def set_new_price(message, material):
    try:
        new_price = int(message.text)
        prices[material] = new_price
        bot.send_message(message.chat.id, f"✅ {material} narxi {new_price} so‘m qilib o‘zgartirildi.")
    except:
        bot.send_message(message.chat.id, "❌ Raqam kiriting.")

# === Fayl qabul qilish va hisoblash ===
@bot.message_handler(content_types=["document"])
def handle_file(message):
    file_name = message.document.file_name
    user_id = message.from_user.id

    try:
        name, _ = file_name.split(".")
        parts = name.split("x")
        eni = float(parts[0]) / 100
        boyi = float(parts[1]) / 100
        kvadrat = round(eni * boyi, 2)
        narx = round(kvadrat * prices["banner"], 2)
    except Exception:
        bot.send_message(message.chat.id, "❌ Fayl nomida o‘lcham topilmadi (masalan: 147x150.jpg).")
        return

    if user_id not in user_orders:
        user_orders[user_id] = []
    user_orders[user_id].append((file_name, eni, boyi, kvadrat, narx))

    # Inline tugma
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📤 Pechatga berish", callback_data="finish_order"))

    bot.send_message(
        message.chat.id,
        f"✅ Qabul qilindi: {file_name}\n"
        f"Eni: {eni} m | Boyi: {boyi} m\n"
        f"Maydoni: {kvadrat} m²\n"
        f"Narxi: {narx} so‘m",
        reply_markup=markup
    )

# === Buyurtmani yakunlash va Excel chiqarish ===
def finish_order(call):
    user_id = call.from_user.id
    files = user_orders.get(user_id, [])

    if not files:
        bot.send_message(call.message.chat.id, "❌ Fayl topilmadi.")
        return

    wb = Workbook()
    ws = wb.active
    ws.append(["Fayl", "Eni (m)", "Boyi (m)", "Maydon (m²)", "Narxi (so‘m)"])

    total_price = 0
    for file_name, eni, boyi, kvadrat, narx in files:
        ws.append([file_name, eni, boyi, kvadrat, narx])
        total_price += narx
        all_orders.append((user_id, file_name, eni, boyi, kvadrat, narx, datetime.now().strftime("%Y-%m-%d")))

    ws.append(["", "", "", "Umumiy", total_price])

    filename = f"order_{user_id}.xlsx"
    wb.save(filename)

    with open(filename, "rb") as f:
        bot.send_document(call.message.chat.id, f, caption="📄 Buyurtma hisobot")

    os.remove(filename)
    user_orders[user_id] = []

# === Umumiy hisobot ===
def send_report(chat_id):
    if not all_orders:
        bot.send_message(chat_id, "📊 Hali buyurtmalar yo‘q.")
        return

    wb = Workbook()
    ws = wb.active
    ws.append(["User ID", "Fayl", "Eni (m)", "Boyi (m)", "Maydon (m²)", "Narxi (so‘m)", "Sana"])

    for order in all_orders:
        ws.append(order)

    filename = "report.xlsx"
    wb.save(filename)

    with open(filename, "rb") as f:
        bot.send_document(chat_id, f, caption="📊 Umumiy hisobot")

    os.remove(filename)

# === Webhook ===
@app.route("/" + BOT_TOKEN, methods=["POST"])
def getMessage():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
    return "Webhook set", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
