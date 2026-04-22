import os
import sys
import asyncio
import random
import sqlite3
import calendar
from datetime import date, datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)

# ================== НАСТРОЙКИ ==================
BOT_TOKEN = "8787051477:AAGWUCIgN7Vd2uICH_txBG3cv6LSW5GSDXg"
ADMIN_IDS = {1367700561}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
IMAGES_FOLDER = os.path.join(BASE_DIR, "images")
os.makedirs(IMAGES_FOLDER, exist_ok=True)

# 5 папок для альбомов команды
PHOTO_ALBUMS = {
    "general":    {"folder": os.path.join(BASE_DIR, "images", "general"),    "emoji": "🏥", "title": "Общее"},
    "doctors":    {"folder": os.path.join(BASE_DIR, "images", "doctors"),    "emoji": "👨‍⚕️", "title": "Наши врачи"},
    "certs":      {"folder": os.path.join(BASE_DIR, "images", "certs"),      "emoji": "📜", "title": "Сертификаты"},
    "events":     {"folder": os.path.join(BASE_DIR, "images", "events"),     "emoji": "🎉", "title": "Мероприятия"},
    "other":      {"folder": os.path.join(BASE_DIR, "images", "other"),      "emoji": "📁", "title": "Прочее"},
}
for album in PHOTO_ALBUMS.values():
    os.makedirs(album["folder"], exist_ok=True)

TIME_SLOTS = [f"{h}:00" for h in range(9, 19)]

calendar.setfirstweekday(calendar.MONDAY)
MONTHS_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]
WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

# ================== БОТ ==================
bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ================== FSM ==================
class Booking(StatesGroup):
    choosing_date = State()
    choosing_time = State()


class EditContent(StatesGroup):
    choosing_section = State()
    entering_text = State()


class ManagePhotos(StatesGroup):
    waiting_photo = State()


# ================== БАЗА ==================
def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            time TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS closed_slots (
            date TEXT,
            time TEXT,
            reason TEXT DEFAULT NULL,
            PRIMARY KEY (date, time)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS closed_dates (
            date TEXT PRIMARY KEY,
            reason TEXT DEFAULT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()

    defaults = {
        "welcome": (
            "🦷 *Добро пожаловать в СААРДЕНТ*\n\n"
            "Современная стоматологическая клиника, уникальная по сочетанию высокого сервиса и любви к своему делу.\n\n"
            "«СААР» — один из многопрофильных центров в сфере стоматологии, объединяющий:\n"
            "🦴 Протезирование и ортопедию\n"
            "📐 Ортодонтию\n"
            "🏗 Хирургию\n"
            "🪥 Профессиональную гигиену\n\n"
            "Клиника оснащена высококачественным оборудованием для диагностики и лечения заболеваний зубов и полости рта.\n\n"
            "Выберите, что вас интересует 👇"
        ),
        "services": (
            "🦷 *Наши услуги*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🔬 *ДИАГНОСТИКА*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "▪️ Первичный осмотр, консультация и составление плана лечения\n"
            "▪️ 3D сканирование\n"
            "▪️ Цифровой рентген\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🩺 *ТЕРАПИЯ*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "▪️ Лечение зубов с помощью дентального микроскопа\n"
            "▪️ Лечение пульпита и периодонтита\n"
            "▪️ Лечение чувствительности зубов\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🏗 *ХИРУРГИЯ*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "▪️ Удаление зубов (простое и сложное)\n"
            "▪️ Удаление зубов мудрости\n"
            "▪️ Имплантация зубов\n"
            "▪️ Костная пластика\n"
            "▪️ Синус-лифтинг\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "✨ *ЭСТЕТИЧЕСКАЯ СТОМАТОЛОГИЯ*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "▪️ Виниры и люминиры\n"
            "▪️ Художественная реставрация\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🦴 *ОРТОПЕДИЯ (ПРОТЕЗИРОВАНИЕ)*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "▪️ Коронки (металлокерамика, цирконий)\n"
            "▪️ Мостовидные протезы\n"
            "▪️ Съёмные протезы\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "📐 *ОРТОДОНТИЯ*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "▪️ Брекеты (металлические, керамические, сапфировые)\n"
            "▪️ Элайнеры (прозрачные капы)\n"
            "▪️ Ретейнеры\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🪥 *ПРОФЕССИОНАЛЬНАЯ ГИГИЕНА*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "▪️ Профессиональная чистка (ультразвук + Air Flow)\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "👶 *ДЕТСКАЯ СТОМАТОЛОГИЯ*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "▪️ Лечение молочных зубов\n"
            "▪️ Серебрение и фторирование\n"
            "▪️ Профилактика и герметизация фиссур\n\n"
            "💫 Стоимость и сроки лечения уточняются на консультации"
        ),
        "doctors": (
            "👨‍⚕️ *Наши специалисты*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🏆 *ГЛАВВРАЧ · ХИРУРГ-ИМПЛАНТОЛОГ*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👨‍⚕️ *Геворгян Арсен Маисович*\n\n"
            "⏳ Опыт работы: более 18 лет\n\n"
            "📜 *Образование и достижения:*\n\n"
            "▪️ 2013 г. — Сертификат на изготовление постоянных ортопедических работ (адгезивных мостов) из керамокомпозита. Шинирование прямым и непрямым методом.\n\n"
            "▪️ 2015 г. — Стажировка в ОАЭ. Сертификат по биомиметической концепции реставрации зубов. Экстремальные реставрации со штифтом и без штифта.\n\n"
            "▪️ 2021 г. — Сертификат «Искусство имплантации сложных случаев».\n\n"
            "🌍 Член *Всемирной ассоциации стоматологов FDI*\n\n"
            "👑 Участник закрытого клуба стоматологов *«Роял Дентист»*\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "📐 *ВРАЧ-ОРТОДОНТ*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👩‍⚕️ *Дерешкевичуте Анна Андреевна*\n\n"
            "⏳ Опыт работы: более 3 лет\n\n"
            "🎓 *Образование:*\n"
            "▪️ Смоленский государственный медицинский университет\n\n"
            "📜 *Семинары и повышение квалификации:*\n\n"
            "▪️ Семинар для врачей-ортодонтов:\n«Биомеханика. Мезиализация и дистализация — когда необходима, а когда не нужна»\n\n"
            "▪️ Семинар:\n«Основные принципы и правила работы с элайнерами»\n\n"
            "▪️ «Цифровой конгресс №1»:\n«Дентальная диагностика — междисциплинарный подход в цифровой стоматологии»\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🩺 *ТЕРАПЕВТ · ХИРУРГ · ОРТОПЕД*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👨‍⚕️ *Исмаилов Узаир Мухидинович*\n\n"
            "⏳ Опыт работы: более 5 лет\n\n"
            "🎓 *Образование:*\n"
            "▪️ 2012–2017 — Дагестанский Государственный Медицинский Университет\n"
            "Диплом по специальности «Врач-стоматолог»\n\n"
            "📜 *Повышение квалификации:*\n\n"
            "▪️ 2019 г. — Диплом о профессиональной подготовке по терапевтической стоматологии\n\n"
            "▪️ 2020 г. — Удостоверение о повышении квалификации по терапевтической стоматологии\n\n"
            "▪️ 2025 г. — Сертификат:\n«Возможности клинических решений в современном цифровом протоколе на системе Anthogyr»\n\n"
            "▪️ 2026 г. — Сертификат:\n«Базовый курс по хирургическим шаблонам и набору SQ GUIDE»\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🩺 *ТЕРАПЕВТ · ХИРУРГ*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👨‍⚕️ *Геворгян Гор Арманович*\n\n"
            "⏳ Опыт работы: 1 год\n\n"
            "🎓 *Образование:*\n"
            "▪️ Московский государственный медико-стоматологический университет им. Евдокимова (МГМСУ)"
        ),
        "contacts": (
            "📍 *СААРДЕНТ — стоматологическая клиника*\n\n"
            "🏠 *Адрес:*\n"
            "г. Истра, ул. Главного конструктора В.И. Адасько, д. 7к2\n\n"
            "📞 *Телефоны:*\n"
            "+7 (916) 977-38-38\n"
            "+7 (499) 551-06-87\n\n"
            "🕰 *График работы:*\n"
            "Ежедневно с 09:00 до 20:00\n\n"
            "🌐 *Сайт:* [saardent.ru](https://saardent.ru/)\n\n"
            "─────────────────────\n"
            "📅 Запись на приём — прямо через этого бота!\n"
            "Ждём вас в СААРДЕНТ — здесь вам улыбнутся! 😁"
        ),
    }
    for key, value in defaults.items():
        cursor.execute(
            "INSERT OR IGNORE INTO content (key, value) VALUES (?, ?)",
            (key, value)
        )
    conn.commit()
    conn.close()


# ================== КОНТЕНТ ==================
def get_content(key: str) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM content WHERE key=?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else ""


def set_content(key: str, value: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO content (key, value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()
    conn.close()


# ================== УТИЛИТЫ ==================



def calendar_keyboard(year, month, for_admin=False):
    kb = []
    cal = calendar.monthcalendar(year, month)
    kb.append([InlineKeyboardButton(text=f"{MONTHS_RU[month]} {year}", callback_data="ignore")])
    kb.append([InlineKeyboardButton(text=d, callback_data="ignore") for d in WEEKDAYS_RU])

    conn = get_connection()
    cursor = conn.cursor()

    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
                continue

            day_date = date(year, month, day)
            if day_date < date.today() or day_date > date.today() + timedelta(days=90):
                row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))
                continue

            day_str = f"{year}-{month:02d}-{day:02d}"

            cursor.execute("SELECT 1 FROM closed_dates WHERE date=?", (day_str,))
            is_closed = cursor.fetchone() is not None

            cursor.execute(
                "SELECT COUNT(*) FROM appointments WHERE date=? AND status IN ('pending', 'confirmed')",
                (day_str,)
            )
            has_appointments = cursor.fetchone()[0] > 0

            if is_closed:
                text = f"⛔ {day}"
            elif has_appointments:
                text = f"🔥 {day}" if for_admin else f"{day} 🔥"
            else:
                text = str(day)

            row.append(InlineKeyboardButton(text=text, callback_data=f"date:{day_str}"))
        kb.append(row)

    conn.close()

    kb.append([
        InlineKeyboardButton(text="⬅️", callback_data=f"prev:{year}:{month}"),
        InlineKeyboardButton(text="➡️", callback_data=f"next:{year}:{month}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def time_slots_keyboard(chosen_date):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM closed_dates WHERE date=?", (chosen_date,))
    day_closed = cursor.fetchone() is not None

    if day_closed:
        conn.close()
        kb = [
            [InlineKeyboardButton(text="⛔ День полностью закрыт", callback_data="ignore")],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh:{chosen_date}")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=kb)

    cursor.execute(
        "SELECT time FROM appointments WHERE date=? AND status IN ('pending', 'confirmed')",
        (chosen_date,)
    )
    booked = {row[0] for row in cursor.fetchall()}

    cursor.execute("SELECT time FROM closed_slots WHERE date=?", (chosen_date,))
    closed = {row[0] for row in cursor.fetchall()}

    conn.close()

    kb = []
    for t in TIME_SLOTS:
        if t in booked:
            kb.append([InlineKeyboardButton(text=f"❌ {t} (занято)", callback_data="ignore")])
        elif t in closed:
            kb.append([InlineKeyboardButton(text=f"🚫 {t} (закрыто)", callback_data="ignore")])
        else:
            kb.append([InlineKeyboardButton(text=t, callback_data=f"time:{t}")])

    kb.append([InlineKeyboardButton(text="🔄 Обновить доступное время", callback_data=f"refresh:{chosen_date}")])

    return InlineKeyboardMarkup(inline_keyboard=kb)


def status_label(status: str) -> str:
    labels = {
        "pending": "⏳ Ожидает подтверждения",
        "confirmed": "✅ Подтверждена",
    }
    return labels.get(status, status)


# ================== КНОПКИ ==================
user_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🦷 Услуги клиники"), KeyboardButton(text="👨‍⚕️ Наши врачи")],
        [KeyboardButton(text="👥 Команда клиники"), KeyboardButton(text="📍 Контакты")],
        [KeyboardButton(text="❓ Частые вопросы"), KeyboardButton(text="📅 Записаться на приём")],
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🦷 Услуги клиники"), KeyboardButton(text="👨‍⚕️ Наши врачи")],
        [KeyboardButton(text="👥 Команда клиники"), KeyboardButton(text="📍 Контакты")],
        [KeyboardButton(text="❓ Частые вопросы"), KeyboardButton(text="📅 Записаться на приём")],
        [KeyboardButton(text="✏️ Админ: Редактор контента"), KeyboardButton(text="🖼 Админ: Управление фото команды")],
    ],
    resize_keyboard=True
)

SECTION_LABELS = {
    "welcome": "👋 Приветствие (/start)",
    "services": "🦷 Услуги клиники",
    "doctors": "👨‍⚕️ Наши врачи",
    "contacts": "📍 Контакты",
}


# ================== ХЕНДЛЕРЫ ==================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    kb = admin_kb if message.from_user.id in ADMIN_IDS else user_kb
    await message.answer(
        get_content("welcome"),
        parse_mode="Markdown",
        reply_markup=kb
    )


@dp.message(lambda m: m.text == "🦷 Услуги клиники")
async def services(message: types.Message):
    await message.answer(get_content("services"), parse_mode="Markdown")


def team_menu_keyboard():
    buttons = []
    for key, album in PHOTO_ALBUMS.items():
        folder = album["folder"]
        imgs = [f for f in os.listdir(folder) if f.lower().endswith(("jpg","jpeg","png"))] if os.path.exists(folder) else []
        count = len(imgs)
        label = f"{album['emoji']} {album['title']}  ({count} фото)" if count > 0 else f"{album['emoji']} {album['title']}  (пусто)"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"album:{key}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.message(lambda m: m.text == "👥 Команда клиники")
async def team_menu(message: types.Message):
    await message.answer(
        "👥 *Команда клиники СААРДЕНТ*\n\n"
        "Выберите раздел 👇",
        parse_mode="Markdown",
        reply_markup=team_menu_keyboard()
    )


@dp.callback_query(lambda c: c.data.startswith("album:"))
async def show_album(callback: types.CallbackQuery):
    key = callback.data.split(":")[1]
    if key not in PHOTO_ALBUMS:
        await callback.answer("Раздел не найден", show_alert=True)
        return

    album = PHOTO_ALBUMS[key]
    folder = album["folder"]
    title = album["title"]
    emoji = album["emoji"]

    imgs = sorted([
        f for f in os.listdir(folder)
        if f.lower().endswith(("jpg", "jpeg", "png"))
    ]) if os.path.exists(folder) else []

    if not imgs:
        await callback.answer(f"В разделе «{title}» пока нет фото 😔", show_alert=True)
        return

    await callback.answer()

    total = len(imgs)
    chunks = [imgs[i:i + 10] for i in range(0, total, 10)]

    if len(chunks) > 1:
        await callback.message.answer(
            f"{emoji} *{title}*\n📸 Фото: {total}",
            parse_mode="Markdown"
        )

    for album_idx, chunk in enumerate(chunks):
        media = []
        for j, fname in enumerate(chunk):
            path = os.path.join(folder, fname)
            if len(chunks) == 1 and j == 0:
                caption = f"{emoji} *{title}*"
            elif len(chunks) > 1 and j == 0:
                caption = f"{emoji} *{title}* — часть {album_idx + 1} из {len(chunks)}"
            else:
                caption = None
            media.append(types.InputMediaPhoto(
                media=FSInputFile(path),
                caption=caption,
                parse_mode="Markdown" if caption else None
            ))
        await callback.message.answer_media_group(media=media)


@dp.message(lambda m: m.text == "👨‍⚕️ Наши врачи")
async def doctors(message: types.Message):
    await message.answer(get_content("doctors"), parse_mode="Markdown")


@dp.message(lambda m: m.text == "📍 Контакты")
async def contacts(message: types.Message):
    await message.answer(get_content("contacts"), parse_mode="Markdown")


@dp.message(lambda m: m.text == "📅 Записаться на приём")
async def booking_start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🌐 Записаться на сайте СААРДЕНТ",
            url="https://saardent.ru/"
        )]
    ])
    await message.answer(
        "📅 *Запись на приём*\n\n"
        "Вы можете записаться к нам удобным способом:\n\n"
        "🌐 Через сайт — выберите врача, дату и время онлайн\n"
        "📞 По телефону:\n"
        "    +7 (916) 977-38-38\n"
        "    +7 (499) 551-06-87\n\n"
        "🕰 Мы работаем ежедневно с 09:00 до 20:00\n\n"
        "Нажмите кнопку ниже 👇",
        parse_mode="Markdown",
        reply_markup=kb
    )





# ================== РЕДАКТОР КОНТЕНТА ==================
def edit_menu_keyboard():
    buttons = []
    for key, label in SECTION_LABELS.items():
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"edit_section:{key}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.message(lambda m: m.text == "✏️ Админ: Редактор контента")
async def admin_editor_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Эта функция доступна только администратору.")
        return
    await state.clear()
    await message.answer(
        "✏️ *Редактор контента*\n\n"
        "Выберите раздел, который хотите изменить:\n\n"
        "⚠️ Поддерживается Markdown-разметка:\n"
        "`*жирный*`  `_курсив_`  `` `код` ``",
        parse_mode="Markdown",
        reply_markup=edit_menu_keyboard()
    )
    await state.set_state(EditContent.choosing_section)


@dp.callback_query(lambda c: c.data.startswith("edit_section:"), EditContent.choosing_section)
async def admin_section_chosen(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return

    key = callback.data.split(":", 1)[1]
    label = SECTION_LABELS.get(key, key)
    current_text = get_content(key)

    await state.update_data(editing_key=key)

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="edit_cancel")]
    ])

    await callback.message.answer(
        f"✏️ Редактирование: *{label}*\n\n"
        f"📄 Текущий текст:\n\n{current_text}\n\n"
        "─────────────────────\n"
        "Отправьте новый текст для этого раздела.\n"
        "Поддерживается Markdown (`*жирный*`, `_курсив_` и т.д.)",
        parse_mode="Markdown",
        reply_markup=cancel_kb
    )
    await state.set_state(EditContent.entering_text)
    await callback.answer()


@dp.callback_query(lambda c: c.data == "edit_cancel")
async def admin_edit_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "❌ Редактирование отменено.",
        reply_markup=edit_menu_keyboard()
    )
    await callback.answer()


@dp.message(EditContent.entering_text)
async def admin_save_content(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    data = await state.get_data()
    key = data.get("editing_key")

    if not key:
        await state.clear()
        return

    new_text = message.text.strip()
    label = SECTION_LABELS.get(key, key)

    set_content(key, new_text)

    preview_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать ещё", callback_data=f"edit_section:{key}")],
        [InlineKeyboardButton(text="📋 К списку разделов", callback_data="edit_back_to_menu")]
    ])

    await message.answer(
        f"✅ Раздел *{label}* успешно обновлён!\n\n"
        f"📄 *Предпросмотр:*\n\n{new_text}",
        parse_mode="Markdown",
        reply_markup=preview_kb
    )
    await state.clear()


@dp.callback_query(lambda c: c.data == "edit_back_to_menu")
async def admin_back_to_edit_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(EditContent.choosing_section)
    await callback.message.answer(
        "✏️ *Редактор контента* — выберите раздел:",
        parse_mode="Markdown",
        reply_markup=edit_menu_keyboard()
    )
    await callback.answer()


# ================== НАВИГАЦИЯ КАЛЕНДАРЯ ==================
@dp.callback_query(lambda c: c.data.startswith(("prev", "next")))
async def change_month(callback: types.CallbackQuery):
    _, y, m = callback.data.split(":")
    y, m = int(y), int(m)
    if callback.data.startswith("prev"):
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    else:
        m += 1
        if m == 13:
            m = 1
            y += 1
    for_admin = callback.from_user.id in ADMIN_IDS
    await callback.message.edit_reply_markup(reply_markup=calendar_keyboard(y, m, for_admin=for_admin))
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("date:"))
async def choose_date(callback: types.CallbackQuery, state: FSMContext):
    chosen_date = callback.data.split(":")[1]

    if callback.from_user.id in ADMIN_IDS:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT reason FROM closed_dates WHERE date=?", (chosen_date,))
        day_closed = cursor.fetchone()

        cursor.execute("""
            SELECT time, user_id, status
            FROM appointments
            WHERE date = ? AND status IN ('pending', 'confirmed')
            ORDER BY time
        """, (chosen_date,))
        rows = cursor.fetchall()

        lines = [f"📅 Записи на {chosen_date}:"]
        if rows:
            for time, user_id, status in rows:
                lines.append(f"⏰ {time} — пациент {user_id} — {status_label(status)}")
        else:
            lines.append("Нет активных записей на этот день.")

        if day_closed:
            lines.append(f"\nДень полностью закрыт ⛔ (причина: {day_closed[0] or 'не указана'})")
            kb_day = [[InlineKeyboardButton(text="Открыть весь день", callback_data=f"open_day:{chosen_date}")]]
        else:
            lines.append("\nДень открыт")
            kb_day = [[InlineKeyboardButton(text="Закрыть весь день", callback_data=f"close_day:{chosen_date}")]]

        lines.append("\nУправление отдельными слотами:")

        cursor.execute("SELECT time FROM closed_slots WHERE date=?", (chosen_date,))
        closed = {row[0] for row in cursor.fetchall()}

        kb_slots = []
        for t in TIME_SLOTS:
            if t in closed:
                btn_text = f"Открыть {t}"
                cb_data = f"open_slot:{chosen_date}:{t}"
            else:
                btn_text = f"Закрыть {t}"
                cb_data = f"close_slot:{chosen_date}:{t}"
            kb_slots.append([InlineKeyboardButton(text=btn_text, callback_data=cb_data)])

        kb = InlineKeyboardMarkup(inline_keyboard=kb_day + kb_slots)

        await callback.message.answer("\n".join(lines), reply_markup=kb)

        conn.close()
        await callback.answer()
        return

    # Обычный пользователь
    await state.update_data(date=chosen_date)
    kb = time_slots_keyboard(chosen_date)

    text = (
        f"⏰ Доступное время на {chosen_date}:\n\n"
        "• Занятые слоты — ❌\n"
        "• Закрытые клиникой — 🚫\n"
        "• Закрытые дни отмечены ⛔ в календаре\n"
        "• Если список выглядит устаревшим — нажмите «Обновить доступное время»"
    )

    if not any(btn.callback_data.startswith("time:") for row in kb.inline_keyboard for btn in row if len(row) > 0):
        await callback.message.answer("На выбранную дату пока нет свободных слотов 😔")
    else:
        await callback.message.answer(text, reply_markup=kb)

    await state.set_state(Booking.choosing_time)
    await callback.answer()


# ================== ЗАКРЫТИЕ/ОТКРЫТИЕ ДНЯ ==================
@dp.callback_query(lambda c: c.data.startswith("close_day:"))
async def close_day(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Доступно только администратору", show_alert=True)
        return
    _, date_str = callback.data.split(":", 1)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO closed_dates (date, reason) VALUES (?, ?)", (date_str, "закрыто администратором"))
    conn.commit()
    conn.close()
    await callback.answer(f"День {date_str} полностью закрыт", show_alert=True)
    await callback.message.answer(f"День {date_str} закрыт для записи ⛔")


@dp.callback_query(lambda c: c.data.startswith("open_day:"))
async def open_day(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Доступно только администратору", show_alert=True)
        return
    _, date_str = callback.data.split(":", 1)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM closed_dates WHERE date=?", (date_str,))
    conn.commit()
    conn.close()
    await callback.answer(f"День {date_str} открыт", show_alert=True)
    await callback.message.answer(f"День {date_str} открыт для записи.")


# ================== ЗАКРЫТИЕ/ОТКРЫТИЕ СЛОТА ==================
@dp.callback_query(lambda c: c.data.startswith("close_slot:"))
async def close_slot(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Доступно только администратору", show_alert=True)
        return
    _, date_str, time_str = callback.data.split(":", 2)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO closed_slots (date, time) VALUES (?, ?)", (date_str, time_str))
    conn.commit()
    conn.close()
    await callback.answer(f"Слот {time_str} на {date_str} закрыт", show_alert=True)
    await callback.message.answer(f"Слот {time_str} закрыт.")


@dp.callback_query(lambda c: c.data.startswith("open_slot:"))
async def open_slot(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Доступно только администратору", show_alert=True)
        return
    _, date_str, time_str = callback.data.split(":", 2)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM closed_slots WHERE date=? AND time=?", (date_str, time_str))
    conn.commit()
    conn.close()
    await callback.answer(f"Слот {time_str} открыт", show_alert=True)
    await callback.message.answer(f"Слот {time_str} открыт.")


# ================== ОБНОВЛЕНИЕ ВРЕМЕНИ ==================
@dp.callback_query(lambda c: c.data.startswith("refresh:"))
async def refresh_times(callback: types.CallbackQuery, state: FSMContext):
    try:
        chosen_date = callback.data.split(":", 1)[1]
        await state.update_data(date=chosen_date)
        kb = time_slots_keyboard(chosen_date)
        await callback.message.answer(
            f"⏰ Доступное время на {chosen_date} (обновлено):\n\n"
            "• Занятые слоты — ❌\n"
            "• Закрытые клиникой — 🚫\n"
            "• Нажмите «Обновить», если список кажется старым",
            reply_markup=kb
        )
        await callback.answer("Список обновлён ✓")
    except Exception as e:
        print(f"[ERROR refresh] {e}", file=sys.stderr)
        await callback.answer("Не удалось обновить список", show_alert=True)


@dp.callback_query(lambda c: c.data == "ignore")
async def ignore_press(callback: types.CallbackQuery):
    await callback.answer()


# ================== ВЫБОР ВРЕМЕНИ ==================
@dp.callback_query(lambda c: c.data.startswith("time:"), Booking.choosing_time)
async def choose_time(callback: types.CallbackQuery, state: FSMContext):
    time = callback.data.split(":")[1]
    data = await state.get_data()
    chosen_date = data.get("date")
    if not chosen_date:
        await callback.answer("Сессия истекла", show_alert=True)
        await state.clear()
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM appointments WHERE date=? AND time=? AND status IN ('pending', 'confirmed')",
        (chosen_date, time)
    )
    if cursor.fetchone():
        conn.close()
        await callback.answer("Это время уже занято", show_alert=True)
        kb = time_slots_keyboard(chosen_date)
        await callback.message.answer(f"⏰ Доступное время на {chosen_date} (обновлено):", reply_markup=kb)
        return

    cursor.execute(
        "INSERT INTO appointments (user_id, date, time) VALUES (?, ?, ?)",
        (callback.from_user.id, chosen_date, time)
    )
    appointment_id = cursor.lastrowid
    conn.commit()
    conn.close()

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm:{appointment_id}"),
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel:{appointment_id}")
        ]
    ])

    await callback.message.edit_text(
        f"🦷 Запись в СААРДЕНТ\n\n📅 {chosen_date} ⏰ {time}\n\nПодтвердите запись на приём:",
        reply_markup=confirm_kb
    )

    await bot.send_message(
        list(ADMIN_IDS)[0],
        f"🆕 Новая запись (ожидает подтверждения)\n"
        f"📅 {chosen_date} ⏰ {time}\n"
        f"👤 Пациент: {callback.from_user.first_name or callback.from_user.id} (ID: {callback.from_user.id})"
    )

    await state.clear()
    await callback.answer()


# ================== ПОДТВЕРЖДЕНИЕ / ОТМЕНА ==================
@dp.callback_query(lambda c: c.data.startswith("confirm:"))
async def confirm_appointment(callback: types.CallbackQuery):
    appointment_id = int(callback.data.split(":")[1])
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET status='confirmed' WHERE id=?", (appointment_id,))
    conn.commit()
    cursor.execute("SELECT user_id, date, time FROM appointments WHERE id=?", (appointment_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        user_id, date_str, time_str = row
        await bot.send_message(
            user_id,
            f"✅ Ваша запись в СААРДЕНТ подтверждена!\n\n"
            f"📅 {date_str} ⏰ {time_str}\n\n"
            f"Ждём вас! Пожалуйста, приходите за 5–10 минут до начала 🦷"
        )
        await bot.send_message(list(ADMIN_IDS)[0], f"✅ Запись подтверждена: {date_str} ⏰ {time_str}")
    await callback.message.edit_text("✅ Запись подтверждена.")
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("cancel:"))
async def cancel_appointment(callback: types.CallbackQuery):
    appointment_id = int(callback.data.split(":")[1])
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, date, time FROM appointments WHERE id=?", (appointment_id,))
    row = cursor.fetchone()
    if not row:
        await callback.answer("Запись уже удалена.", show_alert=True)
        conn.close()
        return
    user_id, date_str, time_str = row
    cursor.execute("UPDATE appointments SET status='cancelled' WHERE id=?", (appointment_id,))
    conn.commit()
    conn.close()
    await bot.send_message(
        user_id,
        f"❌ Ваша запись в СААРДЕНТ на {date_str} ⏰ {time_str} отменена.\n\n"
        f"Если хотите перезаписаться — нажмите «📅 Записаться на приём» 😊"
    )
    await bot.send_message(list(ADMIN_IDS)[0], f"❌ Запись отменена: {date_str} ⏰ {time_str}")
    await callback.message.edit_text("❌ Запись отменена.")
    await callback.answer()



# ================== УПРАВЛЕНИЕ ФОТО КОМАНДЫ ==================

def get_team_photos(folder=None):
    """Возвращает список фото из указанной папки."""
    target = folder if folder else IMAGES_FOLDER
    if not os.path.exists(target):
        return []
    return sorted([
        f for f in os.listdir(target)
        if f.lower().endswith(("jpg", "jpeg", "png"))
    ])


def photo_folders_keyboard():
    """Клавиатура выбора папки для управления."""
    buttons = []
    for key, album in PHOTO_ALBUMS.items():
        count = len(get_team_photos(album["folder"]))
        label = f"{album['emoji']} {album['title']} ({count} фото)"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"pmf:{key}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def photo_manage_keyboard(folder_key):
    """Клавиатура управления фото в конкретной папке."""
    album = PHOTO_ALBUMS[folder_key]
    photos = get_team_photos(album["folder"])
    buttons = [
        [InlineKeyboardButton(text="📸 Добавить фото", callback_data=f"photo_add:{folder_key}")],
    ]
    if photos:
        buttons.append([InlineKeyboardButton(text="🗑 Удалить фото", callback_data=f"photo_delete_list:{folder_key}")])
        buttons.append([InlineKeyboardButton(text="👁 Посмотреть фото", callback_data=f"photo_view_all:{folder_key}")])
    buttons.append([InlineKeyboardButton(text="◀️ К списку папок", callback_data="pmf_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.message(lambda m: m.text == "🖼 Админ: Управление фото команды")
async def admin_photos_menu(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Эта функция доступна только администратору.")
        return
    await state.clear()
    await message.answer(
        "🖼 *Управление фото команды*\n\n"
        "Выберите папку:",
        parse_mode="Markdown",
        reply_markup=photo_folders_keyboard()
    )


@dp.callback_query(lambda c: c.data == "pmf_back")
async def admin_photos_back(callback: types.CallbackQuery):
    await callback.message.answer(
        "🖼 *Управление фото команды*\n\nВыберите папку:",
        parse_mode="Markdown",
        reply_markup=photo_folders_keyboard()
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("pmf:"))
async def admin_folder_chosen(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return
    folder_key = callback.data.split(":")[1]
    album = PHOTO_ALBUMS[folder_key]
    count = len(get_team_photos(album["folder"]))
    await state.update_data(folder_key=folder_key)
    await callback.message.answer(
        f"{album['emoji']} *{album['title']}*\n\n"
        f"📁 Фото в папке: *{count}*\n\n"
        f"Выберите действие:",
        parse_mode="Markdown",
        reply_markup=photo_manage_keyboard(folder_key)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("photo_add:"))
async def photo_add_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return
    folder_key = callback.data.split(":")[1]
    album = PHOTO_ALBUMS[folder_key]
    await state.update_data(folder_key=folder_key)
    await state.set_state(ManagePhotos.waiting_photo)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"pmf:{folder_key}")]
    ])
    await callback.message.answer(
        f"📸 Отправьте фото для папки *{album['emoji']} {album['title']}*\n\n"
        f"Можно отправить несколько подряд — каждое сохранится автоматически.",
        parse_mode="Markdown",
        reply_markup=cancel_kb
    )
    await callback.answer()


@dp.message(ManagePhotos.waiting_photo, lambda m: m.photo)
async def photo_add_receive(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    folder_key = data.get("folder_key", "general")
    album = PHOTO_ALBUMS[folder_key]
    folder = album["folder"]

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    filename = f"{folder_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{photo.file_unique_id[:8]}.jpg"
    dest = os.path.join(folder, filename)
    await bot.download_file(file.file_path, dest)

    count = len(get_team_photos(folder))
    done_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово", callback_data=f"photo_done:{folder_key}")],
        [InlineKeyboardButton(text="📸 Добавить ещё", callback_data=f"photo_add_more:{folder_key}")]
    ])
    await message.answer(
        f"✅ Фото сохранено в *{album['emoji']} {album['title']}*!\n"
        f"📁 Фото в папке: *{count}*\n\n"
        f"Хотите добавить ещё?",
        parse_mode="Markdown",
        reply_markup=done_kb
    )


@dp.message(ManagePhotos.waiting_photo)
async def photo_add_wrong(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        # Не админ и попал в этот стейт — просто сбрасываем
        await state.clear()
        return
    # Если нажали кнопку меню — выходим из режима загрузки без ошибки
    menu_buttons = [
        "🦷 Услуги клиники", "👨\u200d⚕️ Наши врачи", "👥 Команда клиники",
        "📍 Контакты", "❓ Частые вопросы", "📅 Записаться на приём",
        "✏️ Админ: Редактор контента", "🖼 Админ: Управление фото команды"
    ]
    if message.text and message.text in menu_buttons:
        await state.clear()
        return
    if not message.photo:
        await message.answer("⚠️ Пожалуйста, отправьте фото (не файл, а именно фото).")


@dp.callback_query(lambda c: c.data.startswith("photo_add_more:"))
async def photo_add_more(callback: types.CallbackQuery, state: FSMContext):
    folder_key = callback.data.split(":")[1]
    await state.update_data(folder_key=folder_key)
    await state.set_state(ManagePhotos.waiting_photo)
    await callback.message.answer("📸 Отправьте следующее фото:")
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("photo_done:"))
async def photo_done(callback: types.CallbackQuery, state: FSMContext):
    folder_key = callback.data.split(":")[1]
    await state.clear()
    album = PHOTO_ALBUMS[folder_key]
    count = len(get_team_photos(album["folder"]))
    await callback.message.answer(
        f"✅ Готово! В папке *{album['emoji']} {album['title']}* теперь *{count} фото* 🎉",
        parse_mode="Markdown",
        reply_markup=photo_manage_keyboard(folder_key)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("photo_view_all:"))
async def photo_view_all(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return
    folder_key = callback.data.split(":")[1]
    album = PHOTO_ALBUMS[folder_key]
    photos = get_team_photos(album["folder"])
    if not photos:
        await callback.answer("📁 Папка пуста", show_alert=True)
        return
    await callback.answer()
    for i in range(0, len(photos), 10):
        chunk = photos[i:i+10]
        media = []
        for j, fname in enumerate(chunk):
            path = os.path.join(album["folder"], fname)
            caption = f"{album['emoji']} {album['title']} — {len(photos)} фото" if (i==0 and j==0) else None
            media.append(types.InputMediaPhoto(media=FSInputFile(path), caption=caption))
        await callback.message.answer_media_group(media=media)


@dp.callback_query(lambda c: c.data.startswith("photo_delete_list:"))
async def photo_delete_list(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return
    folder_key = callback.data.split(":")[1]
    album = PHOTO_ALBUMS[folder_key]
    photos = get_team_photos(album["folder"])
    if not photos:
        await callback.answer("📁 Нет фото для удаления", show_alert=True)
        return
    buttons = []
    for fname in photos:
        buttons.append([InlineKeyboardButton(
            text=f"🗑 {fname}",
            callback_data=f"pdel:{folder_key}:{fname}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"pmf:{folder_key}")])
    await callback.message.answer(
        f"🗑 *Удаление фото из {album['emoji']} {album['title']}*\n\n⚠️ Удаление необратимо!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("pdel:"))
async def photo_delete_confirm(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа", show_alert=True)
        return
    parts = callback.data.split(":", 2)
    folder_key = parts[1]
    fname = parts[2]
    album = PHOTO_ALBUMS[folder_key]
    path = os.path.join(album["folder"], fname)
    if os.path.exists(path):
        os.remove(path)
        count = len(get_team_photos(album["folder"]))
        await callback.answer("✅ Фото удалено!", show_alert=True)
        await callback.message.answer(
            f"✅ Фото удалено из *{album['emoji']} {album['title']}*\n📁 Осталось: *{count} фото*",
            parse_mode="Markdown",
            reply_markup=photo_manage_keyboard(folder_key)
        )
    else:
        await callback.answer("⚠️ Файл не найден.", show_alert=True)



# ================== FAQ — ЧАСТЫЕ ВОПРОСЫ ==================

FAQ = {
    "🦷 Общие вопросы": {
        "Сколько стоит консультация?": (
            "💬 *Стоимость консультации*\n\n"
            "▪️ Консультация врача — *1 000 ₽*\n"
            "▪️ Консультация с составлением подробного плана лечения — *1 500 ₽*"
        ),
        "Нужно ли записываться заранее?": (
            "📅 *Запись на приём*\n\n"
            "Да, мы работаем по записи, чтобы уделить каждому пациенту достаточно времени.\n\n"
            "Запишитесь удобным способом — и мы подберём ближайшее подходящее время 😊"
        ),
        "Какие способы оплаты?": (
            "💳 *Способы оплаты*\n\n"
            "▪️ Банковская карта\n"
            "▪️ Наличные\n\n"
            "По вопросам рассрочки — уточняйте актуальные условия в клинике во время консультации."
        ),
    },
    "🪥 Лечение зубов": {
        "Сколько стоит лечение кариеса?": (
            "💬 *Лечение кариеса*\n\n"
            "Стоимость зависит от степени кариеса — в среднем от *6 000 ₽*.\n\n"
            "Точную цену врач назовёт после осмотра."
        ),
        "Сколько времени занимает лечение зуба?": (
            "⏱ *Длительность лечения*\n\n"
            "В большинстве несложных случаев — *1 визит длительностью около 1 часа*."
        ),
        "Что делать если выпала пломба?": (
            "⚠️ *Выпала пломба*\n\n"
            "Важно как можно скорее обратиться к стоматологу.\n\n"
            "Открытая полость зуба может привести к:\n"
            "▪️ Воспалению пульпы\n"
            "▪️ Инфицированию корневых каналов\n\n"
            "Даже если зуб не болит — откладывать визит не стоит!"
        ),
        "Есть ли гарантия на лечение?": (
            "✅ *Гарантия на лечение*\n\n"
            "Гарантия на лечение — *1 год*."
        ),
    },
    "🔥 Острая боль": {
        "Примете ли меня срочно сегодня?": (
            "🚨 *Срочный приём*\n\n"
            "Постараемся найти для вас срочное окно!\n\n"
            "📞 Позвоните нам прямо сейчас:\n"
            "+7 (916) 977-38-38\n"
            "+7 (499) 551-06-87\n\n"
            "Мы работаем ежедневно с 09:00 до 20:00 🕐"
        ),
    },
    "🦷 Удаление зубов": {
        "Сколько стоит удаление зуба?": (
            "💬 *Стоимость удаления*\n\n"
            "От *4 000 ₽* — зависит от сложности.\n\n"
            "Простое и сложное удаление отличаются по цене.\n"
            "Врач назовёт точную стоимость после осмотра."
        ),
        "Делаете ли сложное удаление (ретинированные зубы)?": (
            "🦷 *Сложное удаление*\n\n"
            "Да! Мы выполняем сложные удаления, в том числе ретинированных зубов.\n\n"
            "Перед процедурой врач проведёт полное обследование, включая КТ — чтобы точно определить расположение зуба и разработать безопасный план операции."
        ),
    },
    "🔩 Имплантация": {
        "Сколько стоит имплант?": (
            "💬 *Стоимость имплантов*\n\n"
            "▪️ 🇰🇷 OSSTEM (Корея) — *25 000 ₽*\n"
            "▪️ 🇫🇷 ANTHOGYR (Франция) — *45 000 ₽*\n"
            "▪️ 🇨🇭 STRAUMANN (Швейцария) — *65 000 ₽*"
        ),
        "Что лучше: импланты или протезы?": (
            "🤔 *Импланты vs Протезы*\n\n"
            "🔩 *Импланты:*\n"
            "▪️ Долговечны (15–20 лет)\n"
            "▪️ Не затрагивают соседние зубы\n"
            "▪️ Сохраняют костную ткань\n\n"
            "👑 *Протезы:*\n"
            "▪️ Доступнее по цене\n"
            "▪️ Требуют опоры на соседние зубы\n"
            "▪️ Менее комфортны в носке\n\n"
            "Окончательный выбор — после консультации с врачом 😊"
        ),
        "Можно ли поставить имплант сразу после удаления?": (
            "✅ *Одномоментная имплантация*\n\n"
            "Да, возможна! Но только при соблюдении ряда условий и отсутствии противопоказаний.\n\n"
            "Этот метод позволяет:\n"
            "▪️ Восстановить зуб в день удаления\n"
            "▪️ Сократить время лечения\n"
            "▪️ Избежать повторной операции"
        ),
        "Какая гарантия на импланты?": (
            "✅ *Гарантия на импланты*\n\n"
            "Гарантия на импланты — *1 год*."
        ),
    },
    "👑 Протезирование": {
        "Какие виды протезов есть?": (
            "👑 *Виды протезов*\n\n"
            "▪️ *Акри-Фри (Acry-Free)* — съёмный протез из эластичного полимера израильской компании Perflex. Комфортный и эстетичный.\n\n"
            "▪️ *Акриловые протезы* — съёмные конструкции из прочного пластика на основе акриловых смол. Хорошо моделируются и повторяют анатомию десны."
        ),
        "Сколько стоит коронка?": (
            "💬 *Стоимость коронки*\n\n"
            "Коронка цельноциркониевая фрезерованная с керамическим нанесением — *25 000 ₽*"
        ),
        "Сколько служат коронки?": (
            "⏱ *Срок службы коронок*\n\n"
            "В среднем коронка служит *10–15 лет*.\n\n"
            "Это клинический ориентир, а не жёсткий предел — при правильном уходе могут служить дольше."
        ),
        "Какая гарантия на коронки?": (
            "✅ *Гарантия на коронки*\n\n"
            "Гарантия на коронки — *1 год*."
        ),
    },
    "😁 Эстетика": {
        "Чем отличаются коронки от виниров?": (
            "😁 *Коронки vs Виниры*\n\n"
            "▪️ *Коронка* — покрывает зуб со всех сторон, восстанавливает функцию и защищает от разрушения.\n\n"
            "▪️ *Винир* — тонкая пластина на передней поверхности зуба, корректирует цвет и форму.\n\n"
            "Оба изделия — ортопедические конструкции, отличаются по назначению и объёму препарирования."
        ),
        "Делаете ли вы отбеливание зубов?": (
            "❌ *Отбеливание зубов*\n\n"
            "Нет, отбеливание зубов мы не делаем.\n\n"
            "Процедура может оказывать влияние на эмаль и в некоторых случаях нанести ей вред.\n\n"
            "Для улучшения цвета зубов рекомендуем профессиональную чистку AirFlow или виниры 😊"
        ),
    },
    "🧼 Профгигиена": {
        "Сколько стоит чистка зубов?": (
            "💬 *Стоимость профгигиены*\n\n"
            "Трёхэтапная профессиональная гигиена AirFlow — *7 500 ₽*"
        ),
        "Что входит в профессиональную гигиену?": (
            "🧼 *Состав профессиональной гигиены*\n\n"
            "1️⃣ *Ультразвуковой скейлинг*\n"
            "Удаление твёрдых отложений (камня). Промывание водой с антисептиком предотвращает инфицирование.\n\n"
            "2️⃣ *Air Flow — пескоструйная очистка*\n"
            "Смесь воды, воздуха и абразивного порошка удаляет мягкий налёт, пигментацию от кофе, чая, табака и очищает труднодоступные зоны.\n\n"
            "3️⃣ *Полировка и фторирование*\n"
            "Сглаживание эмали щётками и полировочными пастами. Нанесение фторсодержащего геля для укрепления эмали и защиты от кариеса."
        ),
        "Какой эффект от чистки AirFlow?": (
            "✨ *Эффект профессиональной чистки AirFlow*\n\n"
            "▪️ Удаление мягкого налёта и пигментации (кофе, чай, табак)\n"
            "▪️ Снижение бактериальной нагрузки — разрушение биоплёнки\n"
            "▪️ Визуальное осветление эмали на 1–2 тона (без химии!)\n"
            "▪️ Гладкая поверхность — налёт прилипает медленнее 😊"
        ),
    },
    "🧒 Детская стоматология": {
        "Лечите ли вы детей?": (
            "👶 *Детская стоматология*\n\n"
            "Да! Принимаем детей и стараемся сделать приём максимально спокойным и без стресса 😊\n\n"
            "Наши врачи умеют найти подход к маленьким пациентам."
        ),
    },
}


# Строим индексы для коротких callback_data (Telegram лимит 64 символа)
FAQ_CATS = list(FAQ.keys())
FAQ_KEYS = {ci: list(FAQ[cat].keys()) for ci, cat in enumerate(FAQ_CATS)}


def faq_categories_keyboard():
    buttons = []
    for ci, category in enumerate(FAQ_CATS):
        buttons.append([InlineKeyboardButton(text=category, callback_data=f"fc:{ci}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def faq_questions_keyboard(ci):
    buttons = []
    for qi, question in enumerate(FAQ_KEYS[ci]):
        buttons.append([InlineKeyboardButton(text=question, callback_data=f"fq:{ci}:{qi}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад к категориям", callback_data="fb")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.message(lambda m: m.text == "❓ Частые вопросы")
async def faq_start(message: types.Message):
    await message.answer(
        "❓ *Частые вопросы*\n\n"
        "Выберите интересующую категорию 👇",
        parse_mode="Markdown",
        reply_markup=faq_categories_keyboard()
    )


@dp.callback_query(lambda c: c.data.startswith("fc:"))
async def faq_category_chosen(callback: types.CallbackQuery):
    ci = int(callback.data.split(":")[1])
    category = FAQ_CATS[ci]
    await callback.message.edit_text(
        f"{category}\n\nВыберите вопрос 👇",
        parse_mode="Markdown",
        reply_markup=faq_questions_keyboard(ci)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("fq:"))
async def faq_answer(callback: types.CallbackQuery):
    _, ci, qi = callback.data.split(":")
    ci, qi = int(ci), int(qi)
    category = FAQ_CATS[ci]
    question = FAQ_KEYS[ci][qi]
    answer = FAQ[category][question]
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к вопросам", callback_data=f"fc:{ci}")],
        [InlineKeyboardButton(text="🏠 Все категории", callback_data="fb")]
    ])
    await callback.message.edit_text(
        answer,
        parse_mode="Markdown",
        reply_markup=back_kb
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == "fb")
async def faq_back(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "❓ *Частые вопросы*\n\nВыберите интересующую категорию 👇",
        parse_mode="Markdown",
        reply_markup=faq_categories_keyboard()
    )
    await callback.answer()


# ================== ЗАПУСК ==================
async def main():
    init_db()
    print("СААРДЕНТ бот запущен ✅")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
