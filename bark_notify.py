"""
TG Monitor - Bark Notification Module
Sends push notifications to iOS via Bark API.
Bark API format: https://api.day.app/{key}/{title}/{body}
"""
import httpx
import logging
from urllib.parse import quote

from database import get_config, set_config

logger = logging.getLogger("tg-monitor.bark")


async def send_notification(title: str, body: str, group: str = "", level: str = "active"):
    """Send a push notification via Bark API."""
    bark_key = await get_config("bark_key", "")
    bark_server = await get_config("bark_server", "https://api.day.app")

    if not bark_key:
        logger.warning("Bark key not configured, notification not sent")
        return False

    # Bark URL format: {server}/{key}/{title}/{body}?group={group}&level={level}
    safe_title = quote(title[:50], safe="")
    safe_body = quote(body[:200], safe="")
    url = f"{bark_server}/{bark_key}/{safe_title}/{safe_body}"
    params = f"?group={quote(group)}&level={level}&isArchive=1"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url + params)
            if resp.status_code == 200:
                logger.info("Bark notification sent: %s", title)
                return True
            else:
                logger.warning("Bark notification failed: %s %s", resp.status_code, resp.text)
                return False
    except Exception as e:
        logger.error("Bark notification error: %s", e)
        return False


async def send_feedback_alert(
    group_title: str,
    sender_name: str,
    text: str,
    matched_keyword: str,
):
    """Send a Bark alert specifically for feedback detection."""
    title = f"📩 反馈指令: {group_title}"
    body = f"来自 {sender_name}:\n{text[:150]}"
    if matched_keyword:
        body += f"\n\n🔑 匹配关键词: {matched_keyword}"

    await send_notification(
        title=title,
        body=body,
        group="tg-monitor-feedback",
        level="timeSensitive",
    )


async def send_daily_summary(summary_text: str):
    """Send daily summary via Bark."""
    lines = summary_text.split("\n")
    title = lines[0][:50] if lines else "📊 群聊日报"
    body = "\n".join(lines[1:]) if len(lines) > 1 else summary_text

    await send_notification(
        title=title,
        body=body[:500],
        group="tg-monitor-daily",
        level="active",
    )
