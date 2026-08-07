import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import pytest
from core.filters import apply_filters, _filter_exclude_title, _filter_location, _filter_impossible_years


def make_df(rows):
    defaults = {"title": "", "company": "", "location": "", "is_remote": False,
                "description": "", "date_posted": None, "job_url": "http://x.com/1"}
    return pd.DataFrame([{**defaults, **r} for r in rows])


def test_exclude_senior_title():
    df = make_df([{"title": "Senior Python Developer", "location": "Remote"}])
    result = apply_filters(df)
    assert len(result) == 0


def test_exclude_lead_title():
    df = make_df([{"title": "Lead Backend Engineer", "location": "Remote"}])
    result = apply_filters(df)
    assert len(result) == 0


def test_keep_junior_title():
    df = make_df([{"title": "Junior Python Developer", "location": "Remote", "is_remote": True}])
    result = apply_filters(df)
    assert len(result) == 1


def test_exclude_impossible_years():
    df = make_df([{
        "title": "Python Developer",
        "location": "Remote",
        "is_remote": True,
        "description": "We require 7+ years of experience in Python.",
    }])
    result = apply_filters(df)
    assert len(result) == 0


def test_keep_no_years():
    df = make_df([{
        "title": "Python Developer",
        "location": "Remote",
        "is_remote": True,
        "description": "We love Python and Django. Junior welcome.",
    }])
    result = apply_filters(df)
    assert len(result) == 1


def test_location_filter_keeps_remote():
    df = make_df([{"title": "Python Dev", "location": "Anywhere", "is_remote": True}])
    result = apply_filters(df)
    assert len(result) == 1


def test_location_filter_removes_local():
    df = make_df([{"title": "Python Dev", "location": "Germany", "is_remote": False}])
    result = apply_filters(df)
    assert len(result) == 0


def test_empty_title_pattern_list_removes_nothing():
    df = make_df([{"title": "Senior Python Developer"}])
    result = _filter_exclude_title(df, [])
    assert len(result) == 1


def test_empty_location_pattern_list_removes_nothing():
    df = make_df([{"title": "Python Dev", "location": "Germany", "is_remote": False}])
    result = _filter_location(df, [])
    assert len(result) == 1


def test_empty_impossible_years_pattern_list_removes_nothing():
    df = make_df([{"description": "We require 10+ years of experience."}])
    result = _filter_impossible_years(df, [])
    assert len(result) == 1
