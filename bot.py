import os
import re
from datetime import datetime
from flask import Flask, request

import telebot
from telebot import types

# ================== SOZLAMALAR ==================
TOKEN = "7518059950:AAHk86-0Qv9jljSh79VB8WRB3sw8BZZHvBg"
ADMIN_ID = 6988170724
WEBHOOK_HOST = "https://telegram-bott-ejvk.onrender.com"
WEBHOOK_PATH = "/" + TOKEN
WEBHOOK_URL = WEBHOOK_HOST + WEBHOOK_PATH

# Narxlar (standart)
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

# ===== In-memory storage (demo uchun) =====
admins = {ADMIN_ID}
users = {}             # user_id -> {phone, tg_name, username, display_name}
display_names = {}     # user_id -> admin ko'radigan nom (admin o'zgartiradi)
orders = []            # list of dict
debts = {}             # user_id -> qarz summasi
prices = DEFAULT_PRICES.copy()            # global narxlar
user_price_overrides = {}                 # user_id -> {type: price}

# Sessiyalar: foydalanuvchi holati
user_state = {}        # user_id -> {"section": None|banner|..., "sub": None|1.07|1.27|1.52|kichik, "await": None|narx|rename|debt|wage_dates}
admin_state = {}       # admin_id -> {"action": ..., ...}


# ======== YORDAMCHI FUNKSIYALAR ========

def is_image_filename(name: str) -> bool:
    n = name.lower()
    return n.endswith(ALLOWED_EXT)

def extract_dims_and_qty(filename: str):
    """
    Fayl nomidan eni/bo'yi yoki uzunlik (sm) va sonni topishga harakat qiladi.
    Qo'llab-quvvatlaydi: '150x200', '150 X 200', '150*200', '150-200' (sm deb qabul qilinadi)
    Son: '4ta', '4 dona', '4x', '4', '4ta.', '4-dona' va hok.
    """
    name = filename.lower()
    # quantity
    qty = 1
    m_qty = re.search(r'(\d+)\s*(ta|dona|x)?\b', name)
    if m_qty:
        try:
            qty = int(m_qty.group(1))
        except:
            qty = 1

    # Try width x height
    m_wh = re.search(r'(\d+(?:\.\d+)?)\s*[,x\-\*]\s*(\d+(?:\.\d+)?)', name)
    width = height = None
    if m_wh:
        width = float(m_wh.group(1))
        height = float(m_wh.group(2))

    # Try single length (for orakal/setka koef)
    m_len = re.search(r'(\d+(?:\.\d+)?)\s*(sm|cm|)', name)
    length = None
    if m_len:
        try:
            length = float(m_len.group(1))
        except:
            length = None

    return width, height, length, qty


def get_effective_price(user_id: int, otype: str) -> int:
    """Mijozga xos narx bo'lsa, o'shani; bo'lmasa global narx."""
    if user_id in user_price_overrides and otype in user_price_overrides[user_id]:
        return user_price_overrides[user_id][otype]
    return prices.get(otype, 0)


def add_order(user_id: int, otype: str, area_m2: float, price_sum: int):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    orders.append({
        "user_id": user_id,
        "type": otype,
        "area": round(area_m2, 4),
        "price": int(price_sum),
        "date": now
    })
    debts[user_id] = debts.get(user_id, 0) + int(price_sum)


def fmt_user_name(uid: int) -> str:
    base = users.get(uid, {})
    shown = display_names.get(uid) or base.get("tg_name") or f"user_{uid}"
    return shown


def ensure_user_exists(msg):
    uid = msg.from_user.id
    if uid not in users:
        users[uid] = {
            "phone": None,
            "tg_name": msg.from_user.first_name or "",
            "username": msg.from_user.username or "",
            "display_name": None
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
    # 1.07 / 1.27 / 1.52 / Kichik
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("1.07", callback_data=f"s:{section_key}:1.07"),
        types.InlineKeyboardButton("1.27", callback_data=f"s:{section_key}:1.27"),
        types.InlineKeyboardButton("1.52", callback_data=f"s:{section_key}:1.52"),
        types.InlineKeyboardButton("Kichik", callback_data=f"s:{section_key}:kichik"),
    )
    bot.send_message(chat_id, "Turini tanlang:", reply_markup=kb)


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


def try_delete_message(chat_id: int, message_id: int):
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass


# ================= HANDLERS =================

@bot.message_handler(commands=['start'])
def on_start(msg):
    uid = ensure_user_exists(msg)
    # Eslatma va ro'yxatdan o'tish
    note = (
        "📌 <b>Eslatma</b>\n\n"
        "Yuborilayotgan fayl <b>TIFF</b> yoki <b>JPG</b> bo‘lishi va fayl nomida "
        "<b>o‘lchami</b> hamda <b>soni</b> yozilgan bo‘lishi shart. Aks holda faylingiz qabul qilinmaydi!\n\n"
        "👉 Agar nomida o‘lcham bo‘lmasa — fayl piksellari sm ga aylantirilmaydi (standart yo‘q), "
        "shuning uchun nomida aniq o‘lcham (masalan, <i>150x200</i>) va son (masalan, <i>4ta</i>) yozing."
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

    # Menu state reset
    user_state[uid] = {"section": None, "sub": None, "await": None}

    if cmd == "buyurtma":
        show_order_menu(uid)
    elif cmd == "hisobot":
        bot.send_message(uid, format_report_for_user(uid))
    elif cmd == "aloqa":
        bot.send_message(uid, "✍️ Xabaringizni yozing. (Faqat Aloqa bo‘limida matn qabul qilinadi)")
        # Aloqa rejimini bildiruvchi flag shart emas – biz text handlerda tekshiramiz
    elif cmd == "admin":
        if uid not in admins:
            bot.answer_callback_query(call.id, "Faqat adminlar uchun.")
            return
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💵 Narxlarni ko‘rish/o‘zgartirish", callback_data="a:prices"))
        kb.add(types.InlineKeyboardButton("👤 Mijoz ismini o‘zgartirish", callback_data="a:rename"))
        kb.add(types.InlineKeyboardButton("💳 Qarzni tuzatish (+/−)", callback_data="a:debt"))
        kb.add(types.InlineKeyboardButton("🧾 Ish haqi (kun oralig‘i)", callback_data="a:wage"))
        bot.send_message(uid, "⚙️ Admin panel:", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("o:"))
def on_order_section(call):
    uid = call.message.chat.id
    section = call.data.split(":")[1]  # banner, qora_banner, ...
    # set section
    user_state[uid] = {"section": section, "sub": None, "await": None}

    # roll materiallarda sub menyu
    if section in ("orakal", "matoviy_orakal", "setka"):
        show_sub_menu_for_roll(uid, section)
    else:
        bot.send_message(uid, f"📤 <b>{section.replace('_',' ').title()}</b> uchun fayllarni yuboring.\n"
                              f"Fayl nomida o‘lcham va son bo‘lsin (masalan: <code>150x200 4ta</code>).")


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("s:"))
def on_order_sub(call):
    uid = call.message.chat.id
    _, section, sub = call.data.split(":")  # s:orakal:1.27
    user_state[uid] = {"section": section, "sub": sub, "await": None}
    if sub == "kichik":
        bot.send_message(uid, f"📤 <b>{section.title()}</b> → <b>Kichik</b> uchun fayllarni yuboring.\n"
                              f"O‘lcham: <code>eni x bo‘yi</code> va son bo‘lsin (masalan: <code>100x80 3ta</code>).")
    else:
        bot.send_message(uid, f"📤 <b>{section.title()}</b> → <b>{sub}</b> uchun fayllarni yuboring.\n"
                              f"O‘lcham: <code>uzunlik</code> va son (masalan: <code>300 4ta</code>).")


@bot.message_handler(content_types=['document', 'photo'])
def on_file(msg):
    uid = ensure_user_exists(msg)
    st = user_state.get(uid, {"section": None, "sub": None, "await": None})
    section = st.get("section")
    sub = st.get("sub")

    # Sektsiya tanlanmagan bo‘lsa
    if not section:
        bot.reply_to(msg, "Avval buyurtma bo‘limini tanlang: /start → 🛒 Buyurtma")
        return

    # Fayl nomi + kengaytma
    if msg.content_type == 'document':
        file_name = msg.document.file_name or "file"
        if not is_image_filename(file_name):
            bot.reply_to(msg, "❌ Faqat JPG/JPEG yoki TIF/TIFF qabul qilinadi.")
            return
    else:
        # photo – Telegram nom bermaydi, lekin ruxsat beramiz
        file_name = "photo.jpg"

    # O'lcham va sonni ajratish
    width, height, length, qty = extract_dims_and_qty(file_name)

    # Hisoblash (sm asosida → m²)
    try:
        area_m2 = 0.0
        if section in ("banner", "qora_banner", "beklit"):
            # eni x bo'yi x qty
            if (width is None) or (height is None):
                bot.reply_to(msg, "❌ Fayl nomida <b>eni x bo‘yi</b> (sm) ko‘rsating, masalan: 150x200 4ta")
                return
            area_m2 = (float(width) / 100.0) * (float(height) / 100.0) * max(1, qty)
        else:
            # roll materiallar
            if sub == "kichik":
                if (width is None) or (height is None):
                    bot.reply_to(msg, "❌ Fayl nomida <b>eni x bo‘yi</b> (sm) ko‘rsating, masalan: 100x80 3ta")
                    return
                area_m2 = (float(width) / 100.0) * (float(height) / 100.0) * max(1, qty)
            else:
                if length is None:
                    bot.reply_to(msg, "❌ Fayl nomida <b>uzunlik</b> (sm) ko‘rsating, masalan: 300 2ta")
                    return
                coef = 1.0
                if sub in ("1.07", "1.27", "1.52"):
                    coef = float(sub)
                area_m2 = (float(length) / 100.0) * coef * max(1, qty)

        unit_price = get_effective_price(uid, section)
        total_price = round(area_m2 * unit_price)

        add_order(uid, section + (f"({sub})" if section in ("orakal", "matoviy_orakal", "setka") else ""), area_m2, total_price)

        bot.reply_to(msg,
                     f"✅ <b>Qabul qilindi</b>\n"
                     f"• Bo‘lim: <b>{section.replace('_',' ').title()}{' — ' + sub if sub else ''}</b>\n"
                     f"• Maydon: <b>{area_m2:.2f} m²</b>\n"
                     f"• Narx: <b>{total_price} so‘m</b>")

    except Exception as e:
        bot.reply_to(msg, f"❌ Hisoblashda xatolik: {e}")


@bot.message_handler(content_types=['text'])
def on_text(msg):
    uid = ensure_user_exists(msg)
    st = user_state.get(uid, {"section": None, "sub": None, "await": None})
    await_mode = st.get("await")

    # Adminning muloqotli amallari
    if uid in admins and await_mode:
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

        if await_mode == "prices_set_value":
            st_admin = admin_state.get(uid, {})
            key = st_admin.get("key")
            try:
                val = int(msg.text.strip())
                prices[key] = val
                bot.reply_to(msg, f"✅ {key.replace('_',' ').title()} narxi yangilandi: {val} so‘m")
            except:
                bot.reply_to(msg, "Butun son kiriting, masalan: 55000")
            user_state[uid]["await"] = None
            admin_state.pop(uid, None)
            return

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

        if await_mode == "wage_dates":
            # format: YYYY-MM-DD YYYY-MM-DD
            try:
                a, b = msg.text.strip().split()
                d1 = datetime.strptime(a, "%Y-%m-%d")
                d2 = datetime.strptime(b, "%Y-%m-%d")
                if d2 < d1:
                    d1, d2 = d2, d1
                # filter orders in range [d1, d2]
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

    # Aloqa bo'lmasa — matnni o'chiramiz (chat bo'limidayozish taqiqlanadi)
    # Aloqa rejimini maxsus flag bilan emas, menyu tanlovi bilan nazorat qilamiz:
    # Foydalanuvchi 'Aloqa'ni bosganidan keyin hamma matn adminlarga boradi,
    # lekin bu soddalashtirish uchun: bu yerda "aloqa" so'zini shart qilmaymiz,
    # aksincha matn bo'lsa — adminlarga yo'naltiramiz; boshqa bo'limda esa o'chiramiz.
    st = user_state.get(uid, {"section": None, "sub": None, "await": None})
    if st.get("section") is None and st.get("await") is None:
        # Boshqa bo'limlar kontekstida matnni o'chirish
        for aid in admins:
            if aid != uid:
                bot.send_message(aid, f"📩 {fmt_user_name(uid)}: {msg.text}")
        # Matnni foydalanuvchi chatidan o'chirish
        try_delete_message(uid, msg.message_id)
    else:
        # Agar hozir bo'lim tanlangan bo'lsa va foydalanuvchi matn yozsa — o'chiramiz
        try_delete_message(uid, msg.message_id)


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("a:"))
def on_admin(call):
    uid = call.message.chat.id
    if uid not in admins:
        bot.answer_callback_query(call.id, "Faqat adminlar uchun.")
        return

    cmd = call.data.split(":", 1)[1]
    # Reset
    user_state[uid] = {"section": None, "sub": None, "await": None}
    admin_state.pop(uid, None)

    if cmd == "prices":
        # Ko'rsatish va o'zgartirish jarayonini yoqish
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


# ================== WEBHOOK ROUTES ==================

@app.route(WEBHOOK_PATH, methods=['POST'])
def telegram_webhook():
    json_str = request.stream.read().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200


@app.route("/", methods=['GET'])
def index():
    # Webhook ni qayta o'rnatish
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    return "Bot webhook set OK", 200


# ================== MAIN ==================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Flask app run (Render Web Service)
    app.run(host="0.0.0.0", port=port)
