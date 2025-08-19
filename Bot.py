import telebot
from telebot import types
import sqlite3
import os
import datetime
from PIL import Image
import openpyxl

# TOKENINGIZ
TOKEN = "7518059950:AAHk86-0Qv9jljSh79VB8WRB3sw8BZZHvBg"
bot = telebot.TeleBot(TOKEN)

# Admin ID lar ro'yxati
ADMINS = [123456789]  # o'zingizni Telegram ID qo'ying

# Fayllar va mijozlar ma'lumotlari uchun SQLite bazasi
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS clients (
    user_id INTEGER PRIMARY KEY,
    phone TEXT,
    name TEXT,
    debt REAL DEFAULT 0
)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    category TEXT,
    size TEXT,
    area REAL,
    price REAL,
    date TEXT
)""")
conn.commit()

# Standart narxlar
PRICES = {
    "banner": 45000,
    "qora_banner": 50000,
    "orakal": 30000,
    "matoviy_orakal": 35000,
    "setka": 40000,
    "beklit": 60000
}

# Start komandasi
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    cursor.execute("SELECT * FROM clients WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if user:
        show_main_menu(message.chat.id)
    else:
        msg = bot.send_message(message.chat.id, "Ro‘yxatdan o‘tish uchun telefon raqamingizni yuboring 📱", reply_markup=phone_request())
        bot.register_next_step_handler(msg, register_user)

def phone_request():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton("📞 Telefon raqamni yuborish", request_contact=True)
    kb.add(btn)
    return kb

def register_user(message):
    if message.contact:
        phone = message.contact.phone_number
        user_id = message.from_user.id
        name = message.from_user.first_name
        cursor.execute("INSERT OR REPLACE INTO clients (user_id, phone, name) VALUES (?, ?, ?)", (user_id, phone, name))
        conn.commit()
        bot.send_message(user_id, "✅ Ro‘yxatdan o‘tdingiz!", reply_markup=types.ReplyKeyboardRemove())
        show_main_menu(user_id)
    else:
        bot.send_message(message.chat.id, "Iltimos, tugma orqali telefon raqamingizni yuboring 📱")

# Asosiy menyu
def show_main_menu(chat_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🛒 Buyurtma", "📊 Hisobot", "📞 Aloqa")
    if chat_id in ADMINS:
        kb.add("⚙️ Admin panel")
    bot.send_message(chat_id, "Asosiy menyu:", reply_markup=kb)

# Buyurtma menyusi
def show_order_menu(chat_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🖼 Banner", "⬛ Qora Banner")
    kb.add("📐 Orakal", "✨ Matoviy Orakal")
    kb.add("🕸 Setka", "💡 Beklit")
    kb.add("⬅️ Orqaga")
    bot.send_message(chat_id, "Buyurtma turini tanlang:", reply_markup=kb)

# Orakal osti menyusi
def show_orakal_menu(chat_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("1.07", "1.27", "1.52")
    kb.add("⬅️ Orqaga")
    bot.send_message(chat_id, "Orakal turini tanlang:", reply_markup=kb)

# Hisobot menyusi
def show_report_menu(chat_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📅 Kun oralig‘ida hisobot olish", "⬅️ Orqaga")
    bot.send_message(chat_id, "Hisobot bo‘limi:", reply_markup=kb)

# Aloqa bo‘limi
def show_contact_menu(chat_id):
    bot.send_message(chat_id, "✉️ Admin bilan bog‘lanish uchun yozib qoldiring.")

# Admin menyusi
def show_admin_menu(chat_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("👥 Mijozlar", "📂 Buyurtmalar")
    kb.add("💰 Qarz boshqarish", "🧾 Ish haqi")
    kb.add("⬅️ Orqaga")
    bot.send_message(chat_id, "⚙️ Admin paneli:", reply_markup=kb)

# Fayl o‘lchamini hisoblash
def process_file(file_path, category, user_id, extra_multiplier=None):
    with Image.open(file_path) as img:
        width, height = img.size
        width_m = width / 100  # metr sifatida (100 px = 1 metr deb olindi)
        height_m = height / 100
        area = round(width_m * height_m, 2)

        # Orakal uchun maxsus hisob
        if category == "orakal" and extra_multiplier:
            area = round(extra_multiplier * height_m, 2)

        price = PRICES.get(category, 0) * area

        cursor.execute("INSERT INTO orders (user_id, category, size, area, price, date) VALUES (?, ?, ?, ?, ?, ?)", (
            user_id, category, f"{width_m}x{height_m}", area, price, datetime.date.today().isoformat()
        ))
        cursor.execute("UPDATE clients SET debt = debt + ? WHERE user_id=?", (price, user_id))
        conn.commit()

        return width_m, height_m, area, price

# Buyurtma tugmalari
@bot.message_handler(func=lambda m: True)
def handle_messages(message):
    chat_id = message.chat.id
    text = message.text

    if text == "🛒 Buyurtma":
        show_order_menu(chat_id)

    elif text == "🖼 Banner":
        bot.send_message(chat_id, "Banner faylini yuboring (JPG/TIFF)")

    elif text == "⬛ Qora Banner":
        bot.send_message(chat_id, "Qora Banner faylini yuboring (JPG/TIFF)")

    elif text == "📐 Orakal":
        show_orakal_menu(chat_id)

    elif text in ["1.07", "1.27", "1.52"]:
        bot.send_message(chat_id, f"Orakal ({text}m) faylini yuboring (JPG/TIFF)")

    elif text == "✨ Matoviy Orakal":
        bot.send_message(chat_id, "Matoviy Orakal faylini yuboring (JPG/TIFF)")

    elif text == "🕸 Setka":
        bot.send_message(chat_id, "Setka faylini yuboring (JPG/TIFF)")

    elif text == "💡 Beklit":
        bot.send_message(chat_id, "Beklit faylini yuboring (JPG/TIFF)")

    elif text == "📊 Hisobot":
        show_report_menu(chat_id)

    elif text == "📞 Aloqa":
        show_contact_menu(chat_id)

    elif text == "⚙️ Admin panel" and chat_id in ADMINS:
        show_admin_menu(chat_id)

    elif text == "⬅️ Orqaga":
        show_main_menu(chat_id)

    else:
        bot.send_message(chat_id, "❌ Noto‘g‘ri buyruq, menyudan tanlang.")

# Fayl qabul qilish
@bot.message_handler(content_types=['document', 'photo'])
def handle_files(message):
    user_id = message.from_user.id
    if message.document:
        file_info = bot.get_file(message.document.file_id)
        file_ext = os.path.splitext(message.document.file_name)[-1].lower()
        if file_ext not in [".jpg", ".jpeg", ".tiff"]:
            bot.reply_to(message, "❌ Faqat JPG yoki TIFF fayllarni yuboring.")
            return
        downloaded = bot.download_file(file_info.file_path)
        file_path = f"downloads/{message.document.file_name}"
        os.makedirs("downloads", exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(downloaded)

        width_m, height_m, area, price = process_file(file_path, "banner", user_id)
        bot.send_message(user_id, f"✅ Buyurtma qabul qilindi!\n📐 O‘lcham: {width_m}x{height_m} m\n🔲 Maydon: {area} m²\n💰 Narx: {price} so‘m")
        # === Hisobot olish ===
def generate_report(user_id, start_date, end_date, filename="report.xlsx"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Kategoriya", "O‘lcham", "Maydon (m²)", "Narx (so‘m)", "Sana"])

    cursor.execute("SELECT category, size, area, price, date FROM orders WHERE user_id=? AND date BETWEEN ? AND ?", 
                   (user_id, start_date, end_date))
    rows = cursor.fetchall()
    total_area, total_price = 0, 0
    for r in rows:
        ws.append(r)
        total_area += r[2]
        total_price += r[3]

    ws.append([])
    ws.append(["Jami", "", total_area, total_price, ""])

    wb.save(filename)
    return filename

@bot.message_handler(commands=["report"])
def ask_report(message):
    msg = bot.send_message(message.chat.id, "Hisobot uchun sanalarni kiriting (YYYY-MM-DD YYYY-MM-DD)\nMasalan: 2025-01-01 2025-01-31")
    bot.register_next_step_handler(msg, process_report)

def process_report(message):
    try:
        start_date, end_date = message.text.split()
        filename = f"report_{message.from_user.id}.xlsx"
        file = generate_report(message.from_user.id, start_date, end_date, filename)
        with open(file, "rb") as f:
            bot.send_document(message.chat.id, f)
        os.remove(file)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xato: {e}")

# === Admin: barcha mijozlarni ko‘rish ===
def export_all_clients(filename="clients.xlsx"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["ID", "Ism", "Telefon", "Qarz (so‘m)"])
    cursor.execute("SELECT user_id, name, phone, debt FROM clients")
    for row in cursor.fetchall():
        ws.append(row)
    wb.save(filename)
    return filename

@bot.message_handler(commands=["clients"])
def send_clients(message):
    if message.chat.id not in ADMINS:
        return
    file = export_all_clients()
    with open(file, "rb") as f:
        bot.send_document(message.chat.id, f)
    os.remove(file)

# === Admin: qarz boshqarish ===
@bot.message_handler(commands=["reduce_debt"])
def reduce_debt(message):
    if message.chat.id not in ADMINS:
        return
    msg = bot.send_message(message.chat.id, "Qarzdan ayirish uchun: user_id summa\nMasalan: 123456789 50000")
    bot.register_next_step_handler(msg, process_reduce)

def process_reduce(message):
    try:
        user_id, amount = message.text.split()
        amount = float(amount)
        cursor.execute("UPDATE clients SET debt = debt - ? WHERE user_id=?", (amount, int(user_id)))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ {user_id} foydalanuvchi qarzi {amount} so‘mga kamaytirildi.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xato: {e}")

# === Admin: ish haqi ===
@bot.message_handler(commands=["ishhaqi"])
def ask_salary(message):
    if message.chat.id not in ADMINS:
        return
    msg = bot.send_message(message.chat.id, "Ish haqi hisoblash uchun sanalarni kiriting (YYYY-MM-DD YYYY-MM-DD)")
    bot.register_next_step_handler(msg, process_salary)

def process_salary(message):
    try:
        start_date, end_date = message.text.split()
        cursor.execute("SELECT SUM(area) FROM orders WHERE date BETWEEN ? AND ?", (start_date, end_date))
        total_area = cursor.fetchone()[0] or 0
        salary = total_area * 1500
        bot.send_message(message.chat.id, f"🧾 {start_date} - {end_date} oralig‘ida umumiy maydon: {total_area} m²\n💰 Ish haqi: {salary} so‘m")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Xato: {e}")

# === Botni ishga tushirish ===
print("🤖 Bot ishlayapti...")
bot.infinity_polling()
