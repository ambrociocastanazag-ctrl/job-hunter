import re
import pandas as pd
from utils.logger import get_logger

logger = get_logger(__name__)

SCORE_RULES: list[tuple[str, int, str]] = [
    # (pattern, points, field)
    (r"\bdjango\b|\bfastapi\b", 30, "description"),
    (r"\bjunior\b|\bentry[\s-]level\b", 20, "title"),
    (r"\bpostgresql\b|\bpostgres\b", 10, "description"),   # +5 bonus si ya tiene Python
    (r"\blatin america\b|\blatam\b|\bamericas timezone\b|\blatam.friendly\b", 15, "description"),
    (r"\blatam\b|\blatin america\b", 15, "location"),
    (r"\bdocker\b", 10, "description"),
    (r"\bpytest\b|\bunit test", 5, "description"),
    (r"\bjunior\b|\bentry[\s-]level\b", 10, "description"),
]

PENALTY_RULES: list[tuple[str, int, str]] = [
    (r"3\+?\s*years?\s*(of\s*)?(experience|exp)", -20, "description"),
    (r"3\s*-\s*[4-9]\s*years?\s*(of\s*)?(experience|exp)", -20, "description"),
    (r"\bgo\b|\bgolang\b", -15, "description"),
    (r"\brust\b", -15, "description"),
    (r"\bkubernetes\b|\bk8s\b", -10, "description"),
    (r"\bjava\b(?!script)", -10, "description"),
    (r"\bscala\b|\bkotlin\b", -10, "description"),
]


def _compute_score(row: pd.Series) -> int:
    score = 0
    title = str(row.get("title", "")).lower()
    desc = str(row.get("description", "")).lower()
    location = str(row.get("location", "")).lower()

    field_map = {"title": title, "description": desc, "location": location}

    for pattern, pts, field in SCORE_RULES:
        text = field_map.get(field, "")
        if re.search(pattern, text, re.IGNORECASE):
            score += pts

    # PostgreSQL + Python bonus
    if re.search(r"\bpostgresql\b|\bpostgres\b", desc, re.IGNORECASE) and re.search(r"\bpython\b", desc, re.IGNORECASE):
        score += 5

    for pattern, pts, field in PENALTY_RULES:
        text = field_map.get(field, "")
        if re.search(pattern, text, re.IGNORECASE):
            score += pts  # pts is negative

    if row.get("is_remote"):
        score += 5

    return max(0, min(100, score))


def score_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["score"] = df.apply(_compute_score, axis=1)
    logger.info(f"Scored {len(df)} jobs. Score distribution: mean={df['score'].mean():.1f}, max={df['score'].max()}")
    return df
