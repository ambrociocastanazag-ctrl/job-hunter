import requests
import pandas as pd
from config.settings import get_secrets, get_settings
from utils.logger import get_logger

logger = get_logger(__name__)

API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_hot_alert(hot_jobs: pd.DataFrame) -> bool:
    if not get_settings()["notifications"]["hot_alerts_enabled"]:
        return False
    if hot_jobs.empty:
        return False
    return _send(_build_hot_message(hot_jobs))


def send_digest(top_jobs: pd.DataFrame, stats: dict) -> bool:
    if not get_settings()["notifications"]["digest_enabled"]:
        logger.info("Digest notifications disabled. Skipping.")
        return False

    message = _build_message(top_jobs, stats)
    return _send(message)


def send_message(text: str) -> bool:
    """Send a plain text message. Usable standalone for quick tests."""
    return _send(text)


def _build_hot_message(jobs: pd.DataFrame) -> str:
    lines = [f"ALERTA — {len(jobs)} vacante(s) con score alto\n"]
    for i, (_, row) in enumerate(jobs.iterrows(), 1):
        score = row.get("score", 0)
        title = row.get("title", "")
        company = row.get("company", "")
        url = row.get("job_url", "")
        stack = row.get("stack_detected", [])
        stack_str = " | ".join(stack[:4]) if isinstance(stack, list) and stack else ""
        lines.append(f"{i}. [{score}] {title} @ {company}")
        if stack_str:
            lines.append(f"   {stack_str}")
        if url:
            lines.append(f"   {url}")
        lines.append("")
    return "\n".join(lines)


def _build_message(top: pd.DataFrame, stats: dict) -> str:
    run_date = stats.get("date", "")
    new_count = stats.get("new_count", 0)
    total = stats.get("total_found", 0)
    filtered = stats.get("filtered", 0)

    lines = [
        f"Job Hunter — {run_date}",
        f"{new_count} vacantes nuevas ({total} procesadas, {filtered} filtradas)",
        "",
    ]

    if not top.empty:
        lines.append("TOP 3:")
        for i, (_, row) in enumerate(top.head(3).iterrows(), 1):
            score = row.get("score", 0)
            title = row.get("title", "")
            company = row.get("company", "")
            url = row.get("job_url", "")
            lines.append(f"{i}. [{score}] {title} @ {company}")
            if url:
                lines.append(f"   {url}")

    return "\n".join(lines)


def _send(text: str) -> bool:
    secrets = get_secrets()
    token = secrets["telegram_bot_token"]
    chat_id = secrets["telegram_chat_id"]
    if not token or not chat_id:
        logger.warning("Telegram not configured. Skipping.")
        return False

    url = API_URL.format(token=token)
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("Telegram notification sent.")
        return True
    except requests.RequestException as e:
        logger.error(f"Telegram send failed: {e}")
        return False
