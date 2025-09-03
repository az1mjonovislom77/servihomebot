from aiogram import Dispatcher, F
from aiogram.types import Message, CallbackQuery, ContentType, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from keyboards import (
    phone_request_keyboard, regions_keyboard, cities_keyboard,
    services_keyboard, remove_keyboard, REGIONS, SERVICES,
    admin_worker_keyboard, edit_profile_keyboard, worker_panel_keyboard,
)
from database import save_worker, delete_worker, save_offer, save_pending_worker, delete_pending_worker

class WorkerRegistration(StatesGroup):
    contact = State()
    name = State()
    region = State()
    city = State()
    profession = State()

class WorkerEditProfile(StatesGroup):
    edit_name = State()
    edit_region = State()
    edit_city = State()
    edit_profession = State()

class OfferStates(StatesGroup):
    waiting_price = State()

def register_worker_handlers(
    dp: Dispatcher,
    bot,
    admins: set[int],
    workers_db: dict,
    pending_workers: dict,
    offers: dict,
    pool
):
    async def on_worker_entry(message: Message, state: FSMContext):
        await message.answer('📱 Iltimos, telefon raqamingizni yuboring:', reply_markup=phone_request_keyboard())
        await state.set_state(WorkerRegistration.contact)
    dp.message.register(on_worker_entry, F.text == '🛠 Ishchi')

    async def on_worker_contact(message: Message, state: FSMContext):
        if not message.contact:
            await message.answer('⚠️ Tugma orqali telefon raqam yuboring', reply_markup=phone_request_keyboard())
            return
        pending_workers.setdefault(message.from_user.id, {})
        pending_workers[message.from_user.id]['phone'] = message.contact.phone_number
        pending_workers[message.from_user.id]['username'] = message.from_user.username
        async with pool.acquire() as conn:
            await save_pending_worker(conn, message.from_user.id, pending_workers[message.from_user.id])
        await message.answer('✍️ Ism va Familiyangizni yozing:', reply_markup=remove_keyboard())
        await state.set_state(WorkerRegistration.name)
    dp.message.register(on_worker_contact, F.content_type == ContentType.CONTACT, WorkerRegistration.contact)

    async def on_worker_name(message: Message, state: FSMContext):
        pending_workers[message.from_user.id]["name"] = message.text.strip()
        async with pool.acquire() as conn:
            await save_pending_worker(conn, message.from_user.id, pending_workers[message.from_user.id])
        await message.answer('🌆 Viloyatni tanlang:', reply_markup=regions_keyboard())
        await state.set_state(WorkerRegistration.region)
    dp.message.register(on_worker_name, WorkerRegistration.name)

    async def on_worker_region(message: Message, state: FSMContext):
        if message.text not in REGIONS:
            await message.answer('⚠️ Royxatdan viloyat tanlang', reply_markup=regions_keyboard())
            return
        pending_workers[message.from_user.id]["region"] = message.text
        async with pool.acquire() as conn:
            await save_pending_worker(conn, message.from_user.id, pending_workers[message.from_user.id])
        await message.answer('🏙 Shaharni tanlang:', reply_markup=cities_keyboard(message.text))
        await state.set_state(WorkerRegistration.city)
    dp.message.register(on_worker_region, WorkerRegistration.region)

    async def on_worker_city(message: Message, state: FSMContext):
        region = pending_workers.get(message.from_user.id, {}).get('region')
        if message.text not in (REGIONS.get(region) or []):
            await message.answer('⚠️ Royxatdan shahar tanlang', reply_markup=cities_keyboard(region))
            return
        pending_workers[message.from_user.id]['city'] = message.text
        async with pool.acquire() as conn:
            await save_pending_worker(conn, message.from_user.id, pending_workers[message.from_user.id])
        await message.answer('🛠 Kasbingizni tanlang:', reply_markup=services_keyboard())
        await state.set_state(WorkerRegistration.profession)
    dp.message.register(on_worker_city, WorkerRegistration.city)

    async def on_worker_profession(message: Message, state: FSMContext):
        if message.text not in SERVICES:
            await message.answer('⚠️ Royxatdan kasbni tanlang', reply_markup=services_keyboard())
            return
        pending_workers[message.from_user.id]['profession'] = message.text
        async with pool.acquire() as conn:
            await save_pending_worker(conn, message.from_user.id, pending_workers[message.from_user.id])
        await state.clear()
        await message.answer('⏳ Arizangiz adminga yuborildi. Tasdiqlangach buyurtmalar keladi')

        data = pending_workers[message.from_user.id]
        for admin_id in admins:
            await bot.send_message(
                admin_id,
                f'🆕 Yangi ishchi arizasi:\n'
                f'👤 Ismi: {data.get("name","")}\n'
                f'📱 Telefon: {data.get("phone","")}\n'
                f'📍 Hudud: {data.get("region","")}/{data.get("city","")}\n'
                f'🛠 Kasb: {data.get("profession","")}\n',
                reply_markup=admin_worker_keyboard(message.from_user.id, False)
            )

        await message.answer('👷 Ishchi paneliga xush kelibsiz!', reply_markup=worker_panel_keyboard())
    dp.message.register(on_worker_profession, WorkerRegistration.profession)

    async def on_worker_edit_profile(message: Message, state: FSMContext):
        worker = workers_db.get(message.from_user.id)
        if not worker:
            await message.answer('⚠️ Siz hali royxatdan otmagansiz')
            return
        await message.answer('✍️ Qaysi ma’lumotni ozgartirmoqchisiz?', reply_markup=edit_profile_keyboard())
    dp.message.register(on_worker_edit_profile, F.text == '🔧 Profilni tahrirlash')

    async def edit_name_handler(m: Message, state: FSMContext):
        await state.set_state(WorkerEditProfile.edit_name)
        await m.answer('✍️ Yangi ismni kiriting:')

    async def edit_region_handler(m: Message, state: FSMContext):
        await state.set_state(WorkerEditProfile.edit_region)
        await m.answer('🌆 Yangi viloyatni tanlang:', reply_markup=regions_keyboard())

    async def edit_city_handler(m: Message, state: FSMContext):
        await state.set_state(WorkerEditProfile.edit_city)
        await m.answer('🏙 Yangi shaharni tanlang:', reply_markup=cities_keyboard(workers_db.get(m.from_user.id,{}).get('region')))

    async def edit_profession_handler(m: Message, state: FSMContext):
        await state.set_state(WorkerEditProfile.edit_profession)
        await m.answer('🛠 Yangi kasbni tanlang:', reply_markup=services_keyboard())

    dp.message.register(edit_name_handler, F.text == '✍️ Ismni tahrirlash')
    dp.message.register(edit_region_handler, F.text == '🌆 Viloyatni tahrirlash')
    dp.message.register(edit_city_handler, F.text == '🏙 Shaharni tahrirlash')
    dp.message.register(edit_profession_handler, F.text == '🛠 Kasbni tahrirlash')

    async def on_worker_edit_name(message: Message, state: FSMContext):
        workers_db[message.from_user.id]['name'] = message.text.strip()
        async with pool.acquire() as conn:
            await save_worker(conn, message.from_user.id, workers_db[message.from_user.id])
        await message.answer('✅ Ism yangilandi', reply_markup=worker_panel_keyboard())
        await state.clear()
    dp.message.register(on_worker_edit_name, WorkerEditProfile.edit_name)

    async def on_worker_edit_region(message: Message, state: FSMContext):
        if message.text not in REGIONS:
            await message.answer('⚠️ Royxatdan viloyat tanlang', reply_markup=regions_keyboard())
            return
        workers_db[message.from_user.id]['region'] = message.text
        async with pool.acquire() as conn:
            await save_worker(conn, message.from_user.id, workers_db[message.from_user.id])
        await message.answer('✅ Viloyat yangilandi', reply_markup=worker_panel_keyboard())
        await state.clear()
    dp.message.register(on_worker_edit_region, WorkerEditProfile.edit_region)

    async def on_worker_edit_city(message: Message, state: FSMContext):
        region = workers_db.get(message.from_user.id, {}).get('region')
        if message.text not in (REGIONS.get(region) or []):
            await message.answer('⚠️ Royxatdan shahar tanlang', reply_markup=cities_keyboard(region))
            return
        workers_db[message.from_user.id]["city"] = message.text
        async with pool.acquire() as conn:
            await save_worker(conn, message.from_user.id, workers_db[message.from_user.id])
        await message.answer('✅ Shahar yangilandi', reply_markup=worker_panel_keyboard())
        await state.clear()
    dp.message.register(on_worker_edit_city, WorkerEditProfile.edit_city)

    async def on_worker_edit_profession(message: Message, state: FSMContext):
        if message.text not in SERVICES:
            await message.answer('⚠️ Royxatdan kasbni tanlang', reply_markup=services_keyboard())
            return
        workers_db[message.from_user.id]['profession'] = message.text
        async with pool.acquire() as conn:
            await save_worker(conn, message.from_user.id, workers_db[message.from_user.id])
        await message.answer('✅ Kasb yangilandi', reply_markup=worker_panel_keyboard())
        await state.clear()
    dp.message.register(on_worker_edit_profession, WorkerEditProfile.edit_profession)

    async def on_worker_delete_profile(message: Message, state: FSMContext):
        user_id = message.from_user.id
        if user_id in workers_db:
            workers_db.pop(user_id)
            async with pool.acquire() as conn:
                await delete_worker(conn, user_id)
            await state.clear()
            markup = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='/start')]], resize_keyboard=True)
            await message.answer('🗑 Profilingiz ochirildi', reply_markup=markup)
        else:
            await message.answer('⚠️ Profil topilmadi')
    dp.message.register(on_worker_delete_profile, F.text == '🗑 Profilni ochirish')

    async def ask_price(callback: CallbackQuery, state: FSMContext):
        order_id = int(callback.data.split(":")[1])
        await state.set_state(OfferStates.waiting_price)
        await state.update_data(order_id=order_id)
        await callback.message.answer('💰 Taklif qiladigan narxni yozing (somda):')
        await callback.answer()
    dp.callback_query.register(ask_price, F.data.startswith("set_price:"))

    async def save_price(message: Message, state: FSMContext):
        data = await state.get_data()
        order_id = data.get('order_id')
        if not order_id:
            await message.answer('⚠️ Buyurtma topilmadi')
            return
        try:
            price = int(message.text.strip())
        except ValueError:
            await message.answer('❌ Faqat raqam kiriting!')
            return
        if order_id not in offers:
            offers[order_id] = {}
        offers[order_id][message.from_user.id] = price
        async with pool.acquire() as conn:
            await save_offer(conn, order_id, message.from_user.id, price)
        await message.answer(f'✅ Sizning {price} somlik taklifingiz saqlandi. Endi qabul qilish tugmasini bosing.')
        await state.clear()
    dp.message.register(save_price, OfferStates.waiting_price)