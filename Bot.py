import logging import re import os import sqlite3 from datetime import datetime from PIL import Image

from telegram import ( Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, InputFile ) from telegram.ext import ( Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters )

=============================

CONFIG

=============================

BOT_TOKEN = "7518059950:AAHk86-0Qv9jljSh79VB8WRB3sw8BZZHvBg" ADMIN_ID = 6988170724 DB_FILE = "bot.db"

Narhlar (standart)

default_prices = { "banner": 35000, "qora_banner": 30000, "orakal_107": 25000, "orakal_127": 27000, "orakal_152": 30000, "orakal_kichik": 20000, "matoviy_orakal": 32000, "setka": 28000, "beklit": 40000 }

=============================

DATABASE

=============================

def init_db(): conn = sqlite3.connect(DB_FILE) c = conn.cursor() c.execute(""" CREATE TABLE IF NOT EXISTS users ( user_id INTEGER PRIMARY KEY, phone TEXT, is_admin INTEGER DEFAULT 0 )""") c.execute(""" CREATE TABLE IF NOT EXISTS orders ( id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, type TEXT, width REAL, height REAL, count INTEGER, area REAL, price REAL, created_at TEXT )""") c.execute(""" CREATE TABLE IF NOT EXISTS prices ( user_id INTEGER, type TEXT, price REAL, PRIMARY KEY(user_id, type) )""") conn.commit() conn.close()

=============================

HELPERS

=============================

def get_price(user_id, order_type): conn = sqlite3.connect(DB_FILE) c = conn.cursor() c.execute("SELECT price FROM prices WHERE user_id=? AND type=?", (user_id, order_type)) row = c.fetchone() conn.close() if row: return row[0] return default_prices.get(order_type, 0)

def save_order(user_id, order_type, width, height, count, area, price): conn = sqlite3.connect(DB_FILE) c = conn.cursor() c.execute("INSERT INTO orders (user_id,type,width,height,count,area,price,created_at) VALUES (?,?,?,?,?,?,?,?)", (user_id, order_type, width, height, count, area, price, datetime.now().strftime("%Y-%m-%d %H:%M"))) conn.commit() conn.close()

def parse_filename(filename): pattern = r"(\d+(?:[.,]\d+)?)x(\d+(?:[.,]\d+)?)(?:[^\d]*(\d+))?" match = re.search(pattern, filename) if match: width = float(match.group(1).replace(",", ".")) height = float(match.group(2).replace(",", ".")) count = int(match.group(3)) if match.group(3) else 1 return width, height, count return None, None, 1

def image_to_meters(file_path): try: with Image.open(file_path) as img: dpi = img.info.get('dpi', (72, 72))[0] width_px, height_px = img.size width_m = width_px / dpi * 0.0254 height_m = height_px / dpi * 0.0254 return round(width_m, 2), round(height_m, 2) except: return None, None

=============================

HANDLERS

=============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = update.effective_user.id conn = sqlite3.connect(DB_FILE) c = conn.cursor() c.execute("INSERT OR IGNORE INTO users (user_id, phone, is_admin) VALUES (?, ?, ?)", (user_id, None, 1 if user_id == ADMIN_ID else 0)) conn.commit() conn.close()

text = (
    "Assalomu alaykum! 👋 Bizning botimiz eng yaxshi reklama xizmatlarini taqdim etadi.\n\n"
    "📌 *Eslatma*: Fayl nomida o‘lcham va soni yozilmagan bo‘lsa, natijada hisobda xato chiqishi mumkin.\n"
)
btn = [[KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True)]]
await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(btn, resize_keyboard=True))

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE): phone = update.message.contact.phone_number user_id = update.effective_user.id conn = sqlite3.connect(DB_FILE) c = conn.cursor() c.execute("UPDATE users SET phone=? WHERE user_id=?", (phone, user_id)) conn.commit() conn.close() await show_menu(update, context)

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE): user_id = update.effective_user.id conn = sqlite3.connect(DB_FILE) c = conn.cursor() c.execute("SELECT is_admin FROM users WHERE user_id=?", (user_id,)) is_admin = c.fetchone()[0] conn.close()

buttons = [
    ["📝 Buyurtma"],
    ["📊 Hisobot"],
    ["📞 Aloqa"]
]
if is_admin:
    buttons.append(["⚙️ Admin panel"])
await update.message.reply_text("Menyudan tanlang:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))

=============================

MAIN

=============================

def main(): init_db() app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.CONTACT, contact_handler))

logging.basicConfig(level=logging.INFO)
app.run_polling()

if name == "main": main()

