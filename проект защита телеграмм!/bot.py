import os
import random
import datetime
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, MenuButtonWebApp
)
from models import SessionLocal, PendingAuth, normalize_phone

env_token = os.getenv("BOT_TOKEN", "")
if not env_token or "8969572909" in env_token:
    BOT_TOKEN = "8847343202:AAFc4CwRkDVktUgHEaY-zhEVbpJOy3tZdgg"
else:
    BOT_TOKEN = env_token

WEB_APP_URL = os.getenv("WEB_APP_URL", "https://telegram-guard-cxa5.onrender.com")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

def get_webapp_inline_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛡️ Открыть Telegram Guard (Mini App)",
                    web_app=WebAppInfo(url=WEB_APP_URL)
                )
            ]
        ]
    )

def get_main_reply_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="🛡️ Открыть Telegram Guard (Mini App)",
                    web_app=WebAppInfo(url=WEB_APP_URL)
                )
            ],
            [
                KeyboardButton(
                    text="📱 Поделиться контактом",
                    request_contact=True
                )
            ]
        ],
        resize_keyboard=True
    )

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    # Set persistent chat menu button to open Telegram Mini App
    try:
        await bot.set_chat_menu_button(
            chat_id=message.chat.id,
            menu_button=MenuButtonWebApp(text="Guard Shield", web_app=WebAppInfo(url=WEB_APP_URL))
        )
    except Exception as e:
        logging.warning(f"Could not set chat menu button: {e}")

    welcome_text = (
        "🛡 **Добро пожаловать в Telegram Guard Shield!**\n\n"
        "Система защиты аккаунта теперь работает прямо внутри Telegram как **Мини-приложение (Mini App)**!\n\n"
        "🚀 **Как пользоваться:**\n"
        "1. Нажмите кнопку **«🛡️ Открыть Telegram Guard (Mini App)»** ниже, чтобы открыть панель управления прямо в Telegram.\n"
        "2. Для получения кода подтверждения нажмите **«📱 Поделиться контактом»**."
    )
    await message.answer(
        welcome_text,
        reply_markup=get_main_reply_kb(),
        parse_mode=ParseMode.MARKDOWN
    )
    # Also send inline button for 1-tap open
    await message.answer(
        "Нажмите кнопку ниже для запуска Мини-приложения:",
        reply_markup=get_webapp_inline_kb()
    )

@dp.message(F.contact)
async def handle_contact(message: types.Message):
    user_phone = message.contact.phone_number
    normalized_phone = normalize_phone(user_phone)
    telegram_id = str(message.from_user.id)

    db = SessionLocal()
    try:
        now = datetime.datetime.utcnow()
        pending = db.query(PendingAuth).filter(
            PendingAuth.phone_number == normalized_phone,
            PendingAuth.expires_at > now,
            PendingAuth.is_verified == False
        ).order_by(PendingAuth.id.desc()).first()

        # Fallback: Match by last 9 digits
        if not pending and len(normalized_phone) >= 9:
            last9 = normalized_phone[-9:]
            pending = db.query(PendingAuth).filter(
                PendingAuth.phone_number.endswith(last9),
                PendingAuth.expires_at > now,
                PendingAuth.is_verified == False
            ).order_by(PendingAuth.id.desc()).first()

        verify_code = str(random.randint(100000, 999999))
        if not pending:
            pending = PendingAuth(
                phone_number=normalized_phone,
                verify_code=verify_code,
                telegram_id=telegram_id,
                is_verified=False,
                created_at=now,
                expires_at=now + datetime.timedelta(minutes=30)
            )
            db.add(pending)
        else:
            pending.verify_code = verify_code
            pending.telegram_id = telegram_id
            pending.expires_at = now + datetime.timedelta(minutes=30)
            pending.is_verified = False
        db.commit()

        success_msg = (
            f"✅ **Номер успешно подтвержден!**\n\n"
            f"🔑 Ваш код авторизации на сайте Telegram Guard:\n\n"
            f"`{verify_code}`\n\n"
            f"*(Нажмите на код выше, чтобы скопировать)*\n\n"
            f"Введите этот 6-значный код в приложении для входа или подтверждения аккаунта."
        )
        await message.answer(
            success_msg,
            reply_markup=get_webapp_inline_kb(),
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        logging.error(f"Error in contact handler: {e}")
        await message.answer("❌ Произошла ошибка при обработке запроса. Попробуйте еще раз.")
    finally:
        db.close()

@dp.message()
async def any_text_cmd(message: types.Message):
    text = (
        "🔐 **Telegram Guard Shield — Панель управления**\n\n"
        "Нажмите кнопку **«🛡️ Открыть Telegram Guard (Mini App)»**, чтобы запустить систему защиты прямо в Telegram,\n"
        "или нажмите **«📱 Поделиться контактом»**, чтобы получить код безопасности."
    )
    await message.answer(
        text,
        reply_markup=get_main_reply_kb(),
        parse_mode=ParseMode.MARKDOWN
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
