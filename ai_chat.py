"""
TG Monitor - AI Chat Module
DeepSeek API integration for real-time group chat AI responses.
Uses OpenAI-compatible API format.
"""
import logging
from typing import Optional

import httpx

logger = logging.getLogger("tg-monitor.ai")

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"

SYSTEM_PROMPT = """你是一个活跃的 Telegram 群聊助手。你在群聊中与用户交流，请保持友好、有趣、有用。
规则：
1. 用中文回复，保持简洁自然
2. 回答要实用，不要过于冗长
3. 如果不确定就直说不知道
4. 可以适当使用 emoji 让回复更生动
5. 回复控制在 200 字以内"""


async def ask_deepseek(
    api_key: str,
    message: str,
    history: list = None,
    system_prompt: str = None,
    model: str = DEFAULT_MODEL,
) -> Optional[str]:
    """Send a message to DeepSeek API and get response."""
    if not api_key:
        logger.warning("DeepSeek API key not configured")
        return None

    messages = [{"role": "system", "content": system_prompt or SYSTEM_PROMPT}]

    # Add conversation history (last 10 messages)
    if history:
        for msg in history[-10:]:
            role = "assistant" if msg.get("is_bot") else "user"
            messages.append({"role": role, "content": msg.get("text", "")})

    # Add current message
    messages.append({"role": "user", "content": message})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": 500,
                    "temperature": 0.7,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                reply = data["choices"][0]["message"]["content"]
                logger.info("DeepSeek response received (%d tokens)", 
                           data.get("usage", {}).get("total_tokens", 0))
                return reply.strip()
            else:
                logger.error("DeepSeek API error: %s %s", resp.status_code, resp.text)
                return None
    except Exception as e:
        logger.error("DeepSeek request failed: %s", e)
        return None
