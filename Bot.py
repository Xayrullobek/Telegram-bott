import logging
import re
import os
import sqlite3
from datetime import datetime
from PIL import Image
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    filters,
)

# =========================
# CONFIG
# =========================
BOT_TOKEN = "7518059950:AAHk86-0Qv9jljSh79VB8WRB3sw8BZZHvBg"  # Bot tokeningiz
ADMIN_ID = 6988170724  # Sizning ID

# =========================
# DATABASE
# =========================
def init_db():
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()

    # Buyurtmalar
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            order_type TEXT,
            width REAL,
            height REAL,
            quantity INTEGER,
            total_area REAL,
            price REAL,
            created_at TEXT
        )
    """)

    # Narxlar
    c.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            type TEXT PRIMARY KEY,
            price REAL
        )
    """)

    # Foydalanuvchiga alohida narx
    c.execute("""
        CREATE TABLE IF NOT EXISTS user_prices (
            user_id INTEGER,
            type TEXT,
            price REAL,
            PRIMARY KEY (user_id, type)
        )
    """)

    # Default narxlarni kiritish
    default_prices = {
        "banner": 35000,
        "kichik_orakal": 25000,
        "orakal": 30000,
        "setka": 20000,
        "beklit": 40000,
    }
    for t, p in default_prices.items():
        c.execute("INSERT OR IGNORE INTO prices (type, price) VALUES (?, ?)", (t, p))

    conn.commit()
    conn.close()

def get_price(order_type, user_id=None):
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()

    if user_id:
        c.execute("SELECT price FROM user_prices WHERE user_id=? AND type=?", (user_id, order_type))
        row = c.fetchone()
        if row:
            conn.close()
            return row[0]

    c.execute("SELECT price FROM prices WHERE type=?", (order_type,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 30000

def set_price(order_type, price):
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO prices (type, price) VALUES (?, ?)", (order_type, price))
    conn.commit()
    conn.close()

def set_user_price(user_id, order_type, price):
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO user_prices (user_id, type, price) VALUES (?, ?, ?)",
              (user_id, order_type, price))
    conn.commit()
    conn.close()

def save_order(user_id, order_type, width, height, quantity, total_area, price):
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO orders (user_id, order_type, width, height, quantity, total_area, price, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, order_type, width, height, quantity, total_area, price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def get_all_orders():
    conn = sqlite3.connect("orders.db")
    c = conn.cursor()
    c.execute("SELECT * FROM orders ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return rows

# =========================
# HELPERS
# =========================
def parse_size_from_filename(filename: str):
    match = re.search(r"(\d+)[xX](\d+)", filename)
    qty_match = re.search(r"(\d+)\s*ta", filename)

    if match:
        width = float(match.group(1))
        height = float(match.group(2))
    else:
        width = height = 0

    quantity = int(qty_match.group(1)) if qty_match else 1
    return width, height, quantity

def pixels_to_meters(px, dpi=72):
    return round(px / dpi * 0.0254, 2)

# =========================
# HANDLERS
# =========================
async def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id == ADMIN_ID:
        buttons = [
            [KeyboardButton("📊 Hisobotlar"), KeyboardButton("⚙️ Narxlarni boshqarish")],
            [KeyboardButton("📝 Buyurtma berish (Admin)")],
        ]
        await update.message.reply_text(
            "👑 Assalomu alaykum, ADMIN!\nSiz boshqaruv panelidasiz.",
            reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        )
    else:
        buttons = [[KeyboardButton("📝 Buyurtma berish")]]
        await update.message.reply_text(
            "👋 Assalomu alaykum! Eng yaxshi reklama xizmatlarini taqdim etamiz.\n\n"
            "📌 Eslatma: Fayl nomida o‘lcham va nechtaligi yozilmagan bo‘lsa xatolik kelib chiqishi mumkin.",
            reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        )

async def handle_file(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    document = update.message.document
    file_name = document.file_name

    file = await context.bot.get_file(document.file_id)
    file_path = f"downloads/{file_name}"
    os.makedirs("downloads", exist_ok=True)
    await file.download_to_drive(file_path)

    width, height, quantity = parse_size_from_filename(file_name)

    if width == 0 or height == 0:
        with Image.open(file_path) as img:
            px_w, px_h = img.size
            width = pixels_to_meters(px_w)
            height = pixels_to_meters(px_h)

    order_type = context.user_data.get("order_type", "banner")

    total_area = width * height * quantity
    unit_price = get_price(order_type, user_id)
    price = total_area * unit_price

    save_order(user_id, order_type, width, height, quantity, total_area, price)

    await update.message.reply_text(
        f"✅ Buyurtma qabul qilindi!\n\n"
        f"Turi: {order_type}\n"
        f"O‘lcham: {width}m x {height}m\n"
        f"Soni: {quantity} ta\n"
        f"Umumiy maydon: {total_area:.2f} m²\n"
        f"Narx: {price:,.0f} so‘m"
    )

    if user_id != ADMIN_ID:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📥 Yangi buyurtma!\n\nTuri: {order_type}\nO‘lcham: {width}x{height}\nSoni: {quantity} ta\nUmumiy: {total_area:.2f} m²\nNarx: {price:,.0f} so‘m"
        )

async def handle_text(update: Update, context: CallbackContext):
    text = update.message.text
    user_id = update.message.from_user.id

    if text == "📝 Buyurtma berish" or text == "📝 Buyurtma berish (Admin)":
        buttons = [
            [KeyboardButton("Banner"), KeyboardButton("Kichik Orakal")],
            [KeyboardButton("Orakal"), KeyboardButton("Setka")],
            [KeyboardButton("Beklit")]
        ]
        await update.message.reply_text(
            "📌 Qaysi turdagi buyurtma berasiz?",
            reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        )

    elif text in ["Banner", "Kichik Orakal", "Orakal", "Setka", "Beklit"]:
        context.user_data["order_type"] = text.lower().replace(" ", "_")
        await update.message.reply_text(f"📂 Endi faylni yuboring ({text} uchun).")

    elif text == "📊 Hisobotlar" and user_id == ADMIN_ID:
        orders = get_all_orders()
        if not orders:
            await update.message.reply_text("❌ Buyurtmalar yo‘q.")
            return
        report = "📊 Buyurtmalar hisobot:\n\n"
        for o in orders:
            report += (f"{o[8]} | {o[2]} | {o[3]}x{o[4]} | {o[5]} ta | "
                       f"{o[6]:.2f} m² | {o[7]:,.0f} so‘m\n")
        await update.message.reply_text(report)

    elif text == "⚙️ Narxlarni boshqarish" and user_id == ADMIN_ID:
        await update.message.reply_text("📝 Narxlarni o‘zgartirish uchun buyruq yuboring:\n\n"
                                        "• `/narx banner 40000`\n"
                                        "• `/narx_user 123456789 orakal 35000`")

# Admin buyruqlari
async def set_price_cmd(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        return

    try:
        order_type = context.args[0].lower()
        new_price = int(context.args[1])
        set_price(order_type, new_price)
        await update.message.reply_text(f"✅ {order_type} narxi {new_price:,} so‘m qilib o‘rnatildi.")
    except:
        await update.message.reply_text("❌ Foydalanish: /narx <tur> <narx>")

async def set_user_price_cmd(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        return

    try:
        target_id = int(context.args[0])
        order_type = context.args[1].lower()
        new_price = int(context.args[2])
        set_user_price(target_id, order_type, new_price)
        await update.message.reply_text(f"✅ {target_id} foydalanuvchi uchun {order_type} narxi {new_price:,} so‘m qilib belgilandi.")
    except:
        await update.message.reply_text("❌ Foydalanish: /narx_user <user_id> <tur> <narx>")

# =========================
# MAIN
# =========================
def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("narx", set_price_cmd))
    application.add_handler(CommandHandler("narx_user", set_user_price_cmd))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.run_polling()

if __name__ == "__main__":
    main()
