import os
import re
from datetime import datetime
from collections import defaultdict
from io import BytesIO

from flask import Flask, request
import telebot
from telebot import types

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

# ================== SOZLAMALAR ==================
TOKEN = "7518059950:AAHk86-0Qv9jljSh79VB8WRB3sw8BZZHvBg"
ADMIN_ID = 6988170724  # sizning admin ID
WEBHOOK_HOST = "https://telegram-bott-ejvk.onrender.com"
WEBHOOK_PATH = "/" + TOKEN
WEBHOOK_URL  = WEBHOOK_HOST + WEBHOOK_PATH

# Standart narxlar (so'm / m²)
DEFAULT_PRICES = {
    "banner": 45000,
    "qora_banner": 55000,
    "beklit": 65000,
    "orakal": 55000,
    "matoviy_orakal": 55000,
    "setka": 55000,
}

# Ish haqi stavkasi
WAGE_RATE = 1500  # so'm per m²

# Ruxsat etilgan rasm turlari
ALLOWED_EXT = (".jpg", ".jpeg", ".tif", ".tiff")

# =================================================

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ===== In-memory storage =====
admins = {ADMIN_ID}
users = {}             # user_id -> {phone, tg_name, username}
display_names = {}     # user_id -> admin ko'radigan nom
orders = []            # [ {user_id,type,area,price,date,detail} ]
debts = {}             # user_id -> qarz
prices = DEFAULT_PRICES.copy()            # global narxlar
user_price_overrides = {}                 # user_id -> {type: price}

# Foydalanuvchi sessiyasi: har bo‘lim bo‘yicha "pechatga berish"gacha to‘planadigan fayllar
# pending[user_id][(section, sub)] = [ {filename, type, width_cm, height_cm, length_cm, coef, qty, area_m2, price} , ... ]
pending = defaultdict(lambda: defaultdict(list))

# Sessiya holatlari
user_state = {}  # user_id -> {"section":..., "sub":..., "await":...}
admin_state = {} # admin_id -> {"action":..., ...}


# ================= Yordamchi ================

def is_image_filename(name: str) -> bool:
    n = (name or "").lower()
    return n.endswith(ALLOWED_EXT)

def extract_qty(text: str) -> int:
    # '4ta', '4 dona', '4x', '4' va hok.
    m = re.search(r'(\d+)\s*(ta|dona|x)?\b', text.lower())
    return int(m.group(1)) if m else 1

def extract_width_height(text: str):
    # '150x200', '150 X 200', '150*200', '150-200', '150 , 200'
    m = re.search(r'(\d+(?:\.\d+)?)\s*[,x\-\*]\s*(\d+(?:\.\d+)?)', text.lower())
    if not m:
        return None, None
    return float(m.group(1)), float(m.group(2))

def extract_length(text: str):
    # '300' (sm) – birinchi raqamni olamiz, lekin agar u eni×bo‘yi ichida bo‘lsa, baribir alohida ham topiladi
    # Orakal/setka "koeff" rejimida E N I kerak emas; uzunlik bo‘lsa kifoya
    m = re.search(r'\b(\d+(?:\.\d+)?)\b', text.lower())
    return float(m.group(1)) if m else None

def get_effective_price(user_id: int, otype: str) -> int:
    if user_id in user_price_overrides and otype in user_price_overrides[user_id]:
        return user_price_overrides[user_id][otype]
    return prices.get(otype, 0)

def fmt_user_name(uid: int) -> str:
    base = users.get(uid, {})
    return display_names.get(uid) or base.get("tg_name") or f"user_{uid}"

def ensure_user_exists(msg):
    uid = msg.from_user.id
    if uid not in users:
        users[uid] = {
            "phone": None,
            "tg_name": msg.from_user.first_name or "",
            "username": msg.from_user.username or ""
        }
    return uid

def show_main_menu(chat_id: int):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🛒 Buyurtma", callback_data="m:buyurtma"))
    kb.add(types.InlineKeyboardButton("📊 Hisobot", callback_data="m:hisobot"))
    kb.add(types.InlineKeyboardButton("📩 Aloqa", callback_data="m:aloqa"))
    if chat_id in admins:
        kb.add(types.InlineKeyboardButton("⚙️ Admin Panel", callback_data="m:admin"))
    bot.send_message(chat_id, "🏠 Asosiy menyu:", reply_markup=kb)

def show_order_menu(chat_id: int):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📌 Banner", callback_data="o:banner"),
        types.InlineKeyboardButton("⬛ Qora Banner", callback_data="o:qora_banner"),
        types.InlineKeyboardButton("💡 Beklit", callback_data="o:beklit"),
        types.InlineKeyboardButton("🟦 Orakal", callback_data="o:orakal"),
        types.InlineKeyboardButton("🟩 Matoviy Orakal", callback_data="o:matoviy_orakal"),
        types.InlineKeyboardButton("🟥 Setka", callback_data="o:setka"),
    )
    bot.send_message(chat_id, "🛒 Buyurtma bo‘limini tanlang:", reply_markup=kb)

def show_sub_menu_for_roll(chat_id: int, section_key: str):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("1.07", callback_data=f"s:{section_key}:1.07"),
        types.InlineKeyboardButton("1.27", callback_data=f"s:{section_key}:1.27"),
        types.InlineKeyboardButton("1.52", callback_data=f"s:{section_key}:1.52"),
        types.InlineKeyboardButton("Kichik", callback_data=f"s:{section_key}:kichik"),
    )
    bot.send_message(chat_id, "Turini tanlang:", reply_markup=kb)

def show_print_bar(chat_id: int, section: str, sub: str | None):
    # Buyurtma davomida pastda ko‘rinib turadigan pechat tugmasi
    label = f"{section.replace('_',' ').title()}" + (f" — {sub}" if sub else "")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🖨 Pechatga berish", callback_data=f"p:{section}:{sub or ''}"))
    bot.send_message(chat_id, f"📤 <b>{label}</b> uchun fayllarni tashlang.\n\n"
                              f"• JPG/JPEG yoki TIF/TIFF\n"
                              f"• Fayl nomida o‘lcham va son bo‘lsin (masalan: <code>150x200 3ta</code> yoki <code>300 4ta</code>)\n"
                              f"• Orakal/Matoviy/Setka (<b>1.07 | 1.27 | 1.52</b>) rejimida <u>faqat uzunlik</u> hisobga olinadi (eni e’tiborga olinmaydi).",
                     reply_markup=kb)

def build_excel(rows: list, title: str) -> BytesIO:
    """
    rows: [ { 'type','filename','width_cm','height_cm','length_cm','coef','qty','area_m2','price' }, ... ]
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Hisobot"

    # Sarlavha
    ws.cell(row=1, column=1, value=title)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=9)

    headers = ["Turi", "Fayl nomi", "Eni (sm)", "Bo‘yi (sm)", "Uzunlik (sm)", "Koeff.", "Soni", "Maydon (m²)", "Narx (so‘m)"]
    for j, h in enumerate(headers, start=1):
        ws.cell(row=2, column=j, value=h)

    r = 3
    total_area = 0.0
    total_price = 0

    for it in rows:
        ws.cell(row=r, column=1, value=it.get("type",""))
        ws.cell(row=r, column=2, value=it.get("filename",""))
        ws.cell(row=r, column=3, value=it.get("width_cm"))
        ws.cell(row=r, column=4, value=it.get("height_cm"))
        ws.cell(row=r, column=5, value=it.get("length_cm"))
        ws.cell(row=r, column=6, value=it.get("coef"))
        ws.cell(row=r, column=7, value=it.get("qty"))
        ws.cell(row=r, column=8, value=round(it.get("area_m2",0), 4))
        ws.cell(row=r, column=9, value=int(it.get("price",0)))
        total_area += float(it.get("area_m2",0))
        total_price += int(it.get("price",0))
        r += 1

    ws.cell(row=r+1, column=7, value="Jami:")
    ws.cell(row=r+1, column=8, value=round(total_area, 4))
    ws.cell(row=r+1, column=9, value=total_price)

    # Ustun kengliklari
    widths = [15, 30, 10, 10, 12, 8, 8, 12, 14]
    for idx, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = w

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream

def flush_pending_to_orders_and_debt(user_id: int, rows: list):
    # pendingdagi har bir elementni umumiy “orders” ga yozib qo‘yamiz va qarzga qo‘shamiz
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for it in rows:
        orders.append({
            "user_id": user_id,
            "type": it["type"],
            "area": round(it["area_m2"], 4),
            "price": int(it["price"]),
            "date": now,
            "detail": {
                "filename": it["filename"],
                "width_cm": it["width_cm"],
                "height_cm": it["height_cm"],
                "length_cm": it["length_cm"],
                "coef": it["coef"],
                "qty": it["qty"]
            }
        })
        debts[user_id] = debts.get(user_id, 0) + int(it["price"])

def format_report_for_user(uid: int):
    rows = [o for o in orders if o["user_id"] == uid]
    if not rows:
        return "Sizda hozircha buyurtmalar yo‘q."
    text = ["📊 Buyurtmalar tarixi:"]
    total_area = 0.0
    total_price = 0
    for o in rows:
        text.append(f"• {o['date']} | {o['type']} | {o['area']} m² | {o['price']} so‘m")
        total_area += o["area"]
        total_price += o["price"]
    debt = debts.get(uid, 0)
    text.append(f"\nJami: {round(total_area, 2)} m² | {total_price} so‘m")
    text.append(f"Qarz: {debt} so‘m")
    return "\n".join(text)


# ================= HANDLERS =================

@bot.message_handler(commands=['start'])
def on_start(msg):
    uid = ensure_user_exists(msg)
    # Eslatma
    note = (
        "📌 <b>Eslatma</b>\n\n"
        "Yuborilayotgan fayl <b>TIFF</b> yoki <b>JPG</b> bo‘lishi va fayl nomida "
        "<b>o‘lchami</b> hamda <b>soni</b> yozilgan bo‘lishi shart. Aks holda faylingiz qabul qilinmaydi!\n\n"
        "• Banner/Qora Banner/Beklit: <code>eni x bo‘yi</code> (sm) va son (masalan: <code>150x200 3ta</code>)\n"
        "• Orakal/Matoviy/Setka (1.07 | 1.27 | 1.52): faqat <b>uzunlik (sm)</b> va son (masalan: <code>300 4ta</code>)\n"
        "• <i>Kichik</i> ichki bo‘limida — <code>eni x bo‘yi</code> (banner kabi)\n"
    )
    bot.send_message(uid, note)

    if not users[uid]["phone"]:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(types.KeyboardButton("📱 Ro‘yxatdan o‘tish", request_contact=True))
        bot.send_message(uid, "Ro‘yxatdan o‘tish uchun telefon raqamingizni yuboring 👇", reply_markup=kb)
        return

    show_main_menu(uid)

@bot.message_handler(content_types=['contact'])
def on_contact(msg):
    uid = ensure_user_exists(msg)
    if msg.contact and (msg.contact.user_id == uid or True):
        users[uid]["phone"] = msg.contact.phone_number
        users[uid]["tg_name"] = msg.from_user.first_name or users[uid]["tg_name"]
        users[uid]["username"] = msg.from_user.username or users[uid]["username"]
        bot.send_message(uid, "✅ Ro‘yxatdan o‘tdingiz!", reply_markup=types.ReplyKeyboardRemove())
        show_main_menu(uid)
    else:
        bot.send_message(uid, "Noto‘g‘ri kontakt yuborildi.")

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("m:"))
def on_main_menu(call):
    uid = call.message.chat.id
    cmd = call.data.split(":", 1)[1]
    user_state[uid] = {"section": None, "sub": None, "await": None}

    if cmd == "buyurtma":
        show_order_menu(uid)
    elif cmd == "hisobot":
        # Matn ko‘rinishida umumiy
        txt = format_report_for_user(uid)
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("📥 Excelga chiqarish (hammasi)", callback_data="h:excel_all"))
        bot.send_message(uid, txt, reply_markup=kb)
    elif cmd == "aloqa":
        bot.send_message(uid, "✍️ Xabaringizni yozing. (Faqat Aloqa bo‘limida matn qabul qilinadi)")
    elif cmd == "admin":
        if uid not in admins:
            bot.answer_callback_query(call.id, "Faqat adminlar uchun.")
            return
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💵 Narxlarni ko‘rish/o‘zgartirish", callback_data="a:prices"))
        kb.add(types.InlineKeyboardButton("👤 Mijoz ismini o‘zgartirish", callback_data="a:rename"))
        kb.add(types.InlineKeyboardButton("💳 Qarzni tuzatish (+/−)", callback_data="a:debt"))
        kb.add(types.InlineKeyboardButton("🧾 Ish haqi (kun oralig‘i)", callback_data="a:wage"))
        kb.add(types.InlineKeyboardButton("📥 Hisobot (Excel, sana oralig‘i)", callback_data="a:excel"))
        kb.add(types.InlineKeyboardButton("➕ Admin qo‘shish", callback_data="a:add_admin"))
        bot.send_message(uid, "⚙️ Admin panel:", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("o:"))
def on_order_section(call):
    uid = call.message.chat.id
    section = call.data.split(":")[1]
    user_state[uid] = {"section": section, "sub": None, "await": None}

    if section in ("orakal", "matoviy_orakal", "setka"):
        show_sub_menu_for_roll(uid, section)
    else:
        # Banner/Qora/Beklit: to‘g‘ridan fayl, pastda pechat tugmasi
        show_print_bar(uid, section, None)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("s:"))
def on_order_sub(call):
    uid = call.message.chat.id
    _, section, sub = call.data.split(":")
    user_state[uid] = {"section": section, "sub": sub, "await": None}
    show_print_bar(uid, section, sub)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("p:"))
def on_print(call):
    uid = call.message.chat.id
    _, section, sub = call.data.split(":")
    key = (section, sub or None)
    rows = pending[uid].get(key, [])

    if not rows:
        bot.answer_callback_query(call.id, "Hali fayl yuborilmadi.")
        return

    # Excel yaratish
    title = f"{fmt_user_name(uid)} — {section.replace('_',' ').title()}" + (f" — {sub}" if sub else "")
    stream = build_excel(rows, title)

    # Excel yuborish
    file_name = f"buyurtma_{section}_{sub or 'oddiy'}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    bot.send_document(uid, (file_name, stream))

    # Umumiy "orders" ga o‘tkazish va qarzga qo‘shish
    flush_pending_to_orders_and_debt(uid, rows)

    # Sessiyani tozalash (faqat shu bo‘lim uchun)
    pending[uid][key].clear()

    bot.send_message(uid, "✅ Buyurtma qabul qilindi. (Excelda tafsilotlar yuborildi)")

@bot.message_handler(content_types=['document', 'photo'])
def on_file(msg):
    uid = ensure_user_exists(msg)
    st = user_state.get(uid, {"section": None, "sub": None, "await": None})
    section = st.get("section")
    sub = st.get("sub")

    if not section:
        bot.reply_to(msg, "Avval buyurtma bo‘limini tanlang: /start → 🛒 Buyurtma")
        return

    # Fayl nomi va kengaytma
    if msg.content_type == 'document':
        file_name = msg.document.file_name or "file"
        if not is_image_filename(file_name):
            bot.reply_to(msg, "❌ Faqat JPG/JPEG yoki TIF/TIFF qabul qilinadi.")
            return
    else:
        # photo
        file_name = "photo.jpg"  # nom bo‘lmasa ham sessiyaga qo‘shaveramiz

    # Parametrlarni nomdan olish
    qty = extract_qty(file_name)
    w_cm, h_cm = extract_width_height(file_name)
    length_cm = extract_length(file_name)

    # Hisoblash (sm asosida → m²)
    try:
        area_m2 = 0.0
        coef = None

        if section in ("banner", "qora_banner", "beklit"):
            # Eni × Bo‘yi × Soni (sm → m)
            if w_cm is None or h_cm is None:
                bot.reply_to(msg, "❌ Fayl nomida <b>eni x bo‘yi</b> (sm) ko‘rsating, masalan: 150x200 4ta")
                return
            area_m2 = (w_cm / 100.0) * (h_cm / 100.0) * max(1, qty)

        else:
            # Orakal / Matoviy Orakal / Setka
            if sub == "kichik":
                if w_cm is None or h_cm is None:
                    bot.reply_to(msg, "❌ Fayl nomida <b>eni x bo‘yi</b> (sm) ko‘rsating, masalan: 100x80 3ta")
                    return
                area_m2 = (w_cm / 100.0) * (h_cm / 100.0) * max(1, qty)
            else:
                # 1.07 / 1.27 / 1.52 – faqat uzunlik (eni e'tiborga olinmaydi)
                if sub not in ("1.07", "1.27", "1.52"):
                    bot.reply_to(msg, "❌ Avval ichki turini tanlang: 1.07 / 1.27 / 1.52 / Kichik")
                    return
                if length_cm is None:
                    bot.reply_to(msg, "❌ Fayl nomida <b>uzunlik</b> (sm) ko‘rsating, masalan: 300 2ta")
                    return
                coef = float(sub)
                area_m2 = (length_cm / 100.0) * coef * max(1, qty)

        unit_price = get_effective_price(uid, section)
        total_price = round(area_m2 * unit_price)

        # Sessiyaga qo‘shamiz (hech qanday javob yozmaymiz)
        key = (section, sub if section in ("orakal", "matoviy_orakal", "setka") else None)
        pending[uid][key].append({
            "type": section + (f"({sub})" if key[1] else ""),
            "filename": file_name,
            "width_cm": round(w_cm, 2) if w_cm is not None else None,
            "height_cm": round(h_cm, 2) if h_cm is not None else None,
            "length_cm": round(length_cm, 2) if (length_cm is not None and sub not in ("kichik", None)) else None,
            "coef": coef,
            "qty": max(1, qty),
            "area_m2": area_m2,
            "price": total_price
        })

        # xabar yo‘q — foydalanuvchi “🖨 Pechatga berish”ni bosganda Excelga olamiz

    except Exception as e:
        bot.reply_to(msg, f"❌ Hisoblashda xatolik: {e}")

@bot.message_handler(content_types=['text'])
def on_text(msg):
    uid = ensure_user_exists(msg)
    st = user_state.get(uid, {"section": None, "sub": None, "await": None})
    await_mode = st.get("await")

    # Adminning muloqotli amallari
    if uid in admins and await_mode:
        # Narxni o'zgartirish — 1-bosqich: turni so‘rash
        if await_mode == "prices_choose_type":
            key = msg.text.strip().lower().replace(" ", "_")
            if key not in prices:
                bot.reply_to(msg, "Noto‘g‘ri tur. Quyidagilardan birini yozing: " +
                             ", ".join(prices.keys()))
                return
            admin_state[uid] = {"action": "set_price", "key": key}
            user_state[uid]["await"] = "prices_set_value"
            bot.reply_to(msg, f"Yangi narxni yozing (so‘m):")
            return

        # Narxni o'zgartirish — 2-bosqich: qiymat
        if await_mode == "prices_set_value":
            st_admin = admin_state.get(uid, {})
            key = st_admin.get("key")
            try:
                val = int(msg.text.strip())
                prices[key] = val
                bot.reply_to(msg, f"✅ {key.replace('_',' ').title()} narxi yangilandi: {val} so‘m/m²")
            except:
                bot.reply_to(msg, "Butun son kiriting, masalan: 55000")
            user_state[uid]["await"] = None
            admin_state.pop(uid, None)
            return

        # Rename
        if await_mode == "rename_ask_userid":
            try:
                target = int(msg.text.strip())
                if target not in users:
                    bot.reply_to(msg, "Bunday foydalanuvchi topilmadi.")
                else:
                    admin_state[uid] = {"action": "rename", "target": target}
                    user_state[uid]["await"] = "rename_ask_name"
                    bot.reply_to(msg, f"Yangi nomni yozing (faqat admin ko‘radi):")
                return
            except:
                bot.reply_to(msg, "Foydalanuvchi ID sini yozing (butun son).")
                return

        if await_mode == "rename_ask_name":
            st_admin = admin_state.get(uid, {})
            target = st_admin.get("target")
            display_names[target] = msg.text.strip()
            bot.reply_to(msg, f"✅ O‘zgartirildi. Endi adminlar uchun nom: {display_names[target]}")
            user_state[uid]["await"] = None
            admin_state.pop(uid, None)
            return

        # Debt
        if await_mode == "debt_ask_userid":
            try:
                target = int(msg.text.strip())
                if target not in users:
                    bot.reply_to(msg, "Bunday foydalanuvchi topilmadi.")
                else:
                    admin_state[uid] = {"action": "debt", "target": target}
                    user_state[uid]["await"] = "debt_ask_delta"
                    curr = debts.get(target, 0)
                    bot.reply_to(msg, f"Joriy qarz: {curr} so‘m. "
                                      f"Qarzga qo‘shish (+) yoki kamaytirish (−) summasini yozing, masalan: -50000")
                return
            except:
                bot.reply_to(msg, "Foydalanuvchi ID sini yozing (butun son).")
                return

        if await_mode == "debt_ask_delta":
            st_admin = admin_state.get(uid, {})
            target = st_admin.get("target")
            try:
                delta = int(msg.text.strip())
                debts[target] = debts.get(target, 0) + delta
                bot.reply_to(msg, f"✅ Yangilandi. Yangi qarz: {debts[target]} so‘m")
            except:
                bot.reply_to(msg, "Butun son kiriting, masalan: -30000 yoki 45000")
            user_state[uid]["await"] = None
            admin_state.pop(uid, None)
            return

        # Wage dates
        if await_mode == "wage_dates":
            try:
                a, b = msg.text.strip().split()
                d1 = datetime.strptime(a, "%Y-%m-%d")
                d2 = datetime.strptime(b, "%Y-%m-%d")
                if d2 < d1:
                    d1, d2 = d2, d1
                total_area = 0.0
                for o in orders:
                    od = datetime.strptime(o["date"], "%Y-%m-%d %H:%M")
                    if d1 <= od <= d2:
                        total_area += o["area"]
                wage = round(total_area * WAGE_RATE)
                bot.reply_to(msg, f"🧾 Ish haqi:\n"
                                  f"• Oraliq: {a} — {b}\n"
                                  f"• Jami maydon: {total_area:.2f} m²\n"
                                  f"• Stavka: {WAGE_RATE} so‘m/m²\n"
                                  f"• Hisob: <b>{wage} so‘m</b>")
            except:
                bot.reply_to(msg, "Format: <code>YYYY-MM-DD YYYY-MM-DD</code>")
            user_state[uid]["await"] = None
            admin_state.pop(uid, None)
            return

        # Admin Excel date range
        if await_mode == "excel_dates":
            try:
                a, b = msg.text.strip().split()
                d1 = datetime.strptime(a, "%Y-%m-%d")
                d2 = datetime.strptime(b, "%Y-%m-%d")
                if d2 < d1:
                    d1, d2 = d2, d1
                # Filtrlash
                rows = []
                for o in orders:
                    od = datetime.strptime(o["date"], "%Y-%m-%d %H:%M")
                    if d1 <= od <= d2:
                        det = o.get("detail", {})
                        rows.append({
                            "type": o["type"],
                            "filename": det.get("filename"),
                            "width_cm": det.get("width_cm"),
                            "height_cm": det.get("height_cm"),
                            "length_cm": det.get("length_cm"),
                            "coef": det.get("coef"),
                            "qty": det.get("qty"),
                            "area_m2": o["area"],
                            "price": o["price"],
                        })
                if not rows:
                    bot.reply_to(msg, "Ushbu oraliqda buyurtmalar topilmadi.")
                else:
                    title = f"Admin hisobot: {a} — {b}"
                    stream = build_excel(rows, title)
                    fname = f"hisobot_{a}_{b}.xlsx"
                    bot.send_document(uid, (fname, stream))
            except:
                bot.reply_to(msg, "Format: <code>YYYY-MM-DD YYYY-MM-DD</code>")
            user_state[uid]["await"] = None
            admin_state.pop(uid, None)
            return

        # Add admin
        if await_mode == "add_admin":
            try:
                new_id = int(msg.text.strip())
                admins.add(new_id)
                bot.reply_to(msg, f"✅ Yangi admin qo‘shildi: {new_id}")
            except:
                bot.reply_to(msg, "Butun son kiriting (Telegram ID).")
            user_state[uid]["await"] = None
            admin_state.pop(uid, None)
            return

    # Aloqa bo'lmasa — matnni o‘chiramiz
    st = user_state.get(uid, {"section": None, "sub": None, "await": None})
    # Agar hozir bo'lim tanlangan bo'lsa va foydalanuvchi matn yozsa — o'chiramiz
    try:
        if st.get("section") is not None:
            bot.delete_message(uid, msg.message_id)
            return
    except:
        pass
    # Aks holda (Aloqa bo‘limi xabarlarini adminlarga forward qilishni soddalashtirish uchun),
    # bu yerda hech narsa qilmaymiz — foydalanuvchi "Aloqa" ni bosgach yozadi.

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("h:"))
def on_user_history_excel(call):
    uid = call.message.chat.id
    kind = call.data.split(":",1)[1]
    if kind == "excel_all":
        rows = []
        for o in orders:
            if o["user_id"] != uid:
                continue
            det = o.get("detail", {})
            rows.append({
                "type": o["type"],
                "filename": det.get("filename"),
                "width_cm": det.get("width_cm"),
                "height_cm": det.get("height_cm"),
                "length_cm": det.get("length_cm"),
                "coef": det.get("coef"),
                "qty": det.get("qty"),
                "area_m2": o["area"],
                "price": o["price"],
            })
        if not rows:
            bot.answer_callback_query(call.id, "Buyurtmalar topilmadi.")
            return
        title = f"{fmt_user_name(uid)} — Shaxsiy hisobot"
        stream = build_excel(rows, title)
        fname = f"shaxsiy_hisobot_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        bot.send_document(uid, (fname, stream))

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("a:"))
def on_admin(call):
    uid = call.message.chat.id
    if uid not in admins:
        bot.answer_callback_query(call.id, "Faqat adminlar uchun.")
        return

    cmd = call.data.split(":", 1)[1]
    user_state[uid] = {"section": None, "sub": None, "await": None}
    admin_state.pop(uid, None)

    if cmd == "prices":
        txt = ["💵 Hozirgi narxlar:"]
        for k, v in prices.items():
            txt.append(f"• {k.replace('_',' ').title()}: {v} so‘m/m²")
        txt.append("\nQaysi tur narxini o‘zgartirasiz? (nomini yozing)")
        bot.send_message(uid, "\n".join(txt))
        user_state[uid]["await"] = "prices_choose_type"
        return

    if cmd == "rename":
        bot.send_message(uid, "Qaysi foydalanuvchi ID sini o‘zgartirasiz? (butun son)")
        user_state[uid]["await"] = "rename_ask_userid"
        return

    if cmd == "debt":
        bot.send_message(uid, "Qaysi foydalanuvchi ID sini tanlaysiz? (butun son)")
        user_state[uid]["await"] = "debt_ask_userid"
        return

    if cmd == "wage":
        bot.send_message(uid, "Kun oraliqni kiriting: <code>YYYY-MM-DD YYYY-MM-DD</code>")
        user_state[uid]["await"] = "wage_dates"
        return

    if cmd == "excel":
        bot.send_message(uid, "Kun oraliqni kiriting: <code>YYYY-MM-DD YYYY-MM-DD</code>")
        user_state[uid]["await"] = "excel_dates"
        return

    if cmd == "add_admin":
        bot.send_message(uid, "Yangi adminning Telegram ID sini kiriting (butun son).")
        user_state[uid]["await"] = "add_admin"
        return


# ================== WEBHOOK ROUTES ==================

@app.route(WEBHOOK_PATH, methods=['POST'])
def telegram_webhook():
    json_str = request.stream.read().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

@app.route("/", methods=['GET'])
def index():
    # Webhook ni qayta o‘rnatish
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    return "Bot webhook set OK", 200


# ================== MAIN ==================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
