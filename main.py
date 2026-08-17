import telebot
from telebot import types

from config import BOT_TOKEN
from database import init_database, save_user

bot = telebot.TeleBot(BOT_TOKEN)


@bot.message_handler(commands=["start"])
def start(message):
    save_user(message.from_user)

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "💎 VIP tariflar",
            callback_data="vip"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "👤 Profilim",
            callback_data="profile"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "🔎 Qidiruv",
            callback_data="search"
        )
    )

    bot.send_message(
        message.chat.id,
        "👋 Assalomu alaykum!\n\n"
        "🔎 Telegram qidiruv tizimiga xush kelibsiz.",
        reply_markup=markup
    )


# 💎 VIP TARIFLAR
@bot.callback_query_handler(func=lambda call: call.data == "vip")
def vip_menu(call):
    bot.answer_callback_query(call.id)

    markup = types.InlineKeyboardMarkup()

    plans = [
        ("10 daqiqa", "10m"),
        ("30 daqiqa", "30m"),
        ("99 daqiqa", "99m"),
        ("2 kun", "2d"),
        ("7 kun", "7d"),
        ("30 kun", "30d"),
    ]

    for name, code in plans:
        markup.add(
            types.InlineKeyboardButton(
                f"💎 {name}",
                callback_data=f"plan_{code}"
            )
        )

    bot.edit_message_text(
        "💎 VIP tariflardan birini tanlang:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )


# 👤 PROFIL
@bot.callback_query_handler(func=lambda call: call.data == "profile")
def profile(call):
    bot.answer_callback_query(call.id)

    username = call.from_user.username

    bot.send_message(
        call.message.chat.id,
        "👤 <b>Profilingiz</b>\n\n"
        f"🆔 ID: <code>{call.from_user.id}</code>\n"
        f"👤 Username: @{username if username else 'yo‘q'}\n\n"
        "💎 VIP: Hozircha faol emas",
        parse_mode="HTML"
    )


# 🔎 QIDIRUV
@bot.callback_query_handler(func=lambda call: call.data == "search")
def search_info(call):
    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        "🔎 Qidiruvdan foydalanish uchun faol VIP kerak."
    )


# 💎 TARIF TANLASH
@bot.callback_query_handler(
    func=lambda call: call.data.startswith("plan_")
)
def select_plan(call):

    plans = {
        "10m": ("10 daqiqa", 5000),
        "30m": ("30 daqiqa", 10000),
        "99m": ("99 daqiqa", 20000),
        "2d": ("2 kun", 30000),
        "7d": ("7 kun", 50000),
        "30d": ("30 kun", 100000),
    }

    code = call.data.replace("plan_", "")

    if code not in plans:
        bot.answer_callback_query(
            call.id,
            "Tarif topilmadi!",
            show_alert=True
        )
        return

    name, price = plans[code]

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "💳 To‘lov qildim",
            callback_data=f"payment_{code}"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "⬅️ Orqaga",
            callback_data="vip"
        )
    )

    bot.answer_callback_query(call.id)

    bot.edit_message_text(
        f"💎 <b>{name}</b>\n\n"
        f"💰 Narxi: <b>{price:,} so‘m</b>\n\n"
        "💳 Karta raqami:\n"
        "<code>9860606750247151</code>\n"
        "👤 Abidjanov H\n\n"
        "To‘lovni amalga oshirgach, "
        "pastdagi tugmani bosing.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode="HTML"
    )


# 💳 TO‘LOV QILDIM
@bot.callback_query_handler(
    func=lambda call: call.data.startswith("payment_")
)
def payment(call):

    code = call.data.replace("payment_", "")

    plans = {
        "10m": ("10 daqiqa", 5000),
        "30m": ("30 daqiqa", 10000),
        "99m": ("99 daqiqa", 20000),
        "2d": ("2 kun", 30000),
        "7d": ("7 kun", 50000),
        "30d": ("30 kun", 100000),
    }

    if code not in plans:
        bot.answer_callback_query(
            call.id,
            "Xatolik!",
            show_alert=True
        )
        return

    name, price = plans[code]

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        "✅ <b>Arizangiz yuborildi!</b>\n\n"
        f"💎 Tarif: {name}\n"
        f"💰 Summa: {price:,} so‘m\n\n"
        "⏳ Admin to‘lovni tekshiradi.\n"
        "Tasdiqlangandan keyin VIP avtomatik faollashadi.",
        parse_mode="HTML"
    )


if __name__ == "__main__":

    print("⏳ Database ishga tushmoqda...")

    init_database()

    print("✅ Database tayyor!")
    print("🤖 BOT ISHGA TUSHDI")

    bot.infinity_polling(
        skip_pending=True
  )
