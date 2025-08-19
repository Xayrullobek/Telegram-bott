# =========================================
# IMPORTS
# =========================================
import logging
import sqlite3
from datetime import datetime

from telegram import (
    Update, KeyboardButton, ReplyKeyboardMarkup,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, CallbackContext, CallbackQueryHandler, ConversationHandler
)

# =========================================
# CONFIG
# =========================================
BOT_TOKEN = "7518059950:AAHk86-OQv9j1jSh79VB8WRXXXXXXXX"
ADMIN_ID = 6988170724   # admin ID

# Standart narxlar
default_prices = {
    "banner": 35000,
    "orakal": 45000,
    "setka": 30000,
    "beklit": 50000,
}

# =========================================
# DATABASE
# =========================================
DB_FILE = "orders.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        section TEXT,
        size TEXT,
        files_count INTEGER,
        price REAL,
        created_at TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS prices
        (section TEXT PRIMARY KEY,
        price REAL)''')

    for section, price in default_prices.items():
        cursor.execute("INSERT OR IGNORE INTO prices (section, price) VALUES (?, ?)", (section, price))

    conn.commit()
    conn.close()

def get_price(section):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT price FROM prices WHERE section=?", (section,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default_prices.get(section, 0)

def update_price(section, new_price):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO prices (section, price) VALUES (?, ?)", (section, new_price))
    conn.commit()
    conn.close()

# =========================================
# CONVERSATION STATES
# =========================================
SECTION, SIZE, FILES = range(3)

# =========================================
# USER HANDLERS
# =========================================
async def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    if user_id == ADMIN_ID:
        keyboard = [
            [KeyboardButton("📝 Buyurtma berish")],
            [KeyboardButton("📊 Admin panel")]
        ]
    else:
        keyboard = [[KeyboardButton("📝 Buyurtma berish")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Xush kelibsiz! Kerakli bo‘limni tanlang 👇", reply_markup=reply_markup)

async def order(update: Update, context: CallbackContext):
    sections = [
        [InlineKeyboardButton("Banner", callback_data="order_banner")],
        [InlineKeyboardButton("Orakal", callback_data="order_orakal")],
        [InlineKeyboardButton("Setka", callback_data="order_setka")],
        [InlineKeyboardButton("Beklit", callback_data="order_beklit")]
    ]
    reply_markup = InlineKeyboardMarkup(sections)
    await update.message.reply_text("Qaysi bo‘lim uchun buyurtma berasiz?", reply_markup=reply_markup)

async def choose_section(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    section = query.data.replace("order_", "")
    context.user_data["section"] = section
    await query.message.reply_text(f"{section.capitalize()} uchun o‘lcham kiriting (masalan: 3x6):")
    return SIZE

async def choose_size(update: Update, context: CallbackContext):
    context.user_data["size"] = update.message.text
    await update.message.reply_text("Nechta fayl kerak?")
    return FILES

async def choose_files(update: Update, context: CallbackContext):
    try:
        files_count = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Iltimos, son kiriting.")
        return FILES

    section = context.user_data["section"]
    size = context.user_data["size"]
    price_per_file = get_price(section)
    total_price = price_per_file * files_count

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (user_id, section, size, files_count, price, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                   (update.message.from_user.id, section, size, files_count, total_price, datetime.now().isoformat()))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Buyurtma qabul qilindi!\n\n"
        f"Bo‘lim: {section}\n"
        f"O‘lcham: {size}\n"
        f"Fayl soni: {files_count}\n"
        f"Umumiy narx: {total_price} so‘m"
    )
    return ConversationHandler.END

# =========================================
# ADMIN HANDLERS
# =========================================
async def admin_panel(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        return
    sections = [
        [InlineKeyboardButton("📋 Buyurtmalar", callback_data="admin_orders")],
        [InlineKeyboardButton("💰 Narxlarni sozlash", callback_data="admin_prices")]
    ]
    reply_markup = InlineKeyboardMarkup(sections)
    await update.message.reply_text("Admin panel:", reply_markup=reply_markup)

async def admin_orders(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, section, size, files_count, price, created_at FROM orders ORDER BY created_at DESC LIMIT 5")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await query.message.reply_text("Hali buyurtmalar yo‘q.")
    else:
        text = "📋 So‘nggi buyurtmalar:\n\n"
        for row in rows:
            text += f"#{row[0]} | {row[1]} | {row[2]} | {row[3]} ta | {row[4]} so‘m | {row[5][:16]}\n"
        await query.message.reply_text(text)

async def admin_prices(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    text = "💰 Hozirgi narxlar:\n\n"
    for section, price in default_prices.items():
        text += f"{section.capitalize()}: {get_price(section)} so‘m\n"
    text += "\nNarxni o‘zgartirish uchun: /setprice banner 40000"

    await query.message.reply_text(text)

async def set_price(update: Update, context: CallbackContext):
    if update.message.from_user.id != ADMIN_ID:
        return
    try:
        section, new_price = context.args
        new_price = int(new_price)
        update_price(section, new_price)
        await update.message.reply_text(f"✅ {section} narxi {new_price} so‘m qilib yangilandi.")
    except:
        await update.message.reply_text("❌ To‘g‘ri format: /setprice banner 40000")

# =========================================
# MAIN
# =========================================
def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(choose_section, pattern="^order_")],
        states={
            SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_size)],
            FILES: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_files)],
        },
        fallbacks=[],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("📝 Buyurtma berish"), order))
    application.add_handler(MessageHandler(filters.Regex("📊 Admin panel"), admin_panel))
    application.add_handler(CallbackQueryHandler(admin_orders, pattern="^admin_orders$"))
    application.add_handler(CallbackQueryHandler(admin_prices, pattern="^admin_prices$"))
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("setprice", set_price))

    application.run_polling()

if __name__ == "__main__":
    main()
