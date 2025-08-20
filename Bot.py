import logging import re from aiogram import Bot, Dispatcher, executor, types from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

=============================

TOKEN VA ADMIN ID

=============================

API_TOKEN = "7518059950:AAHk86-0Qv9jljSh79VB8WRB3sw8BZZHvBg" ADMIN_ID = 6988170724

=============================

LOGGING

=============================

logging.basicConfig(level=logging.INFO)

=============================

BOT VA DISPATCHER

=============================

bot = Bot(token=API_TOKEN) dp = Dispatcher(bot)

=============================

NARHLAR

=============================

prices = { "banner": 45000, "qora_banner": 55000, "orakal": 55000, "mat_orakal": 55000, "setka": 55000, "beklit": 65000 }

Orakal koeffitsiyentlari

orakal_coeff = { "1.07": 1.07, "1.27": 1.27, "1.52": 1.52, "kichik": 1.0  # faqat uzunlik × eni (klassik formula emas) }

=============================

KLAVIATURA

=============================

main_menu = ReplyKeyboardMarkup(resize_keyboard=True) main_menu.add("📦 Buyurtma", "📊 Hisobot", "📞 Aloqa")

order_menu = ReplyKeyboardMarkup(resize_keyboard=True) order_menu.add("🖼 Banner", "⬛ Qora Banner") order_menu.add("🔵 Orakal", "✨ Matoviy Orakal") order_menu.add("🕸 Setka", "💡 Beklit") order_menu.add("⬅️ Orqaga")

orakal_menu = ReplyKeyboardMarkup(resize_keyboard=True) orakal_menu.add("1.07", "1.27", "1.52", "Kichik") orakal_menu.add("⬅️ Orqaga")

=============================

MALUMOTLARNI SAQLASH

=============================

user_orders = {}  # {user_id: [ { 'type':..., 'size':..., 'count':..., 'area':..., 'price':... } ] }

=============================

START

=============================

@dp.message_handler(commands=['start']) async def start_cmd(message: types.Message): await message.answer( "Salom! 👋\n\nEslatma:\nYuborilayotgan fayl jpg yoki tiff bo'lishi shart. Fayl nomida o'lcham (eni×uzunlik) va soni yozilishi kerak. Agar qoida bajarilmasa fayl qabul qilinmaydi!", parse_mode="Markdown", reply_markup=main_menu )

=============================

BUYURTMA MENYU

=============================

@dp.message_handler(lambda m: m.text == "📦 Buyurtma") async def order_handler(message: types.Message): await message.answer("Buyurtma turini tanlang:", reply_markup=order_menu)

@dp.message_handler(lambda m: m.text == "🔵 Orakal") async def orakal_handler(message: types.Message): await message.answer("Orakal bo'limini tanlang:", reply_markup=orakal_menu)

=============================

FAYL QABUL QILISH

=============================

@dp.message_handler(content_types=['document', 'photo']) async def file_handler(message: types.Message): user_id = message.from_user.id

# Fayl nomini olish
if message.document:
    filename = message.document.file_name
else:
    filename = message.caption or ""

# Regex: orakal 100x200 2ta
match = re.search(r"(\d+)x(\d+)(?:\s*(\d+)ta)?", filename)
if not match:
    await message.answer("❌ Fayl nomida o'lcham (eni×uzunlik) va soni yozilishi kerak!")
    return

width = int(match.group(1)) / 100   # santimetr → metr
length = int(match.group(2)) / 100  # santimetr → metr
count = int(match.group(3)) if match.group(3) else 1

# Hozircha turini filename’dan aniqlaymiz
file_type = "banner" if "banner" in filename.lower() else "orakal"

# Hisoblash
if file_type in ["banner", "qora_banner", "beklit"]:
    area = width * length * count
    price = area * prices[file_type]
else:  # orakal/matoviy/setka
    # default coefficient
    coeff = 1.27
    for key in orakal_coeff:
        if key in filename:
            coeff = orakal_coeff[key]
            break
    area = length * coeff * count
    price = area * prices[file_type]

# Saqlash
if user_id not in user_orders:
    user_orders[user_id] = []
user_orders[user_id].append({
    "type": file_type,
    "size": f"{width*100}x{length*100}",
    "count": count,
    "area": round(area, 2),
    "price": round(price, 2)
})

await message.answer(f"✅ Fayl qabul qilindi!\n📐 Maydon: {round(area,2)} m²\n💰 Narx: {round(price,2)} so'm")

=============================

HISOBOT

=============================

@dp.message_handler(lambda m: m.text == "📊 Hisobot") async def report_handler(message: types.Message): user_id = message.from_user.id if user_id not in user_orders or not user_orders[user_id]: await message.answer("Siz hali buyurtma bermagansiz!") return

text = "📊 Buyurtmalar tarixi:\n\n"
total = 0
for order in user_orders[user_id]:
    text += f"➡️ {order['type']} | {order['size']} | {order['count']} dona | {order['area']} m² | {order['price']} so'm\n"
    total += order['price']
text += f"\nJami: {round(total,2)} so'm"
await message.answer(text)

=============================

ADMIN PANEL

=============================

@dp.message_handler(commands=['admin']) async def admin_cmd(message: types.Message): if message.from_user.id != ADMIN_ID: return text = "🔑 Admin panel:\n/narh [tur] [yangi_narh] — narhni o'zgartirish\n/addadmin [id] — yangi admin qo'shish" await message.answer(text)

@dp.message_handler(commands=['narh']) async def change_price(message: types.Message): if message.from_user.id != ADMIN_ID: return args = message.text.split() if len(args) != 3: await message.answer("❌ Format: /narh banner 50000") return typ, val = args[1], int(args[2]) if typ in prices: prices[typ] = val await message.answer(f"✅ {typ} narhi {val} so'm qilib o'zgartirildi!") else: await message.answer("❌ Noto'g'ri tur!")

=============================

RUN

=============================

if name == 'main': executor.start_polling(dp, skip_updates=True)

