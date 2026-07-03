from app_settings import (
    effective_agent_prompt,
    read_agent_prompt_variant,
    read_custom_agent_prompt,
    merge_system_prompt,
    read_global_system_prefix,
    read_max_concurrent_llm,
    write_agent_prompt_variant,
    write_custom_agent_prompt,
    write_global_system_prefix,
    write_max_concurrent_llm,
)


def test_merge_system_prefix_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    assert merge_system_prompt("Agent body") == "Agent body"


def test_merge_system_prefix_prepends(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    write_global_system_prefix("Always past tense.")
    merged = merge_system_prompt("You are the Scribe.")
    assert merged.startswith("Always past tense.")
    assert "You are the Scribe." in merged
    assert "---" in merged


def test_read_write_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    write_global_system_prefix("  hello  ")
    assert read_global_system_prefix().strip() == "hello"


def test_max_concurrent_llm_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    assert read_max_concurrent_llm() == 2
    assert write_max_concurrent_llm(4) == 4
    assert read_max_concurrent_llm() == 4
    monkeypatch.setenv("NOVEL_OS_MAX_CONCURRENT_LLM", "6")
    assert read_max_concurrent_llm() == 6


def test_agent_prompt_variant_defaults_to_current(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    assert read_agent_prompt_variant("scribe") == "current"
    assert effective_agent_prompt("scribe", "CURRENT PROMPT") == "CURRENT PROMPT"


def test_custom_agent_prompt_appends_contract_guard(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    write_custom_agent_prompt("scribe", "Write in a warmer voice.")
    write_agent_prompt_variant("scribe", "custom")
    prompt = effective_agent_prompt("scribe", "CURRENT PROMPT")
    assert prompt.startswith("Write in a warmer voice.")
    assert "IMMUTABLE OUTPUT CONTRACT" in prompt
    assert "[SCRIBE_STATE_UPDATE]" in prompt
    assert read_custom_agent_prompt("scribe") == "Write in a warmer voice."


def test_recommended_agent_prompt_can_be_selected(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    write_agent_prompt_variant("architect", "recommended")
    prompt = effective_agent_prompt("architect", "CURRENT PROMPT")
    assert "recommended default" in prompt
    assert "[CHAPTER_OUTLINE]" in prompt
