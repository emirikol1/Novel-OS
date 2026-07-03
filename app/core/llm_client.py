"""
Novel OS - Local-only LLM Client

Calls your configured model endpoint. Local-only installs are enforced by a
LOCAL_ONLY/.localonly sentinel in NOVEL_OS_HOME; published installs can expose
cloud providers when that sentinel is absent.

Configure via environment (or .env in project root):

  NOVEL_OS_LLM_PROVIDER    lmstudio | ollama | openai_compatible
  NOVEL_OS_MODEL           model id loaded in your local server
  NOVEL_OS_BASE_URL        required for openai_compatible; must be localhost
  NOVEL_OS_API_KEY         optional key for local servers that require one
  NOVEL_OS_MAX_TOKENS      int, default 8192
"""

from __future__ import annotations

import os
import socket
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse


DEFAULT_MAX_TOKENS = 8192

# Local OpenAI-compatible aliases only — no cloud preset URLs.
LOCAL_OPENAI_ALIASES = {
    "lmstudio": ("http://127.0.0.1:1234/v1", "local-model", "LMSTUDIO_API_KEY"),
    "ollama": ("http://127.0.0.1:11434/v1", "llama3.2", "OLLAMA_API_KEY"),
}

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _load_dotenv_if_present() -> None:
    """Load .env from cwd. Uses python-dotenv if installed, else a minimal parser."""
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv(env_path)
        return
    except ImportError:
        pass
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv_if_present()


class LLMError(RuntimeError):
    """Raised when the LLM call cannot be made or fails."""


def assert_local_endpoint(base_url: str) -> None:
    """Reject any LLM endpoint that is not on localhost."""
    parsed = urlparse(base_url.strip())
    host = (parsed.hostname or "").lower()
    if host not in LOCAL_HOSTS:
        raise LLMError(
            f"Blocked non-local LLM endpoint: {base_url!r}. "
            "Novel OS only calls your local model server "
            "(e.g. http://127.0.0.1:1234/v1 for LM Studio)."
        )


def _port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class LLMClient:
    """Configured LLM client with local-only policy enforcement."""

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self._settings = self._settings_config()
        self.provider_name = (provider or self._resolve_provider()).lower()
        self.max_tokens = max_tokens or int(os.environ.get("NOVEL_OS_MAX_TOKENS", DEFAULT_MAX_TOKENS))
        self._explicit_base_url = base_url
        self._explicit_api_key = api_key
        self._backend, self.model, self._base_url = self._build_backend(model)

    @staticmethod
    def _settings_config() -> dict:
        try:
            from app_settings import llm_runtime_config  # noqa: WPS433

            return llm_runtime_config()
        except Exception:  # noqa: BLE001
            return {}

    @staticmethod
    def _ensure_provider_allowed(provider: str) -> None:
        try:
            from app_settings import _validate_llm_provider  # noqa: WPS433

            _validate_llm_provider(provider)
        except ValueError as e:
            raise LLMError(str(e)) from e

    @staticmethod
    def _resolve_provider() -> str:
        env_pick = os.environ.get("NOVEL_OS_LLM_PROVIDER")
        if env_pick:
            LLMClient._ensure_provider_allowed(env_pick)
            return env_pick
        settings = LLMClient._settings_config()
        if settings.get("provider"):
            provider = str(settings["provider"])
            LLMClient._ensure_provider_allowed(provider)
            return provider
        base_url = os.environ.get("NOVEL_OS_BASE_URL")
        if base_url:
            assert_local_endpoint(base_url)
            return "openai_compatible"
        if _port_open("127.0.0.1", 1234):
            return "lmstudio"
        if _port_open("127.0.0.1", 11434):
            return "ollama"
        raise LLMError(
            "No local LLM configured. Set NOVEL_OS_LLM_PROVIDER=lmstudio, "
            "NOVEL_OS_MODEL, and NOVEL_OS_BASE_URL=http://127.0.0.1:1234/v1 in .env, "
            "then start LM Studio's Local Server."
        )

    def _build_backend(self, model: Optional[str]) -> Tuple[object, str, str]:
        name = self.provider_name
        env_model = os.environ.get("NOVEL_OS_MODEL")
        settings_model = self._settings.get("model")
        settings_base_url = self._settings.get("base_url")
        settings_api_key = self._settings.get("api_key")
        self._ensure_provider_allowed(name)

        if name in LOCAL_OPENAI_ALIASES:
            default_url, default_model, key_env = LOCAL_OPENAI_ALIASES[name]
            base_url = self._explicit_base_url or os.environ.get("NOVEL_OS_BASE_URL") or settings_base_url or default_url
            assert_local_endpoint(base_url)
            key = (
                self._explicit_api_key
                or os.environ.get(key_env)
                or os.environ.get("NOVEL_OS_API_KEY")
                or settings_api_key
                or "not-needed"
            )
            return (
                self._build_openai_compatible(base_url, key),
                model or env_model or settings_model or default_model,
                base_url,
            )

        if name == "openai_compatible":
            base_url = self._explicit_base_url or os.environ.get("NOVEL_OS_BASE_URL") or settings_base_url
            key = self._explicit_api_key or os.environ.get("NOVEL_OS_API_KEY") or settings_api_key or "not-needed"
            if not base_url:
                raise LLMError("openai_compatible requires NOVEL_OS_BASE_URL (localhost only).")
            assert_local_endpoint(base_url)
            if not (model or env_model or settings_model):
                raise LLMError("openai_compatible requires NOVEL_OS_MODEL (or model=).")
            return self._build_openai_compatible(base_url, key), model or env_model or settings_model, base_url

        if name == "openai":
            base_url = self._explicit_base_url or os.environ.get("NOVEL_OS_BASE_URL") or settings_base_url or "https://api.openai.com/v1"
            key = self._explicit_api_key or os.environ.get("NOVEL_OS_API_KEY") or os.environ.get("OPENAI_API_KEY") or settings_api_key
            if not key:
                raise LLMError("OpenAI requires an API key.")
            return (
                self._build_openai_compatible(base_url, key, require_local=False),
                model or env_model or settings_model or "gpt-4o-mini",
                base_url,
            )

        if name in {"anthropic", "google_gemini"}:
            raise LLMError(
                f"Provider {name!r} can be saved in settings, but runtime support is not installed in this local build.",
            )

        raise LLMError(
            f"Unknown provider {name!r}."
        )

    def _build_openai_compatible(self, base_url: str, api_key: str, *, require_local: bool = True):
        if require_local:
            assert_local_endpoint(base_url)
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            raise LLMError("Install: pip install openai") from e
        return OpenAI(api_key=api_key, base_url=base_url)

    @property
    def provider(self) -> str:
        return self.provider_name

    @property
    def base_url(self) -> str:
        return self._base_url

    def list_models(self) -> list[str]:
        if hasattr(self._backend, "models"):
            models = self._backend.models.list()
            return sorted(
                str(getattr(item, "id", ""))
                for item in getattr(models, "data", [])
                if str(getattr(item, "id", "")).strip()
            )
        return []

    def complete(self, system: str, user: str, *, label: str = "") -> str:
        """Single-turn message → assistant text."""
        from app_settings import merge_system_prompt  # noqa: WPS433
        from prompt_budget import check_prompt_budget, log_prompt_metrics  # noqa: WPS433

        merged_system = merge_system_prompt(system)
        log_prompt_metrics(user, system=merged_system, label=label or "LLM prompt")
        try:
            check_prompt_budget(user, label=label or "LLM prompt")
        except RuntimeError as exc:
            raise LLMError(str(exc)) from exc
        return self._complete_openai_shape(merged_system, user, label=label)

    def run_agent(self, agent_name: str, user: str, agents_dir: Optional[Path] = None) -> str:
        base = agents_dir or (Path(__file__).resolve().parent.parent / "agents")
        prompt_path = base / agent_name / "prompt.md"
        if not prompt_path.exists():
            raise LLMError(f"Agent prompt not found: {prompt_path}")
        from llm_call_context import format_timestamp, get_llm_job_label  # noqa: WPS433

        ctx = get_llm_job_label()
        agent_label = f"Agent:{agent_name}"
        call_label = f"{ctx} · {agent_label}" if ctx else f"App · {agent_label} · {format_timestamp()}"
        from app_settings import effective_agent_prompt  # noqa: WPS433

        current_prompt = prompt_path.read_text(encoding="utf-8")
        return self.complete(
            effective_agent_prompt(agent_name, current_prompt),
            user,
            label=call_label,
        )

    def _complete_openai_shape(self, system: str, user: str, *, label: str = "") -> str:
        from llm_queue import QueueCancelledError, QueueFlushedError, get_llm_queue  # noqa: WPS433
        from log_redaction import safe_log  # noqa: WPS433

        queue = get_llm_queue()
        parts: list[str] = []
        queued_at = time.monotonic()
        queue_wait_ms = 0
        first_token_ms: int | None = None
        try:
            with queue.acquire(label) as slot:
                acquired_at = time.monotonic()
                queue_wait_ms = int((acquired_at - queued_at) * 1000)
                if slot.is_cancelled():
                    raise QueueCancelledError("Cancelled")
                stream = self._backend.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    stream=True,
                )

                def abort() -> None:
                    try:
                        stream.close()
                    except Exception:  # noqa: BLE001
                        pass

                slot.register_abort(abort)

                for chunk in stream:
                    if slot.is_cancelled():
                        abort()
                        raise QueueCancelledError("Cancelled")
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        if first_token_ms is None:
                            first_token_ms = int((time.monotonic() - acquired_at) * 1000)
                        parts.append(delta)
        except QueueFlushedError as e:
            raise LLMError(str(e)) from e
        except QueueCancelledError as e:
            raise LLMError("Cancelled") from e
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(str(e)) from e
        text = "".join(parts)
        if not text.strip():
            raise LLMError("Model returned an empty response")
        safe_log(
            "LLM timing metrics: "
            f"queue_wait_ms={queue_wait_ms}, "
            f"time_to_first_token_ms={first_token_ms if first_token_ms is not None else 'none'}, "
            f"total_ms={int((time.monotonic() - queued_at) * 1000)}",
        )
        return text
