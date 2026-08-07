import re
import pandas as pd
from config.settings import get_settings


def detect_stack(description: str, stack_patterns: dict | None = None) -> list[str]:
    if stack_patterns is None:
        stack_patterns = get_settings()["stack_patterns"]
    found = []
    desc_lower = (description or "").lower()
    for tech, pattern in stack_patterns.items():
        if re.search(pattern, desc_lower, re.IGNORECASE):
            found.append(tech)
    return found


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    stack_patterns = get_settings()["stack_patterns"]
    df = df.copy()
    df["stack_detected"] = df["description"].apply(
        lambda d: detect_stack(d, stack_patterns) if isinstance(d, str) else []
    )
    return df
