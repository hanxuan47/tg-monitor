"""
TG Monitor - FastAPI Backend
Web dashboard API and monitoring control.
Supports both Bot mode (primary) and Telethon user-client mode.
"""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from database import (
    init_db, get_config, set_config,
    add_group, remove_group, get_groups,
    get_recent_messages, get_messages_by_group,
    get_feedback_keywords, add_feedback_keyword, remove_feedback_keyword,
    generate_report, get_reports,
    get_overview_stats, get_activity_timeline,
)
from bark_notify import send_notification, send_feedback_alert, send_daily_summary
from report_image import generate_report_image, generate_multi_group_report

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

class BotStart(BaseModel):
    token: str

class TelethonStart(BaseModel):
    api_id: int
    api_hash: str
    phone: str

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

app = FastAPI(title="TG Monitor Dashboard", lifespan=lifespan)

# Templates + static
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/report_images", StaticFiles(directory="data/report_images"), name="report_images")

# ─── Web Routes ─────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    stats = await get_overview_stats()
    groups = await get_groups()
    reports = await get_reports(days=7)
    keywords = await get_feedback_keywords()
    running = monitor.is_running()
    mode = monitor.mode
    bark_key = await get_config("bark_key", "")
    bot_token = await get_config("bot_token", "")
    api_id = await get_config("api_id", "")
    api_hash = await get_config("api_hash", "")
    phone = await get_config("phone", "")

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
    })


# ─── API Routes ─────────────────────────────────────────────────

@app.get("/api/stats")
async def api_stats():
    stats = await get_overview_stats()
    timeline = await get_activity_timeline(hours=24)
    return {"stats": stats, "timeline": timeline}

@app.get("/api/groups")
async def api_groups():
    return {"groups": await get_groups()}

@app.post("/api/groups/add")
async def api_add_group(data: GroupAdd):
    try:
        await add_group(data.group_id, data.title, data.username)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/api/groups/remove")
async def api_remove_group(data: GroupAdd):
    await remove_group(data.group_id)
    return {"ok": True}

@app.get("/api/messages")
async def api_messages(group_id: Optional[int] = Query(None), days: int = 7):
    if group_id:
        msgs = await get_messages_by_group(group_id, days)
    else:
        msgs = await get_recent_messages(limit=100)
    return {"messages": msgs}

@app.get("/api/reports")
async def api_reports(days: int = 7):
    return {"reports": await get_reports(days)}

@app.post("/api/reports/generate")
async def api_generate_report(data: GroupAdd):
    try:
        report = await generate_report(data.group_id)
        return {"ok": True, "report": report}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/reports/generate-image")
async def api_generate_report_image(data: ReportImageRequest = ReportImageRequest()):
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
async def api_list_report_images():
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
async def api_setup_daily_cron():
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
async def api_keywords():
    return {"keywords": await get_feedback_keywords()}

@app.post("/api/keywords/add")
async def api_add_keyword(data: KeywordAdd):
    await add_feedback_keyword(data.keyword)
    return {"ok": True}

@app.post("/api/keywords/remove")
async def api_remove_keyword(data: KeywordAdd):
    await remove_feedback_keyword(data.keyword)
    return {"ok": True}

@app.post("/api/config")
async def api_update_config(data: ConfigUpdate):
    await set_config(data.key, data.value)
    return {"ok": True}

@app.get("/api/config")
async def api_get_config(key: str = ""):
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
async def api_bot_info():
    if monitor._bot_module and monitor._bot_module.is_running():
        info = await monitor._bot_module.get_bot_info()
        return {"ok": True, "info": info}
    return {"ok": False, "error": "Bot not running"}

# ─── Telethon Mode API ──────────────────────────────────────────

@app.post("/api/monitor/telethon/start")
async def api_telethon_start(data: TelethonStart):
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
async def api_telethon_stop():
    if monitor._telethon_module:
        await monitor._telethon_module.stop_client()
        monitor.mode = None
        return {"ok": True}
    return {"ok": False, "error": "Telethon not running"}

@app.get("/api/monitor/telethon/dialogs")
async def api_telethon_dialogs():
    dialogs = await monitor.list_dialogs()
    return {"dialogs": dialogs}

# ─── Generic Monitor API ────────────────────────────────────────

@app.post("/api/monitor/stop")
async def api_monitor_stop():
    await monitor.stop()
    return {"ok": True}

@app.get("/api/monitor/status")
async def api_monitor_status():
    return await monitor.get_status()

# ─── Bark API ───────────────────────────────────────────────────

@app.post("/api/bark/test")
async def api_bark_test():
    await send_notification(
        title="🔔 TG Monitor 测试通知",
        body="监控面板已成功配置 Bark 通知！",
        group="tg-monitor-test",
        level="active",
    )
    return {"ok": True}

@app.post("/api/bark/send")
async def api_bark_send(data: ConfigUpdate):
    await send_notification(
        title=data.key,
        body=data.value,
        group="tg-monitor-custom",
        level="active",
    )
    return {"ok": True}
