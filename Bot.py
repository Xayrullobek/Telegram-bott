import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# 🔑 TOKENINGIZNI shu yerga yozing
TOKEN = "7518059950:AAHk86-0Qv9jljSh79VB8WRB3sw8BZZHvBg"

# 📌 ADMIN ID
ADMIN_ID = 6988170724   # o‘zingizning telegram ID’ingizni qo‘ying

# Narxlar
PRICES = {
    "banner": 45000,
    "qora_banner": 55000,
    "beklit": 65000,
    "orakal": 55000,
    "matoviy_orakal": 55000,
    "setka": 55000
}

# Log sozlamalari
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# START komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📌 Eslatma:\n"
        "Yuborilayotgan fayl *tiff* yoki *jpg* shaklida bo‘lishi va "
        "fayl nomida o‘lchami hamda soni yozilgan bo‘lishi shart.\n\n"
        "⚠️ Aks holda faylingiz qabul qilinmaydi!"
    )
    keyboard = [[InlineKeyboardButton("📋 Ro‘yxatdan o‘tish", callback_data="register")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# Ro‘yxatdan o‘tish
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    # Bu yerda user ma’lumotlari bazaga saqlanishi mumkin (id, username, full_name)
    text = (
        f"✅ Ro‘yxatdan o‘tdingiz!\n\n"
        f"👤 Sizning ID: {user.id}\n"
        f"🔗 Username: @{user.username if user.username else 'yo‘q'}\n"
        f"📝 Ism: {user.full_name}"
    )

    # Mijoz uchun menyu
    keyboard = [
        [InlineKeyboardButton("🛒 Buyurtma berish", callback_data="menu_orders")],
        [InlineKeyboardButton("📊 Hisobotlar", callback_data="menu_reports")],
        [InlineKeyboardButton("☎️ Aloqa", callback_data="menu_contact")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# Menyularni ko‘rsatish
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "menu_orders":
        keyboard = [
            [InlineKeyboardButton("📦 Banner", callback_data="order_banner")],
            [InlineKeyboardButton("🖤 Qora Banner", callback_data="order_qora_banner")],
            [InlineKeyboardButton("🌌 Beklit", callback_data="order_beklit")],
            [InlineKeyboardButton("📐 Orakal", callback_data="order_orakal")],
            [InlineKeyboardButton("📏 Matoviy Orakal", callback_data="order_matoviy_orakal")],
            [InlineKeyboardButton("🎛 Setka", callback_data="order_setka")],
            [InlineKeyboardButton("⬅️ Orqaga", callback_data="back_main")]
        ]
        await query.edit_message_text("📦 Buyurtma bo‘limlari:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "menu_reports":
        await query.edit_message_text("📊 Sizning hisobotlaringiz (jadval ko‘rinishida bo‘lishi kerak).")

    elif query.data == "menu_contact":
        await query.edit_message_text("☎️ Adminlar bilan bog‘lanish: @admin_username")

    elif query.data == "back_main":
        keyboard = [
            [InlineKeyboardButton("🛒 Buyurtma berish", callback_data="menu_orders")],
            [InlineKeyboardButton("📊 Hisobotlar", callback_data="menu_reports")],
            [InlineKeyboardButton("☎️ Aloqa", callback_data="menu_contact")]
        ]
        await query.edit_message_text("🏠 Asosiy menyu", reply_markup=InlineKeyboardMarkup(keyboard))


# Fayl yuborilganda
async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document:
        return

    file_name = document.file_name
    user = update.message.from_user

    # Fayl qabul qilingani haqida adminlarga xabar
    await context.bot.send_message(
        ADMIN_ID,
        f"📥 Yangi fayl!\n"
        f"👤 {user.full_name}\n"
        f"📄 Fayl: {file_name}"
    )

    await update.message.reply_text("✅ Fayl qabul qilindi! Hisob-kitob tez orada chiqadi.")


# Bosh dastur
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(register, pattern="register"))
    app.add_handler(CallbackQueryHandler(menu_handler, pattern="menu_.*|back_main"))
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))

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
