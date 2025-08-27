from aiogram import Dispatcher, types, F, Bot
from keyboards import admin_worker_keyboard, confirm_keyboard
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import save_worker, delete_worker, delete_user, add_blocked, delete_blocked, add_admin, remove_admin


class FeedbackStates(StatesGroup):
    waiting_feedback = State()


async def feedback_worker_callback(
    call: types.CallbackQuery,
    state: FSMContext,
):
    worker_id = int(call.data.split(":")[1])
    await state.set_state(FeedbackStates.waiting_feedback)
    await state.update_data(worker_id=worker_id)
    await call.message.answer("✍️ Feedback yozib yuboring (arizada xato bolsa):")
    await call.answer()


async def feedback_text(
    message: types.Message,
    state: FSMContext,
    workers_db: dict,
    bot: Bot,
    pool
):
    data = await state.get_data()
    worker_id = data.get("worker_id")
    feedback_message = message.text

    if worker_id in workers_db:
        workers_db.pop(worker_id)
        async with pool.acquire() as conn:
            await delete_worker(conn, worker_id)
        try:
            await bot.send_message(
                worker_id,
                f"❌ Sizning arizangiz rad etildi.\n\n📝 Feedback: {feedback_message}"
            )
        except:
            await message.answer(
                "⚠️ Ishchiga feedback yuborib bolmadi (u botni bloklagan bolishi mumkin)"
            )
    else:
        await message.answer("⚠️ Bu ishchi topilmadi")

    await message.answer("✅ Feedback yuborildi va ariza rad etildi")
    await state.clear()


def register_admin_handlers(
    dp: Dispatcher,
    bot: Bot,
    admins: set[int],
    users_db: dict,
    workers_db: dict,
    blocked_users: set,
    pool
):

    dp.callback_query.register(
        feedback_worker_callback,
        F.data.startswith("feedback:")
    )

    async def feedback_handler(message: types.Message, state: FSMContext):
        await feedback_text(message, state, workers_db, bot, pool)

    dp.message.register(feedback_handler, FeedbackStates.waiting_feedback)

    def is_admin(message_or_call) -> bool:
        user_id = message_or_call.from_user.id
        return user_id in admins

    def get_user_status(user_id: int) -> str:
        return "ADMIN👮" if user_id in admins else "USER👤"

    async def show_workers(message: types.Message):
        if not is_admin(message):
            return
        if not workers_db:
            await message.answer("👷 Ishchilar royxati bosh")
            return
        for worker_id, data in workers_db.items():
            user = await bot.get_chat(worker_id)
            text = (
                "👷 Ishchi ma’lumoti\n"
                f"Foydalanuvchi: {user.username or "username yoq"}\n"
                f"Ismi: {data.get("name")}\n"
                f"Telefon: {data.get("phone","N/A")}\n"
                f"Manzil: {data.get("region")}/{data.get("city")}\n"
                f"Kasb: {data.get("profession")}\n"
                f"Status: {"Tasdiqlangan" if data.get("approved") else "Tasdiqlanmagan"}"
            )
            await message.answer(
                text,
                reply_markup=admin_worker_keyboard(worker_id, bool(data.get("approved")))
            )

    async def show_users(message: types.Message):
        if not is_admin(message):
            return

        if not users_db:
            await message.answer("👤 Userlar royxati bosh")
            return


        txt = ["👤 Userlar:"]
        for user_id, data in users_db.items():
            try:
                user = await bot.get_chat(user_id)
                username = f"@{user.username}" if user.username else "username yoq"
                phone = data.get("phone", "N/A")

                txt.append(
                    f"🆔 ID: {user_id}\n"
                    f"👤 {username}\n"
                    f"📞 Tel: {phone}\n"
                    f"♻  Status: {get_user_status(user_id)}\n"
                    "---------------------------------"
                )
            except Exception:
                txt.append(f"🆔 ID: {user_id} — (chatga kira olmadi)")

        await message.answer("\n".join(txt))

    async def block_user(message: types.Message):
        if not is_admin(message):
            return
        try:
            username = message.text.split(" ")[1].lstrip("@").lower()
        except:
            await message.answer("⚠️ Foydalanish: /block <username>")
            return

        blocked_users.add(username)
        async with pool.acquire() as conn:
            await add_blocked(conn, username)

        to_remove = []
        for user_id in list(users_db.keys()):
            try:
                chat = await bot.get_chat(user_id)
                if chat.username and chat.username.lower() == username:
                    to_remove.append(user_id)
            except:
                pass

        for user_id in to_remove:
            users_db.pop(user_id, None)
            async with pool.acquire() as conn:
                await delete_user(conn, user_id)
            if user_id in workers_db:
                workers_db.pop(user_id, None)
                async with pool.acquire() as conn:
                    await delete_worker(conn, user_id)
            try:
                await bot.send_message(user_id, "🚫 Siz admin tomonidan bloklandingiz va botdan foydalana olmaysiz")
            except:
                pass

        await message.answer(f"🚫 User @{username} bloklandi")

    async def show_blocked_users(message: types.Message):
        if not is_admin(message):
            return

        if not blocked_users:
            await message.answer("♻ Bloklangan userlar yoq\n\n"
                                 "Block va Unblock qilish uchun korsatilgani kabi yozing‼️ \n"
                                 "/block username\n"
                                 "/unblock username\n")
            return

        txt = ["♻ Bloklangan userlar:"]
        for username in blocked_users:
            txt.append(f"👤 @{username}")
        await message.answer("\n".join(txt))



    async def unblock_user(message: types.Message):
        if not is_admin(message):
            return
        try:
            username = message.text.split(" ")[1].lstrip("@").lower()
        except:
            await message.answer("⚠️ Foydalanish: /unblock <username>")
            return

        if username in blocked_users:
            blocked_users.remove(username)
            async with pool.acquire() as conn:
                await delete_blocked(conn, username)
            await message.answer(f"✅ User @{username} blokdan chiqarildi")
        else:
            await message.answer("⚠️ Bu user bloklanmagan")


    async def process_worker_actions(call: types.CallbackQuery):
        if not is_admin(call):
            return
        action, wid_str = call.data.split(":")
        worker_id = int(wid_str)
        data = workers_db.get(worker_id)

        if not data:
            await call.answer("Ishchi topilmadi", show_alert=True)
            return

        if action == "approve_worker":
            data["approved"] = True
            async with pool.acquire() as conn:
                await save_worker(conn, worker_id, data)
            await bot.send_message(worker_id, "✅ Admin tasdiqladi. Endi buyurtmalarni qabul qilishingiz mumkin")
            await call.message.edit_text("✅ Ishchi tasdiqlandi")
        elif action == "reject_worker":
            workers_db.pop(worker_id, None)
            async with pool.acquire() as conn:
                await delete_worker(conn, worker_id)
            await bot.send_message(worker_id, "❌ Admin arizangizni rad etdi")
            await call.message.edit_text("❌ Ishchi rad etildi va ochirildi")
        elif action == "fire_worker":
            workers_db.pop(worker_id, None)
            async with pool.acquire() as conn:
                await delete_worker(conn, worker_id)
            await bot.send_message(worker_id, "🗑 Siz ishdan boshatildingiz")
            await call.message.edit_text("🗑 Ishchi ishdan boshatildi")

        await call.answer()

    async def add_admin_cmd(message: types.Message):
        if not is_admin(message):
            return
        try:
            new_admin_id = int(message.text.split(" ")[1])
        except:
            await message.answer("⚠️ Foydalanish: /add_admin <user_id>")
            return
        admins.add(new_admin_id)
        async with pool.acquire() as conn:
            await add_admin(conn, new_admin_id)
        await message.answer(f"✅ Admin {new_admin_id} qoshildi")

    async def remove_admin_cmd(message: types.Message):
        if not is_admin(message):
            return
        try:
            remove_admin_id = int(message.text.split(" ")[1])
        except:
            await message.answer("⚠️ Foydalanish: /remove_admin <user_id>")
            return
        if remove_admin_id in admins:
            admins.remove(remove_admin_id)
            async with pool.acquire() as conn:
                await remove_admin(conn, remove_admin_id)
            await message.answer(f"✅ Admin {remove_admin_id} ochirildi")
        else:
            await message.answer("⚠️ Bu admin topilmadi")

    dp.message.register(show_workers, F.text == "/workers")
    dp.message.register(show_blocked_users, F.text == "/blocked_users")
    dp.message.register(show_users,   F.text == "/users")
    dp.message.register(block_user,   F.text.startswith("/block"))
    dp.message.register(unblock_user, F.text.startswith("/unblock"))
    dp.message.register(add_admin_cmd, F.text.startswith("/add_admin"))
    dp.message.register(remove_admin_cmd, F.text.startswith("/remove_admin"))
    dp.callback_query.register(
        process_worker_actions,
        F.data.startswith(("approve_worker", "reject_worker", "fire_worker"))
    )