from __future__ import annotations

import json
from typing import Any, Dict

import requests

BASE_URL = "https://webapi.leigod.com"
TIMEOUT_SECONDS = 5
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36 Edg/88.0.705.53",
    "Connection": "keep-alive",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "DNT": "1",
    "Referer": "https://www.legod.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Origin": "https://www.legod.com",
}


def build_payload(account_token: str, lang: str) -> Dict[str, Any]:
    return {
        "account_token": account_token,
        "lang": lang,
    }


def pause(
    account_token: str,
    lang: str,
    base_url: str = BASE_URL,
    timeout_seconds: int = TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    url = f"{base_url}/api/user/pause"
    payload = build_payload(account_token, lang)

    resp = requests.post(
        url,
        json=payload,
        headers={**DEFAULT_HEADERS, "Content-Type": "application/json; charset=UTF-8"},
        timeout=timeout_seconds,
    )
    resp.raise_for_status()

    try:
        return resp.json()
    except json.JSONDecodeError as exc:
        raise ValueError("invalid JSON response") from exc
