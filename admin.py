from aiogram.types import Message
from aiogram import Dispatcher, types, F, Bot
from keyboards import admin_worker_keyboard, remove_keyboard, cities_keyboard, regions_keyboard, \
    REGIONS, admin_keyboard, target_keyboard, filter_type_keyboard, cancel_keyboard
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import save_worker, delete_worker, add_blocked, delete_blocked, add_admin, remove_admin, \
    delete_pending_worker


class FeedbackStates(StatesGroup):
    waiting_feedback = State()


class AdminStates(StatesGroup):
    select_target = State()
    select_filter_type = State()
    select_region = State()
    select_city = State()
    enter_message = State()
    enter_global_message = State()


async def feedback_worker_callback(
        call: types.CallbackQuery,
        state: FSMContext,
):
    worker_id = int(call.data.split(":")[1])
    await state.set_state(FeedbackStates.waiting_feedback)
    await state.update_data(worker_id=worker_id)
    await call.message.answer(
        "✍️ Feedback yozib yuboring (arizada xato bolsa):",
        reply_markup=cancel_keyboard()
    )
    await call.answer()


async def feedback_text(
        message: types.Message,
        state: FSMContext,
        workers_db: dict,
        pending_workers: dict,
        bot: Bot,
        pool
):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi", reply_markup=admin_keyboard())
        return

    data = await state.get_data()
    worker_id = data.get("worker_id")
    feedback_message = message.text

    if worker_id in workers_db:
        workers_db.pop(worker_id)
        async with pool.acquire() as conn:
            await delete_worker(conn, worker_id)
    elif worker_id in pending_workers:
        pending_workers.pop(worker_id)
        async with pool.acquire() as conn:
            await delete_pending_worker(conn, worker_id)
    else:
        await message.answer("⚠️ Bu ishchi topilmadi")
        await state.clear()
        return

    try:
        await bot.send_message(
            worker_id,
            f"❌ Sizning arizangiz rad etildi.\n\n📝 Feedback: {feedback_message}"
        )
    except:
        await message.answer(
            "⚠️ Ishchiga feedback yuborib bolmadi (u botni bloklagan bolishi mumkin)"
        )

    await message.answer("✅ Feedback yuborildi va ariza rad etildi", reply_markup=admin_keyboard())
    await state.clear()


def register_admin_handlers(
        dp: Dispatcher,
        bot: Bot,
        admins: set[int],
        users_db: dict,
        pending_users: dict,
        workers_db: dict,
        pending_workers: dict,
        blocked_users: set,
        pool
):
    dp.callback_query.register(
        feedback_worker_callback,
        F.data.startswith("feedback:")
    )

    async def feedback_handler(message: types.Message, state: FSMContext):
        await feedback_text(message, state, workers_db, pending_workers, bot, pool)

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
                f"Foydalanuvchi: {user.username or 'username yoq'}\n"
                f"Ismi: {data.get('name')}\n"
                f"Telefon: {data.get('phone', 'N/A')}\n"
                f"Manzil: {data.get('region')}/{data.get('city')}\n"
                f"Kasb: {data.get('profession')}\n"
                f"Status: {'Tasdiqlangan' if data.get('approved') else 'Tasdiqlanmagan'}"
            )
            await message.answer(
                text,
                reply_markup=admin_worker_keyboard(worker_id, bool(data.get("approved")))
            )

    async def show_users(message: Message):
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

        args = message.text.split(" ", 1)
        if len(args) < 2:
            await message.answer("⚠️ Foydalanish: /block <user_id yoki username>")
            return

        identifier = args[1].strip()
        user_id = None
        username = None

        if identifier.isdigit():
            user_id = int(identifier)
        else:
            username = identifier.lstrip("@").lower()

        if username:
            for uid, data in users_db.items():
                if data.get("username", "").lower() == username:
                    user_id = uid
                    break
            if not user_id:
                for uid, data in pending_users.items():
                    if data.get("username", "").lower() == username:
                        user_id = uid
                        break
            if not user_id:
                for worker_id, data in workers_db.items():
                    if data.get("username", "").lower() == username:
                        user_id = worker_id
                        break
            if not user_id:
                for worker_id, data in pending_workers.items():
                    if data.get("username", "").lower() == username:
                        user_id = worker_id
                        break

        if user_id:
            users_db.pop(user_id, None)
            pending_users.pop(user_id, None)
            workers_db.pop(user_id, None)
            pending_workers.pop(user_id, None)

        async with pool.acquire() as conn:
            await add_blocked(conn, user_id or username)

        blocked_users.add(user_id if user_id else username)

        if user_id:
            try:
                await bot.send_message(
                    user_id,
                    "🚫 Siz admin tomonidan bloklandingiz va botdan foydalana olmaysiz"
                )
            except:
                pass

        await message.answer(f"🚫 Foydalanuvchi {'@' + username if username else user_id} bloklandi")

    async def show_blocked_users(message: types.Message):
        if not is_admin(message):
            return

        if not blocked_users:
            await message.answer(
                "♻ Bloklangan userlar yo'q\n\n"
                "Block va Unblock qilish uchun:\n"
                "/block username yoki user_id\n"
                "/unblock username yoki user_id\n"
            )
            return

        txt = ["♻ Bloklangan userlar:"]
        async with pool.acquire() as conn:
            for identifier in blocked_users:
                user_id = None
                username = None
                user_data = None

                if isinstance(identifier, int):
                    user_id = identifier
                else:
                    username = identifier.lstrip("@").lower()

                if user_id and user_id in users_db:
                    user_data = users_db[user_id]
                elif user_id and user_id in pending_users:
                    user_data = pending_users[user_id]
                elif user_id and user_id in workers_db:
                    user_data = workers_db[user_id]
                elif user_id and user_id in pending_workers:
                    user_data = pending_workers[user_id]
                elif username:
                    for db in [users_db, pending_users, workers_db, pending_workers]:
                        for uid, data in db.items():
                            if data.get("username", "").lower() == username:
                                user_id = uid
                                user_data = data
                                break
                        if user_data:
                            break

                if not user_data:
                    for table in ['users', 'pending_users', 'workers', 'pending_workers']:
                        id_field = 'user_id' if 'user' in table else 'worker_id'
                        row = await conn.fetchrow(f"SELECT * FROM {table} WHERE lower(username)=$1", username)
                        if row:
                            user_id = row[id_field]
                            user_data = dict(row)
                            break
                        row = await conn.fetchrow(f"SELECT * FROM {table} WHERE {id_field}=$1", user_id)
                        if row:
                            user_data = dict(row)
                            break

                if not user_data:
                    try:
                        chat = await bot.get_chat(user_id or f"@{username}")
                        user_data = {
                            "phone": "Noma’lum",
                            "region": "Noma’lum",
                            "city": "Noma’lum",
                            "username": chat.username or username
                        }
                        user_id = chat.id
                    except Exception:
                        user_data = {
                            "phone": "Noma’lum",
                            "region": "Noma’lum",
                            "city": "Noma’lum",
                            "username": username
                        }

                display = f"@{user_data.get('username')}" if user_data.get('username') else f"{user_id}"

                txt.append(
                    f"👤 {display}\n"
                    f"ID: {user_id}\n"
                    f"Tel: {user_data.get('phone', 'Noma’lum')}\n"
                    f"Viloyat/Shahar: {user_data.get('region', 'Noma’lum')}/{user_data.get('city', 'Noma’lum')}\n"
                    "---------------------------------"
                )

        await message.answer("\n".join(txt))

    async def unblock_user(message: types.Message):
        if not is_admin(message):
            return

        args = message.text.split(" ", 1)
        if len(args) < 2:
            await message.answer("⚠️ Foydalanish: /unblock <user_id yoki username>")
            return

        identifier = args[1].strip()
        user_id = None
        username = None
        target = None

        async with pool.acquire() as conn:
            if identifier.isdigit():
                user_id = int(identifier)
                if user_id in blocked_users:
                    target = user_id
            else:
                username = identifier.lstrip("@").lower()
                if username in blocked_users:
                    target = username
                else:
                    for table in ['users', 'pending_users', 'workers', 'pending_workers']:
                        id_field = 'user_id' if 'user' in table else 'worker_id'
                        row = await conn.fetchrow(f"SELECT {id_field} FROM {table} WHERE lower(username)=$1", username)
                        if row:
                            user_id = row[id_field]
                            break
                    if user_id and user_id in blocked_users:
                        target = user_id

            if target is None:
                await message.answer("⚠️ Bu foydalanuvchi bloklanmagan")
                return

            blocked_users.remove(target)
            await delete_blocked(conn, target)

            if user_id is None and username:
                for table in ['users', 'pending_users', 'workers', 'pending_workers']:
                    id_field = 'user_id' if 'user' in table else 'worker_id'
                    row = await conn.fetchrow(f"SELECT * FROM {table} WHERE lower(username)=$1", username)
                    if row:
                        user_id = row[id_field]
                        if 'user' in table:
                            if table == 'users':
                                users_db[user_id] = dict(row)
                            else:
                                pending_users[user_id] = dict(row)
                        else:
                            if table == 'workers':
                                workers_db[user_id] = dict(row)
                            else:
                                pending_workers[user_id] = dict(row)
                        break
            elif user_id:
                for table in ['users', 'pending_users', 'workers', 'pending_workers']:
                    id_field = 'user_id' if 'user' in table else 'worker_id'
                    row = await conn.fetchrow(f"SELECT * FROM {table} WHERE {id_field}=$1", user_id)
                    if row:
                        if 'user' in table:
                            if table == 'users':
                                users_db[user_id] = dict(row)
                            else:
                                pending_users[user_id] = dict(row)
                        else:
                            if table == 'workers':
                                workers_db[user_id] = dict(row)
                            else:
                                pending_workers[user_id] = dict(row)
                        break

        await message.answer(f"✅ Foydalanuvchi {'@' + username if username else user_id} blokdan chiqarildi")

    async def process_worker_actions(call: types.CallbackQuery):
        if not is_admin(call):
            return
        action, worker_id_str = call.data.split(":")
        worker_id = int(worker_id_str)
        data = workers_db.get(worker_id) or pending_workers.get(worker_id)

        if not data:
            await call.answer("Ishchi topilmadi", show_alert=True)
            return

        if action == "approve_worker":
            if worker_id not in pending_workers:
                await call.answer("Allaqachon tasdiqlangan yoki topilmadi", show_alert=True)
                return
            data = pending_workers.pop(worker_id)
            data["approved"] = True
            workers_db[worker_id] = data
            async with pool.acquire() as conn:
                await save_worker(conn, worker_id, data)
                await delete_pending_worker(conn, worker_id)
            await bot.send_message(worker_id, "✅ Admin tasdiqladi. Endi buyurtmalarni qabul qilishingiz mumkin")
            await call.message.edit_text("✅ Ishchi tasdiqlandi")
        elif action == "reject_worker":
            if worker_id in pending_workers:
                pending_workers.pop(worker_id)
                async with pool.acquire() as conn:
                    await delete_pending_worker(conn, worker_id)
                await bot.send_message(worker_id, "❌ Admin arizangizni rad etdi")
                await call.message.edit_text("❌ Ishchi rad etildi va ochirildi")
            else:
                await call.answer("Arizachi topilmadi", show_alert=True)
                return
        elif action == "fire_worker":
            if worker_id in workers_db:
                workers_db.pop(worker_id)
                async with pool.acquire() as conn:
                    await delete_worker(conn, worker_id)
                await bot.send_message(worker_id, "🗑 Siz ishdan boshatildingiz")
                await call.message.edit_text("🗑 Ishchi ishdan boshatildi")
            else:
                await call.answer("Ishchi topilmadi", show_alert=True)
                return

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

    async def message_to_all_start(message: types.Message, state: FSMContext):
        if not is_admin(message):
            return
        await message.answer("Kimga habar yubormoqchisiz?", reply_markup=target_keyboard())
        await state.set_state(AdminStates.select_target)

    async def on_select_target(message: types.Message, state: FSMContext):
        if message.text == "❌ Bekor qilish":
            await state.clear()
            await message.answer("❌ Bekor qilindi", reply_markup=admin_keyboard())
            return
        if message.text == "🔙 Orqaga":
            await state.clear()
            await message.answer("❌ Bekor qilindi", reply_markup=admin_keyboard())
            return
        if message.text not in ["👤 Userlarga", "👷 Ishchilarga"]:
            await message.answer("⚠️ Ro'yxatdan tanlang", reply_markup=target_keyboard())
            return
        await state.update_data(target=message.text)
        await message.answer("Qanday tanlov bo'yicha?", reply_markup=filter_type_keyboard())
        await state.set_state(AdminStates.select_filter_type)

    async def on_select_filter_type(message: types.Message, state: FSMContext):
        if message.text == "❌ Bekor qilish":
            await state.clear()
            await message.answer("❌ Bekor qilindi", reply_markup=admin_keyboard())
            return
        if message.text == "🔙 Orqaga":
            await state.set_state(AdminStates.select_target)
            await message.answer("Kimga habar yubormoqchisiz?", reply_markup=target_keyboard())
            return
        if message.text not in ["🌆 Viloyat bo'yicha", "🏙 Shahar bo'yicha"]:
            await message.answer("⚠️ Ro'yxatdan tanlang", reply_markup=filter_type_keyboard())
            return
        await state.update_data(filter_type=message.text)
        await message.answer("🌆 Viloyatni tanlang:", reply_markup=regions_keyboard())
        await state.set_state(AdminStates.select_region)

    async def on_select_region(message: types.Message, state: FSMContext):
        if message.text == "❌ Bekor qilish":
            await state.clear()
            await message.answer("❌ Bekor qilindi", reply_markup=admin_keyboard())
            return
        if message.text == "🔙 Orqaga":
            await state.set_state(AdminStates.select_filter_type)
            await message.answer("Qanday tanlov bo'yicha?", reply_markup=filter_type_keyboard())
            return
        if message.text not in REGIONS:
            await message.answer("⚠️ Ro'yxatdan viloyatni tanlang", reply_markup=regions_keyboard())
            return
        await state.update_data(region=message.text)
        data = await state.get_data()
        if data.get("filter_type") == "🏙 Shahar bo'yicha":
            await message.answer("🏙 Shaharni tanlang:", reply_markup=cities_keyboard(message.text))
            await state.set_state(AdminStates.select_city)
        else:
            await message.answer("✍️ Habar matnini kiriting:", reply_markup=remove_keyboard())
            await state.set_state(AdminStates.enter_message)

    async def on_select_city(message: types.Message, state: FSMContext):
        data = await state.get_data()
        region = data.get("region")
        if message.text == "❌ Bekor qilish":
            await state.clear()
            await message.answer("❌ Bekor qilindi", reply_markup=admin_keyboard())
            return
        if message.text == "🔙 Orqaga":
            await state.set_state(AdminStates.select_region)
            await message.answer("🌆 Viloyatni tanlang:", reply_markup=regions_keyboard())
            return
        if message.text not in (REGIONS.get(region) or []):
            await message.answer("⚠️ Ro'yxatdan shaharni tanlang", reply_markup=cities_keyboard(region))
            return
        await state.update_data(city=message.text)
        await message.answer("✍️ Habar matnini kiriting:", reply_markup=remove_keyboard())
        await state.set_state(AdminStates.enter_message)

    async def on_enter_message(message: types.Message, state: FSMContext):
        data = await state.get_data()
        target = data.get("target")
        filter_type = data.get("filter_type")
        region = data.get("region")
        city = data.get("city")
        message_text = message.text.strip()

        targeted_users = set()
        if target == "👤 Userlarga":
            db = users_db
        else:
            db = workers_db

        for uid, udata in db.items():
            if filter_type == "🌆 Viloyat bo'yicha":
                if udata.get('region') == region:
                    targeted_users.add(uid)
            else:
                if udata.get('region') == region and udata.get('city') == city:
                    targeted_users.add(uid)

        sent_count = 0
        for user_id in targeted_users:
            try:
                await bot.send_message(user_id, message_text)
                sent_count += 1
            except:
                pass

        await message.answer(f"✅ Habar {sent_count} ta foydalanuvchiga yuborildi.", reply_markup=admin_keyboard())
        await state.clear()

    async def broadcast_start(message: types.Message, state: FSMContext):
        if not is_admin(message):
            return
        await message.answer(
            "✍️ Barcha user va ishchilarga yuboriladigan habar matnini kiriting:",
            reply_markup=cancel_keyboard()
        )
        await state.set_state(AdminStates.enter_global_message)

    async def on_enter_global_message(message: types.Message, state: FSMContext):
        if message.text == "❌ Bekor qilish":
            await state.clear()
            await message.answer("❌ Bekor qilindi", reply_markup=admin_keyboard())
            return

        message_text = message.text.strip()

        targeted_users = set(users_db.keys()) | set(workers_db.keys())

        sent_count = 0
        for user_id in targeted_users:
            try:
                await bot.send_message(user_id, message_text)
                sent_count += 1
            except:
                pass

        await message.answer(f"✅ Habar {sent_count} ta foydalanuvchiga yuborildi.", reply_markup=admin_keyboard())
        await state.clear()

    dp.message.register(show_workers, F.text == "Barcha ishchilar")
    dp.message.register(show_blocked_users, F.text == "🚷Bloklangan userlar")
    dp.message.register(show_users, F.text == "👤Barcha userlar")
    dp.message.register(block_user, F.text.startswith("/block"))
    dp.message.register(unblock_user, F.text.startswith("/unblock"))
    dp.message.register(add_admin_cmd, F.text.startswith("/add_admin"))
    dp.message.register(remove_admin_cmd, F.text.startswith("/remove_admin"))
    dp.message.register(message_to_all_start, F.text == "📣Tanlab habar yuborish")
    dp.message.register(broadcast_start, F.text == "📣Barchaga habar yuborish")
    dp.message.register(on_select_target, AdminStates.select_target)
    dp.message.register(on_select_filter_type, AdminStates.select_filter_type)
    dp.message.register(on_select_region, AdminStates.select_region)
    dp.message.register(on_select_city, AdminStates.select_city)
    dp.message.register(on_enter_message, AdminStates.enter_message)
    dp.message.register(on_enter_global_message, AdminStates.enter_global_message)
    dp.callback_query.register(
        process_worker_actions,
        F.data.startswith(("approve_worker", "reject_worker", "fire_worker"))
    )
