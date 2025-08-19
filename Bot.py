# bot.py
import json
import os
import datetime
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler
)

TOKEN = "YOUR_BOT_TOKEN"  # <-- shu yerga tokeningizni yozasiz
ADMIN_IDS = [6988170724]  # siz admin sifatida belgilandingiz

DATA_FILE = "data.json"

# Agar data.json bo'lmasa, yaratamiz
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"users": {}, "orders": [], "prices": {
            "banner": 45000,
            "qora_banner": 55000,
            "beklit": 65000,
            "orakal": 55000,
            "matoviy_orakal": 55000,
            "setka": 55000
        }, "admins": ADMIN_IDS}, f)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- Start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    data = load_data()
    if str(user_id) not in data["users"]:
        # yangi foydalanuvchi
        data["users"][str(user_id)] = {
            "name": update.message.from_user.full_name,
            "username": update.message.from_user.username,
            "phone": None
        }
        save_data(data)
        # Eslatma matni
        text = (
            "📌 *Eslatma*\n\n"
            "Yuborilayotgan fayl TIFF yoki JPG shaklida bo‘lishi va fayl nomida "
            "o‘lchami va soni yozilgan bo‘lishi shart. Aks holda faylingiz qabul qilinmaydi!"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
        # Ro'yxatdan o'tish tugmasi
        button = KeyboardButton("📱 Raqamni ulashish", request_contact=True)
        await update.message.reply_text("Ro‘yxatdan o‘tish uchun raqamingizni ulashing:",
                                        reply_markup=ReplyKeyboardMarkup([[button]], resize_keyboard=True))
    else:
        await main_menu(update, context)

# --- Ro‘yxatdan o‘tish ---
async def register_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    contact = update.message.contact
    data = load_data()
    if str(user_id) in data["users"]:
        data["users"][str(user_id)]["phone"] = contact.phone_number
        save_data(data)
        await update.message.reply_text("✅ Ro‘yxatdan o‘tish muvaffaqiyatli!", reply_markup=None)
        await main_menu(update, context)

# --- Asosiy menyu ---
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📦 Buyurtma", "📊 Hisobot"],
        ["📞 Aloqa"]
    ]
    if update.message:
        await update.message.reply_text("Asosiy menyu:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    else:
        await update.callback_query.message.reply_text("Asosiy menyu:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

# --- Buyurtma menyu ---
async def order_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📜 Banner", "⚫ Qora Banner"],
        ["🪧 Beklit", "🖼 Orakal"],
        ["✨ Matoviy Orakal", "🔲 Setka"],
        ["⬅️ Orqaga"]
    ]
    await update.message.reply_text("Buyurtma bo‘limi:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

# --- Hisobot ---
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    data = load_data()
    orders = [o for o in data["orders"] if o["user_id"] == user_id]
    if not orders:
        await update.message.reply_text("❌ Sizda hali buyurtmalar yo‘q.")
        return
    text = "📊 Sizning buyurtmalaringiz:\n\n"
    for o in orders:
        text += f"{o['date']} | {o['type']} | {o['size']} m² | {o['count']} dona | {o['price']} so‘m\n"
    await update.message.reply_text(text)

# --- Aloqa ---
async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✉️ Adminlarga xabar yuboring, ular siz bilan bog‘lanishadi.")

# --- Admin panel ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Siz admin emassiz.")
        return
    keyboard = [
        ["💰 Narhlarni boshqarish", "📈 Ish haqi"],
        ["👥 Admin boshqaruvi", "💳 Qarzlarni boshqarish"],
        ["📦 Buyurtmalar ro‘yxati", "⬅️ Orqaga"]
    ]
    await update.message.reply_text("⚙️ Admin paneli:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

# --- Fallback ---
async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    if msg == "📦 Buyurtma":
        await order_menu(update, context)
    elif msg == "📊 Hisobot":
        await report(update, context)
    elif msg == "📞 Aloqa":
        await contact_admin(update, context)
    elif msg == "⬅️ Orqaga":
        await main_menu(update, context)
    elif msg == "⚙️ Admin":
        await admin_panel(update, context)
    else:
        await update.message.reply_text("❓ Noma’lum buyruq.")

# --- Run bot ---
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, register_contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler))
    app.run_polling()

if __name__ == "__main__":
    main()
    import re

# --- Fayl qabul qilish va hisoblash ---
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    data = load_data()

    if not update.message.document:
        await update.message.reply_text("❌ Iltimos, TIFF yoki JPG fayl yuboring.")
        return

    file_name = update.message.document.file_name.lower()

    # Fayl nomidan o‘lchamlarni ajratamiz (masalan: "2x5", "3x7 4ta")
    size_match = re.search(r"(\d+)[xX](\d+)", file_name)
    count_match = re.search(r"(\d+)\s*ta", file_name)

    count = int(count_match.group(1)) if count_match else 1

    # --- Buyurtma turi aniqlash ---
    order_type = None
    if "banner" in file_name and "qora" not in file_name:
        order_type = "banner"
    elif "qora" in file_name:
        order_type = "qora_banner"
    elif "beklit" in file_name:
        order_type = "beklit"
    elif "matoviy" in file_name:
        order_type = "matoviy_orakal"
    elif "orakal" in file_name:
        order_type = "orakal"
    elif "setka" in file_name:
        order_type = "setka"

    if not order_type:
        await update.message.reply_text("❌ Buyurtma turini aniqlab bo‘lmadi. Fayl nomini tekshiring.")
        return

    # --- Hisoblash ---
    area = 0
    if order_type in ["banner", "qora_banner", "beklit"]:
        if size_match:
            en = int(size_match.group(1))
            boy = int(size_match.group(2))
            area = en * boy * count
    elif order_type in ["orakal", "matoviy_orakal", "setka"]:
        if size_match:
            uzunlik = int(size_match.group(2))  # "1x3" → uzunlik = 3
            koef = 1.0
            if "1.07" in file_name:
                koef = 1.07
            elif "1.27" in file_name:
                koef = 1.27
            elif "1.52" in file_name:
                koef = 1.52
            area = uzunlik * koef * count

    if area == 0:
        await update.message.reply_text("❌ O‘lcham yoki ko‘paytirish soni noto‘g‘ri.")
        return

    price_per_m2 = data["prices"][order_type]
    total_price = int(area * price_per_m2)

    # Buyurtmani saqlash
    order = {
        "user_id": user_id,
        "type": order_type,
        "size": area,
        "count": count,
        "price": total_price,
        "date": str(datetime.date.today()),
        "file_name": file_name
    }
    data["orders"].append(order)
    save_data(data)

    # Foydalanuvchiga javob
    await update.message.reply_text(
        f"✅ Faylingiz qabul qilindi!\n\n"
        f"📂 Buyurtma turi: {order_type}\n"
        f"📏 Kvadrat: {area:.2f} m²\n"
        f"💵 Narx: {total_price:,} so‘m\n",
        parse_mode="Markdown"
    )
