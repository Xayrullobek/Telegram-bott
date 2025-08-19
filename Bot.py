import logging from aiogram import Bot, Dispatcher, types from aiogram.utils import executor from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton from aiogram.contrib.fsm_storage.memory import MemoryStorage import re

Token va Admin ID

BOT_TOKEN = "7518059950:AAHk86-0Qv9jljSh79VB8WRB3sw8BZZHvBg" ADMIN_ID = 6988170724

Logging

logging.basicConfig(level=logging.INFO)

Bot va Dispatcher

bot = Bot(token=BOT_TOKEN) storage = MemoryStorage() dp = Dispatcher(bot, storage=storage)

Narxlar (m² uchun)

PRICES = { "banner": 45000, "orakal": 55000, "setka": 55000, "beklit": 65000, "matoviy_orakal": 55000, "qora_banner": 55000 }

Foydalanuvchilar ma’lumotlari

users = {}

Start komandasi

@dp.message_handler(commands=["start"]) async def start_cmd(message: types.Message): text = ( "👋 Assalomu alaykum! Bu bot orqali buyurtmalarni berishingiz mumkin.\n\n" "📌 Eslatma:\n" "Fayllar faqat JPG yoki TIFF shaklida qabul qilinadi.\n" "Fayl nomida o‘lcham va soni ko‘rsatilishi shart. Aks holda faylingiz qabul qilinmaydi!" ) markup = InlineKeyboardMarkup().add( InlineKeyboardButton("📋 Ro‘yxatdan o‘tish", callback_data="register") ) await message.answer(text, reply_markup=markup)

Ro‘yxatdan o‘tish

@dp.callback_query_handler(lambda c: c.data == "register") async def register_user(callback_query: types.CallbackQuery): user = callback_query.from_user users[user.id] = { "id": user.id, "name": user.full_name, "username": user.username, "phone": None } # Asosiy menyu markup = InlineKeyboardMarkup(row_width=2) markup.add( InlineKeyboardButton("🛒 Buyurtma", callback_data="buyurtma"), InlineKeyboardButton("📊 Hisobot", callback_data="hisobot"), InlineKeyboardButton("📞 Aloqa", callback_data="aloqa") ) await bot.send_message(user.id, "✅ Ro‘yxatdan o‘tdingiz!", reply_markup=markup)

Asosiy menyu tugmalar

@dp.callback_query_handler(lambda c: c.data in ["buyurtma", "hisobot", "aloqa"]) async def main_menu(callback_query: types.CallbackQuery): cid = callback_query.data if cid == "buyurtma": markup = InlineKeyboardMarkup(row_width=2) markup.add( InlineKeyboardButton("📌 Banner", callback_data="banner"), InlineKeyboardButton("📌 Orakal", callback_data="orakal"), InlineKeyboardButton("📌 Setka", callback_data="setka"), InlineKeyboardButton("📌 Beklit", callback_data="beklit"), InlineKeyboardButton("📌 Matoviy Orakal", callback_data="matoviy_orakal"), InlineKeyboardButton("📌 Qora Banner", callback_data="qora_banner") ) await bot.send_message(callback_query.from_user.id, "Buyurtma turini tanlang:", reply_markup=markup) elif cid == "hisobot": await bot.send_message(callback_query.from_user.id, "📊 Sizning buyurtmalaringiz bo‘yicha hisobot hozircha yo‘q.") elif cid == "aloqa": await bot.send_message(callback_query.from_user.id, "📞 Admin bilan bog‘lanish: @your_admin_username")

Buyurtma bo‘limlari

@dp.callback_query_handler(lambda c: c.data in ["banner", "orakal", "setka", "beklit", "matoviy_orakal", "qora_banner"]) async def order_section(callback_query: types.CallbackQuery): section = callback_query.data await bot.send_message( callback_query.from_user.id, f"📤 {section.upper()} bo‘limi tanlandi. Fayllarni yuboring (bir nechta fayl tashlashingiz mumkin)." )

Fayl qabul qilish

@dp.message_handler(content_types=["document", "photo"]) async def handle_file(message: types.Message): user_id = message.from_user.id if user_id not in users: await message.answer("❌ Avval ro‘yxatdan o‘ting.") return

filename = message.document.file_name if message.document else ""
match = re.search(r"(\d+)x(\d+)(?:\s*(\d+)ta)?", filename)
if not match:
    await message.answer("❌ Fayl nomida o‘lcham yoki soni ko‘rsatilmagan.")
    return

eni = int(match.group(1)) / 100  # santimetr → metr
boyi = int(match.group(2)) / 100
soni = int(match.group(3)) if match.group(3) else 1

# Kvadrat metr
kvadrat = eni * boyi * soni

# Bo‘limni aniqlash
section = "banner"
for sec in PRICES.keys():
    if sec in filename.lower():
        section = sec
        break

summa = kvadrat * PRICES[section]

await message.answer(
    f"✅ Fayl qabul qilindi!\n"
    f"📂 Nomi: {filename}\n"
    f"📐 Hajmi: {eni:.2f}m x {boyi:.2f}m x {soni} dona = {kvadrat:.2f} m²\n"
    f"💰 Narx: {summa:,.0f} so‘m"
)

if name == "main": executor.start_polling(dp, skip_updates=True)

