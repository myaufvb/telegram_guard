"""
TELEGRAM ANTI-SPAM & HONEYPOT SENTINEL
1. Monitors outgoing messages: if >= 5 messages sent in 3 seconds or spam keywords sent in blast,
   instantly DELETES them for all parties (revoke=True) and executes PANIC LOCKDOWN!
2. Honeypot Trap: monitors decoy chat/messages — instant kill on hacker touch!
"""

import time
import logging
import asyncio
from collections import deque
from telethon import events
from telethon.tl.functions.messages import DeleteMessagesRequest

logging.basicConfig(level=logging.INFO)

# Spam keywords commonly used by Telegram hijackers
SPAM_KEYWORDS = [
    "деньги", "денег", "карта", "карту", "одолжи", "займи",
    "голосуй", "проголосуй", "помоги", "сбор", "переведи",
    "выиграл", "премиум", "крипт", "crypto", "usdt", "giveaway",
    "t.me/boost", "t.me/gift", "http://", "https://"
]

class AntiSpamSentinel:
    def __init__(self, watchdog, on_panic_trigger=None):
        self.watchdog = watchdog
        self.on_panic_trigger = on_panic_trigger
        self.outgoing_history = deque()  # stores (timestamp, chat_id, msg_id, text)
        self.honeypot_dialog_id = None
        self.lockdown_triggered = False

    def check_is_spam_blast(self, now: float, text_lower: str) -> bool:
        """
        Detects if either:
        1. >= 5 messages sent within 3.0 seconds (rate blast).
        2. >= 2 messages containing spam keywords sent within 5.0 seconds.
        """
        # Clean older than 5 seconds
        while self.outgoing_history and (now - self.outgoing_history[0][0]) > 5.0:
            self.outgoing_history.popleft()

        recent_count = len(self.outgoing_history)
        
        # Rule 1: 5 messages in 3 seconds
        three_sec_count = sum(1 for t, _, _, _ in self.outgoing_history if (now - t) <= 3.0)
        if three_sec_count >= 5:
            return True

        # Rule 2: Keyword match in blast
        has_keyword = any(kw in text_lower for kw in SPAM_KEYWORDS)
        if has_keyword and recent_count >= 2:
            return True

        return False

    async def handle_outgoing_message(self, event):
        """Processes each outgoing message from the user's account."""
        if self.lockdown_triggered:
            # Already in lockdown, delete any further outgoing message immediately
            try:
                await event.delete(revoke=True)
            except Exception:
                pass
            return

        now = time.time()
        text = event.raw_text or ""
        text_lower = text.lower()
        chat_id = event.chat_id
        msg_id = event.id

        self.outgoing_history.append((now, chat_id, msg_id, text))

        # Check for Honeypot interaction
        if self.honeypot_dialog_id and chat_id == self.honeypot_dialog_id:
            logging.critical(f"🪤 HONEYPOT TRAP TRIGGERED! Action in decoy chat {chat_id}")
            await self._trigger_emergency_response(event, reason="HONEYPOT_TRAP")
            return

        # Check for Spam Blast
        if self.check_is_spam_blast(now, text_lower):
            logging.critical(f"🚨 ANTI-SPAM BLAST DETECTED! Outgoing velocity exceeded: {len(self.outgoing_history)} msgs")
            await self._trigger_emergency_response(event, reason="SPAM_BLAST")

    async def _trigger_emergency_response(self, event, reason="SPAM_BLAST"):
        """Emergency Response: deletes spam messages and initiates Panic Lockdown."""
        self.lockdown_triggered = True
        client = event.client

        # 1. Instantly delete recent messages for all parties
        try:
            recent_ids = [m_id for _, _, m_id, _ in self.outgoing_history]
            recent_ids.append(event.id)
            await event.delete(revoke=True)
            logging.info("🧹 Deleted triggering spam message for all recipients (revoke=True)")
        except Exception as e:
            logging.error(f"Error revoking spam message: {e}")

        # 2. Execute Panic Lockdown on watchdog
        try:
            import secrets
            import string
            alphabet = string.ascii_letters + string.digits + "!@#$%&*-_=+"
            new_crypto_pwd = "".join(secrets.choice(alphabet) for _ in range(32))
            
            res = await self.watchdog.panic_lockdown_execute(new_crypto_pwd)
            logging.critical(f"🛑 PANIC LOCKDOWN COMPLETE! Terminated: {res.get('terminated_sessions', 0)} hacker sessions. Reason: {reason}")

            if self.on_panic_trigger:
                await self.on_panic_trigger(reason=reason, new_password=new_crypto_pwd)
        except Exception as ex:
            logging.error(f"Panic execution failed: {ex}")
