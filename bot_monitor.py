"""
TG Monitor - Bot Monitor Module
Uses python-telegram-bot to monitor groups via Bot API.
Simpler setup than Telethon — just a Bot token from @BotFather.

Prerequisites:
  1. Create a bot via @BotFather on Telegram
  2. Add the bot to your group as admin
  3. Run /setprivacy → Disable so the bot can read all messages
"""
import asyncio
import logging
from datetime import datetime
from typing import Callable, Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
)

from database import (
    add_group, get_groups, save_message, get_feedback_keywords, get_config,
)

logger = logging.getLogger("tg-monitor.bot")

FeedbackCallback = Callable[[dict], None]

_bot_app: Optional[Application] = None
_on_feedback: Optional[FeedbackCallback] = None
_monitoring = False


async def start_bot(
    token: str,
    feedback_callback: Optional[FeedbackCallback] = None,
):
    """Start the Telegram bot and begin monitoring groups."""
    global _bot_app, _on_feedback, _monitoring

    _on_feedback = feedback_callback

    _bot_app = Application.builder().token(token).build()

    # Register handlers
    _bot_app.add_handler(CommandHandler("start", _cmd_start))
    _bot_app.add_handler(CommandHandler("status", _cmd_status))
    _bot_app.add_handler(CommandHandler("help", _cmd_help))
    _bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))
    _bot_app.add_error_handler(_error_handler)

    # Start polling (non-blocking)
    await _bot_app.initialize()
    await _bot_app.start()
    asyncio.create_task(_run_polling())

    _monitoring = True

    # Log groups the bot is already in
    logger.info("Bot started — monitoring groups it belongs to")
    return _bot_app


async def _run_polling():
    """Run polling in the background."""
    global _bot_app
    try:
        await _bot_app.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
    except Exception as e:
        logger.error("Bot polling error: %s", e)


async def _cmd_start(update: Update, context: CallbackContext):
    """Handle /start command."""
    chat = update.effective_chat
    if chat:
        await update.message.reply_text(
            "🤖 TG Monitor Bot 已启动！\n\n"
            "将我添加到群组并设置为管理员，我会自动监控所有消息。\n"
            "当检测到反馈关键词时，将通过 Bark 推送通知到你的手机。\n\n"
            "命令列表:\n"
            "/status — 查看监控状态\n"
            "/help — 查看帮助"
        )


async def _cmd_status(update: Update, context: CallbackContext):
    """Handle /status command."""
    chat = update.effective_chat
    if not chat:
        return

    groups = await get_groups(active_only=True)
    keywords = await get_feedback_keywords()

    msg = (
        f"📊 TG Monitor 状态\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🤖 Bot: 运行中\n"
        f"👥 监控群组: {len(groups)} 个\n"
        f"🔑 反馈关键词: {len(keywords)} 个\n"
    )
    if keywords:
        msg += f"   {', '.join(keywords)}\n"
    if groups:
        msg += f"📋 群组列表:\n"
        for g in groups[:5]:
            msg += f"   • {g['title'] or g['group_id']}\n"

    await update.message.reply_text(msg)


async def _cmd_help(update: Update, context: CallbackContext):
    """Handle /help command."""
    await update.message.reply_text(
        "🤖 TG Monitor 帮助\n\n"
        "1. 将 Bot 添加到群聊并设为管理员\n"
        "2. 在监控面板设置反馈关键词\n"
        "3. 配置 Bark 密钥以接收推送通知\n"
        "4. 当群聊中出现关键词时自动通知你\n\n"
        "命令:\n"
        "/start — 启动引导\n"
        "/status — 查看状态\n"
        "/help — 查看帮助"
    )


async def _handle_message(update: Update, context: CallbackContext):
    """Process incoming messages from monitored groups."""
    global _on_feedback

    if not update.message or not update.message.text:
        return

    chat = update.effective_chat
    if not chat:
        return

    # Only process group/channel messages
    if chat.type not in ("group", "supergroup", "channel"):
        return

    group_id = chat.id
    group_title = chat.title or f"Group {group_id}"
    username = chat.username or ""

    message = update.message
    text = message.text
    sender_id = message.from_user.id if message.from_user else 0
    sender_name = ""
    if message.from_user:
        sender_name = message.from_user.full_name or message.from_user.username or f"User {sender_id}"

    msg_date = message.date or datetime.now()

    # Check for feedback keywords
    keywords = await get_feedback_keywords()
    is_feedback = False
    matched_keyword = ""
    for kw in keywords:
        if kw.lower() in text.lower():
            is_feedback = True
            matched_keyword = kw
            break

    # Save message to database
    await save_message(
        group_id=group_id,
        sender_id=sender_id,
        sender_name=sender_name,
        text=text,
        msg_date=msg_date,
        is_feedback=is_feedback,
    )

    # Ensure group is in the database
    await add_group(group_id, group_title, username, member_count=0)

    # Fire feedback callback (→ Bark notification)
    if is_feedback:
        # Bot auto-reply in group
        try:
            reply_text = await get_config("auto_reply", "✅ 已收到您的反馈，管理员会尽快处理。")
            if reply_text:
                await message.reply_text(reply_text)
                logger.info("🤖 Auto-replied to feedback in %s", group_title)
        except Exception as e:
            logger.warning("Auto-reply failed: %s", e)

        # Fire Bark notification
        if _on_feedback:
            _on_feedback({
                "group_id": group_id,
                "group_title": group_title,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "text": text,
                "matched_keyword": matched_keyword,
                "timestamp": msg_date.isoformat(),
            })


async def _error_handler(update: Optional[Update], context: CallbackContext):
    """Log errors."""
    logger.error("Bot error: %s", context.error)


async def stop_bot():
    """Stop the bot gracefully."""
    global _bot_app, _monitoring
    _monitoring = False
    if _bot_app:
        try:
            if _bot_app.updater:
                await _bot_app.updater.stop()
            await _bot_app.stop()
            await _bot_app.shutdown()
        except Exception as e:
            logger.error("Error stopping bot: %s", e)
        _bot_app = None
    logger.info("Bot stopped")


async def get_bot_info():
    """Get connected bot information."""
    if _bot_app and _bot_app.bot:
        try:
            me = await _bot_app.bot.get_me()
            return {
                "id": me.id,
                "username": me.username,
                "name": me.full_name,
                "is_bot": me.is_bot,
            }
        except Exception:
            return None
    return None


def is_running() -> bool:
    return _monitoring and _bot_app is not None


async def send_to_group(group_id: int, text: str) -> bool:
    """Send a text message to a specific group via the bot."""
    if not _bot_app or not _bot_app.bot:
        logger.warning("Bot not running, cannot send message")
        return False
    try:
        await _bot_app.bot.send_message(chat_id=group_id, text=text)
        logger.info("Message sent to group %s", group_id)
        return True
    except Exception as e:
        logger.error("Failed to send message to group %s: %s", group_id, e)
        return False


async def send_photo_to_group(group_id: int, photo_path: str, caption: str = "") -> bool:
    """Send a photo/image to a specific group via the bot."""
    if not _bot_app or not _bot_app.bot:
        logger.warning("Bot not running, cannot send photo")
        return False
    try:
        with open(photo_path, "rb") as f:
            await _bot_app.bot.send_photo(chat_id=group_id, photo=f, caption=caption)
        logger.info("Photo sent to group %s", group_id)
        return True
    except Exception as e:
        logger.error("Failed to send photo to group %s: %s", group_id, e)
        return False


async def get_group_dialogs() -> list[dict]:
    """List groups the bot has access to (from DB)."""
    from database import get_groups
    return await get_groups()
