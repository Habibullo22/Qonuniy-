from database import get_connection


def index_profile(user):
    """
    Foydalanuvchi bot bilan o'zaro aloqaga kirganda
    uning mavjud Telegram profil ma'lumotlarini bazaga saqlaydi.
    """

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO indexed_profiles
        (
            telegram_id,
            username,
            first_name,
            last_name,
            updated_at
        )
        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)

        ON CONFLICT DO NOTHING;
    """, (
        user.id,
        user.username,
        user.first_name,
        user.last_name
    ))

    # Agar shu Telegram ID oldin mavjud bo'lsa,
    # profil ma'lumotlarini yangilaymiz.
    cur.execute("""
        UPDATE indexed_profiles
        SET
            username = %s,
            first_name = %s,
            last_name = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE telegram_id = %s;
    """, (
        user.username,
        user.first_name,
        user.last_name,
        user.id
    ))

    conn.commit()

    cur.close()
    conn.close()


def index_public_message(
    telegram_id,
    chat_id,
    chat_title,
    message_id,
    message_text,
    message_date
):
    """
    Tizimga qonuniy ravishda kelib tushgan
    ochiq xabarni indekslaydi.
    """

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO indexed_messages
        (
            telegram_id,
            chat_id,
            chat_title,
            message_id,
            message_text,
            message_date
        )
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        telegram_id,
        chat_id,
        chat_title,
        message_id,
        message_text,
        message_date
    ))

    conn.commit()

    cur.close()
    conn.close()
