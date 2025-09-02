# user_panel.py
from aiogram import Dispatcher, F
from aiogram.types import Message, CallbackQuery, ContentType, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, \
    InputMediaDocument
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import StateFilter
from keyboards import (
    start_keyboard, phone_request_keyboard, regions_keyboard, cities_keyboard, services_keyboard,
    location_request_keyboard, confirm_keyboard, remove_keyboard, skip_keyboard,
    REGIONS, SERVICES, worker_actions_keyboard, admin_user_keyboard, choose_worker_keyboard,
    location_button, choose_time_keyboard
)
from database import save_user, save_order, update_order


class UserOrder(StatesGroup):
    contact = State()
    name = State()
    region = State()
    city = State()
    service = State()
    description = State()
    time = State()
    media = State()
    budget = State()
    location = State()
    confirm = State()

class AdminFeedback(StatesGroup):
    writing = State()


def _safe_username(obj: Message | CallbackQuery) -> str:
    return obj.from_user.username or "username yoq"


def register_user_handlers(
        dp: Dispatcher,
        bot,
        admins: set[int],
        users_db: dict,
        workers_db: dict,
        orders: dict,
        offers: dict,
        order_id_counter,
        pool
):

    async def on_user_entry(message: Message, state: FSMContext):
        await message.answer("📱 Iltimos, telefon raqamingizni yuboring:", reply_markup=phone_request_keyboard())
        await state.set_state(UserOrder.contact)
    dp.message.register(on_user_entry, F.text.in_({"/start", "👤 Foydalanuvchi"}))

    async def on_user_contact(message: Message, state: FSMContext):
        if not message.contact:
            await message.answer("⚠️ Tugma orqali telefon raqam yuboring", reply_markup=phone_request_keyboard())
            return
        users_db[message.from_user.id] = {
            "phone": message.contact.phone_number,
            "username": message.from_user.username
        }
        async with pool.acquire() as conn:
            await save_user(conn, message.from_user.id, users_db[message.from_user.id])
        await message.answer("✍️ Ism-familiyangizni yozing:", reply_markup=remove_keyboard())
        await state.set_state(UserOrder.name)
    dp.message.register(on_user_contact, F.content_type == ContentType.CONTACT, StateFilter(UserOrder.contact))

    async def on_user_name(message: Message, state: FSMContext):
        await state.update_data(name=message.text.strip())
        await message.answer("🌆 Viloyatni tanlang:", reply_markup=regions_keyboard())
        await state.set_state(UserOrder.region)
    dp.message.register(on_user_name, StateFilter(UserOrder.name))

    async def on_user_region(message: Message, state: FSMContext):
        if message.text == "❌ Bekor qilish":
            await state.clear()
            await message.answer("❌ Bekor qilindi", reply_markup=start_keyboard())
            return
        if message.text == "🔙 Orqaga":
            await state.set_state(UserOrder.name)
            await message.answer("✍️ Ism-familiyangizni yozing:", reply_markup=remove_keyboard())
            return
        if message.text not in REGIONS:
            await message.answer("⚠️ Royxatdan viloyat tanlang", reply_markup=regions_keyboard())
            return
        await state.update_data(region=message.text)
        users_db[message.from_user.id]['region'] = message.text
        async with pool.acquire() as conn:
            await save_user(conn, message.from_user.id, users_db[message.from_user.id])
        await message.answer("🏙 Shaharni tanlang:", reply_markup=cities_keyboard(message.text))
        await state.set_state(UserOrder.city)
    dp.message.register(on_user_region, StateFilter(UserOrder.region))

    async def on_user_city(message: Message, state: FSMContext):
        data = await state.get_data()
        region = data.get("region")
        if message.text == "❌ Bekor qilish":
            await state.clear()
            await message.answer("❌ Bekor qilindi", reply_markup=start_keyboard())
            return
        if message.text == "🔙 Orqaga":
            await state.set_state(UserOrder.region)
            await message.answer("🌆 Viloyatni tanlang:", reply_markup=regions_keyboard())
            return
        if message.text not in (REGIONS.get(region) or []):
            await message.answer("⚠️ Royxatdan shahar tanlang", reply_markup=cities_keyboard(region))
            return
        await state.update_data(city=message.text)
        users_db[message.from_user.id]['city'] = message.text
        async with pool.acquire() as conn:
            await save_user(conn, message.from_user.id, users_db[message.from_user.id])
        await message.answer("🛠 Xizmat turini tanlang:", reply_markup=services_keyboard())
        await state.set_state(UserOrder.service)
    dp.message.register(on_user_city, StateFilter(UserOrder.city))

    async def on_user_service(message: Message, state: FSMContext):
        if message.text == "❌ Bekor qilish":
            await state.clear()
            await message.answer("❌ Bekor qilindi", reply_markup=start_keyboard())
            return
        if message.text == "🔙 Orqaga":
            data = await state.get_data()
            await state.set_state(UserOrder.city)
            await message.answer("🏙 Shaharni tanlang:", reply_markup=cities_keyboard(data.get("region")))
            return
        if message.text not in SERVICES:
            await message.answer("⚠️ Royxatdan xizmat turini tanlang", reply_markup=services_keyboard())
            return
        await state.update_data(service=message.text)
        await message.answer("📝 Nima ish qilinishi kerakligini batafsil yozing:", reply_markup=remove_keyboard())
        await state.set_state(UserOrder.description)
    dp.message.register(on_user_service, StateFilter(UserOrder.service))

    async def on_user_description(message: Message, state: FSMContext):
        await state.update_data(description=message.text.strip())
        await message.answer("🕒Ishchi ishni qachondan boshlashi kerak?", reply_markup=choose_time_keyboard())
        await state.set_state(UserOrder.time)
    dp.message.register(on_user_description, StateFilter(UserOrder.description))

    async def on_user_time_choice(callback: CallbackQuery, state: FSMContext):
        if not callback.data.startswith("time:"):
            return
        time_choice = callback.data.split(":")[1]
        await state.update_data(time=time_choice)
        await callback.message.answer("📸 Rasm yoki 🎥 video yuboring (ixtiyoriy, hajmi 15 MB dan oshmasin):", reply_markup=skip_keyboard())
        await state.set_state(UserOrder.media)
        await callback.answer()
    dp.callback_query.register(on_user_time_choice, StateFilter(UserOrder.time), F.data.startswith("time:"))

    MAX_FILES = 2

    async def on_user_media(message: Message, state: FSMContext):
        data = await state.get_data()
        media_list = data.get("media", [])

        if message.text == "⏭ Otkazib yuborish":
            await state.update_data(media=media_list[:MAX_FILES])
            await state.set_state(UserOrder.budget)
            await message.answer("💵 Qancha pul berishga tayyorsiz? (faqat raqam)", reply_markup=remove_keyboard())
            return

        if len(media_list) >= MAX_FILES:
            await message.answer("✅ Maksimal 2 ta fayl qabul qilindi. Endi davom etamiz.")
            return

        file_size, file_id, media_type = None, None, None

        if message.photo:
            file_size = message.photo[-1].file_size
            file_id = message.photo[-1].file_id
            media_type = "photo"
        elif message.video:
            file_size = message.video.file_size
            file_id = message.video.file_id
            media_type = "video"
        else:
            await message.answer("⚠️ Faqat rasm yoki video yuboring yoki ⏭ tugmasi bilan davom eting.")
            return

        if file_size > 15 * 1024 * 1024:
            await message.answer("⚠️ Fayl hajmi 15 MB dan oshmasligi kerak.")
            return

        media_list.append({"type": media_type, "file_id": file_id})
        await state.update_data(media=media_list)

        if len(media_list) < MAX_FILES:
            await message.answer(
                f"📸 {len(media_list)} ta fayl saqlandi. Yana yuborishingiz mumkin yoki ⏭ tugmasi bilan davom eting.",
                reply_markup=skip_keyboard(),
            )
        else:
            await message.answer("✅ Maksimal 2 ta fayl qabul qilindi. Endi davom etamiz.")
            await state.set_state(UserOrder.budget)
            await message.answer("💵 Qancha pul berishga tayyorsiz? (faqat raqam)", reply_markup=remove_keyboard())

    dp.message.register(on_user_media, StateFilter(UserOrder.media))

    async def on_user_budget(message: Message, state: FSMContext):
        if not message.text.isdigit():
            await message.answer("⚠️ Faqat raqam kiriting (masalan: 150000)")
            return
        await state.update_data(budget=int(message.text))
        await message.answer("📍 Iltimos, lokatsiyani yuboring:", reply_markup=location_request_keyboard())
        await state.set_state(UserOrder.location)
    dp.message.register(on_user_budget, StateFilter(UserOrder.budget))

    async def on_user_location(message: Message, state: FSMContext):
        data = await state.get_data()

        if message.text == "Boshqa lokatsiya yuborish":
            await message.answer(
                "📍 Iltimos, boshqa lokatsiyani yuboring.\n"
                "Telegram orqali lokatsiyani yuborish uchun 📎 tugmasini bosing va 'Location' ni tanlang.",
                reply_markup=location_request_keyboard()
            )
            await state.set_state(UserOrder.location)
            return

        if not message.location:
            await message.answer(
                "⚠️ Iltimos, GPS tugmasini bosib yoki 📎 orqali lokatsiyani yuboring.",
                reply_markup=location_request_keyboard()
            )
            return

        latitude = message.location.latitude
        longitude = message.location.longitude
        await state.update_data(location=(latitude, longitude))

        summary = (
            "📦 Buyurtma ma’lumoti:\n"
            f"👤FIO: {data.get('name', 'N/A')}\n"
            f"📞Telefon: (tanlangandan keyin beriladi)\n"
            f"📍Manzil: {data.get('region', 'N/A')} / {data.get('city', 'N/A')}\n"
            f"🛠️Xizmat: {data.get('service', 'N/A')}\n"
            f"💭Tavsif: {data.get('description', 'N/A')}\n"
            f"🕒Vaqt: {data.get('time', 'N/A')}\n"
            f"💵Budjet: {data.get('budget', 'N/A')} som\n"
        )

        markup = location_button(latitude, longitude)

        await message.answer(summary, reply_markup=markup)
        await message.answer("Yuborilsinmi?", reply_markup=confirm_keyboard())
        await state.set_state(UserOrder.confirm)

    dp.message.register(on_user_location, F.content_type == ContentType.LOCATION, StateFilter(UserOrder.location))

    async def on_user_confirm(message: Message, state: FSMContext):
        if message.text == "❌ Bekor qilish":
            await state.clear()
            await message.answer("❌ Bekor qilindi", reply_markup=start_keyboard())
            return

        if message.text != "✅ Yuborish":
            await message.answer(
                "⚠️ ✅ Yuborish yoki ❌ Bekor qilish ni tanlang.",
                reply_markup=confirm_keyboard()
            )
            return

        order_id = next(order_id_counter)
        data = await state.get_data()
        orders[order_id] = {
            "order_id": order_id,
            "user_id": message.from_user.id,
            "username": message.from_user.username,
            "name": data["name"],
            "region": data["region"],
            "city": data["city"],
            "service": data["service"],
            "description": data["description"],
            "time": data["time"],
            "budget": data["budget"],
            "location": data["location"],
            "chosen_worker": None,
            "workers_accepted": set(),
            "media": data.get("media")
        }

        async with pool.acquire() as conn:
            await save_order(conn, order_id, orders[order_id])

        offers[order_id] = {}


        for admin_id in admins:
            user_phone = users_db.get(message.from_user.id, {}).get("phone", "N/A")
            text = (
                "📢 Yangi buyurtma (kuzatuv):\n"
                f"👤User: @{_safe_username(message)}\n"
                f"📍Hudud: {data['region']} / {data['city']}\n"
                f"🛠️Xizmat: {data['service']}\n"
                f"💭Tavsif: {data['description']}\n"
                f"🕒Vaqt: {data['time']}\n"
                f"💵Budjet: {data['budget']} som\n"
                f"📞Nomer: {user_phone}\n"
            )
            markup = location_button(data["location"][0], data["location"][1])

            media_list = orders[order_id].get("media")

            if media_list and isinstance(media_list, list) and len(media_list) > 1:
                album = []
                for i, m in enumerate(media_list):
                    if m["type"] == "photo":
                        album.append(InputMediaPhoto(media=m["file_id"], caption=text if i == 0 else None))
                    elif m["type"] == "video":
                        album.append(InputMediaVideo(media=m["file_id"], caption=text if i == 0 else None))
                    elif m["type"] == "document":
                        album.append(InputMediaDocument(media=m["file_id"], caption=text if i == 0 else None))

                if album:
                    await bot.send_media_group(admin_id, album)
                    await bot.send_message(admin_id, "📍 Buyurtma joylashuvi:", reply_markup=markup)
                else:
                    await bot.send_message(admin_id, text, reply_markup=markup)


            elif media_list and len(media_list) == 1:
                m = media_list[0]
                if m["type"] == "photo":
                    await bot.send_photo(admin_id, m["file_id"], caption=text, reply_markup=markup)
                elif m["type"] == "video":
                    await bot.send_video(admin_id, m["file_id"], caption=text, reply_markup=markup)
                elif m["type"] == "document":
                    await bot.send_document(admin_id, m["file_id"], caption=text, reply_markup=markup)
                else:
                    await bot.send_message(admin_id, text, reply_markup=markup)

            else:

                await bot.send_message(admin_id, text, reply_markup=markup)

            await bot.send_message(admin_id, "Amalni tanlang:", reply_markup=admin_user_keyboard(order_id))

        await message.answer("✅ Buyurtmangiz admin tasdiqlashiga yuborildi.", reply_markup=start_keyboard())
        await state.clear()

    dp.message.register(on_user_confirm, StateFilter(UserOrder.confirm))

    async def stop_any(message: Message, state: FSMContext):
        await state.clear()
        await message.answer("⛔ Bekor qilindi", reply_markup=start_keyboard())
    dp.message.register(stop_any, F.text == "/stop")

    async def on_admin_action(callback: CallbackQuery, state: FSMContext):
        data = callback.data
        if not data.startswith("admin_"):
            return

        order_id = int(data.split(":")[1])
        order = orders.get(order_id)
        if not order:
            await callback.answer("❌ Buyurtma topilmadi", show_alert=True)
            return

        if data.startswith("admin_feedback"):
            await state.update_data(order_id=order_id)
            await callback.message.answer("✍️ Iltimos, fikr-mulohazangizni yozing:")
            await state.set_state(AdminFeedback.writing)
            await callback.answer()
            return

        elif data.startswith("admin_approve"):
            matched_workers = [
                (worker_id, worker) for worker_id, worker in workers_db.items()
                if worker.get("approved") and
                   worker.get("region") == order["region"] and
                   worker.get("city") == order["city"] and
                   worker.get("profession") == order["service"]
            ]
            if not matched_workers:
                await bot.send_message(order["user_id"],
                                       "⚠️ Sizning buyurtmangiz tasdiqlandi, ammo hozircha ishchi topilmadi")
            else:
                notif_text = (
                    f"🆕 Yangi buyurtma!\n"
                    f"📍Hudud: {order['region']} / {order['city']}\n"
                    f"🛠️Xizmat: {order['service']}\n"
                    f"💭Tavsif: {order['description']}\n"
                    f"🕒Vaqt: {order['time']}\n"
                    f"💵Budjet: {order['budget']} som\n"
                    f"👤Buyurtmachi: {order['name']}\n"
                )
                location_markup = location_button(order["location"][0], order["location"][1])
                action_markup = worker_actions_keyboard(order_id)
                full_markup = InlineKeyboardMarkup(inline_keyboard=action_markup.inline_keyboard + location_markup.inline_keyboard)
                for worker_id, _w in matched_workers:
                    if order.get("media"):
                        media_list = order["media"]

                        if len(media_list) > 1:
                            album = []
                            for i, m in enumerate(media_list):
                                caption = notif_text if i == 0 else None
                                if m["type"] == "photo":
                                    album.append(InputMediaPhoto(media=m["file_id"], caption=caption))
                                elif m["type"] == "video":
                                    album.append(InputMediaVideo(media=m["file_id"], caption=caption))
                                elif m["type"] == "document":
                                    album.append(InputMediaDocument(media=m["file_id"], caption=caption))

                            if album:
                                await bot.send_media_group(worker_id, album)
                                await bot.send_message(worker_id, "📍 Joylashuvi:", reply_markup=full_markup)

                        else:  # Faqat 1 ta fayl bolsa
                            m = media_list[0]
                            if m["type"] == "photo":
                                await bot.send_photo(worker_id, m["file_id"], caption=notif_text,
                                                     reply_markup=full_markup)
                            elif m["type"] == "video":
                                await bot.send_video(worker_id, m["file_id"], caption=notif_text,
                                                     reply_markup=full_markup)
                            elif m["type"] == "document":
                                await bot.send_document(worker_id, m["file_id"], caption=notif_text,
                                                        reply_markup=full_markup)
                            else:
                                await bot.send_message(worker_id, notif_text, reply_markup=full_markup)

                    else:
                        await bot.send_message(worker_id, notif_text, reply_markup=full_markup)
                await bot.send_message(order["user_id"], "✅ Buyurtmangiz tasdiqlandi va ishchilarga yuborildi")
            await callback.answer("✅ Buyurtma ishchilarga yuborildi", show_alert=True)

        elif data.startswith("admin_reject"):
            await bot.send_message(order["user_id"], "❌ Sizning buyurtmangiz admin tomonidan rad etildi")
            orders.pop(order_id, None)
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM orders WHERE order_id=$1", order_id)
            await callback.answer("❌ Buyurtma rad etildi", show_alert=True)

    async def on_admin_feedback_text(message: Message, state: FSMContext):
        data = await state.get_data()
        order_id = data.get("order_id")
        order = orders.get(order_id)
        if not order:
            await message.answer("❌ Buyurtma topilmadi")
            await state.clear()
            return

        await bot.send_message(
            order["user_id"],
            f"❌ Sizning buyurtmangiz admin tomonidan rad etildi.\n\n📝 Admin izohi:\n{message.text}"
        )

        orders.pop(order_id, None)
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM orders WHERE order_id=$1", order_id)

        await message.answer("✅ Feedback yuborildi va buyurtma rad etildi")
        await state.clear()

    dp.callback_query.register(on_admin_action, F.data.startswith("admin_"))
    dp.message.register(on_admin_feedback_text, StateFilter(AdminFeedback.writing))

    async def on_worker_accept(callback: CallbackQuery, state: FSMContext):
        if not callback.data.startswith("w:accept:"):
            return
        order_id = int(callback.data.split(":")[2])
        worker_id = callback.from_user.id

        order = orders.get(order_id)
        if not order or order.get("chosen_worker"):
            await callback.answer("❌ Bu buyurtma allaqachon tanlangan", show_alert=True)
            return

        worker = workers_db.get(worker_id)
        if not worker:
            await callback.answer("❌ Siz royxatdan otmagansiz", show_alert=True)
            return

        price = offers.get(order_id, {}).get(worker_id) or order["budget"]

        order["workers_accepted"].add(worker_id)

        text = (
            f"👷 Ishchi buyurtmangizni qabul qildi!\n\n"
            f"👤 Ism: {worker['name']}\n"
            f"📍 Hudud: {worker['region']}, {worker['city']}\n"
            f"🔧 Kasb: {worker['profession']}\n"
            f"💰 Taklif narxi: {price} som\n"
        )
        await bot.send_message(
            order["user_id"],
            text,
            reply_markup=choose_worker_keyboard(worker_id, order_id, str(price))
        )

        for admin_id in admins:
            await bot.send_message(
                admin_id,
                f"📢 Ishchi @{worker.get('username', 'yoq')} buyurtma #{order_id} ni qabul qildi"
            )

        await callback.answer("✅ Buyurtma qabul qilindi")

    dp.callback_query.register(on_worker_accept, F.data.startswith("w:accept:"))

    async def on_user_choose_worker(callback: CallbackQuery, state: FSMContext):
        if not callback.data.startswith("choose:"):
            return
        _, worker_id_str, order_id_str = callback.data.split(":")
        worker_id = int(worker_id_str)
        order_id = int(order_id_str)

        order = orders.get(order_id)
        if not order or order.get("chosen_worker"):
            await callback.answer("❌ Allaqachon tanlangan", show_alert=True)
            return

        worker = workers_db.get(worker_id)
        if not worker:
            await callback.answer("❌ Ma’lumot topilmadi", show_alert=True)
            return

        user_id = order["user_id"]
        user = users_db.get(user_id)
        if not user:
            await callback.answer("❌ Foydalanuvchi ma’lumoti topilmadi", show_alert=True)
            return

        order["chosen_worker"] = worker_id
        async with pool.acquire() as conn:
            await update_order(conn, order_id, chosen_worker=worker_id)

        await bot.send_message(
            user_id,
            f"✅ Siz {worker['name']} ni tanladingiz!\n\n"
            f"📱 Telefon: {worker['phone']}\n"
            f"🔗 Username: @{worker.get('username', 'yoq')}"
        )

        await bot.send_message(
            worker_id,
            f"✅ Sizni {order['name']} tanladi!\n\n"
            f"📱 Telefon: {user['phone']}\n"
            f"🔗 Username: @{order.get('username', 'yoq')}"
        )

        for admin_id in admins:
            await bot.send_message(
                admin_id,
                f"📢 Buyurtma #{order_id} da ishchi @{worker.get('username', 'yoq')} tanlandi"
            )

        await callback.answer("✅ Ishchi tanlandi")

    dp.callback_query.register(on_user_choose_worker, F.data.startswith("choose:"))