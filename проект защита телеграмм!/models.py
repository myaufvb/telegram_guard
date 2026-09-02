import re
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text
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
    password_hash = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

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

    user = relationship("User", back_populates="protection_config")

class WhitelistedSession(Base):
    __tablename__ = "whitelisted_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_name = Column(String(100), nullable=False)
    session_hash = Column(String(100), nullable=False)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# Engine & Session setup
DATABASE_URL = "sqlite:///./telegram_guard.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
