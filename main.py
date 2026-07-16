"""
TG Monitor - FastAPI Backend
Web dashboard API and monitoring control.
Supports both Bot mode (primary) and Telethon user-client mode.
"""
import asyncio
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.gzip import GZipMiddleware
from pydantic import BaseModel

from database import (
    init_db, close_db, get_config, set_config, get_config_batch,
    add_group, remove_group, get_groups,
    get_recent_messages, get_messages_by_group,
    get_feedback_keywords, add_feedback_keyword, remove_feedback_keyword,
    generate_report, get_reports,
    get_overview_stats, get_activity_timeline,
)
from bark_notify import send_notification, send_feedback_alert, send_daily_summary
from report_image import generate_report_image, generate_multi_group_report
from media_tracker import get_trending, get_now_playing, get_on_the_air, format_media_message, format_media_summary
import pyotp, io, base64, qrcode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("tg-monitor")

# ─── Models ─────────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    key: str
    value: str

class GroupAdd(BaseModel):
    group_id: int
    title: str = ""
    username: str = ""

class ReportImageRequest(BaseModel):
    group_id: Optional[int] = None

class KeywordAdd(BaseModel):
    keyword: str

class AutoReplyConfig(BaseModel):
    enabled: bool = True
    message: str = "✅ 已收到您的反馈，管理员会尽快处理。"

class BotStart(BaseModel):
    token: str

class TelethonStart(BaseModel):
    api_id: int
    api_hash: str
    phone: str

class LoginData(BaseModel):
    password: str

# ─── Auth middleware ────────────────────────────────────────────

async def check_auth(request: Request):
    """Check if user is logged in via random session token."""
    password = await get_config("panel_password", "")
    if not password:
        return True  # No password set = open access
    valid_token = await get_config("session_token", "")
    if not valid_token:
        return False  # No session token generated yet
    token = request.cookies.get("session")
    return token == valid_token

async def require_auth(request: Request):
    """Raise 401 if not authenticated."""
    if not await check_auth(request):
        raise HTTPException(status_code=401, detail="未登录")
    return True


# ─── Feedback handler ───────────────────────────────────────────

def make_feedback_handler():
    """Create a feedback callback that sends Bark notifications."""
    async def handler(feedback: dict):
        logger.info("📩 Feedback: [%s] %s: %s",
                     feedback["group_title"], feedback["sender_name"],
                     feedback["text"][:60])
        await send_feedback_alert(
            group_title=feedback["group_title"],
            sender_name=feedback["sender_name"],
            text=feedback["text"],
            matched_keyword=feedback.get("matched_keyword", ""),
        )
    return handler

# ─── Monitor abstraction ───────────────────────────────────────

class MonitorManager:
    """Unified monitor management — Bot mode (primary) or Telethon mode."""

    def __init__(self):
        self.mode = None  # 'bot' or 'telethon'
        self._bot_module = None
        self._telethon_module = None

    async def start_bot(self, token: str):
        """Start Bot mode monitoring."""
        import bot_monitor as bm
        self._bot_module = bm
        if bm.is_running():
            return {"ok": False, "error": "Bot already running"}
        await bm.start_bot(token=token, feedback_callback=make_feedback_handler())
        self.mode = 'bot'
        return {"ok": True}

    async def start_telethon(self, api_id: int, api_hash: str, phone: str):
        """Start Telethon mode monitoring."""
        import telegram_monitor as tm
        self._telethon_module = tm
        if tm.is_running():
            return {"ok": False, "error": "Telethon already running"}
        await tm.start_client(
            api_id=api_id, api_hash=api_hash, phone=phone,
            feedback_callback=make_feedback_handler(),
        )
        self.mode = 'telethon'
        return {"ok": True}

    async def stop(self):
        """Stop whichever monitor is running."""
        if self._bot_module and self._bot_module.is_running():
            await self._bot_module.stop_bot()
        if self._telethon_module and self._telethon_module.is_running():
            await self._telethon_module.stop_client()
        self.mode = None

    def is_running(self) -> bool:
        if self._bot_module and self._bot_module.is_running():
            return True
        if self._telethon_module and self._telethon_module.is_running():
            return True
        return False

    async def get_status(self) -> dict:
        info = {"running": self.is_running(), "mode": self.mode}
        if self._bot_module and self._bot_module.is_running():
            info["bot_info"] = await self._bot_module.get_bot_info()
        return info

    async def list_dialogs(self):
        """List available groups (Telethon only — Bot auto-discovers via groups table)."""
        if self._telethon_module and self._telethon_module.is_running():
            return await self._telethon_module.list_dialogs()
        return []


monitor = MonitorManager()

# ─── Lifespan ───────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    os.makedirs("data/report_images", exist_ok=True)
    logger.info("Database initialized")
    yield
    await monitor.stop()
    await close_db()

app = FastAPI(title="TG Monitor Dashboard", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ─── TOTP 2FA ─────────────────────────────────────────────────

@app.get("/api/2fa/status")
async def api_2fa_status():
    """Check if 2FA is enabled."""
    secret = await get_config("totp_secret", "")
    return {"enabled": bool(secret)}


@app.post("/api/2fa/setup")
async def api_2fa_setup():
    """Generate TOTP secret and return QR code."""
    secret = pyotp.random_base32()
    await set_config("totp_secret_temp", secret)  # store temporarily until verified

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name="TG Monitor", issuer_name="tg-monitor")

    qr = qrcode.make(uri)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return {
        "ok": True,
        "secret": secret,
        "qr": f"data:image/png;base64,{qr_b64}",
    }


@app.post("/api/2fa/verify")
async def api_2fa_verify(data: ConfigUpdate):
    """Verify a TOTP code and activate 2FA."""
    secret = await get_config("totp_secret_temp", "")
    if not secret:
        return {"ok": False, "error": "请先获取密钥"}
    totp = pyotp.TOTP(secret)
    if totp.verify(data.value):
        await set_config("totp_secret", secret)
        await set_config("totp_secret_temp", "")
        return {"ok": True}
    return {"ok": False, "error": "验证码错误"}


@app.post("/api/2fa/disable")
async def api_2fa_disable(data: ConfigUpdate):
    """Disable 2FA (requires password)."""
    password = await get_config("panel_password", "")
    if password and data.value != password:
        return {"ok": False, "error": "密码错误"}
    await set_config("totp_secret", "")
    await set_config("totp_secret_temp", "")
    return {"ok": True}


@app.post("/api/login")
async def api_login(data: LoginData):
    """Verify password + TOTP if enabled."""
    password = await get_config("panel_password", "")
    if not password:
        return {"ok": True}

    if data.password != password:
        return {"ok": False, "error": "密码错误"}

    # Check TOTP if enabled
    totp_secret = await get_config("totp_secret", "")
    if totp_secret:
        # Expect TOTP code in format "password:totpcode"
        if ":" not in data.password:
            return {"ok": False, "totp_required": True, "error": "需要验证码"}
        pwd, code = data.password.rsplit(":", 1)
        if pwd != password:
            return {"ok": False, "error": "密码错误"}
        totp = pyotp.TOTP(totp_secret)
        if not totp.verify(code):
            return {"ok": False, "error": "验证码错误"}

    token = secrets.token_hex(32)
    await set_config("session_token", token)
    return {"ok": True, "token": token}



# Templates + static
os.makedirs("data/report_images", exist_ok=True)
templates = Jinja2Templates(directory="templates")
app.mount("/report_images", StaticFiles(directory="data/report_images"), name="report_images")

# ─── Exception handler for redirect ──────────────────────────

@app.exception_handler(HTTPException)
async def auth_redirect_handler(request, exc):
    if exc.status_code == 303:
        return RedirectResponse(url="/login")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

# ─── Web Routes ─────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render login page."""
    password = await get_config("panel_password", "")
    return templates.TemplateResponse(request, "login.html", {
        "has_password": bool(password),
    })

@app.post("/api/login")
@app.get("/api/logout")
async def api_logout():
    """Logout: clear session token and cookie."""
    await set_config("session_token", "")
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("session")
    return resp

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    # Auth check — always redirect to login page, which handles setup or auth
    password = await get_config("panel_password", "")
    session = request.cookies.get("session")
    if password and session != "authenticated":
        return RedirectResponse(url="/login")
    if not password:
        # No password set — redirect to setup page
        return RedirectResponse(url="/login")
    stats = await get_overview_stats()
    groups = await get_groups()
    reports = await get_reports(days=7)
    keywords = await get_feedback_keywords()
    running = monitor.is_running()
    mode = monitor.mode

    # Batch read all configs in one query
    configs = await get_config_batch(["bark_key", "bot_token", "api_id", "api_hash", "phone", "panel_password"])
    bark_key = configs.get("bark_key", "")
    bot_token = configs.get("bot_token", "")
    api_id = configs.get("api_id", "")
    api_hash = configs.get("api_hash", "")
    phone = configs.get("phone", "")
    password = configs.get("panel_password", "")
    # Aggregate reports for chart
    report_dates = sorted(set(r["report_date"] for r in reports))
    msg_counts = []
    fb_counts = []
    active_users = []
    for d in report_dates:
        day_msgs = sum(r["msg_count"] for r in reports if r["report_date"] == d)
        day_fb = sum(r["feedback_count"] for r in reports if r["report_date"] == d)
        day_users = sum(r["active_users"] for r in reports if r["report_date"] == d)
        msg_counts.append(day_msgs)
        fb_counts.append(day_fb)
        active_users.append(day_users)

    recent_msgs = await get_recent_messages(limit=30)

    return templates.TemplateResponse(request, "dashboard.html", {
        "stats": stats,
        "groups": groups,
        "reports": reports,
        "keywords": keywords,
        "monitoring": running,
        "monitor_mode": mode or "none",
        "bark_key": bark_key,
        "bot_token": "****" + bot_token[-4:] if len(bot_token) > 4 else "",
        "api_id": api_id,
        "api_hash": "****" if api_hash else "",
        "phone": phone,
        "report_dates": json.dumps(report_dates),
        "msg_counts": json.dumps(msg_counts),
        "fb_counts": json.dumps(fb_counts),
        "active_users": json.dumps(active_users),
        "recent_msgs": recent_msgs,
        "now": datetime.now().strftime("%H:%M:%S"),
        "has_password": bool(password),
    })


# ─── API Routes ─────────────────────────────────────────────────

@app.get("/api/stats")
async def api_stats(_ = Depends(require_auth)):
    stats = await get_overview_stats()
    timeline = await get_activity_timeline(hours=24)
    return {"stats": stats, "timeline": timeline}

@app.get("/api/groups")
async def api_groups(_ = Depends(require_auth)):
    return {"groups": await get_groups()}

@app.post("/api/groups/add")
async def api_add_group(data: GroupAdd, _ = Depends(require_auth)):
    try:
        await add_group(data.group_id, data.title, data.username)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/api/groups/remove")
async def api_remove_group(data: GroupAdd, _ = Depends(require_auth)):
    await remove_group(data.group_id)
    return {"ok": True}

@app.get("/api/messages")
async def api_messages(group_id: Optional[int] = Query(None), days: int = 7, _ = Depends(require_auth)):
    if group_id:
        msgs = await get_messages_by_group(group_id, days)
    else:
        msgs = await get_recent_messages(limit=100)
    return {"messages": msgs}

@app.get("/api/reports")
async def api_reports(days: int = 7, _ = Depends(require_auth)):
    return {"reports": await get_reports(days)}

@app.post("/api/reports/generate")
async def api_generate_report(data: GroupAdd, _ = Depends(require_auth)):
    try:
        report = await generate_report(data.group_id)
        return {"ok": True, "report": report}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/reports/generate-image")
async def api_generate_report_image(data: ReportImageRequest = ReportImageRequest(), _ = Depends(require_auth)):
    """Generate a report image for a specific group or all groups."""
    try:
        os.makedirs("data/report_images", exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        ts = datetime.now().strftime("%H%M%S")

        if data and data.group_id:
            # Single group
            report = await generate_report(data.group_id)
            top_msgs = await get_messages_by_group(data.group_id, days=1)
            img_bytes = generate_report_image(
                group_title=report["group_title"],
                report_date=today,
                msg_count=report["msg_count"],
                active_users=report["active_users"],
                feedback_count=report["feedback_count"],
                top_messages=top_msgs[:5],
            )
            if img_bytes:
                filename = f"report_{data.group_id}_{today}_{ts}.png"
                filepath = f"data/report_images/{filename}"
                with open(filepath, "wb") as f:
                    f.write(img_bytes)
                return {"ok": True, "filename": filename, "url": f"/report_images/{filename}"}
            return {"ok": False, "error": "Image generation failed"}

        else:
            # All active groups
            groups = await get_groups()
            reports_data = []
            filenames = []
            for g in groups:
                report = await generate_report(g["group_id"])
                top_msgs = await get_messages_by_group(g["group_id"], days=1)
                img_bytes = generate_report_image(
                    group_title=report["group_title"],
                    report_date=today,
                    msg_count=report["msg_count"],
                    active_users=report["active_users"],
                    feedback_count=report["feedback_count"],
                    top_messages=top_msgs[:5],
                )
                if img_bytes:
                    filename = f"report_{g['group_id']}_{today}_{ts}.png"
                    filepath = f"data/report_images/{filename}"
                    with open(filepath, "wb") as f:
                        f.write(img_bytes)
                    filenames.append(filename)
                reports_data.append(report)

            # Also generate multi-group summary
            summary_img = generate_multi_group_report(reports_data, today)
            if summary_img:
                sf = f"summary_{today}.png"
                with open(f"data/report_images/{sf}", "wb") as f:
                    f.write(summary_img)
                filenames.append(sf)

            return {"ok": True, "count": len(groups), "images": filenames}
    except Exception as e:
        logger.exception("Report image generation failed")
        return {"ok": False, "error": str(e)}


@app.get("/api/reports/images")
async def api_list_report_images(_ = Depends(require_auth)):
    """List all generated report images."""
    os.makedirs("data/report_images", exist_ok=True)
    images = sorted(os.listdir("data/report_images"), reverse=True)[:30]
    result = []
    for img in images:
        path = f"data/report_images/{img}"
        size = os.path.getsize(path) if os.path.exists(path) else 0
        result.append({
            "filename": img,
            "url": f"/report_images/{img}",
            "size_kb": round(size / 1024, 1),
            "created": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M") if os.path.exists(path) else "",
        })
    return {"images": result}


@app.post("/api/reports/daily-cron")
async def api_setup_daily_cron(_ = Depends(require_auth)):
    """Return the cron setup command for daily 22:00 reports."""
    import sys
    cron_cmd = (
        "To set up daily report at 22:00, run this in Hermes:\n"
        "cronjob action=create schedule='0 22 * * *' name='daily-report' \\\n"
        "  prompt='Run the daily TG Monitor report. Generate report images for all active groups. Send the summary image via Bark notification if configured. At the end show the summary text in your response.' \\\n"
        "  skills='[\"tg-monitor\"]' deliver='origin'\n\n"
        "Or visit the Reports page on the dashboard and click '⚙️ 设置定时任务' to see setup instructions."
    )
    return {"ok": True, "setup": cron_cmd}

@app.get("/api/keywords")
async def api_keywords(_ = Depends(require_auth)):
    return {"keywords": await get_feedback_keywords()}

@app.post("/api/keywords/add")
async def api_add_keyword(data: KeywordAdd, _ = Depends(require_auth)):
    await add_feedback_keyword(data.keyword)
    return {"ok": True}

@app.post("/api/keywords/remove")
async def api_remove_keyword(data: KeywordAdd, _ = Depends(require_auth)):
    await remove_feedback_keyword(data.keyword)
    return {"ok": True}

@app.post("/api/config")
async def api_update_config(data: ConfigUpdate, _ = Depends(require_auth)):
    await set_config(data.key, data.value)
    return {"ok": True}

@app.post("/api/set-password")
async def api_set_password(data: ConfigUpdate):
    """Set or change panel login password."""
    if len(data.value) < 4:
        return {"ok": False, "error": "密码至少4位"}
    await set_config("panel_password", data.value)
    return {"ok": True}

@app.get("/api/auto-reply")
async def api_get_auto_reply(_ = Depends(require_auth)):
    """Get auto-reply config."""
    msg = await get_config("auto_reply", "✅ 已收到您的反馈，管理员会尽快处理。")
    return {"message": msg}

@app.post("/api/auto-reply")
async def api_set_auto_reply(data: ConfigUpdate, _ = Depends(require_auth)):
    """Set auto-reply message."""
    await set_config("auto_reply", data.value)
    return {"ok": True}

@app.get("/api/config")
async def api_get_config(key: str = "", _ = Depends(require_auth)):
    if key:
        return {"key": key, "value": await get_config(key, "")}
    keys = ["bark_key", "bot_token", "api_id", "api_hash", "phone"]
    result = {}
    for k in keys:
        v = await get_config(k, "")
        result[k] = "****" + v[-4:] if v and len(v) > 4 else v
    return result

# ─── Bot Mode API ───────────────────────────────────────────────

@app.post("/api/monitor/bot/start")
async def api_bot_start(data: BotStart):
    if monitor.is_running():
        return {"ok": False, "error": "Monitor already running"}
    try:
        await set_config("bot_token", data.token)
        result = await monitor.start_bot(data.token)
        return result
    except Exception as e:
        logger.exception("Failed to start bot")
        return {"ok": False, "error": str(e)}

@app.post("/api/monitor/bot/stop")
async def api_bot_stop():
    if monitor._bot_module:
        await monitor._bot_module.stop_bot()
        monitor.mode = None
        return {"ok": True}
    return {"ok": False, "error": "Bot not running"}

@app.get("/api/monitor/bot/info")
async def api_bot_info(_ = Depends(require_auth)):
    if monitor._bot_module and monitor._bot_module.is_running():
        info = await monitor._bot_module.get_bot_info()
        return {"ok": True, "info": info}
    return {"ok": False, "error": "Bot not running"}


class BotSendMsg(BaseModel):
    group_id: int
    text: str = ""
    image: str = ""

class MediaQuery(BaseModel):
    type: str = "trending"  # trending, nowplaying, ontv
    group_id: Optional[int] = None


@app.post("/api/monitor/bot/send")
async def api_bot_send(data: BotSendMsg, _ = Depends(require_auth)):
    """Send a message or report image to a group via the bot."""
    if not monitor._bot_module or not monitor._bot_module.is_running():
        return {"ok": False, "error": "Bot not running"}
    try:
        if data.image:
            ok = await monitor._bot_module.send_photo_to_group(data.group_id, data.image, data.text)
        else:
            ok = await monitor._bot_module.send_to_group(data.group_id, data.text)
        return {"ok": ok}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/monitor/bot/send-report")
async def api_bot_send_report(data: GroupAdd, _ = Depends(require_auth)):
    """Generate and send daily report image to a group."""
    if not monitor._bot_module or not monitor._bot_module.is_running():
        return {"ok": False, "error": "Bot not running"}
    try:
        # Generate report
        report = await generate_report(data.group_id)
        top_msgs = await get_messages_by_group(data.group_id, days=1)
        img_bytes = generate_report_image(
            group_title=report["group_title"],
            report_date=datetime.now().strftime("%Y-%m-%d"),
            msg_count=report["msg_count"],
            active_users=report["active_users"],
            feedback_count=report["feedback_count"],
            top_messages=top_msgs[:5],
        )
        if not img_bytes:
            return {"ok": False, "error": "Image generation failed"}

        # Save and send
        ts = datetime.now().strftime("%H%M%S")
        filename = f"report_{data.group_id}_{ts}.png"
        filepath = f"data/report_images/{filename}"
        with open(filepath, "wb") as f:
            f.write(img_bytes)

        caption = f"📊 {report['group_title']} 日报\\n{report['date']} | 💬 {report['msg_count']}条 | 👥 {report['active_users']}人 | 📩 {report['feedback_count']}条反馈"
        ok = await monitor._bot_module.send_photo_to_group(data.group_id, filepath, caption)
        return {"ok": ok, "report": report}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ─── Media Tracker API ──────────────────────────────────────────

@app.post("/api/media/check")
async def api_media_check(data: MediaQuery, _ = Depends(require_auth)):
    api_key = await get_config("tmdb_key", "")
    if not api_key:
        return {"ok": False, "error": "请先配置 TMDB API Key (themoviedb.org)"}
    items = []
    title = ""
    if data.type == "trending":
        items = await get_trending(api_key, "all", "day")
        title = "🎬 今日热门影视"
    elif data.type == "nowplaying":
        items = await get_now_playing(api_key)
        title = "🎬 正在热映"
    elif data.type == "ontv":
        items = await get_on_the_air(api_key)
        title = "📺 今日更新剧集"
    if data.group_id and monitor._bot_module and monitor._bot_module.is_running():
        msg = format_media_message(items, title)
        if len(msg) > 4000:
            msg = format_media_summary(items, title)
        await monitor._bot_module.send_to_group(data.group_id, msg)
    return {"ok": True, "count": len(items), "title": title, "items": items[:5]}

@app.get("/api/media/preview")
async def api_media_preview(type: str = "trending", _ = Depends(require_auth)):
    api_key = await get_config("tmdb_key", "")
    if not api_key:
        return {"ok": False, "error": "请先配置 TMDB API Key"}
    items = []
    if type == "trending":
        items = await get_trending(api_key, "all", "day")
    elif type == "nowplaying":
        items = await get_now_playing(api_key)
    elif type == "ontv":
        items = await get_on_the_air(api_key)
    return {"ok": True, "count": len(items), "items": items[:10]}

# ─── Telethon Mode API ──────────────────────────────────────────

@app.post("/api/monitor/telethon/start")
async def api_telethon_start(data: TelethonStart, _ = Depends(require_auth)):
    if monitor.is_running():
        return {"ok": False, "error": "Monitor already running"}
    try:
        await set_config("api_id", str(data.api_id))
        await set_config("api_hash", data.api_hash)
        await set_config("phone", data.phone)
        result = await monitor.start_telethon(data.api_id, data.api_hash, data.phone)
        return result
    except Exception as e:
        logger.exception("Failed to start Telethon")
        return {"ok": False, "error": str(e)}

@app.post("/api/monitor/telethon/stop")
async def api_telethon_stop(_ = Depends(require_auth)):
    if monitor._telethon_module:
        await monitor._telethon_module.stop_client()
        monitor.mode = None
        return {"ok": True}
    return {"ok": False, "error": "Telethon not running"}

@app.get("/api/monitor/telethon/dialogs")
async def api_telethon_dialogs(_ = Depends(require_auth)):
    dialogs = await monitor.list_dialogs()
    return {"dialogs": dialogs}

# ─── Generic Monitor API ────────────────────────────────────────

@app.post("/api/monitor/stop")
async def api_monitor_stop(_ = Depends(require_auth)):
    await monitor.stop()
    return {"ok": True}

@app.get("/api/monitor/status")
async def api_monitor_status(_ = Depends(require_auth)):
    return await monitor.get_status()

# ─── Bark API ───────────────────────────────────────────────────

@app.post("/api/bark/test")
async def api_bark_test(_ = Depends(require_auth)):
    await send_notification(
        title="🔔 TG Monitor 测试通知",
        body="监控面板已成功配置 Bark 通知！",
        group="tg-monitor-test",
        level="active",
    )
    return {"ok": True}

@app.post("/api/bark/send")
async def api_bark_send(data: ConfigUpdate, _ = Depends(require_auth)):
    await send_notification(
        title=data.key,
        body=data.value,
        group="tg-monitor-custom",
        level="active",
    )
    return {"ok": True}
