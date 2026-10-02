# =====================================================
# ЗАПУСК: БОТ + API ОДНОВРЕМЕННО
# =====================================================
import asyncio
import logging
import os

import uvicorn
from aiogram import Bot, Dispatcher

# Импортируем бота и его диспетчер из main.py
# (main.py должен экспортировать dp и bot)
import main as bot_module

# Импортируем FastAPI-приложение из api.py
from api import app as fastapi_app


logging.basicConfig(level=logging.INFO)


async def run_bot():
    """Запускаем Telegram-бота в polling."""
    await bot_module.dp.start_polling(bot_module.bot)


async def run_api():
    """Запускаем FastAPI на 0.0.0.0 и порту из окружения."""
    port = int(os.getenv("PORT", 3000))
    config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    # Инициализация БД один раз
    await bot_module.init_db()

    # Запускаем оба параллельно
    await asyncio.gather(
        run_bot(),
        run_api(),
    )


if __name__ == "__main__":
    asyncio.run(main())
