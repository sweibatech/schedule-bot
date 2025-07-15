import os
import logging

# It's best to directly load ADMIN_IDS here so it's always up-to-date
ADMIN_IDS = set(int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip())
logger = logging.getLogger(__name__)

async def notify_admins(context, text: str):
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, text)
        except Exception as e:
            logger.warning(f"Failed to notify admin {admin_id}: {e}")