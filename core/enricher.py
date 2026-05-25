import re
import pandas as pd
from config.settings import BONUS_STACK

STACK_PATTERNS = {
    "Django": r"\bdjango\b",
    "FastAPI": r"\bfastapi\b",
    "Flask": r"\bflask\b",
    "DRF": r"\b(django rest framework|drf)\b",
    "PostgreSQL": r"\bpostgresql\b|\bpostgres\b",
    "MySQL": r"\bmysql\b",
    "SQLAlchemy": r"\bsqlalchemy\b",
    "REST API": r"\brest(ful)?\s*(api)?\b",
    "Docker": r"\bdocker\b",
    "JWT": r"\bjwt\b",
    "pytest": r"\bpytest\b",
    "Redis": r"\bredis\b",
    "Celery": r"\bcelery\b",
    "AWS": r"\baws\b|\bamazon web services\b",
    "GCP": r"\bgcp\b|\bgoogle cloud\b",
    "Azure": r"\bazure\b",
    "React": r"\breact(\.js|js)?\b",
    "Angular": r"\bangular\b",
    "GraphQL": r"\bgraphql\b",
    "Kubernetes": r"\bkubernetes\b|\bk8s\b",
    "Terraform": r"\bterraform\b",
    "CI/CD": r"\bci/cd\b|\bgithub actions\b|\bjenkins\b",
}


def detect_stack(description: str) -> list[str]:
    found = []
    desc_lower = (description or "").lower()
    for tech, pattern in STACK_PATTERNS.items():
        if re.search(pattern, desc_lower, re.IGNORECASE):
            found.append(tech)
    return found


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["stack_detected"] = df["description"].apply(
        lambda d: detect_stack(d) if isinstance(d, str) else []
    )
    return df
