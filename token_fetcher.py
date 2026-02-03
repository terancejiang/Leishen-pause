from __future__ import annotations

import json
import re
import time
from typing import Optional
from urllib.parse import parse_qs

from playwright.sync_api import sync_playwright


def _extract_token_from_text(text: str) -> Optional[str]:
    if not text:
        return None

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            token = data.get("account_token")
            if token and token != "null":
                return str(token)
    except json.JSONDecodeError:
        pass

    if "account_token=" in text:
        parsed = parse_qs(text, keep_blank_values=True)
        token_list = parsed.get("account_token", [])
        if token_list:
            token = token_list[0]
            if token and token != "null":
                return token

    match = re.search(r"account_token\"?\s*[:=]\s*\"?([A-Za-z0-9_-]{8,})", text)
    if match:
        return match.group(1)

    return None


def fetch_token_with_browser(
    url: str,
    timeout_seconds: int = 180,
) -> str:
    token_holder: dict[str, Optional[str]] = {"token": None}

    def handle_request(request) -> None:
        if "webapi.leigod.com" not in request.url:
            return
        data = request.post_data or ""
        token = _extract_token_from_text(data)
        if token:
            token_holder["token"] = token

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=False)
        except Exception:
            browser = p.chromium.launch(headless=False)

        context = browser.new_context()
        page = context.new_page()
        page.on("request", handle_request)

        page.goto(url)

        start = time.time()
        while time.time() - start < timeout_seconds:
            if token_holder["token"]:
                break
            time.sleep(1)

        browser.close()

    token = token_holder["token"]
    if not token:
        raise TimeoutError("token not detected within timeout")
    return token
