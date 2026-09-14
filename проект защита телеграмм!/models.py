import re
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()

def normalize_phone(phone: str) -> str:
    """
    Normalizes phone number to E.164 format (+CountryCodeNumber).
    Example: '+998 (90) 123-45-67' -> '+998901234567'
             '89991234567' -> '+79991234567'
    """
    if not phone:
        return ""
    digits = re.sub(r'[^\d]', '', str(phone))
    if not digits:
        return ""
    
    # Handling Russian/Kazakh 8 prefix fallback
    if len(digits) == 11 and digits.startswith('8'):
        digits = '7' + digits[1:]
        
    return f"+{digits}"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    phone_number = Column(String(30), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True, index=True)
    role = Column(String(20), default="client")
    password_hash = Column(String(255), nullable=False)
    duress_password_hash = Column(String(255), nullable=True)
    emergency_trusted_phone = Column(String(30), nullable=True)
    sms_kill_code = Column(String(50), nullable=True)
    telegram_chat_id = Column(String(50), nullable=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    @property
    def is_developer(self):
        return self.phone_number == "+998334906969" or self.role == "developer"

    protection_config = relationship("TelegramProtectionConfig", back_populates="user", uselist=False)

class PendingAuth(Base):
    __tablename__ = "pending_auths"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(30), nullable=False, index=True)
    verify_code = Column(String(10), nullable=False)
    telegram_id = Column(String(50), nullable=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

class TelegramProtectionConfig(Base):
    __tablename__ = "protection_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    device_limit = Column(Integer, default=2)
    auto_kill_enabled = Column(Boolean, default=True)
    api_id = Column(String(50), nullable=True)
    api_hash = Column(String(100), nullable=True)
    session_string = Column(Text, nullable=True)
    current_2fa_otp = Column(String(50), nullable=True)
    geofence_enabled = Column(Boolean, default=True)
    allowed_countries = Column(String(100), default="UZ,RU")
    lockdown_active = Column(Boolean, default=False)
    honeypot_id = Column(String(50), nullable=True)
    block_web_logins = Column(Boolean, default=True)
    web_login_allow_until = Column(DateTime, nullable=True)
    honeytoken_key = Column(String(100), nullable=True)

    user = relationship("User", back_populates="protection_config")

class WebAuthnCredential(Base):
    __tablename__ = "webauthn_credentials"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    credential_id = Column(String(255), unique=True, nullable=False, index=True)
    public_key = Column(Text, nullable=False)
    sign_count = Column(Integer, default=0)
    device_name = Column(String(100), default="Биометрия / Ключ")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User")

class WhitelistedSession(Base):
    __tablename__ = "whitelisted_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_name = Column(String(100), nullable=False)
    session_hash = Column(String(100), nullable=False)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class BotSubscriber(Base):
    __tablename__ = "bot_subscribers"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String(50), unique=True, nullable=False, index=True)
    phone_number = Column(String(30), nullable=True)
    username = Column(String(50), nullable=True)
    first_name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class SystemMeta(Base):
    __tablename__ = "system_metas"

    key = Column(String(50), primary_key=True)
    value = Column(Text, nullable=True)

import os

# Engine & Session setup
raw_db_url = os.getenv("DATABASE_URL", "sqlite:///./telegram_guard.db").strip()
# Render provides postgres://, SQLAlchemy requires postgresql://
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

DATABASE_URL = raw_db_url

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=30,
        max_overflow=50,
        pool_timeout=15,
        pool_recycle=300,
        pool_pre_ping=True
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    
    is_sqlite = DATABASE_URL.startswith("sqlite")
    
    migrations = [
        ("protection_configs", "current_2fa_otp", "VARCHAR(50)", None),
        ("users", "email", "VARCHAR(100)", None),
        ("users", "role", "VARCHAR(20)", "'client'"),
        ("protection_configs", "geofence_enabled", "BOOLEAN", "TRUE" if not is_sqlite else "1"),
        ("protection_configs", "allowed_countries", "VARCHAR(100)", "'UZ,RU'"),
        ("protection_configs", "lockdown_active", "BOOLEAN", "FALSE" if not is_sqlite else "0"),
        ("protection_configs", "honeypot_id", "VARCHAR(50)", None),
        ("users", "duress_password_hash", "VARCHAR(255)", None),
        ("users", "emergency_trusted_phone", "VARCHAR(30)", None),
        ("users", "sms_kill_code", "VARCHAR(50)", None),
        ("protection_configs", "block_web_logins", "BOOLEAN", "TRUE" if not is_sqlite else "1"),
        ("protection_configs", "web_login_allow_until", "TIMESTAMP", None),
        ("protection_configs", "honeytoken_key", "VARCHAR(100)", None),
        ("users", "telegram_chat_id", "VARCHAR(50)", None),
    ]

    for table, col, col_type, default_val in migrations:
        try:
            with engine.begin() as conn:
                def_clause = f" DEFAULT {default_val}" if default_val is not None else ""
                if is_sqlite:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}{def_clause}"))
                else:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}{def_clause}"))
        except Exception:
            pass

