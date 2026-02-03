from __future__ import annotations

from typing import Any, Dict, Optional

import requests


def send_telegram_message(
    bot_token: str,
    chat_id: str,
    text: str,
    timeout_seconds: int = 5,
) -> Dict[str, Any]:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }

    resp = requests.post(url, json=payload, timeout=timeout_seconds)
    resp.raise_for_status()
    return resp.json()


def get_updates(
    bot_token: str,
    offset: Optional[int] = None,
    timeout_seconds: int = 5,
) -> Dict[str, Any]:
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    params: Dict[str, Any] = {"timeout": 0}
    if offset is not None:
        params["offset"] = offset

    resp = requests.get(url, params=params, timeout=timeout_seconds)
    resp.raise_for_status()
    return resp.json()
