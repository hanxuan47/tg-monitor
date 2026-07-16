"""
TG Monitor - Report Image Generator
Creates beautiful summary images for daily group chat reports.
Designed to look clean on mobile (Bark notifications) and desktop.
"""
import io
import logging
import os
from datetime import datetime
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger("tg-monitor.report-img")

# Color scheme — dark theme matching dashboard
COLORS = {
    "bg_dark": (15, 17, 23),
    "bg_card": (30, 32, 56),
    "border": (45, 49, 84),
    "text_primary": (232, 234, 240),
    "text_secondary": (139, 143, 163),
    "text_muted": (92, 96, 128),
    "accent_blue": (91, 141, 239),
    "accent_green": (76, 217, 100),
    "accent_orange": (255, 149, 0),
    "accent_red": (255, 71, 87),
    "accent_purple": (168, 85, 247),
    "accent_cyan": (34, 211, 238),
}

WIDTH = 800
PADDING = 32
CARD_GAP = 16
CARD_RADIUS = 16

_fonts_loaded = False
_font_large = None
_font_medium = None
_font_small = None
_font_bold = None
_font_emoji = None
_font_file_cached = None  # Cache found font path


def _find_font():
    """Find a suitable CJK font and cache the result."""
    global _font_file_cached
    if _font_file_cached:
        return _font_file_cached

    font_paths = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]

    for fp in font_paths:
        if os.path.exists(fp):
            _font_file_cached = fp
            return fp

    # Search system for any CJK font (cached after first run)
    try:
        import subprocess
        result = subprocess.run(
            ["fc-list", ":lang=zh", "file"],
            capture_output=True, text=True, timeout=5
        )
        lines = [l.strip() for l in result.stdout.split("\n") if l.strip()]
        if lines:
            font_file = lines[0].split(":")[0]
            if os.path.exists(font_file):
                _font_file_cached = font_file
                return font_file
    except Exception:
        pass

    # Last resort
    _font_file_cached = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return _font_file_cached


def _load_fonts():
    """Load fonts once, reusing cached font path."""
    global _fonts_loaded, _font_large, _font_medium, _font_small, _font_bold

    if _fonts_loaded:
        return

    font_file = _find_font()
    if not font_file or not os.path.exists(font_file):
        font_file = None

    try:
        if font_file:
            _font_large = ImageFont.truetype(font_file, 36)
            _font_medium = ImageFont.truetype(font_file, 24)
            _font_small = ImageFont.truetype(font_file, 18)
            _font_bold = ImageFont.truetype(font_file, 28)
            logger.info("Loaded font: %s", font_file)
        else:
            raise OSError("No font file")
    except Exception as e:
        logger.warning("Font load failed, using default: %s", e)
        _font_large = ImageFont.load_default()
        _font_medium = ImageFont.load_default()
        _font_small = ImageFont.load_default()
        _font_bold = ImageFont.load_default()

    _fonts_loaded = True


def _draw_rounded_rect(draw, xy, radius, fill, outline=None, outline_width=1):
    """Draw a rounded rectangle."""
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline or None, width=outline_width if outline else 0)


def _draw_stat_card(draw, x, y, width, icon, label, value, accent_color):
    """Draw a single stat card."""
    card_h = 80
    _draw_rounded_rect(draw, (x, y, x + width, y + card_h), CARD_RADIUS, fill=COLORS["bg_card"])

    # Gradient-like accent line on the left
    draw.rounded_rectangle(
        [x + 2, y + 8, x + 4, y + card_h - 8], 2,
        fill=accent_color
    )

    # Icon
    try:
        draw.text((x + 16, y + 12), icon, fill=accent_color, font=_font_small)
    except Exception:
        pass

    # Label
    draw.text((x + 16, y + 38), label, fill=COLORS["text_muted"], font=_font_small)

    # Value
    draw.text((x + 16, y + 52), str(value), fill=accent_color, font=_font_large)


# Cache generated report images in memory (key: group_id+date, value: bytes)
_report_image_cache: dict = {}



def generate_report_image(
    group_title: str,
    report_date: str,
    msg_count: int,
    active_users: int,
    feedback_count: int,
    top_messages: list = None,
) -> Optional[bytes]:
    """Generate a report image. Returns cached result if same data."""
    cache_key = f"{group_title}:{report_date}:{msg_count}:{active_users}:{feedback_count}"
    cached = _report_image_cache.get(cache_key)
    if cached:
        return cached

    try:
        _load_fonts()
    except Exception as e:
        logger.error("Font loading failed: %s", e)
        return None

    top_messages = top_messages or []

    # Calculate height based on content
    base_height = 460
    extra_height = len(top_messages) * 28
    height = base_height + extra_height

    img = Image.new("RGB", (WIDTH, height), COLORS["bg_dark"])
    draw = ImageDraw.Draw(img)

    y = 0

    # ── Header ──
    header_h = 100
    _draw_rounded_rect(draw, (PADDING, PADDING, WIDTH - PADDING, PADDING + header_h),
                       CARD_RADIUS, fill=COLORS["bg_card"])

    # Logo accent bar
    draw.rounded_rectangle([PADDING + 20, PADDING + 20, PADDING + 24, PADDING + 56],
                           4, fill=COLORS["accent_blue"])
    try:
        draw.text((PADDING + 36, PADDING + 24), "📊 TG Monitor", fill=COLORS["accent_blue"], font=_font_medium)
    except Exception:
        draw.text((PADDING + 36, PADDING + 28), "TG Monitor", fill=COLORS["accent_blue"], font=_font_medium)
    draw.text((PADDING + 36, PADDING + 52), "群聊日报", fill=COLORS["text_secondary"], font=_font_small)

    # Date badge
    date_text = report_date
    date_bbox = draw.textbbox((0, 0), date_text, font=_font_small)
    date_w = date_bbox[2] - date_bbox[0] + 24
    date_x = WIDTH - PADDING - date_w - 16
    _draw_rounded_rect(draw, (date_x, PADDING + 20, date_x + date_w, PADDING + 52),
                       12, fill=COLORS["accent_blue"] + (40,))
    draw.text((date_x + 12, PADDING + 26), date_text, fill=COLORS["accent_blue"], font=_font_small)

    y = PADDING + header_h + CARD_GAP

    # ── Group title bar ──
    title_h = 50
    _draw_rounded_rect(draw, (PADDING, y, WIDTH - PADDING, y + title_h),
                       CARD_RADIUS, fill=COLORS["bg_card"])

    try:
        draw.text((PADDING + 20, y + 14), f"📋  {group_title}", fill=COLORS["text_primary"], font=_font_small)
    except Exception:
        draw.text((PADDING + 20, y + 14), group_title, fill=COLORS["text_primary"], font=_font_small)

    y += title_h + CARD_GAP

    # ── Stats row ──
    stat_w = (WIDTH - 2 * PADDING - 2 * CARD_GAP) // 3
    stats = [
        ("💬", "消息数", msg_count, COLORS["accent_blue"]),
        ("👥", "活跃用户", active_users, COLORS["accent_green"]),
        ("📩", "反馈数", feedback_count, COLORS["accent_orange"]),
    ]
    for i, (icon, label, value, color) in enumerate(stats):
        sx = PADDING + i * (stat_w + CARD_GAP)
        _draw_stat_card(draw, sx, y, stat_w, icon, label, value, color)

    y += 80 + CARD_GAP

    # ── Activity bar ──
    bar_h = 60
    _draw_rounded_rect(draw, (PADDING, y, WIDTH - PADDING, y + bar_h),
                       CARD_RADIUS, fill=COLORS["bg_card"])

    # Activity level bar
    total = max(msg_count, 1)
    bar_full_w = WIDTH - 2 * PADDING - 40
    bar_inner_x = PADDING + 20
    bar_inner_y = y + 18
    bar_inner_h = 24

    draw.rounded_rectangle([bar_inner_x, bar_inner_y, bar_inner_x + bar_full_w, bar_inner_y + bar_inner_h],
                           radius=12, fill=COLORS["border"])

    # Fill bar proportionally
    fill_w = int(bar_full_w * min(total / 100, 1.0))
    if fill_w > 0:
        draw.rounded_rectangle([bar_inner_x, bar_inner_y, bar_inner_x + fill_w, bar_inner_y + bar_inner_h],
                               radius=12, fill=COLORS["accent_blue"])

    draw.text((bar_inner_x + 8, bar_inner_y + 2), f"{msg_count} 条消息", fill="white", font=_font_small)

    y += bar_h + CARD_GAP

    # ── Top messages ──
    if top_messages:
        msg_header_h = 36
        _draw_rounded_rect(draw, (PADDING, y, WIDTH - PADDING, y + msg_header_h),
                           CARD_RADIUS, fill=COLORS["bg_card"])
        draw.text((PADDING + 20, y + 8), "📝 热门口碑", fill=COLORS["text_secondary"], font=_font_small)
        y += msg_header_h + 4

        for msg in top_messages[:5]:
            sender = msg.get("sender_name", "用户")
            text = msg.get("text", "")[:60]
            item_h = 28

            bg = COLORS["bg_card"]
            draw.rounded_rectangle([PADDING, y, WIDTH - PADDING, y + item_h],
                                   radius=6, fill=bg)

            draw.text((PADDING + 20, y + 4), f"{sender}:", fill=COLORS["accent_cyan"], font=_font_small)
            name_w = draw.textbbox((0, 0), f"{sender}:", font=_font_small)[2]
            draw.text((PADDING + 24 + name_w, y + 4), text, fill=COLORS["text_primary"], font=_font_small)

            y += item_h + 2
        y += 4

    # ── Footer ──
    footer_y = height - 50
    draw.text((PADDING, footer_y), "由 TG Monitor 自动生成", fill=COLORS["text_muted"], font=_font_small)

    # Timestamp
    now_str = datetime.now().strftime("%H:%M")
    draw.text((WIDTH - PADDING - 100, footer_y), now_str, fill=COLORS["text_muted"], font=_font_small)

    # Output to bytes with optimized compression
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True, compress_level=9)
    buf.seek(0)
    result = buf.getvalue()
    logger.info("Report image: %dx%d, %.1fKB", WIDTH, height, len(result) / 1024)

    # Cache result
    _report_image_cache[cache_key] = result
    # Limit cache size
    if len(_report_image_cache) > 50:
        _report_image_cache.clear()
    return result


def generate_multi_group_report(
    reports_data: list,
    report_date: str,
) -> Optional[bytes]:
    """Generate a multi-group summary report image with caching."""
    # Build cache key from all data
    cache_parts = [report_date]
    for r in reports_data:
        cache_parts.append(f"{r.get('group_id','')}:{r.get('msg_count',0)}")
    cache_key = "multi:" + "|".join(cache_parts)
    cached = _report_image_cache.get(cache_key)
    if cached:
        return cached

    try:
        _load_fonts()
    except Exception as e:
        logger.error("Font loading failed: %s", e)
        return None

    n_groups = len(reports_data)
    height = 200 + n_groups * 120 + 60

    img = Image.new("RGB", (WIDTH, height), COLORS["bg_dark"])
    draw = ImageDraw.Draw(img)

    y = PADDING

    # Header
    header_h = 80
    _draw_rounded_rect(draw, (PADDING, y, WIDTH - PADDING, y + header_h),
                       CARD_RADIUS, fill=COLORS["bg_card"])
    draw.rounded_rectangle([PADDING + 20, y + 16, PADDING + 24, y + 52],
                           4, fill=COLORS["accent_blue"])
    try:
        draw.text((PADDING + 36, y + 18), "📊 TG Monitor 汇总日报", fill=COLORS["accent_blue"], font=_font_medium)
    except Exception:
        draw.text((PADDING + 36, y + 22), "TG Monitor 汇总日报", fill=COLORS["accent_blue"], font=_font_medium)
    draw.text((PADDING + 36, y + 48), report_date, fill=COLORS["text_secondary"], font=_font_small)
    y += header_h + CARD_GAP

    # Total stats
    total_msgs = sum(r.get("msg_count", 0) for r in reports_data)
    total_users = sum(r.get("active_users", 0) for r in reports_data)
    total_fb = sum(r.get("feedback_count", 0) for r in reports_data)

    summary_h = 50
    _draw_rounded_rect(draw, (PADDING, y, WIDTH - PADDING, y + summary_h),
                       CARD_RADIUS, fill=COLORS["bg_card"])
    summary_text = f"📊 总计: {n_groups} 个群组  |  💬 {total_msgs} 条消息  |  👥 {total_users} 活跃用户  |  📩 {total_fb} 条反馈"
    draw.text((PADDING + 20, y + 14), summary_text, fill=COLORS["text_primary"], font=_font_small)
    y += summary_h + CARD_GAP

    # Per-group cards
    colors_cycle = [COLORS["accent_blue"], COLORS["accent_green"], COLORS["accent_orange"], COLORS["accent_purple"]]
    for idx, r in enumerate(reports_data):
        g_title = r.get("group_title", "未知群组")
        g_msgs = r.get("msg_count", 0)
        g_users = r.get("active_users", 0)
        g_fb = r.get("feedback_count", 0)
        accent = colors_cycle[idx % len(colors_cycle)]

        card_h = 100
        _draw_rounded_rect(draw, (PADDING, y, WIDTH - PADDING, y + card_h),
                           CARD_RADIUS, fill=COLORS["bg_card"])

        # Accent bar
        draw.rounded_rectangle([PADDING + 2, y + 8, PADDING + 4, y + card_h - 8],
                               2, fill=accent)

        # Group icon
        try:
            draw.text((PADDING + 16, y + 18), "👥", fill=accent, font=_font_small)
        except Exception:
            pass

        draw.text((PADDING + 16, y + 46), g_title, fill=COLORS["text_primary"], font=_font_medium)

        # Mini stats row
        stats_x = PADDING + 200
        stats_y = y + 24
        mini_items = [
            (f"💬 {g_msgs}", COLORS["accent_blue"]),
            (f"👥 {g_users}", COLORS["accent_green"]),
            (f"📩 {g_fb}", COLORS["accent_orange"]),
        ]
        sx = stats_x
        for text, color in mini_items:
            draw.text((sx, stats_y), text, fill=color, font=_font_small)
            text_w = draw.textbbox((0, 0), text, font=_font_small)[2] + 24
            sx += text_w

        y += card_h + 8

    # Footer
    draw.text((PADDING, height - 40), "由 TG Monitor 自动生成", fill=COLORS["text_muted"], font=_font_small)
    draw.text((WIDTH - PADDING - 100, height - 40),
              datetime.now().strftime("%H:%M"), fill=COLORS["text_muted"], font=_font_small)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True, compress_level=9)
    buf.seek(0)
    result = buf.getvalue()
    logger.info("Multi-group report: %dx%d, %.1fKB", WIDTH, height, len(result) / 1024)

    _report_image_cache[cache_key] = result
    if len(_report_image_cache) > 50:
        _report_image_cache.clear()
    return result
