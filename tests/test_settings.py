import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
import pytest

import config.settings as settings_module
from config.validation import ValidationError


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module, "SETTINGS_PATH", str(tmp_path / "settings.yaml"))
    monkeypatch.setattr(settings_module, "PROFILE_PATH", str(tmp_path / "profile.yaml"))
    monkeypatch.setattr(settings_module, "ENV_PATH", str(tmp_path / ".env"))
    monkeypatch.setattr(settings_module, "_cache", None)
    monkeypatch.setattr(settings_module, "_cache_mtime", None)
    monkeypatch.setattr(settings_module, "_migrated", True)
    return settings_module


def test_defaults_used_when_no_yaml(isolated_settings):
    s = isolated_settings.get_settings()
    assert s["search"]["sites"] == ["linkedin", "indeed", "glassdoor"]
    assert s["filters"]["min_score_to_save"] == 0


def test_save_section_partial_preserves_sibling_keys(isolated_settings):
    isolated_settings.save_section_partial("search", {"sites": ["linkedin"]})
    isolated_settings.save_section_partial("search", {"keywords": ["Python Developer"]})
    s = isolated_settings.get_settings()
    assert s["search"]["sites"] == ["linkedin"]
    assert s["search"]["keywords"] == ["Python Developer"]
    # untouched keys still fall back to defaults
    assert s["search"]["results_wanted"] == 25


def test_invalid_regex_rejected_and_file_unchanged(isolated_settings):
    before = isolated_settings.get_settings()["filters"]["exclude_title_words"]
    with pytest.raises(ValidationError):
        isolated_settings.save_section("filters", {
            **isolated_settings.get_settings()["filters"],
            "exclude_title_words": ["[unclosed"],
        })
    after = isolated_settings.get_settings()["filters"]["exclude_title_words"]
    assert before == after
    assert not os.path.exists(isolated_settings.SETTINGS_PATH)


def test_stack_patterns_override_replaces_wholesale(isolated_settings):
    isolated_settings.save_section("stack_patterns", {"Django": r"\bdjango\b"})
    s = isolated_settings.get_settings()
    assert s["stack_patterns"] == {"Django": r"\bdjango\b"}


def test_reset_section_restores_defaults(isolated_settings):
    isolated_settings.save_section("stack_patterns", {"Django": r"\bdjango\b"})
    isolated_settings.reset_section("stack_patterns")
    s = isolated_settings.get_settings()
    assert len(s["stack_patterns"]) == 22


def test_reset_section_keys_only_resets_given_keys(isolated_settings):
    isolated_settings.save_section_partial("search", {"sites": ["linkedin"], "keywords": ["custom"]})
    isolated_settings.reset_section_keys("search", ["sites"])
    s = isolated_settings.get_settings()
    assert s["search"]["sites"] == ["linkedin", "indeed", "glassdoor"]
    assert s["search"]["keywords"] == ["custom"]


def test_cache_invalidates_on_mtime_change(isolated_settings):
    isolated_settings.save_section_partial("filters", {"min_score_to_save": 10})
    assert isolated_settings.get_settings()["filters"]["min_score_to_save"] == 10

    # Simulate a different process editing settings.yaml directly (e.g. a
    # subprocess corrida saving its own config) — this process's cache must
    # still pick up the change on the next read, without a restart.
    with open(isolated_settings.SETTINGS_PATH, "w", encoding="utf-8") as f:
        f.write("filters:\n  min_score_to_save: 42\n")
    future = time.time() + 5
    os.utime(isolated_settings.SETTINGS_PATH, (future, future))

    assert isolated_settings.get_settings()["filters"]["min_score_to_save"] == 42


def test_secrets_roundtrip(isolated_settings):
    isolated_settings.save_secrets(telegram_bot_token="123:ABC", telegram_chat_id="999")
    secrets = isolated_settings.get_secrets()
    assert secrets["telegram_bot_token"] == "123:ABC"
    assert secrets["telegram_chat_id"] == "999"


def test_atomic_write_creates_backup(isolated_settings):
    isolated_settings.save_section_partial("filters", {"min_score_to_save": 1})
    isolated_settings.save_section_partial("filters", {"min_score_to_save": 2})
    assert os.path.exists(isolated_settings.SETTINGS_PATH + ".bak")


def test_schedule_crud(isolated_settings):
    sched = {
        "id": isolated_settings.new_schedule_id(),
        "name": "Test", "mode": "daily",
        "days_of_week": ["mon"], "time": "06:30",
        "enabled": True, "notify": True,
    }
    isolated_settings.add_schedule(sched)
    assert len(isolated_settings.get_settings()["schedules"]) == 1

    isolated_settings.update_schedule(sched["id"], {"enabled": False})
    assert isolated_settings.get_settings()["schedules"][0]["enabled"] is False

    isolated_settings.delete_schedule(sched["id"])
    assert isolated_settings.get_settings()["schedules"] == []


def test_schedule_validation_rejects_bad_time(isolated_settings):
    sched = {
        "id": isolated_settings.new_schedule_id(),
        "name": "Test", "mode": "daily",
        "days_of_week": ["mon"], "time": "25:99",
        "enabled": True, "notify": True,
    }
    with pytest.raises(ValidationError):
        isolated_settings.add_schedule(sched)
