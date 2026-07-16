"""
TG Monitor - Telegram Client Module
Uses Telethon to connect to Telegram and monitor groups for messages and feedback.
"""
import asyncio
import re
import logging
from datetime import datetime
from typing import Callable, Optional

from telethon import TelegramClient, events
from telethon.tl.types import Message

from database import (
    add_group, get_groups, save_message, get_feedback_keywords,
    get_config, set_config, get_overview_stats,
)

logger = logging.getLogger("tg-monitor.telegram")

# Callback type for when feedback is detected
FeedbackCallback = Callable[[dict], None]

_client: Optional[TelegramClient] = None
_on_feedback: Optional[FeedbackCallback] = None
_monitoring = False


async def start_client(api_id: int, api_hash: str, phone: str,
                        feedback_callback: Optional[FeedbackCallback] = None,
                        session_name: str = "tg_monitor_session"):
    """Start the Telegram client and begin monitoring."""
    global _client, _on_feedback, _monitoring

    _on_feedback = feedback_callback
    session_path = f"data/{session_name}"

    _client = TelegramClient(session_path, api_id, api_hash)

    await _client.start(phone=phone)
    logger.info("Telegram client started as %s", await _client.get_me())

    # Register message handler
    @_client.on(events.NewMessage)
    async def handle_message(event):
        await _process_message(event.message)

    _monitoring = True

    # Join all configured groups to ensure client is in them
    groups = await get_groups()
    for g in groups:
        try:
            entity = await _client.get_entity(g["group_id"])
            logger.info("Connected to group: %s", entity.title)
        except Exception as e:
            logger.warning("Cannot access group %s: %s", g["group_id"], e)

    return _client


async def _process_message(msg: Message):
    """Process an incoming Telegram message."""
    if not msg.peer_id or not hasattr(msg.peer_id, "channel_id"):
        return

    group_id = msg.peer_id.channel_id
    try:
        group_entity = await _client.get_entity(msg.peer_id)
        group_title = getattr(group_entity, "title", f"Group {group_id}")
    except Exception:
        group_title = f"Group {group_id}"

    # Get sender info
    sender_id = msg.sender_id or 0
    sender_name = ""
    try:
        sender = await msg.get_sender()
        if sender:
            sender_name = getattr(sender, "first_name", "") or ""
            last = getattr(sender, "last_name", "") or ""
            if last:
                sender_name += f" {last}"
            if not sender_name:
                sender_name = getattr(sender, "username", "") or f"User {sender_id}"
    except Exception:
        sender_name = f"User {sender_id}"

    text = msg.text or msg.message or ""
    if not text:
        return

    # Check for feedback keywords
    keywords = await get_feedback_keywords()
    is_feedback = False
    matched_keyword = ""
    if keywords:
        for kw in keywords:
            if kw.lower() in text.lower():
                is_feedback = True
                matched_keyword = kw
                break

    # Save message
    await save_message(
        group_id=group_id,
        sender_id=sender_id,
        sender_name=sender_name,
        text=text,
        msg_date=msg.date or datetime.now(),
        is_feedback=is_feedback,
    )

    # Ensure group is in DB
    member_count = 0
    try:
        member_count = getattr(group_entity, "participants_count", 0)
    except Exception:
        pass
    await add_group(group_id, group_title, member_count=member_count)

    # Fire feedback callback
    if is_feedback and _on_feedback:
        _on_feedback({
            "group_id": group_id,
            "group_title": group_title,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "text": text,
            "matched_keyword": matched_keyword,
            "timestamp": (msg.date or datetime.now()).isoformat(),
        })


async def fetch_recent_messages(group_id: int, limit: int = 100):
    """Fetch recent messages from a group (for catch-up / reports)."""
    if not _client:
        return []
    try:
        entity = await _client.get_entity(group_id)
        msgs = []
        async for msg in _client.iter_messages(entity, limit=limit):
            text = msg.text or msg.message or ""
            if text:
                msgs.append({
                    "id": msg.id,
                    "sender_id": msg.sender_id,
                    "text": text,
                    "date": (msg.date or datetime.now()).isoformat(),
                })
        return msgs
    except Exception as e:
        logger.error("Error fetching messages from group %s: %s", group_id, e)
        return []


async def get_group_info(group_id: int) -> Optional[dict]:
    """Get group information from Telegram."""
    if not _client:
        return None
    try:
        entity = await _client.get_entity(group_id)
        return {
            "id": entity.id,
            "title": entity.title,
            "username": getattr(entity, "username", "") or "",
            "members": getattr(entity, "participants_count", 0),
        }
    except Exception as e:
        logger.error("Error getting group info: %s", e)
        return None


async def list_dialogs():
    """List all dialogs (chats/groups) the client has access to."""
    if not _client:
        return []
    result = []
    try:
        async for dialog in _client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                result.append({
                    "id": dialog.entity.id,
                    "title": dialog.title,
                    "type": "group" if dialog.is_group else "channel",
                    "members": getattr(dialog.entity, "participants_count", 0),
                })
    except Exception as e:
        logger.error("Error listing dialogs: %s", e)
    return result


def is_running() -> bool:
    return _monitoring and _client is not None and _client.is_connected()


async def stop_client():
    """Stop the Telegram client."""
    global _client, _monitoring
    _monitoring = False
    if _client:
        await _client.disconnect()
        _client = None
