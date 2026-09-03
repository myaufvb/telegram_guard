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

# Official Telegram Desktop app credentials & client parameters
DEFAULT_API_ID = 2040
DEFAULT_API_HASH = "b18441a12607e109d940d9261c1b57e8"

DEVICE_MODEL = "Telegram Desktop"
SYSTEM_VERSION = "Windows 10"
APP_VERSION = "4.16.8 x64"
LANG_CODE = "en"

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

        if parsed_id and api_hash and len(str(api_hash).strip()) > 10:
            self.api_id = parsed_id
            self.api_hash = str(api_hash).strip()
        else:
            self.api_id = DEFAULT_API_ID
            self.api_hash = DEFAULT_API_HASH

        self.session_string = session_string

    def _create_client(self, session_str=None):
        sess = StringSession(session_str) if session_str else StringSession(self.session_string)
        return TelegramClient(
            sess,
            self.api_id,
            self.api_hash,
            device_model=DEVICE_MODEL,
            system_version=SYSTEM_VERSION,
            app_version=APP_VERSION,
            lang_code=LANG_CODE
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
        # Disconnect any old pending client for this phone
        if phone in _active_auth_clients:
            old_entry = _active_auth_clients.pop(phone, None)
            if old_entry and old_entry.get("client"):
                try:
                    await old_entry["client"].disconnect()
                except Exception:
                    pass

        client = self._create_client()
        try:
            await client.connect()
            res = await client.send_code_request(phone)
            saved_session = client.session.save()
            
            # Keep client connected! Telegram invalidates code if client disconnects before sign_in
            _active_auth_clients[phone] = {
                "client": client,
                "phone_code_hash": res.phone_code_hash,
                "session_string": saved_session,
                "api_id": self.api_id,
                "api_hash": self.api_hash
            }

            return {
                "success": True,
                "phone_code_hash": res.phone_code_hash,
                "session_string": saved_session,
                "used_api_id": self.api_id,
                "used_api_hash": self.api_hash
            }
        except Exception as e:
            logging.error(f"Error sending MTProto code: {e}")
            try:
                await client.disconnect()
            except Exception:
                pass
            return {"success": False, "error": str(e)}

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
            client = self._create_client(sess_str)
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
