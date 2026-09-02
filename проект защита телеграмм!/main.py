import os
import asyncio
import logging
import uvicorn
from app import app
from bot import dp, bot

logging.basicConfig(level=logging.INFO)

async def run_web():
    """Starts FastAPI web server using Uvicorn"""
    port = int(os.getenv("PORT", 8000))
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

async def run_bot():
    """Starts Telegram Bot polling"""
    logging.info("Starting Telegram Bot @Defense_telegram_lerman_bot...")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Bot error: {e}")

async def main():
    logging.info("Initializing Telegram Guard System (Web + Bot)...")
    await asyncio.gather(
        run_web(),
        run_bot()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Telegram Guard System stopped.")
