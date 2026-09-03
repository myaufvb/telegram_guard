import os
import random
import datetime
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from models import SessionLocal, PendingAuth, normalize_phone

BOT_TOKEN = os.getenv("BOT_TOKEN", "8969572909:AAGrd_XB5-r0kmkKM0t21Vet9Zz6ZFHiH48")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    welcome_text = (
        "🛡 **Добро пожаловать в Telegram Guard!**\n\n"
        "Данный бот служит для подтверждения владения аккаунтом и отправки одноразовых кодов авторизации.\n\n"
        "📋 **Инструкция:**\n"
        "1. Заполните форму регистрации на нашем сайте и укажите ваш номер телефона.\n"
        "2. Нажмите кнопку **«📱 Поделиться контактом»** внизу экрана.\n"
        "3. Бот проверит совпадение номеров и выдаст 6-значный код безопасности.\n"
        "4. Введите полученный код на сайте."
    )
    await message.answer(welcome_text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

@dp.message(F.contact)
async def handle_contact(message: types.Message):
    user_phone = message.contact.phone_number
    normalized_phone = normalize_phone(user_phone)
    telegram_id = str(message.from_user.id)

    db = SessionLocal()
    try:
        # Find latest non-expired pending auth for this phone number
        now = datetime.datetime.utcnow()
        pending = db.query(PendingAuth).filter(
            PendingAuth.phone_number == normalized_phone,
            PendingAuth.expires_at > now,
            PendingAuth.is_verified == False
        ).order_by(PendingAuth.id.desc()).first()

        # Fallback: Match by last 9 digits in case of prefix differences (+998, 8, 7, etc.)
        if not pending and len(normalized_phone) >= 9:
            last9 = normalized_phone[-9:]
            pending = db.query(PendingAuth).filter(
                PendingAuth.phone_number.endswith(last9),
                PendingAuth.expires_at > now,
                PendingAuth.is_verified == False
            ).order_by(PendingAuth.id.desc()).first()

        # Second fallback: allow matching if created in the last 1 hour
        if not pending:
            one_hour_ago = now - datetime.timedelta(hours=1)
            pending = db.query(PendingAuth).filter(
                PendingAuth.phone_number == normalized_phone,
                PendingAuth.created_at >= one_hour_ago,
                PendingAuth.is_verified == False
            ).order_by(PendingAuth.id.desc()).first()

        if not pending:
            await message.answer(
                f"⚠️ **Номер телефона не найден в ожидающих запросах на сайте**\n\n"
                f"Вы передали номер: `{normalized_phone}`\n"
                f"Пожалуйста, убедитесь, что вы указали этот же номер на сайте перед нажатием кнопки в боте.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # Generate 6-digit code
        verify_code = str(random.randint(100000, 999999))
        pending.verify_code = verify_code
        pending.telegram_id = telegram_id
        pending.expires_at = now + datetime.timedelta(minutes=30)
        db.commit()

        success_msg = (
            f"✅ **Номер успешно подтвержден!**\n\n"
            f"🔑 Ваш код авторизации на сайте Telegram Guard:\n\n"
            f"`{verify_code}`\n\n"
            f"*(Нажмите на код выше, чтобы скопировать)*\n"
            f"Введите этот 6-значный код в форме на сайте."
        )
        await message.answer(success_msg, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logging.error(f"Error in contact handler: {e}")
        await message.answer("❌ Произошла ошибка при обработке запроса. Попробуйте еще раз.")
    finally:
        db.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
