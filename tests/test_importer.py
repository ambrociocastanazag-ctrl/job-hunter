import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import re
import pytest

import config.settings as settings_module
from config.importer import ImportConfigError, apply_import, parse_import, word_pattern, years_patterns

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "ayuda_prompt.md")


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_module, "SETTINGS_PATH", str(tmp_path / "settings.yaml"))
    monkeypatch.setattr(settings_module, "PROFILE_PATH", str(tmp_path / "profile.yaml"))
    monkeypatch.setattr(settings_module, "ENV_PATH", str(tmp_path / ".env"))
    monkeypatch.setattr(settings_module, "_cache", None)
    monkeypatch.setattr(settings_module, "_cache_mtime", None)
    monkeypatch.setattr(settings_module, "_migrated", True)
    return settings_module


def _prompt_example() -> str:
    with open(PROMPT_PATH, encoding="utf-8") as f:
        return re.search(r"```yaml\n(.*?)```", f.read(), re.DOTALL).group(1)


def test_prompt_example_imports_cleanly(isolated_settings):
    plan = parse_import(_prompt_example())
    assert plan.warnings == []
    apply_import(plan)

    s = isolated_settings.get_settings()
    assert "Accountant" in s["search"]["keywords"]
    assert s["search"]["work_modes"] == ["remote", "hybrid"]
    assert s["search"]["job_types"] == ["fulltime"]
    assert s["runtime"]["country_indeed"] == "colombia"
    assert s["filters"]["min_score_to_save"] == 25
    assert [r["label"] for r in s["scoring"]["rules"]] == ["contabilidad", "accounting", "junior", "NIIF", "IFRS"]
    assert s["scoring"]["penalties"][0]["points"] == -15
    assert set(s["stack_patterns"]) == {"Excel", "SAP", "Power BI", "NIIF", "IFRS"}
    assert s["schedules"][0]["days_of_week"] == ["mon", "tue", "wed", "thu", "fri"]
    assert s["schedules"][0]["time"] == "09:00"

    profile = isolated_settings.get_profile()
    assert profile["name"] == "Ana López"
    assert profile["stack"]["primary"] == ["Contabilidad", "Excel", "SAP"]


def test_ai_answer_wrapped_in_code_fence(isolated_settings):
    text = "¡Listo! Aquí está:\n```yaml\nbusqueda:\n  puestos: [Contador]\n```\nGuárdalo."
    plan = parse_import(text)
    assert plan.sections["search"]["keywords"] == ["Contador"]


def test_word_pattern_ignores_accents_case_and_hyphens():
    assert re.search(word_pattern("Bogotá"), "bogota, colombia", re.IGNORECASE)
    assert re.search(word_pattern("bogota"), "Bogotá D.C.", re.IGNORECASE)
    assert re.search(word_pattern("entry level"), "Entry-Level Analyst", re.IGNORECASE)
    assert re.search(word_pattern("C++"), "we use C++ daily", re.IGNORECASE)
    assert not re.search(word_pattern("lead"), "leadership skills", re.IGNORECASE)


def test_years_patterns_only_reject_above_the_limit():
    combined = "|".join(years_patterns(3))
    assert re.search(combined, "Requires 5+ years of experience", re.IGNORECASE)
    assert re.search(combined, "mínimo 4 años de experiencia", re.IGNORECASE)
    assert re.search(combined, "10 years experience", re.IGNORECASE)
    assert not re.search(combined, "3+ years of experience", re.IGNORECASE)
    assert not re.search(combined, "2 years of experience", re.IGNORECASE)
    assert years_patterns(20) == []


def test_unquoted_time_is_read_as_hhmm(isolated_settings):
    # YAML 1.1 convierte `hora: 09:30` sin comillas en 570 (base 60).
    plan = parse_import("horarios:\n  - dias: [sab]\n    hora: 09:30\n")
    assert plan.sections["schedules"][0]["time"] == "09:30"


def test_locations_filter_derived_from_search_locations(isolated_settings):
    plan = parse_import("busqueda:\n  ubicaciones: [Madrid, Spain]\n  modalidad: [remoto]\n")
    patterns = plan.sections["filters"]["allowed_location_patterns"]
    combined = "|".join(patterns)
    assert re.search(combined, "Madrid, Comunidad de Madrid", re.IGNORECASE)
    assert re.search(combined, "Remote", re.IGNORECASE)
    assert not re.search(combined, "Bogotá, Colombia", re.IGNORECASE)


def test_unknown_country_falls_back_to_worldwide(isolated_settings):
    plan = parse_import("busqueda:\n  pais: Guatemala\n")
    assert plan.runtime_patch["country_indeed"] == "worldwide"
    assert any("Guatemala" in w for w in plan.warnings)


def test_spanish_country_name_is_translated(isolated_settings):
    plan = parse_import("busqueda:\n  pais: España\n")
    assert plan.runtime_patch["country_indeed"] == "spain"


def test_errors_are_collected_and_nothing_is_saved(isolated_settings):
    bad = "busqueda:\n  modalidad: [teletrabajo]\n  sitios: [computrabajo]\nhorarios:\n  - dias: [lunes]\n    hora: 25:00\n"
    with pytest.raises(ImportConfigError) as exc:
        parse_import(bad)
    text = " ".join(exc.value.errors)
    assert "teletrabajo" in text and "computrabajo" in text and "hora" in text
    assert not os.path.exists(isolated_settings.SETTINGS_PATH)


def test_invalid_yaml_reports_line(isolated_settings):
    with pytest.raises(ImportConfigError) as exc:
        parse_import("busqueda:\n  puestos: [Contador\n  sitios: linkedin\n")
    assert "línea" in exc.value.errors[0]


def test_unknown_sections_are_warned_not_fatal(isolated_settings):
    plan = parse_import("busqueda:\n  puestos: [Chef]\nsalario: 1000\n")
    assert any("salario" in w for w in plan.warnings)


def test_prompt_example_stays_within_combination_budget(isolated_settings):
    plan = parse_import(_prompt_example())
    search_lines = dict(plan.summary)["Búsqueda"]
    assert any("búsquedas por corrida" in line for line in search_lines)
    assert not any("búsquedas por corrida" in w for w in plan.warnings)


def test_too_many_combinations_is_warned(isolated_settings):
    keywords = ", ".join(f"Puesto {i}" for i in range(12))
    plan = parse_import(f"busqueda:\n  puestos: [{keywords}]\n  ubicaciones: [A, B, C, D, E]\n  sitios: [linkedin, indeed, glassdoor]\n")
    assert any("180 búsquedas" in w for w in plan.warnings)


def test_excluded_word_that_kills_a_keyword_is_an_error(isolated_settings):
    text = "busqueda:\n  puestos: [Junior Accountant, Contador]\nfiltros:\n  excluir_en_titulo: [junior, senior]\n"
    with pytest.raises(ImportConfigError) as exc:
        parse_import(text)
    assert any("Junior Accountant" in e and "junior" in e for e in exc.value.errors)
