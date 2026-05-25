import sys
import requests
import pandas as pd
from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from utils.logger import get_logger

logger = get_logger(__name__)

API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_digest(top_jobs: pd.DataFrame, stats: dict) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured. Skipping.")
        return False

    message = _build_message(top_jobs, stats)
    return _send(message)


def send_message(text: str) -> bool:
    """Send a plain text message. Usable standalone for quick tests."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured. Skipping.")
        return False
    return _send(text)


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
    url = API_URL.format(token=TELEGRAM_BOT_TOKEN)
    try:
        resp = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("Telegram notification sent.")
        return True
    except requests.RequestException as e:
        logger.error(f"Telegram send failed: {e}")
        return False
