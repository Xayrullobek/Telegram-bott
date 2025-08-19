import logging
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InputFile
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

# 🔑 TOKEN va ADMIN ID
TOKEN = "7577643640:AAF7wvo9l6Cg4XCFjCKN8X_wL7cYqCe_0WI"
ADMIN_IDS = [6988170724]  # Sizning admin ID

# 📌 Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# --- GLOBAL DATA ---
users = {}  # user_id: {name, username, phone, orders: [], debt}
prices = {
    "banner": 45000,
    "qora_banner": 55000,
    "beklit": 65000,
    "orakal": 55000,
    "matoviy_orakal": 55000,
    "setka": 55000,
}
orders = []  # barcha buyurtmalar saqlanadi

# --- STATES ---
(
    MENU,
    REGISTER_PHONE,
    ORDER_CATEGORY,
    ORDER_SUBCATEGORY,
    WAIT_FILE,
    ADMIN_PANEL,
    ADMIN_EDIT_PRICE,
    ADMIN_DEBT,
    ADMIN_EDIT_USER,
    SALARY_RANGE,
) = range(10)


# --- HELPERS ---
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def parse_filename(filename: str):
    """
    Fayl nomidan eni, bo‘yi va sonini ajratib olish
    Masalan: "orakal 1x3 4ta"
    """
    import re

    numbers = re.findall(r"(\d+(?:\.\d+)?)", filename)
    count = 1
    if "ta" in filename:
        c = re.findall(r"(\d+)ta", filename)
        if c:
            count = int(c[0])
    if len(numbers) >= 2:
        x = float(numbers[0])
        y = float(numbers[1])
        return x, y, count
    elif len(numbers) == 1:
        return float(numbers[0]), 1.0, count
    return 1.0, 1.0, count


def calc_area(category, subcategory, filename):
    x, y, count = parse_filename(filename)
    if category in ["orakal", "matoviy_orakal", "setka"]:
        # Uzunlik * koeff * son
        if subcategory in ["1.07", "1.27", "1.52"]:
            coeff = float(subcategory)
            return y * coeff * count
        else:
            return x * y * count
    elif category in ["banner", "qora_banner", "beklit"]:
        return x * y * count
    return 0


def format_orders(user_id: int):
    text = "📊 Buyurtma hisobot:\n\n"
    user_orders = [o for o in orders if o["user_id"] == user_id]
    if not user_orders:
        return "❌ Buyurtma yo‘q"
    text += "Sana | Kategoriya | Kv.m | Narx\n"
    for o in user_orders:
        text += f"{o['date']} | {o['category']} | {o['area']:.2f} | {o['price']:,} so‘m\n"
    return text


# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in users:
        users[user_id] = {
            "name": update.effective_user.full_name,
            "username": update.effective_user.username,
            "phone": None,
            "orders": [],
            "debt": 0,
        }
    text = (
        "📌 Eslatma:\n\n"
        "Yuborilayotgan fayl TIFF yoki JPG shaklida bo‘lishi kerak.\n"
        "Fayl nomida o‘lcham va soni yozilgan bo‘lishi shart, aks holda qabul qilinmaydi!\n"
    )
    keyboard = [[KeyboardButton("📱 Ro‘yxatdan o‘tish", request_contact=True)]]
    await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return REGISTER_PHONE


async def register_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    phone = update.message.contact.phone_number
    users[user_id]["phone"] = phone
    await update.message.reply_text("✅ Ro‘yxatdan o‘tish tugadi!\n\nEndi buyurtma bera olasiz.", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Buyurtma", callback_data="order_menu")],
        [InlineKeyboardButton("📊 Hisobot", callback_data="report")],
        [InlineKeyboardButton("📞 Aloqa", callback_data="contact")],
    ]))
    return MENU


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "order_menu":
        keyboard = [
            [InlineKeyboardButton("📦 Banner", callback_data="banner")],
            [InlineKeyboardButton("⚫ Qora Banner", callback_data="qora_banner")],
            [InlineKeyboardButton("🖼️ Beklit", callback_data="beklit")],
            [InlineKeyboardButton("🟩 Orakal", callback_data="orakal")],
            [InlineKeyboardButton("🌫️ Matoviy Orakal", callback_data="matoviy_orakal")],
            [InlineKeyboardButton("🕸️ Setka", callback_data="setka")],
        ]
        await query.message.reply_text("🔽 Bo‘limni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
        return ORDER_CATEGORY
    elif data == "report":
        text = format_orders(query.from_user.id)
        await query.message.reply_text(text)
        return MENU
    elif data == "contact":
        await query.message.reply_text("📞 Admin bilan bog‘lanish: @your_admin_username")
        return MENU


async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data
    context.user_data["category"] = category
    if category in ["orakal", "matoviy_orakal", "setka"]:
        keyboard = [
            [InlineKeyboardButton("1.07", callback_data="1.07")],
            [InlineKeyboardButton("1.27", callback_data="1.27")],
            [InlineKeyboardButton("1.52", callback_data="1.52")],
            [InlineKeyboardButton("Kichik", callback_data="kichik")],
        ]
        await query.message.reply_text("🔽 Ichki bo‘limni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
        return ORDER_SUBCATEGORY
    else:
        await query.message.reply_text("📂 Faylni yuboring:")
        return WAIT_FILE


async def subcategory_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["subcategory"] = query.data
    await query.message.reply_text("📂 Faylni yuboring:")
    return WAIT_FILE


async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not update.message.document and not update.message.photo:
        await update.message.reply_text("❌ Faqat fayl yuboring (jpg/tiff).")
        return WAIT_FILE
    filename = ""
    if update.message.document:
        filename = update.message.document.file_name
    elif update.message.photo:
        filename = "photo.jpg"
    category = context.user_data.get("category")
    subcategory = context.user_data.get("subcategory", "kichik")
    area = calc_area(category, subcategory, filename)
    price = area * prices.get(category, 0)
    order = {
        "user_id": user_id,
        "category": category,
        "subcategory": subcategory,
        "filename": filename,
        "area": area,
        "price": price,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    orders.append(order)
    users[user_id]["orders"].append(order)
    await update.message.reply_text(
        f"✅ Buyurtma qabul qilindi!\n\n"
        f"Kategoriya: {category}\n"
        f"Kvadrat: {area:.2f}\n"
        f"Narx: {price:,.0f} so‘m"
    )
    return MENU


# --- MAIN ---
def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REGISTER_PHONE: [MessageHandler(filters.CONTACT, register_phone)],
            MENU: [CallbackQueryHandler(menu_handler)],
            ORDER_CATEGORY: [CallbackQueryHandler(category_handler)],
            ORDER_SUBCATEGORY: [CallbackQueryHandler(subcategory_handler)],
            WAIT_FILE: [MessageHandler(filters.Document.ALL | filters.PHOTO, file_handler)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conv)

    logging.info("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
