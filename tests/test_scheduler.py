import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import config.settings as settings_module
import automation.scheduler as scheduler_module


@pytest.fixture
def sched_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module, "SETTINGS_PATH", str(tmp_path / "settings.yaml"))
    monkeypatch.setattr(settings_module, "PROFILE_PATH", str(tmp_path / "profile.yaml"))
    monkeypatch.setattr(settings_module, "ENV_PATH", str(tmp_path / ".env"))
    monkeypatch.setattr(settings_module, "_cache", None)
    monkeypatch.setattr(settings_module, "_cache_mtime", None)
    monkeypatch.setattr(settings_module, "_migrated", True)
    monkeypatch.setattr(scheduler_module, "_scheduler", None)

    yield settings_module, scheduler_module

    if scheduler_module._scheduler is not None:
        scheduler_module._scheduler.shutdown(wait=False)
        scheduler_module._scheduler = None


def _trigger_field(trigger, name):
    return str(next(f for f in trigger.fields if f.name == name))


def _make_schedule(**overrides):
    sched = {
        "id": "sched-1", "name": "Test", "mode": "daily",
        "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
        "time": "06:30", "enabled": True, "notify": True,
    }
    sched.update(overrides)
    return sched


def test_sync_creates_cron_job_with_correct_schedule(sched_env):
    settings, scheduler = sched_env
    settings.add_schedule(_make_schedule())
    scheduler.sync_schedules()

    jobs = scheduler.get_scheduler().get_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "sched-1"
    assert _trigger_field(job.trigger, "day_of_week") == "mon,tue,wed,thu,fri"
    assert _trigger_field(job.trigger, "hour") == "6"
    assert _trigger_field(job.trigger, "minute") == "30"


def test_sync_skips_disabled_schedules(sched_env):
    settings, scheduler = sched_env
    settings.add_schedule(_make_schedule(id="a", enabled=True))
    settings.add_schedule(_make_schedule(id="b", enabled=False))
    scheduler.sync_schedules()

    job_ids = {job.id for job in scheduler.get_scheduler().get_jobs()}
    assert job_ids == {"a"}


def test_sync_prunes_deleted_schedules(sched_env):
    settings, scheduler = sched_env
    settings.add_schedule(_make_schedule())
    scheduler.sync_schedules()
    assert len(scheduler.get_scheduler().get_jobs()) == 1

    settings.delete_schedule("sched-1")
    scheduler.sync_schedules()
    assert len(scheduler.get_scheduler().get_jobs()) == 0


def test_sync_is_idempotent(sched_env):
    settings, scheduler = sched_env
    settings.add_schedule(_make_schedule())
    scheduler.sync_schedules()
    scheduler.sync_schedules()
    assert len(scheduler.get_scheduler().get_jobs()) == 1
