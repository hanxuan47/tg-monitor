"""
TG Monitor - Database Layer
SQLite async database for storing groups, messages, config, and reports.
"""
import aiosqlite
import json
import os
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "monitor.db")


async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


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
    await db.close()


# ─── Config helpers ──────────────────────────────────────────────

async def get_config(key: str, default: str = "") -> str:
    db = await get_db()
    cursor = await db.execute("SELECT value FROM config WHERE key=?", (key,))
    row = await cursor.fetchone()
    await db.close()
    return row["value"] if row else default


async def set_config(key: str, value: str):
    db = await get_db()
    await db.execute(
        "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=?",
        (key, value, value),
    )
    await db.commit()
    await db.close()


# ─── Group helpers ───────────────────────────────────────────────

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
    await db.close()


async def remove_group(group_id: int):
    db = await get_db()
    await db.execute("UPDATE groups SET is_active=0 WHERE group_id=?", (group_id,))
    await db.commit()
    await db.close()


async def get_groups(active_only: bool = True) -> list:
    db = await get_db()
    if active_only:
        cursor = await db.execute("SELECT * FROM groups WHERE is_active=1 ORDER BY title")
    else:
        cursor = await db.execute("SELECT * FROM groups ORDER BY title")
    rows = await cursor.fetchall()
    await db.close()
    return [dict(r) for r in rows]


# ─── Message helpers ─────────────────────────────────────────────

async def save_message(group_id: int, sender_id: int, sender_name: str,
                        text: str, msg_date: datetime, is_feedback: bool = False):
    db = await get_db()
    await db.execute(
        """INSERT INTO messages (group_id, sender_id, sender_name, text, msg_date, is_feedback)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (group_id, sender_id, sender_name, text, msg_date.isoformat(), 1 if is_feedback else 0),
    )
    await db.commit()
    await db.close()


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
    await db.close()
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
    await db.close()
    return [dict(r) for r in rows]


# ─── Feedback keywords ──────────────────────────────────────────

async def get_feedback_keywords() -> list[str]:
    db = await get_db()
    cursor = await db.execute("SELECT keyword FROM feedback_keywords")
    rows = await cursor.fetchall()
    await db.close()
    return [r["keyword"] for r in rows]


async def add_feedback_keyword(keyword: str):
    db = await get_db()
    try:
        await db.execute("INSERT INTO feedback_keywords (keyword) VALUES (?)", (keyword,))
        await db.commit()
    except aiosqlite.IntegrityError:
        pass
    await db.close()


async def remove_feedback_keyword(keyword: str):
    db = await get_db()
    await db.execute("DELETE FROM feedback_keywords WHERE keyword=?", (keyword,))
    await db.commit()
    await db.close()


# ─── Daily reports ──────────────────────────────────────────────

async def generate_report(group_id: int):
    """Generate a daily summary report for a group."""
    today = datetime.now().strftime("%Y-%m-%d")
    since = f"{today}T00:00:00"

    db = await get_db()

    # Count messages today
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM messages WHERE group_id=? AND msg_date >= ?",
        (group_id, since),
    )
    msg_count = (await cursor.fetchone())["cnt"]

    # Count active users
    cursor = await db.execute(
        "SELECT COUNT(DISTINCT sender_id) as cnt FROM messages WHERE group_id=? AND msg_date >= ?",
        (group_id, since),
    )
    active_users = (await cursor.fetchone())["cnt"]

    # Count feedback
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM messages WHERE group_id=? AND msg_date >= ? AND is_feedback=1",
        (group_id, since),
    )
    feedback_count = (await cursor.fetchone())["cnt"]

    # Get group title
    cursor = await db.execute("SELECT title FROM groups WHERE group_id=?", (group_id,))
    group_row = await cursor.fetchone()
    group_title = group_row["title"] if group_row else f"Group {group_id}"

    # Get latest messages for summary
    cursor = await db.execute(
        "SELECT text, sender_name FROM messages WHERE group_id=? AND msg_date >= ? ORDER BY msg_date DESC LIMIT 5",
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
    await db.close()

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
    await db.close()
    return [dict(r) for r in rows]


# ─── Stats helpers ──────────────────────────────────────────────

async def get_overview_stats() -> dict:
    db = await get_db()

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM groups WHERE is_active=1")
    total_groups = (await cursor.fetchone())["cnt"]

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM messages WHERE msg_date >= datetime('now', '-24 hours')")
    today_msgs = (await cursor.fetchone())["cnt"]

    cursor = await db.execute("SELECT COUNT(DISTINCT group_id) as cnt FROM messages WHERE msg_date >= datetime('now', '-24 hours')")
    active_groups = (await cursor.fetchone())["cnt"]

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM messages WHERE is_feedback=1 AND msg_date >= datetime('now', '-24 hours')")
    today_feedback = (await cursor.fetchone())["cnt"]

    cursor = await db.execute("SELECT COUNT(*) as cnt FROM messages")
    total_msgs = (await cursor.fetchone())["cnt"]

    await db.close()
    return {
        "total_groups": total_groups,
        "active_groups": active_groups,
        "today_msgs": today_msgs,
        "today_feedback": today_feedback,
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
    await db.close()
    return [{"hour": r["hour"], "count": r["cnt"]} for r in rows]
