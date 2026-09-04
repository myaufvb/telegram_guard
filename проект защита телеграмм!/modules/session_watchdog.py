import os
import asyncio
import random
import string
import logging
import re
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest
from telethon.errors import (
    SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError,
    PasswordHashInvalidError, ApiIdInvalidError, FreshResetAuthorisationForbiddenError,
    FloodWaitError
)

logging.basicConfig(level=logging.INFO)

# Working official & primary Telegram credentials (verified with MTProto send_code_request)
DEFAULT_API_ID = int(os.environ.get("TELEGRAM_API_ID", "30893799"))
DEFAULT_API_HASH = os.environ.get("TELEGRAM_API_HASH", "104e933f456c9caee9c3645e9dfc2421")

DEVICE_MODEL = "Telegram Guard Security"
SYSTEM_VERSION = "Linux / Windows"
APP_VERSION = "2.4.0"
LANG_CODE = "ru"

# Fallback credentials pool if primary credentials fail
FALLBACK_CREDENTIALS = [
    {
        "api_id": 30893799,
        "api_hash": "104e933f456c9caee9c3645e9dfc2421",
        "device_model": "Telegram Guard Security",
        "system_version": "Linux / Windows",
        "app_version": "2.4.0",
        "lang_code": "ru"
    },
    {
        "api_id": 2834,
        "api_hash": "68875f756c9b437a8b916ca3de215815",
        "device_model": "MacBook Pro",
        "system_version": "macOS 14.4",
        "app_version": "10.8",
        "lang_code": "ru"
    }
]

# Cache of actively connected clients during authorization flow:
# phone -> {"client": TelegramClient, "phone_code_hash": str, "session_string": str}
_active_auth_clients = {}

class SessionWatchdog:
    def __init__(self, api_id = None, api_hash: str = None, session_string: str = None):
        parsed_id = None
        if api_id:
            try:
                parsed_id = int(str(api_id).strip())
            except ValueError:
                parsed_id = None

        # Filter out obsolete/revoked keys like 2040
        if parsed_id and parsed_id != 2040 and api_hash and len(str(api_hash).strip()) > 10:
            self.api_id = parsed_id
            self.api_hash = str(api_hash).strip()
        else:
            self.api_id = DEFAULT_API_ID
            self.api_hash = DEFAULT_API_HASH

        self.session_string = session_string

    def _create_client(self, session_str=None, api_id=None, api_hash=None, device_model=None, system_version=None, app_version=None, lang_code=None):
        sess = StringSession(session_str) if session_str else StringSession(self.session_string)
        return TelegramClient(
            sess,
            api_id or self.api_id,
            api_hash or self.api_hash,
            device_model=device_model or DEVICE_MODEL,
            system_version=system_version or SYSTEM_VERSION,
            app_version=app_version or APP_VERSION,
            lang_code=lang_code or LANG_CODE
        )

    async def update_2fa_password(self, new_password: str, current_password: str = None):
        """
        Updates Telegram 2FA Cloud Password directly on user's Telegram account.
        """
        if not self.session_string:
            return {"success": False, "error": "MTProto сессия не подключена"}

        client = self._create_client()
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return {"success": False, "error": "Сессия не авторизована в Telegram"}

        try:
            await client.edit_2fa(new_password=new_password, current_password=current_password)
            await client.disconnect()
            return {"success": True, "new_password": new_password}
        except Exception as e:
            logging.error(f"Error editing 2FA password: {e}")
            await client.disconnect()
            return {"success": False, "error": str(e)}

    async def send_login_code(self, phone: str):
        # Build candidate credential list
        candidates = []
        if self.api_id and self.api_hash and self.api_id != 2040:
            candidates.append({
                "api_id": self.api_id,
                "api_hash": self.api_hash,
                "device_model": DEVICE_MODEL,
                "system_version": SYSTEM_VERSION,
                "app_version": APP_VERSION,
                "lang_code": LANG_CODE
            })
        for fb in FALLBACK_CREDENTIALS:
            if not any(c["api_id"] == fb["api_id"] for c in candidates):
                candidates.append(fb)

        last_error = None
        for cand in candidates:
            # Disconnect any old pending client for this phone
            if phone in _active_auth_clients:
                old_entry = _active_auth_clients.pop(phone, None)
                if old_entry and old_entry.get("client"):
                    try:
                        await old_entry["client"].disconnect()
                    except Exception:
                        pass

            client = self._create_client(
                api_id=cand["api_id"],
                api_hash=cand["api_hash"],
                device_model=cand.get("device_model"),
                system_version=cand.get("system_version"),
                app_version=cand.get("app_version"),
                lang_code=cand.get("lang_code")
            )
            try:
                await client.connect()
                res = await client.send_code_request(phone)
                saved_session = client.session.save()
                
                # Keep client connected! Telegram invalidates code if client disconnects before sign_in
                _active_auth_clients[phone] = {
                    "client": client,
                    "phone_code_hash": res.phone_code_hash,
                    "session_string": saved_session,
                    "api_id": cand["api_id"],
                    "api_hash": cand["api_hash"]
                }

                logging.info(f"✅ Telegram code sent successfully using api_id={cand['api_id']}")
                return {
                    "success": True,
                    "phone_code_hash": res.phone_code_hash,
                    "session_string": saved_session,
                    "used_api_id": cand["api_id"],
                    "used_api_hash": cand["api_hash"]
                }
            except ApiIdInvalidError as ex:
                last_error = ex
                logging.warning(f"Telegram API ID {cand['api_id']} rejected with ApiIdInvalidError, trying fallback...")
                try:
                    await client.disconnect()
                except Exception:
                    pass
                continue
            except Exception as ex:
                err_text = str(ex)
                if "api_id/api_hash combination is invalid" in err_text or "ApiIdInvalid" in type(ex).__name__:
                    last_error = ex
                    logging.warning(f"Telegram API ID {cand['api_id']} invalid: {err_text}, trying fallback...")
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                    continue
                # If error is e.g. FloodWaitError, PhoneNumberInvalidError etc.
                logging.error(f"Error sending MTProto code with api_id={cand['api_id']}: {ex}")
                try:
                    await client.disconnect()
                except Exception:
                    pass
                return {"success": False, "error": str(ex)}

        return {
            "success": False,
            "error": f"Ошибка ключей API Telegram: {last_error or 'Не удалось подключиться'}. Проверьте правильность API ID и API Hash на my.telegram.org."
        }

    async def complete_login(self, phone: str, code: str, phone_code_hash: str, session_string: str = None, password: str = None):
        clean_code = re.sub(r'\D', '', str(code))
        if not clean_code:
            return {"success": False, "error": "Пожалуйста, введите код из сообщения Telegram"}

        # Use existing actively connected client if available to prevent PhoneCodeInvalidError
        auth_entry = _active_auth_clients.get(phone)
        client = None
        if auth_entry and auth_entry.get("client"):
            client = auth_entry["client"]
            if not phone_code_hash:
                phone_code_hash = auth_entry.get("phone_code_hash")

        if client is None or not client.is_connected():
            sess_str = session_string or (auth_entry.get("session_string") if auth_entry else None)
            used_api_id = (auth_entry.get("api_id") if auth_entry else None) or self.api_id
            used_api_hash = (auth_entry.get("api_hash") if auth_entry else None) or self.api_hash
            client = self._create_client(sess_str, api_id=used_api_id, api_hash=used_api_hash)
            await client.connect()

        try:
            try:
                await client.sign_in(phone=phone, code=clean_code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if not password:
                    # Keep client connected so user can provide 2FA cloud password next
                    return {"success": False, "requires_2fa": True, "error": "Требуется облачный пароль (2FA)"}
                await client.sign_in(password=password.strip())

            final_session = client.session.save()
            try:
                await client.disconnect()
            except Exception:
                pass
            _active_auth_clients.pop(phone, None)
            return {
                "success": True,
                "session_string": final_session
            }
        except PhoneCodeInvalidError:
            return {"success": False, "error": "Неверный код из Telegram. Проверьте правильность введенных цифр"}
        except PhoneCodeExpiredError:
            try:
                await client.disconnect()
            except Exception:
                pass
            _active_auth_clients.pop(phone, None)
            return {"success": False, "error": "Срок действия кода истек. Запросите новый код"}
        except PasswordHashInvalidError:
            return {"success": False, "requires_2fa": True, "error": "Неверный облачный пароль (2FA). Попробуйте еще раз"}
        except FloodWaitError as e:
            return {"success": False, "error": f"Слишком много попыток. Подождите {e.seconds} секунд"}
        except Exception as e:
            logging.error(f"Error completing MTProto login: {e}")
            return {"success": False, "error": str(e)}

    async def get_active_sessions(self):
        if not self.session_string:
            return []

        client = self._create_client()
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return []

        try:
            authorizations = await client(GetAuthorizationsRequest())
            sessions_data = []
            for auth in authorizations.authorizations:
                sessions_data.append({
                    "hash": auth.hash,
                    "device_model": auth.device_model,
                    "platform": auth.platform,
                    "system_version": auth.system_version,
                    "api_id": auth.api_id,
                    "app_name": auth.app_name,
                    "app_version": auth.app_version,
                    "date_created": str(auth.date_created),
                    "date_active": str(auth.date_active),
                    "ip": auth.ip,
                    "country": auth.country,
                    "current": auth.current
                })
            return sessions_data
        except Exception as e:
            logging.error(f"Error fetching authorizations: {e}")
            return []
        finally:
            await client.disconnect()

    async def enforce_device_limit(self, device_limit: int):
        if not self.session_string:
            return {"status": "ok", "action": "none", "count": 0}

        sessions = await self.get_active_sessions()
        if len(sessions) <= device_limit:
            return {"status": "ok", "action": "none", "count": len(sessions)}

        client = self._create_client()
        await client.connect()
        
        kicked_count = 0
        try:
            for s in sessions:
                if s["current"]:
                    continue  # Keep watchdog session active
                
                if (len(sessions) - kicked_count) > device_limit:
                    try:
                        await client(ResetAuthorizationRequest(hash=s["hash"]))
                        kicked_count += 1
                        logging.info(f"🛡️ AUTO-KILL: Terminated excess session {s['device_model']} (IP: {s['ip']})")
                    except FreshResetAuthorisationForbiddenError:
                        logging.warning("⚠️ Новая сессия защитника ожидает 24 часа для сброса других устройств по правилам Telegram.")
                    except Exception as ex:
                        logging.error(f"Failed to reset authorization {s['hash']}: {ex}")

            return {
                "status": "warning",
                "action": "kicked",
                "kicked_count": kicked_count,
                "remaining_sessions": len(sessions) - kicked_count
            }
        finally:
            await client.disconnect()
