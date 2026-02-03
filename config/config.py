from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value


def _get_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config(require_token: bool = True) -> dict:
    env_path = _project_root() / ".env"
    load_dotenv(env_path)

    account_token = os.getenv("TOKEN", "")
    if require_token and not account_token:
        raise ValueError("TOKEN environment variable is not set")

    return {
        "account_token": account_token,
        "lang": os.getenv("LANG", "zh_CN"),
        "run_time": os.getenv("RUN_TIME", "04:00"),
        "timeout_seconds": _get_int_env("TIMEOUT_SECONDS", 5),
        "base_url": os.getenv("BASE_URL", "https://webapi.leigod.com"),
        "telegram_enabled": _get_bool_env("TELEGRAM_ENABLED", False),
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
        "telegram_poll_seconds": _get_int_env("TELEGRAM_POLL_SECONDS", 0),
        "telegram_poll_time": os.getenv("TELEGRAM_POLL_TIME", "00:00"),
        "token_fetch_url": os.getenv("TOKEN_FETCH_URL", "https://vip.leigod.com/user.html"),
        "token_fetch_timeout_seconds": _get_int_env("TOKEN_FETCH_TIMEOUT_SECONDS", 180),
    }


def update_env_vars(values: dict[str, str]) -> None:
    env_path = _project_root() / ".env"

    lines: list[str] = []
    if env_path.exists():
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []

    updated_keys = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in line:
            new_lines.append(line)
            continue
        name = line.split("=", 1)[0].strip()
        if name in values:
            new_lines.append(f"{name}={values[name]}")
            updated_keys.add(name)
        else:
            new_lines.append(line)

    missing = [key for key in values.keys() if key not in updated_keys]
    if missing:
        if new_lines and new_lines[-1].strip() != "":
            new_lines.append("")
        for key in missing:
            new_lines.append(f"{key}={values[key]}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def write_token_to_env(token: str) -> None:
    update_env_vars({"TOKEN": token})
