import asyncio
import logging
from itertools import count
import asyncpg
import os
import random
import re
import requests
from aiogram import Bot, Dispatcher, F, types
from aiogram.fsm.storage.memory import MemoryStorage
from middlewares import BlockMiddleware
from keyboards import start_keyboard, admin_keyboard, phone_request_keyboard
from admin import register_admin_handlers
from user_panel import register_user_handlers
from workers_panel import register_worker_handlers
from database import create_tables, load_from_db

API_TOKEN = '8372351670:AAH389RletRBd8eNL2v9a5-tfSF-i_4R33c'
DSN = os.getenv("DATABASE_URL")

ESKIZ_EMAIL = "azimjonovislomjon77@gmail.com"  # sizning eskiz email
ESKIZ_PASSWORD = "7sbAXZLjyO7KCLOn6k8ZZYboXU4XpefkAyMeHFVG"  # sizning eskiz parol
ESKIZ_LOGIN_URL = "https://notify.eskiz.uz/api/auth/login"
ESKIZ_SMS_URL = "https://notify.eskiz.uz/api/message/sms/send"
ESKIZ_SENDER = "4546"  # default sender id (4546) yoki sizniki

logging.basicConfig(level=logging.INFO)

pool = None
pending_codes = {}  # user_id: {"phone": str, "code": int}


async def ensure_verification_table(conn):
    await conn.execute("""
                       CREATE TABLE IF NOT EXISTS verified_users
                       (
                           user_id
                           BIGINT
                           PRIMARY
                           KEY,
                           phone
                           TEXT
                       )
                       """)


async def is_user_verified(conn, user_id: int) -> bool:
    row = await conn.fetchrow("SELECT 1 FROM verified_users WHERE user_id=$1", user_id)
    return row is not None


async def save_verified_user(conn, user_id: int, phone: str):
    await conn.execute(
        "INSERT INTO verified_users (user_id, phone) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING",
        user_id, phone
    )


def get_eskiz_token():
    if not ESKIZ_EMAIL or not ESKIZ_PASSWORD:
        raise RuntimeError("Eskiz credentials are not set (ESKIZ_EMAIL/ESKIZ_PASSWORD).")
    resp = requests.post(ESKIZ_LOGIN_URL, data={
        "email": ESKIZ_EMAIL,
        "password": ESKIZ_PASSWORD
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    # structure: {"status": True, "message": "...", "data": {"token": "..." } }
    token = data.get("data", {}).get("token")
    if not token:
        raise RuntimeError("Eskiz token not found in response.")
    return token


def send_sms_eskiz(phone: str, message: str):
    token = get_eskiz_token()
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "mobile_phone": phone,
        "message": message,
        "from": ESKIZ_SENDER
    }
    resp = requests.post(ESKIZ_SMS_URL, headers=headers, data=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def normalize_phone_for_eskiz(raw_phone: str) -> str:
    digits = re.sub(r"\D", "", raw_phone or "")
    if not digits:
        return digits

    if digits.startswith("998"):
        return digits
    if len(digits) == 9 and digits.startswith("9"):
        return "998" + digits
    if digits.startswith("0"):
        stripped = digits.lstrip("0")
        if len(stripped) >= 9:
            return "998" + stripped
    return digits


async def main():
    global pool
    pool = await asyncpg.create_pool(DSN)

    bot = Bot(API_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    pending_users: dict[int, dict] = {}
    pending_workers: dict[int, dict] = {}
    blocked_users: set[int] = set()
    admins: set[int] = set()
    users_db: dict[int, dict] = {}
    workers_db: dict[int, dict] = {}
    orders: dict[int, dict] = {}
    offers: dict[int, dict] = {}
    chosen_orders: set[int] = set()
    order_id_counter = count(1)

    dp.message.middleware(BlockMiddleware(blocked_users))

    async with pool.acquire() as conn:
        await create_tables(conn)
        await ensure_verification_table(conn)
        await load_from_db(
            conn,
            users_db,
            pending_users,
            workers_db,
            pending_workers,
            orders,
            offers,
            chosen_orders,
            blocked_users,
            admins
        )

    async def cmd_start(message: types.Message):
        async with pool.acquire() as conn:
            verified = await is_user_verified(conn, message.from_user.id)

        if not verified:
            await message.answer(
                "Botdan foydalanish uchun telefon raqamingizni yuboring:",
                reply_markup=phone_request_keyboard()
            )
            return

        if message.from_user.id in admins:
            await message.answer(
                '👮 Admin paneliga xush kelibsiz!',
                reply_markup=admin_keyboard()
            )
        else:
            await message.answer(
                """
✅ Assalomu alaykum! ✅
🛠️ UygaXizmatBot 🛠️ ga hush kelibsiz!

Bu bot orqali 🏠 uydan chiqmasdan uyingizga 🛠️ ishchi chaqirishingiz 
yoki uyga 🏃‍♂️ borib xizmat ko‘rsatish uchun 🛠️ ish topishingiz mumkin! ✅

🔹 Agar sizga xizmat ko‘rsatish uchun ishchi kerak bo‘lsa:
👉 Foydalanuvchi

🔹 Agar siz ish qidirayotgan bo‘lsangiz:
👉 Ishchi
""",
                reply_markup=start_keyboard()
            )

    dp.message.register(cmd_start, F.text == '/start')

    async def contact_handler(message: types.Message):
        if not message.contact or not message.contact.phone_number:
            await message.answer("❌ Telefon raqami yuborilmadi. Iltimos, qayta urinib ko‘ring.")
            return

        raw_phone = message.contact.phone_number
        eskiz_phone = normalize_phone_for_eskiz(raw_phone)

        if not eskiz_phone:
            await message.answer("❌ Telefon raqami noto'g'ri formatda. Iltimos tugma orqali qayta yuboring.",
                                 reply_markup=phone_request_keyboard())
            return

        code = random.randint(1000, 9999)
        pending_codes[message.from_user.id] = {"phone": eskiz_phone, "code": code}

        try:
            send_sms_eskiz(eskiz_phone, f"Sizning tasdiqlash kodingiz: {code}")
            await message.answer("✅ SMS yuborildi. Kodni shu yerga kiriting:", reply_markup=types.ReplyKeyboardRemove())
        except requests.HTTPError as e:
            try:
                err_json = e.response.json()
            except Exception:
                err_json = str(e)
            await message.answer(f"❌ SMS yuborishda xatolik: {err_json}")
        except Exception as e:
            await message.answer(f"❌ SMS yuborishda xatolik: {e}")

    dp.message.register(contact_handler, F.contact)

    async def code_handler(message: types.Message):
        if message.from_user.id not in pending_codes:
            return

        try:
            entered = int(message.text.strip())
        except ValueError:
            await message.answer("❌ Faqat 4 xonali kod kiriting.")
            return

        correct = pending_codes[message.from_user.id]["code"]
        phone = pending_codes[message.from_user.id]["phone"]

        if entered == correct:
            async with pool.acquire() as conn:
                await save_verified_user(conn, message.from_user.id, phone)

            del pending_codes[message.from_user.id]
            await message.answer("✅ Telefon raqamingiz muvaffaqiyatli tasdiqlandi!", reply_markup=start_keyboard())
        else:
            await message.answer("❌ Noto‘g‘ri kod. Qayta urinib ko‘ring.")

    dp.message.register(code_handler, F.text.regexp(r"^\d{4}$"))

    register_admin_handlers(
        dp=dp,
        bot=bot,
        admins=admins,
        users_db=users_db,
        workers_db=workers_db,
        blocked_users=blocked_users,
        pool=pool,
        pending_workers=pending_workers,
        pending_users=pending_users
    )

    register_user_handlers(
        dp=dp,
        bot=bot,
        admins=admins,
        users_db=users_db,
        workers_db=workers_db,
        orders=orders,
        offers=offers,
        order_id_counter=order_id_counter,
        pool=pool,
        pending_users=pending_users
    )

    register_worker_handlers(
        dp=dp,
        bot=bot,
        admins=admins,
        workers_db=workers_db,
        offers=offers,
        pool=pool,
        pending_workers=pending_workers
    )

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == '__main__':
    asyncio.run(main())
