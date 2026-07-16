"""
TG Monitor - AI Chat Module
OpenAI-compatible API integration (DeepSeek, Xiaomi, OpenAI, etc.)
"""
import logging

import httpx

logger = logging.getLogger("tg-monitor.ai")


async def ask_ai(
    api_key: str,
    api_url: str,
    model: str,
    message: str,
    history: list = None,
    system_prompt: str = None,
) -> Optional[str]:
    """Send a message to any OpenAI-compatible API and get response."""
    if not api_key or not api_url:
        logger.warning("AI API not configured")
        return None

    # Ensure URL ends with /chat/completions
    if not api_url.endswith("/chat/completions"):
        api_url = api_url.rstrip("/") + "/chat/completions"

    messages = [{"role": "system", "content": system_prompt or _default_prompt()}]

    if history:
        for msg in history[-10:]:
            role = "assistant" if msg.get("is_bot") else "user"
            messages.append({"role": role, "content": msg.get("text", "")})

    messages.append({"role": "user", "content": message})

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": 1000,
                    "temperature": 0.7,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                reply = data["choices"][0]["message"]["content"]
                logger.info("AI response received (%d tokens)",
                           data.get("usage", {}).get("total_tokens", 0))
                return reply.strip()
            else:
                logger.error("AI API error: %s %s", resp.status_code, resp.text)
                return None
    except Exception as e:
        logger.error("AI request failed: %s", e)
        return None


def _default_prompt() -> str:
    return """你是一个活跃的 Telegram 群聊助手。你在群聊中与用户交流，请保持友好、有趣、有用。
规则：
1. 用中文回复，保持简洁自然
2. 回答要实用，不要过于冗长
3. 如果不确定就直说不知道
4. 可以适当使用 emoji 让回复更生动
5. 回复控制在 200 字以内"""
