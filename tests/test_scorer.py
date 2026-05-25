import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import pytest
from core.scorer import score_dataframe


def make_df(rows):
    defaults = {"title": "", "company": "", "location": "", "is_remote": False, "description": ""}
    return pd.DataFrame([{**defaults, **r} for r in rows])


def test_django_bonus():
    df = make_df([{"description": "We use Django and PostgreSQL.", "is_remote": True}])
    result = score_dataframe(df)
    assert result.iloc[0]["score"] >= 30


def test_fastapi_bonus():
    df = make_df([{"description": "FastAPI microservices.", "is_remote": True}])
    result = score_dataframe(df)
    assert result.iloc[0]["score"] >= 30


def test_junior_title_bonus():
    df = make_df([{"title": "Junior Python Developer", "description": "Python dev.", "is_remote": True}])
    result = score_dataframe(df)
    assert result.iloc[0]["score"] >= 20


def test_latam_bonus():
    df = make_df([{"description": "We are LATAM-friendly, remote.", "is_remote": True}])
    result = score_dataframe(df)
    assert result.iloc[0]["score"] >= 15


def test_high_years_penalty():
    df = make_df([{"description": "Requires 3+ years of experience in Python.", "is_remote": True}])
    result = score_dataframe(df)
    # With penalty, score should be lower
    score_without = 5  # remote only
    assert result.iloc[0]["score"] <= score_without


def test_score_clamped_to_100():
    df = make_df([{
        "title": "Junior Python Developer",
        "description": "Django FastAPI PostgreSQL Docker pytest Latin America LATAM remote",
        "location": "LATAM Remote",
        "is_remote": True,
    }])
    result = score_dataframe(df)
    assert result.iloc[0]["score"] <= 100


def test_score_not_negative():
    df = make_df([{
        "description": "Java Kotlin Scala Rust Kubernetes 5+ years experience",
        "is_remote": False,
    }])
    result = score_dataframe(df)
    assert result.iloc[0]["score"] >= 0
