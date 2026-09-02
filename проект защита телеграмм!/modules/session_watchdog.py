import os
import asyncio
import random
import string
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, ApiIdInvalidError, FreshResetAuthorisationForbiddenError

logging.basicConfig(level=logging.INFO)

# Official Telegram Desktop app credentials & client parameters
DEFAULT_API_ID = 2040
DEFAULT_API_HASH = "b18441a12607e109d940d9261c1b57e8"

DEVICE_MODEL = "Telegram Desktop"
SYSTEM_VERSION = "Windows 10"
APP_VERSION = "4.16.8 x64"
LANG_CODE = "en"

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
        client = self._create_client()
        try:
            await client.connect()
            res = await client.send_code_request(phone)
            saved_session = client.session.save()
            await client.disconnect()
            return {
                "success": True,
                "phone_code_hash": res.phone_code_hash,
                "session_string": saved_session,
                "used_api_id": self.api_id,
                "used_api_hash": self.api_hash
            }
        except Exception as e:
            logging.error(f"Error sending MTProto code: {e}")
            await client.disconnect()
            return {"success": False, "error": str(e)}

    async def complete_login(self, phone: str, code: str, phone_code_hash: str, session_string: str, password: str = None):
        client = self._create_client(session_string)
        await client.connect()
        try:
            try:
                await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                if not password:
                    await client.disconnect()
                    return {"success": False, "requires_2fa": True, "error": "Требуется облачный пароль (2FA)"}
                await client.sign_in(password=password)

            final_session = client.session.save()
            await client.disconnect()
            return {
                "success": True,
                "session_string": final_session
            }
        except Exception as e:
            logging.error(f"Error completing MTProto login: {e}")
            await client.disconnect()
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
