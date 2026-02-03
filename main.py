from __future__ import annotations

import argparse
import atexit
import os
import signal
import sys
from datetime import datetime, time as dt_time, timedelta
import time

import portalocker

from api.client import pause
from app_logging import get_logger, setup_logging
from config.config import load_config, update_env_vars
from telegram_notify import get_updates, send_telegram_message
from token_fetcher import fetch_token_with_browser


LOCK_HANDLE = None


def _parse_time_value(value: str, name: str) -> dt_time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise ValueError(f"{name} must be in HH:MM 24-hour format") from exc


def _parse_run_time(value: str) -> dt_time:
    return _parse_time_value(value, "RUN_TIME")


def _seconds_until(target_time: dt_time) -> tuple[float, datetime]:
    now = datetime.now()
    target = datetime.combine(now.date(), target_time)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds(), target


def _pause_with_token(logger, cfg: dict, token: str) -> dict:
    logger.info(cfg["base_url"])
    return pause(
        token,
        cfg["lang"],
        base_url=cfg["base_url"],
        timeout_seconds=cfg["timeout_seconds"],
    )


def _notify(logger, cfg: dict, message: str) -> None:
    if not cfg.get("telegram_enabled"):
        return
    bot_token = cfg.get("telegram_bot_token", "")
    chat_id = cfg.get("telegram_chat_id", "")
    if not bot_token or not chat_id:
        logger.warning("telegram enabled but BOT_TOKEN/CHAT_ID missing")
        return
    try:
        send_telegram_message(
            bot_token,
            chat_id,
            message,
            timeout_seconds=cfg["timeout_seconds"],
        )
    except Exception as exc:
        logger.warning("telegram notify failed: %s", exc)


def _poll_telegram_for_token(logger, cfg: dict, state: dict) -> None:
    if not cfg.get("telegram_enabled"):
        return
    bot_token = cfg.get("telegram_bot_token", "")
    chat_id = cfg.get("telegram_chat_id", "")
    if not bot_token or not chat_id:
        return

    offset = state.get("offset")
    try:
        resp = get_updates(bot_token, offset=offset, timeout_seconds=cfg["timeout_seconds"])
    except Exception as exc:
        logger.warning("telegram getUpdates failed: %s", exc)
        return

    if not resp.get("ok"):
        logger.warning("telegram getUpdates returned ok=false")
        return

    updates = resp.get("result", [])
    if not updates:
        return

    max_update_id = None
    for update in updates:
        update_id = update.get("update_id")
        if update_id is not None:
            max_update_id = update_id if max_update_id is None else max(max_update_id, update_id)

        message = update.get("message") or update.get("edited_message")
        if not message:
            continue

        from_chat_id = str(message.get("chat", {}).get("id", ""))
        if from_chat_id != str(chat_id):
            continue

        text = (message.get("text") or "").strip()
        if not text:
            continue

        if text.startswith("/token"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                _notify(logger, cfg, "Usage: /token <new_token>")
                continue

            new_token = parts[1].strip()
            update_env_vars({"TOKEN": new_token})
            cfg["account_token"] = new_token
            logger.info("token updated via telegram")
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _notify(logger, cfg, f"TOKEN updated at {now_str}.")

    if max_update_id is not None:
        state["offset"] = max_update_id + 1


def _sleep_with_poll(logger, cfg: dict, total_seconds: float, state: dict) -> None:
    if not cfg.get("telegram_enabled"):
        time.sleep(total_seconds)
        return

    poll_seconds = int(cfg.get("telegram_poll_seconds", 0))
    poll_time_value = cfg.get("telegram_poll_time", "")
    poll_time = None
    if poll_time_value and poll_seconds <= 0:
        try:
            poll_time = _parse_time_value(poll_time_value, "TELEGRAM_POLL_TIME")
        except ValueError as exc:
            logger.warning("invalid TELEGRAM_POLL_TIME: %s", exc)
            poll_time = None

    next_poll_at = None
    if poll_time:
        now = datetime.now()
        next_poll_at = datetime.combine(now.date(), poll_time)
        if next_poll_at <= now:
            next_poll_at += timedelta(days=1)

    remaining = total_seconds
    while remaining > 0:
        step = remaining

        if next_poll_at is not None:
            now = datetime.now()
            seconds_until_poll = (next_poll_at - now).total_seconds()
            if seconds_until_poll <= 0:
                _poll_telegram_for_token(logger, cfg, state)
                next_poll_at += timedelta(days=1)
                continue
            step = min(step, seconds_until_poll)
        elif poll_seconds > 0:
            step = min(step, poll_seconds)

        time.sleep(step)
        remaining -= step

        if next_poll_at is not None:
            now = datetime.now()
            if now >= next_poll_at:
                _poll_telegram_for_token(logger, cfg, state)
                next_poll_at += timedelta(days=1)
        elif poll_seconds > 0:
            _poll_telegram_for_token(logger, cfg, state)


def _fetch_token_interactive(logger, cfg: dict) -> int:
    logger.info("opening browser to fetch token")
    try:
        token = fetch_token_with_browser(
            cfg["token_fetch_url"],
            timeout_seconds=cfg["token_fetch_timeout_seconds"],
        )
    except Exception as exc:
        logger.error("failed to fetch token: %s", exc)
        _notify(logger, cfg, f"Token fetch failed: {exc}")
        return 1

    update_env_vars({"TOKEN": token})
    cfg["account_token"] = token
    logger.info("token fetched and saved to .env")
    _notify(logger, cfg, "Token fetched and saved.")
    return 0

def _ensure_telegram_config(logger, cfg: dict) -> bool:
    if not cfg.get("telegram_enabled"):
        return True

    bot_token = cfg.get("telegram_bot_token", "")
    chat_id = cfg.get("telegram_chat_id", "")
    if bot_token and chat_id:
        return True

    if not sys.stdin.isatty():
        logger.error("telegram enabled but BOT_TOKEN/CHAT_ID missing and no TTY available")
        return False

    logger.info("telegram enabled, please input BOT_TOKEN and CHAT_ID")
    if not bot_token:
        bot_token = input("Telegram BOT_TOKEN: ").strip()
    if not chat_id:
        chat_id = input("Telegram CHAT_ID: ").strip()

    if not bot_token or not chat_id:
        logger.error("telegram configuration incomplete")
        return False

    cfg["telegram_bot_token"] = bot_token
    cfg["telegram_chat_id"] = chat_id
    update_env_vars(
        {
            "TELEGRAM_BOT_TOKEN": bot_token,
            "TELEGRAM_CHAT_ID": chat_id,
        }
    )
    logger.info("telegram settings saved to .env")
    return True


def _run_once(logger, cfg: dict) -> int:
    token = cfg["account_token"]
    if not token:
        logger.error("TOKEN not set. Please update .env and try again.")
        return 1

    try:
        resp = _pause_with_token(logger, cfg, token)
    except Exception as exc:
        logger.error("pause failed: %s", exc)
        _notify(logger, cfg, f"Pause failed: {exc}")
        return 1

    code = resp.get("code")
    msg = resp.get("msg")

    if code == 400006:
        logger.error("token expired. Please update TOKEN in .env and retry.")
        _notify(logger, cfg, "Token expired. Please update TOKEN.")
        return 1

    if code == 0:
        logger.info("%s:%s", code, msg)
        logger.info("paused successfully")
        _notify(logger, cfg, "Pause successful.")
        return 0

    if code == 400803:
        logger.info("already paused: %s - %s", code, msg)
        # _notify(logger, cfg, "Already paused.")
        return 0

    logger.error("pause failed: %s - %s", code, msg)
    _notify(logger, cfg, f"Pause failed: {code} - {msg}")
    return 1


def run_loop(logger, cfg: dict, run_time: dt_time) -> int:
    poll_state = {"offset": None}

    while True:
        seconds, target = _seconds_until(run_time)
        logger.info("next run scheduled at %s", target.strftime("%Y-%m-%d %H:%M:%S"))
        _sleep_with_poll(logger, cfg, seconds, poll_state)
        _run_once(logger, cfg)


def run_interval_loop(logger, cfg: dict, interval_minutes: int) -> int:
    if interval_minutes <= 0:
        raise ValueError("interval_minutes must be > 0")

    seconds = interval_minutes * 60
    logger.info("interval mode: every %d minutes", interval_minutes)
    poll_state = {"offset": None}

    while True:
        _run_once(logger, cfg)
        _sleep_with_poll(logger, cfg, seconds, poll_state)


def setup_signal_handlers(logger) -> None:
    def _handle_stop(signum, _frame):
        logger.info("received signal %s, exiting", signum)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)


def _pid_file_path() -> str:
    return os.path.join(os.path.dirname(__file__), "app.pid")


def _lock_file_path() -> str:
    return os.path.join(os.path.dirname(__file__), "app.lock")


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def acquire_lock(logger) -> None:
    global LOCK_HANDLE
    lock_path = _lock_file_path()
    lock_handle = open(lock_path, "a", encoding="utf-8")
    try:
        portalocker.lock(lock_handle, portalocker.LOCK_EX | portalocker.LOCK_NB)
    except portalocker.LockException:
        logger.error("another instance is already running (lockfile: %s)", lock_path)
        raise SystemExit(1)

    LOCK_HANDLE = lock_handle

    def _cleanup() -> None:
        try:
            if LOCK_HANDLE is not None:
                try:
                    portalocker.unlock(LOCK_HANDLE)
                except portalocker.LockException:
                    pass
                LOCK_HANDLE.close()
        except OSError:
            return

    atexit.register(_cleanup)


def write_pid_file(logger) -> None:
    pid_path = _pid_file_path()
    if os.path.exists(pid_path):
        try:
            with open(pid_path, "r", encoding="utf-8") as handle:
                existing = handle.read().strip()
            existing_pid = int(existing) if existing else 0
        except (OSError, ValueError):
            existing_pid = 0

        if existing_pid and _pid_is_running(existing_pid):
            logger.error("another instance is already running (pid=%s)", existing_pid)
            raise SystemExit(1)

        logger.warning("stale pid file found, overwriting: %s", pid_path)

    with open(pid_path, "w", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))

    def _cleanup() -> None:
        try:
            if os.path.exists(pid_path):
                os.remove(pid_path)
        except OSError:
            return

    atexit.register(_cleanup)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Leishen Auto Pause")
    parser.add_argument(
        "--run-time",
        default=None,
        help="Daily run time in HH:MM (overrides RUN_TIME in .env)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once immediately and exit",
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=None,
        help="Run repeatedly every N minutes (overrides daily schedule)",
    )
    parser.add_argument(
        "--fetch-token",
        action="store_true",
        help="Open browser to fetch TOKEN and save to .env",
    )
    return parser.parse_args()


def main() -> int:
    setup_logging()
    logger = get_logger()

    logger.info("start running")
    setup_signal_handlers(logger)
    acquire_lock(logger)
    write_pid_file(logger)

    args = parse_args()

    try:
        cfg = load_config(require_token=False)
    except Exception as exc:
        logger.error("config error: %s", exc)
        return 1

    if not _ensure_telegram_config(logger, cfg):
        return 1

    if args.fetch_token:
        return _fetch_token_interactive(logger, cfg)

    if args.once:
        return _run_once(logger, cfg)

    if args.interval_minutes is not None:
        return run_interval_loop(logger, cfg, args.interval_minutes)

    run_time_value = args.run_time or cfg["run_time"]
    run_time = _parse_run_time(run_time_value)
    return run_loop(logger, cfg, run_time)


if __name__ == "__main__":
    raise SystemExit(main())
