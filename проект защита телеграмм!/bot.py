import os
import random
import datetime
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, MenuButtonWebApp
)
from models import SessionLocal, User, PendingAuth, BotSubscriber, SystemMeta, normalize_phone

env_token = os.getenv("BOT_TOKEN", "")
if not env_token or "8969572909" in env_token:
    BOT_TOKEN = "8847343202:AAFc4CwRkDVktUgHEaY-zhEVbpJOy3tZdgg"
else:
    BOT_TOKEN = env_token

WEB_APP_URL = os.getenv("WEB_APP_URL", "https://telegram-guard-cxa5.onrender.com")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

CURRENT_UPDATE_VERSION = "v2.6-speed-and-updates-notify"

CHANGELOG_TEXT = (
    "🚀 **ОБНОВЛЕНИЕ СИСТЕМЫ TELEGRAM GUARD УСПЕШНО УСТАНОВЛЕНО!**\n\n"
    "🛡️ **Список улучшений в этой версии:**\n\n"
    "⚡ **1. Экстремальное ускорение сайта:**\n"
    "• Устранены зависания и задержки. Пул базы данных оптимизирован (до 50 соединений) — сайт открывается мгновенно.\n\n"
    "📱 **2. Мгновенные коды подтверждения:**\n"
    "• Исправлена ошибка при нажатии «📱 Поделиться контактом». Код теперь генерируется и доставляется за 0.1 сек.\n\n"
    "📢 **3. Авто-уведомления об обновлениях:**\n"
    "• Бот теперь автоматически оповещает вас о выходе всех новых функций и защитных модулей.\n\n"
    "🚫 **4. Zero-Trust Web & QR-Login Blocker:**\n"
    "• Автоматическая блокировка любых фишинговых браузерных входов и входов по QR-кодам за 1 секунду.\n\n"
    "🪤 **5. Honeytoken в «Избранном»:**\n"
    "• Ловушка в Saved Messages: если взломщик попытается открыть архив с паролями — его сессия моментально уничтожится.\n\n"
    "👥 **6. Fake-Profile Detector:**\n"
    "• Сканирование чатов на мошенников-клонов, копирующих ваше имя и фото.\n\n"
    "📱 **7. Emergency SMS Kill-Switch:**\n"
    "• Экстренное уничтожение всех чужих сессий по СМС без захода на сайт.\n\n"
    "👆 **8. Вход по биометрии (WebAuthn / Passkey):**\n"
    "• Вход в панель управления по Face ID / Touch ID / Windows Hello / YubiKey в 1 касание.\n\n"
    "📦 **9. Резервный ZIP-экспорт:**\n"
    "• Защита от кражи архивов чатов + скачивание защищенного архива данных в ZIP.\n\n"
    "🎭 **10. Режим Двойного Дна:**\n"
    "• Второй пароль «под принуждением», открывающий чистый профиль и сбрасывающий сессии в фоне.\n\n"
    "🌐 **Открыть панель управления:** [telegram-guard-cxa5.onrender.com](https://telegram-guard-cxa5.onrender.com)"
)

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
                ),
                KeyboardButton(
                    text="📢 Что нового в обновлении"
                )
            ]
        ],
        resize_keyboard=True
    )

def save_subscriber(chat_id: str, phone: str = None, username: str = None, first_name: str = None):
    """Saves user into bot_subscribers table for auto update broadcasts"""
    db = SessionLocal()
    try:
        sub = db.query(BotSubscriber).filter(BotSubscriber.chat_id == str(chat_id)).first()
        if not sub:
            sub = BotSubscriber(
                chat_id=str(chat_id),
                phone_number=phone,
                username=username,
                first_name=first_name
            )
            db.add(sub)
        else:
            if phone:
                sub.phone_number = phone
            if username:
                sub.username = username
            if first_name:
                sub.first_name = first_name
        db.commit()
    except Exception as e:
        logging.error(f"Error saving subscriber: {e}")
    finally:
        db.close()

async def broadcast_system_update(force: bool = False):
    """
    Broadcasts changelog notification to all subscribers upon deployment.
    """
    await asyncio.sleep(2.0)
    db = SessionLocal()
    already_sent = False
    chat_ids = set()
    try:
        meta = db.query(SystemMeta).filter(SystemMeta.key == "last_broadcast_version").first()
        if meta and meta.value == CURRENT_UPDATE_VERSION and not force:
            already_sent = True

        if not already_sent:
            subs = db.query(BotSubscriber).all()
            for s in subs:
                if s.chat_id:
                    chat_ids.add(str(s.chat_id))
            users = db.query(User).filter(User.telegram_chat_id.isnot(None)).all()
            for u in users:
                chat_ids.add(str(u.telegram_chat_id))
            pending = db.query(PendingAuth).filter(PendingAuth.telegram_id.isnot(None)).all()
            for p in pending:
                chat_ids.add(str(p.telegram_id))

            if not meta:
                meta = SystemMeta(key="last_broadcast_version", value=CURRENT_UPDATE_VERSION)
                db.add(meta)
            else:
                meta.value = CURRENT_UPDATE_VERSION
            db.commit()
    except Exception as e:
        logging.error(f"Error checking broadcast meta: {e}")
    finally:
        db.close()

    if already_sent:
        logging.info(f"Broadcast for version {CURRENT_UPDATE_VERSION} was already completed.")
        return

    logging.info(f"Broadcasting update {CURRENT_UPDATE_VERSION} to {len(chat_ids)} users...")
    for cid in chat_ids:
        try:
            await bot.send_message(
                chat_id=cid,
                text=CHANGELOG_TEXT,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_reply_kb(),
                disable_web_page_preview=True
            )
            await asyncio.sleep(0.08)
        except Exception as ex:
            logging.warning(f"Could not send update to chat {cid}: {ex}")

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    # Register subscriber
    save_subscriber(
        chat_id=str(message.chat.id),
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )

    try:
        await bot.set_chat_menu_button(
            chat_id=message.chat.id,
            menu_button=MenuButtonWebApp(text="Guard Shield", web_app=WebAppInfo(url=WEB_APP_URL))
        )
    except Exception as e:
        logging.warning(f"Could not set chat menu button: {e}")

    welcome_text = (
        "🛡 **Добро пожаловать в Telegram Guard Shield!**\n\n"
        "Система защиты аккаунта работает прямо внутри Telegram как **Мини-приложение (Mini App)**!\n\n"
        "🚀 **Быстрые действия:**\n"
        "1. Нажмите кнопку **«🛡️ Открыть Telegram Guard (Mini App)»** ниже для запуска панели.\n"
        "2. Для входа на сайте нажмите **«📱 Поделиться контактом»** (код придет за 0.1 сек).\n"
        "3. Нажмите **«📢 Что нового в обновлении»**, чтобы узнать обо всех новых функциях."
    )
    await message.answer(
        welcome_text,
        reply_markup=get_main_reply_kb(),
        parse_mode=ParseMode.MARKDOWN
    )
    await message.answer(
        "Нажмите кнопку ниже для запуска Мини-приложения:",
        reply_markup=get_webapp_inline_kb()
    )

@dp.message(Command("updates"))
@dp.message(Command("changelog"))
@dp.message(F.text == "📢 Что нового в обновлении")
async def changelog_cmd(message: types.Message):
    save_subscriber(
        chat_id=str(message.chat.id),
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    await message.answer(
        CHANGELOG_TEXT,
        reply_markup=get_main_reply_kb(),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

@dp.message(F.contact)
async def handle_contact(message: types.Message):
    user_phone = message.contact.phone_number
    normalized_phone = normalize_phone(user_phone)
    telegram_id = str(message.from_user.id)
    chat_id = str(message.chat.id)

    # Save subscriber
    save_subscriber(
        chat_id=chat_id,
        phone=normalized_phone,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )

    db = SessionLocal()
    try:
        # Link user's telegram_chat_id
        user = db.query(User).filter(User.phone_number == normalized_phone).first()
        if not user and len(normalized_phone) >= 9:
            user = db.query(User).filter(User.phone_number.endswith(normalized_phone[-9:])).first()
        if user:
            user.telegram_chat_id = chat_id
            db.commit()

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
            f"Введите этот 6-значный код на сайте или в приложении для входа."
        )
        await message.answer(
            success_msg,
            reply_markup=get_webapp_inline_kb(),
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        logging.error(f"Error in contact handler: {e}")
        await message.answer("❌ Произошла ошибка при обработке запроса. Попробуйте еще раз через 5 секунд.")
    finally:
        db.close()

@dp.message()
async def any_text_cmd(message: types.Message):
    save_subscriber(
        chat_id=str(message.chat.id),
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    text = (
        "🔐 **Telegram Guard Shield — Панель управления**\n\n"
        "• Нажмите **«🛡️ Открыть Telegram Guard (Mini App)»**, чтобы запустить систему защиты прямо в Telegram.\n"
        "• Нажмите **«📱 Поделиться контактом»**, чтобы мгновенно получить код авторизации.\n"
        "• Нажмите **«📢 Что нового в обновлении»**, чтобы посмотреть список обновлений."
    )
    await message.answer(
        text,
        reply_markup=get_main_reply_kb(),
        parse_mode=ParseMode.MARKDOWN
    )

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
