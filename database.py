import psycopg2
from config import DATABASE_URL


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def init_database():
    conn = get_connection()
    cur = conn.cursor()

    # 👤 Foydalanuvchilar
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 💎 VIP obunalar
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vip_subscriptions (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            plan_name TEXT NOT NULL,
            starts_at TIMESTAMP,
            expires_at TIMESTAMP,
            active BOOLEAN DEFAULT FALSE
        );
    """)

    # 💳 To‘lov arizalari
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            plan_name TEXT NOT NULL,
            amount BIGINT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 🔎 Qidiruv tarixi
    cur.execute("""
        CREATE TABLE IF NOT EXISTS search_logs (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            query TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 📚 Indekslangan profillar
    cur.execute("""
        CREATE TABLE IF NOT EXISTS indexed_profiles (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            bio TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 💬 Indekslangan ochiq xabarlar
    cur.execute("""
        CREATE TABLE IF NOT EXISTS indexed_messages (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT,
            chat_id BIGINT,
            chat_title TEXT,
            message_id BIGINT,
            message_text TEXT,
            message_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()

    cur.close()
    conn.close()

    print("✅ Database tayyor!")


def save_user(user):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users
        (telegram_id, username, first_name, last_name)
        VALUES (%s, %s, %s, %s)

        ON CONFLICT (telegram_id)
        DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name;
    """, (
        user.id,
        user.username,
        user.first_name,
        user.last_name
    ))

    conn.commit()

    cur.close()
    conn.close()
