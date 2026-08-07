import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.validation import (
    validate_regex, validate_time_hhmm, validate_int_range,
    validate_search, validate_filters, validate_scoring, validate_schedule,
)


def test_validate_regex_accepts_valid_pattern():
    assert validate_regex(r"\bsenior\b") is None


def test_validate_regex_rejects_invalid_pattern():
    assert validate_regex("[unclosed") is not None


def test_validate_time_hhmm_accepts_valid():
    assert validate_time_hhmm("06:30") is None
    assert validate_time_hhmm("23:59") is None


def test_validate_time_hhmm_rejects_invalid():
    assert validate_time_hhmm("25:00") is not None
    assert validate_time_hhmm("6:30") is not None
    assert validate_time_hhmm("not-a-time") is not None


def test_validate_int_range():
    assert validate_int_range(50, 0, 100) is None
    assert validate_int_range(150, 0, 100) is not None
    assert validate_int_range(-1, 0, 100) is not None
    assert validate_int_range("50", 0, 100) is not None
    assert validate_int_range(True, 0, 100) is not None  # bool is not a valid int here


def test_validate_search_requires_at_least_one_site():
    errors = validate_search({
        "sites": [], "keywords": ["x"], "locations": ["x"],
        "work_modes": ["remote"], "job_types": [],
        "results_wanted": 25, "hours_old_daily": 168, "hours_old_initial": 720,
    })
    assert "sites" in errors


def test_validate_search_rejects_empty_keywords():
    errors = validate_search({
        "sites": ["linkedin"], "keywords": [], "locations": ["x"],
        "work_modes": ["remote"], "job_types": [],
        "results_wanted": 25, "hours_old_daily": 168, "hours_old_initial": 720,
    })
    assert "keywords" in errors


def test_validate_filters_rejects_bad_regex():
    errors = validate_filters({
        "exclude_title_words": ["[unclosed"],
        "allowed_location_patterns": [],
        "impossible_years_patterns": [],
        "max_age_days": 30,
        "min_score_to_save": 0,
    })
    assert any("exclude_title_words" in k for k in errors)


def test_validate_filters_allows_empty_pattern_lists():
    errors = validate_filters({
        "exclude_title_words": [],
        "allowed_location_patterns": [],
        "impossible_years_patterns": [],
        "max_age_days": 30,
        "min_score_to_save": 0,
    })
    assert errors == {}


def test_validate_scoring_rejects_rule_without_pattern():
    errors = validate_scoring({
        "score_hot": 70, "bonus_skill_points": 5, "bonus_skill_cap": 20, "remote_bonus": 5,
        "rules": [{"label": "x", "pattern": "", "points": 10, "field": "description", "enabled": True}],
        "penalties": [],
    })
    assert any("rules[0].pattern" in k for k in errors)


def test_validate_scoring_rejects_bad_field():
    errors = validate_scoring({
        "score_hot": 70, "bonus_skill_points": 5, "bonus_skill_cap": 20, "remote_bonus": 5,
        "rules": [{"label": "x", "pattern": r"\bx\b", "points": 10, "field": "nope", "enabled": True}],
        "penalties": [],
    })
    assert any("rules[0].field" in k for k in errors)


def test_validate_schedule_requires_days():
    errors = validate_schedule({"id": "a", "name": "x", "mode": "daily", "days_of_week": [], "time": "06:30"})
    assert "days_of_week" in errors


def test_validate_schedule_accepts_valid():
    errors = validate_schedule({"id": "a", "name": "x", "mode": "daily", "days_of_week": ["mon"], "time": "06:30"})
    assert errors == {}
