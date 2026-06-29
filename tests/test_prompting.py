"""Unit tests for the transcription prompt builder (offline, no network)."""

import whisperflow.prompting as p


def test_load_base_prompt_default(monkeypatch):
    monkeypatch.delenv("WHISPERFLOW_PROMPT", raising=False)
    monkeypatch.delenv("WHISPERFLOW_GLOSSARY", raising=False)
    base = p.load_base_prompt()
    assert base == p.DEFAULT_GLOSSARY
    # a few grounded, high-value terms must be present
    for term in ("BigQuery", "CREATIA", "n8n", "Qdrant", "Cloud Run"):
        assert term in base


def test_load_base_prompt_override(monkeypatch):
    monkeypatch.setenv("WHISPERFLOW_PROMPT", "  Acme, Foo Bar, BazQL  ")
    assert p.load_base_prompt() == "Acme, Foo Bar, BazQL"


def test_load_base_prompt_disabled(monkeypatch):
    monkeypatch.delenv("WHISPERFLOW_PROMPT", raising=False)
    monkeypatch.setenv("WHISPERFLOW_GLOSSARY", "off")
    assert p.load_base_prompt() == ""
    # empty override also disables
    monkeypatch.delenv("WHISPERFLOW_GLOSSARY", raising=False)
    monkeypatch.setenv("WHISPERFLOW_PROMPT", "")
    assert p.load_base_prompt() == ""


def test_build_prompt_glossary_preserved_and_rolling_tail_appended():
    base = "BigQuery, Cloud Run, CREATIA"
    rolling = "el equipo revisó los cambios del pipeline de datos"
    out = p.build_prompt(base, rolling, max_chars=200)
    assert out.startswith(base)
    assert out.endswith("pipeline de datos")  # most recent context kept


def test_build_prompt_trims_rolling_not_glossary():
    base = "BigQuery, Cloud Run, CREATIA"
    rolling = "x" * 500
    out = p.build_prompt(base, rolling, max_chars=len(base) + 11)  # 10 chars for tail
    assert out.startswith(base + " ")
    assert len(out) <= len(base) + 11
    assert out.endswith("xxxxxxxxxx")  # only the rolling tail, glossary intact


def test_build_prompt_base_only_and_rolling_only():
    assert p.build_prompt("BigQuery", "", 100) == "BigQuery"
    assert p.build_prompt("", "hola mundo", 100) == "hola mundo"
    assert p.build_prompt("", "", 100) == ""


def test_build_prompt_oversized_glossary_is_capped():
    base = "A" * 50
    out = p.build_prompt(base, "rolling text", max_chars=20)
    assert out == "A" * 20  # glossary itself capped, no rolling appended


def test_build_prompt_zero_budget():
    assert p.build_prompt("BigQuery", "hola", 0) == ""
