import asyncio
import logging
from itertools import count
import asyncpg
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.fsm.storage.memory import MemoryStorage
from middlewares import BlockMiddleware
from keyboards import start_keyboard, admin_keyboard
from admin import register_admin_handlers
from user_panel import register_user_handlers
from workers_panel import register_worker_handlers
from database import create_tables, load_from_db


API_TOKEN = '8372351670:AAH389RletRBd8eNL2v9a5-tfSF-i_4R33c'
DSN = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)

pool = None

async def main():
    global pool
    pool = await asyncpg.create_pool(DSN)

    bot = Bot(API_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    blocked_users: set[str] = set()
    dp.message.middleware(BlockMiddleware(blocked_users))

    users_db: dict[int, dict] = {}
    workers_db: dict[int, dict] = {}
    orders: dict[int, dict] = {}
    offers: dict[int, dict] = {}
    chosen_orders: set[int] = set()
    admins: set[int] = set()
    order_id_counter = count(1)

    async with pool.acquire() as conn:
        await create_tables(conn)
        await load_from_db(conn, users_db, workers_db, orders, offers, chosen_orders, blocked_users, admins)

    async def cmd_start(message: types.Message):
        if message.from_user.id in admins:
            await message.answer('👮 Admin paneliga xush kelibsiz!', reply_markup=admin_keyboard())
        else:
            await message.answer('ㅤㅤㅤㅤㅤㅤㅤㅤㅤ ✅Assalomu alaykum!✅\n'
                                 ' ㅤㅤㅤㅤㅤ🛠️UygaXizmatBot🛠️ ga hush kelibisiz!\n\n '
                                 'Bu bot orqali 🏠uydan chiqmasdan uyingizga 🛠️ishchi chaqirishingiz yoki uyga 🏃‍♂️‍➡️borib xizmat ko`rsatish uchun 🛠️ish topishingiz mumkun!✅\n\n '
                                 'ㅤㅤㅤAgar sizga xizmat korsatish uchun ishchi kerak bolsa! \n\n'
                                 'ㅤㅤㅤㅤㅤㅤㅤㅤㅤ👤Foydalanuvchi👤 \n\n'
                                 'ㅤㅤㅤㅤㅤㅤAgar siz ish qidirayotgan bolsangiz! \n\n'
                                 'ㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤㅤ🛠️Ishchi🛠️\n\n '
                                 'tugmasini bosing!✅', reply_markup=start_keyboard())

    dp.message.register(cmd_start, F.text == '/start')


    register_admin_handlers(
        dp=dp,
        bot=bot,
        admins=admins,
        users_db=users_db,
        workers_db=workers_db,
        blocked_users = blocked_users,
        pool=pool
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
        pool=pool
    )

    register_worker_handlers(
        dp=dp,
        bot=bot,
        admins=admins,
        workers_db=workers_db,
        offers=offers,
        pool=pool
    )

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == '__main__':
    asyncio.run(main())