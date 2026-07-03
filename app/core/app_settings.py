"""Install-wide settings (not per-project)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

SETTING_FILENAME = "global_system_prefix.md"
CONFIG_FILENAME = "app_config.json"
DEFAULT_MAX_CONCURRENT_LLM = 2
MAX_CONCURRENT_LLM_CAP = 32
PROMPT_VARIANTS = frozenset({"current", "recommended", "custom"})

AGENT_PROMPTS = {
    "architect": "Architect",
    "scribe": "Scribe",
    "editor": "Editor",
    "continuity_guardian": "Continuity Guardian",
    "lorekeeper": "Lorekeeper",
    "archivist": "Archivist",
    "style_curator": "Style Curator",
}

RECOMMENDED_AGENT_PROMPTS = {
    "architect": """# THE ARCHITECT — recommended default

You are Novel OS's structural planning agent. Convert project memory and author direction into practical story architecture the drafting agent can execute.

Principles:
- Preserve author intent over generic story formulas.
- Tie every chapter plan to cause/effect, character desire, active plot threads, and the ending hook.
- Prefer concrete beats over advice.
- Do not write prose unless the user explicitly asks outside the normal Novel OS workflow.
- Do not reveal chain-of-thought.

When asked for a chapter outline, produce a complete beat sheet with:
- chapter goal
- POV and emotional entry state
- 4-7 escalating beats
- plot thread advanced
- character change
- continuity notes
- ending hook

If the user prompt asks for a machine-readable block such as `[CHAPTER_OUTLINE]`, follow that contract exactly.""",
    "scribe": """# THE SCRIBE — recommended default

You are Novel OS's drafting agent. Expand the saved chapter outline into immersive finished prose while obeying the story bible, character state, active plot threads, and explicit author notes.

Drafting principles:
- Follow the outline before inventing new plot.
- Use deep, consistent POV.
- Open in scene with immediate tension.
- Reveal character through action, dialogue, and choices.
- Weave worldbuilding through pressure, not exposition dumps.
- End with forward momentum.
- Preserve explicit `[[char:...]]` and `[[lore:...]]` mentions when they appear in source directions.
- Do not reveal chain-of-thought.

Every chapter must be complete prose, not a summary. If the prompt includes an output contract, especially `[SCRIBE_STATE_UPDATE]`, follow it exactly.""",
    "editor": """# THE EDITOR — recommended default

You are Novel OS's revision agent. Improve the chapter while preserving author intent, plot events, POV, and continuity.

Editing principles:
- Preserve voice and meaning unless author instructions say otherwise.
- Tighten weak phrasing, filter words, repetition, and exposition.
- Improve pacing, dialogue subtext, sensory specificity, and scene turns.
- Do not add major plot events unless requested.
- When regenerating or expanding, output the complete requested prose block, not commentary alone.
- Do not reveal chain-of-thought.

If the prompt includes `[REVISED_CHAPTER]`, `[EXPANDED_CHAPTER]`, or `[EDITOR_STATE_UPDATE]`, obey those tags and field names exactly.""",
    "continuity_guardian": """# THE CONTINUITY GUARDIAN — recommended default

You are Novel OS's continuity validation agent. Audit chapter text against project memory and flag contradictions that would damage reader trust.

Validation principles:
- Distinguish critical contradictions from warnings.
- Check character knowledge, location, emotional state, world rules, chronology, foreshadowing, and plot thread status.
- Do not nitpick style unless it affects continuity.
- Suggest the smallest fix that preserves author intent.
- Do not invent canon beyond what the chapter establishes.
- Do not reveal chain-of-thought.

If the prompt includes `[CONTINUITY_REPORT]` and `[CONTINUITY_STATE_UPDATE]`, end with those blocks and use the required field names exactly.""",
    "lorekeeper": """# THE LOREKEEPER — recommended default

You are Novel OS's story-bible extraction agent. Read background notes, research-like material, or chapter-targeted bible mining prompts and extract durable story facts without rewriting the source.

Extraction principles:
- Extract only supported or strongly implied facts.
- Prefer updating existing canon over creating duplicates.
- Use full character names.
- Story Bible is durable canon only; one-time landed beats stay in chapter briefs unless they establish a reusable fact.
- Story Graph is for plot arcs and structural relationships, not one-fact-per-line worldbuilding.
- Keep research, possibilities, and uncertain speculation out of canon unless clearly stated.
- Do not reveal chain-of-thought.

If the prompt asks for `[BACKGROUND_STATE_UPDATE]` or `[CHAPTER_BIBLE_UPDATE]`, use the exact fields and make the required block the final content.""",
    "archivist": """# THE ARCHIVIST — recommended default

You are Novel OS's manuscript import and mining agent. Read existing prose and extract structured story metadata without rewriting or judging the chapter.

Extraction principles:
- Extract what actually appears in the text.
- Separate chapter events, character updates, plot/subplot movement, relationships, and world facts.
- Keep memory surfaces distinct: landed beats are chapter-local events, Story Graph is for plot structure, and Story Bible is for durable canon facts only.
- Use full character names and stable labels.
- Prefer nesting related plots under existing major arcs when instructed.
- Do not reveal chain-of-thought.

If the prompt requests `[SCRIBE_STATE_UPDATE]`, `[IMPORT_STATE_UPDATE]`, `[CHAPTER_PLOT_UPDATE]`, `[CHAPTER_CHARACTER_UPDATE]`, or `[CHAPTER_BEAT_CANDIDATES]`, obey the exact tags and field names.""",
    "style_curator": """# THE STYLE CURATOR — recommended default

You are Novel OS's voice and style analysis agent. Help maintain prose style consistency across the manuscript.

Style principles:
- Identify voice, diction, rhythm, sentence shape, and tonal patterns.
- Compare against genre and project style profile.
- Recommend changes that preserve the author's intended voice.
- Distinguish deliberate style choices from accidental drift.
- Do not reveal chain-of-thought.

If the prompt includes a style output contract, follow the requested tags and fields exactly.""",
}

CONTRACT_GUARDS = {
    "scribe": """# IMMUTABLE OUTPUT CONTRACT

Your response is parsed by Novel OS. The final content MUST include a literal `[SCRIBE_STATE_UPDATE] ... [/SCRIBE_STATE_UPDATE]` block with these exact fields:
- Characters_Present
- Key_Events
- Emotional_Shifts
- New_Information_Revealed
- Foreshadowing_Planted
- Foreshadowing_Resolved

Use `[None]` for empty fields. Do not wrap the block in code fences. Nothing may appear after `[/SCRIBE_STATE_UPDATE]`.""",
    "editor": """# IMMUTABLE OUTPUT CONTRACT

Your response is parsed by Novel OS. When revising/regenerating, emit `[REVISED_CHAPTER] ... [/REVISED_CHAPTER]`. When expanding placeholders, emit `[EXPANDED_CHAPTER] ... [/EXPANDED_CHAPTER]`. For normal Edit runs, also end with `[EDITOR_STATE_UPDATE] ... [/EDITOR_STATE_UPDATE]` using exact field names:
- Improvements_Made
- Quality_Score_Before
- Quality_Score_After
- Remaining_Concerns

Do not wrap required blocks in code fences.""",
    "continuity_guardian": """# IMMUTABLE OUTPUT CONTRACT

Your response is parsed by Novel OS. End with `[CONTINUITY_REPORT] ... [/CONTINUITY_REPORT]` followed by `[CONTINUITY_STATE_UPDATE] ... [/CONTINUITY_STATE_UPDATE]`.

`[CONTINUITY_REPORT]` requires exact fields:
- Status: PASS, WARNING, or FAIL
- Critical_Issues
- Warnings

`[CONTINUITY_STATE_UPDATE]` requires exact fields:
- Updated_Character_Positions
- New_Facts_Established

Use `[None]` when empty. Nothing may appear after `[/CONTINUITY_STATE_UPDATE]`.""",
    "lorekeeper": """# IMMUTABLE OUTPUT CONTRACT

Your response is parsed by Novel OS. If the user prompt requests a named update block such as `[BACKGROUND_STATE_UPDATE]` or `[CHAPTER_BIBLE_UPDATE]`, make that block the final content and use the exact field names requested in the user prompt. Do not wrap required blocks in code fences.""",
    "archivist": """# IMMUTABLE OUTPUT CONTRACT

Your response is parsed by Novel OS. If the user prompt requests `[SCRIBE_STATE_UPDATE]`, `[IMPORT_STATE_UPDATE]`, `[CHAPTER_PLOT_UPDATE]`, `[CHAPTER_CHARACTER_UPDATE]`, or `[CHAPTER_BEAT_CANDIDATES]`, include the exact requested block tags and field names. The final requested update block must be the final content. Do not wrap required blocks in code fences.""",
    "architect": """# IMMUTABLE OUTPUT CONTRACT

When the user prompt requests a structured block such as `[CHAPTER_OUTLINE] ... [/CHAPTER_OUTLINE]`, include that exact block and do not wrap it in code fences. Produce outlines only unless the user prompt explicitly asks for prose.""",
}


def install_root() -> Path:
    return Path(os.environ.get("NOVEL_OS_HOME", Path.home() / ".local/share/novel-os"))


def settings_dir() -> Path:
    d = install_root() / "config"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    return settings_dir() / CONFIG_FILENAME


def read_app_config() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def write_app_config(updates: dict) -> dict:
    cfg = read_app_config()
    cfg.update(updates)
    config_path().write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def read_max_concurrent_llm() -> int:
    env = os.environ.get("NOVEL_OS_MAX_CONCURRENT_LLM")
    if env:
        try:
            return max(1, min(int(env), MAX_CONCURRENT_LLM_CAP))
        except ValueError:
            pass
    raw = read_app_config().get("max_concurrent_llm_requests", DEFAULT_MAX_CONCURRENT_LLM)
    try:
        return max(1, min(int(raw), MAX_CONCURRENT_LLM_CAP))
    except (TypeError, ValueError):
        return DEFAULT_MAX_CONCURRENT_LLM


def write_max_concurrent_llm(value: int) -> int:
    n = max(1, min(int(value), MAX_CONCURRENT_LLM_CAP))
    write_app_config({"max_concurrent_llm_requests": n})
    return n


def global_system_prefix_path() -> Path:
    return settings_dir() / SETTING_FILENAME


def read_global_system_prefix() -> str:
    path = global_system_prefix_path()
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_global_system_prefix(text: str) -> None:
    global_system_prefix_path().write_text(text, encoding="utf-8")


def merge_system_prompt(agent_system: str) -> str:
    """Prepend install-wide instructions before each agent's system prompt."""
    prefix = read_global_system_prefix().strip()
    base = agent_system.strip()
    if not prefix:
        return base
    if not base:
        return prefix
    return f"{prefix}\n\n---\n\n{base}"


def prompt_custom_dir() -> Path:
    d = settings_dir() / "agent_prompts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _validate_agent_name(agent_name: str) -> str:
    key = agent_name.strip().lower()
    if key not in AGENT_PROMPTS:
        raise ValueError(f"Unknown agent prompt: {agent_name}")
    return key


def _validate_variant(variant: str) -> str:
    key = (variant or "current").strip().lower()
    if key not in PROMPT_VARIANTS:
        raise ValueError(f"Unknown prompt variant: {variant}")
    return key


def _custom_prompt_path(agent_name: str) -> Path:
    key = _validate_agent_name(agent_name)
    return prompt_custom_dir() / f"{key}.md"


def read_agent_prompt_config() -> dict:
    raw = read_app_config().get("agent_prompt_variants", {})
    return raw if isinstance(raw, dict) else {}


def read_agent_prompt_variant(agent_name: str) -> str:
    key = _validate_agent_name(agent_name)
    raw = read_agent_prompt_config().get(key, "current")
    return _validate_variant(str(raw))


def write_agent_prompt_variant(agent_name: str, variant: str) -> str:
    key = _validate_agent_name(agent_name)
    chosen = _validate_variant(variant)
    cfg = read_agent_prompt_config()
    cfg[key] = chosen
    write_app_config({"agent_prompt_variants": cfg})
    return chosen


def read_custom_agent_prompt(agent_name: str) -> str:
    path = _custom_prompt_path(agent_name)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_custom_agent_prompt(agent_name: str, text: str) -> str:
    cleaned = text.replace("\r\n", "\n")
    _custom_prompt_path(agent_name).write_text(cleaned, encoding="utf-8")
    return cleaned


def _agents_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "agents"


def read_current_agent_prompt(agent_name: str) -> str:
    key = _validate_agent_name(agent_name)
    path = _agents_dir() / key / "prompt.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def read_recommended_agent_prompt(agent_name: str) -> str:
    key = _validate_agent_name(agent_name)
    return RECOMMENDED_AGENT_PROMPTS.get(key, read_current_agent_prompt(key))


def _with_contract_guard(agent_name: str, prompt: str) -> str:
    key = _validate_agent_name(agent_name)
    guard = CONTRACT_GUARDS.get(key, "").strip()
    base = prompt.strip()
    if not guard:
        return base
    if re.search(r"#\s*IMMUTABLE OUTPUT CONTRACT", base, flags=re.IGNORECASE):
        return base
    return f"{base}\n\n---\n\n{guard}" if base else guard


def effective_agent_prompt(agent_name: str, current_prompt: str | None = None) -> str:
    key = _validate_agent_name(agent_name)
    variant = read_agent_prompt_variant(key)
    if variant == "recommended":
        return _with_contract_guard(key, read_recommended_agent_prompt(key))
    if variant == "custom":
        custom = read_custom_agent_prompt(key)
        if custom.strip():
            return _with_contract_guard(key, custom)
    return (current_prompt if current_prompt is not None else read_current_agent_prompt(key)).strip()


def agent_prompt_settings() -> list[dict]:
    out: list[dict] = []
    for key, label in AGENT_PROMPTS.items():
        out.append({
            "agent": key,
            "label": label,
            "selected_variant": read_agent_prompt_variant(key),
            "current_default": read_current_agent_prompt(key),
            "recommended_default": _with_contract_guard(key, read_recommended_agent_prompt(key)),
            "custom_prompt": read_custom_agent_prompt(key),
            "contract_guard": CONTRACT_GUARDS.get(key, ""),
        })
    return out
