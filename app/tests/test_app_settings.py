from app_settings import (
    effective_agent_prompt,
    global_system_prefix_path,
    is_local_only_install,
    read_llm_connection_settings,
    read_agent_prompt_variant,
    read_custom_agent_prompt,
    merge_system_prompt,
    read_global_system_prefix,
    read_max_concurrent_llm,
    resolve_llm_connection_api_key,
    write_llm_connection_settings,
    write_agent_prompt_variant,
    write_custom_agent_prompt,
    write_global_system_prefix,
    write_max_concurrent_llm,
)


def test_merge_system_prefix_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    assert merge_system_prompt("Agent body") == "Agent body"


def test_missing_global_system_prefix_regenerates_blank(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    path = global_system_prefix_path()
    assert not path.exists()

    assert read_global_system_prefix() == ""
    assert path.exists()
    assert path.read_text(encoding="utf-8") == ""


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


def test_llm_connection_masks_api_key_and_preserves_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    saved = write_llm_connection_settings({
        "provider": "lmstudio",
        "model": "local-model",
        "base_url": "http://127.0.0.1:1234/v1",
        "api_key": "secret",
    })

    assert saved["api_key_set"] is True
    assert "api_key" not in saved
    assert read_llm_connection_settings(include_secret=True)["api_key"] == "secret"

    write_llm_connection_settings({
        "provider": "lmstudio",
        "model": "other-local",
        "base_url": "http://127.0.0.1:1234/v1",
    })
    assert read_llm_connection_settings(include_secret=True)["api_key"] == "secret"


def test_llm_profiles_are_masked_and_reuse_key_by_server(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    saved = write_llm_connection_settings({
        "provider": "lmstudio",
        "model": "draft-model",
        "base_url": "http://127.0.0.1:1234/v1",
        "api_key": "secret",
        "profile_name": "Local Drafting",
        "save_profile": True,
    })

    assert saved["active_profile_id"]
    assert saved["profiles"][0]["name"] == "Local Drafting"
    assert saved["profiles"][0]["api_key_set"] is True
    assert "api_key" not in saved["profiles"][0]

    write_llm_connection_settings({
        "provider": "lmstudio",
        "model": "revision-model",
        "base_url": "http://127.0.0.1:1234/v1/",
    })
    current = read_llm_connection_settings(include_secret=True)
    assert current["api_key"] == "secret"
    assert resolve_llm_connection_api_key({
        "provider": "lmstudio",
        "base_url": "http://127.0.0.1:1234/v1",
    }) == "secret"


def test_local_only_sentinel_blocks_cloud_providers(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    (tmp_path / "LOCAL_ONLY").write_text("", encoding="utf-8")

    assert is_local_only_install() is True
    try:
        write_llm_connection_settings({
            "provider": "openai",
            "model": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
            "api_key": "secret",
        })
    except ValueError as e:
        assert "local-only" in str(e)
    else:
        raise AssertionError("cloud provider should be blocked")


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


def test_recommended_scribe_prompt_defines_characters_present(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    write_agent_prompt_variant("scribe", "recommended")
    prompt = effective_agent_prompt("scribe", "CURRENT PROMPT")

    assert "Characters_Present" in prompt
    assert "directly on-page" in prompt
    assert "remembered, discussed" in prompt


def test_recommended_archivist_prompt_separates_present_and_mentioned(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVEL_OS_HOME", str(tmp_path))
    write_agent_prompt_variant("archivist", "recommended")
    prompt = effective_agent_prompt("archivist", "CURRENT PROMPT")

    assert "Characters_Present" in prompt
    assert "Characters_Mentioned" in prompt
    assert "present takes precedence" in prompt
