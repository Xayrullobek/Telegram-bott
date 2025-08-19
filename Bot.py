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

# 🔑 BOT TOKEN (siz bergan token shu yerda turibdi)
TOKEN = "7491021612:AAGmR1EmLfhV_LhmdEy3w1Xid7_yY9M7hC0"

# 📌 ADMIN ID (siz bergan ID shu yerda turibdi)
ADMIN_ID = 6258656774

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

    # Fayl haqida adminni xabardor qilish
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
