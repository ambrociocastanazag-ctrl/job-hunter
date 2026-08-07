import re
import pandas as pd
from utils.logger import get_logger

logger = get_logger(__name__)


def _rule_matches(rule: dict, field_map: dict) -> bool:
    field_text = field_map.get(rule["field"], "")
    if not re.search(rule["pattern"], field_text, re.IGNORECASE):
        return False
    for extra_pattern in rule.get("all_of", []) or []:
        if not re.search(extra_pattern, field_text, re.IGNORECASE):
            return False
    return True


def _compute_score(row: pd.Series, bonus_skills: list[str], scoring_cfg: dict) -> int:
    score = 0
    title = str(row.get("title", "")).lower()
    desc = str(row.get("description", "")).lower()
    location = str(row.get("location", "")).lower()

    field_map = {"title": title, "description": desc, "location": location}

    for rule in scoring_cfg["rules"]:
        if not rule.get("enabled", True):
            continue
        if _rule_matches(rule, field_map):
            score += rule["points"]

    for rule in scoring_cfg["penalties"]:
        if not rule.get("enabled", True):
            continue
        if _rule_matches(rule, field_map):
            score += rule["points"]

    if row.get("is_remote"):
        score += scoring_cfg["remote_bonus"]

    skill_bonus = 0
    cap = scoring_cfg["bonus_skill_cap"]
    points_per_skill = scoring_cfg["bonus_skill_points"]
    for skill in bonus_skills:
        if skill_bonus >= cap:
            break
        if re.search(re.escape(skill), desc, re.IGNORECASE):
            skill_bonus += points_per_skill
    score += skill_bonus

    return max(0, min(100, score))


def score_dataframe(df: pd.DataFrame, bonus_skills: list[str] | None = None) -> pd.DataFrame:
    from config.settings import get_settings
    settings = get_settings()
    if bonus_skills is None:
        bonus_skills = settings["search"]["bonus_skills"]
    scoring_cfg = settings["scoring"]

    df = df.copy()
    df["score"] = df.apply(lambda row: _compute_score(row, bonus_skills, scoring_cfg), axis=1)
    logger.info(f"Scored {len(df)} jobs. mean={df['score'].mean():.1f}, max={df['score'].max()}")
    return df
