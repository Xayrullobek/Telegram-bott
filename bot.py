import os
import re
import telebot
import pandas as pd
from flask import Flask, request
from datetime import datetime

# ====== Config ======
TOKEN = os.getenv("BOT_TOKEN", "7518059950:AAHk86-0Qv9jljSh79VB8WRB3sw8BZZHvBg")
ADMIN_ID = int(os.getenv("ADMIN_ID", "6988170724"))
APP_URL = os.getenv("APP_URL", "https://telegram-bott-ejvk.onrender.com")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ====== Memory storage ======
orders = {}  # {user_id: {"section": str, "files": [dict]}}
prices = {
    "banner": 50,
    "qora_banner": 60,
    "orakal": 40,
    "matoviy_orakal": 45,
    "setka": 30
}
admins = {ADMIN_ID}
history = []  # [{user, section, files, date}]

# ====== Keyboards ======
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📦 Buyurtma berish", "📊 Hisobotlar")
    kb.add("⚙️ Admin panel", "📞 Aloqa")
    return kb

def order_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🖼 Banner", "⬛ Qora Banner")
    kb.add("📜 Orakal", "📜 Matoviy Orakal")
    kb.add("#️⃣ Setka")
    kb.add("⬅️ Orqaga")
    return kb

def inline_print_button():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Pechatga berish", callback_data="print_order"))
    return kb

# ====== Utils ======
def parse_size(filename):
    """ Fayl nomidan eni va bo‘yni ajratib olish (cm -> m) """
    match = re.search(r'(\d+)[xX](\d+)', filename)
    if not match:
        return None, None, None
    w_cm, h_cm = int(match.group(1)), int(match.group(2))
    w_m, h_m = w_cm / 100, h_cm / 100
    area = round(w_m * h_m, 3)
    return w_m, h_m, area

def calculate_price(section, filename):
    w, h, area = parse_size(filename)
    if not area:
        return 0, 0, 0
    if section in ["banner", "qora_banner", "setka"]:
        summa = round(area * prices[section], 2)
        return area, summa, h
    elif section in ["orakal", "matoviy_orakal"]:
        # Faqat bo‘yi hisoblanadi (kvadrat emas)
        summa = round(h * prices[section], 2)
        return h, summa, h
    return 0, 0, 0

def generate_excel(user_id, section, files):
    rows = []
    total = 0
    for f in files:
        area, summa, height = calculate_price(section, f["name"])
        rows.append({
            "Fayl nomi": f["name"],
            "O‘lcham": f"{height} m",
            "Hisoblangan": area,
            "Narxi": summa
        })
        total += summa
    df = pd.DataFrame(rows)
    df.loc[len(df.index)] = ["Jami", "", "", total]
    filename = f"order_{user_id}_{int(datetime.now().timestamp())}.xlsx"
    df.to_excel(filename, index=False)
    return filename

# ====== Handlers ======
@bot.message_handler(commands=['start'])
def start(msg):
    bot.send_message(msg.chat.id, "Assalomu alaykum! Asosiy menyu:", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "📦 Buyurtma berish")
def buyurtma(msg):
    orders[msg.chat.id] = {"section": None, "files": []}
    bot.send_message(msg.chat.id, "Kerakli bo‘limni tanlang:", reply_markup=order_menu())

@bot.message_handler(func=lambda m: m.text in ["🖼 Banner", "⬛ Qora Banner", "📜 Orakal", "📜 Matoviy Orakal", "#️⃣ Setka"])
def choose_section(msg):
    mapping = {
        "🖼 Banner": "banner",
        "⬛ Qora Banner": "qora_banner",
        "📜 Orakal": "orakal",
        "📜 Matoviy Orakal": "matoviy_orakal",
        "#️⃣ Setka": "setka"
    }
    orders[msg.chat.id] = {"section": mapping[msg.text], "files": []}
    bot.send_message(msg.chat.id, f"{msg.text} bo‘limiga fayllarni yuboring.\nTayyor bo‘lgach '✅ Pechatga berish' tugmasini bosing.", reply_markup=inline_print_button())

@bot.message_handler(content_types=['document', 'photo'])
def handle_files(msg):
    if msg.chat.id not in orders or not orders[msg.chat.id]["section"]:
        bot.delete_message(msg.chat.id, msg.message_id)  # boshqa joyda fayl yuborilsa o‘chirish
        return
    file_name = msg.document.file_name if msg.content_type == "document" else f"photo_{msg.message_id}.jpg"
    orders[msg.chat.id]["files"].append({"name": file_name})
    # Fayl qabul qilinganda xabar bermaymiz

@bot.callback_query_handler(func=lambda c: c.data == "print_order")
def finalize_order(call):
    data = orders.get(call.message.chat.id)
    if not data or not data["files"]:
        bot.answer_callback_query(call.id, "Fayl yuborilmagan!", show_alert=True)
        return
    excel_file = generate_excel(call.message.chat.id, data["section"], data["files"])
    bot.send_message(call.message.chat.id, "✅ Buyurtmangiz qabul qilindi!")
    with open(excel_file, "rb") as f:
        bot.send_document(call.message.chat.id, f)
    history.append({"user": call.message.chat.id, "section": data["section"], "files": data["files"], "date": datetime.now()})
    os.remove(excel_file)
    orders[call.message.chat.id] = {"section": None, "files": []}

# ====== Flask Webhook ======
@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "OK", 200

@app.route("/")
def index():
    bot.remove_webhook()
    bot.set_webhook(url=f"{APP_URL}/{TOKEN}")
    return "Bot ishlayapti!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
