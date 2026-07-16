"""
TG Monitor - Media Tracker Module
Tracks new movie/TV show releases via TMDB API and sends notifications to groups.
"""
import logging
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger("tg-monitor.media")

TMDB_API_BASE = "https://api.themoviedb.org/3"
POSTER_BASE = "https://image.tmdb.org/t/p/w400"


async def tmdb_get(token: str, endpoint: str, params: dict = None) -> Optional[dict]:
    """Make a request to TMDB API using Bearer token (v4)."""
    if not token:
        return None
    params = params or {}
    params["language"] = "zh-CN"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{TMDB_API_BASE}/{endpoint}",
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                return resp.json()
            logger.warning("TMDB API error: %s %s", resp.status_code, resp.text)
            return None
    except Exception as e:
        logger.error("TMDB request failed: %s", e)
        return None


async def get_trending(token: str, media_type: str = "all", time_window: str = "day") -> list:
    data = await tmdb_get(token, f"trending/{media_type}/{time_window}")
    if not data:
        return []
    results = []
    for item in data.get("results", [])[:10]:
        title = item.get("title") or item.get("name", "未知")
        date = item.get("release_date") or item.get("first_air_date", "")
        results.append({
            "id": item["id"],
            "title": title,
            "type": "电影" if item.get("media_type") == "movie" or item.get("title") else "剧集",
            "overview": (item.get("overview") or "")[:120],
            "date": date,
            "vote": item.get("vote_average", 0),
            "poster": f"{POSTER_BASE}{item['poster_path']}" if item.get("poster_path") else "",
            "url": f"https://www.themoviedb.org/{item.get('media_type', 'movie')}/{item['id']}",
        })
    return results


async def get_now_playing(token: str, page: int = 1) -> list:
    """Get movies now playing in theaters."""
    data = await tmdb_get(token, "movie/now_playing", {"page": page, "region": "CN"})
    if not data:
        return []
    results = []
    for item in data.get("results", [])[:10]:
        results.append({
            "id": item["id"],
            "title": item.get("title", "未知"),
            "type": "电影",
            "overview": (item.get("overview") or "")[:120],
            "date": item.get("release_date", ""),
            "vote": item.get("vote_average", 0),
            "poster": f"{POSTER_BASE}{item['poster_path']}" if item.get("poster_path") else "",
            "url": f"https://www.themoviedb.org/movie/{item['id']}",
        })
    return results


async def get_on_the_air(api_key: str) -> list:
    """Get TV shows airing today."""
    data = await tmdb_get(token, "tv/on_the_air")
    if not data:
        return []
    results = []
    for item in data.get("results", [])[:10]:
        results.append({
            "id": item["id"],
            "title": item.get("name", "未知"),
            "type": "剧集",
            "overview": (item.get("overview") or "")[:120],
            "date": item.get("first_air_date", "") or item.get("last_air_date", ""),
            "vote": item.get("vote_average", 0),
            "poster": f"{POSTER_BASE}{item['poster_path']}" if item.get("poster_path") else "",
            "url": f"https://www.themoviedb.org/tv/{item['id']}",
        })
    return results


def format_media_message(items: list, title: str) -> str:
    """Format media list into a Telegram message."""
    if not items:
        return f"📭 暂无{title}"

    msg = f"🎬 {title}\n{'─'*16}\n"
    for i, item in enumerate(items[:8], 1):
        stars = "⭐" * max(1, round(item["vote"] / 2)) if item["vote"] > 0 else ""
        msg += (
            f"\n{i}. <b>{item['title']}</b>"
            f"\n📅 {item['date'] or '未知'} | {item['type']} {stars}"
        )
        if item["overview"]:
            msg += f"\n💬 {item['overview'][:80]}..."
        msg += f"\n🔗 {item['url']}"
    return msg


def format_media_summary(items: list, title: str) -> str:
    """Format a compact summary for quick viewing."""
    if not items:
        return f"📭 暂无{title}"
    msg = f"🎬 {title}\n"
    for i, item in enumerate(items[:10], 1):
        stars = "⭐" * max(1, round(item["vote"] / 2)) if item["vote"] > 0 else ""
        msg += f"\n{i}. <b>{item['title']}</b> {stars} — {item['date'][:10] if item['date'] else '?'}"
    return msg
