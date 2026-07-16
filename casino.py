"""
TG Monitor - Casino Module
Virtual gambling games for group entertainment.
Balance, dice, slots, coinflip, daily bonus.
"""
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from database import get_db

logger = logging.getLogger("tg-monitor.casino")

DAILY_BONUS = 100
STARTING_BALANCE = 500
MAX_BET = 10000
COOLDOWN_SECONDS = 3  # Anti-spam

# ─── Database ────────────────────────────────────────────────

async def init_casino_db():
    """Create casino tables if not exist."""
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS user_balances (
            user_id     INTEGER PRIMARY KEY,
            group_id    INTEGER NOT NULL,
            username    TEXT DEFAULT '',
            balance     INTEGER DEFAULT 500,
            last_daily  TEXT DEFAULT '',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS gambling_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            group_id    INTEGER NOT NULL,
            game        TEXT NOT NULL,
            bet         INTEGER DEFAULT 0,
            result      TEXT NOT NULL,
            payout      INTEGER DEFAULT 0,
            balance_after INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_gambling_logs_user
            ON gambling_logs(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_gambling_logs_group
            ON gambling_logs(group_id, created_at);
    """)
    await db.commit()


async def _get_or_create_user(user_id: int, group_id: int, username: str = "") -> dict:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM user_balances WHERE user_id=? AND group_id=?",
        (user_id, group_id),
    )
    row = await cursor.fetchone()
    if row:
        if username and row["username"] != username:
            await db.execute(
                "UPDATE user_balances SET username=? WHERE user_id=? AND group_id=?",
                (username, user_id, group_id),
            )
            await db.commit()
        return dict(row)
    # Create new user
    await db.execute(
        "INSERT INTO user_balances (user_id, group_id, username, balance) VALUES (?, ?, ?, ?)",
        (user_id, group_id, username, STARTING_BALANCE),
    )
    await db.commit()
    return {"user_id": user_id, "group_id": group_id, "username": username,
            "balance": STARTING_BALANCE, "last_daily": ""}


async def get_balance(user_id: int, group_id: int) -> int:
    user = await _get_or_create_user(user_id, group_id)
    return user["balance"]


async def _update_balance(user_id: int, group_id: int, delta: int) -> int:
    db = await get_db()
    await db.execute(
        "UPDATE user_balances SET balance = balance + ? WHERE user_id=? AND group_id=?",
        (delta, user_id, group_id),
    )
    await db.commit()
    cursor = await db.execute(
        "SELECT balance FROM user_balances WHERE user_id=? AND group_id=?",
        (user_id, group_id),
    )
    row = await cursor.fetchone()
    return row["balance"] if row else 0


async def _log_game(user_id: int, group_id: int, game: str, bet: int,
                     result: str, payout: int, balance_after: int):
    db = await get_db()
    await db.execute(
        """INSERT INTO gambling_logs (user_id, group_id, game, bet, result, payout, balance_after)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, group_id, game, bet, result, payout, balance_after),
    )
    await db.commit()


async def get_leaderboard(group_id: int, limit: int = 10) -> list:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM user_balances WHERE group_id=? ORDER BY balance DESC LIMIT ?",
        (group_id, limit),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_casino_stats(group_id: int = None) -> dict:
    """Get aggregated casino stats for dashboard."""
    db = await get_db()
    if group_id:
        cursor = await db.execute(
            "SELECT COUNT(*) as total, SUM(bet) as total_bet, SUM(payout) as total_payout FROM gambling_logs WHERE group_id=?",
            (group_id,),
        )
    else:
        cursor = await db.execute(
            "SELECT COUNT(*) as total, SUM(bet) as total_bet, SUM(payout) as total_payout FROM gambling_logs",
        )
    row = await cursor.fetchone()
    return {
        "total_games": row["total"] or 0,
        "total_bet": row["total_bet"] or 0,
        "total_payout": row["total_payout"] or 0,
    }


# ─── Games ───────────────────────────────────────────────────

async def daily_bonus(user_id: int, group_id: int, username: str = "") -> dict:
    """Claim daily bonus."""
    user = await _get_or_create_user(user_id, group_id, username)
    today = datetime.now().strftime("%Y-%m-%d")
    if user["last_daily"] == today:
        return {"ok": False, "msg": "今天已经领过啦，明天再来吧 🎁"}
    bonus = DAILY_BONUS
    # Streak bonus: consecutive days = extra 50%
    balance = await _update_balance(user_id, group_id, bonus)
    db = await get_db()
    await db.execute(
        "UPDATE user_balances SET last_daily=? WHERE user_id=? AND group_id=?",
        (today, user_id, group_id),
    )
    await db.commit()
    await _log_game(user_id, group_id, "daily", 0, f"daily_bonus+{bonus}", bonus, balance)
    return {"ok": True, "bonus": bonus, "balance": balance}


async def coinflip(user_id: int, group_id: int, bet: int, choice: str,
                    username: str = "") -> dict:
    """Coin flip game."""
    user = await _get_or_create_user(user_id, group_id, username)
    if bet < 1 or bet > user["balance"] or bet > MAX_BET:
        return {"ok": False, "msg": "❌ 筹码不足或超出限制"}
    if choice not in ("正面", "反面", "heads", "tails"):
        return {"ok": False, "msg": "请选择 正面 或 反面"}

    flip = random.choice(["正面", "反面"])
    win = (choice in ("正面", "heads") and flip == "正面") or \
          (choice in ("反面", "tails") and flip == "反面")

    if win:
        payout = bet * 2  # 2x
        balance = await _update_balance(user_id, group_id, bet)  # net +bet (bet already deducted? No)
        # Actually: deduct bet first, then add payout
        balance = await _update_balance(user_id, group_id, -bet)
        balance = await _update_balance(user_id, group_id, payout)
        result_text = f"🎉 {flip}！你赢了 {payout} 筹码！"
        await _log_game(user_id, group_id, "coinflip", bet, f"win:{flip}", payout, balance)
    else:
        await _update_balance(user_id, group_id, -bet)
        balance = await get_balance(user_id, group_id)
        result_text = f"😅 {flip}！你输了 {bet} 筹码"
        await _log_game(user_id, group_id, "coinflip", bet, f"lose:{flip}", 0, balance)

    return {"ok": True, "msg": result_text, "balance": balance, "flip": flip}


async def dice(user_id: int, group_id: int, bet: int, guess: str = None,
               username: str = "") -> dict:
    """Dice roll game. Guess: big(4-6), small(1-3), or exact number."""
    user = await _get_or_create_user(user_id, group_id, username)
    if bet < 1 or bet > user["balance"] or bet > MAX_BET:
        return {"ok": False, "msg": "❌ 筹码不足或超出限制"}

    roll = random.randint(1, 6)
    payout = 0
    result_text = ""

    if guess is None:
        # Just roll for fun
        return {"ok": True, "msg": f"🎲 掷出了 {roll}！", "roll": roll}

    if guess in ("大", "big") and roll >= 4:
        payout = int(bet * 1.8)
        result_text = f"🎲 {roll}（大）！你赢了 {payout} 筹码！"
    elif guess in ("小", "small") and roll <= 3:
        payout = int(bet * 1.8)
        result_text = f"🎲 {roll}（小）！你赢了 {payout} 筹码！"
    elif guess.isdigit() and int(guess) == roll:
        payout = bet * 5  # Exact number = 5x
        result_text = f"🎲 猜中 {roll}！5倍奖励！你赢了 {payout} 筹码！"
    else:
        result_text = f"🎲 掷出了 {roll}，你猜错了"

    await _update_balance(user_id, group_id, -bet)
    if payout > 0:
        await _update_balance(user_id, group_id, payout)
    balance = await get_balance(user_id, group_id)
    await _log_game(user_id, group_id, "dice", bet,
                    f"{'win' if payout else 'lose'}:{roll}", payout, balance)
    return {"ok": True, "msg": result_text, "balance": balance, "roll": roll}


async def slot_machine(user_id: int, group_id: int, bet: int,
                        username: str = "") -> dict:
    """Slot machine game. 3 reels with emoji symbols."""
    user = await _get_or_create_user(user_id, group_id, username)
    if bet < 1 or bet > user["balance"] or bet > MAX_BET:
        return {"ok": False, "msg": "❌ 筹码不足或超出限制"}

    symbols = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣", "⭐", "🔔"]
    reels = [random.choice(symbols) for _ in range(3)]
    display = " | ".join(reels)
    payout = 0
    result_text = ""

    if reels[0] == reels[1] == reels[2]:
        # Jackpot! All three match
        multiplier = {"💎": 10, "7️⃣": 8, "⭐": 6, "🔔": 5}
        mult = multiplier.get(reels[0], 3)
        payout = bet * mult
        result_text = f"🎰 {display}\n💰 JACKPOT！{mult}倍！赢了 {payout} 筹码！"
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        # Two match
        payout = int(bet * 1.2)
        result_text = f"🎰 {display}\n✨ 两个相同！小赢 {payout} 筹码"
    else:
        result_text = f"🎰 {display}\n😅 没中，再试试"

    await _update_balance(user_id, group_id, -bet)
    if payout > 0:
        await _update_balance(user_id, group_id, payout)
    balance = await get_balance(user_id, group_id)
    await _log_game(user_id, group_id, "slot", bet,
                    f"{'win' if payout else 'lose'}:{''.join(reels)}", payout, balance)
    return {"ok": True, "msg": result_text, "balance": balance, "reels": display}
