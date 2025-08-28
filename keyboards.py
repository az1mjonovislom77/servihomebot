
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
)


REGIONS = {
    "Toshkent viloyati": ["Toshkent sh.", "Chirchiq", "Angren", "Olmaliq"],
    "Samarqand viloyati": ["Samarqand sh", "Kattaqorgon"],
    "Fargona viloyati": ["Fargona sh.", "Qoqon", "Margilon"],
    "Andijon viloyati": ["Andijon sh.", "Asaka", "Shahrikhon"],
    "Namangan viloyati": ["Namangan sh.", "Chortoq", "Chust"],
    "Buxoro viloyati": ["Buxoro sh.", "Kogon"],
    "Navoiy viloyati": ["Navoiy sh.", "Zarafshon"],
    "Qashqadaryo viloyati": ["Qarshi", "Shahrisabz"],
    "Surxondaryo viloyati": ["Termiz", "Denov"],
    "Xorazm viloyati": ["Urganch", "Xiva"],
    "Qoraqalpogiston": ["Nukus", "Taxiatosh"]
}

SERVICES = [
    "Santexnik",
    "Elektrik",
    "Quruvchi",
    "Shinamlashtirish",
    "Mebel ustasi",
    "Bog`bon",
    "Uy tozalash",
    "Uy dizayneri",
    "Qurilish buyumlarini yetkazib berish",

]


def start_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Foydalanuvchi"), KeyboardButton(text="🛠 Ishchi")]
        ],
        resize_keyboard=True
    )



def phone_request_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )


def location_request_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Lokatsiyani yuborish", request_location=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )


def regions_keyboard():
    rows, row = [], []
    for index, region in enumerate(REGIONS.keys(), start=1):
        row.append(KeyboardButton(text=region))
        if index % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(text="🔙 Orqaga"), KeyboardButton(text="❌ Bekor qilish")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def cities_keyboard(region: str):
    rows, row = [], []
    for index, city in enumerate(REGIONS.get(region, []), start=1):
        row.append(KeyboardButton(text=city))
        if index % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(text="🔙 Orqaga"), KeyboardButton(text="❌ Bekor qilish")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def services_keyboard():
    rows, row = [], []
    for index, services in enumerate(SERVICES, start=1):
        row.append(KeyboardButton(text=services))
        if index % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KeyboardButton(text="🔙 Orqaga"), KeyboardButton(text="❌ Bekor qilish")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def confirm_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Yuborish"), KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True, one_time_keyboard=True
    )


def remove_keyboard():
    return ReplyKeyboardRemove()


def skip_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⏭ Otkazib yuborish")]],
        resize_keyboard=True, one_time_keyboard=True
    )


def worker_actions_keyboard(order_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"w:accept:{order_id}"),
                InlineKeyboardButton(text="💰 Narx belgilash", callback_data=f"set_price:{order_id}")]
        ]
    )

def choose_worker_keyboard(worker_id: int, order_id: int, price: str | None = None):
    label = "✅ Tanlash" if not price else f"✅ Tanlash ({price} som)"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=label, callback_data=f"choose:{worker_id}:{order_id}"),
            ]
        ]
    )
    return keyboard



def admin_worker_keyboard(worker_id: int, approved: bool):
    if not approved:
        keyboard = [
            [InlineKeyboardButton(text="✅ Ruxsat berish", callback_data=f"approve_worker:{worker_id}")],
            [InlineKeyboardButton(text="💭 Feedback yozish", callback_data=f"feedback:{worker_id}")],
            [InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_worker:{worker_id}")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(text="🗑 Ishdan boshatish", callback_data=f"fire_worker:{worker_id}")]
        ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def admin_user_keyboard(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ruxsat berish", callback_data=f"admin_approve:{order_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"admin_reject:{order_id}")
        ],
        [
            InlineKeyboardButton(text="✍️ Feedback", callback_data=f"admin_feedback:{order_id}")
        ]
    ])

def admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/workers"), KeyboardButton(text="/users"), KeyboardButton(text="/blocked_users"), KeyboardButton(text="/message_to_all")],
        ],
        resize_keyboard=True,
        is_persistent=True
    )


def worker_panel_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔧 Profilni tahrirlash")],
            [KeyboardButton(text="🗑 Profilni ochirish")]
        ],
        resize_keyboard=True
    )
    return keyboard


def edit_profile_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✍️ Ismni tahrirlash")],
            [KeyboardButton(text="🌆 Viloyatni tahrirlash")],
            [KeyboardButton(text="🏙 Shaharni tahrirlash")],
            [KeyboardButton(text="🛠 Kasbni tahrirlash")],
            [KeyboardButton(text="🔙 Orqaga")]
        ],
        resize_keyboard=True
    )


def location_button(lat: float, lon: float):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📍 Lokatsiyani ko`rish", url=f"https://www.google.com/maps/search/?api=1&query={lat}%2C{lon}")]
        ]
    )