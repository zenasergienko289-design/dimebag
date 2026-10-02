# =====================================================
# Уведомления в боте (для вызова из API)
# =====================================================
import logging
from aiogram import Bot
from config import BOT_TOKEN, MINI_APP_URL

logger = logging.getLogger(__name__)

_bot = Bot(token=BOT_TOKEN)


async def notify_buyer_gift_sent(buyer_id: int, code: str):
    """Продавец передал подарок в банк — уведомляем покупателя."""
    try:
        text = (
            f"🎁 <b>Продавец передал подарок в банк</b>\n\n"
            f"Сделка: <b>#{code}</b>\n\n"
            f"Откройте приложение и подтвердите получение."
        )
        await _bot.send_message(buyer_id, text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"notify_buyer_gift_sent failed: {e}")


async def notify_seller_done(seller_id: int, code: str):
    """Сделка завершена — уведомляем продавца."""
    try:
        text = (
            f"✅ <b>Сделка завершена!</b>\n\n"
            f"Сделка: <b>#{code}</b>\n"
            f"Деньги зачислены на ваш баланс."
        )
        await _bot.send_message(seller_id, text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"notify_seller_done failed: {e}")