"""Tests for local-only LLM client behavior."""

import pytest

from llm_client import LLMClient, LLMError, assert_local_endpoint


@pytest.fixture
def clean_env(monkeypatch):
    for var in (
        "NOVEL_OS_LLM_PROVIDER", "NOVEL_OS_MODEL", "NOVEL_OS_BASE_URL",
        "NOVEL_OS_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_assert_local_endpoint_allows_localhost():
    assert_local_endpoint("http://127.0.0.1:1234/v1")
    assert_local_endpoint("http://localhost:11434/v1")


def test_assert_local_endpoint_blocks_remote():
    with pytest.raises(LLMError, match="Blocked non-local"):
        assert_local_endpoint("https://api.openai.com/v1")


def test_resolve_provider_uses_env(clean_env):
    clean_env.setenv("NOVEL_OS_LLM_PROVIDER", "lmstudio")
    assert LLMClient._resolve_provider() == "lmstudio"


def test_unknown_provider_raises(clean_env):
    clean_env.setenv("NOVEL_OS_LLM_PROVIDER", "not_a_provider")
    with pytest.raises(LLMError, match="Unknown LLM provider"):
        LLMClient(provider="not_a_provider", model="x", base_url="http://127.0.0.1:1234/v1")


def test_local_only_sentinel_blocks_cloud_provider(clean_env, tmp_path):
    clean_env.setenv("NOVEL_OS_HOME", str(tmp_path))
    (tmp_path / "LOCAL_ONLY").write_text("", encoding="utf-8")
    with pytest.raises(LLMError, match="local-only"):
        LLMClient(provider="openai", model="gpt-4o-mini", base_url="https://api.openai.com/v1")


def test_openai_provider_allowed_without_local_only_sentinel(clean_env, tmp_path):
    clean_env.setenv("NOVEL_OS_HOME", str(tmp_path))
    client = LLMClient(
        provider="openai",
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        api_key="test-key",
    )

    assert client.provider == "openai"
    assert client.base_url == "https://api.openai.com/v1"


def test_openai_compatible_requires_local_base_url(clean_env):
    clean_env.setenv("NOVEL_OS_LLM_PROVIDER", "openai_compatible")
    clean_env.setenv("NOVEL_OS_MODEL", "local-model")
    clean_env.setenv("NOVEL_OS_BASE_URL", "https://api.openai.com/v1")
    with pytest.raises(LLMError, match="Blocked non-local"):
        LLMClient()
