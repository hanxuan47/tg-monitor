"""
TG Monitor - Database Layer (Optimized)
SQLite async database with indexes and optimized queries.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import aiosqlite

logger = logging.getLogger("tg-monitor.db")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "monitor.db")

# ─── Connection ──────────────────────────────────────────

_db: Optional[aiosqlite.Connection] = None


async def get_db():
    """Get DB connection with auto-reconnect on failure."""
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA synchronous=NORMAL")
        await _db.execute("PRAGMA cache_size=-8000")  # 8MB cache
        await _db.execute("PRAGMA busy_timeout=5000")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def _get_db_with_retry(max_retries: int = 3):
    """Get DB connection, reconnecting if closed/dead."""
    global _db
    for attempt in range(max_retries):
        try:
            db = await get_db()
            await db.execute("SELECT 1")  # Test connection
            return db
        except Exception as e:
            logger.warning("DB connection failed (attempt %d/%d): %s", attempt + 1, max_retries, e)
            _db = None  # Force reconnect
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(0.5 * (attempt + 1))
    raise RuntimeError("DB unavailable")


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None


# ─── Init with indexes ────────────────────────────────────────

async def init_db():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS groups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id    INTEGER UNIQUE NOT NULL,
            title       TEXT NOT NULL DEFAULT '',
            username    TEXT DEFAULT '',
            member_count INTEGER DEFAULT 0,
            is_active   INTEGER DEFAULT 1,
            added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id    INTEGER NOT NULL,
            sender_id   INTEGER,
            sender_name TEXT DEFAULT '',
            text        TEXT DEFAULT '',
            msg_date    TIMESTAMP,
            is_feedback INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES groups(group_id)
        );

        CREATE INDEX IF NOT EXISTS idx_messages_group_date
            ON messages(group_id, msg_date);

        CREATE INDEX IF NOT EXISTS idx_messages_date
            ON messages(msg_date);

        CREATE INDEX IF NOT EXISTS idx_messages_feedback
            ON messages(is_feedback, msg_date);

        CREATE TABLE IF NOT EXISTS daily_reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id    INTEGER NOT NULL,
            report_date TEXT NOT NULL,
            msg_count   INTEGER DEFAULT 0,
            active_users INTEGER DEFAULT 0,
            feedback_count INTEGER DEFAULT 0,
            summary     TEXT DEFAULT '',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(group_id, report_date)
        );

        CREATE INDEX IF NOT EXISTS idx_reports_date
            ON daily_reports(report_date);

        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS feedback_keywords (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE NOT NULL
        );
    """)
    await db.commit()


# ─── Config helpers (with in-memory cache) ────────────────────

_config_cache: dict = {}
_config_cache_ttl: datetime = datetime.min
_CONFIG_CACHE_TTL_SECONDS = 60  # config rarely changes


async def get_config(key: str, default: str = "") -> str:
    global _config_cache, _config_cache_ttl

    if key in _config_cache and (datetime.now() - _config_cache_ttl).seconds < _CONFIG_CACHE_TTL_SECONDS:
        return _config_cache[key]

    db = await _get_db_with_retry()
    cursor = await db.execute("SELECT value FROM config WHERE key=?", (key,))
    row = await cursor.fetchone()
    value = row["value"] if row else default

    _config_cache[key] = value
    _config_cache_ttl = datetime.now()
    return value


async def set_config(key: str, value: str):
    global _config_cache
    db = await _get_db_with_retry()
    await db.execute(
        "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=?",
        (key, value, value),
    )
    await db.commit()
    _config_cache[key] = value  # update cache immediately


# ─── Config batch read ────────────────────────────────────────

async def get_config_batch(keys: list[str]) -> dict:
    """Read multiple config values in one query."""
    db = await get_db()
    placeholders = ",".join("?" for _ in keys)
    cursor = await db.execute(
        f"SELECT key, value FROM config WHERE key IN ({placeholders})", keys
    )
    rows = await cursor.fetchall()
    result = {r["key"]: r["value"] for r in rows}
    for k in keys:
        if k not in result:
            result[k] = ""
    return result


# ─── Group helpers ─────────────────────────────────────────────

async def add_group(group_id: int, title: str, username: str = "", member_count: int = 0):
    db = await get_db()
    await db.execute(
        """INSERT INTO groups (group_id, title, username, member_count)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(group_id) DO UPDATE SET
               title=excluded.title,
               username=excluded.username,
               member_count=excluded.member_count,
               is_active=1""",
        (group_id, title, username, member_count),
    )
    await db.commit()


async def remove_group(group_id: int):
    db = await get_db()
    await db.execute("UPDATE groups SET is_active=0 WHERE group_id=?", (group_id,))
    await db.commit()


async def get_groups(active_only: bool = True) -> list:
    db = await get_db()
    if active_only:
        cursor = await db.execute("SELECT * FROM groups WHERE is_active=1 ORDER BY title")
    else:
        cursor = await db.execute("SELECT * FROM groups ORDER BY title")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ─── Message helpers ───────────────────────────────────────────

async def save_message(group_id: int, sender_id: int, sender_name: str,
                        text: str, msg_date: datetime, is_feedback: bool = False):
    db = await get_db()
    await db.execute(
        """INSERT INTO messages (group_id, sender_id, sender_name, text, msg_date, is_feedback)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (group_id, sender_id, sender_name, text, msg_date.isoformat(), 1 if is_feedback else 0),
    )
    await db.commit()


async def get_recent_messages(limit: int = 50) -> list:
    db = await get_db()
    cursor = await db.execute(
        """SELECT m.*, g.title as group_title
           FROM messages m
           JOIN groups g ON m.group_id = g.group_id
           ORDER BY m.msg_date DESC LIMIT ?""",
        (limit,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_messages_by_group(group_id: int, days: int = 7) -> list:
    db = await get_db()
    since = (datetime.now() - timedelta(days=days)).isoformat()
    cursor = await db.execute(
        """SELECT * FROM messages
           WHERE group_id=? AND msg_date >= ?
           ORDER BY msg_date DESC""",
        (group_id, since),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ─── Feedback keywords ─────────────────────────────────────────

async def get_feedback_keywords() -> list[str]:
    db = await get_db()
    cursor = await db.execute("SELECT keyword FROM feedback_keywords")
    rows = await cursor.fetchall()
    return [r["keyword"] for r in rows]


async def add_feedback_keyword(keyword: str):
    db = await get_db()
    try:
        await db.execute("INSERT INTO feedback_keywords (keyword) VALUES (?)", (keyword,))
        await db.commit()
    except aiosqlite.IntegrityError:
        pass


async def remove_feedback_keyword(keyword: str):
    db = await get_db()
    await db.execute("DELETE FROM feedback_keywords WHERE keyword=?", (keyword,))
    await db.commit()


# ─── Daily reports (optimized single-query) ───────────────────

async def generate_report(group_id: int) -> dict:
    """Generate a daily summary report using optimized queries."""
    today = datetime.now().strftime("%Y-%m-%d")
    since = f"{today}T00:00:00"

    db = await get_db()

    # Single query for all stats
    cursor = await db.execute(
        """SELECT
               COUNT(*) as msg_count,
               COUNT(DISTINCT sender_id) as active_users,
               SUM(is_feedback) as feedback_count
           FROM messages
           WHERE group_id=? AND msg_date >= ?""",
        (group_id, since),
    )
    stats = await cursor.fetchone()
    msg_count = stats["msg_count"]
    active_users = stats["active_users"]
    feedback_count = stats["feedback_count"] or 0

    # Get group title
    cursor = await db.execute("SELECT title FROM groups WHERE group_id=?", (group_id,))
    group_row = await cursor.fetchone()
    group_title = group_row["title"] if group_row else f"Group {group_id}"

    # Get latest messages for summary (limit 3)
    cursor = await db.execute(
        """SELECT text, sender_name FROM messages
           WHERE group_id=? AND msg_date >= ?
           ORDER BY msg_date DESC LIMIT 3""",
        (group_id, since),
    )
    latest = await cursor.fetchall()
    recent_lines = "\n".join(
        f"  • {r['sender_name']}: {r['text'][:80]}" for r in latest
    )

    summary = (
        f"📊 {group_title} — {today}\n"
        f"   💬 消息: {msg_count} | 👥 活跃用户: {active_users} | 📩 反馈: {feedback_count}\n"
        f"   📝 最近消息:\n{recent_lines}"
    )

    await db.execute(
        """INSERT INTO daily_reports (group_id, report_date, msg_count, active_users, feedback_count, summary)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(group_id, report_date) DO UPDATE SET
               msg_count=excluded.msg_count,
               active_users=excluded.active_users,
               feedback_count=excluded.feedback_count,
               summary=excluded.summary""",
        (group_id, today, msg_count, active_users, feedback_count, summary),
    )
    await db.commit()

    return {
        "group_id": group_id,
        "group_title": group_title,
        "date": today,
        "msg_count": msg_count,
        "active_users": active_users,
        "feedback_count": feedback_count,
        "summary": summary,
    }


async def get_reports(days: int = 7) -> list:
    db = await get_db()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    cursor = await db.execute(
        """SELECT r.*, g.title as group_title
           FROM daily_reports r
           JOIN groups g ON r.group_id = g.group_id
           WHERE r.report_date >= ?
           ORDER BY r.report_date DESC, g.title""",
        (since,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ─── Stats (optimized single-query) ──────────────────────────

async def get_overview_stats() -> dict:
    db = await get_db()

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM groups WHERE is_active=1")
    total_groups = (await cursor.fetchone())["cnt"]

    cursor = await db.execute(
        """SELECT
               COUNT(*) as today_msgs,
               COUNT(DISTINCT group_id) as active_groups,
               COALESCE(SUM(is_feedback), 0) as today_feedback
           FROM messages
           WHERE msg_date >= datetime('now', '-24 hours')"""
    )
    today = await cursor.fetchone()

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM messages")
    total_msgs = (await cursor.fetchone())["cnt"]

    return {
        "total_groups": total_groups,
        "active_groups": today["active_groups"],
        "today_msgs": today["today_msgs"],
        "today_feedback": today["today_feedback"],
        "total_msgs": total_msgs,
    }


async def get_activity_timeline(hours: int = 24) -> list:
    db = await get_db()
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    cursor = await db.execute(
        """SELECT strftime('%Y-%m-%d %H:00', msg_date) as hour,
                  COUNT(*) as cnt
           FROM messages
           WHERE msg_date >= ?
           GROUP BY hour
           ORDER BY hour""",
        (since,),
    )
    rows = await cursor.fetchall()
    return [{"hour": r["hour"], "count": r["cnt"]} for r in rows]
