# Bot.py
# -*- coding: utf-8 -*-

import os
import re
import time
import csv
import sqlite3
import threading
from datetime import datetime
from io import BytesIO

from flask import Flask, request
from PIL import Image
import telebot
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove, InputMediaPhoto, InputMediaDocument
)

# =========================
# CONFIG
# =========================
TOKEN = "7518059950:AAHk86-0Qv9jljSh79VB8WRB3sw8BZZHvBg"
SUPER_ADMIN_ID = 6988170724  # sizning ID'ingiz

PORT = int(os.getenv("PORT", 8000))

# Narxlar (m² uchun standart)
DEFAULT_PRICES = {
    "banner": 45000,
    "qora_banner": 55000,
    "beklit": 65000,
    "orakal": 55000,
    "mat_orakal": 55000,
    "setka": 55000,
}

ISH_HAQI_K = 1500  # ish haqi koeff

# Qabul qilinadigan fayl turlari
ALLOWED_MIMES = ("image/jpeg", "image/tiff")
ALLOWED_EXTS = (".jpg", ".jpeg", ".tif", ".tiff")

# =========================
# TELEGRAM
# =========================
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")


# =========================
# DATABASE
# =========================
DB_PATH = "bot.db"

def db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    con = db()
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        phone TEXT,
        tg_name TEXT,
        username TEXT,
        real_name TEXT,
        registered_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS admins(
        user_id INTEGER PRIMARY KEY
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS prices(
        key TEXT PRIMARY KEY,
        value INTEGER
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS client_prices(
        user_id INTEGER,
        key TEXT,
        value INTEGER,
        PRIMARY KEY(user_id, key)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        category TEXT,
        subkey TEXT,
        file_name TEXT,
        count INTEGER,
        width_cm REAL,
        height_cm REAL,
        length_cm REAL,
        coef REAL,
        area_m2 REAL,
        unit_price INTEGER,
        total_price INTEGER,
        created_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS debts(
        user_id INTEGER PRIMARY KEY,
        amount INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS states(
        user_id INTEGER PRIMARY KEY,
        state TEXT,
        payload TEXT
    )""")
    # Insert default prices if not exist
    for k,v in DEFAULT_PRICES.items():
        cur.execute("INSERT OR IGNORE INTO prices(key,value) VALUES(?,?)",(k,v))
    # Ensure super admin
    cur.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)",(SUPER_ADMIN_ID,))
    con.commit()
    con.close()

init_db()

# =========================
# HELPERS
# =========================
def is_admin(uid:int)->bool:
    con=db();cur=con.cursor()
    cur.execute("SELECT 1 FROM admins WHERE user_id=?",(uid,))
    r=cur.fetchone()
    con.close()
    return r is not None

def get_price(uid:int, key:str)->int:
    con=db();cur=con.cursor()
    cur.execute("SELECT value FROM client_prices WHERE user_id=? AND key=?",(uid,key))
    r=cur.fetchone()
    if r: 
        con.close()
        return int(r[0])
    cur.execute("SELECT value FROM prices WHERE key=?",(key,))
    r=cur.fetchone()
    con.close()
    return int(r[0]) if r else 0

def set_state(uid:int, state:str, payload:str=""):
    con=db();cur=con.cursor()
    cur.execute("REPLACE INTO states(user_id,state,payload) VALUES(?,?,?)",(uid,state,payload))
    con.commit();con.close()

def get_state(uid:int):
    con=db();cur=con.cursor()
    cur.execute("SELECT state,payload FROM states WHERE user_id=?",(uid,))
    r=cur.fetchone()
    con.close()
    return (r[0], r[1]) if r else (None,"")

def clear_state(uid:int):
    con=db();cur=con.cursor()
    cur.execute("DELETE FROM states WHERE user_id=?",(uid,))
    con.commit();con.close()

FILENAME_RE = re.compile(
    r"(?P<a>\d+)\s*[xX]\s*(?P<b>\d+)|(?P<count>\d+)\s*(?:ta|xona|don[aou]?)",
    re.IGNORECASE
)

def parse_name_for_dims_and_count(name:str):
    """
    Qidiradi: '150x200 3ta' yoki '3ta 150x200' kabi.
    Santimetr deb qabul qilamiz. Son topilmasa 1.
    """
    name = name.replace(",", ".")
    width_cm = height_cm = length_cm = None
    count = 1

    # topish: eni x bo'yi
    m = re.search(r"(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)", name)
    if m:
        width_cm = float(m.group(1))
        height_cm = float(m.group(2))

    # topish: uzunlik
    if width_cm is None and height_cm is None:
        m2 = re.search(r"(\d+(?:\.\d+)?)\s*(?:sm|cm)?\s*(?:uzunlik|uzun|long)?", name, re.IGNORECASE)
        if m2:
            length_cm = float(m2.group(1))

    # count
    m3 = re.search(r"(\d+)\s*(?:ta|don[aou]?|xona)", name, re.IGNORECASE)
    if m3:
        count = int(m3.group(1))

    return width_cm, height_cm, length_cm, count

def ensure_user(msg):
    uid = msg.from_user.id
    con=db();cur=con.cursor()
    cur.execute("SELECT 1 FROM users WHERE user_id=?",(uid,))
    if not cur.fetchone():
        cur.execute("""INSERT INTO users(user_id, phone, tg_name, username, real_name, registered_at)
                       VALUES(?,?,?,?,?,?)""",
                    (uid, None, msg.from_user.full_name, msg.from_user.username or "",
                     msg.from_user.full_name, datetime.utcnow().isoformat()))
    con.commit();con.close()

def main_menu(uid:int):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🧾 Buyurtma","📊 Hisobot")
    kb.row("📞 Aloqa")
    if is_admin(uid):
        kb.row("🛠 Admin panel")
    return kb

def order_menu():
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("📈 Banner","order_banner"),
           InlineKeyboardButton("⬛ Qora banner","order_qbanner"))
    kb.row(InlineKeyboardButton("💡 Beklit","order_beklit"))
    kb.row(InlineKeyboardButton("🧩 Orakal","order_orakal"),
           InlineKeyboardButton("🧩 Matoviy orakal","order_matorakal"))
    kb.row(InlineKeyboardButton("🧵 Setka","order_setka"))
    return kb

def orakal_submenu(prefix:str):
    kb = InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("1.07","%s_1.07"%prefix),
           InlineKeyboardButton("1.27","%s_1.27"%prefix),
           InlineKeyboardButton("1.52","%s_1.52"%prefix))
    kb.row(InlineKeyboardButton("Kichik","%s_kichik"%prefix))
    kb.row(InlineKeyboardButton("⬅️ Orqaga","back_orders"))
    return kb

def eslatma_text():
    return (
        "<b>Eslatma</b>\n"
        "Yuboriladigan fayl <b>TIFF</b> yoki <b>JPG</b> bo‘lishi shart.\n"
        "Fayl <b>nomida</b> o‘lcham va soni yozilgan bo‘lsa, avtomatik hisoblaymiz."
        " Aks holda fayl yuborgach o‘lcham (sm) va sonni so‘raymiz.\n\n"
        "Orakal/Matoviy orakal/Setka bo‘limlarida <b>1.07 / 1.27 / 1.52</b> tanlanganda kvadrat: "
        "<i>uzunlik (sm) × koeffitsient × son / 100</i> bo‘yicha; "
        "<b>Kichik</b> bo‘limida esa <i>eni (sm) × bo‘yi (sm) × son / 10000</i> bo‘yicha hisoblanadi.\n"
    )

def send_register_prompt(chat_id):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📲 Raqamni ulashish", request_contact=True))
    bot.send_message(chat_id, eslatma_text(), reply_markup=kb)

# =========================
# START / REGISTER
# =========================
@bot.message_handler(commands=["start"])
def cmd_start(msg):
    ensure_user(msg)
    uid = msg.from_user.id

    # tekshiramiz — ro‘yxatdan o‘tganmi
    con=db();cur=con.cursor()
    cur.execute("SELECT phone FROM users WHERE user_id=?",(uid,))
    row=cur.fetchone();con.close()
    if not row or not row[0]:
        send_register_prompt(msg.chat.id)
        return

    bot.send_message(msg.chat.id, "Salom! Menyudan bo‘lim tanlang 👇", reply_markup=main_menu(uid))
    # pastga tezkor buyurtma tugmalari
    bot.send_message(msg.chat.id, "⚙️ Buyurtma bo‘limlari:", reply_markup=ReplyKeyboardRemove())
    bot.send_message(msg.chat.id, "Bo‘limni tanlang:", reply_markup=main_menu(uid))
    bot.send_message(msg.chat.id, "⬇️", reply_markup=ReplyKeyboardRemove())
    bot.send_message(msg.chat.id, "Buyurtma bo‘limi:", reply_markup=main_menu(uid))
    bot.send_message(msg.chat.id, "Buyurtmani boshlash uchun tugmani bosing:", reply_markup=main_menu(uid))
    bot.send_message(msg.chat.id, " ", reply_markup=ReplyKeyboardRemove())
    bot.send_message(msg.chat.id, "📦 Buyurtmalar menyusi:", reply_markup=main_menu(uid))
    bot.send_message(msg.chat.id, " ", reply_markup=ReplyKeyboardRemove())
    # Inline menyu
    bot.send_message(msg.chat.id, "📦 Buyurtma bo‘limlarini tanlang:", reply_markup=order_menu())

@bot.message_handler(content_types=['contact'])
def on_contact(msg):
    ensure_user(msg)
    uid = msg.from_user.id
    if not msg.contact or (msg.contact.user_id != uid and not is_admin(uid)):
        bot.reply_to(msg, "Iltimos, o‘zingizning raqamingizni ulashing.")
        return
    con=db();cur=con.cursor()
    cur.execute("UPDATE users SET phone=?, tg_name=?, username=?, real_name=? WHERE user_id=?",
                (msg.contact.phone_number, msg.from_user.full_name, msg.from_user.username or "",
                 msg.from_user.full_name, uid))
    con.commit();con.close()
    bot.send_message(msg.chat.id, "✅ Ro‘yxatdan o‘tdingiz!", reply_markup=main_menu(uid))
    bot.send_message(msg.chat.id, "📦 Buyurtma bo‘limlarini tanlang:", reply_markup=order_menu())

# =========================
# MENU HANDLERS
# =========================
@bot.message_handler(func=lambda m: m.text=="🧾 Buyurtma")
def m_order(msg):
    bot.send_message(msg.chat.id, "Bo‘limni tanlang:", reply_markup=order_menu())

@bot.message_handler(func=lambda m: m.text=="📞 Aloqa")
def m_contact(msg):
    bot.send_message(msg.chat.id, "✉️ Adminlar bilan yozishish uchun shu chatdan yozavering. Xabaringizga javob beramiz.")

@bot.message_handler(func=lambda m: m.text=="📊 Hisobot")
def m_report(msg):
    uid=msg.from_user.id
    bot.send_message(msg.chat.id, "Hisobot uchun <b>YYYY-MM-DD YYYY-MM-DD</b> formatda sana oralig‘ini yozing.\nMasalan: <code>2025-08-01 2025-08-31</code>")
    set_state(uid, "ask_report_range")

@bot.message_handler(func=lambda m: m.text=="🛠 Admin panel")
def m_admin(msg):
    uid=msg.from_user.id
    if not is_admin(uid):
        bot.reply_to(msg, "Bu bo‘lim faqat adminlar uchun.")
        return
    kb=InlineKeyboardMarkup()
    kb.row(InlineKeyboardButton("💸 Narxlar","adm_prices"),
           InlineKeyboardButton("👤 Mijoz narxi","adm_cprice"))
    kb.row(InlineKeyboardButton("➕ Admin qo‘shish","adm_addadmin"),
           InlineKeyboardButton("💳 Qarz boshqarish","adm_debt"))
    kb.row(InlineKeyboardButton("🧾 Ish haqi","adm_payroll"),
           InlineKeyboardButton("🗑 Buyurtma o‘chirish","adm_delorder"))
    kb.row(InlineKeyboardButton("⬅️ Orqaga","back_root"))
    bot.send_message(msg.chat.id, "Admin panelini tanlang:", reply_markup=kb)

# =========================
# CALLBACKS (ORDERS)
# =========================
@bot.callback_query_handler(func=lambda c: c.data=="back_orders")
def cb_back_orders(c):
    bot.edit_message_text("📦 Buyurtma bo‘limlarini tanlang:", c.message.chat.id, c.message.id, reply_markup=order_menu())

def start_file_capture(uid:int, chat_id:int, category:str, subkey:str=None):
    """
    Foydalanuvchi tanlagan bo‘lim kontekstini state'ga yozamiz.
    """
    payload = {"category":category, "subkey":subkey or ""}
    set_state(uid, "waiting_files", str(payload))
    note = ""
    if category in ("orakal","mat_orakal","setka") and subkey and subkey!="kichik":
        note = f"\n\n<i>Ushbu bo‘limda uzunlikni sm da kiriting yoki fayl nomida uzunlik bo‘lsin. Hisob: uzunlik×{subkey}×son/100</i>"
    elif category in ("orakal","mat_orakal","setka") and subkey=="kichik":
        note = "\n\n<i>Kichik varianti: eni×bo‘yi×son/10000</i>"
    else:
        note = "\n\n<i>Hisob: eni×bo‘yi×son/10000</i>"
    bot.send_message(chat_id, "Endi fayllarni yuboring (jpg/tiff). Bir nechta fayl yuborsangiz ham bo‘ladi."+note)

@bot.callback_query_handler(func=lambda c: c.data.startswith("order_"))
def cb_order(c):
    d = c.data
    if d=="order_banner":
        start_file_capture(c.from_user.id, c.message.chat.id, "banner")
        bot.answer_callback_query(c.id, "Banner tanlandi")
    elif d=="order_qbanner":
        start_file_capture(c.from_user.id, c.message.chat.id, "qora_banner")
        bot.answer_callback_query(c.id, "Qora banner tanlandi")
    elif d=="order_beklit":
        start_file_capture(c.from_user.id, c.message.chat.id, "beklit")
        bot.answer_callback_query(c.id, "Beklit tanlandi")
    elif d=="order_orakal":
        bot.edit_message_text("Orakal uchun pastdan tanlang:", c.message.chat.id, c.message.id, reply_markup=orakal_submenu("orakal"))
    elif d=="order_matorakal":
        bot.edit_message_text("Matoviy orakal uchun pastdan tanlang:", c.message.chat.id, c.message.id, reply_markup=orakal_submenu("matorakal"))
    elif d=="order_setka":
        bot.edit_message_text("Setka uchun pastdan tanlang:", c.message.chat.id, c.message.id, reply_markup=orakal_submenu("setka"))
    else:
        bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("orakal_") or c.data.startswith("matorakal_") or c.data.startswith("setka_"))
def cb_orakal_sub(c):
    part, sub = c.data.split("_",1)
    if part=="orakal":
        cat="orakal"
    elif part=="matorakal":
        cat="mat_orakal"
    else:
        cat="setka"
    start_file_capture(c.from_user.id, c.message.chat.id, cat, sub)
    bot.answer_callback_query(c.id, f"{cat} → {sub} tanlandi")

@bot.callback_query_handler(func=lambda c: c.data=="back_root")
def cb_back_root(c):
    bot.edit_message_text("Salom! Menyudan bo‘lim tanlang 👇", c.message.chat.id, c.message.id, reply_markup=None)
    bot.send_message(c.message.chat.id, "📦 Buyurtma bo‘limlarini tanlang:", reply_markup=order_menu())

# =========================
# FILE HANDLING
# =========================
def extension_ok(name:str):
    n = name.lower()
    return any(n.endswith(e) for e in ALLOWED_EXTS)

def mime_ok(mime:str):
    if not mime: return False
    return any(mime.startswith(m) for m in ALLOWED_MIMES)

def save_order(uid:int, category:str, subkey:str, file_name:str, count:int,
               width_cm:float, height_cm:float, length_cm:float, coef:float, area_m2:float):
    key_for_price = {
        "banner":"banner",
        "qora_banner":"qora_banner",
        "beklit":"beklit",
        "orakal":"orakal",
        "mat_orakal":"mat_orakal",
        "setka":"setka",
    }[category]
    unit_price = get_price(uid, key_for_price)
    total = int(round(area_m2 * unit_price))
    con=db();cur=con.cursor()
    cur.execute("""INSERT INTO orders(user_id,category,subkey,file_name,count,width_cm,height_cm,length_cm,coef,area_m2,unit_price,total_price,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (uid,category,subkey,file_name,count,width_cm,height_cm,length_cm,coef,area_m2,unit_price,total,datetime.utcnow().isoformat()))
    # init debt row if absent
    cur.execute("INSERT OR IGNORE INTO debts(user_id,amount) VALUES(?,0)",(uid,))
    # add to debt
    cur.execute("UPDATE debts SET amount=amount+? WHERE user_id=?", (total, uid))
    con.commit();con.close()
    return unit_price, total

def compute_area(category:str, subkey:str, width_cm, height_cm, length_cm, count:int):
    """
    Santimetr kiritilgan deb qabul qilamiz.
    Banner/Qora/Beklit/Kichik: area = w*h/10000 * count
    Orakal/Matoviy/Setka (1.07/1.27/1.52): area = (length_cm/100)*coef*count
    """
    coef = None
    area_m2 = 0.0
    if category in ("orakal","mat_orakal","setka") and subkey and subkey!="kichik":
        try:
            coef = float(subkey)
        except:
            coef = 1.0
        if not length_cm:
            return None, None  # kerakli uzunlik yo‘q
        area_m2 = (float(length_cm)/100.0) * coef * count
    else:
        if not width_cm or not height_cm:
            return None, None
        area_m2 = (float(width_cm)*float(height_cm)/10000.0) * count
    return (coef, round(area_m2, 4))

def handle_incoming_file(msg, file_name:str, mime:str):
    uid=msg.from_user.id
    state, payload = get_state(uid)
    if state!="waiting_files":
        bot.reply_to(msg, "Avval bo‘limni tanlang: /start → 🧾 Buyurtma.")
        return
    # ruxsat etilgan formatmi?
    if not (extension_ok(file_name) or mime_ok(mime)):
        bot.reply_to(msg, "❌ Bu format qo‘llab-quvvatlanmaydi. TIFF yoki JPG yuboring.")
        return
    # kontekst
    m = re.search(r"\{'category': '([^']+)', 'subkey': '([^']*)'\}", payload)
    if not m:
        bot.reply_to(msg, "Ichki holat topilmadi, qayta tanlang: 🧾 Buyurtma.")
        return
    category, subkey = m.group(1), (m.group(2) or "")

    # nomdan o‘qish
    w_cm, h_cm, L_cm, count = parse_name_for_dims_and_count(file_name)

    coef, area = compute_area(category, subkey, w_cm, h_cm, L_cm, count)
    if area is None:
        # kerakli o‘lchamlar yetishmadi — foydalanuvchidan so‘raymiz
        if category in ("orakal","mat_orakal","setka") and subkey and subkey!="kichik":
            bot.reply_to(msg, f"Uzunlik (sm) va sonni kiriting. Masalan: <code>300 4</code>  → (300 sm, 4 ta)")
            set_state(uid, "ask_len_count", f"{category}|{subkey}|{file_name}")
        else:
            bot.reply_to(msg, f"Eni va bo‘yni (sm), hamda sonni kiriting. Masalan: <code>150 200 3</code>")
            set_state(uid, "ask_whc", f"{category}|{subkey}|{file_name}")
        return

    unit_price, total = save_order(uid, category, subkey, file_name, count, w_cm, h_cm, L_cm, coef or 1.0, area)

    # javob
    if category in ("orakal","mat_orakal","setka") and subkey and subkey!="kichik":
        detail = f"Uzunlik: {L_cm or '-'} sm × koef {coef} × {count} ta"
    else:
        detail = f"Eni: {w_cm or '-'} sm × Bo‘yi: {h_cm or '-'} sm × {count} ta"
    bot.reply_to(msg,
        "✅ <b>Buyurtma qabul qilindi</b>\n"
        f"Bo‘lim: <b>{pretty_category(category, subkey)}</b>\n"
        f"{detail}\n"
        f"Maydon: <b>{area} m²</b>\n"
        f"Narx (m²): <b>{unit_price:,} so‘m</b>\n"
        f"Jami: <b>{total:,} so‘m</b>"
    )

def pretty_category(cat, sub):
    names = {
        "banner":"Banner",
        "qora_banner":"Qora banner",
        "beklit":"Beklit",
        "orakal":"Orakal",
        "mat_orakal":"Matoviy orakal",
        "setka":"Setka",
    }
    base = names.get(cat, cat)
    if cat in ("orakal","mat_orakal","setka"):
        if sub == "kichik": return f"{base} • Kichik"
        elif sub: return f"{base} • {sub}"
    return base

@bot.message_handler(content_types=["document"])
def on_document(msg):
    file_name = msg.document.file_name or "file"
    mime = msg.document.mime_type or ""
    handle_incoming_file(msg, file_name, mime)

@bot.message_handler(content_types=["photo"])
def on_photo(msg):
    # photoda asl nom yo‘q — foydalanuvchidan caption orqali o‘qishga harakat qilamiz
    name = (msg.caption or "photo").strip()
    handle_incoming_file(msg, name, "image/jpeg")

# =========================
# FOLLOW-UP (ASK WH/LEN)
# =========================
@bot.message_handler(func=lambda m: get_state(m.from_user.id)[0] in ("ask_whc","ask_len_count","ask_report_range",
                                                                     "adm_ask_price","adm_ask_client_price",
                                                                     "adm_ask_addadmin","adm_ask_debt",
                                                                     "adm_ask_payroll","adm_ask_delorder"))
def on_follow(m):
    uid=m.from_user.id
    state,payload=get_state(uid)

    if state=="ask_report_range":
        rng = m.text.strip().split()
        if len(rng)!=2:
            bot.reply_to(m, "Format: <code>YYYY-MM-DD YYYY-MM-DD</code>")
            return
        start, end = rng
        try:
            dt1 = datetime.fromisoformat(start)
            dt2 = datetime.fromisoformat(end)            
        except:
            bot.reply_to(m, "Sana noto‘g‘ri. Masalan: 2025-08-01 2025-08-31")
            return
        con=db();cur=con.cursor()
        cur.execute("""SELECT category,subkey,file_name,count,width_cm,height_cm,length_cm,coef,area_m2,unit_price,total_price,created_at
                       FROM orders WHERE user_id=? AND date(created_at) BETWEEN date(?) AND date(?) ORDER BY created_at""",
                    (uid, start, end))
        rows=cur.fetchall();con.close()
        if not rows:
            bot.reply_to(m, "Ushbu oralikda buyurtmalar topilmadi.")
            clear_state(uid);return
        total_area=0.0; total_sum=0
        lines=[]
        for r in rows:
            cat,sub,fname,cnt,w,h,L,cf,ar,up,tp,ts=r
            total_area += float(ar)
            total_sum += int(tp)
            lines.append(f"{ts[:10]} | {pretty_category(cat,sub)} | {fname} | {cnt} ta | {ar} m² | {tp:,} so‘m")
        text = "<b>Hisobot</b>\n" + "\n".join(lines[:60])  # telegram limitga ehtiyot
        text += f"\n\nJami maydon: <b>{round(total_area,4)} m²</b>\nJami summa: <b>{total_sum:,} so‘m</b>"
        bot.reply_to(m, text)

        # CSV
        buf = BytesIO()
        w = csv.writer(buf)
        w.writerow(["date","category","file","count","width_cm","height_cm","length_cm","coef","area_m2","unit_price","total"])
        for r in rows:
            w.writerow(r[11][:10:]+"" if False else [])
        # qayta yozish (yuqoridagi qo‘pol bo‘ldi), to‘g‘ri eksport:
        buf.seek(0); buf = BytesIO()  # tozalaymiz
        cw = csv.writer(buf)
        cw.writerow(["date","category","subkey","file","count","width_cm","height_cm","length_cm","coef","area_m2","unit_price","total"])
        for r in rows:
            cat,sub,fname,cnt,w,h,L,cf,ar,up,tp,ts=r
            cw.writerow([ts, pretty_category(cat,sub), sub, fname, cnt, w, h, L, cf, ar, up, tp])
        buf.seek(0)
        bot.send_document(m.chat.id, ("hisobot.csv", buf), caption=f"{start}..{end} oraligi uchun CSV")
        clear_state(uid);return

    if state=="ask_whc":
        # payload: category|subkey|filename
        try:
            category, subkey, fname = payload.split("|",2)
        except:
            bot.reply_to(m, "Holat xatosi. Qaytadan boshlang /start")
            clear_state(uid);return
        parts = m.text.replace(","," ").split()
        if len(parts) not in (2,3):
            bot.reply_to(m, "Format: <code>eni_sm bo‘yi_sm [son]</code>, masalan <code>150 200 3</code>")
            return
        w_cm = float(parts[0]); h_cm=float(parts[1]); count=int(parts[2]) if len(parts)==3 else 1
        coef, area = compute_area(category, subkey, w_cm, h_cm, None, count)
        if area is None:
            bot.reply_to(m,"Kiritilgan qiymatlar noto‘g‘ri.")
            return
        unit_price, total = save_order(uid, category, subkey, fname, count, w_cm, h_cm, None, coef or 1.0, area)
        bot.reply_to(m, f"✅ Buyurtma qabul qilindi\n{pretty_category(category,subkey)}\n"
                        f"Eni {w_cm} × Bo‘yi {h_cm} sm × {count} ta = {area} m²\n"
                        f"Narx: {unit_price:,} so‘m/m² → Jami {total:,} so‘m")
        clear_state(uid);return

    if state=="ask_len_count":
        # payload: category|subkey|filename
        try:
            category, subkey, fname = payload.split("|",2)
        except:
            bot.reply_to(m, "Holat xatosi. /start dan qayta kiriting.")
            clear_state(uid);return
        parts = m.text.replace(","," ").split()
        if len(parts) not in (1,2):
            bot.reply_to(m, "Format: <code>uzunlik_sm [son]</code>, masalan <code>300 4</code>")
            return
        L_cm = float(parts[0]); count=int(parts[1]) if len(parts)==2 else 1
        coef, area = compute_area(category, subkey, None, None, L_cm, count)
        if area is None:
            bot.reply_to(m,"Qiymatlar yetarli emas.")
            return
        unit_price, total = save_order(uid, category, subkey, fname, count, None, None, L_cm, coef or 1.0, area)
        bot.reply_to(m, f"✅ Buyurtma qabul qilindi\n{pretty_category(category,subkey)}\n"
                        f"Uzunlik {L_cm} sm × koef {coef} × {count} ta = {area} m²\n"
                        f"Narx: {unit_price:,} so‘m/m² → Jami {total:,} so‘m")
        clear_state(uid);return

    # ===== Admin flowlar =====
    if state=="adm_ask_price":
        # payload: key
        key = payload
        try:
            newp = int(m.text.strip())
        except:
            bot.reply_to(m, "Butun son kiriting.")
            return
        con=db();cur=con.cursor()
        cur.execute("REPLACE INTO prices(key,value) VALUES(?,?)",(key,newp))
        con.commit();con.close()
        bot.reply_to(m, f"✅ '{key}' narxi {newp:,} so‘m/m² qilib saqlandi.")
        clear_state(uid);return

    if state=="adm_ask_client_price":
        # payload: key|user_id
        key, who = payload.split("|",1)
        who=int(who)
        try:
            newp = int(m.text.strip())
        except:
            bot.reply_to(m,"Butun son kiriting.")
            return
        con=db();cur=con.cursor()
        cur.execute("REPLACE INTO client_prices(user_id,key,value) VALUES(?,?,?)",(who,key,newp))
        con.commit();con.close()
        bot.reply_to(m, f"✅ Mijoz {who} uchun '{key}' narxi {newp:,} so‘m/m² bo‘ldi.")
        clear_state(uid);return

    if state=="adm_ask_addadmin":
        if uid!=SUPER_ADMIN_ID:
            bot.reply_to(m,"Yangi admin qo‘shish faqat super-admin uchun.")
            clear_state(uid);return
        try:
            new_id = int(m.text.strip())
        except:
            bot.reply_to(m, "Foydalanuvchi ID sini kiriting (butun son).")
            return
        con=db();cur=con.cursor()
        cur.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)",(new_id,))
        con.commit();con.close()
        bot.reply_to(m, f"✅ {new_id} admin qilindi.")
        clear_state(uid);return

    if state=="adm_ask_debt":
        # payload: user_id
        who=int(payload)
        try:
            delta = int(m.text.strip())
        except:
            bot.reply_to(m,"Butun son kiriting. (masalan 50000 yoki -20000)")
            return
        con=db();cur=con.cursor()
        cur.execute("INSERT OR IGNORE INTO debts(user_id,amount) VALUES(?,0)",(who,))
        cur.execute("UPDATE debts SET amount=amount+? WHERE user_id=?", (delta, who))
        con.commit();con.close()
        bot.reply_to(m, f"✅ Qarz {delta:+,} so‘mga yangilandi.")
        clear_state(uid);return

    if state=="adm_ask_payroll":
        rng = m.text.strip().split()
        if len(rng)!=2:
            bot.reply_to(m, "Format: <code>YYYY-MM-DD YYYY-MM-DD</code>")
            return
        start,end=rng
        con=db();cur=con.cursor()
        cur.execute("""SELECT SUM(area_m2) FROM orders WHERE date(created_at) BETWEEN date(?) AND date(?)""",
                    (start,end))
        s = cur.fetchone()[0] or 0.0
        con.close()
        pay = int(round(float(s)*ISH_HAQI_K))
        bot.reply_to(m, f"🧾 Ish haqi hisobi\nOralik: {start}..{end}\nJami m²: {round(float(s),4)}\nTo‘lov: <b>{pay:,} so‘m</b>")
        clear_state(uid);return

    if state=="adm_ask_delorder":
        try:
            oid = int(m.text.strip())
        except:
            bot.reply_to(m,"Buyurtma ID (butun son) kiriting.")
            return
        con=db();cur=con.cursor()
        # avval topamiz
        cur.execute("SELECT user_id,total_price FROM orders WHERE id=?",(oid,))
        r=cur.fetchone()
        if not r:
            bot.reply_to(m,"Bunday ID topilmadi.")
            con.close();clear_state(uid);return
        user_id,total=r
        cur.execute("DELETE FROM orders WHERE id=?",(oid,))
        cur.execute("UPDATE debts SET amount=amount-? WHERE user_id=?", (total,user_id))
        con.commit();con.close()
        bot.reply_to(m, f"✅ Buyurtma #{oid} o‘chirildi va qarzdan {total:,} so‘m olib tashlandi.")
        clear_state(uid);return


# =========================
# ADMIN CALLBACKS
# =========================
@bot.callback_query_handler(func=lambda c: c.data=="adm_prices")
def cb_prices(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id, "Adminlar uchun.")
        return
    con=db();cur=con.cursor()
    cur.execute("SELECT key,value FROM prices")
    rows=cur.fetchall();con.close()
    lines = ["<b>Standart narxlar (so‘m/m²)</b>"]
    for k,v in rows:
        lines.append(f"• {k}: <b>{int(v):,}</b>")
    kb=InlineKeyboardMarkup()
    for k,_ in rows:
        kb.add(InlineKeyboardButton(f"⚙️ {k} ni o‘zgartirish", callback_data=f"set_price|{k}"))
    kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="back_root"))
    bot.send_message(c.message.chat.id, "\n".join(lines), reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("set_price|"))
def cb_setprice(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id,"Adminlar uchun.")
        return
    key=c.data.split("|",1)[1]
    set_state(c.from_user.id,"adm_ask_price", key)
    bot.send_message(c.message.chat.id, f"Yangi narxni kiriting (so‘m/m²) uchun: <b>{key}</b>")

@bot.callback_query_handler(func=lambda c: c.data=="adm_cprice")
def cb_cprice(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id,"Adminlar uchun.");return
    bot.send_message(c.message.chat.id, "Format: <code>user_id key yangi_narx</code>\nMasalan: <code>123456789 banner 40000</code>")
    set_state(c.from_user.id, "adm_ask_cprice_triplet", "")

@bot.message_handler(func=lambda m: get_state(m.from_user.id)[0]=="adm_ask_cprice_triplet")
def on_cprice_triplet(m):
    uid=m.from_user.id
    if not is_admin(uid):
        clear_state(uid);return
    parts=m.text.split()
    if len(parts)!=3:
        bot.reply_to(m,"Aynan 3 ta qiymat kiriting: <code>user_id key yangi_narx</code>")
        return
    try:
        who=int(parts[0]); key=parts[1]; price=int(parts[2])
    except:
        bot.reply_to(m,"Qiymatlar noto‘g‘ri.")
        return
    con=db();cur=con.cursor()
    cur.execute("REPLACE INTO client_prices(user_id,key,value) VALUES(?,?,?)",(who,key,price))
    con.commit();con.close()
    bot.reply_to(m,f"✅ {who} uchun {key} = {price:,} saqlandi.")
    clear_state(uid)

@bot.callback_query_handler(func=lambda c: c.data=="adm_addadmin")
def cb_addadmin(c):
    if c.from_user.id!=SUPER_ADMIN_ID:
        bot.answer_callback_query(c.id,"Yangi admin qo‘shish faqat super-admin uchun.")
        return
    bot.send_message(c.message.chat.id, "Yangi adminning <b>Telegram ID</b> sini yuboring.")
    set_state(c.from_user.id,"adm_ask_addadmin","")

@bot.callback_query_handler(func=lambda c: c.data=="adm_debt")
def cb_debt(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id,"Adminlar uchun.");return
    bot.send_message(c.message.chat.id, "Format: <code>user_id delta_som</code>\nMasalan: <code>123456789 -20000</code>")
    set_state(c.from_user.id,"adm_ask_debt","")

@bot.callback_query_handler(func=lambda c: c.data=="adm_payroll")
def cb_payroll(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id,"Adminlar uchun.");return
    bot.send_message(c.message.chat.id, "Ish haqi uchun sana oralig‘i: <code>YYYY-MM-DD YYYY-MM-DD</code>")
    set_state(c.from_user.id,"adm_ask_payroll","")

@bot.callback_query_handler(func=lambda c: c.data=="adm_delorder")
def cb_delorder(c):
    if not is_admin(c.from_user.id):
        bot.answer_callback_query(c.id,"Adminlar uchun.");return
    bot.send_message(c.message.chat.id, "O‘chiriladigan buyurtma ID sini yuboring.")
    set_state(c.from_user.id,"adm_ask_delorder","")

# =========================
# FLASK KEEP-ALIVE (Render Web Service)
# =========================
app = Flask(__name__)

@app.route("/")
def index():
    return "OK", 200

def run_flask():
    app.run(host="0.0.0.0", port=PORT, debug=False)

def run_bot():
    # polling
    bot.infinity_polling(timeout=60, long_polling_timeout=30)

if __name__ == "__main__":
    # Flask va botni parallel ishga tushiramiz
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    run_bot()
