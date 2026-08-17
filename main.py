import time
import threading
from datetime import datetime, timedelta

import telebot
from telebot import types

from config import BOT_TOKEN, ADMIN_ID

from database import (
    init_database,
    save_user,
    create_payment,
    get_connection,
)

from collector import index_profile

bot = telebot.TeleBot(BOT_TOKEN)


# ============================================================
# 💎 VIP TARIFLAR
# ============================================================

PLANS = {
    "10m": {
        "name": "10 daqiqa",
        "minutes": 10,
        "price": 5000,
    },
    "30m": {
        "name": "30 daqiqa",
        "minutes": 30,
        "price": 10000,
    },
    "99m": {
        "name": "99 daqiqa",
        "minutes": 99,
        "price": 20000,
    },
    "2d": {
        "name": "2 kun",
        "minutes": 2 * 24 * 60,
        "price": 30000,
    },
    "7d": {
        "name": "7 kun",
        "minutes": 7 * 24 * 60,
        "price": 50000,
    },
    "30d": {
        "name": "30 kun",
        "minutes": 30 * 24 * 60,
        "price": 100000,
    },
}

CARD_NUMBER = "9860606750247151"
CARD_NAME = "Abidjanov H"


# ============================================================
# 🧰 YORDAMCHI FUNKSIYALAR
# ============================================================

def format_money(amount):
    return f"{amount:,}".replace(",", " ")


def get_plan(code):
    return PLANS.get(code)


def get_pending_payment(telegram_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, plan_name, amount
        FROM payments
        WHERE telegram_id = %s
        AND status = 'pending'
        ORDER BY id DESC
        LIMIT 1
    """, (telegram_id,))

    result = cur.fetchone()

    cur.close()
    conn.close()

    return result


def get_active_vip(telegram_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, plan_name, starts_at, expires_at
        FROM vip_subscriptions
        WHERE telegram_id = %s
        AND active = TRUE
        AND expires_at > CURRENT_TIMESTAMP
        ORDER BY expires_at DESC
        LIMIT 1
    """, (telegram_id,))

    result = cur.fetchone()

    cur.close()
    conn.close()

    return result


def deactivate_expired_vips():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE vip_subscriptions
        SET active = FALSE
        WHERE active = TRUE
        AND expires_at <= CURRENT_TIMESTAMP
    """)

    conn.commit()

    cur.close()
    conn.close()


def vip_worker():
    while True:
        try:
            deactivate_expired_vips()
        except Exception as e:
            print("VIP worker xatosi:", e)

        time.sleep(30)


# ============================================================
# 🔎 QIDIRUV — DATABASE
# ============================================================

def search_profile(query):
    """
    indexed_profiles jadvalidan username yoki Telegram ID bo'yicha
    oldindan indekslangan profilni qidiradi.
    """

    conn = get_connection()
    cur = conn.cursor()

    query = query.strip()

    if query.startswith("@"):
        username = query[1:].lower()

        cur.execute("""
            SELECT
                telegram_id,
                username,
                first_name,
                last_name,
                bio,
                created_at,
                updated_at
            FROM indexed_profiles
            WHERE LOWER(username) = %s
            ORDER BY updated_at DESC
            LIMIT 1
        """, (username,))

    elif query.isdigit():

        telegram_id = int(query)

        cur.execute("""
            SELECT
                telegram_id,
                username,
                first_name,
                last_name,
                bio,
                created_at,
                updated_at
            FROM indexed_profiles
            WHERE telegram_id = %s
            ORDER BY updated_at DESC
            LIMIT 1
        """, (telegram_id,))

    else:
        cur.close()
        conn.close()
        return None

    result = cur.fetchone()

    cur.close()
    conn.close()

    return result


def search_messages(telegram_id, limit=20):
    """
    Tizimda oldindan indekslangan xabarlarni qidiradi.
    """

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            chat_title,
            message_id,
            message_text,
            message_date
        FROM indexed_messages
        WHERE telegram_id = %s
        ORDER BY message_date DESC
        LIMIT %s
    """, (telegram_id, limit))

    results = cur.fetchall()

    cur.close()
    conn.close()

    return results


def save_search_log(telegram_id, query):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO search_logs
        (telegram_id, query)
        VALUES (%s, %s)
    """, (telegram_id, query))

    conn.commit()

    cur.close()
    conn.close()


# ============================================================
# 🚀 START
# ============================================================
@bot.message_handler(commands=["start"])
def start(message):

    save_user(message.from_user)
    index_profile(message.from_user)

    markup = types.InlineKeyboardMarkup(row_width=1)

    markup.add(
        types.InlineKeyboardButton(
            "💎 VIP tariflar",
            callback_data="vip"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🔎 Qidiruv",
            callback_data="search"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "👤 Profilim",
            callback_data="profile"
        )
    )

    if message.from_user.id == ADMIN_ID:
        markup.add(
            types.InlineKeyboardButton(
                "👨‍💼 Admin panel",
                callback_data="admin"
            )
        )

    bot.send_message(
        message.chat.id,
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "🔎 Telegram qidiruv tizimiga xush kelibsiz.\n\n"
        "Kerakli bo‘limni tanlang:",
        reply_markup=markup,
        parse_mode="HTML"
    )


# ============================================================
# 💎 VIP MENYU
# ============================================================

@bot.callback_query_handler(func=lambda call: call.data == "vip")
def vip_menu(call):

    bot.answer_callback_query(call.id)

    pending = get_pending_payment(call.from_user.id)

    if pending:
        bot.send_message(
            call.message.chat.id,
            "⚠️ <b>Sizda ko‘rib chiqilayotgan ariza mavjud.</b>\n\n"
            "Admin arizangizni tasdiqlashi yoki rad etishini kuting.",
            parse_mode="HTML"
        )
        return

    active_vip = get_active_vip(call.from_user.id)

    if active_vip:
        bot.send_message(
            call.message.chat.id,
            "💎 Sizda hozir faol VIP mavjud.\n\n"
            "Joriy VIP muddati tugagandan keyin yangi tarif olishingiz mumkin."
        )
        return

    markup = types.InlineKeyboardMarkup(row_width=2)

    for code, plan in PLANS.items():
        markup.add(
            types.InlineKeyboardButton(
                f"💎 {plan['name']}\n"
                f"💰 {format_money(plan['price'])} so‘m",
                callback_data=f"plan_{code}"
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            "⬅️ Orqaga",
            callback_data="back_main"
        )
    )

    bot.edit_message_text(
        "💎 <b>VIP tariflardan birini tanlang:</b>",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="HTML"
    )


# ============================================================
# 💎 TARIF TANLASH
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("plan_")
)
def select_plan(call):

    code = call.data.replace("plan_", "")
    plan = get_plan(code)

    if not plan:
        bot.answer_callback_query(
            call.id,
            "Tarif topilmadi!",
            show_alert=True
        )
        return

    if get_pending_payment(call.from_user.id):
        bot.answer_callback_query(
            call.id,
            "Sizda ko‘rib chiqilayotgan ariza bor!",
            show_alert=True
        )
        return

    if get_active_vip(call.from_user.id):
        bot.answer_callback_query(
            call.id,
            "Sizda faol VIP mavjud!",
            show_alert=True
        )
        return

    markup = types.InlineKeyboardMarkup(row_width=1)

    markup.add(
        types.InlineKeyboardButton(
            "💳 To‘lov qildim",
            callback_data=f"payment_{code}"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "⬅️ Tariflarga qaytish",
            callback_data="vip"
        )
    )

    bot.answer_callback_query(call.id)

    bot.edit_message_text(
        f"💎 <b>{plan['name']}</b>\n\n"
        f"💰 Narxi: <b>{format_money(plan['price'])} so‘m</b>\n\n"
        "💳 <b>To‘lov uchun karta:</b>\n"
        f"<code>{CARD_NUMBER}</code>\n"
        f"👤 {CARD_NAME}\n\n"
        "To‘lovni amalga oshirgach, "
        "«💳 To‘lov qildim» tugmasini bosing.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="HTML"
    )


# ============================================================
# 💳 TO‘LOV ARIZASI
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("payment_")
)
def payment(call):

    code = call.data.replace("payment_", "")
    plan = get_plan(code)

    if not plan:
        bot.answer_callback_query(
            call.id,
            "Tarif topilmadi!",
            show_alert=True
        )
        return

    if get_pending_payment(call.from_user.id):
        bot.answer_callback_query(
            call.id,
            "Sizda allaqachon ariza mavjud!",
            show_alert=True
        )
        return

    if get_active_vip(call.from_user.id):
        bot.answer_callback_query(
            call.id,
            "Sizda faol VIP mavjud!",
            show_alert=True
        )
        return

    payment_id = create_payment(
        call.from_user.id,
        plan["name"],
        plan["price"]
    )

    if payment_id is False:
        bot.answer_callback_query(
            call.id,
            "Sizda ko‘rib chiqilayotgan ariza mavjud!",
            show_alert=True
        )
        return

    username = call.from_user.username or "yo‘q"

    admin_markup = types.InlineKeyboardMarkup(row_width=2)

    admin_markup.add(
        types.InlineKeyboardButton(
            "✅ TASDIQLASH",
            callback_data=f"approve_{payment_id}"
        ),
        types.InlineKeyboardButton(
            "❌ RAD ETISH",
            callback_data=f"reject_{payment_id}"
        )
    )

    admin_text = (
        "🆕 <b>YANGI TO‘LOV ARIZASI</b>\n\n"
        f"🆔 Ariza: <code>#{payment_id}</code>\n"
        f"👤 Ism: {call.from_user.first_name}\n"
        f"🔗 Username: @{username}\n"
        f"🆔 Telegram ID: <code>{call.from_user.id}</code>\n\n"
        f"💎 Tarif: <b>{plan['name']}</b>\n"
        f"💰 Summa: <b>{format_money(plan['price'])} so‘m</b>"
    )

    bot.send_message(
        ADMIN_ID,
        admin_text,
        reply_markup=admin_markup,
        parse_mode="HTML"
    )

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        "✅ <b>Arizangiz adminga yuborildi!</b>\n\n"
        f"💎 Tarif: {plan['name']}\n"
        f"💰 Summa: {format_money(plan['price'])} so‘m\n\n"
        "⏳ Admin to‘lovni tekshirmoqda.\n"
        "Tasdiqlanmaguncha boshqa tariflardan foydalanib bo‘lmaydi.",
        parse_mode="HTML"
    )


# ============================================================
# 👨‍💼 TASDIQLASH
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("approve_")
)
def approve_payment(call):

    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(
            call.id,
            "Siz admin emassiz!",
            show_alert=True
        )
        return

    payment_id = int(call.data.replace("approve_", ""))

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT telegram_id, plan_name, amount, status
        FROM payments
        WHERE id = %s
    """, (payment_id,))

    data = cur.fetchone()

    if not data:
        cur.close()
        conn.close()
        bot.answer_callback_query(
            call.id,
            "Ariza topilmadi!",
            show_alert=True
        )
        return

    telegram_id, plan_name, amount, status = data

    if status != "pending":
        cur.close()
        conn.close()
        bot.answer_callback_query(
            call.id,
            "Ariza allaqachon yopilgan!",
            show_alert=True
        )
        return

    minutes = None

    for plan in PLANS.values():
        if plan["name"] == plan_name:
            minutes = plan["minutes"]
            break

    if minutes is None:
        cur.close()
        conn.close()
        bot.answer_callback_query(
            call.id,
            "Tarif topilmadi!",
            show_alert=True
        )
        return

    starts_at = datetime.now()
    expires_at = starts_at + timedelta(minutes=minutes)

    cur.execute("""
        UPDATE payments
        SET status = 'approved'
        WHERE id = %s
    """, (payment_id,))

    cur.execute("""
        INSERT INTO vip_subscriptions
        (
            telegram_id,
            plan_name,
            starts_at,
            expires_at,
            active
        )
        VALUES (%s, %s, %s, %s, TRUE)
    """, (
        telegram_id,
        plan_name,
        starts_at,
        expires_at
    ))

    conn.commit()

    cur.close()
    conn.close()

    bot.answer_callback_query(
        call.id,
        "VIP tasdiqlandi!",
        show_alert=True
    )

    try:
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=None
        )
    except Exception:
        pass

    bot.send_message(
        telegram_id,
        "🎉 <b>To‘lov tasdiqlandi!</b>\n\n"
        f"💎 VIP: <b>{plan_name}</b>\n"
        f"💰 To‘lov: {format_money(amount)} so‘m\n\n"
        f"⏰ Boshlanish: {starts_at:%Y-%m-%d %H:%M}\n"
        f"⏳ Tugash: {expires_at:%Y-%m-%d %H:%M}\n\n"
        "✅ VIP faollashtirildi.",
        parse_mode="HTML"
    )


# ============================================================
# ❌ RAD ETISH
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("reject_")
)
def reject_payment(call):

    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(
            call.id,
            "Siz admin emassiz!",
            show_alert=True
        )
        return

    payment_id = int(call.data.replace("reject_", ""))

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT telegram_id, plan_name
        FROM payments
        WHERE id = %s
        AND status = 'pending'
    """, (payment_id,))

    data = cur.fetchone()

    if not data:
        cur.close()
        conn.close()
        bot.answer_callback_query(
            call.id,
            "Ariza topilmadi yoki yopilgan!",
            show_alert=True
        )
        return

    telegram_id, plan_name = data

    cur.execute("""
        UPDATE payments
        SET status = 'rejected'
        WHERE id = %s
    """, (payment_id,))

    conn.commit()

    cur.close()
    conn.close()

    bot.answer_callback_query(
        call.id,
        "Ariza rad etildi!",
        show_alert=True
    )

    try:
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=None
        )
    except Exception:
        pass

    bot.send_message(
        telegram_id,
        "❌ <b>Arizangiz rad etildi.</b>\n\n"
        f"💎 Tarif: {plan_name}\n\n"
        "Endi yangi tarif uchun ariza yuborishingiz mumkin.",
        parse_mode="HTML"
    )


# ============================================================
# 👤 PROFILIM
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data == "profile"
)
def profile(call):

    bot.answer_callback_query(call.id)

    username = call.from_user.username or "yo‘q"
    vip = get_active_vip(call.from_user.id)

    if vip:

        vip_id, plan_name, starts_at, expires_at = vip

        remaining = expires_at - datetime.now()
        seconds = max(0, int(remaining.total_seconds()))

        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60

        if days:
            remaining_text = f"{days} kun {hours} soat"
        else:
            remaining_text = f"{hours} soat {minutes} daqiqa"

        vip_text = (
            "🟢 <b>VIP FAOL</b>\n\n"
            f"💎 Tarif: <b>{plan_name}</b>\n"
            f"⏳ Qolgan vaqt: <b>{remaining_text}</b>\n"
            f"📅 Tugash: <b>{expires_at:%Y-%m-%d %H:%M}</b>"
        )

    else:
        vip_text = (
            "🔴 <b>VIP faol emas</b>\n\n"
            "Qidiruvdan foydalanish uchun VIP tarif oling."
        )

    markup = types.InlineKeyboardMarkup(row_width=1)

    markup.add(
        types.InlineKeyboardButton(
            "💎 VIP tariflar",
            callback_data="vip"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🔎 Qidiruv",
            callback_data="search"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "⬅️ Bosh menyu",
            callback_data="back_main"
        )
    )

    bot.send_message(
        call.message.chat.id,
        "👤 <b>PROFILIM</b>\n\n"
        f"🆔 ID: <code>{call.from_user.id}</code>\n"
        f"👤 Username: @{username}\n\n"
        f"{vip_text}",
        reply_markup=markup,
        parse_mode="HTML"
    )


# ============================================================
# 🔎 QIDIRUVNI BOSHLASH
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data == "search"
)
def search_menu(call):

    bot.answer_callback_query(call.id)

    vip = get_active_vip(call.from_user.id)

    if not vip:

        markup = types.InlineKeyboardMarkup()

        markup.add(
            types.InlineKeyboardButton(
                "💎 VIP tariflar",
                callback_data="vip"
            )
        )

        bot.send_message(
            call.message.chat.id,
            "🔒 <b>Qidiruv yopiq.</b>\n\n"
            "Qidiruvdan foydalanish uchun faol VIP kerak.",
            reply_markup=markup,
            parse_mode="HTML"
        )

        return

    bot.send_message(
        call.message.chat.id,
        "🔎 <b>Qidiruv</b>\n\n"
        "Username yoki Telegram ID yuboring.\n\n"
        "Misol:\n"
        "<code>@username</code>\n"
        "<code>123456789</code>\n\n"
        "ℹ️ Natijalar tizimda oldindan "
        "indekslangan ochiq/ruxsat etilgan "
        "ma’lumotlardan olinadi.",
        parse_mode="HTML"
    )

    bot.register_next_step_handler(
        call.message,
        process_search
    )


# ============================================================
# 🔎 QIDIRUVNI BAJARISH
# ============================================================

def process_search(message):

    query = message.text.strip()

    if not query:
        bot.send_message(
            message.chat.id,
            "❌ Qidiruv so‘rovi bo‘sh."
        )
        return

    vip = get_active_vip(message.from_user.id)

    if not vip:
        bot.send_message(
            message.chat.id,
            "🔒 VIP muddati tugagan."
        )
        return

    if len(query) > 100:
        bot.send_message(
            message.chat.id,
            "❌ So‘rov juda uzun."
        )
        return

    save_search_log(
        message.from_user.id,
        query
    )

    profile_data = search_profile(query)

    if not profile_data:

        bot.send_message(
            message.chat.id,
            "❌ <b>Ma’lumot topilmadi.</b>\n\n"
            f"🔎 So‘rov: <code>{query}</code>\n\n"
            "Bu profil hali tizimimizda "
            "indekslanmagan bo‘lishi mumkin.",
            parse_mode="HTML"
        )

        return

    (
        telegram_id,
        username,
        first_name,
        last_name,
        bio,
        created_at,
        updated_at
    ) = profile_data

    messages = search_messages(
        telegram_id,
        limit=20
    )

    username_text = (
        f"@{username}"
        if username
        else "yo‘q"
    )

    full_name = " ".join(
        x for x in [first_name, last_name]
        if x
    )

    if not full_name:
        full_name = "Noma’lum"

    # --------------------------------------------------------
    # 👤 PROFIL
    # --------------------------------------------------------

    profile_text = (
        "👤 <b>PROFIL TOPILDI</b>\n\n"
        f"👤 Ism: <b>{full_name}</b>\n"
        f"🔗 Username: <b>{username_text}</b>\n"
        f"🆔 Telegram ID: <code>{telegram_id}</code>\n"
    )

    if bio:
        profile_text += (
            f"📝 Bio: {bio[:500]}\n"
        )

    if created_at:
        profile_text += (
            f"\n📅 Birinchi indeks: "
            f"{created_at:%Y-%m-%d %H:%M}"
        )

    if updated_at:
        profile_text += (
            f"\n🔄 Oxirgi yangilanish: "
            f"{updated_at:%Y-%m-%d %H:%M}"
        )

    bot.send_message(
        message.chat.id,
        profile_text,
        parse_mode="HTML"
    )

    # --------------------------------------------------------
    # 💬 XABARLAR
    # --------------------------------------------------------

    if not messages:

        bot.send_message(
            message.chat.id,
            "💬 <b>Indekslangan xabarlar</b>\n\n"
            "Hozircha shu profilga tegishli "
            "indekslangan ochiq xabar topilmadi.",
            parse_mode="HTML"
        )

        return

    bot.send_message(
        message.chat.id,
        f"💬 <b>Topilgan xabarlar:</b> {len(messages)}",
        parse_mode="HTML"
    )

    for chat_title, message_id, text, message_date in messages:

        if not text:
            text = "(matn mavjud emas)"

        text = text[:700]

        date_text = (
            message_date.strftime("%Y-%m-%d %H:%M")
            if message_date
            else "noma’lum"
        )

        msg_text = (
            "💬 <b>XABAR</b>\n\n"
            f"📢 Chat: <b>{chat_title or 'Noma’lum'}</b>\n"
            f"📅 Sana: {date_text}\n"
            f"🆔 Xabar ID: <code>{message_id}</code>\n\n"
            f"{text}"
        )

        bot.send_message(
            message.chat.id,
            msg_text,
            parse_mode="HTML"
        )


# ============================================================
# 👨‍💼 ADMIN PANEL
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data == "admin"
)
def admin_panel(call):

    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(
            call.id,
            "Siz admin emassiz!",
            show_alert=True
        )
        return

    bot.answer_callback_query(call.id)

    markup = types.InlineKeyboardMarkup(row_width=1)

    markup.add(
        types.InlineKeyboardButton(
            "📋 Pending arizalar",
            callback_data="admin_pending"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "📊 Statistika",
            callback_data="admin_stats"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "⬅️ Bosh menyu",
            callback_data="back_main"
        )
    )

    bot.send_message(
        call.message.chat.id,
        "👨‍💼 <b>ADMIN PANEL</b>\n\n"
        "Kerakli bo‘limni tanlang:",
        reply_markup=markup,
        parse_mode="HTML"
    )


# ============================================================
# 📋 PENDING
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data == "admin_pending"
)
def admin_pending(call):

    if call.from_user.id != ADMIN_ID:
        return

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            id,
            telegram_id,
            plan_name,
            amount,
            created_at
        FROM payments
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT 20
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    bot.answer_callback_query(call.id)

    if not rows:
        bot.send_message(
            call.message.chat.id,
            "📭 Pending arizalar yo‘q."
        )
        return

    for row in rows:

        payment_id, telegram_id, plan_name, amount, created_at = row

        markup = types.InlineKeyboardMarkup(row_width=2)

        markup.add(
            types.InlineKeyboardButton(
                "✅ Tasdiqlash",
                callback_data=f"approve_{payment_id}"
            ),
            types.InlineKeyboardButton(
                "❌ Rad etish",
                callback_data=f"reject_{payment_id}"
            )
        )

        bot.send_message(
            call.message.chat.id,
            "🆕 <b>PENDING ARIZA</b>\n\n"
            f"🆔 #{payment_id}\n"
            f"👤 ID: <code>{telegram_id}</code>\n"
            f"💎 Tarif: {plan_name}\n"
            f"💰 Summa: {format_money(amount)} so‘m\n"
            f"🕐 {created_at}",
            reply_markup=markup,
            parse_mode="HTML"
        )


# ============================================================
# 📊 STATISTIKA
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data == "admin_stats"
)
def admin_stats(call):

    if call.from_user.id != ADMIN_ID:
        return

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    users_count = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM payments
        WHERE status = 'approved'
    """)
    approved_count = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM payments
        WHERE status = 'pending'
    """)
    pending_count = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM vip_subscriptions
        WHERE active = TRUE
        AND expires_at > CURRENT_TIMESTAMP
    """)
    active_vips = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM search_logs
    """)
    searches_count = cur.fetchone()[0]

    cur.close()
    conn.close()

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        "📊 <b>STATISTIKA</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{users_count}</b>\n"
        f"💎 Faol VIP: <b>{active_vips}</b>\n"
        f"💳 Tasdiqlangan to‘lovlar: <b>{approved_count}</b>\n"
        f"⏳ Pending arizalar: <b>{pending_count}</b>\n"
        f"🔎 Qidiruvlar: <b>{searches_count}</b>",
        parse_mode="HTML"
    )


# ============================================================
# 🔙 BOSH MENU
# ============================================================

@bot.callback_query_handler(
    func=lambda call: call.data == "back_main"
)
def back_main(call):

    bot.answer_callback_query(call.id)

    markup = types.InlineKeyboardMarkup(row_width=1)

    markup.add(
        types.InlineKeyboardButton(
            "💎 VIP tariflar",
            callback_data="vip"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🔎 Qidiruv",
            callback_data="search"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "👤 Profilim",
            callback_data="profile"
        )
    )

    if call.from_user.id == ADMIN_ID:
        markup.add(
            types.InlineKeyboardButton(
                "👨‍💼 Admin panel",
                callback_data="admin"
            )
        )

    bot.edit_message_text(
        "🏠 <b>Bosh menyu</b>\n\n"
        "Kerakli bo‘limni tanlang:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="HTML"
    )


# ============================================================
# 🚀 ISHGA TUSHIRISH
# ============================================================

if __name__ == "__main__":

    print("⏳ Database ishga tushmoqda...")

    init_database()

    print("✅ Database tayyor!")

    worker = threading.Thread(
        target=vip_worker,
        daemon=True
    )

    worker.start()

    print("🤖 BOT ISHGA TUSHDI")

    bot.infinity_polling(
        skip_pending=True
    )
