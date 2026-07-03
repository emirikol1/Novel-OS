import json
import os
import re
import shutil
import sys
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable
from dataclasses import asdict

from . import db
from .models import (
    ChapterDetail, ChapterPasteResult, ChapterStages, ChapterSummary, CharacterDetail,
    ChapterStructureChapter, ChapterStructureIssue, ChapterStructureReport,
    CharacterSummary, DuplicateGroupModel, DuplicatesReport, MergeResult, PlotThreadSummary,
    StoryGraphNodeSummary, StoryGraphEdgeSummary, StoryGraphMigrateResult,
    EligibleGraphNodesResult, ChapterBeatSummary,
    ChapterBriefSummary,
    ChapterContextPreview,
    ChapterContextPreviewRequest,
    ContextPreviewCharacter,
    ContextPreviewBeat,
    ContextPreviewItem,
    ContextPreviewSection,
    ChapterBeatCandidate,
    ChapterBeatCandidatesResult,
    ApplyChapterBeatCandidatesRequest,
    ChapterMinePreview,
    ChapterMinePreviewSummary,
    ApplyChapterMinePreviewResult,
    ProjectDetail, ProjectSummary, StashedProjectSummary, AutoResolveResult, TimelineEventSummary,
    TimelineGenerationResult, TimelineGeneratedEvent, TimelineSkippedChapter,
    BibleDuplicateGroupModel, BibleDuplicateMember, BibleDuplicatesReport,
    BibleDedupeMerge, BibleAutoDedupeResult, ResearchSparkSummary,
    GraphDuplicateGroupModel, GraphDuplicatesReport, GraphAutoDedupeResult,
    ProjectMapSummary, ProjectMapDetail, MapPinSummary, GenerateChapterBriefsResult,
    GenerateChapterTitlesRequest, GenerateChapterTitlesResult, ChapterTitleResult,
    BatchExtractOutlineStats,
    PlanOutlinePreview,
    SplitChapterResult,
    ReviewableChangeModel, GenerateGraphSuggestionsResult, MineAllResult,
)
from . import map_assets
from . import portrait_assets

# core/ modules import each other by top-level name; put core/ on the path once.
_CORE = Path(__file__).resolve().parent.parent / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from state_manager import StoryState, Character, PlotThread, TimelineEvent, ChapterState  # noqa: E402
from relationship_roles import parse_relationship_label, stringify_relationship_label  # noqa: E402
from story_graph import (  # noqa: E402
    ChapterBeat,
    ChapterBrief,
    StoryGraphEdge,
    StoryGraphLayout,
    StoryGraphNode,
    character_display_name,
    eligible_graph_nodes,
    new_chapter_beat_id,
    node_eligible_at_chapter,
    normalize_brief_characters,
    sync_brief_active_from_pin,
    sync_chapter_pins_for_brief,
    validate_brief_active_nodes,
)
from reviewable_changes import (  # noqa: E402
    ReviewableChange,
    ReviewableChangeActionError,
    apply_reviewable_change,
    dismiss_reviewable_change,
    generate_graph_reviewable_changes,
    mark_reviewable_change_reviewed,
    revert_reviewable_change,
)


class ProjectNotFound(Exception):
    pass


class ChapterNotFound(Exception):
    pass


class CharacterNotFound(Exception):
    pass


class PlotThreadNotFound(Exception):
    pass


class TimelineEventNotFound(Exception):
    pass


class ResearchSparkNotFound(Exception):
    pass


class ProjectMapNotFound(Exception):
    pass


class MapPinNotFound(Exception):
    pass


class StoryGraphNodeNotFound(Exception):
    pass


class StoryGraphEdgeNotFound(Exception):
    pass


class ChapterBriefNotFound(Exception):
    pass


class ChapterBeatNotFound(Exception):
    pass


class ReviewableChangeNotFound(Exception):
    pass


_TIMELINE_EVENT_TYPES = frozenset({"scene", "backstory", "flashback", "summary"})
_TIMELINE_SIGNIFICANCE = frozenset({"minor", "major", "turning_point", "climax"})
_RESEARCH_KINDS = frozenset({"note", "link", "quote", "image", "idea"})


def _normalize_relationships_for_storage(value):
    """Normalize known role/subrole labels while preserving custom free text."""
    if not isinstance(value, dict):
        return value
    normalized = {}
    for target_id, label in value.items():
        raw = str(label or "").strip()
        parsed = parse_relationship_label(raw)
        if parsed.role:
            normalized[target_id] = stringify_relationship_label(parsed.role, parsed.subrole, parsed.note)
        else:
            normalized[target_id] = raw
    return normalized


class NoSourceArtifact(Exception):
    """Raised when promoting to Final but no draft/revised exists to promote."""
    pass


class NothingToUnfinalize(Exception):
    """Raised when a chapter has no final text and is not marked complete."""
    pass


class BadRequest(Exception):
    pass


def build_orchestrator(project_dir: str):
    """Construct a NovelOrchestrator for a project folder. Patchable in tests."""
    from orchestrator import NovelOrchestrator  # noqa: E402 (lazy: heavy import)
    return NovelOrchestrator(project_dir)


# stage -> how to invoke it on an orchestrator with the given params
PHASES: dict[str, Callable[[object, dict], object]] = {
    "plan_outline": lambda o, p: o.plan_outline(int(p.get("chapters", 12)), int(p.get("words", 24000))),
    "plan_chapter": lambda o, p: o.plan_chapter(int(p["number"]), p.get("summary", ""), p.get("pov", "")),
    "write": lambda o, p: o.write_chapter(int(p["number"])),
    "edit": lambda o, p: o.edit_chapter(
        int(p["number"]), p.get("mode", "line"), p.get("instructions", ""),
    ),
    "validate": lambda o, p: o.validate_chapter(int(p["number"])),
    "approve": None,  # handled in ProjectService.approve_chapter (includes draft→final promote)
}


def _operational_log(msg: str) -> None:
    """Sanitized progress line for backend.log (no manuscript prose)."""
    from log_redaction import safe_log  # noqa: WPS433

    safe_log(msg)


def _slugify(text: str) -> str:
    out = "".join(c.lower() if c.isalnum() else "-" for c in text.strip())
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "untitled"


def _read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def _has_stage_content(path: Path) -> bool:
    text = _read(path)
    return bool(text and text.strip())


def _atomic_write(path: Path, text: str) -> None:
    """Write via temp file + os.replace so a Final is never left half-written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


class ProjectService:
    """Reads Novel OS projects (folders containing outputs/state/story_state.json)."""

    def __init__(self, root: Path):
        self.root = Path(root)

    @property
    def stashed_root(self) -> Path:
        return Path(os.environ.get("NOVEL_OS_STASHED_DIR", self.root.parent / "stashed"))

    # --- discovery
    def _project_dir(self, project_id: str) -> Path:
        d = self.root / project_id
        if not (d / "outputs" / "state" / "story_state.json").exists():
            raise ProjectNotFound(project_id)
        return d

    def _load(self, project_id: str) -> StoryState:
        return StoryState(str(self._project_dir(project_id)), persist_migration=True)

    @staticmethod
    def _project_summary_from_state_file(child: Path, state_file: Path) -> ProjectSummary:
        """Lightweight JSON read for project listing — no migration persist."""
        data = json.loads(state_file.read_text(encoding="utf-8"))
        metadata = data.get("metadata", {})
        return ProjectSummary(
            id=child.name,
            title=metadata.get("title", child.name),
            genre=metadata.get("genre", ""),
            chapter_count=len(data.get("chapters", {})),
            status=metadata.get("status", "in_progress"),
        )

    def list_projects(self) -> list[ProjectSummary]:
        out: list[ProjectSummary] = []
        if not self.root.exists():
            return out
        for child in sorted(self.root.iterdir()):
            if not child.is_dir():
                continue
            state_file = child / "outputs" / "state" / "story_state.json"
            if not state_file.exists():
                continue
            out.append(self._project_summary_from_state_file(child, state_file))
        return out

    def project_detail(self, project_id: str) -> ProjectDetail:
        s = self._load(project_id)
        proj = self._project_dir(project_id)
        return ProjectDetail(
            id=project_id,
            title=s.metadata.get("title", project_id),
            genre=s.metadata.get("genre", ""),
            author=s.metadata.get("author", ""),
            chapter_count=len(s.chapters),
            status=s.metadata.get("status", "in_progress"),
            style={
                "tone": s.style_profile.tone,
                "point_of_view": s.style_profile.point_of_view,
                "prose_style": s.style_profile.prose_style,
                "tense": s.style_profile.tense,
                "vocabulary_level": s.style_profile.vocabulary_level,
                "description": s.style_profile.description,
                "paragraph_format": s.style_profile.paragraph_format,
                "chapter_target_words": str(s.style_profile.chapter_target_words),
            },
            project_path=str(proj),
            story_state_path=str(proj / "outputs" / "state" / "story_state.json"),
            manuscript_path=str(proj / "outputs" / "manuscript"),
        )

    def validate_chapter_structure(self, project_id: str) -> ChapterStructureReport:
        proj = self._project_dir(project_id)
        state_path = proj / "outputs" / "state" / "story_state.json"
        manuscript_path = proj / "outputs" / "manuscript"
        s = self._load(project_id)
        issues: list[ChapterStructureIssue] = []

        def issue(
            severity: str,
            component: str,
            message: str,
            chapter: int | None = None,
            path: Path | None = None,
            resolution: str = "",
            action_url: str | None = None,
        ) -> None:
            issues.append(ChapterStructureIssue(
                severity=severity,
                chapter=chapter,
                component=component,
                message=message,
                path=str(path) if path is not None else None,
                resolution=resolution,
                action_url=action_url,
            ))

        if not state_path.exists():
            issue("error", "state", "Missing story_state.json", path=state_path,
                  resolution="Restore this project from backup or recreate the missing state file.")
        if not manuscript_path.exists():
            issue("warning", "manuscript", "Missing manuscript folder", path=manuscript_path,
                  resolution="Create or regenerate manuscript artifacts for chapters that need prose.")

        chapter_numbers = sorted(s.chapters)
        expected = list(range(1, len(chapter_numbers) + 1))
        if chapter_numbers and chapter_numbers != expected:
            issue(
                "warning",
                "numbering",
                f"Chapter numbers contain gaps or offsets: {chapter_numbers}. Use Remove Gaps to compact them.",
                resolution="Click Remove Gaps in Writing progress to renumber chapters sequentially.",
            )

        raw_state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        raw_chapters = raw_state.get("chapters", {})
        if isinstance(raw_chapters, dict):
            for key, raw in raw_chapters.items():
                try:
                    key_num = int(key)
                except (TypeError, ValueError):
                    issue("error", "state", f"Chapter key is not numeric: {key!r}",
                          resolution="Repair story_state.json so chapter keys are numeric.")
                    continue
                if isinstance(raw, dict) and int(raw.get("number", key_num)) != key_num:
                    issue(
                        "error",
                        "state",
                        f"Chapter key {key_num} does not match stored number {raw.get('number')}",
                        chapter=key_num,
                        path=state_path,
                        resolution="Use Renumber on this chapter or repair story_state.json so the key and number match.",
                        action_url=f"/projects/{project_id}/chapters/{key_num}",
                    )

        asset_numbers: dict[int, list[Path]] = {}
        chapter_asset_re = re.compile(r"chapter_(\d{3})")
        outputs = proj / "outputs"
        if outputs.exists():
            for path in outputs.rglob("*chapter_[0-9][0-9][0-9]*"):
                if not path.is_file():
                    continue
                if path.parent == outputs / "sources":
                    continue
                match = chapter_asset_re.search(path.name)
                if not match:
                    continue
                asset_numbers.setdefault(int(match.group(1)), []).append(path)
        for asset_num, paths in sorted(asset_numbers.items()):
            if asset_num not in s.chapters:
                issue(
                    "error",
                    "assets",
                    f"Found {len(paths)} chapter asset(s) for missing chapter {asset_num}",
                    chapter=asset_num,
                    path=paths[0],
                    resolution="Restore this chapter if it was deleted accidentally, or remove/rename the orphan asset.",
                )

        raw_briefs = raw_state.get("chapter_briefs", {})
        if isinstance(raw_briefs, dict):
            for key, raw in raw_briefs.items():
                try:
                    key_num = int(key)
                except (TypeError, ValueError):
                    issue("error", "brief", f"Brief key is not numeric: {key!r}",
                          resolution="Repair story_state.json so chapter brief keys are numeric.")
                    continue
                brief_num = raw.get("chapter_number", key_num) if isinstance(raw, dict) else key_num
                if int(brief_num) != key_num:
                    issue(
                        "error",
                        "brief",
                        f"Brief key {key_num} does not match stored chapter_number {brief_num}",
                        chapter=key_num,
                        path=state_path,
                        resolution="Open the chapter brief and save it again, or repair the brief number in story_state.json.",
                        action_url=f"/projects/{project_id}/chapters/{key_num}",
                    )
                if key_num not in s.chapters:
                    issue("error", "brief", f"Brief exists for missing chapter {key_num}", chapter=key_num, path=state_path,
                          resolution="Restore the missing chapter or remove the orphan chapter brief.")

        chapters: list[ChapterStructureChapter] = []
        for chapter in sorted(s.chapters.values(), key=lambda c: c.number):
            paths = self._stage_paths(project_id, chapter.number)
            stages_present = [stage for stage, path in paths.items() if path.exists()]
            has_brief = chapter.number in s.chapter_briefs
            if chapter.status != "planned" and not stages_present:
                issue(
                    "warning",
                    "stages",
                    "Chapter is not planned but has no outline/draft/revised/final stage files",
                    chapter=chapter.number,
                    resolution="Open the chapter and generate, paste, or restore manuscript stage content.",
                    action_url=f"/projects/{project_id}/chapters/{chapter.number}",
                )
            if not has_brief:
                issue("warning", "brief", "Chapter has no chapter brief", chapter=chapter.number,
                      resolution="Open the chapter and generate or save a chapter brief.",
                      action_url=f"/projects/{project_id}/chapters/{chapter.number}")
            chapters.append(ChapterStructureChapter(
                number=chapter.number,
                title=chapter.title,
                status=chapter.status,
                stages_present=stages_present,
                has_brief=has_brief,
                asset_count=len(asset_numbers.get(chapter.number, [])),
            ))

        error_count = sum(1 for row in issues if row.severity == "error")
        warning_count = sum(1 for row in issues if row.severity == "warning")
        return ChapterStructureReport(
            ok=error_count == 0,
            error_count=error_count,
            warning_count=warning_count,
            project_path=str(proj),
            story_state_path=str(state_path),
            manuscript_path=str(manuscript_path),
            issues=issues,
            chapters=chapters,
        )

    def update_style_profile(self, project_id: str, updates: dict) -> ProjectDetail:
        s = self._load(project_id)
        allowed = {
            "tone",
            "point_of_view",
            "tense",
            "prose_style",
            "vocabulary_level",
            "description",
            "paragraph_format",
            "chapter_target_words",
        }
        paragraph_formats = {"block", "indented"}
        for key, value in updates.items():
            if key in allowed and value is not None:
                if key == "chapter_target_words":
                    try:
                        setattr(s.style_profile, key, max(1, int(str(value).strip())))
                    except (TypeError, ValueError):
                        raise BadRequest("chapter_target_words must be a positive integer") from None
                elif key == "paragraph_format":
                    fmt = str(value).strip() or "block"
                    if fmt not in paragraph_formats:
                        raise BadRequest("paragraph_format must be 'block' or 'indented'")
                    setattr(s.style_profile, key, fmt)
                else:
                    setattr(s.style_profile, key, str(value).strip())
        s.save_state()
        return self.project_detail(project_id)

    def preview_plan_outline(self, project_id: str, chapters: int = 12, words: int = 24000) -> PlanOutlinePreview:
        s = self._load(project_id)
        if chapters < 1 or chapters > 120:
            raise BadRequest("chapters must be between 1 and 120")
        if words < 1000:
            raise BadRequest("words must be at least 1000")
        outline = self._build_outline_payload(s, chapters, words)
        summary = [
            f"Title: {s.metadata.get('title', project_id)}",
            f"Genre: {s.metadata.get('genre', 'Unknown')}",
            f"Target: {chapters} chapters / {words:,} words",
            f"Style: {s.style_profile.tone}, {s.style_profile.point_of_view}, {s.style_profile.tense}, {s.style_profile.prose_style}",
            f"Cast entries: {len(s.characters)}",
            f"Story graph nodes: {len(s.story_graph_nodes)}",
            f"Timeline events: {len(s.timeline)}",
        ]
        return PlanOutlinePreview(outline=outline, context_summary=summary)

    def apply_plan_outline(self, project_id: str, chapters: int = 12, words: int = 24000) -> PlanOutlinePreview:
        preview = self.preview_plan_outline(project_id, chapters, words)
        path = self._project_dir(project_id) / "outputs" / "outline.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(preview.outline, indent=2), encoding="utf-8")
        s = self._load(project_id)
        for item in preview.outline.get("chapter_summaries", []):
            number = int(item.get("number", 0))
            if number <= 0:
                continue
            scenes = [str(scene).strip() for scene in item.get("scenes", []) if str(scene).strip()]
            per_chapter_target = int(item.get("word_count_target", max(1, words // chapters)))
            project_default = s.style_profile.chapter_target_words or 2500
            brief_target = (
                per_chapter_target
                if per_chapter_target != project_default
                else 0
            )
            if number not in s.chapters:
                s.chapters[number] = ChapterState(
                    number=number,
                    title=str(item.get("title", f"Chapter {number}")),
                    status="planned",
                )
            if number not in s.chapter_briefs:
                s.set_chapter_brief(ChapterBrief(
                    chapter_number=number,
                    pov_mode=s.style_profile.point_of_view or "third_limited",
                    target_word_count=brief_target,
                    ending_hook=str(item.get("ending_hook", "")),
                    continuity_notes=str(item.get("continuity_notes", "")),
                ))
            if scenes:
                from chapter_brief_utils import merge_planned_beats  # noqa: WPS433

                s.set_chapter_beats(number, merge_planned_beats(s, number, scenes))
            chapter = s.chapters.get(number)
            brief = s.get_chapter_brief(number)
            if chapter is not None and brief is not None:
                from story_graph import apply_brief_target_to_chapter  # noqa: WPS433

                apply_brief_target_to_chapter(s, chapter, brief)
        s.save_state()
        return preview

    @staticmethod
    def _build_outline_payload(s: StoryState, chapters: int, words: int) -> dict:
        act1_end = max(1, int(chapters * 0.25))
        act2_end = max(act1_end + 1, int(chapters * 0.75)) if chapters > 1 else 1
        graph_focus = [
            {
                "id": node.id,
                "title": node.title,
                "kind": node.kind,
                "priority": node.priority,
                "status": node.status,
            }
            for node in sorted(
                s.story_graph_nodes.values(),
                key=lambda n: (-n.priority, n.sort_order, n.title),
            )[:20]
        ]
        return {
            "metadata": {
                "title": s.metadata.get("title", "Untitled"),
                "genre": s.metadata.get("genre", "Unknown"),
                "target_chapters": chapters,
                "target_word_count": words,
                "created": datetime.now(timezone.utc).isoformat(),
                "style": {
                    "tone": s.style_profile.tone,
                    "point_of_view": s.style_profile.point_of_view,
                    "tense": s.style_profile.tense,
                    "prose_style": s.style_profile.prose_style,
                    "vocabulary_level": s.style_profile.vocabulary_level,
                    "description": s.style_profile.description,
                },
            },
            "acts": [
                {"act_number": 1, "name": "Setup", "chapters": list(range(1, act1_end + 1)), "percent": 25},
                {"act_number": 2, "name": "Confrontation", "chapters": list(range(act1_end + 1, act2_end + 1)), "percent": 50},
                {"act_number": 3, "name": "Resolution", "chapters": list(range(act2_end + 1, chapters + 1)), "percent": 25},
            ],
            "chapter_summaries": [
                {
                    "number": i,
                    "title": f"Chapter {i}",
                    "status": "planned",
                    "pov_character": "",
                    "summary": "",
                    "word_count_target": max(1, words // chapters),
                    "active_story_graph_nodes": [],
                    "ending_hook": "",
                    "continuity_notes": "",
                    "scenes": [],
                }
                for i in range(1, chapters + 1)
            ],
            "planning_context": {
                "cast": [c.full_name for c in s.characters.values()],
                "story_graph_focus": graph_focus,
                "timeline_event_count": len(s.timeline),
            },
        }

    def _chapter_pipeline_step(self, project_id: str, number: int, status: str) -> str:
        """Furthest completed pipeline milestone (for chapter status lights).

        Green (final) requires a saved Final manuscript. Pink (approved) is Approve
        without Final yet — distinct from orchestrator status ``complete``.
        """
        p = self._stage_paths(project_id, number)
        if _has_stage_content(p["final"]):
            return "final"
        try:
            db_text = db.get_artifact_text(project_id, number, "final")
            if db_text and db_text.strip():
                return "final"
        except Exception:  # noqa: BLE001
            pass
        if status == "complete":
            return "approved"
        if status == "validated":
            return "validated"
        if _has_stage_content(p["revised"]) or status in ("edited", "editing"):
            return "revised"
        if _has_stage_content(p["draft"]) or status in ("drafted", "drafting"):
            return "drafted"
        return "none"

    def _chapter_summary(self, project_id: str, c) -> ChapterSummary:
        from chapter_display import chapter_display_label  # noqa: WPS433
        from prompt_context import format_chapter_pov_display  # noqa: WPS433

        s = self._load(project_id)
        pov = format_chapter_pov_display(s, c.number, chapter=c) or c.pov_character or ""
        return ChapterSummary(
            number=c.number,
            display_label=chapter_display_label(c),
            title=c.title or "",
            title_source=(getattr(c, "title_source", "") or "").strip(),
            status=c.status,
            word_count=c.word_count,
            pov=pov,
            pipeline_step=self._chapter_pipeline_step(project_id, c.number, c.status),
            has_brief=c.number in s.chapter_briefs,
            part_of=int(getattr(c, "part_of", 0) or 0),
            part_label=(getattr(c, "part_label", "") or "").strip(),
        )

    def list_chapters(self, project_id: str) -> list[ChapterSummary]:
        from chapter_display import chapter_sort_key  # noqa: WPS433

        s = self._load(project_id)
        return [
            self._chapter_summary(project_id, c)
            for c in sorted(s.chapters.values(), key=chapter_sort_key)
        ]

    def chapter_detail(self, project_id: str, number: int) -> ChapterDetail:
        s = self._load(project_id)
        c = s.chapters.get(number)
        if c is None:
            raise ChapterNotFound(number)
        summary = self._chapter_summary(project_id, c)
        proj = self._project_dir(project_id)
        nnn = f"{number:03d}"
        outline_path = proj / "outputs" / f"chapter_{nnn}_outline.md"
        draft_path = proj / "outputs" / "manuscript" / f"chapter_{nnn}_draft.md"
        return ChapterDetail(
            **summary.model_dump(),
            outline=outline_path.read_text(encoding="utf-8") if outline_path.exists() else None,
            draft=draft_path.read_text(encoding="utf-8") if draft_path.exists() else None,
        )

    def list_characters(self, project_id: str) -> list[CharacterSummary]:
        s = self._load(project_id)
        return [self._character_summary(project_id, c) for c in s.get_all_characters()]

    def _character_portrait_url(self, project_id: str, character_id: str) -> str:
        return f"/api/projects/{project_id}/characters/{character_id}/portrait"

    def _character_summary(self, project_id: str, char: Character) -> CharacterSummary:
        portrait_url = (
            self._character_portrait_url(project_id, char.id)
            if char.portrait_filename else None
        )
        return CharacterSummary(
            id=char.id,
            full_name=char.full_name,
            role=char.role,
            aliases=list(char.aliases),
            portrait_url=portrait_url,
        )

    def _plot_thread_summary(self, t: PlotThread) -> PlotThreadSummary:
        return PlotThreadSummary(
            id=t.id,
            name=t.name,
            description=t.description,
            thread_type=t.thread_type,
            status=t.status,
            priority=t.priority,
            sort_order=t.sort_order,
            subplots=list(t.subplots or []),
        )

    def list_plot_threads(self, project_id: str) -> list[PlotThreadSummary]:
        s = self._load(project_id)
        return [self._plot_thread_summary(t) for t in s.get_ordered_plot_threads()]

    def reorder_plot_threads(self, project_id: str, ordered_ids: list[str]) -> list[PlotThreadSummary]:
        s = self._load(project_id)
        missing = [tid for tid in ordered_ids if tid not in s.plot_threads]
        if missing:
            raise BadRequest(f"Unknown plot thread id(s): {', '.join(missing)}")
        if len(ordered_ids) != len(s.plot_threads):
            raise BadRequest("ordered_ids must include every plot thread exactly once.")
        s.reorder_plot_threads(ordered_ids)
        s.save_state()
        return self.list_plot_threads(project_id)

    def raw_state(self, project_id: str) -> dict:
        import json as _json
        sf = self._project_dir(project_id) / "outputs" / "state" / "story_state.json"
        return _json.loads(sf.read_text(encoding="utf-8"))

    # ----- M2: pipeline stages + editable Final

    def _stage_paths(self, project_id: str, number: int) -> dict[str, Path]:
        proj = self._project_dir(project_id)
        nnn = f"{number:03d}"
        return {
            "outline": proj / "outputs" / f"chapter_{nnn}_outline.md",
            "draft": proj / "outputs" / "manuscript" / f"chapter_{nnn}_draft.md",
            "revised": proj / "outputs" / "manuscript" / f"chapter_{nnn}_revised.md",
            "final": proj / "outputs" / "manuscript" / f"chapter_{nnn}_final.md",
        }

    def ensure_chapter(self, project_id: str, number: int) -> None:
        """Raise ProjectNotFound / ChapterNotFound if the chapter doesn't exist."""
        s = self._load(project_id)
        if number not in s.chapters:
            raise ChapterNotFound(number)

    def get_final_text(self, project_id: str, number: int) -> str | None:
        return _read(self._stage_paths(project_id, number)["final"])

    def _get_final_text_for_export(self, project_id: str, number: int) -> str | None:
        """Final manuscript text from file, with DB artifact fallback."""
        text = _read(self._stage_paths(project_id, number)["final"])
        if text and text.strip():
            return text
        try:
            db_text = db.get_artifact_text(project_id, number, "final")
            if db_text and db_text.strip():
                return db_text
        except Exception:  # noqa: BLE001
            pass
        return None

    def chapter_stages(self, project_id: str, number: int) -> ChapterStages:
        s = self._load(project_id)
        c = s.chapters.get(number)
        if c is None:
            raise ChapterNotFound(number)
        # keep the DB mirror fresh with whatever the engine produced
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001 - ingest is best-effort
            pass
        p = self._stage_paths(project_id, number)
        return ChapterStages(
            number=number,
            status=c.status,
            outline=_read(p["outline"]),
            draft=_read(p["draft"]),
            revised=_read(p["revised"]),
            final=_read(p["final"]),
            continuity=c.continuity_checks or None,
        )

    def _commit_final(self, project_id: str, number: int, text: str) -> int:
        """Write final.md atomically, update chapter word_count + timestamp, persist."""
        s = self._load(project_id)
        c = s.chapters.get(number)
        if c is None:
            raise ChapterNotFound(number)
        _atomic_write(self._stage_paths(project_id, number)["final"], text)
        wc = len(text.split())
        c.word_count = wc
        c.last_modified = datetime.now(timezone.utc).isoformat()
        s.save_state()
        # DB is the system-of-record for the human-owned Final
        try:
            db.upsert_artifact(project_id, number, "final", text)
        except Exception:  # noqa: BLE001
            pass
        return wc

    def promote_final(self, project_id: str, number: int, force: bool = False) -> str:
        """Seed Final from revised||draft. Idempotent: never clobbers a human edit unless forced."""
        p = self._stage_paths(project_id, number)
        if _has_stage_content(p["final"]) and not force:
            return p["final"].read_text(encoding="utf-8")
        source = _read(p["revised"]) if _has_stage_content(p["revised"]) else _read(p["draft"])
        if source is None or not source.strip():
            raise NoSourceArtifact(number)
        self._commit_final(project_id, number, source)
        return source

    def approve_chapter(self, project_id: str, number: int) -> None:
        """Approve a chapter; when no revised text exists, promote draft to final."""
        self._project_dir(project_id)
        orch = build_orchestrator(str(self.root / project_id))
        if not orch.approve_chapter(number):
            return
        p = self._stage_paths(project_id, number)
        if not _has_stage_content(p["revised"]) and not _has_stage_content(p["final"]):
            try:
                self.promote_final(project_id, number)
            except NoSourceArtifact:
                pass
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass

    def save_final(self, project_id: str, number: int, text: str) -> int:
        return self._commit_final(project_id, number, text)

    def unfinalize_chapter(self, project_id: str, number: int) -> ChapterStages:
        """Remove Final and roll back validate/approve so Revise can run again."""
        s = self._load(project_id)
        c = s.chapters.get(number)
        if c is None:
            raise ChapterNotFound(number)
        p = self._stage_paths(project_id, number)
        final_text = _read(p["final"])
        if final_text is None:
            try:
                final_text = db.get_artifact_text(project_id, number, "final")
            except Exception:  # noqa: BLE001
                pass
        has_final = bool(final_text and final_text.strip())
        post_revise = c.status in ("complete", "validated") or has_final
        if not post_revise:
            raise NothingToUnfinalize(number)

        if has_final and final_text:
            _atomic_write(p["draft"], final_text)
            _atomic_write(p["revised"], final_text)
            try:
                db.upsert_artifact(project_id, number, "draft", final_text)
                db.upsert_artifact(project_id, number, "revised", final_text)
                db.delete_artifact(project_id, number, "final")
            except Exception:  # noqa: BLE001
                pass
            if p["final"].exists():
                p["final"].unlink()
            c.word_count = len(final_text.split())

        c.status = "edited"
        c.continuity_checks = {}
        c.last_modified = datetime.now(timezone.utc).isoformat()
        s.save_state()
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return self.chapter_stages(project_id, number)

    # ----- Tier 0: create / edit the world

    def create_project(
        self,
        title: str,
        genre: str,
        author: str = "",
        *,
        for_import: bool = False,
    ) -> ProjectSummary:
        title = title.strip()
        if not title:
            raise BadRequest("Title is required.")
        slug = _slugify(title)
        folder = self.root / slug
        n = 2
        while (folder / "outputs" / "state" / "story_state.json").exists():
            folder = self.root / f"{slug}-{n}"
            n += 1
        folder.mkdir(parents=True, exist_ok=True)
        build_orchestrator(str(folder)).init_project(title, genre, author)
        state = self._load(folder.name)
        if not for_import:
            from starter_seed import seed_starter_project  # noqa: WPS433
            seed_starter_project(state)
            state.save_state()
        try:
            db.ingest_project(self.root, folder.name)
        except Exception:  # noqa: BLE001
            pass
        return ProjectSummary(
            id=folder.name,
            title=title,
            genre=genre,
            chapter_count=len(state.chapters),
            status="in_progress",
        )

    def add_character(self, project_id: str, name: str, role: str) -> list[CharacterSummary]:
        self._project_dir(project_id)  # 404 if missing
        if not name.strip():
            raise BadRequest("Character name is required.")
        build_orchestrator(str(self.root / project_id)).add_character(name.strip(), role)
        return self.list_characters(project_id)

    def make_phase_job(self, project_id: str, stage: str, params: dict) -> Callable[[], None]:
        """Validate inputs and return a 0-arg callable the JobRunner can run."""
        self._project_dir(project_id)  # 404 if missing
        if stage not in PHASES:
            raise BadRequest(f"Unknown stage '{stage}'. Expected one of {sorted(PHASES)}.")
        project_dir = str(self.root / project_id)

        def fn() -> None:
            if stage == "approve":
                self.approve_chapter(project_id, int(params["number"]))
                return
            orch = build_orchestrator(project_dir)
            phase_fn = PHASES[stage]
            if phase_fn is None:
                raise BadRequest(f"Unknown stage '{stage}'.")
            phase_fn(orch, params)

        return fn

    def make_import_job(
        self,
        chapters_dir: str,
        *,
        title: str = "",
        genre: str = "",
        author: str = "",
        project_id: str = "",
        synthesize: bool = True,
        no_extract: bool = False,
        from_chapter: int | None = None,
        to_chapter: int | None = None,
    ) -> tuple[Callable[[], None], str]:
        """Return (callable, project_id) for a background import job."""
        from import_pipeline import ImportPipeline  # noqa: E402

        src = Path(chapters_dir).expanduser()
        if not src.is_dir():
            raise BadRequest(f"Chapters directory not found: {chapters_dir}")

        if project_id:
            proj_path = str(self._project_dir(project_id))
            resolved_id = project_id
        else:
            if not title.strip() or not genre.strip():
                raise BadRequest("Title and genre are required for a new import.")
            summary = self.create_project(
                title.strip(), genre.strip(), author.strip(), for_import=True,
            )
            resolved_id = summary.id
            proj_path = str(self.root / resolved_id)

        def fn() -> None:
            pipe = ImportPipeline(proj_path)
            pipe.import_directory(
                src,
                chapter_from=from_chapter,
                chapter_to=to_chapter,
                extract=not no_extract,
                dry_run=False,
                on_progress=_operational_log,
            )
            if synthesize and not no_extract:
                from job_control import check_job_cancelled  # noqa: WPS433

                check_job_cancelled()
                pipe.synthesize_structure(on_progress=_operational_log)
                pipe.write_character_profiles()
            try:
                db.ingest_project(self.root, resolved_id)
            except Exception:  # noqa: BLE001
                pass

        return fn, resolved_id

    def preview_ebook_upload(self, content: bytes, filename: str):
        from ebook_importer import parse_ebook  # noqa: E402
        from import_staging import save_upload  # noqa: E402
        from api.models import EbookChapterPreview, EbookParsePreview  # noqa: E402

        upload_id, path = save_upload(content, filename)
        parsed = parse_ebook(path)
        chapters = [
            EbookChapterPreview(
                number=ch.number,
                title=ch.title,
                word_count=len(ch.text.split()),
            )
            for ch in parsed.chapters
        ]
        total_words = sum(c.word_count for c in chapters)
        return EbookParsePreview(
            upload_id=upload_id,
            filename=Path(filename).name,
            title=parsed.metadata.title,
            author=parsed.metadata.author,
            language=parsed.metadata.language,
            source_format=parsed.metadata.source_format,
            split_strategy=parsed.metadata.split_strategy,
            chapters=chapters,
            total_words=total_words,
            notes=parsed.metadata.notes,
        )

    def _resolve_ebook_source(self, source_path: str, upload_id: str) -> Path:
        if upload_id.strip():
            from import_staging import resolve_upload  # noqa: E402

            return resolve_upload(upload_id)
        if not source_path.strip():
            raise BadRequest("upload_id or source_path is required")
        src = Path(source_path).expanduser()
        if not src.exists():
            raise BadRequest(f"Source not found: {source_path}")
        return src

    def make_ebook_import_job(
        self,
        source_path: str = "",
        *,
        upload_id: str = "",
        title: str = "",
        genre: str = "",
        author: str = "",
        project_id: str = "",
        split_strategy: str = "auto",
        parts: int | None = None,
        synthesize: bool = True,
        no_extract: bool = False,
        from_chapter: int | None = None,
        to_chapter: int | None = None,
    ) -> tuple[Callable[[], None], str]:
        """Return (callable, project_id) for a background ebook import job."""
        from ebook_importer import import_ebook, parse_ebook  # noqa: E402

        src = self._resolve_ebook_source(source_path, upload_id)

        parsed = parse_ebook(src, split_strategy=split_strategy, parts=parts)
        resolved_title = title.strip() or parsed.metadata.title
        if not project_id:
            if not resolved_title or not genre.strip():
                raise BadRequest(
                    "Genre is required for a new import; title can be auto-detected from the file."
                )
            summary = self.create_project(
                resolved_title, genre.strip(), author.strip(), for_import=True,
            )
            resolved_id = summary.id
        else:
            resolved_id = project_id
            self._project_dir(project_id)

        proj_path = str(self.root / resolved_id)

        def fn() -> None:
            import_ebook(
                src,
                proj_path,
                title=resolved_title,
                genre=genre.strip(),
                author=author.strip(),
                split_strategy=split_strategy,
                parts=parts,
                extract=not no_extract,
                from_chapter=from_chapter,
                to_chapter=to_chapter,
                on_progress=_operational_log,
            )
            if synthesize and not no_extract:
                from import_pipeline import ImportPipeline  # noqa: E402
                from job_control import check_job_cancelled  # noqa: WPS433

                check_job_cancelled()
                pipe = ImportPipeline(proj_path)
                pipe.synthesize_structure(on_progress=_operational_log)
                pipe.write_character_profiles()
            try:
                db.ingest_project(self.root, resolved_id)
            except Exception:  # noqa: BLE001
                pass

        return fn, resolved_id

    def export_markdown(self, project_id: str) -> str:
        """Compile the manuscript, preferring the human-reviewed Final per chapter."""
        s = self._load(project_id)
        lines = [
            f"# {s.metadata.get('title', 'Untitled')}",
            "",
            f"*{s.metadata.get('genre', 'Fiction')}*",
            "",
            "---",
            "",
        ]
        for c in sorted(s.chapters.values(), key=lambda c: c.number):
            p = self._stage_paths(project_id, c.number)
            text = _read(p["final"]) or _read(p["revised"]) or _read(p["draft"])
            if text:
                lines.append(text)
                lines.append("\n\n---\n\n")
        return "\n".join(lines)

    def export_epub(self, project_id: str) -> tuple[str, bytes]:
        """Build an EPUB from Final chapter texts only."""
        from epub_exporter import build_epub  # noqa: E402

        s = self._load(project_id)
        chapters_data: list[tuple[int, str, str]] = []
        for c in sorted(s.chapters.values(), key=lambda c: c.number):
            text = self._get_final_text_for_export(project_id, c.number)
            if text:
                chapters_data.append((c.number, c.title or f"Chapter {c.number}", text))
        if not chapters_data:
            raise BadRequest("No chapters with Final text to export.")
        title = s.metadata.get("title", project_id)
        author = s.metadata.get("author", "Unknown")
        paragraph_format = getattr(s.style_profile, "paragraph_format", "block") or "block"
        data = build_epub(title, author, chapters_data, paragraph_format=paragraph_format)
        return f"{project_id}.epub", data

    # ----- Manual edit: chapters, characters, plots, story bible

    @staticmethod
    def _character_chapter_references(s: StoryState, character_id: str) -> list[dict]:
        refs: list[dict] = []
        for chapter_number, brief in sorted(s.chapter_briefs.items()):
            active_ids = set(brief.active_character_ids or [])
            mentioned_ids = set(brief.mentioned_character_ids or [])
            present = character_id in active_ids or character_id == (brief.pov_character_id or "")
            mentioned = character_id in mentioned_ids and not present
            if not present and not mentioned:
                continue
            chapter = s.get_chapter(chapter_number)
            refs.append({
                "chapter_number": chapter_number,
                "chapter_title": (chapter.title if chapter else "") or "",
                "present": present,
                "mentioned": mentioned,
            })
        return refs

    def _character_detail(self, project_id: str, char: Character) -> CharacterDetail:
        s = self._load(project_id)
        data = {k: v for k, v in char.to_dict().items() if k != "portrait_filename"}
        data["portrait_url"] = (
            self._character_portrait_url(project_id, char.id)
            if char.portrait_filename else None
        )
        data["chapter_references"] = self._character_chapter_references(s, char.id)
        return CharacterDetail(**data)

    def get_character(self, project_id: str, character_id: str) -> CharacterDetail:
        s = self._load(project_id)
        char = s.get_character(character_id)
        if char is None:
            raise CharacterNotFound(character_id)
        return self._character_detail(project_id, char)

    def update_character(self, project_id: str, character_id: str, updates: dict) -> CharacterDetail:
        s = self._load(project_id)
        if s.get_character(character_id) is None:
            raise CharacterNotFound(character_id)
        filtered = {
            k: v for k, v in updates.items()
            if v is not None and k not in ("portrait_filename", "portrait_url")
        }
        if "relationships" in filtered:
            filtered["relationships"] = _normalize_relationships_for_storage(filtered["relationships"])
        if filtered:
            s.update_character(character_id, filtered)
            s.save_state()
        return self.get_character(project_id, character_id)

    def upload_character_portrait(
        self, project_id: str, character_id: str, data: bytes,
    ) -> CharacterDetail:
        proj = self._project_dir(project_id)
        s = self._load(project_id)
        char = s.get_character(character_id)
        if char is None:
            raise CharacterNotFound(character_id)
        if not data:
            raise BadRequest("Empty image upload.")
        if len(data) > 20 * 1024 * 1024:
            raise BadRequest("Image must be 20 MB or smaller.")
        try:
            filename = portrait_assets.store_portrait_image(proj, character_id, data)
        except portrait_assets.PortraitAssetError as e:
            raise BadRequest(str(e)) from e
        old_file = char.portrait_filename
        s.update_character(character_id, {"portrait_filename": filename})
        s.save_state()
        if old_file and old_file != filename:
            portrait_assets.remove_portrait_image(proj, character_id, old_file)
        return self.get_character(project_id, character_id)

    def remove_character_portrait(self, project_id: str, character_id: str) -> CharacterDetail:
        proj = self._project_dir(project_id)
        s = self._load(project_id)
        char = s.get_character(character_id)
        if char is None:
            raise CharacterNotFound(character_id)
        old_file = char.portrait_filename
        if old_file:
            s.update_character(character_id, {"portrait_filename": ""})
            s.save_state()
            portrait_assets.remove_portrait_image(proj, character_id, old_file)
        return self.get_character(project_id, character_id)

    def resolve_character_portrait_path(
        self, project_id: str, character_id: str,
    ) -> tuple[Path, str]:
        proj = self._project_dir(project_id)
        s = self._load(project_id)
        char = s.get_character(character_id)
        if char is None or not char.portrait_filename:
            raise CharacterNotFound(character_id)
        try:
            path = portrait_assets.resolve_portrait_image_path(
                proj, character_id, char.portrait_filename,
            )
        except (portrait_assets.PortraitAssetError, FileNotFoundError) as e:
            raise CharacterNotFound(character_id) from e
        media_type = portrait_assets.media_type_for_filename(char.portrait_filename)
        return path, media_type

    def create_plot_thread(self, project_id: str, name: str, description: str = "",
                           thread_type: str = "main", priority: int = 3,
                           status: str = "active", subplots: list[str] | None = None) -> PlotThreadSummary:
        s = self._load(project_id)
        if not name.strip():
            raise BadRequest("Plot thread name is required.")
        n = len(s.plot_threads) + 1
        tid = f"plot_{n:03d}"
        while tid in s.plot_threads:
            n += 1
            tid = f"plot_{n:03d}"
        thread = PlotThread(
            id=tid, name=name.strip(), description=description.strip(),
            thread_type=thread_type, priority=priority, status=status,
            subplots=list(subplots or []),
        )
        s.add_plot_thread(thread)
        s.save_state()
        return self._plot_thread_summary(thread)

    def update_plot_thread(self, project_id: str, thread_id: str, updates: dict) -> PlotThreadSummary:
        s = self._load(project_id)
        thread = s.get_plot_thread(thread_id)
        if thread is None:
            raise PlotThreadNotFound(thread_id)
        filtered = {k: v for k, v in updates.items() if v is not None}
        if filtered:
            s.update_plot_thread(thread_id, filtered)
            s.save_state()
            thread = s.get_plot_thread(thread_id)
        return self._plot_thread_summary(thread)

    def _timeline_event_summary(self, event: TimelineEvent) -> TimelineEventSummary:
        return TimelineEventSummary(**event.to_dict())

    def list_timeline_events(self, project_id: str) -> list[TimelineEventSummary]:
        s = self._load(project_id)
        events = sorted(s.timeline, key=lambda e: (e.chapter, e.day or 0, e.id))
        return [self._timeline_event_summary(e) for e in events]

    def create_timeline_event(
        self,
        project_id: str,
        description: str,
        chapter: int,
        day: int | None = None,
        time: str | None = None,
        location: str = "",
        characters_present: list[str] | None = None,
        event_type: str = "scene",
        significance: str = "minor",
    ) -> TimelineEventSummary:
        s = self._load(project_id)
        if not description.strip():
            raise BadRequest("Event description is required.")
        if chapter < 1:
            raise BadRequest("Chapter must be at least 1.")
        if event_type not in _TIMELINE_EVENT_TYPES:
            raise BadRequest(f"event_type must be one of: {', '.join(sorted(_TIMELINE_EVENT_TYPES))}")
        if significance not in _TIMELINE_SIGNIFICANCE:
            raise BadRequest(f"significance must be one of: {', '.join(sorted(_TIMELINE_SIGNIFICANCE))}")
        char_ids = list(characters_present or [])
        for cid in char_ids:
            if s.get_character(cid) is None:
                raise CharacterNotFound(cid)
        n = len(s.timeline) + 1
        eid = f"event_{n:03d}"
        existing = {e.id for e in s.timeline}
        while eid in existing:
            n += 1
            eid = f"event_{n:03d}"
        event = TimelineEvent(
            id=eid,
            description=description.strip(),
            chapter=chapter,
            day=day,
            time=(time or "").strip() or None,
            location=location.strip(),
            characters_present=char_ids,
            event_type=event_type,
            significance=significance,
        )
        s.add_timeline_event(event)
        s.save_state()
        return self._timeline_event_summary(event)

    def update_timeline_event(self, project_id: str, event_id: str, updates: dict) -> TimelineEventSummary:
        s = self._load(project_id)
        event = s.get_timeline_event(event_id)
        if event is None:
            raise TimelineEventNotFound(event_id)
        filtered = {k: v for k, v in updates.items() if v is not None}
        if "description" in filtered and not str(filtered["description"]).strip():
            raise BadRequest("Event description is required.")
        if "chapter" in filtered and filtered["chapter"] < 1:
            raise BadRequest("Chapter must be at least 1.")
        if "event_type" in filtered and filtered["event_type"] not in _TIMELINE_EVENT_TYPES:
            raise BadRequest(f"event_type must be one of: {', '.join(sorted(_TIMELINE_EVENT_TYPES))}")
        if "significance" in filtered and filtered["significance"] not in _TIMELINE_SIGNIFICANCE:
            raise BadRequest(f"significance must be one of: {', '.join(sorted(_TIMELINE_SIGNIFICANCE))}")
        if "characters_present" in filtered:
            for cid in filtered["characters_present"]:
                if s.get_character(cid) is None:
                    raise CharacterNotFound(cid)
        if "time" in filtered:
            t = filtered["time"]
            filtered["time"] = (t or "").strip() or None
        if "location" in filtered:
            filtered["location"] = str(filtered["location"]).strip()
        if filtered:
            s.update_timeline_event(event_id, filtered)
            s.save_state()
            event = s.get_timeline_event(event_id)
        return self._timeline_event_summary(event)

    def delete_timeline_event(self, project_id: str, event_id: str) -> None:
        s = self._load(project_id)
        if s.get_timeline_event(event_id) is None:
            raise TimelineEventNotFound(event_id)
        s.delete_timeline_event(event_id)
        s.save_state()

    def delete_all_timeline_events(self, project_id: str) -> int:
        s = self._load(project_id)
        deleted = len(s.timeline)
        s.timeline = []
        if deleted:
            s.save_state()
        return deleted

    _TIMELINE_SOURCES = frozenset({"best", "draft", "revised", "final"})

    def _timeline_text_for_generation(
        self,
        project_id: str,
        number: int,
        source: str,
    ) -> tuple[str, str] | None:
        if source not in self._TIMELINE_SOURCES:
            raise BadRequest("source must be best, draft, revised, or final")
        self.ensure_chapter(project_id, number)
        order = ("final", "revised", "draft") if source == "best" else (source,)
        paths = self._stage_paths(project_id, number)
        for stage in order:
            text = _read(paths[stage])
            if not text or not text.strip():
                try:
                    text = db.get_artifact_text(project_id, number, stage)
                except Exception:  # noqa: BLE001
                    text = None
            if text and text.strip():
                return stage, text
        return None

    def generate_timeline_from_chapters(
        self,
        project_id: str,
        *,
        chapters: list[int] | None = None,
        source: str = "best",
        max_events_per_chapter: int = 5,
    ) -> TimelineGenerationResult:
        from timeline_extractor import extract_timeline_candidates  # noqa: WPS433

        s = self._load(project_id)
        if source not in self._TIMELINE_SOURCES:
            raise BadRequest("source must be best, draft, revised, or final")
        if max_events_per_chapter < 1 or max_events_per_chapter > 12:
            raise BadRequest("max_events_per_chapter must be between 1 and 12")
        chapter_numbers = sorted(chapters or list(s.chapters.keys()))
        if not chapter_numbers:
            raise BadRequest("No chapters available for timeline generation.")
        for number in chapter_numbers:
            if number not in s.chapters:
                raise ChapterNotFound(number)

        rows: list[tuple[int, str, str]] = []
        skipped: list[TimelineSkippedChapter] = []
        for number in chapter_numbers:
            found = self._timeline_text_for_generation(project_id, number, source)
            if found is None:
                skipped.append(TimelineSkippedChapter(
                    chapter=number,
                    reason=f"No {source if source != 'best' else 'final/revised/draft'} text found.",
                ))
                continue
            stage, text = found
            rows.append((number, stage, text))

        characters = {
            cid: character.all_names()
            for cid, character in s.characters.items()
        }
        pool_per_chapter = min(36, max_events_per_chapter * 3)
        candidates = [
            TimelineGeneratedEvent(**candidate.to_dict())
            for candidate in extract_timeline_candidates(
                rows,
                characters,
                max_events_per_chapter=pool_per_chapter,
            )
        ]
        return TimelineGenerationResult(
            source=source,
            recommended_per_chapter=max_events_per_chapter,
            chapters_scanned=[number for number, _, _ in rows],
            candidates=candidates,
            skipped_chapters=skipped,
        )

    def apply_generated_timeline_events(
        self,
        project_id: str,
        events: list[dict],
    ) -> list[TimelineEventSummary]:
        if not events:
            raise BadRequest("No generated timeline events selected.")
        created: list[TimelineEventSummary] = []
        for event in events:
            created.append(self.create_timeline_event(
                project_id,
                description=str(event.get("description", "")),
                chapter=int(event.get("chapter", 0)),
                day=event.get("day"),
                time=event.get("time"),
                location=str(event.get("location", "")),
                characters_present=list(event.get("characters_present") or []),
                event_type=str(event.get("event_type", "scene")),
                significance=str(event.get("significance", "minor")),
            ))
        return created

    def _research_spark_summary(self, row: db.ResearchSpark) -> ResearchSparkSummary:
        return ResearchSparkSummary(
            id=row.id,
            title=row.title,
            body=row.body,
            source_url=row.source_url,
            tags=db._spark_tags_decode(row.tags_json),
            kind=row.kind,
            attachment_ref=row.attachment_ref,
            link_character_id=row.link_character_id or None,
            link_chapter=row.link_chapter,
            link_plot_thread_id=row.link_plot_thread_id or None,
            link_bible_section=row.link_bible_section or None,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _validate_research_links(self, s: StoryState, data: dict) -> None:
        if "link_character_id" in data and data["link_character_id"]:
            if s.get_character(data["link_character_id"]) is None:
                raise CharacterNotFound(data["link_character_id"])
        if "link_plot_thread_id" in data and data["link_plot_thread_id"]:
            if s.get_plot_thread(data["link_plot_thread_id"]) is None:
                raise PlotThreadNotFound(data["link_plot_thread_id"])
        if "link_chapter" in data and data["link_chapter"] is not None:
            if data["link_chapter"] < 1:
                raise BadRequest("link_chapter must be at least 1.")

    def _filter_research_sparks(
        self,
        sparks: list[ResearchSparkSummary],
        *,
        q: str | None = None,
        tag: str | None = None,
        kind: str | None = None,
    ) -> list[ResearchSparkSummary]:
        needle = (q or "").strip().lower()
        tag_needle = (tag or "").strip().lower()
        kind_filter = (kind or "").strip().lower()
        out: list[ResearchSparkSummary] = []
        for spark in sparks:
            if kind_filter and spark.kind.lower() != kind_filter:
                continue
            if tag_needle and not any(t.lower() == tag_needle for t in spark.tags):
                continue
            if needle:
                hay = " ".join([
                    spark.title, spark.body, spark.source_url,
                    spark.attachment_ref, " ".join(spark.tags),
                ]).lower()
                if needle not in hay:
                    continue
            out.append(spark)
        return out

    def list_research_sparks(
        self,
        project_id: str,
        *,
        q: str | None = None,
        tag: str | None = None,
        kind: str | None = None,
    ) -> list[ResearchSparkSummary]:
        self._project_dir(project_id)
        rows = db.research_sparks_list(project_id)
        sparks = [self._research_spark_summary(r) for r in rows]
        return self._filter_research_sparks(sparks, q=q, tag=tag, kind=kind)

    def create_research_spark(
        self,
        project_id: str,
        title: str,
        body: str = "",
        source_url: str = "",
        tags: list[str] | None = None,
        kind: str = "note",
        attachment_ref: str = "",
        link_character_id: str | None = None,
        link_chapter: int | None = None,
        link_plot_thread_id: str | None = None,
        link_bible_section: str | None = None,
    ) -> ResearchSparkSummary:
        s = self._load(project_id)
        if not title.strip():
            raise BadRequest("Title is required.")
        if kind not in _RESEARCH_KINDS:
            raise BadRequest(f"kind must be one of: {', '.join(sorted(_RESEARCH_KINDS))}")
        link_data = {
            "link_character_id": link_character_id,
            "link_plot_thread_id": link_plot_thread_id,
            "link_chapter": link_chapter,
        }
        self._validate_research_links(s, link_data)
        row = db.research_spark_create(
            project_id,
            title=title.strip(),
            body=body.strip(),
            source_url=source_url.strip(),
            tags=tags or [],
            kind=kind,
            attachment_ref=attachment_ref.strip(),
            link_character_id=(link_character_id or "").strip(),
            link_chapter=link_chapter,
            link_plot_thread_id=(link_plot_thread_id or "").strip(),
            link_bible_section=(link_bible_section or "").strip(),
        )
        return self._research_spark_summary(row)

    def update_research_spark(self, project_id: str, spark_id: str, updates: dict) -> ResearchSparkSummary:
        self._project_dir(project_id)
        if db.research_spark_get(project_id, spark_id) is None:
            raise ResearchSparkNotFound(spark_id)
        filtered = {k: v for k, v in updates.items() if v is not None}
        if "title" in filtered and not str(filtered["title"]).strip():
            raise BadRequest("Title is required.")
        if "kind" in filtered and filtered["kind"] not in _RESEARCH_KINDS:
            raise BadRequest(f"kind must be one of: {', '.join(sorted(_RESEARCH_KINDS))}")
        if "title" in filtered:
            filtered["title"] = str(filtered["title"]).strip()
        for key in ("body", "source_url", "attachment_ref", "link_bible_section"):
            if key in filtered:
                filtered[key] = str(filtered[key]).strip()
        for key in ("link_character_id", "link_plot_thread_id"):
            if key in filtered:
                val = filtered[key]
                filtered[key] = (val or "").strip() if val is not None else ""
        s = self._load(project_id)
        self._validate_research_links(s, filtered)
        row = db.research_spark_update(project_id, spark_id, **filtered)
        if row is None:
            raise ResearchSparkNotFound(spark_id)
        return self._research_spark_summary(row)

    def delete_research_spark(self, project_id: str, spark_id: str) -> None:
        self._project_dir(project_id)
        if not db.research_spark_delete(project_id, spark_id):
            raise ResearchSparkNotFound(spark_id)

    def _map_image_url(self, project_id: str, map_id: str) -> str | None:
        row = db.project_map_get(project_id, map_id)
        if row is None or not row.image_filename:
            return None
        return f"/api/projects/{project_id}/maps/{map_id}/image"

    def _map_pin_summary(self, row: db.MapPin) -> MapPinSummary:
        return MapPinSummary(
            id=row.id,
            map_id=row.map_id,
            label=row.label,
            x=row.x,
            y=row.y,
            lore_section=row.lore_section,
            lore_label=row.lore_label,
            notes=row.notes,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _map_summary(self, row: db.ProjectMap, *, pin_count: int = 0) -> ProjectMapSummary:
        image_url = (
            self._map_image_url(row.project_id, row.id)
            if row.image_filename else None
        )
        return ProjectMapSummary(
            id=row.id,
            name=row.name,
            image_url=image_url,
            pin_count=pin_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def list_project_maps(self, project_id: str) -> list[ProjectMapSummary]:
        self._project_dir(project_id)
        rows = db.project_maps_list(project_id)
        out: list[ProjectMapSummary] = []
        for row in rows:
            pin_count = len(db.map_pins_list(project_id, row.id))
            out.append(self._map_summary(row, pin_count=pin_count))
        return out

    def get_project_map(self, project_id: str, map_id: str) -> ProjectMapDetail:
        proj = self._project_dir(project_id)
        row = db.project_map_get(project_id, map_id)
        if row is None:
            raise ProjectMapNotFound(map_id)
        pins = [self._map_pin_summary(p) for p in db.map_pins_list(project_id, map_id)]
        image_url = self._map_image_url(project_id, map_id) if row.image_filename else None
        return ProjectMapDetail(
            id=row.id,
            name=row.name,
            image_url=image_url,
            created_at=row.created_at,
            updated_at=row.updated_at,
            pins=pins,
        )

    def create_project_map(self, project_id: str, name: str) -> ProjectMapSummary:
        self._project_dir(project_id)
        cleaned = name.strip() or "Main Map"
        row = db.project_map_create(project_id, name=cleaned)
        return self._map_summary(row, pin_count=0)

    def update_project_map(self, project_id: str, map_id: str, updates: dict) -> ProjectMapSummary:
        self._project_dir(project_id)
        filtered = {k: v for k, v in updates.items() if v is not None}
        if "name" in filtered:
            cleaned = str(filtered["name"]).strip()
            if not cleaned:
                raise BadRequest("Map name is required.")
            filtered["name"] = cleaned
        row = db.project_map_update(project_id, map_id, **filtered)
        if row is None:
            raise ProjectMapNotFound(map_id)
        pin_count = len(db.map_pins_list(project_id, map_id))
        return self._map_summary(row, pin_count=pin_count)

    def delete_project_map(self, project_id: str, map_id: str) -> None:
        proj = self._project_dir(project_id)
        row = db.project_map_get(project_id, map_id)
        if row is None:
            raise ProjectMapNotFound(map_id)
        old_file = row.image_filename
        if not db.project_map_delete(project_id, map_id):
            raise ProjectMapNotFound(map_id)
        if old_file:
            map_assets.remove_map_image(proj, map_id, old_file)
        try:
            map_assets.remove_map_assets(proj, map_id)
        except map_assets.MapAssetError:
            pass

    def upload_map_image(self, project_id: str, map_id: str, data: bytes) -> ProjectMapSummary:
        proj = self._project_dir(project_id)
        row = db.project_map_get(project_id, map_id)
        if row is None:
            raise ProjectMapNotFound(map_id)
        if not data:
            raise BadRequest("Empty image upload.")
        if len(data) > 20 * 1024 * 1024:
            raise BadRequest("Image must be 20 MB or smaller.")
        try:
            filename = map_assets.store_map_image(proj, map_id, data)
        except map_assets.MapAssetError as e:
            raise BadRequest(str(e)) from e
        old_file = row.image_filename
        row = db.project_map_set_image(project_id, map_id, filename)
        if row is None:
            raise ProjectMapNotFound(map_id)
        if old_file and old_file != filename:
            map_assets.remove_map_image(proj, map_id, old_file)
        pin_count = len(db.map_pins_list(project_id, map_id))
        return self._map_summary(row, pin_count=pin_count)

    def resolve_map_image_path(self, project_id: str, map_id: str) -> tuple[Path, str]:
        proj = self._project_dir(project_id)
        row = db.project_map_get(project_id, map_id)
        if row is None or not row.image_filename:
            raise ProjectMapNotFound(map_id)
        try:
            path = map_assets.resolve_map_image_path(proj, map_id, row.image_filename)
        except (map_assets.MapAssetError, FileNotFoundError) as e:
            raise ProjectMapNotFound(map_id) from e
        media_type = map_assets.media_type_for_filename(row.image_filename)
        return path, media_type

    def list_map_pins(self, project_id: str, map_id: str) -> list[MapPinSummary]:
        self._project_dir(project_id)
        if db.project_map_get(project_id, map_id) is None:
            raise ProjectMapNotFound(map_id)
        return [self._map_pin_summary(p) for p in db.map_pins_list(project_id, map_id)]

    def create_map_pin(
        self,
        project_id: str,
        map_id: str,
        *,
        label: str,
        x: float,
        y: float,
        lore_section: str = "",
        lore_label: str = "",
        notes: str = "",
    ) -> MapPinSummary:
        self._project_dir(project_id)
        if db.project_map_get(project_id, map_id) is None:
            raise ProjectMapNotFound(map_id)
        if not label.strip():
            raise BadRequest("Pin label is required.")
        row = db.map_pin_create(
            project_id,
            map_id,
            label=label.strip(),
            x=x,
            y=y,
            lore_section=lore_section.strip(),
            lore_label=lore_label.strip(),
            notes=notes.strip(),
        )
        return self._map_pin_summary(row)

    def update_map_pin(self, project_id: str, map_id: str, pin_id: str, updates: dict) -> MapPinSummary:
        self._project_dir(project_id)
        if db.project_map_get(project_id, map_id) is None:
            raise ProjectMapNotFound(map_id)
        filtered = {k: v for k, v in updates.items() if v is not None}
        if "label" in filtered:
            cleaned = str(filtered["label"]).strip()
            if not cleaned:
                raise BadRequest("Pin label is required.")
            filtered["label"] = cleaned
        for key in ("lore_section", "lore_label", "notes"):
            if key in filtered:
                filtered[key] = str(filtered[key]).strip()
        row = db.map_pin_update(project_id, map_id, pin_id, **filtered)
        if row is None:
            raise MapPinNotFound(pin_id)
        return self._map_pin_summary(row)

    def delete_map_pin(self, project_id: str, map_id: str, pin_id: str) -> None:
        self._project_dir(project_id)
        if db.project_map_get(project_id, map_id) is None:
            raise ProjectMapNotFound(map_id)
        if not db.map_pin_delete(project_id, map_id, pin_id):
            raise MapPinNotFound(pin_id)

    def get_story_bible(self, project_id: str) -> dict:
        return self._load(project_id).story_bible

    def update_story_bible_section(self, project_id: str, section: str, content) -> dict:
        s = self._load(project_id)
        s.update_story_bible(section, content)
        s.save_state()
        return s.story_bible

    def create_chapter(self, project_id: str, number: int, title: str = "",
                       text: str = "", extract: bool = False) -> ChapterPasteResult | tuple[Callable, str, int]:
        """Create chapter. Returns sync result or (job_fn, project_id, number) if extract."""
        self._project_dir(project_id)
        if number < 1:
            raise BadRequest("Chapter number must be at least 1.")
        s = self._load(project_id)
        if number in s.chapters and text.strip():
            raise BadRequest(f"Chapter {number} already exists — open it to edit or pick another number.")
        if not text.strip():
            s.create_chapter(number, title.strip())
            if title.strip():
                s.update_chapter(number, {"title": title.strip()})
            s.save_state()
            ch = s.get_chapter(number)
            return ChapterPasteResult(number=number, word_count=ch.word_count if ch else 0)

        if extract:
            proj_path = str(self._project_dir(project_id))
            def fn() -> None:
                from import_pipeline import ImportPipeline  # noqa: E402
                ImportPipeline(proj_path).import_chapter_text(
                    number, text, title=title, extract=True,
                    on_progress=_operational_log,
                )
                try:
                    db.ingest_project(self.root, project_id)
                except Exception:  # noqa: BLE001
                    pass
            return fn, project_id, number

        from import_pipeline import ImportPipeline  # noqa: E402
        wc, changes = ImportPipeline(str(self._project_dir(project_id))).import_chapter_text(
            number, text, title=title, extract=False,
        )
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return ChapterPasteResult(number=number, word_count=wc, changes=changes)

    def update_chapter(self, project_id: str, number: int, updates: dict) -> ChapterSummary:
        s = self._load(project_id)
        c = s.chapters.get(number)
        if c is None:
            raise ChapterNotFound(number)
        filtered = {k: v for k, v in updates.items() if v is not None}
        if "title" in filtered:
            filtered["title_source"] = "manual"
        if filtered:
            s.update_chapter(number, filtered)
            s.save_state()
            c = s.chapters[number]
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass
        return self._chapter_summary(project_id, c)

    def save_draft(self, project_id: str, number: int, text: str) -> int:
        s = self._load(project_id)
        if number not in s.chapters:
            s.create_chapter(number)
            s.save_state()
        draft_path = self._stage_paths(project_id, number)["draft"]
        _atomic_write(draft_path, text)
        wc = len(text.split())
        s.update_chapter(number, {"word_count": wc, "status": "drafted"})
        s.save_state()
        try:
            db.upsert_artifact(project_id, number, "draft", text)
        except Exception:  # noqa: BLE001
            pass
        return wc

    def save_revised(self, project_id: str, number: int, text: str) -> int:
        s = self._load(project_id)
        if number not in s.chapters:
            raise ChapterNotFound(number)
        _atomic_write(self._stage_paths(project_id, number)["revised"], text)
        wc = len(text.split())
        status = s.chapters[number].status
        if status in ("validated", "complete"):
            status = "edited"
        elif status not in ("editing", "edited"):
            status = "edited"
        s.update_chapter(number, {"word_count": wc, "status": status})
        s.save_state()
        try:
            db.upsert_artifact(project_id, number, "revised", text)
        except Exception:  # noqa: BLE001
            pass
        return wc

    @staticmethod
    def _chapter_files(proj: Path, number: int) -> list[Path]:
        nnn = f"{number:03d}"
        out = proj / "outputs"
        if not out.exists():
            return []
        return sorted(path for path in out.rglob(f"*chapter_{nnn}*") if path.is_file())

    @staticmethod
    def _chapter_file_rename_steps(proj: Path, from_num: int, to_num: int) -> list[tuple[Path, Path]]:
        if from_num == to_num:
            return []
        return [
            (
                path,
                path.parent / path.name.replace(f"chapter_{from_num:03d}", f"chapter_{to_num:03d}"),
            )
            for path in ProjectService._chapter_files(proj, from_num)
        ]

    @staticmethod
    def _preflight_chapter_file_renames(
        proj: Path,
        steps: list[tuple[Path, Path]],
        copy_steps: list[tuple[Path, Path]] | None = None,
    ) -> None:
        """Simulate all file moves before touching disk so collisions cancel cleanly."""
        out = proj / "outputs"
        existing = set(out.rglob("*")) if out.exists() else set()
        existing = {path for path in existing if path.is_file()}
        for src, dest in steps:
            if src not in existing:
                raise BadRequest(
                    "Chapter file collision check failed; no files were moved. "
                    f"Expected source is missing: {src}"
                )
            if dest in existing and dest != src:
                raise BadRequest(
                    "Chapter file collision detected; no files were moved. "
                    f"Source: {src} Destination already exists: {dest}"
                )
            existing.remove(src)
            existing.add(dest)
        for src, dest in copy_steps or []:
            if src not in existing:
                raise BadRequest(
                    "Chapter file collision check failed; no files were copied. "
                    f"Expected source is missing: {src}"
                )
            if dest in existing and dest != src:
                raise BadRequest(
                    "Chapter file collision detected; no files were copied. "
                    f"Source: {src} Destination already exists: {dest}"
                )

    @staticmethod
    def _apply_chapter_file_renames(steps: list[tuple[Path, Path]]) -> None:
        for src, dest in steps:
            dest.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dest)

    def reassign_chapter(self, project_id: str, from_number: int, to_number: int) -> dict:
        if from_number < 1 or to_number < 1:
            raise BadRequest("Chapter numbers must be at least 1.")
        s = self._load(project_id)
        if from_number not in s.chapters:
            raise ChapterNotFound(from_number)
        if from_number == to_number:
            c = s.chapters[from_number]
            return {
                "action": "unchanged",
                "from_number": from_number,
                "to_number": to_number,
                "chapter": self._chapter_summary(project_id, c),
            }
        proj = self._project_dir(project_id)
        swap = to_number in s.chapters
        if swap:
            sentinel = max(s.chapters.keys()) + 10000
            from_to_sentinel = self._chapter_file_rename_steps(proj, from_number, sentinel)
            to_to_from = self._chapter_file_rename_steps(proj, to_number, from_number)
            sentinel_to_to = [
                (
                    dest,
                    dest.parent / dest.name.replace(f"chapter_{sentinel:03d}", f"chapter_{to_number:03d}"),
                )
                for _, dest in from_to_sentinel
            ]
            steps = from_to_sentinel + to_to_from + sentinel_to_to
        else:
            steps = self._chapter_file_rename_steps(proj, from_number, to_number)
        self._preflight_chapter_file_renames(proj, steps)
        self._apply_chapter_file_renames(steps)
        action = s.reassign_chapter(from_number, to_number)
        s.save_state()
        try:
            db.chapter_reassign(project_id, from_number, to_number, swap=swap)
        except Exception:  # noqa: BLE001
            pass
        c = s.chapters[to_number]
        other = s.chapters.get(from_number) if swap else None
        result = {
            "action": action,
            "from_number": from_number,
            "to_number": to_number,
            "chapter": self._chapter_summary(project_id, c),
        }
        if other is not None:
            result["swapped_with"] = self._chapter_summary(project_id, other)
        return result

    def insert_chapter_at(self, project_id: str, number: int, title: str = "") -> dict:
        """Insert a blank chapter, shifting existing chapters at/after the slot up by one."""
        if number < 1:
            raise BadRequest("Chapter number must be at least 1.")
        s = self._load(project_id)
        existing = sorted(s.chapters)
        if existing and number > max(existing) + 1:
            raise BadRequest(f"Chapter {number} would leave a gap. Insert at {max(existing) + 1} or earlier.")

        proj = self._project_dir(project_id)
        shifted = [n for n in existing if n >= number]
        steps: list[tuple[Path, Path]] = []
        for old in sorted(shifted, reverse=True):
            steps.extend(self._chapter_file_rename_steps(proj, old, old + 1))
        self._preflight_chapter_file_renames(proj, steps)
        self._apply_chapter_file_renames(steps)
        for old in sorted(shifted, reverse=True):
            s.reassign_chapter(old, old + 1)
        s.create_chapter(number, title.strip())
        if title.strip():
            s.update_chapter(number, {"title": title.strip()})
        s.save_state()
        for old in sorted(shifted, reverse=True):
            try:
                db.chapter_reassign(project_id, old, old + 1, swap=False)
            except Exception:  # noqa: BLE001
                pass
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return {
            "action": "inserted",
            "inserted_number": number,
            "mapping": [
                {"from_number": old, "to_number": old + 1}
                for old in sorted(shifted)
            ],
            "chapters": self.list_chapters(project_id),
        }

    def renumber_chapters_sequential(self, project_id: str) -> dict:
        """Compact chapter numbers to 1..N while preserving current numeric order."""
        s = self._load(project_id)
        existing = sorted(s.chapters)
        mapping = [
            (old, new)
            for new, old in enumerate(existing, start=1)
            if old != new
        ]
        if not mapping:
            return {
                "action": "unchanged",
                "inserted_number": None,
                "mapping": [],
                "chapters": self.list_chapters(project_id),
            }

        proj = self._project_dir(project_id)
        steps: list[tuple[Path, Path]] = []
        for old, new in mapping:
            steps.extend(self._chapter_file_rename_steps(proj, old, new))
        self._preflight_chapter_file_renames(proj, steps)
        self._apply_chapter_file_renames(steps)
        for old, new in mapping:
            s.reassign_chapter(old, new)
        s.save_state()
        for old, new in mapping:
            try:
                db.chapter_reassign(project_id, old, new, swap=False)
            except Exception:  # noqa: BLE001
                pass
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return {
            "action": "renumbered",
            "inserted_number": None,
            "mapping": [
                {"from_number": old, "to_number": new}
                for old, new in mapping
            ],
            "chapters": self.list_chapters(project_id),
        }

    def duplicate_chapter(self, project_id: str, number: int, title: str = "") -> dict:
        """Duplicate a chapter into the next slot, shifting later chapters up."""
        s = self._load(project_id)
        source = s.chapters.get(number)
        if source is None:
            raise ChapterNotFound(number)
        proj = self._project_dir(project_id)
        new_number = number + 1
        shifted = [n for n in sorted(s.chapters) if n >= new_number]
        rename_steps: list[tuple[Path, Path]] = []
        for old in sorted(shifted, reverse=True):
            rename_steps.extend(self._chapter_file_rename_steps(proj, old, old + 1))
        copy_steps = [
            (
                path,
                path.parent / path.name.replace(f"chapter_{number:03d}", f"chapter_{new_number:03d}"),
            )
            for path in self._chapter_files(proj, number)
        ]
        self._preflight_chapter_file_renames(proj, rename_steps, copy_steps)
        self._apply_chapter_file_renames(rename_steps)
        for src, dest in copy_steps:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        for old in sorted(shifted, reverse=True):
            s.reassign_chapter(old, old + 1)
        clone = ChapterState.from_dict(source.to_dict())
        clone.number = new_number
        clone.title = title.strip() or f"{source.title or f'Chapter {number}'} (copy)"
        s.chapters[new_number] = clone
        brief = s.chapter_briefs.get(number)
        if brief is not None:
            brief_clone = ChapterBrief.from_dict(brief.to_dict())
            brief_clone.chapter_number = new_number
            s.chapter_briefs[new_number] = brief_clone
        s.save_state()
        for old in sorted(shifted, reverse=True):
            try:
                db.chapter_reassign(project_id, old, old + 1, swap=False)
            except Exception:  # noqa: BLE001
                pass
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return {
            "action": "duplicated",
            "inserted_number": new_number,
            "mapping": [
                {"from_number": old, "to_number": old + 1}
                for old in sorted(shifted)
            ],
            "chapters": self.list_chapters(project_id),
        }

    def merge_chapter(self, project_id: str, keep_number: int, source_number: int) -> dict:
        """Merge the next chapter into the current chapter without compacting numbering."""
        if source_number != keep_number + 1:
            raise BadRequest("Merge currently supports only the next chapter into this chapter.")
        s = self._load(project_id)
        keep = s.chapters.get(keep_number)
        source = s.chapters.get(source_number)
        if keep is None:
            raise ChapterNotFound(keep_number)
        if source is None:
            raise ChapterNotFound(source_number)

        proj = self._project_dir(project_id)
        source_stage_paths = set(self._stage_paths(project_id, source_number).values())
        archive_steps = [
            (
                path,
                path.with_name(
                    path.name.replace(
                        f"chapter_{source_number:03d}",
                        f"chapter_{keep_number:03d}_merged_from_{source_number:03d}",
                    ),
                ),
            )
            for path in self._chapter_files(proj, source_number)
            if path not in source_stage_paths
        ]
        self._preflight_chapter_file_renames(proj, archive_steps)

        from chapter_brief_utils import migrate_legacy_brief_beats_to_chapter_beats  # noqa: WPS433

        keep_brief = s.chapter_briefs.get(keep_number)
        source_brief = s.chapter_briefs.get(source_number)
        if keep_brief is not None:
            migrate_legacy_brief_beats_to_chapter_beats(s, keep_number, keep_brief)
        if source_brief is not None:
            migrate_legacy_brief_beats_to_chapter_beats(s, source_number, source_brief)
        keep_beats = list(s.get_chapter_beats(keep_number))
        source_beats = list(s.get_chapter_beats(source_number))
        merged_brief = self._merge_chapter_briefs(
            keep_number,
            keep_brief,
            source_brief,
            source_number=source_number,
        )

        for stage, keep_path in self._stage_paths(project_id, keep_number).items():
            source_path = self._stage_paths(project_id, source_number)[stage]
            keep_text = _read(keep_path) or ""
            source_text = _read(source_path) or ""
            if not source_text.strip():
                continue
            merged = source_text if not keep_text.strip() else f"{keep_text.rstrip()}\n\n---\n\n{source_text.lstrip()}"
            _atomic_write(keep_path, merged)
            try:
                db.upsert_artifact(project_id, keep_number, stage, merged)
            except Exception:  # noqa: BLE001
                pass

        self._apply_chapter_file_renames(archive_steps)
        for path in self._chapter_files(proj, source_number):
            path.unlink()
        s.chapter_briefs.pop(source_number, None)
        s._remap_chapter_number(source_number, keep_number)
        merged_beats = keep_beats + source_beats
        if merged_beats:
            for index, beat in enumerate(merged_beats):
                beat.sort_order = index
            s.set_chapter_beats(keep_number, merged_beats)
        s.chapters.pop(source_number, None)
        self._merge_chapter_state(keep, source, source_number=source_number)
        keep.title = f"{keep.title or f'Chapter {keep_number}'} / {source.title or f'Chapter {source_number}'}"
        best_text = (
            _read(self._stage_paths(project_id, keep_number)["final"])
            or _read(self._stage_paths(project_id, keep_number)["revised"])
            or _read(self._stage_paths(project_id, keep_number)["draft"])
            or ""
        )
        keep.word_count = len(best_text.split())
        keep.last_modified = datetime.now(timezone.utc).isoformat()
        if merged_brief is not None:
            s.chapter_briefs[keep_number] = merged_brief
        s.save_state()
        removed_snapshots = 0
        try:
            removed_snapshots = db.chapter_merge_cleanup(project_id, source_number, keep_number)
        except Exception:  # noqa: BLE001
            pass
        return {
            "action": "merged",
            "inserted_number": keep_number,
            "mapping": [{"from_number": source_number, "to_number": keep_number}],
            "chapters": self.list_chapters(project_id),
            "removed_snapshot_count": removed_snapshots,
        }

    @staticmethod
    def _merge_chapter_state(keep: ChapterState, source: ChapterState, *, source_number: int) -> None:
        def merged_list(a: list, b: list) -> list:
            out: list = []
            seen: set[str] = set()
            for item in [*a, *b]:
                key = json.dumps(item, sort_keys=True, default=str)
                if key in seen:
                    continue
                seen.add(key)
                out.append(item)
            return out

        def merged_dict(a: dict, b: dict) -> dict:
            out = dict(a)
            for key, value in b.items():
                if key not in out or out[key] == value:
                    out[key] = value
                    continue
                merged_key = f"{key} (merged from chapter {source_number})"
                suffix = 2
                while merged_key in out:
                    merged_key = f"{key} (merged from chapter {source_number} #{suffix})"
                    suffix += 1
                out[merged_key] = value
            return out

        keep.target_word_count = max(keep.target_word_count, 0) + max(source.target_word_count, 0)
        keep.scenes = merged_list(keep.scenes, source.scenes)
        keep.plot_advances = merged_list(keep.plot_advances, source.plot_advances)
        keep.character_development = merged_dict(keep.character_development, source.character_development)
        keep.emotional_beats = merged_list(keep.emotional_beats, source.emotional_beats)
        keep.new_information = merged_list(keep.new_information, source.new_information)
        keep.foreshadowing_planted = merged_list(keep.foreshadowing_planted, source.foreshadowing_planted)
        keep.foreshadowing_resolved = merged_list(keep.foreshadowing_resolved, source.foreshadowing_resolved)
        keep.hooks_start = merged_list(keep.hooks_start, source.hooks_start)
        keep.hooks_end = merged_list(keep.hooks_end, source.hooks_end)
        keep.continuity_checks = merged_dict(keep.continuity_checks, source.continuity_checks)
        keep.quality_scores = merged_dict(keep.quality_scores, source.quality_scores)
        keep.continuity_checks = merged_dict(
            keep.continuity_checks,
            {
                f"merged_from_chapter_{source_number}": {
                    "title": source.title,
                    "status": source.status,
                    "pov_character": source.pov_character,
                    "location": source.location,
                    "time": source.time,
                    "target_word_count": source.target_word_count,
                    "word_count": source.word_count,
                },
            },
        )

    @staticmethod
    def _merge_chapter_briefs(
        keep_number: int,
        keep: ChapterBrief | None,
        source: ChapterBrief | None,
        *,
        source_number: int,
    ) -> ChapterBrief | None:
        if keep is None and source is None:
            return None

        def merged_list(a: list[str], b: list[str]) -> list[str]:
            out: list[str] = []
            seen: set[str] = set()
            for item in [*a, *b]:
                text = str(item).strip()
                if not text:
                    continue
                key = text.casefold()
                if key in seen:
                    continue
                seen.add(key)
                out.append(text)
            return out

        def merged_notes(a: str, b: str) -> str:
            left = (a or "").strip()
            right = (b or "").strip()
            if left and right and left != right:
                return f"{left}\n\nMerged from chapter {source_number}:\n{right}"
            return left or right

        base = keep if keep is not None else ChapterBrief(chapter_number=keep_number)
        extra = source if source is not None else ChapterBrief(chapter_number=source_number)
        return ChapterBrief(
            chapter_number=keep_number,
            pov_character_id=base.pov_character_id,
            pov_mode=base.pov_mode,
            tone=base.tone or extra.tone,
            tense=base.tense or extra.tense,
            prose_style=base.prose_style or extra.prose_style,
            vocabulary_level=base.vocabulary_level or extra.vocabulary_level,
            style_notes=merged_notes(base.style_notes, extra.style_notes),
            target_word_count=base.target_word_count or extra.target_word_count,
            active_character_ids=merged_list(base.active_character_ids, extra.active_character_ids),
            active_node_ids=merged_list(base.active_node_ids, extra.active_node_ids),
            continuity_notes=merged_notes(base.continuity_notes, extra.continuity_notes),
            ending_hook=base.ending_hook,
        )

    def paste_chapter(self, project_id: str, number: int, text: str,
                      title: str = "", extract: bool = False) -> ChapterPasteResult | tuple[Callable, str, int]:
        s = self._load(project_id)
        if number not in s.chapters:
            s.create_chapter(number, title.strip())
            s.save_state()
        if extract:
            proj_path = str(self._project_dir(project_id))
            def fn() -> None:
                from import_pipeline import ImportPipeline  # noqa: E402
                ImportPipeline(proj_path).import_chapter_text(
                    number, text, title=title, extract=True,
                    on_progress=_operational_log,
                )
                try:
                    db.ingest_project(self.root, project_id)
                except Exception:  # noqa: BLE001
                    pass
            return fn, project_id, number
        from import_pipeline import ImportPipeline  # noqa: E402
        wc, changes = ImportPipeline(str(self._project_dir(project_id))).import_chapter_text(
            number, text, title=title, extract=False,
        )
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return ChapterPasteResult(number=number, word_count=wc, changes=changes)

    def make_extract_job(self, project_id: str, number: int) -> Callable[[], None]:
        self.ensure_chapter(project_id, number)
        proj_path = str(self._project_dir(project_id))
        def fn() -> None:
            from import_pipeline import ImportPipeline  # noqa: E402
            ImportPipeline(proj_path).extract_chapter_from_draft(
                number, on_progress=_operational_log,
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass
        return fn

    def _chapter_mine_preview_path(self, project_id: str, chapter_number: int, kind: str) -> Path:
        return (
            self._project_dir(project_id)
            / "outputs"
            / "feedback"
            / f"chapter_{chapter_number:03d}_mine_{kind}_preview.json"
        )

    def list_chapter_mine_previews(
        self,
        project_id: str,
        *,
        kind: str | None = None,
    ) -> list[ChapterMinePreviewSummary]:
        feedback = self._project_dir(project_id) / "outputs" / "feedback"
        if not feedback.is_dir():
            return []
        summaries: list[ChapterMinePreviewSummary] = []
        for path in sorted(feedback.glob("chapter_*_mine_*_preview.json")):
            parts = path.stem.split("_")
            # chapter_NNN_mine_KIND_preview
            if len(parts) < 5:
                continue
            preview_kind = parts[3]
            if kind and preview_kind != kind:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                summaries.append(
                    ChapterMinePreviewSummary(
                        chapter_number=int(data.get("chapter_number", int(parts[1]))),
                        kind=str(data.get("kind", preview_kind)),
                        change_count=len(data.get("changes") or []),
                    ),
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        return summaries

    def get_chapter_mine_preview(
        self,
        project_id: str,
        chapter_number: int,
        kind: str,
    ) -> ChapterMinePreview | None:
        self.ensure_chapter(project_id, chapter_number)
        if kind not in ("plots", "characters", "bible"):
            raise BadRequest("kind must be plots, characters, or bible")
        path = self._chapter_mine_preview_path(project_id, chapter_number, kind)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        ui_summary = data.get("ui_summary")
        if not ui_summary and data.get("parsed") is not None:
            from mine_preview_ui import build_mine_preview_ui  # noqa: WPS433

            ui_summary = build_mine_preview_ui(
                kind,
                data.get("parsed") or {},
                list(data.get("changes") or []),
            )
        return ChapterMinePreview(
            chapter_number=int(data["chapter_number"]),
            kind=str(data["kind"]),
            stage_source=str(data.get("stage_source", "draft")),
            source=str(data.get("source", f"mine_{kind}")),
            changes=list(data.get("changes") or []),
            report_path=str(data.get("report_path", "")),
            ui_summary=ui_summary,
        )

    def discard_chapter_mine_preview(
        self,
        project_id: str,
        chapter_number: int,
        kind: str,
    ) -> None:
        self.ensure_chapter(project_id, chapter_number)
        if kind not in ("plots", "characters", "bible"):
            raise BadRequest("kind must be plots, characters, or bible")
        path = self._chapter_mine_preview_path(project_id, chapter_number, kind)
        if path.exists():
            path.unlink()

    def apply_chapter_mine_preview(
        self,
        project_id: str,
        chapter_number: int,
        kind: str,
    ) -> ApplyChapterMinePreviewResult:
        from chapter_miner import apply_mine_preview_to_state  # noqa: WPS433
        from state_manager import project_state_lock  # noqa: WPS433

        self.ensure_chapter(project_id, chapter_number)
        if kind not in ("plots", "characters", "bible"):
            raise BadRequest("kind must be plots, characters, or bible")
        path = self._chapter_mine_preview_path(project_id, chapter_number, kind)
        if not path.exists():
            raise BadRequest("No mine preview for this chapter")
        data = json.loads(path.read_text(encoding="utf-8"))
        parsed = data.get("parsed")
        if not isinstance(parsed, dict):
            raise BadRequest("Mine preview is invalid")

        proj_path = str(self._project_dir(project_id))
        lock = project_state_lock(proj_path)
        with lock:
            state = StoryState(proj_path)
            changes = apply_mine_preview_to_state(state, chapter_number, kind, parsed)
            if kind == "characters":
                try:
                    from import_pipeline import ImportPipeline  # noqa: WPS433
                    ImportPipeline(proj_path).write_character_profiles()
                except Exception:  # noqa: BLE001
                    pass
            state.save_state()
            path.unlink(missing_ok=True)

        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass

        return ApplyChapterMinePreviewResult(
            chapter_number=chapter_number,
            kind=kind,
            changes=changes,
        )

    def make_mine_job(
        self,
        project_id: str,
        number: int,
        kind: str,
        *,
        source: str = "draft",
    ) -> Callable[[], None]:
        self.ensure_chapter(project_id, number)
        if kind not in ("plots", "characters", "bible"):
            raise BadRequest("kind must be plots, characters, or bible")
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from chapter_miner import ChapterMiner  # noqa: WPS433
            ChapterMiner(proj_path).mine(
                number, kind, source=source,
                on_progress=_operational_log,
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    def make_background_extract_job(
        self, project_id: str, text: str, label: str = "Background",
    ) -> Callable[[], None]:
        self._project_dir(project_id)
        if not text.strip():
            raise BadRequest("Background text is required.")
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from background_extractor import BackgroundExtractor  # noqa: E402
            BackgroundExtractor(proj_path).extract(
                text.strip(), label=label.strip() or "Background",
                on_progress=_operational_log,
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    # ----- Character profile generation (preview → merge in UI)

    def _character_generator(self, project_id: str):
        from character_generator import CharacterGenerator  # noqa: E402
        return CharacterGenerator(str(self._project_dir(project_id)))

    def get_character_generate_preview(self, project_id: str) -> dict | None:
        self._project_dir(project_id)
        path = self._character_generator(project_id).preview_path()
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def make_character_generate_job(
        self,
        project_id: str,
        prompt: str,
        *,
        character_id: str | None = None,
        hint_name: str = "",
        hint_role: str = "",
    ) -> Callable[[], None]:
        self._project_dir(project_id)
        if not prompt.strip():
            raise BadRequest("Character prompt is required.")
        if character_id:
            s = self._load(project_id)
            if s.get_character(character_id) is None:
                raise CharacterNotFound(character_id)
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from character_generator import CharacterGenerator  # noqa: E402
            CharacterGenerator(proj_path).generate(
                prompt.strip(),
                character_id=character_id,
                hint_name=hint_name,
                hint_role=hint_role,
                on_progress=_operational_log,
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    def discard_character_generate_preview(self, project_id: str) -> None:
        path = self._character_generator(project_id).preview_path()
        if path.exists():
            path.unlink()

    # ----- Plot thread description generation (preview → apply in UI)

    def _plot_generator(self, project_id: str):
        from plot_generator import PlotGenerator  # noqa: E402
        return PlotGenerator(str(self._project_dir(project_id)))

    def get_plot_generate_preview(self, project_id: str, thread_id: str) -> dict | None:
        self._project_dir(project_id)
        path = self._plot_generator(project_id).preview_path(thread_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def make_plot_generate_job(
        self,
        project_id: str,
        thread_id: str,
        prompt: str = "",
    ) -> Callable[[], None]:
        self._project_dir(project_id)
        s = self._load(project_id)
        if thread_id not in s.plot_threads:
            raise PlotThreadNotFound(thread_id)
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from plot_generator import PlotGenerator  # noqa: E402
            PlotGenerator(proj_path).generate(
                thread_id,
                prompt=prompt,
                on_progress=_operational_log,
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    def discard_plot_generate_preview(self, project_id: str, thread_id: str) -> None:
        path = self._plot_generator(project_id).preview_path(thread_id)
        if path.exists():
            path.unlink()

    # ----- Plot panel dedup (subplots vs threads on plots page)

    def _plot_panel_issue_model(self, issue) -> "PlotPanelIssueModel":
        from api.models import PlotPanelIssueModel, PlotPanelLocation  # noqa: E402
        return PlotPanelIssueModel(
            issue_id=issue.issue_id,
            kind=issue.kind,
            confidence=issue.confidence,
            reason=issue.reason,
            subplot_line=issue.subplot_line,
            locations=[PlotPanelLocation(**loc) for loc in issue.locations],
            thread_id=issue.thread_id,
            thread_name=issue.thread_name,
            suggested_parent_id=issue.suggested_parent_id,
            suggested_parent_name=issue.suggested_parent_name,
            suggested_action=issue.suggested_action,
        )

    def get_plot_panel_issues(self, project_id: str):
        from api.models import PlotPanelIssuesReport  # noqa: E402
        from entity_dedup import find_plot_panel_issues  # noqa: E402

        s = self._load(project_id)
        issues = find_plot_panel_issues(s)
        return PlotPanelIssuesReport(
            issues=[self._plot_panel_issue_model(i) for i in issues],
        )

    def resolve_plot_panel_issue(self, project_id: str, issue_id: str):
        from api.models import PlotPanelResolveResult  # noqa: E402
        from entity_dedup import find_plot_panel_issues, resolve_plot_panel_issue  # noqa: E402

        s = self._load(project_id)
        issues = find_plot_panel_issues(s)
        try:
            log = resolve_plot_panel_issue(s, issue_id, issues=issues)
        except ValueError as e:
            raise BadRequest(str(e)) from e
        s.save_state()
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return PlotPanelResolveResult(issue_id=issue_id, log=log)

    def auto_resolve_plot_panel_issues(self, project_id: str):
        from api.models import PlotPanelAutoResolveResult  # noqa: E402
        from entity_dedup import auto_resolve_plot_panel_issues, find_plot_panel_issues  # noqa: E402

        s = self._load(project_id)
        before = len(find_plot_panel_issues(s))
        log = auto_resolve_plot_panel_issues(s)
        after = len(find_plot_panel_issues(s))
        if log:
            s.save_state()
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass
        return PlotPanelAutoResolveResult(resolved=max(0, before - after), log=log)

    # ----- Chapter regenerate (preview → keep / discard)

    def _regenerator(self, project_id: str):
        from chapter_regenerator import ChapterRegenerator  # noqa: E402
        return ChapterRegenerator(str(self._project_dir(project_id)))

    def get_regenerate_preview(self, project_id: str, number: int) -> dict | None:
        self.ensure_chapter(project_id, number)
        reg = self._regenerator(project_id)
        preview_path = reg.preview_path(number)
        if not preview_path.exists():
            return None
        meta: dict = {}
        meta_path = reg.meta_path(number)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return {
            "text": preview_path.read_text(encoding="utf-8"),
            "source": meta.get("source", "draft"),
            "original_word_count": meta.get("original_word_count", 0),
            "preview_word_count": meta.get("preview_word_count", 0),
            "generated_at": meta.get("generated_at"),
            "instructions": meta.get("instructions", ""),
        }

    def make_regenerate_job(
        self,
        project_id: str,
        number: int,
        *,
        source: str = "draft",
        instructions: str = "",
    ) -> Callable[[], None]:
        self.ensure_chapter(project_id, number)
        reg = self._regenerator(project_id)
        reg.read_source(number, source)  # validate before starting job
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from chapter_regenerator import ChapterRegenerator  # noqa: E402
            ChapterRegenerator(proj_path).regenerate(
                number,
                source=source,
                instructions=instructions,
                on_progress=_operational_log,
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    def apply_regenerate_preview(
        self,
        project_id: str,
        number: int,
        text: str,
        target: str | None = None,
    ) -> tuple[str, int]:
        self.ensure_chapter(project_id, number)
        if not text.strip():
            raise BadRequest("Preview text is empty.")
        reg = self._regenerator(project_id)
        if not reg.preview_path(number).exists():
            raise BadRequest("No regenerate preview to apply.")
        meta_path = reg.meta_path(number)
        meta: dict = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        stage = (target or meta.get("source") or "draft").lower()
        if stage not in ("draft", "revised", "final"):
            raise BadRequest("target must be draft, revised, or final")
        if stage == "draft":
            wc = self.save_draft(project_id, number, text)
        elif stage == "final":
            wc = self.save_final(project_id, number, text)
        else:
            wc = self.save_revised(project_id, number, text)
        self.discard_regenerate_preview(project_id, number)
        return stage, wc

    def discard_regenerate_preview(self, project_id: str, number: int) -> None:
        self.ensure_chapter(project_id, number)
        reg = self._regenerator(project_id)
        for path in (reg.preview_path(number), reg.meta_path(number)):
            if path.exists():
                path.unlink()

    # ----- Redraft from brief (preview → keep / discard; apply writes draft only)

    def _redrafter(self, project_id: str):
        from chapter_brief_redrafter import ChapterBriefRedrafter  # noqa: E402
        return ChapterBriefRedrafter(str(self._project_dir(project_id)))

    def get_redraft_preview(self, project_id: str, number: int) -> dict | None:
        self.ensure_chapter(project_id, number)
        rd = self._redrafter(project_id)
        preview_path = rd.preview_path(number)
        if not preview_path.exists():
            return None
        meta: dict = {}
        meta_path = rd.meta_path(number)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return {
            "text": preview_path.read_text(encoding="utf-8"),
            "source": meta.get("source", "final"),
            "mode": meta.get("mode", "align"),
            "original_word_count": meta.get("original_word_count", 0),
            "preview_word_count": meta.get("preview_word_count", 0),
            "generated_at": meta.get("generated_at"),
            "instructions": meta.get("instructions", ""),
        }

    def make_redraft_job(
        self,
        project_id: str,
        number: int,
        *,
        source: str = "final",
        mode: str = "align",
        instructions: str = "",
    ) -> Callable[[], None]:
        self.ensure_chapter(project_id, number)
        rd = self._redrafter(project_id)
        from chapter_brief_redrafter import VALID_MODES  # noqa: E402
        from chapter_brief_utils import brief_has_content  # noqa: E402

        if mode not in VALID_MODES:
            raise BadRequest("mode must be align or preserve")
        brief = rd.state.get_chapter_brief(number)
        if not brief_has_content(brief):
            raise BadRequest(f"Chapter {number} has no saved brief with content")
        rd.read_source(number, source)
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from chapter_brief_redrafter import ChapterBriefRedrafter  # noqa: E402
            ChapterBriefRedrafter(proj_path).redraft(
                number,
                source=source,
                mode=mode,
                instructions=instructions,
                on_progress=_operational_log,
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    def apply_redraft_preview(self, project_id: str, number: int, text: str) -> tuple[str, int]:
        self.ensure_chapter(project_id, number)
        if not text.strip():
            raise BadRequest("Preview text is empty.")
        rd = self._redrafter(project_id)
        if not rd.preview_path(number).exists():
            raise BadRequest("No redraft preview to apply.")
        wc = self.save_draft(project_id, number, text)
        self.discard_redraft_preview(project_id, number)
        return "draft", wc

    def discard_redraft_preview(self, project_id: str, number: int) -> None:
        self.ensure_chapter(project_id, number)
        rd = self._redrafter(project_id)
        nnn = f"{number:03d}"
        feedback = self._project_dir(project_id) / "outputs" / "feedback"
        for path in (
            rd.preview_path(number),
            rd.meta_path(number),
            feedback / f"chapter_{nnn}_redraft_prompt.md",
            feedback / f"chapter_{nnn}_redraft_report.md",
        ):
            if path.exists():
                path.unlink()

    # ----- Expand [[expand: …]] placeholders (preview → keep / discard)

    def _expander(self, project_id: str):
        from chapter_expander import ChapterExpander  # noqa: E402
        return ChapterExpander(str(self._project_dir(project_id)))

    def get_expand_preview(self, project_id: str, number: int) -> dict | None:
        self.ensure_chapter(project_id, number)
        exp = self._expander(project_id)
        preview_path = exp.preview_path(number)
        if not preview_path.exists():
            return None
        meta: dict = {}
        meta_path = exp.meta_path(number)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return {
            "text": preview_path.read_text(encoding="utf-8"),
            "source": meta.get("source", "draft"),
            "original_word_count": meta.get("original_word_count", 0),
            "preview_word_count": meta.get("preview_word_count", 0),
            "generated_at": meta.get("generated_at"),
            "instructions": meta.get("instructions", ""),
            "placeholder_count": meta.get("placeholder_count"),
        }

    def make_expand_job(
        self,
        project_id: str,
        number: int,
        *,
        source: str = "draft",
        instructions: str = "",
    ) -> Callable[[], None]:
        self.ensure_chapter(project_id, number)
        exp = self._expander(project_id)
        text = exp.read_source(number, source)
        from chapter_expander import find_placeholders  # noqa: E402
        if not find_placeholders(text):
            raise BadRequest(
                "No [[expand: …]] placeholders in this chapter. "
                "Add markers like [[expand: describe the crowd at the market]]."
            )
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from chapter_expander import ChapterExpander  # noqa: E402
            ChapterExpander(proj_path).expand(
                number,
                source=source,
                instructions=instructions,
                on_progress=_operational_log,
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    def apply_expand_preview(
        self,
        project_id: str,
        number: int,
        text: str,
        target: str | None = None,
    ) -> tuple[str, int]:
        self.ensure_chapter(project_id, number)
        if not text.strip():
            raise BadRequest("Preview text is empty.")
        exp = self._expander(project_id)
        if not exp.preview_path(number).exists():
            raise BadRequest("No expand preview to apply.")
        meta_path = exp.meta_path(number)
        meta: dict = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        stage = (target or meta.get("source") or "draft").lower()
        if stage not in ("draft", "revised", "final"):
            raise BadRequest("target must be draft, revised, or final")
        if stage == "draft":
            wc = self.save_draft(project_id, number, text)
        elif stage == "final":
            wc = self.save_final(project_id, number, text)
        else:
            wc = self.save_revised(project_id, number, text)
        self.discard_expand_preview(project_id, number)
        return stage, wc

    def discard_expand_preview(self, project_id: str, number: int) -> None:
        self.ensure_chapter(project_id, number)
        exp = self._expander(project_id)
        for path in (exp.preview_path(number), exp.meta_path(number)):
            if path.exists():
                path.unlink()

    # ----- AI paragraph / scene-break formatting (preview → keep / discard)

    def _paragraph_formatter(self, project_id: str):
        from chapter_paragraph_formatter import ChapterParagraphFormatter  # noqa: E402
        return ChapterParagraphFormatter(str(self._project_dir(project_id)))

    def get_paragraphs_preview(self, project_id: str, number: int) -> dict | None:
        self.ensure_chapter(project_id, number)
        fmt = self._paragraph_formatter(project_id)
        preview_path = fmt.preview_path(number)
        if not preview_path.exists():
            return None
        meta: dict = {}
        meta_path = fmt.meta_path(number)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return {
            "text": preview_path.read_text(encoding="utf-8"),
            "source": meta.get("source", "draft"),
            "original_word_count": meta.get("original_word_count", 0),
            "preview_word_count": meta.get("preview_word_count", 0),
            "generated_at": meta.get("generated_at"),
            "instructions": "",
            "scene_break_count": meta.get("scene_break_count"),
        }

    def make_format_paragraphs_job(
        self,
        project_id: str,
        number: int,
        *,
        source: str = "draft",
    ) -> Callable[[], None]:
        self.ensure_chapter(project_id, number)
        fmt = self._paragraph_formatter(project_id)
        text = fmt.read_source(number, source)
        if not text.strip():
            raise BadRequest(f"No {source} text found for this chapter.")
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from chapter_paragraph_formatter import ChapterParagraphFormatter  # noqa: E402
            ChapterParagraphFormatter(proj_path).format_paragraphs(
                number,
                source=source,
                on_progress=_operational_log,
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    def apply_paragraphs_preview(
        self,
        project_id: str,
        number: int,
        text: str,
        target: str | None = None,
    ) -> tuple[str, int]:
        self.ensure_chapter(project_id, number)
        if not text.strip():
            raise BadRequest("Preview text is empty.")
        fmt = self._paragraph_formatter(project_id)
        if not fmt.preview_path(number).exists():
            raise BadRequest("No paragraph-format preview to apply.")
        from chapter_paragraph_formatter import validate_formatting_only  # noqa: E402

        meta_path = fmt.meta_path(number)
        meta: dict = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        stage = (target or meta.get("source") or "draft").lower()
        if stage not in ("draft", "revised", "final"):
            raise BadRequest("target must be draft, revised, or final")
        original = fmt.read_source(number, stage)
        validate_formatting_only(original, text)
        if stage == "draft":
            wc = self.save_draft(project_id, number, text)
        elif stage == "final":
            wc = self.save_final(project_id, number, text)
        else:
            wc = self.save_revised(project_id, number, text)
        self.discard_paragraphs_preview(project_id, number)
        return stage, wc

    def discard_paragraphs_preview(self, project_id: str, number: int) -> None:
        self.ensure_chapter(project_id, number)
        fmt = self._paragraph_formatter(project_id)
        for path in (fmt.preview_path(number), fmt.meta_path(number)):
            if path.exists():
                path.unlink()

    def get_dialogue_quotes_preview(self, project_id: str, number: int) -> dict | None:
        self.ensure_chapter(project_id, number)
        fmt = self._paragraph_formatter(project_id)
        preview_path = fmt.dialogue_quotes_preview_path(number)
        if not preview_path.exists():
            return None
        meta: dict = {}
        meta_path = fmt.dialogue_quotes_meta_path(number)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return {
            "text": preview_path.read_text(encoding="utf-8"),
            "source": meta.get("source", "draft"),
            "original_word_count": meta.get("original_word_count", 0),
            "preview_word_count": meta.get("preview_word_count", 0),
            "generated_at": meta.get("generated_at"),
            "instructions": "",
            "quote_mark_count": meta.get("quote_mark_count"),
        }

    def make_check_dialogue_quotes_job(
        self,
        project_id: str,
        number: int,
        *,
        source: str = "draft",
    ) -> Callable[[], None]:
        self.ensure_chapter(project_id, number)
        fmt = self._paragraph_formatter(project_id)
        text = fmt.read_source(number, source)
        if not text.strip():
            raise BadRequest(f"No {source} text found for this chapter.")
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from chapter_paragraph_formatter import ChapterParagraphFormatter  # noqa: E402
            ChapterParagraphFormatter(proj_path).check_dialogue_quotes(
                number,
                source=source,
                on_progress=_operational_log,
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    def apply_dialogue_quotes_preview(
        self,
        project_id: str,
        number: int,
        text: str,
        target: str | None = None,
    ) -> tuple[str, int]:
        self.ensure_chapter(project_id, number)
        if not text.strip():
            raise BadRequest("Preview text is empty.")
        fmt = self._paragraph_formatter(project_id)
        if not fmt.dialogue_quotes_preview_path(number).exists():
            raise BadRequest("No dialogue quote preview to apply.")
        from chapter_paragraph_formatter import validate_dialogue_quotes_only  # noqa: E402

        meta_path = fmt.dialogue_quotes_meta_path(number)
        meta: dict = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        stage = (target or meta.get("source") or "draft").lower()
        if stage not in ("draft", "revised", "final"):
            raise BadRequest("target must be draft, revised, or final")
        original = fmt.read_source(number, stage)
        validate_dialogue_quotes_only(original, text)
        if stage == "draft":
            wc = self.save_draft(project_id, number, text)
        elif stage == "final":
            wc = self.save_final(project_id, number, text)
        else:
            wc = self.save_revised(project_id, number, text)
        self.discard_dialogue_quotes_preview(project_id, number)
        return stage, wc

    def discard_dialogue_quotes_preview(self, project_id: str, number: int) -> None:
        self.ensure_chapter(project_id, number)
        fmt = self._paragraph_formatter(project_id)
        for path in (fmt.dialogue_quotes_preview_path(number), fmt.dialogue_quotes_meta_path(number)):
            if path.exists():
                path.unlink()

    # ----- Chapter boundary alignment (preview → keep / discard)

    def _boundary_aligner(self, project_id: str):
        from chapter_boundary_aligner import ChapterBoundaryAligner  # noqa: E402
        return ChapterBoundaryAligner(str(self._project_dir(project_id)))

    def get_alignment_preview(self, project_id: str, number: int) -> dict | None:
        self.ensure_chapter(project_id, number)
        align = self._boundary_aligner(project_id)
        meta_path = align.meta_path(number)
        if not meta_path.exists():
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return {
            "chapter_a": int(meta.get("chapter_a", number)),
            "chapter_b": int(meta.get("chapter_b", number + 1)),
            "source": meta.get("source", "draft"),
            "adjusted": bool(meta.get("adjusted")),
            "direction": meta.get("direction"),
            "move_text": meta.get("move_text", ""),
            "text_a": meta.get("text_a", ""),
            "text_b": meta.get("text_b", ""),
            "original_word_count_a": meta.get("original_word_count_a", 0),
            "original_word_count_b": meta.get("original_word_count_b", 0),
            "preview_word_count_a": meta.get("preview_word_count_a", 0),
            "preview_word_count_b": meta.get("preview_word_count_b", 0),
            "generated_at": meta.get("generated_at"),
        }

    def make_align_boundary_job(
        self,
        project_id: str,
        number: int,
        *,
        source: str = "draft",
    ) -> Callable[[], None]:
        self.ensure_chapter(project_id, number)
        align = self._boundary_aligner(project_id)
        s = self._load(project_id)
        next_num = number + 1
        if next_num not in s.chapters:
            raise BadRequest(f"Chapter {next_num} does not exist — nothing to align with.")
        if not align.read_source(number, source).strip():
            raise BadRequest(f"No {source} text found for this chapter.")
        if not align.read_source(next_num, source).strip():
            raise BadRequest(f"No {source} text in chapter {next_num} for boundary alignment.")
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from chapter_boundary_aligner import ChapterBoundaryAligner  # noqa: E402
            ChapterBoundaryAligner(proj_path).align_boundary(
                number,
                next_num,
                source=source,
                on_progress=_operational_log,
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    def apply_alignment_preview(
        self,
        project_id: str,
        number: int,
        text_a: str,
        text_b: str,
    ) -> dict:
        self.ensure_chapter(project_id, number)
        if not text_a.strip() or not text_b.strip():
            raise BadRequest("Preview text is empty.")
        align = self._boundary_aligner(project_id)
        if not align.has_preview(number):
            raise BadRequest("No boundary alignment preview to apply.")
        meta = json.loads(align.meta_path(number).read_text(encoding="utf-8"))
        chapter_b = int(meta["chapter_b"])
        source = meta.get("source", "draft")
        align.apply_preview(number, text_a=text_a, text_b=text_b)
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return {
            "chapter_a": number,
            "chapter_b": chapter_b,
            "source": source,
            "word_count_a": len(text_a.split()),
            "word_count_b": len(text_b.split()),
        }

    def discard_alignment_preview(self, project_id: str, number: int) -> None:
        self.ensure_chapter(project_id, number)
        self._boundary_aligner(project_id).discard_preview(number)

    def _resolve_split_word_limit(
        self,
        project_id: str,
        number: int,
        *,
        max_words: int,
        use_target_length: bool,
    ) -> int:
        from prompt_budget import DEFAULT_SPLIT_WORDS  # noqa: E402
        from prompt_context import effective_target_word_count  # noqa: E402

        if max_words > 0:
            return max_words
        if use_target_length:
            s = self._load(project_id)
            chapter = s.get_chapter(number)
            brief = s.get_chapter_brief(number)
            target = effective_target_word_count(brief, s, chapter)
            return max(500, target)
        return DEFAULT_SPLIT_WORDS

    # ----- Generate outline from chapter prose (preview → keep / discard)

    def _outline_generator(self, project_id: str):
        from chapter_outline_generator import ChapterOutlineGenerator  # noqa: WPS433
        return ChapterOutlineGenerator(str(self._project_dir(project_id)))

    def save_outline(self, project_id: str, number: int, text: str) -> int:
        from prompt_context import strip_outline_pov_metadata  # noqa: WPS433

        self.ensure_chapter(project_id, number)
        cleaned = strip_outline_pov_metadata(text)
        _atomic_write(self._stage_paths(project_id, number)["outline"], cleaned)
        wc = len(cleaned.split())
        try:
            db.upsert_artifact(project_id, number, "outline", cleaned)
        except Exception:  # noqa: BLE001
            pass
        return wc

    def get_outline_preview(self, project_id: str, number: int) -> dict | None:
        self.ensure_chapter(project_id, number)
        gen = self._outline_generator(project_id)
        preview_path = gen.preview_path(number)
        if not preview_path.exists():
            return None
        meta: dict = {}
        meta_path = gen.meta_path(number)
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return {
            "text": preview_path.read_text(encoding="utf-8"),
            "source": meta.get("source", "draft"),
            "original_word_count": meta.get("original_word_count", 0),
            "preview_word_count": meta.get("preview_word_count", 0),
            "generated_at": meta.get("generated_at"),
            "instructions": meta.get("instructions", ""),
        }

    def make_generate_outline_job(
        self,
        project_id: str,
        number: int,
        *,
        source: str = "draft",
        instructions: str = "",
    ) -> Callable[[], None]:
        self.ensure_chapter(project_id, number)
        gen = self._outline_generator(project_id)
        if source == "notes":
            if not instructions.strip():
                raise BadRequest("Outline notes / direction are required.")
        else:
            gen._reader.read_source(number, source)
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from chapter_outline_generator import ChapterOutlineGenerator  # noqa: WPS433
            ChapterOutlineGenerator(proj_path).generate(
                number,
                source=source,
                instructions=instructions,
                on_progress=_operational_log,
            )

        return fn

    def batch_extract_outlines_stats(
        self,
        project_id: str,
        *,
        source: str = "best",
    ) -> BatchExtractOutlineStats:
        from batch_extract import BATCH_SOURCES, batch_outline_extract_stats  # noqa: WPS433

        self._project_dir(project_id)
        if source not in BATCH_SOURCES:
            raise BadRequest("source must be best, draft, revised, or final")
        stats = batch_outline_extract_stats(
            str(self._project_dir(project_id)),
            source=source,
        )
        return BatchExtractOutlineStats(**stats)

    def batch_extract_codex_stats(
        self,
        project_id: str,
        *,
        source: str = "best",
    ) -> BatchExtractOutlineStats:
        from batch_extract import BATCH_SOURCES, batch_codex_extract_stats  # noqa: WPS433

        self._project_dir(project_id)
        if source not in BATCH_SOURCES:
            raise BadRequest("source must be best, draft, revised, or final")
        stats = batch_codex_extract_stats(
            str(self._project_dir(project_id)),
            source=source,
        )
        return BatchExtractOutlineStats(**stats)

    def make_batch_extract_outlines_job(
        self,
        project_id: str,
        *,
        source: str = "best",
        skip_existing: bool = True,
        auto_accept: bool = False,
        chapters: list[int] | None = None,
    ) -> Callable[[], None]:
        from batch_extract import BATCH_SOURCES, batch_extract_outlines  # noqa: WPS433

        self._project_dir(project_id)
        if source not in BATCH_SOURCES:
            raise BadRequest("source must be best, draft, revised, or final")
        if chapters:
            for number in chapters:
                self.ensure_chapter(project_id, number)
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            batch_extract_outlines(
                proj_path,
                source=source,
                skip_existing=skip_existing,
                auto_accept=auto_accept,
                chapters=chapters,
                on_progress=_operational_log,
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    def make_batch_extract_codex_job(
        self,
        project_id: str,
        *,
        source: str = "best",
        skip_existing: bool = True,
        auto_accept: bool = False,
        chapters: list[int] | None = None,
    ) -> Callable[[], None]:
        from batch_extract import BATCH_SOURCES, batch_extract_codex  # noqa: WPS433

        self._project_dir(project_id)
        if source not in BATCH_SOURCES:
            raise BadRequest("source must be best, draft, revised, or final")
        if chapters:
            for number in chapters:
                self.ensure_chapter(project_id, number)
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            batch_extract_codex(
                proj_path,
                source=source,
                skip_existing=skip_existing,
                auto_accept=auto_accept,
                chapters=chapters,
                on_progress=_operational_log,
            )
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass

        return fn

    def apply_outline_preview(self, project_id: str, number: int, text: str) -> int:
        self.ensure_chapter(project_id, number)
        if not text.strip():
            raise BadRequest("Preview text is empty.")
        gen = self._outline_generator(project_id)
        if not gen.preview_path(number).exists():
            raise BadRequest("No outline preview to apply.")
        wc = self.save_outline(project_id, number, text)
        self.discard_outline_preview(project_id, number)
        return wc

    def discard_outline_preview(self, project_id: str, number: int) -> None:
        self.ensure_chapter(project_id, number)
        gen = self._outline_generator(project_id)
        for path in (gen.preview_path(number), gen.meta_path(number)):
            if path.exists():
                path.unlink()

    def split_oversized_chapter(
        self,
        project_id: str,
        number: int,
        *,
        source: str = "draft",
        max_words: int = 0,
        use_target_length: bool = False,
        align_boundaries: bool = False,
    ) -> SplitChapterResult:
        from chapter_splitter import ChapterSplitter, ChapterSplitError  # noqa: WPS433

        self.ensure_chapter(project_id, number)
        if source not in ("draft", "revised", "final"):
            raise BadRequest("source must be draft, revised, or final")
        limit = self._resolve_split_word_limit(
            project_id, number, max_words=max_words, use_target_length=use_target_length,
        )
        try:
            result = ChapterSplitter(str(self._project_dir(project_id))).split_chapter(
                number,
                source=source,
                max_words=limit,
            )
        except ChapterSplitError as exc:
            raise BadRequest(str(exc)) from exc

        alignments_applied = 0
        if align_boundaries and len(result.parts) > 1:
            from chapter_boundary_aligner import ChapterBoundaryAligner  # noqa: E402
            part_nums = [p["number"] for p in result.parts]
            alignments_applied = ChapterBoundaryAligner(
                str(self._project_dir(project_id)),
            ).align_boundaries_after_split(part_nums, source=source, on_progress=_operational_log)

        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        from api.models import SplitChapterPart  # noqa: E402

        return SplitChapterResult(
            parent_number=result.parent_number,
            parts=[
                SplitChapterPart(
                    number=p["number"],
                    display_label=p["display_label"],
                    word_count=p["word_count"],
                )
                for p in result.parts
            ],
            total_words=result.total_words,
            recovered_from_backup=result.recovered_from_backup,
            alignments_applied=alignments_applied,
            chapters=self.list_chapters(project_id),
        )

    # ----- Duplicate detection & merge

    def _dedup_suggestions_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "outputs" / "dedup" / "suggestions.json"

    def _group_to_model(self, g) -> DuplicateGroupModel:
        return DuplicateGroupModel(
            kind=g.kind,
            confidence=g.confidence,
            reason=g.reason,
            suggested_keep_id=g.suggested_keep_id,
            members=g.members,
        )

    def _ai_group_to_model(self, g: dict) -> DuplicateGroupModel | None:
        from api.models import DuplicateMember  # noqa: E402

        members = []
        for m in g.get("members") or []:
            if not isinstance(m, dict) or not m.get("id"):
                continue
            members.append(DuplicateMember(
                id=str(m["id"]),
                label=str(m.get("label") or m["id"]),
                role=m.get("role"),
                thread_type=m.get("thread_type"),
            ))
        if len(members) < 2:
            return None
        return DuplicateGroupModel(
            kind=str(g.get("kind", "character")),
            confidence=float(g.get("confidence", 0.85)),
            reason=str(g.get("reason", "AI suggested merge")),
            suggested_keep_id=str(g.get("suggested_keep_id", "")),
            members=members,
        )

    def _sync_entity_dedup_file(self, project_id: str, s, data: dict) -> dict:
        from entity_dedup import filter_stale_entity_groups  # noqa: E402

        ai_path = self._dedup_suggestions_path(project_id)
        chars = filter_stale_entity_groups(s, data.get("characters") or [], "character")
        plots = filter_stale_entity_groups(s, data.get("plot_threads") or [], "plot_thread")
        if chars == (data.get("characters") or []) and plots == (data.get("plot_threads") or []):
            return data
        data = dict(data)
        data["characters"] = chars
        data["plot_threads"] = plots
        if chars or plots or data.get("scanned_at"):
            ai_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        else:
            ai_path.unlink(missing_ok=True)
        return data

    def get_duplicates(self, project_id: str, *, prefer_ai: bool = False) -> DuplicatesReport:
        from entity_dedup import scan_duplicates  # noqa: E402

        s = self._load(project_id)
        ai_path = self._dedup_suggestions_path(project_id)
        if prefer_ai and ai_path.exists():
            data = json.loads(ai_path.read_text(encoding="utf-8"))
            data = self._sync_entity_dedup_file(project_id, s, data)
            char_models = [
                m for g in data.get("characters") or []
                if (m := self._ai_group_to_model(g)) is not None
            ]
            plot_models = [
                m for g in data.get("plot_threads") or []
                if (m := self._ai_group_to_model(g)) is not None
            ]
            return DuplicatesReport(
                characters=char_models,
                plot_threads=plot_models,
                source="ai",
                ai_scan_completed=bool(data.get("scanned_at")),
                scanned_at=data.get("scanned_at"),
            )
        report = scan_duplicates(s)
        return DuplicatesReport(
            characters=[self._group_to_model(g) for g in report["characters"]],
            plot_threads=[self._group_to_model(g) for g in report["plot_threads"]],
            source="heuristic",
        )

    def make_ai_duplicate_scan_job(self, project_id: str) -> Callable[[], None]:
        self._project_dir(project_id)
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from datetime import datetime, timezone

            from entity_dedup import ai_suggest_duplicate_groups  # noqa: E402
            from llm_client import LLMClient  # noqa: E402
            from state_manager import StoryState  # noqa: E402

            state = StoryState(proj_path)
            report = ai_suggest_duplicate_groups(state, LLMClient())
            out_path = Path(proj_path) / "outputs" / "dedup" / "suggestions.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "scanned_at": datetime.now(timezone.utc).isoformat(),
                "characters": [g.__dict__ for g in report["characters"]],
                "plot_threads": [g.__dict__ for g in report["plot_threads"]],
            }
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(
                f"AI duplicate scan: {len(payload['characters'])} character groups, "
                f"{len(payload['plot_threads'])} plot groups",
                flush=True,
            )

        return fn

    def _prune_dedup_suggestions(
        self, project_id: str, affected_ids: set[str],
    ) -> None:
        path = self._dedup_suggestions_path(project_id)
        if not path.exists() or not affected_ids:
            return
        data = json.loads(path.read_text(encoding="utf-8"))

        def touched(group: dict) -> bool:
            member_ids = {str(m.get("id", "")) for m in group.get("members") or []}
            return bool(member_ids & affected_ids)

        for key in ("characters", "plot_threads"):
            data[key] = [g for g in data.get(key, []) if not touched(g)]
        if not data.get("characters") and not data.get("plot_threads"):
            if data.get("scanned_at"):
                path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            else:
                path.unlink()
        else:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def merge_entities(
        self,
        project_id: str,
        kind: str,
        keep_id: str,
        merge_ids: list[str],
        *,
        mode: str = "parallel",
        label_override: str = "",
    ) -> MergeResult:
        from entity_dedup import merge_characters, merge_plot_threads, nest_plot_threads  # noqa: E402

        s = self._load(project_id)
        merge_ids = [m for m in merge_ids if m != keep_id]
        if not merge_ids:
            raise BadRequest("Nothing to merge.")
        override = label_override.strip()
        if kind == "character":
            if mode != "parallel":
                raise BadRequest("Characters only support parallel merge.")
            log = merge_characters(s, keep_id, merge_ids, label_override=override)
            keep_label = s.characters[keep_id].full_name if keep_id in s.characters else override
        elif kind == "plot_thread":
            if mode == "nest":
                log = nest_plot_threads(s, keep_id, merge_ids, label_override=override)
            else:
                log = merge_plot_threads(s, keep_id, merge_ids, label_override=override)
            keep_label = s.plot_threads[keep_id].name if keep_id in s.plot_threads else override
        else:
            raise BadRequest("kind must be character or plot_thread")
        s.save_state()
        affected = {keep_id, *merge_ids}
        self._prune_dedup_suggestions(project_id, affected)
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return MergeResult(
            kind=kind, keep_id=keep_id, merged=merge_ids, log=log, mode=mode,
            keep_label=keep_label or override,
        )

    def nest_plot_threads(self, project_id: str, parent_id: str, child_ids: list[str]) -> MergeResult:
        return self.merge_entities(
            project_id, "plot_thread", parent_id, child_ids, mode="nest",
        )

    def auto_resolve_duplicates(self, project_id: str) -> AutoResolveResult:
        from entity_dedup import auto_resolve_duplicates  # noqa: E402

        s = self._load(project_id)
        before_c = len(s.characters)
        before_p = len(s.plot_threads)
        log = auto_resolve_duplicates(s)
        s.save_state()
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return AutoResolveResult(
            merged_characters=before_c - len(s.characters),
            merged_plot_threads=before_p - len(s.plot_threads),
            log=log,
        )

    def clear_ai_duplicate_suggestions(self, project_id: str) -> None:
        path = self._dedup_suggestions_path(project_id)
        if path.exists():
            path.unlink()

    # ----- Story bible deduplication

    def _bible_dedup_suggestions_path(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "outputs" / "dedup" / "bible_suggestions.json"

    def _bible_group_to_model(self, g) -> BibleDuplicateGroupModel:
        return BibleDuplicateGroupModel(
            section=g.section,
            confidence=g.confidence,
            reason=g.reason,
            suggested_keep_index=g.suggested_keep_index,
            members=[BibleDuplicateMember(**m) for m in g.members],
        )

    def get_bible_duplicates(self, project_id: str, *, prefer_ai: bool = False) -> BibleDuplicatesReport:
        from bible_dedup import filter_stale_bible_groups, find_bible_duplicate_groups  # noqa: E402

        s = self._load(project_id)
        ai_path = self._bible_dedup_suggestions_path(project_id)
        if prefer_ai and ai_path.exists():
            data = json.loads(ai_path.read_text(encoding="utf-8"))
            raw_groups = filter_stale_bible_groups(s.story_bible, data.get("groups", []))
            if raw_groups != data.get("groups", []):
                if raw_groups:
                    data["groups"] = raw_groups
                    ai_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
                else:
                    ai_path.unlink(missing_ok=True)
            return BibleDuplicatesReport(
                groups=[BibleDuplicateGroupModel(**g) for g in raw_groups],
                source="ai",
            )
        groups = find_bible_duplicate_groups(s.story_bible)
        return BibleDuplicatesReport(
            groups=[self._bible_group_to_model(g) for g in groups],
            source="heuristic",
        )

    def get_bible_dedup_status(self, project_id: str):
        from api.models import BibleDedupStatus  # noqa: E402

        ai_path = self._bible_dedup_suggestions_path(project_id)
        if not ai_path.exists():
            return BibleDedupStatus(ai_suggestions_ready=False, ai_group_count=0)
        try:
            data = json.loads(ai_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return BibleDedupStatus(ai_suggestions_ready=False, ai_group_count=0)
        groups = data.get("groups") or []
        return BibleDedupStatus(ai_suggestions_ready=bool(groups), ai_group_count=len(groups))

    def get_duplicates_status(self, project_id: str):
        from api.models import EntityDedupStatus  # noqa: E402

        ai_path = self._dedup_suggestions_path(project_id)
        if not ai_path.exists():
            return EntityDedupStatus(
                ai_suggestions_ready=False,
                ai_group_count=0,
                has_ai_file=False,
                ai_scan_completed=False,
            )
        try:
            data = json.loads(ai_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return EntityDedupStatus(
                ai_suggestions_ready=False,
                ai_group_count=0,
                has_ai_file=True,
                ai_scan_completed=False,
            )
        char_count = len(data.get("characters") or [])
        plot_count = len(data.get("plot_threads") or [])
        count = char_count + plot_count
        scanned_at = data.get("scanned_at")
        return EntityDedupStatus(
            ai_suggestions_ready=count > 0,
            ai_group_count=count,
            has_ai_file=True,
            ai_scan_completed=bool(scanned_at),
            character_group_count=char_count,
            plot_thread_group_count=plot_count,
        )

    def make_bible_ai_dedup_job(self, project_id: str) -> Callable[[], None]:
        self._project_dir(project_id)
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from bible_dedup import ai_suggest_bible_duplicate_groups  # noqa: E402
            from llm_client import LLMClient  # noqa: E402
            from state_manager import StoryState  # noqa: E402

            state = StoryState(proj_path)
            groups = ai_suggest_bible_duplicate_groups(state.story_bible, LLMClient())
            out_path = Path(proj_path) / "outputs" / "dedup" / "bible_suggestions.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"groups": [g.__dict__ for g in groups]}
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"AI bible dedup: {len(groups)} group(s)", flush=True)

        return fn

    def merge_bible_duplicates(self, project_id: str, body: BibleDedupeMerge) -> BibleAutoDedupeResult:
        from bible_dedup import apply_bible_group_members, prune_bible_suggestion_groups, section_items  # noqa: E402

        s = self._load(project_id)
        members = [m.model_dump() for m in body.members]
        if len(members) < 2:
            raise BadRequest("Need at least two bible entries to merge.")
        try:
            log = apply_bible_group_members(
                s.story_bible,
                members,
                body.keep_section,
                body.keep_index,
                text_override=body.text_override,
            )
        except ValueError as e:
            raise BadRequest(str(e)) from e
        s.save_state()
        from bible_dedup import bible_match_score  # noqa: E402

        keep_text = body.text_override.strip()
        if not keep_text:
            items = section_items(s.story_bible, body.keep_section)
            keep_label = next(
                (
                    str(m["label"])
                    for m in members
                    if m["section"] == body.keep_section and m["index"] == body.keep_index
                ),
                "",
            )
            for item in items:
                if keep_label and bible_match_score(item, keep_label) >= 0.85:
                    keep_text = item
                    break
            if not keep_text and items:
                keep_text = items[0]
        affected = {str(m.get("id", "")) for m in members if m.get("id")}
        ai_path = self._bible_dedup_suggestions_path(project_id)
        if ai_path.exists() and affected:
            data = json.loads(ai_path.read_text(encoding="utf-8"))
            remaining = prune_bible_suggestion_groups(data.get("groups", []), affected)
            if remaining:
                data["groups"] = remaining
                ai_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            else:
                ai_path.unlink(missing_ok=True)
        return BibleAutoDedupeResult(removed=len(log), log=log, keep_text=keep_text)

    def auto_dedupe_bible(self, project_id: str) -> BibleAutoDedupeResult:
        from bible_dedup import auto_dedupe_bible  # noqa: E402

        s = self._load(project_id)
        log = auto_dedupe_bible(s.story_bible)
        if log:
            s.save_state()
        return BibleAutoDedupeResult(removed=len(log), log=log)

    # ----- Project backups

    def _backup_hooks(self, project_id: str):
        from project_backup import BACKUP_VERSION  # noqa: WPS433

        def prepare_export() -> dict:
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass
            data = db.export_project_data(project_id)
            data["version"] = BACKUP_VERSION
            return data

        def import_db(data: dict) -> None:
            db.import_project_data(project_id, data)

        def sync_artifacts() -> None:
            db.sync_artifacts_to_files(self.root, project_id)

        return prepare_export, import_db, sync_artifacts

    def list_backups(self, project_id: str) -> dict:
        from project_backup import list_backups  # noqa: WPS433

        proj = self._project_dir(project_id)
        report = list_backups(proj)
        return report

    def create_named_backup(self, project_id: str, label: str) -> dict:
        from project_backup import create_named_backup  # noqa: WPS433

        proj = self._project_dir(project_id)
        prepare, _, _ = self._backup_hooks(project_id)
        entry = create_named_backup(proj, label, db_export=prepare())
        return entry

    def restore_named_backup(self, project_id: str, backup_id: str) -> dict:
        from project_backup import restore_named_backup  # noqa: WPS433

        proj = self._project_dir(project_id)
        prepare, import_db, sync_artifacts = self._backup_hooks(project_id)
        return restore_named_backup(
            proj, backup_id,
            import_db=import_db,
            sync_artifacts=sync_artifacts,
        )

    def delete_named_backup(self, project_id: str, backup_id: str) -> None:
        from project_backup import delete_named_backup  # noqa: WPS433

        proj = self._project_dir(project_id)
        if not delete_named_backup(proj, backup_id):
            raise BadRequest(f"Backup {backup_id!r} not found.")

    def quick_save_backup(self, project_id: str) -> dict:
        from project_backup import quick_save  # noqa: WPS433

        proj = self._project_dir(project_id)
        prepare, _, _ = self._backup_hooks(project_id)
        return quick_save(proj, db_export=prepare())

    def quick_restore_backup(self, project_id: str) -> dict:
        from project_backup import quick_restore  # noqa: WPS433

        proj = self._project_dir(project_id)
        prepare, import_db, sync_artifacts = self._backup_hooks(project_id)
        return quick_restore(
            proj,
            db_export=prepare(),
            import_db=import_db,
            sync_artifacts=sync_artifacts,
        )

    def undo_backup_restore(self, project_id: str) -> dict:
        from project_backup import undo_quick_restore  # noqa: WPS433

        proj = self._project_dir(project_id)
        _, import_db, sync_artifacts = self._backup_hooks(project_id)
        return undo_quick_restore(
            proj,
            import_db=import_db,
            sync_artifacts=sync_artifacts,
        )

    # ----- Portable export / import

    def export_project_package(self, project_id: str) -> tuple[str, bytes]:
        from project_portable import build_package_bytes  # noqa: WPS433

        proj = self._project_dir(project_id)
        prepare, _, _ = self._backup_hooks(project_id)
        db_data = prepare()
        s = self._load(project_id)
        title = s.metadata.get("title", project_id)
        data = build_package_bytes(proj, db_data, project_id=project_id, title=title)
        filename = f"{_slugify(title)}.novel-os.zip"
        return filename, data

    def import_project_package(self, zip_bytes: bytes) -> ProjectSummary:
        from project_portable import import_package_bytes  # noqa: WPS433

        def import_db(new_id: str, data: dict) -> None:
            map_remap = db.import_project_data(
                new_id, data, allow_id_mismatch=True, remap_ids=True,
            )
            if map_remap:
                map_assets.remap_map_asset_dirs(self._project_dir(new_id), map_remap)

        def sync_artifacts(new_id: str) -> None:
            db.sync_artifacts_to_files(self.root, new_id)

        project_id, title = import_package_bytes(
            self.root,
            zip_bytes,
            import_db=import_db,
            sync_artifacts=sync_artifacts,
            slugify=_slugify,
        )
        s = self._load(project_id)
        return ProjectSummary(
            id=project_id,
            title=s.metadata.get("title", title),
            genre=s.metadata.get("genre", ""),
            chapter_count=len(s.chapters),
            status=s.metadata.get("status", "in_progress"),
        )

    # ----- Stashed projects

    def list_stashed_projects(self) -> list[StashedProjectSummary]:
        from project_stash import list_stashed  # noqa: WPS433

        return [StashedProjectSummary(**entry) for entry in list_stashed(self.stashed_root)]

    def stash_project(self, project_id: str) -> StashedProjectSummary:
        from project_portable import build_package_bytes  # noqa: WPS433
        from project_stash import stash_project as core_stash  # noqa: WPS433

        proj = self._project_dir(project_id)
        s = self._load(project_id)
        prepare, _, _ = self._backup_hooks(project_id)
        db_data = prepare()
        title = s.metadata.get("title", project_id)
        genre = s.metadata.get("genre", "")
        chapter_count = len(s.chapters)
        zip_bytes = build_package_bytes(proj, db_data, project_id=project_id, title=title)
        entry = core_stash(
            proj,
            self.stashed_root,
            zip_bytes,
            {
                "id": project_id,
                "title": title,
                "genre": genre,
                "chapter_count": chapter_count,
            },
        )
        try:
            db.project_delete(project_id)
        except Exception:  # noqa: BLE001
            pass
        shutil.rmtree(proj)
        return StashedProjectSummary(**entry)

    def restore_stashed_project(self, stash_id: str) -> ProjectSummary:
        from project_portable import import_package_bytes  # noqa: WPS433
        from project_stash import restore_stashed  # noqa: WPS433

        def import_fn(zip_bytes: bytes) -> tuple[str, str]:
            def import_db(new_id: str, data: dict) -> None:
                map_remap = db.import_project_data(
                    new_id, data, allow_id_mismatch=True, remap_ids=True,
                )
                if map_remap:
                    map_assets.remap_map_asset_dirs(self._project_dir(new_id), map_remap)

            def sync_artifacts(new_id: str) -> None:
                db.sync_artifacts_to_files(self.root, new_id)

            return import_package_bytes(
                self.root,
                zip_bytes,
                import_db=import_db,
                sync_artifacts=sync_artifacts,
                slugify=_slugify,
                preferred_project_id=stash_id,
            )

        project_id, title = restore_stashed(
            self.stashed_root,
            self.root,
            stash_id,
            import_fn,
        )
        s = self._load(project_id)
        return ProjectSummary(
            id=project_id,
            title=s.metadata.get("title", title),
            genre=s.metadata.get("genre", ""),
            chapter_count=len(s.chapters),
            status=s.metadata.get("status", "in_progress"),
        )

    # ----- Delete operations

    def delete_project(self, project_id: str) -> None:
        proj = self._project_dir(project_id)
        try:
            db.project_delete(project_id)
        except Exception:  # noqa: BLE001
            pass
        shutil.rmtree(proj)

    def delete_chapter(self, project_id: str, number: int) -> None:
        s = self._load(project_id)
        if number not in s.chapters:
            raise ChapterNotFound(number)
        proj = self._project_dir(project_id)
        for path in self._chapter_files(proj, number):
            path.unlink()
        s.delete_chapter(number)
        s.save_state()
        try:
            db.chapter_delete_all(project_id, number)
        except Exception:  # noqa: BLE001
            pass

    def delete_character(self, project_id: str, character_id: str) -> None:
        proj = self._project_dir(project_id)
        s = self._load(project_id)
        char = s.get_character(character_id)
        if char is None:
            raise CharacterNotFound(character_id)
        name = char.full_name
        had_portrait = bool(char.portrait_filename)
        s.delete_character(character_id)
        s.save_state()
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        prof = proj / "outputs" / "characters" / f"{slug}.md"
        if prof.exists():
            prof.unlink()
        if had_portrait:
            try:
                portrait_assets.remove_portrait_assets(proj, character_id)
            except portrait_assets.PortraitAssetError:
                pass

    def delete_plot_thread(self, project_id: str, thread_id: str) -> None:
        s = self._load(project_id)
        if s.get_plot_thread(thread_id) is None:
            raise PlotThreadNotFound(thread_id)
        s.delete_plot_thread(thread_id)
        s.save_state()

    # ----- Reviewable changes

    @staticmethod
    def _reviewable_change_model(change: ReviewableChange) -> ReviewableChangeModel:
        return ReviewableChangeModel(**change.to_dict())

    def list_reviewable_changes(
        self,
        project_id: str,
        *,
        status: str | None = None,
        kind: str | None = None,
        source: str | None = None,
    ) -> list[ReviewableChangeModel]:
        s = self._load(project_id)
        changes = list(s.reviewable_changes.values())
        if status:
            changes = [c for c in changes if c.status == status]
        if kind:
            changes = [c for c in changes if c.kind == kind]
        if source:
            changes = [c for c in changes if c.source == source]
        changes.sort(key=lambda c: (c.created_at, c.id))
        return [self._reviewable_change_model(c) for c in changes]

    def generate_graph_suggestions(
        self,
        project_id: str,
        *,
        auto_apply: bool = False,
    ) -> GenerateGraphSuggestionsResult:
        s = self._load(project_id)
        changes = generate_graph_reviewable_changes(s)
        applied = 0
        if auto_apply:
            for change in changes:
                before_status = change.status
                apply_reviewable_change(s, change)
                if before_status != "applied_needs_review" and change.status == "applied_needs_review":
                    applied += 1
        if changes:
            s.save_state()
        return GenerateGraphSuggestionsResult(
            changes=[self._reviewable_change_model(c) for c in changes],
            generated=len(changes),
            applied=applied,
        )

    def _get_reviewable_change(self, state: StoryState, change_id: str) -> ReviewableChange:
        change = state.reviewable_changes.get(change_id)
        if change is None:
            raise ReviewableChangeNotFound(change_id)
        return change

    def apply_reviewable_change(self, project_id: str, change_id: str) -> ReviewableChangeModel:
        s = self._load(project_id)
        change = self._get_reviewable_change(s, change_id)
        try:
            apply_reviewable_change(s, change)
        except ReviewableChangeActionError as e:
            raise BadRequest(str(e)) from e
        s.save_state()
        return self._reviewable_change_model(change)

    def dismiss_reviewable_change(self, project_id: str, change_id: str) -> ReviewableChangeModel:
        s = self._load(project_id)
        change = self._get_reviewable_change(s, change_id)
        try:
            dismiss_reviewable_change(change)
        except ReviewableChangeActionError as e:
            raise BadRequest(str(e)) from e
        s.save_state()
        return self._reviewable_change_model(change)

    def mark_reviewable_change_reviewed(self, project_id: str, change_id: str) -> ReviewableChangeModel:
        s = self._load(project_id)
        change = self._get_reviewable_change(s, change_id)
        mark_reviewable_change_reviewed(change)
        s.save_state()
        return self._reviewable_change_model(change)

    def revert_reviewable_change(self, project_id: str, change_id: str) -> ReviewableChangeModel:
        s = self._load(project_id)
        change = self._get_reviewable_change(s, change_id)
        try:
            revert_reviewable_change(s, change)
        except ReviewableChangeActionError as e:
            raise BadRequest(str(e)) from e
        s.save_state()
        return self._reviewable_change_model(change)

    def mine_all(
        self,
        project_id: str,
        *,
        mode: str,
        auto_apply: bool = False,
        chapters: list[int] | None = None,
    ) -> MineAllResult:
        mode_key = (mode or "").strip()
        if mode_key not in {"missing_outlines", "missing_briefs", "everything"}:
            raise BadRequest("mode must be missing_outlines, missing_briefs, or everything")
        if chapters is not None and any(int(n) < 1 for n in chapters):
            raise BadRequest("chapters must contain positive chapter numbers")
        # First backend slice: graph suggestions are wired now; prose/brief mining remains job-scoped.
        result = self.generate_graph_suggestions(project_id, auto_apply=auto_apply)
        chapter_scope = "all chapters" if not chapters else f"{len(chapters)} chapter(s)"
        return MineAllResult(
            mode=mode_key,
            status="scaffolded",
            message=(
                "Graph suggestions generated synchronously; outline and brief mining "
                f"for {chapter_scope} is not yet orchestrated by this endpoint."
            ),
            changes=result.changes,
        )

    def make_mine_all_job(
        self,
        project_id: str,
        *,
        mode: str,
        auto_apply: bool = False,
        chapters: list[int] | None = None,
    ) -> Callable[[], None]:
        """Build a project-level mining job from existing preview/apply-safe phases."""
        from batch_extract import BATCH_SOURCES, batch_extract_codex, batch_extract_outlines  # noqa: WPS433
        from job_control import check_job_cancelled  # noqa: WPS433
        from job_progress import RollingJobProgress  # noqa: WPS433

        self._project_dir(project_id)
        mode_key = (mode or "").strip()
        if mode_key not in {"missing_outlines", "missing_briefs", "everything"}:
            raise BadRequest("mode must be missing_outlines, missing_briefs, or everything")
        if "best" not in BATCH_SOURCES:
            raise BadRequest("best source unavailable")
        if chapters:
            for number in chapters:
                self.ensure_chapter(project_id, number)
        if chapters is not None and any(int(n) < 1 for n in chapters):
            raise BadRequest("chapters must contain positive chapter numbers")

        project_path = str(self._project_dir(project_id))
        skip_existing = mode_key != "everything"
        phase_total = 1 if mode_key == "missing_outlines" else 5

        def fn() -> None:
            progress = RollingJobProgress(total=phase_total, unit="phase")

            progress.start("Extracting chapter outlines")
            batch_extract_outlines(
                project_path,
                source="best",
                skip_existing=skip_existing,
                auto_accept=auto_apply,
                chapters=chapters,
                on_progress=_operational_log,
            )
            progress.complete("Outline extraction finished")
            check_job_cancelled()

            if mode_key == "missing_outlines":
                try:
                    db.ingest_project(self.root, project_id)
                except Exception:  # noqa: BLE001
                    pass
                return

            progress.start("Mining characters, plots, and bible")
            batch_extract_codex(
                project_path,
                source="best",
                skip_existing=skip_existing,
                auto_accept=auto_apply,
                chapters=chapters,
                on_progress=_operational_log,
            )
            progress.complete("Codex mining finished")
            check_job_cancelled()

            progress.start("Generating graph suggestions")
            self.generate_graph_suggestions(project_id, auto_apply=auto_apply)
            progress.complete("Graph suggestions generated")
            check_job_cancelled()

            if auto_apply:
                progress.start("Generating chapter briefs")
                self.generate_chapter_briefs(
                    project_id,
                    source="best",
                    overwrite_existing=mode_key == "everything",
                    use_ai=True,
                )
                progress.complete("Chapter briefs generated")
                check_job_cancelled()
            else:
                progress.start("Skipping direct chapter brief writes")
                _operational_log(
                    "Mine All skipped chapter brief generation because review mode "
                    "requires a reviewable brief wrapper before writing briefs.",
                )
                progress.skip("Chapter brief generation queued for future reviewable wrapper")

            progress.start("Refreshing project index")
            try:
                db.ingest_project(self.root, project_id)
            except Exception:  # noqa: BLE001
                pass
            progress.complete("Mine All complete")

        return fn

    # ----- Story graph / chapter briefs

    def _story_graph_node_summary(self, node: StoryGraphNode) -> StoryGraphNodeSummary:
        data = node.to_dict()
        layout = data.get("layout")
        if layout is not None and not isinstance(layout, dict):
            data["layout"] = layout
        elif layout is None:
            data.pop("layout", None)
        return StoryGraphNodeSummary(**data)

    @staticmethod
    def _chapter_beat_summary(beat: ChapterBeat) -> ChapterBeatSummary:
        return ChapterBeatSummary(**beat.to_dict())

    def list_story_graph_nodes(self, project_id: str) -> list[StoryGraphNodeSummary]:
        s = self._load(project_id)
        return [self._story_graph_node_summary(n) for n in s.get_ordered_story_graph_nodes()]

    def create_story_graph_node(
        self,
        project_id: str,
        title: str,
        kind: str = "beat",
        description: str = "",
        status: str = "active",
        priority: int = 1,
        linked_character_ids: list[str] | None = None,
        legacy_plot_thread_id: str = "",
        sort_order: int = 0,
        start_chapter: int = 0,
        resolution_chapter: int | None = None,
        layout: dict | None = None,
        act: int = 0,
        chapter_number: int | None = None,
        assign_to_brief: bool = False,
    ) -> StoryGraphNodeSummary:
        s = self._load(project_id)
        if not title.strip():
            raise BadRequest("Node title is required.")
        for cid in linked_character_ids or []:
            if s.get_character(cid) is None:
                raise CharacterNotFound(cid)
        if legacy_plot_thread_id and s.get_plot_thread(legacy_plot_thread_id) is None:
            raise PlotThreadNotFound(legacy_plot_thread_id)
        if chapter_number is not None and chapter_number < 1:
            raise BadRequest("chapter_number must be at least 1.")
        if assign_to_brief and chapter_number is None:
            raise BadRequest("chapter_number is required when assign_to_brief is true.")
        effective_start = start_chapter
        if chapter_number is not None and effective_start <= 0:
            effective_start = chapter_number
        n = len(s.story_graph_nodes) + 1
        nid = f"graph_node_{n:03d}"
        while nid in s.story_graph_nodes:
            n += 1
            nid = f"graph_node_{n:03d}"
        node_layout = StoryGraphLayout.from_dict(layout) if layout else None
        node = StoryGraphNode(
            id=nid,
            kind=kind.strip() or "beat",
            title=title.strip(),
            description=description.strip(),
            status=status,
            priority=priority,
            linked_character_ids=list(linked_character_ids or []),
            legacy_plot_thread_id=legacy_plot_thread_id.strip(),
            created_from="manual",
            sort_order=sort_order,
            start_chapter=effective_start,
            resolution_chapter=resolution_chapter,
            layout=node_layout,
            act=act,
        )
        s.add_story_graph_node(node)
        if assign_to_brief and chapter_number is not None:
            brief = s.get_chapter_brief(chapter_number)
            if brief is None:
                brief = ChapterBrief(chapter_number=chapter_number)
            active = list(brief.active_node_ids or [])
            if nid not in active:
                active.append(nid)
            brief.active_node_ids = active
            s.set_chapter_brief(brief)
            sync_chapter_pins_for_brief(s, brief)
        s.save_state()
        return self._story_graph_node_summary(node)

    def update_story_graph_node(
        self, project_id: str, node_id: str, updates: dict,
    ) -> StoryGraphNodeSummary:
        s = self._load(project_id)
        node = s.get_story_graph_node(node_id)
        if node is None:
            raise StoryGraphNodeNotFound(node_id)
        filtered = {k: v for k, v in updates.items() if v is not None}
        if "title" in filtered and not str(filtered["title"]).strip():
            raise BadRequest("Node title is required.")
        if "linked_character_ids" in filtered:
            for cid in filtered["linked_character_ids"]:
                if s.get_character(cid) is None:
                    raise CharacterNotFound(cid)
        if "legacy_plot_thread_id" in filtered and filtered["legacy_plot_thread_id"]:
            if s.get_plot_thread(filtered["legacy_plot_thread_id"]) is None:
                raise PlotThreadNotFound(filtered["legacy_plot_thread_id"])
        if filtered:
            s.update_story_graph_node(node_id, filtered)
            s.save_state()
            node = s.get_story_graph_node(node_id)
        return self._story_graph_node_summary(node)

    def delete_story_graph_node(self, project_id: str, node_id: str) -> None:
        s = self._load(project_id)
        if s.get_story_graph_node(node_id) is None:
            raise StoryGraphNodeNotFound(node_id)
        s.delete_story_graph_node(node_id)
        s.save_state()

    def get_eligible_graph_nodes(
        self, project_id: str, chapter_number: int,
    ) -> EligibleGraphNodesResult:
        s = self._load(project_id)
        if chapter_number < 1:
            raise BadRequest("Chapter number must be at least 1.")
        brief = s.get_chapter_brief(chapter_number)
        in_effect = list(brief.active_node_ids or []) if brief else []
        eligible_nodes = eligible_graph_nodes(s, chapter_number)
        eligible_ids = {n.id for n in eligible_nodes}
        out_of_range = [
            node for node in s.story_graph_nodes.values()
            if node.id not in eligible_ids
        ]
        return EligibleGraphNodesResult(
            chapter_number=chapter_number,
            eligible=[self._story_graph_node_summary(n) for n in eligible_nodes],
            in_effect_ids=in_effect,
            out_of_range=[self._story_graph_node_summary(n) for n in out_of_range],
        )

    def pin_story_graph_node(
        self,
        project_id: str,
        node_id: str,
        chapter_number: int,
        *,
        pinned: bool = True,
    ) -> StoryGraphNodeSummary:
        s = self._load(project_id)
        node = s.get_story_graph_node(node_id)
        if node is None:
            raise StoryGraphNodeNotFound(node_id)
        if chapter_number < 1:
            raise BadRequest("Chapter number must be at least 1.")
        if pinned and not node_eligible_at_chapter(node, chapter_number):
            raise BadRequest(
                f"Node '{node_id}' is not eligible at chapter {chapter_number}.",
            )
        sync_brief_active_from_pin(s, node_id, chapter_number, pinned=pinned)
        s.save_state()
        return self._story_graph_node_summary(s.get_story_graph_node(node_id))

    def list_chapter_beats(self, project_id: str, chapter_number: int) -> list[ChapterBeatSummary]:
        s = self._load(project_id)
        if chapter_number < 1:
            raise BadRequest("Chapter number must be at least 1.")
        beats = s.get_chapter_beats(chapter_number)
        if not beats:
            migrated = self._lazy_migrate_chapter_beats_from_brief(s, chapter_number)
            if migrated:
                s.save_state()
                beats = migrated
        return [self._chapter_beat_summary(b) for b in beats]

    def _lazy_migrate_chapter_beats_from_brief(
        self, s: StoryState, chapter_number: int,
    ) -> list[ChapterBeat]:
        """One-time compatibility import from old brief beat strings."""
        from chapter_brief_utils import migrate_legacy_brief_beats_to_chapter_beats  # noqa: WPS433

        brief = s.get_chapter_brief(chapter_number)
        if brief is None:
            return []
        return migrate_legacy_brief_beats_to_chapter_beats(s, chapter_number, brief)

    def create_chapter_beat(
        self,
        project_id: str,
        chapter_number: int,
        title: str,
        summary: str = "",
        status: str = "planned",
        linked_node_ids: list[str] | None = None,
        sort_order: int | None = None,
    ) -> ChapterBeatSummary:
        s = self._load(project_id)
        if chapter_number < 1:
            raise BadRequest("Chapter number must be at least 1.")
        if not title.strip():
            raise BadRequest("Beat title is required.")
        if status not in {"planned", "landed"}:
            raise BadRequest("status must be planned or landed")
        for nid in linked_node_ids or []:
            if s.get_story_graph_node(nid) is None:
                raise StoryGraphNodeNotFound(nid)
        beats = s.get_chapter_beats(chapter_number)
        order = sort_order if sort_order is not None else len(beats)
        beat = ChapterBeat(
            id=new_chapter_beat_id(s, chapter_number),
            title=title.strip(),
            summary=summary.strip(),
            sort_order=order,
            status=status,
            linked_node_ids=list(linked_node_ids or []),
        )
        s.add_chapter_beat(chapter_number, beat)
        s.save_state()
        return self._chapter_beat_summary(beat)

    def update_chapter_beat(
        self, project_id: str, chapter_number: int, beat_id: str, updates: dict,
    ) -> ChapterBeatSummary:
        s = self._load(project_id)
        if chapter_number < 1:
            raise BadRequest("Chapter number must be at least 1.")
        filtered = {k: v for k, v in updates.items() if v is not None}
        if "title" in filtered and not str(filtered["title"]).strip():
            raise BadRequest("Beat title is required.")
        if "status" in filtered and filtered["status"] not in {"planned", "landed"}:
            raise BadRequest("status must be planned or landed")
        if "linked_node_ids" in filtered:
            for nid in filtered["linked_node_ids"]:
                if s.get_story_graph_node(nid) is None:
                    raise StoryGraphNodeNotFound(nid)
        beat = s.update_chapter_beat(chapter_number, beat_id, filtered)
        if beat is None:
            raise ChapterBeatNotFound(beat_id)
        s.save_state()
        return self._chapter_beat_summary(beat)

    def delete_chapter_beat(self, project_id: str, chapter_number: int, beat_id: str) -> None:
        s = self._load(project_id)
        if chapter_number < 1:
            raise BadRequest("Chapter number must be at least 1.")
        if not s.delete_chapter_beat(chapter_number, beat_id):
            raise ChapterBeatNotFound(beat_id)
        s.save_state()

    def reorder_chapter_beats(
        self, project_id: str, chapter_number: int, ordered_ids: list[str],
    ) -> list[ChapterBeatSummary]:
        s = self._load(project_id)
        if chapter_number < 1:
            raise BadRequest("Chapter number must be at least 1.")
        if not ordered_ids:
            raise BadRequest("ordered_ids must not be empty.")
        beats = s.get_chapter_beats(chapter_number)
        known = {b.id for b in beats}
        if not all(bid in known for bid in ordered_ids):
            raise ChapterBeatNotFound(ordered_ids[0])
        reordered = s.reorder_chapter_beats(chapter_number, ordered_ids)
        s.save_state()
        return [self._chapter_beat_summary(b) for b in reordered]

    def set_chapter_beats(
        self, project_id: str, chapter_number: int, beats: list[dict],
    ) -> list[ChapterBeatSummary]:
        s = self._load(project_id)
        if chapter_number < 1:
            raise BadRequest("Chapter number must be at least 1.")
        parsed: list[ChapterBeat] = []
        for i, row in enumerate(beats):
            title = (row.get("title") or "").strip()
            if not title:
                raise BadRequest("Each beat requires a title.")
            status = (row.get("status") or "planned").strip()
            if status not in {"planned", "landed"}:
                raise BadRequest("status must be planned or landed")
            linked = list(row.get("linked_node_ids") or [])
            for nid in linked:
                if s.get_story_graph_node(nid) is None:
                    raise StoryGraphNodeNotFound(nid)
            beat_id = (row.get("id") or "").strip() or new_chapter_beat_id(s, chapter_number)
            parsed.append(
                ChapterBeat(
                    id=beat_id,
                    title=title,
                    summary=(row.get("summary") or "").strip(),
                    sort_order=int(row.get("sort_order", i)),
                    status=status,
                    linked_node_ids=linked,
                ),
            )
        saved = s.set_chapter_beats(chapter_number, parsed)
        s.save_state()
        return [self._chapter_beat_summary(b) for b in saved]

    def _story_graph_edge_summary(self, edge: StoryGraphEdge) -> StoryGraphEdgeSummary:
        return StoryGraphEdgeSummary(**edge.to_dict())

    def list_story_graph_edges(self, project_id: str) -> list[StoryGraphEdgeSummary]:
        s = self._load(project_id)
        edges = sorted(s.story_graph_edges.values(), key=lambda e: (e.kind, e.id))
        return [self._story_graph_edge_summary(e) for e in edges]

    def create_story_graph_edge(
        self,
        project_id: str,
        source_id: str,
        target_id: str,
        kind: str = "relates",
        label: str = "",
    ) -> StoryGraphEdgeSummary:
        s = self._load(project_id)
        if not source_id.strip() or not target_id.strip():
            raise BadRequest("source_id and target_id are required.")
        if kind == "character_relationship":
            if s.get_character(source_id) is None:
                raise CharacterNotFound(source_id)
            if s.get_character(target_id) is None:
                raise CharacterNotFound(target_id)
        else:
            if s.get_story_graph_node(source_id) is None:
                raise StoryGraphNodeNotFound(source_id)
            if s.get_story_graph_node(target_id) is None:
                raise StoryGraphNodeNotFound(target_id)
        n = len(s.story_graph_edges) + 1
        eid = f"graph_edge_{n:03d}"
        while eid in s.story_graph_edges:
            n += 1
            eid = f"graph_edge_{n:03d}"
        edge = StoryGraphEdge(
            id=eid,
            source_id=source_id.strip(),
            target_id=target_id.strip(),
            kind=kind.strip() or "relates",
            label=label.strip(),
        )
        s.add_story_graph_edge(edge)
        s.save_state()
        return self._story_graph_edge_summary(edge)

    def update_story_graph_edge(
        self, project_id: str, edge_id: str, updates: dict,
    ) -> StoryGraphEdgeSummary:
        s = self._load(project_id)
        edge = s.get_story_graph_edge(edge_id)
        if edge is None:
            raise StoryGraphEdgeNotFound(edge_id)
        filtered = {k: v for k, v in updates.items() if v is not None}
        kind = filtered.get("kind", edge.kind)
        src = filtered.get("source_id", edge.source_id)
        tgt = filtered.get("target_id", edge.target_id)
        if kind == "character_relationship":
            if s.get_character(src) is None:
                raise CharacterNotFound(src)
            if s.get_character(tgt) is None:
                raise CharacterNotFound(tgt)
        else:
            if s.get_story_graph_node(src) is None:
                raise StoryGraphNodeNotFound(src)
            if s.get_story_graph_node(tgt) is None:
                raise StoryGraphNodeNotFound(tgt)
        if filtered:
            s.update_story_graph_edge(edge_id, filtered)
            s.save_state()
            edge = s.get_story_graph_edge(edge_id)
        return self._story_graph_edge_summary(edge)

    def delete_story_graph_edge(self, project_id: str, edge_id: str) -> None:
        s = self._load(project_id)
        if s.get_story_graph_edge(edge_id) is None:
            raise StoryGraphEdgeNotFound(edge_id)
        s.delete_story_graph_edge(edge_id)
        s.save_state()

    def migrate_story_graph(self, project_id: str, *, force: bool = False) -> StoryGraphMigrateResult:
        s = self._load(project_id)
        result = s.migrate_story_graph_from_plot_threads(force=force)
        if not result.get("skipped"):
            s.save_state()
        return StoryGraphMigrateResult(
            nodes_created=int(result.get("nodes_created", 0)),
            edges_created=int(result.get("edges_created", 0)),
            skipped=bool(result.get("skipped")),
        )

    def _graph_group_to_model(self, g) -> GraphDuplicateGroupModel:
        from api.models import GraphDuplicateMember  # noqa: E402

        return GraphDuplicateGroupModel(
            confidence=g.confidence,
            reason=g.reason,
            suggested_keep_id=g.suggested_keep_id,
            members=[GraphDuplicateMember(**m) for m in g.members],
        )

    def get_graph_duplicates(self, project_id: str) -> GraphDuplicatesReport:
        from graph_dedup import find_graph_duplicate_groups  # noqa: E402

        s = self._load(project_id)
        groups = find_graph_duplicate_groups(s)
        return GraphDuplicatesReport(
            groups=[self._graph_group_to_model(g) for g in groups],
            source="heuristic",
        )

    def merge_graph_duplicates(
        self, project_id: str, keep_id: str, merge_ids: list[str], *, title_override: str = "",
    ) -> GraphAutoDedupeResult:
        from graph_dedup import merge_graph_nodes  # noqa: E402

        s = self._load(project_id)
        merge_ids = [m for m in merge_ids if m != keep_id]
        if not merge_ids:
            raise BadRequest("Nothing to merge.")
        if s.get_story_graph_node(keep_id) is None:
            raise StoryGraphNodeNotFound(keep_id)
        for mid in merge_ids:
            if s.get_story_graph_node(mid) is None:
                raise StoryGraphNodeNotFound(mid)
        try:
            log = merge_graph_nodes(s, keep_id, merge_ids, title_override=title_override)
        except ValueError as e:
            raise BadRequest(str(e)) from e
        s.save_state()
        keep_label = s.story_graph_nodes[keep_id].title if keep_id in s.story_graph_nodes else ""
        return GraphAutoDedupeResult(merged=len(merge_ids), log=log, keep_label=keep_label)

    def auto_resolve_graph_duplicates(self, project_id: str) -> GraphAutoDedupeResult:
        from graph_dedup import auto_resolve_graph_duplicates  # noqa: E402

        s = self._load(project_id)
        before = len(s.story_graph_nodes)
        log = auto_resolve_graph_duplicates(s)
        merged = before - len(s.story_graph_nodes)
        if log:
            s.save_state()
        keep_label = ""
        if merged and s.story_graph_nodes:
            keep_label = next(iter(s.story_graph_nodes.values())).title
        return GraphAutoDedupeResult(merged=merged, log=log, keep_label=keep_label)

    def _chapter_brief_summary(self, brief: ChapterBrief) -> ChapterBriefSummary:
        return ChapterBriefSummary(**brief.to_dict())

    @staticmethod
    def _chapter_brief_from_current_fields(chapter_number: int, data: dict) -> ChapterBrief:
        try:
            target_word_count = max(0, int(data.get("target_word_count") or 0))
        except (TypeError, ValueError):
            raise BadRequest("target_word_count must be a non-negative integer") from None
        return ChapterBrief(
            chapter_number=chapter_number,
            pov_character_id=(data.get("pov_character_id") or "").strip(),
            pov_mode=(data.get("pov_mode") or "").strip(),
            tone=(data.get("tone") or "").strip(),
            tense=(data.get("tense") or "").strip(),
            prose_style=(data.get("prose_style") or "").strip(),
            vocabulary_level=(data.get("vocabulary_level") or "").strip(),
            style_notes=(data.get("style_notes") or "").strip(),
            target_word_count=target_word_count,
            active_character_ids=list(data.get("active_character_ids") or []),
            mentioned_character_ids=list(data.get("mentioned_character_ids") or []),
            active_node_ids=list(data.get("active_node_ids") or []),
            continuity_notes=(data.get("continuity_notes") or "").strip(),
            ending_hook=(data.get("ending_hook") or "").strip(),
        )

    def get_chapter_brief(self, project_id: str, chapter_number: int) -> ChapterBriefSummary:
        from copy import deepcopy
        from story_graph import legacy_chapter_pov_character_id, legacy_chapter_target_override  # noqa: WPS433

        s = self._load(project_id)
        brief = s.get_chapter_brief(chapter_number)
        if brief is None:
            raise ChapterBriefNotFound(chapter_number)
        display = deepcopy(brief)
        if not (display.pov_character_id or "").strip():
            legacy_pov = legacy_chapter_pov_character_id(s, chapter_number)
            if legacy_pov:
                display.pov_character_id = legacy_pov
        if (display.target_word_count or 0) <= 0:
            legacy = legacy_chapter_target_override(s, chapter_number)
            if legacy > 0:
                display.target_word_count = legacy
        return self._chapter_brief_summary(display)

    _CONTEXT_PREVIEW_MODES = frozenset({"outline", "draft", "revise", "validation"})

    @staticmethod
    def _context_preview_budget(mode: str):
        from context_resolver import (  # noqa: WPS433
            BUDGET_DRAFT,
            BUDGET_OUTLINE,
            BUDGET_REVISE,
            BUDGET_VALIDATION,
        )

        return {
            "outline": BUDGET_OUTLINE,
            "draft": BUDGET_DRAFT,
            "revise": BUDGET_REVISE,
            "validation": BUDGET_VALIDATION,
        }[mode]

    @staticmethod
    def _resolved_context_section(resolved) -> ContextPreviewSection:
        return ContextPreviewSection(
            items=[
                ContextPreviewItem(
                    key=item.key,
                    label=item.label,
                    body=item.body,
                    reason=item.reason,
                    score=item.score,
                )
                for item in resolved.items
            ],
            omitted_count=resolved.omitted_count,
            omitted_labels=list(resolved.omitted_labels),
            omitted_reason=resolved.omitted_reason,
        )

    def _context_preview_hint_text(
        self,
        project_id: str,
        chapter_number: int,
        brief: ChapterBrief,
        *,
        state: StoryState | None = None,
    ) -> str:
        from chapter_brief_utils import beats_for_prompt  # noqa: WPS433

        paths = self._stage_paths(project_id, chapter_number)
        parts: list[str] = []
        outline = _read(paths["outline"])
        if outline and outline.strip():
            parts.append(outline.strip())
        try:
            found = self._timeline_text_for_generation(project_id, chapter_number, "best")
        except ChapterNotFound:
            found = None
        if found:
            parts.append(found[1].strip()[:4000])
        if state is not None:
            chapter_beats = beats_for_prompt(state, chapter_number, brief)
            if chapter_beats:
                for beat in sorted(chapter_beats, key=lambda b: (b.sort_order, b.id)):
                    title = (beat.title or "").strip()
                    summary = (beat.summary or "").strip()
                    if summary and summary != title:
                        parts.append(f"{title} {summary}")
                    elif title:
                        parts.append(title)
        notes = (brief.continuity_notes or "").strip()
        if notes:
            parts.append(notes)
        hook = (brief.ending_hook or "").strip()
        if hook:
            parts.append(hook)
        return "\n".join(parts)

    @staticmethod
    def _brief_from_preview_request(chapter_number: int, data: dict) -> ChapterBrief:
        return ProjectService._chapter_brief_from_current_fields(chapter_number, data)

    def get_chapter_context_preview(
        self,
        project_id: str,
        chapter_number: int,
        *,
        mode: str = "draft",
        brief_data: dict | None = None,
    ) -> ChapterContextPreview:
        from context_resolver import resolve_bible_context, resolve_brief_graph_context  # noqa: WPS433

        mode_key = (mode or "draft").strip().lower()
        if mode_key not in self._CONTEXT_PREVIEW_MODES:
            raise BadRequest("mode must be outline, draft, revise, or validation")
        self.ensure_chapter(project_id, chapter_number)
        s = self._load(project_id)

        if brief_data is not None:
            brief = self._brief_from_preview_request(chapter_number, brief_data)
        else:
            saved = s.get_chapter_brief(chapter_number)
            brief = saved if saved is not None else ChapterBrief(chapter_number=chapter_number)

        budget = self._context_preview_budget(mode_key)
        hint_text = self._context_preview_hint_text(project_id, chapter_number, brief, state=s)
        bible = resolve_bible_context(s, budget=budget, hint_text=hint_text)
        graph = resolve_brief_graph_context(s, brief, budget=budget, hint_text=hint_text)

        active_chars = [
            ContextPreviewCharacter(
                id=cid,
                name=character_display_name(s, cid),
            )
            for cid in (brief.active_character_ids or [])
            if (cid or "").strip()
        ]
        mentioned_ids = list(brief.mentioned_character_ids or [])
        mentioned_chars = [
            ContextPreviewCharacter(
                id=cid,
                name=character_display_name(s, cid),
            )
            for cid in mentioned_ids
            if (cid or "").strip()
        ]
        from chapter_brief_utils import beats_for_prompt  # noqa: WPS433

        beat_preview = [
            ContextPreviewBeat(
                id=beat.id,
                title=beat.title,
                status=beat.status,
                summary=beat.summary,
            )
            for beat in beats_for_prompt(s, chapter_number, brief)
        ]

        return ChapterContextPreview(
            chapter_number=chapter_number,
            mode=mode_key,
            bible=self._resolved_context_section(bible),
            graph=self._resolved_context_section(graph),
            active_characters=active_chars,
            mentioned_characters=mentioned_chars,
            beats=beat_preview,
        )

    def _generate_chapter_brief_from_materials(
        self,
        s: StoryState,
        chapter: ChapterState,
        *,
        outline: str,
        body_text: str,
        source_label: str,
        max_beats: int | None,
        beat_importance_threshold: int = 4,
        current_brief: ChapterBrief | None = None,
        require_scored_beats: bool = False,
    ) -> ChapterBriefSummary:
        chapter_number = chapter.number
        from chapter_brief_utils import (  # noqa: WPS433
            infer_cast_from_text,
            merge_cast_ids,
            migrate_legacy_brief_beats_to_chapter_beats,
            replace_planned_beats,
        )

        combined = f"{outline}\n\n{body_text}".strip()
        if not combined:
            raise BadRequest("No outline, final, revised, or draft text found for this chapter.")

        saved_brief = s.get_chapter_brief(chapter_number)
        existing_brief = current_brief if current_brief is not None else saved_brief
        prefer_current_brief = current_brief is not None
        explicit_pov_name = self._brief_pov_character_name_from_text(combined)
        if explicit_pov_name and not (existing_brief and (existing_brief.pov_character_id or "").strip()):
            self._ensure_brief_pov_character(s, explicit_pov_name, chapter_number)
        pov_name = explicit_pov_name or chapter.pov_character or ""
        if existing_brief and (existing_brief.pov_character_id or "").strip():
            pov_name = character_display_name(s, existing_brief.pov_character_id)

        mentioned_ids, active_ids = infer_cast_from_text(s, combined, pov_name)
        ai_active_ids = self._brief_character_ids_from_section(
            s,
            combined,
            {"characters present", "characters_present", "present characters", "active characters"},
        )
        ai_mentioned_ids = self._brief_character_ids_from_section(
            s,
            combined,
            {"characters mentioned", "characters_mentioned", "mentioned characters"},
        )
        active_ids = merge_cast_ids(active_ids, ai_active_ids)
        mentioned_ids = merge_cast_ids(mentioned_ids, ai_mentioned_ids)
        pov_id = ""
        if existing_brief and (existing_brief.pov_character_id or "").strip():
            pov_id = existing_brief.pov_character_id
        elif explicit_pov_name:
            pov_id = self._brief_character_id_by_name(s, explicit_pov_name)
        elif chapter.pov_character:
            for cid, char in s.characters.items():
                if char.full_name.lower() == chapter.pov_character.lower():
                    pov_id = cid
                    break
        if not pov_id and active_ids:
            pov_id = active_ids[0]
        if pov_id and pov_id not in active_ids:
            active_ids.append(pov_id)
        if pov_id and pov_id not in active_ids and body_text:
            char = s.characters.get(pov_id)
            if char:
                from mention_updates import _detect_explicit_presence  # noqa: WPS433

                if _detect_explicit_presence(char.full_name, combined, pov_name):
                    active_ids.append(pov_id)

        active_ids, mentioned_ids = self._dedupe_brief_cast_ids(s, active_ids, mentioned_ids)

        beat_strings = self._brief_beats_from_text(
            outline or body_text,
            max_beats=max_beats,
            beat_importance_threshold=beat_importance_threshold,
            require_scored_beats=require_scored_beats,
        )
        active_nodes = self._brief_graph_nodes_for_text(
            s,
            combined,
            active_ids,
            beat_strings,
            chapter_number=chapter_number,
        )
        ending_hook = self._brief_ending_hook(outline) or self._brief_ending_hook(body_text)
        notes = self._brief_continuity_notes(chapter, source_label, active_nodes, s)
        source_notes = self._brief_continuity_notes_from_text(combined)
        if source_notes:
            notes = f"{source_notes} {notes}".strip()
        style_fields = self._brief_style_fields_for_generation(
            s,
            existing_brief,
            combined,
            fingerprint_text=body_text or outline,
            prefer_brief=prefer_current_brief,
        )
        target_word_count = self._brief_target_word_count_for_generation(
            s,
            chapter,
            existing_brief,
            combined,
            source_word_count=len(body_text.split()),
            prefer_brief=prefer_current_brief,
        )

        if saved_brief:
            migrate_legacy_brief_beats_to_chapter_beats(s, chapter_number, saved_brief)

        merged_beats = replace_planned_beats(s, chapter_number, beat_strings)
        s.set_chapter_beats(chapter_number, merged_beats)
        s.save_state()

        return ChapterBriefSummary(
            chapter_number=chapter_number,
            pov_character_id=pov_id,
            target_word_count=target_word_count,
            mentioned_character_ids=mentioned_ids,
            active_character_ids=active_ids,
            active_node_ids=active_nodes[:12],
            continuity_notes=notes,
            ending_hook=ending_hook,
            **style_fields,
        )

    def generate_chapter_brief(
        self,
        project_id: str,
        chapter_number: int,
        *,
        source: str = "best",
        max_beats: int | None = None,
        beat_importance_threshold: int | None = 4,
        current_brief: dict | None = None,
    ) -> ChapterBriefSummary:
        s = self._load(project_id)
        chapter = s.chapters.get(chapter_number)
        if chapter is None:
            raise ChapterNotFound(chapter_number)
        max_beats = self._normalize_brief_max_beats(max_beats)
        beat_importance_threshold = self._normalize_brief_importance_threshold(
            beat_importance_threshold,
        )
        found = self._timeline_text_for_generation(project_id, chapter_number, source)
        outline = _read(self._stage_paths(project_id, chapter_number)["outline"]) or ""
        body_text = found[1] if found else ""
        source_label = found[0] if found else "outline"
        current = (
            self._chapter_brief_from_current_fields(chapter_number, current_brief)
            if current_brief is not None
            else None
        )
        return self._generate_chapter_brief_from_materials(
            s,
            chapter,
            outline=outline,
            body_text=body_text,
            source_label=source_label,
            max_beats=max_beats,
            beat_importance_threshold=beat_importance_threshold,
            current_brief=current,
        )

    @staticmethod
    def _ai_chapter_brief_prompt(
        chapter_number: int,
        *,
        title: str,
        source_label: str,
        source_text: str,
        existing_outline: str,
        max_beats: int | None,
        beat_importance_threshold: int = 4,
    ) -> str:
        outline_block = ""
        if existing_outline.strip():
            outline_block = f"""
## Existing outline or notes (context only)

```markdown
{existing_outline.strip()}
```
"""
        beat_limit_instruction = (
            f"After applying the importance threshold, list at most {max_beats} beats. "
            "`max_beats`/count is a cap, not a target; do not add lower-importance beats to reach it."
            if max_beats
            else "List every beat that meets the importance threshold; do not pad to a target count or stop at an arbitrary count."
        )
        return f"""# CHAPTER BRIEF GENERATION — Chapter {chapter_number}

You are the **Archivist**. Read the chapter text below and produce an author-facing
chapter brief that captures what actually happens and what should guide later planning.

- **Chapter title:** {title or "Untitled"}
- **Source stage:** {source_label}
- **Word count:** {len(source_text.split())}

Rules:
- Use only facts supported by the supplied chapter material.
- Generate from prose even when there is no saved outline.
- `Characters_Present` means directly on-page: POV, speaking, acting, reacting,
  moving, addressed, or actively participating.
- `Characters_Mentioned` means referenced while absent. Do not put the same
  character in both fields; present takes precedence.
- Beats are chapter-local planned/summary beats for the beat board, not Story Bible canon.
- Score each candidate beat on a 0-5 integer importance scale and include only beats with
  importance score >= {beat_importance_threshold}.
- Importance scale: 5 = chapter-defining turn, transformation, reveal, irreversible
  decision, or main obstacle shift; 4 = consequential scene-level beat that changes a
  goal, access, danger, relationship, or next action; 3 = meaningful local action or
  characterization but not required later; 2 = texture, mood, repeated attempt, or minor
  observation; 1 = incidental; 0 = not a beat.
- Include only consequential beats: turning points, decisions, discoveries/reveals,
  conflicts, relationship/status changes, setup/payoff moments, and irreversible actions.
- Skip travel, blocking, atmosphere, repeated micro-actions, metadata, and style notes unless
  they change story state.
- If a request provides a limit, `max_beats`/count is a cap, not a target.
- Use scored beat lines in this format: `1. 5 | Alice makes the irreversible choice.`
- Keep continuity notes brief and useful for later chapters.
- `Style Notes` must be a reusable prose style fingerprint for drafting another chapter in
  the same voice. Describe sentence cadence, paragraph density, diction/register, imagery,
  dialogue vs. interiority balance, punctuation/rhythm, and POV distance. Do not summarize
  plot, copy distinctive phrases, or include story facts.

{outline_block}
## Chapter material ({source_label})

```markdown
{source_text}
```

## Output contract

Return exactly one `[CHAPTER_BRIEF]` block. Do not add a preface, explanation,
Markdown fence, or commentary outside the block. The `## Beats` section is mandatory;
if no beat meets the threshold, write no beat lines under that heading.

```
[CHAPTER_BRIEF]
POV Character: <full name or blank>
POV Mode: <first person | third limited | third omniscient | multiple | blank>
Tone: <short tone>
Tense: <past | present | blank>
Prose Style: <short style>
Vocabulary Level: <simple | moderate | elevated | blank>
Style Notes: <prose style fingerprint for reproducing this chapter's voice>
Target Word Count: <number or blank>
Characters_Present:
- <full name>
Characters_Mentioned:
- <full name>
## Beats
1. <importance score 0-5> | <beat summary>
2. ...
## Continuity Notes
- <note>
## Ending Hook
<how the chapter ends>
[/CHAPTER_BRIEF]
```

{beat_limit_instruction} Every beat line must match `N. S | summary`, where `S`
is an integer importance score from 0 to 5.
"""

    def generate_chapter_brief_ai(
        self,
        project_id: str,
        chapter_number: int,
        *,
        source: str = "best",
        max_beats: int | None = None,
        beat_importance_threshold: int | None = 4,
        current_brief: dict | None = None,
        on_progress: Callable[[str], None] | None = None,
    ) -> ChapterBriefSummary:
        from llm_client import LLMClient, LLMError  # noqa: WPS433
        from state_parser import extract_block  # noqa: WPS433

        log = on_progress or (lambda _msg: None)
        s = self._load(project_id)
        chapter = s.chapters.get(chapter_number)
        if chapter is None:
            raise ChapterNotFound(chapter_number)
        max_beats = self._normalize_brief_max_beats(max_beats)
        beat_importance_threshold = self._normalize_brief_importance_threshold(
            beat_importance_threshold,
        )
        if source not in self._TIMELINE_SOURCES:
            raise BadRequest("source must be best, draft, revised, or final")

        found = self._timeline_text_for_generation(project_id, chapter_number, source)
        outline = _read(self._stage_paths(project_id, chapter_number)["outline"]) or ""
        if found:
            source_label, source_text = found
        elif outline.strip():
            source_label, source_text = "outline", outline
        else:
            raise BadRequest("No outline, final, revised, or draft text found for this chapter.")

        prompt = self._ai_chapter_brief_prompt(
            chapter_number,
            title=chapter.title or "",
            source_label=source_label,
            source_text=source_text,
            existing_outline=outline if found else "",
            max_beats=max_beats,
            beat_importance_threshold=beat_importance_threshold,
        )
        feedback_dir = self._project_dir(project_id) / "outputs" / "feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)
        nnn = f"{chapter_number:03d}"
        prompt_path = feedback_dir / f"chapter_{nnn}_brief_prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")

        log(f"Generating chapter {chapter_number} brief with AI ({source_label})...")
        try:
            raw = LLMClient().run_agent("archivist", prompt)
        except LLMError as exc:
            raise RuntimeError(f"Chapter brief generation failed: {exc}") from exc

        report_path = feedback_dir / f"chapter_{nnn}_brief_report.md"
        report_path.write_text(raw, encoding="utf-8")
        ai_brief = (extract_block(raw, "CHAPTER_BRIEF") or raw).strip()
        if not ai_brief:
            raise RuntimeError("Archivist returned an empty chapter brief.")

        current = (
            self._chapter_brief_from_current_fields(chapter_number, current_brief)
            if current_brief is not None
            else None
        )
        return self._generate_chapter_brief_from_materials(
            s,
            chapter,
            outline=ai_brief,
            body_text=source_text if found else "",
            source_label=f"{source_label} AI brief",
            max_beats=max_beats,
            beat_importance_threshold=beat_importance_threshold,
            current_brief=current,
            require_scored_beats=True,
        )

    def make_chapter_brief_job(
        self,
        project_id: str,
        chapter_number: int,
        *,
        source: str = "best",
        max_beats: int | None = None,
        beat_importance_threshold: int | None = 4,
        current_brief: dict | None = None,
    ):
        s = self._load(project_id)
        if chapter_number not in s.chapters:
            raise ChapterNotFound(chapter_number)
        max_beats = self._normalize_brief_max_beats(max_beats)
        beat_importance_threshold = self._normalize_brief_importance_threshold(
            beat_importance_threshold,
        )

        def fn() -> None:
            generated = self.generate_chapter_brief_ai(
                project_id,
                chapter_number,
                source=source,
                max_beats=max_beats,
                beat_importance_threshold=beat_importance_threshold,
                current_brief=current_brief,
                on_progress=_operational_log,
            )
            self.save_chapter_brief(project_id, chapter_number, generated.model_dump())

        return fn

    @staticmethod
    def _normalize_brief_max_beats(max_beats: int | None) -> int | None:
        """Return None for uncapped brief beats; positive values are explicit caller caps."""
        if max_beats is None:
            return None
        try:
            value = int(max_beats)
        except (TypeError, ValueError):
            raise BadRequest("max_beats must be omitted, null, zero, or a positive integer") from None
        if value < 0:
            raise BadRequest("max_beats must be omitted, null, zero, or a positive integer")
        return value or None

    @staticmethod
    def _normalize_brief_importance_threshold(value: int | None) -> int:
        """Normalize the AI beat importance threshold to the supported 0-5 scale."""
        if value is None:
            return 4
        try:
            threshold = int(value)
        except (TypeError, ValueError):
            raise BadRequest("beat_importance_threshold must be an integer from 0 to 5") from None
        if threshold < 0 or threshold > 5:
            raise BadRequest("beat_importance_threshold must be an integer from 0 to 5")
        return threshold

    def generate_chapter_briefs(
        self,
        project_id: str,
        *,
        source: str = "best",
        max_beats: int | None = None,
        beat_importance_threshold: int | None = 4,
        overwrite_existing: bool = False,
        use_ai: bool = False,
    ) -> GenerateChapterBriefsResult:
        s = self._load(project_id)
        max_beats = self._normalize_brief_max_beats(max_beats)
        beat_importance_threshold = self._normalize_brief_importance_threshold(
            beat_importance_threshold,
        )
        generated: list[ChapterBriefSummary] = []
        skipped: list[dict[str, str | int]] = []
        numbers = sorted(s.chapters)
        from job_progress import RollingJobProgress  # noqa: WPS433

        progress = RollingJobProgress(total=len(numbers), unit="chapter brief")
        progress.report("Preparing chapter brief batch")
        for number in numbers:
            if s.get_chapter_brief(number) is not None and not overwrite_existing:
                skipped.append({"chapter": number, "reason": "Brief already exists."})
                progress.skip(f"Skipped chapter {number}")
                continue
            try:
                progress.start(f"Generating brief for chapter {number}")
                if use_ai:
                    brief = self.generate_chapter_brief_ai(
                        project_id,
                        number,
                        source=source,
                        max_beats=max_beats,
                        beat_importance_threshold=beat_importance_threshold,
                        on_progress=_operational_log,
                    )
                else:
                    brief = self.generate_chapter_brief(
                        project_id,
                        number,
                        source=source,
                        max_beats=max_beats,
                        beat_importance_threshold=beat_importance_threshold,
                    )
                generated.append(self.save_chapter_brief(project_id, number, brief.model_dump()))
                progress.complete(f"Chapter {number} brief saved")
            except BadRequest as e:
                skipped.append({"chapter": number, "reason": str(e)})
                progress.skip(f"Skipped chapter {number}")
        progress.report("Chapter brief batch complete")
        return GenerateChapterBriefsResult(generated=generated, skipped=skipped)

    def make_chapter_briefs_job(
        self,
        project_id: str,
        *,
        source: str = "best",
        max_beats: int | None = None,
        beat_importance_threshold: int | None = 4,
        overwrite_existing: bool = False,
    ):
        self._project_dir(project_id)
        max_beats = self._normalize_brief_max_beats(max_beats)
        beat_importance_threshold = self._normalize_brief_importance_threshold(
            beat_importance_threshold,
        )

        def fn() -> None:
            self.generate_chapter_briefs(
                project_id,
                source=source,
                max_beats=max_beats,
                beat_importance_threshold=beat_importance_threshold,
                overwrite_existing=overwrite_existing,
                use_ai=True,
            )

        return fn

    def auto_title_chapter_stats(self, project_id: str) -> BatchExtractOutlineStats:
        s = self._load(project_id)
        with_prose: list[int] = []
        eligible: list[int] = []
        auto_titled: list[int] = []
        for chapter in sorted(s.chapters.values(), key=lambda row: row.number):
            if (chapter.word_count or 0) <= 0:
                continue
            number = chapter.number
            with_prose.append(number)
            source = (getattr(chapter, "title_source", "") or "").strip()
            if source != "manual":
                eligible.append(number)
            if source == "auto":
                auto_titled.append(number)
        return BatchExtractOutlineStats(
            total_with_prose=len(with_prose),
            missing_count=len(eligible),
            missing_chapters=eligible,
            secondary_count=len(auto_titled),
            secondary_chapters=auto_titled,
        )

    def generate_chapter_title(
        self,
        project_id: str,
        chapter_number: int,
        *,
        source: str = "best",
    ) -> ChapterTitleResult:
        from chapter_title_generator import ChapterTitleGenerator  # noqa: WPS433

        s = self._load(project_id)
        if chapter_number not in s.chapters:
            raise ChapterNotFound(chapter_number)
        if source not in self._TIMELINE_SOURCES:
            raise BadRequest("source must be best, draft, revised, or final")
        proj = self._project_dir(project_id)
        title = ChapterTitleGenerator(str(proj)).generate(chapter_number, source=source)
        s.update_chapter(chapter_number, {"title": title, "title_source": "auto"})
        s.save_state()
        try:
            db.ingest_project(self.root, project_id)
        except Exception:  # noqa: BLE001
            pass
        return ChapterTitleResult(chapter=chapter_number, title=title, title_source="auto")

    def generate_chapter_titles(
        self,
        project_id: str,
        *,
        source: str = "best",
        scope: str = "eligible",
    ) -> GenerateChapterTitlesResult:
        if scope not in {"eligible", "auto_only"}:
            raise BadRequest("scope must be eligible or auto_only")
        if source not in self._TIMELINE_SOURCES:
            raise BadRequest("source must be best, draft, revised, or final")
        stats = self.auto_title_chapter_stats(project_id)
        targets = stats.missing_chapters if scope == "eligible" else stats.secondary_chapters
        generated: list[ChapterTitleResult] = []
        skipped: list[dict[str, str | int]] = []
        from job_progress import RollingJobProgress  # noqa: WPS433

        progress = RollingJobProgress(total=len(targets), unit="chapter title")
        progress.report("Preparing title batch")
        for number in targets:
            chapter = self._load(project_id).chapters.get(number)
            if chapter is None:
                skipped.append({"chapter": number, "reason": "Chapter not found."})
                progress.skip(f"Skipped chapter {number}")
                continue
            title_source = (getattr(chapter, "title_source", "") or "").strip()
            if scope == "eligible" and title_source == "manual":
                skipped.append({"chapter": number, "reason": "Title was set manually."})
                progress.skip(f"Skipped chapter {number}")
                continue
            if scope == "auto_only" and title_source != "auto":
                skipped.append({"chapter": number, "reason": "Title was not auto-generated."})
                progress.skip(f"Skipped chapter {number}")
                continue
            try:
                progress.start(f"Generating title for chapter {number}")
                generated.append(
                    self.generate_chapter_title(project_id, number, source=source),
                )
                progress.complete(f"Chapter {number} title saved")
            except (BadRequest, ChapterNotFound) as exc:
                skipped.append({"chapter": number, "reason": str(exc)})
                progress.skip(f"Skipped chapter {number}")
            except (FileNotFoundError, ValueError, RuntimeError) as exc:
                skipped.append({"chapter": number, "reason": str(exc)})
                progress.skip(f"Skipped chapter {number}")
        progress.report("Title batch complete")
        return GenerateChapterTitlesResult(generated=generated, skipped=skipped)

    def make_chapter_titles_job(
        self,
        project_id: str,
        *,
        source: str = "best",
        scope: str = "eligible",
    ):
        self._project_dir(project_id)
        if scope not in {"eligible", "auto_only"}:
            raise BadRequest("scope must be eligible or auto_only")
        if source not in self._TIMELINE_SOURCES:
            raise BadRequest("source must be best, draft, revised, or final")

        def fn() -> None:
            self.generate_chapter_titles(project_id, source=source, scope=scope)

        return fn

    @staticmethod
    def _brief_graph_nodes_for_text(
        state: StoryState,
        text: str,
        active_character_ids: list[str],
        beats: list[str],
        *,
        chapter_number: int | None = None,
    ) -> list[str]:
        eligible_ids: set[str] | None = None
        if chapter_number is not None:
            eligible_ids = {node.id for node in eligible_graph_nodes(state, chapter_number)}
        haystack = f"{text}\n{' '.join(beats)}".lower()
        scored: list[tuple[int, int, str]] = []
        for node in state.story_graph_nodes.values():
            if eligible_ids is not None and node.id not in eligible_ids:
                continue
            score = 0
            title = (node.title or "").strip().lower()
            desc = (node.description or "").strip().lower()
            if title and title in haystack:
                score += 8
            title_terms = [t for t in re.split(r"\W+", title) if len(t) >= 4]
            score += min(5, sum(1 for term in title_terms if term in haystack))
            desc_terms = [t for t in re.split(r"\W+", desc) if len(t) >= 5]
            score += min(3, sum(1 for term in desc_terms if term in haystack))
            linked_hits = len(set(node.linked_character_ids or []) & set(active_character_ids))
            score += linked_hits * 3
            if node.kind in {"main", "plot_thread"} and linked_hits:
                score += 1
            if score > 0:
                scored.append((score, node.priority, node.id))
        scored.sort(key=lambda row: (-row[0], -row[1], row[2]))
        selected: list[str] = []
        selected_titles: list[str] = []
        for _, _, node_id in scored:
            node = state.story_graph_nodes.get(node_id)
            title = (node.title if node else node_id) or node_id
            if any(ProjectService._brief_story_node_titles_similar(title, seen) for seen in selected_titles):
                continue
            selected.append(node_id)
            selected_titles.append(title)
            if len(selected) >= 12:
                break
        return selected

    @staticmethod
    def _brief_label_key(label: str) -> str:
        label = re.sub(r"\*\*", "", label or "").strip().lower()
        return re.sub(r"[^a-z0-9]+", " ", label).strip()

    @staticmethod
    def _brief_clean_value(value: str) -> str:
        value = re.sub(r"\*\*", "", value or "").strip()
        value = value.strip("`\"' ")
        value = re.sub(r"\s+", " ", value)
        if value.lower() in {"", "unknown", "[unknown]", "n/a", "none"}:
            return ""
        return value

    @classmethod
    def _brief_metadata_pairs(cls, text: str) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for raw in (text or "").splitlines():
            line = raw.strip()
            if not line:
                continue
            line = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s*)", "", line).strip()
            line = re.sub(r"\*\*([^*]+?)\*\*", r"\1", line)
            if line.startswith("|") and line.endswith("|"):
                cells = [cell.strip() for cell in line.strip("|").split("|")]
                if (
                    len(cells) >= 2
                    and not re.fullmatch(r":?-{2,}:?", cells[0])
                    and cls._brief_label_key(cells[0]) not in {"field", "label", "metadata"}
                ):
                    label = cls._brief_label_key(cells[0])
                    value = cls._brief_clean_value(cells[1])
                    if label and value:
                        pairs.append((label, value))
                continue
            for part in re.split(r"\s+\|\s+", line):
                match = re.match(
                    r"^(?:#{1,6}\s*)?(?P<label>[A-Za-z][A-Za-z0-9 ()/_-]{0,64})\s*[:：—-]\s*(?P<value>.+)$",
                    part.strip(),
                )
                if not match:
                    continue
                label = cls._brief_label_key(match.group("label"))
                value = cls._brief_clean_value(match.group("value"))
                if label and value:
                    pairs.append((label, value))
        return pairs

    @classmethod
    def _brief_metadata_value(cls, text: str, labels: set[str]) -> str:
        keys = {cls._brief_label_key(label) for label in labels}
        for label, value in cls._brief_metadata_pairs(text):
            if label in keys:
                return value
        return ""

    @classmethod
    def _brief_markdown_section(cls, text: str, headings: set[str]) -> str:
        keys = {cls._brief_label_key(heading) for heading in headings}
        capture = False
        lines: list[str] = []
        for raw in (text or "").splitlines():
            heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", raw)
            if heading:
                key = cls._brief_label_key(heading.group(1))
                if capture:
                    break
                if key in keys:
                    capture = True
                    continue
            if capture:
                lines.append(raw)
        if not lines:
            return ""
        cleaned: list[str] = []
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("```"):
                continue
            line = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s*)", "", line).strip()
            line = cls._brief_clean_value(line)
            if line:
                cleaned.append(line)
        return " ".join(cleaned)

    @staticmethod
    def _brief_normalize_pov_mode(value: str) -> str:
        lower = re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()
        if not lower:
            return ""
        compact = lower.replace(" ", "_")
        valid = {
            "first_person",
            "second_person",
            "third_limited",
            "third_omniscient",
            "third_objective",
            "multiple_pov",
            "epistolary",
            "stream_of_consciousness",
            "other",
        }
        if compact in valid:
            return compact
        if "stream" in lower and "conscious" in lower:
            return "stream_of_consciousness"
        if "epistolary" in lower or "document" in lower or "letter" in lower:
            return "epistolary"
        if "multiple" in lower or "multi pov" in lower:
            return "multiple_pov"
        if "second" in lower:
            return "second_person"
        if "first" in lower:
            return "first_person"
        if "third" in lower and "omniscient" in lower:
            return "third_omniscient"
        if "third" in lower and "objective" in lower:
            return "third_objective"
        if "third" in lower and ("limited" in lower or "close" in lower or "deep" in lower):
            return "third_limited"
        if "third" in lower:
            return "third_limited"
        return ""

    @classmethod
    def _brief_pov_character_name_from_text(cls, text: str) -> str:
        raw = cls._brief_metadata_value(
            text,
            {"pov character", "viewpoint character", "viewpoint", "pov"},
        )
        if not raw:
            return ""
        candidate = re.split(
            r"\s*(?:\(|,|;|\||/|\s[-—]\s)\s*(?:first|second|third|multiple|multi|epistolary|stream|objective)\b",
            raw,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()
        if not candidate or cls._brief_normalize_pov_mode(candidate):
            return ""
        return candidate

    @staticmethod
    def _brief_character_name_key(name: str) -> str:
        """Normalize character names for matching AI output to existing cast."""
        folded = unicodedata.normalize("NFKD", name or "")
        ascii_text = "".join(ch for ch in folded if not unicodedata.combining(ch))
        ascii_text = re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()
        return re.sub(r"\s+", " ", ascii_text)

    @staticmethod
    def _brief_character_names_similar(left: str, right: str) -> bool:
        left = ProjectService._brief_character_name_key(left)
        right = ProjectService._brief_character_name_key(right)
        if not left or not right:
            return False
        if left == right:
            return True
        if min(len(left), len(right)) >= 6 and (left in right or right in left):
            return True
        return SequenceMatcher(None, left, right).ratio() >= 0.92

    @staticmethod
    def _brief_story_node_titles_similar(left: str, right: str) -> bool:
        left = ProjectService._brief_character_name_key(left)
        right = ProjectService._brief_character_name_key(right)
        if not left or not right:
            return False
        if left == right:
            return True
        if min(len(left), len(right)) >= 6 and (left in right or right in left):
            return True
        return SequenceMatcher(None, left, right).ratio() >= 0.86

    @classmethod
    def _brief_character_ids_from_section(
        cls,
        state: StoryState,
        text: str,
        headings: set[str],
    ) -> list[str]:
        keys = {cls._brief_label_key(h) for h in headings}
        capture = False
        ids: list[str] = []
        seen: set[str] = set()
        for raw in (text or "").splitlines():
            line = raw.strip()
            if not line:
                continue
            label = re.match(r"^(?P<label>[A-Za-z][A-Za-z0-9 _-]{1,64})\s*:\s*$", line)
            heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", raw)
            if label or heading:
                current = cls._brief_label_key(label.group("label") if label else heading.group(1))
                if capture and current not in keys:
                    break
                capture = current in keys
                continue
            if not capture:
                continue
            name = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s*)", "", line).strip()
            name = cls._brief_clean_value(name)
            cid = cls._brief_character_id_by_name(state, name)
            if cid and cid not in seen:
                ids.append(cid)
                seen.add(cid)
        return ids

    @classmethod
    def _dedupe_brief_cast_ids(
        cls,
        state: StoryState,
        active_ids: list[str],
        mentioned_ids: list[str],
    ) -> tuple[list[str], list[str]]:
        kept: list[str] = []

        def is_duplicate(candidate_id: str) -> bool:
            candidate = state.characters.get(candidate_id)
            if candidate is None:
                return candidate_id in kept
            candidate_names = [candidate.full_name, *getattr(candidate, "aliases", [])]
            for kept_id in kept:
                if kept_id == candidate_id:
                    return True
                kept_char = state.characters.get(kept_id)
                if kept_char is None:
                    continue
                kept_names = [kept_char.full_name, *getattr(kept_char, "aliases", [])]
                if any(
                    cls._brief_character_names_similar(candidate_name, kept_name)
                    for candidate_name in candidate_names
                    for kept_name in kept_names
                ):
                    return True
            return False

        active: list[str] = []
        for cid in active_ids or []:
            cid = (cid or "").strip()
            if cid and not is_duplicate(cid):
                active.append(cid)
                kept.append(cid)

        mentioned: list[str] = []
        for cid in mentioned_ids or []:
            cid = (cid or "").strip()
            if cid and not is_duplicate(cid):
                mentioned.append(cid)
                kept.append(cid)
        return active, mentioned

    @staticmethod
    def _brief_character_id_by_name(state: StoryState, name: str) -> str:
        target = ProjectService._brief_character_name_key(name)
        if not target:
            return ""
        for cid, char in state.characters.items():
            names = [
                ProjectService._brief_character_name_key(n)
                for n in char.all_names()
                if (n or "").strip()
            ]
            if target in names:
                return cid
        for cid, char in state.characters.items():
            names = [
                ProjectService._brief_character_name_key(n)
                for n in char.all_names()
                if (n or "").strip()
            ]
            if any(ProjectService._brief_character_names_similar(target, n) for n in names):
                return cid
        return ""

    @classmethod
    def _ensure_brief_pov_character(cls, state: StoryState, name: str, chapter_number: int) -> str:
        existing_id = cls._brief_character_id_by_name(state, name)
        if existing_id:
            return existing_id

        base = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_") or "pov"
        cid = f"char_{base}"
        suffix = 2
        while cid in state.characters:
            cid = f"char_{base}_{suffix}"
            suffix += 1
        state.add_character(
            Character(
                id=cid,
                full_name=name.strip(),
                role="supporting",
                notes=f"Created from chapter {chapter_number} POV metadata.",
                last_appearance_chapter=chapter_number,
            ),
        )
        return cid

    @classmethod
    def _brief_int_from_text(cls, value: str) -> int:
        match = re.search(r"(\d+(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k|thousand|words?)?", value or "", re.I)
        if not match:
            return 0
        number = float(match.group(1).replace(",", ""))
        suffix = (match.group(2) or "").lower()
        if suffix in {"k", "thousand"}:
            number *= 1000
        return max(0, int(round(number)))

    @classmethod
    def _brief_target_word_count_for_generation(
        cls,
        state: StoryState,
        chapter,
        existing_brief: ChapterBrief | None,
        text: str,
        *,
        source_word_count: int = 0,
        prefer_brief: bool = False,
    ) -> int:
        if existing_brief is not None and (existing_brief.target_word_count or 0) > 0:
            existing_target = int(existing_brief.target_word_count)
        else:
            existing_target = 0
        if prefer_brief and existing_target > 0:
            return existing_target
        source_value = cls._brief_metadata_value(
            text,
            {
                "desired word count",
                "desired length",
                "target length",
                "target length words",
                "target word count",
                "word count target",
                "word count target words",
                "target words",
                "chapter length",
                "length target",
                "word count",
                "word count target length",
                "word count goal",
                "wordcount target",
                "wordcount",
                "word_count_target",
                "length",
            },
        ) or cls._brief_markdown_section(
            text,
            {"target length", "target word count", "word count", "chapter length"},
        )
        parsed = cls._brief_int_from_text(source_value)
        if parsed > 0:
            return parsed
        if existing_target > 0:
            return existing_target
        if source_word_count > 0:
            return source_word_count
        chapter_target = int(getattr(chapter, "target_word_count", 0) or 0)
        if chapter_target > 0:
            return chapter_target
        return max(0, int(getattr(state.style_profile, "chapter_target_words", 0) or 0))

    @staticmethod
    def _brief_style_fingerprint_from_text(text: str) -> str:
        """Aggregate prose-shape guidance for recreating style without quoting content."""
        raw = (text or "").strip()
        if not raw:
            return ""
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", raw) if p.strip()]
        sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+", raw)
            if s.strip()
        ]
        words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", raw)
        if len(words) < 8:
            return ""

        def avg(values: list[int]) -> float:
            return sum(values) / max(1, len(values))

        avg_sentence = avg([len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", s)) for s in sentences])
        avg_paragraph = avg([len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", p)) for p in paragraphs])
        avg_word_len = avg([len(w) for w in words])
        quoted_words = len(re.findall(r'"[^"]+"|“[^”]+”', raw))
        quote_ratio = quoted_words / max(1, len(sentences))
        question_count = raw.count("?")
        exclamation_count = raw.count("!")
        semicolon_count = raw.count(";")
        dash_count = raw.count("—") + raw.count("--")
        interior_markers = len(re.findall(
            r"\b(thought|felt|knew|wondered|remembered|wanted|feared|hoped|realized|noticed)\b",
            raw,
            flags=re.IGNORECASE,
        ))

        sentence_label = "short, clipped" if avg_sentence < 11 else "long, flowing" if avg_sentence > 22 else "mid-length"
        paragraph_label = "brief" if avg_paragraph < 55 else "dense" if avg_paragraph > 130 else "moderate"
        diction_label = "plain" if avg_word_len < 4.6 else "elevated" if avg_word_len > 5.6 else "moderate"
        dialogue_label = "dialogue-forward" if quote_ratio >= 0.45 else "dialogue-light"
        interiority_label = "interior/reflective" if interior_markers >= max(2, len(sentences) // 4) else "externally focused"
        punctuation_bits: list[str] = []
        if question_count:
            punctuation_bits.append("questions")
        if exclamation_count:
            punctuation_bits.append("exclamations")
        if semicolon_count:
            punctuation_bits.append("semicolons")
        if dash_count:
            punctuation_bits.append("dashes")
        punctuation = ", ".join(punctuation_bits) if punctuation_bits else "clean sentence-ending punctuation"

        return (
            "Style fingerprint: "
            f"{sentence_label} sentence cadence (avg {avg_sentence:.0f} words); "
            f"{paragraph_label} paragraphing (avg {avg_paragraph:.0f} words); "
            f"{dialogue_label}; {interiority_label}; "
            f"{diction_label} diction; punctuation rhythm uses {punctuation}."
        )

    @classmethod
    def _brief_style_fields_for_generation(
        cls,
        state: StoryState,
        existing_brief: ChapterBrief | None,
        text: str,
        *,
        fingerprint_text: str = "",
        prefer_brief: bool = False,
    ) -> dict[str, str]:
        style_profile = state.style_profile
        pov_mode_source = cls._brief_metadata_value(
            text,
            {
                "narrative perspective",
                "narrative point of view",
                "perspective",
                "point of view",
                "pov mode",
            },
        ) or cls._brief_metadata_value(text, {"pov"})
        source = {
            "pov_mode": cls._brief_normalize_pov_mode(pov_mode_source),
            "tone": cls._brief_metadata_value(text, {"tone", "emotional tone"}),
            "tense": cls._brief_metadata_value(text, {"tense", "narrative tense"}),
            "prose_style": cls._brief_metadata_value(text, {"prose style", "writing style", "style"}),
            "vocabulary_level": cls._brief_metadata_value(
                text,
                {"vocabulary level", "vocabulary register", "vocabulary"},
            ),
            "style_notes": "",
        }
        style_notes = [
            cls._brief_markdown_section(text, {"style notes", "writing style notes", "voice notes"}),
            cls._brief_metadata_value(text, {"style notes", "writing style notes", "voice notes"}),
            cls._brief_markdown_section(text, {"vocabulary description", "vocabulary notes"}),
            cls._brief_metadata_value(text, {"vocabulary description", "vocabulary notes"}),
        ]
        source["style_notes"] = " ".join(dict.fromkeys(note for note in style_notes if note))
        if not source["style_notes"]:
            source["style_notes"] = cls._brief_style_fingerprint_from_text(fingerprint_text)

        defaults = {
            "pov_mode": (getattr(style_profile, "point_of_view", "") or "").strip(),
            "tone": (getattr(style_profile, "tone", "") or "").strip(),
            "tense": (getattr(style_profile, "tense", "") or "").strip(),
            "prose_style": (getattr(style_profile, "prose_style", "") or "").strip(),
            "vocabulary_level": (getattr(style_profile, "vocabulary_level", "") or "").strip(),
            "style_notes": (getattr(style_profile, "description", "") or "").strip(),
        }
        fields = dict.fromkeys(defaults, "")
        for key in fields:
            source_value = source.get(key, "").strip()
            existing_value = (getattr(existing_brief, key, "") if existing_brief is not None else "") or ""
            existing_value = existing_value.strip()
            if prefer_brief:
                fields[key] = existing_value or source_value or defaults[key]
            else:
                fields[key] = source_value or existing_value or defaults[key]
        return fields

    @classmethod
    def _brief_continuity_notes_from_text(cls, text: str) -> str:
        return cls._brief_markdown_section(text, {"continuity notes", "continuity"})

    @staticmethod
    def _brief_continuity_notes(chapter, source_label: str, active_node_ids: list[str], state: StoryState) -> str:
        notes = [
            f"Generated from chapter {chapter.number} {source_label} text; review before outlining or drafting.",
        ]
        if getattr(chapter, "location", ""):
            notes.append(f"Location: {chapter.location}.")
        if getattr(chapter, "time", ""):
            notes.append(f"Time: {chapter.time}.")
        if active_node_ids:
            names = [
                state.story_graph_nodes[nid].title
                for nid in active_node_ids[:5]
                if nid in state.story_graph_nodes
            ]
            if names:
                notes.append(f"Mapped story graph focus: {', '.join(names)}.")
        return " ".join(notes)

    @staticmethod
    def _is_pov_metadata_beat(line: str) -> bool:
        """Skip outline/metadata lines whose POV is already stored on the chapter brief."""
        text = re.sub(r"\*\*", "", line.strip()).strip()
        if not text:
            return False
        lower = text.lower()
        if re.match(
            r"^(?:pov|point of view|narrative perspective|viewpoint character)\s*[:—\-]",
            lower,
        ):
            return True
        # Header rows like "POV: Alice | Source: outline"
        if re.match(r"^pov\s*:", lower):
            return True
        return False

    @staticmethod
    def _is_important_prose_beat(line: str) -> bool:
        """Heuristic for fallback prose extraction when no explicit beat list exists."""
        text = re.sub(r"\*\*", "", (line or "")).strip()
        if not text or ProjectService._is_pov_metadata_beat(text):
            return False
        if re.match(r"^[A-Za-z][A-Za-z0-9 ()/_-]{0,64}\s*[:：]", text):
            return False
        words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text)
        if len(words) < 5:
            return False
        return bool(re.search(
            r"\b("
            r"accepts?|arrives?|attacks?|betrays?|breaks?|captures?|changes?|chooses?|"
            r"confesses?|confronts?|decides?|discovers?|escapes?|fails?|finds?|forces?|"
            r"frees?|gives?|learns?|leaves?|loses?|meets?|opens?|promises?|realizes?|"
            r"refuses?|reveals?|saves?|sees?|starts?|stops?|takes?|threatens?|turns?|wins?"
            r")\b",
            text,
            flags=re.IGNORECASE,
        ))

    @staticmethod
    def _parse_brief_beat_importance(line: str) -> tuple[str, int | None, bool]:
        """Return clean beat title, optional score, and whether score metadata was malformed."""
        text = (line or "").strip()
        prefix_score = re.match(r"^(?P<score>\d+)\s*\|\s*(?P<title>.+)$", text)
        if prefix_score:
            raw_score = prefix_score.group("score")
            title = prefix_score.group("title").strip()
            if re.fullmatch(r"[0-5]", raw_score):
                return title, int(raw_score), False
            return title, None, True

        suffix_score = re.match(
            r"^(?P<title>.+?)\s*\|\s*(?:importance_score|importance|score)\s*[:=]\s*(?P<score>[^|]+?)\s*$",
            text,
            flags=re.IGNORECASE,
        )
        if suffix_score:
            raw_score = suffix_score.group("score").strip()
            title = suffix_score.group("title").strip()
            if re.fullmatch(r"[0-5]", raw_score):
                return title, int(raw_score), False
            return title, None, True

        leading_score = re.match(
            r"^(?:importance_score|importance|score)\s*[:=]\s*(?P<score>[^|]+?)\s*\|\s*(?P<title>.+)$",
            text,
            flags=re.IGNORECASE,
        )
        if leading_score:
            raw_score = leading_score.group("score").strip()
            title = leading_score.group("title").strip()
            if re.fullmatch(r"[0-5]", raw_score):
                return title, int(raw_score), False
            return title, None, True

        return text, None, False

    @staticmethod
    def _brief_beats_from_text(
        text: str,
        *,
        max_beats: int | None,
        beat_importance_threshold: int = 4,
        require_scored_beats: bool = False,
    ) -> list[str]:
        source_lines = list((text or "").splitlines())
        scoped: list[str] = []
        capturing = False
        found_beats_section = False
        for raw in source_lines:
            heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", raw)
            if heading:
                key = ProjectService._brief_label_key(heading.group(1))
                if key in {"beats", "chapter beats", "planned beats", "plot points", "planned plot points"}:
                    capturing = True
                    found_beats_section = True
                    continue
                if capturing:
                    break
            elif capturing:
                scoped.append(raw)
        lines = []
        list_line_pattern = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s*)")
        for raw in scoped if found_beats_section else source_lines:
            if not found_beats_section and not list_line_pattern.match(raw):
                continue
            line = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s*)", "", raw).strip()
            if len(line.split()) >= 3 and not ProjectService._is_pov_metadata_beat(line):
                lines.append(line)
        if not lines:
            lines = [
                s.strip()
                for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
                if ProjectService._is_important_prose_beat(s)
            ]
        out: list[str] = []
        seen: set[str] = set()
        skipped_labels = {
            "chapter goal",
            "characters threads",
            "characters and threads",
            "continuity",
            "continuity notes",
            "ending hook",
            "hook",
            "prose style",
            "style notes",
            "target word count",
            "tone",
            "vocabulary level",
        }
        for line in lines:
            if line.startswith("#"):
                continue
            label = ProjectService._brief_label_key(line.rstrip(":"))
            if label in skipped_labels:
                continue
            if ProjectService._is_pov_metadata_beat(line):
                continue
            line, score, malformed_score = ProjectService._parse_brief_beat_importance(line)
            if malformed_score:
                continue
            if score is None:
                if require_scored_beats:
                    continue
            elif score < beat_importance_threshold:
                continue
            line = line.strip()
            if not line:
                continue
            if len(line) > 180:
                line = line[:177].rstrip() + "..."
            key = re.sub(r"\s+", " ", re.sub(r"\*\*", "", line).strip().lower()).strip(" .!?:;—-")
            if key and key not in seen:
                out.append(line)
                seen.add(key)
            if max_beats is not None and len(out) >= max_beats:
                break
        return out

    @staticmethod
    def _brief_ending_hook(text: str) -> str:
        section = ProjectService._brief_markdown_section(text, {"ending hook", "hook"})
        if section:
            hook = section
            return hook if len(hook) <= 180 else hook[:177].rstrip() + "..."
        sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text).strip())
            if len(s.split()) >= 5
        ]
        if not sentences:
            return ""
        hook = sentences[-1]
        return hook if len(hook) <= 180 else hook[:177].rstrip() + "..."

    def save_chapter_brief(
        self, project_id: str, chapter_number: int, data: dict,
    ) -> ChapterBriefSummary:
        s = self._load(project_id)
        if chapter_number < 1:
            raise BadRequest("Chapter number must be at least 1.")
        pov = (data.get("pov_character_id") or "").strip()
        if pov and s.get_character(pov) is None:
            raise CharacterNotFound(pov)
        active_chars = list(data.get("active_character_ids") or [])
        for cid in active_chars:
            if s.get_character(cid) is None:
                raise CharacterNotFound(cid)
        mentioned_chars = list(data.get("mentioned_character_ids") or [])
        for cid in mentioned_chars:
            if s.get_character(cid) is None:
                raise CharacterNotFound(cid)
        active_nodes = list(data.get("active_node_ids") or [])
        for nid in active_nodes:
            if s.get_story_graph_node(nid) is None:
                raise StoryGraphNodeNotFound(nid)
        brief = self._chapter_brief_from_current_fields(chapter_number, data)
        from prompt_context import normalize_brief_for_storage  # noqa: WPS433
        from story_graph import apply_brief_pov_to_chapter, apply_brief_target_to_chapter  # noqa: WPS433

        normalize_brief_characters(brief)
        invalid_nodes = validate_brief_active_nodes(s, brief)
        if invalid_nodes:
            raise BadRequest(
                f"active_node_ids not eligible at chapter {chapter_number}: "
                + ", ".join(invalid_nodes),
            )
        chapter = s.chapters.get(chapter_number)
        normalize_brief_for_storage(brief, s)
        s.set_chapter_brief(brief)
        sync_chapter_pins_for_brief(s, brief)
        if chapter is not None:
            apply_brief_pov_to_chapter(s, chapter, brief)
            apply_brief_target_to_chapter(s, chapter, brief)
        s.save_state()
        return self._chapter_brief_summary(brief)

    def generate_chapter_beat_candidates(
        self,
        project_id: str,
        chapter_number: int,
        *,
        source: str = "best",
        count: int = 10,
    ) -> ChapterBeatCandidatesResult:
        from chapter_beat_extractor import ChapterBeatExtractor  # noqa: WPS433

        s = self._load(project_id)
        if chapter_number not in s.chapters:
            raise ChapterNotFound(chapter_number)
        if count < 1 or count > 20:
            raise BadRequest("count must be between 1 and 20")
        if source not in {"best", "draft", "revised", "final"}:
            raise BadRequest("source must be best, draft, revised, or final")

        project_path = str(self._project_dir(project_id))
        extractor = ChapterBeatExtractor(project_path)
        try:
            parsed, source_used, _report = extractor.extract(
                chapter_number,
                source=source,
                count=count,
            )
        except FileNotFoundError as exc:
            raise BadRequest(str(exc)) from exc
        except ValueError as exc:
            raise BadRequest(str(exc)) from exc
        except RuntimeError as exc:
            raise BadRequest(str(exc)) from exc

        candidates = [
            ChapterBeatCandidate(
                rank=item.rank,
                beat=item.beat,
                significance=item.significance,
                involved_characters=list(item.involved_characters),
                story_relevance=item.story_relevance,
                category=item.category,
            )
            for item in parsed
        ]
        return ChapterBeatCandidatesResult(
            chapter_number=chapter_number,
            source_used=source_used,
            candidates=candidates,
        )

    def _chapter_beat_candidates_preview_path(self, project_id: str, chapter_number: int) -> Path:
        return (
            self._project_dir(project_id)
            / "outputs"
            / "feedback"
            / f"chapter_{chapter_number:03d}_beat_candidates_preview.json"
        )

    def get_chapter_beat_candidates_preview(
        self,
        project_id: str,
        chapter_number: int,
    ) -> ChapterBeatCandidatesResult | None:
        s = self._load(project_id)
        if chapter_number not in s.chapters:
            raise ChapterNotFound(chapter_number)
        path = self._chapter_beat_candidates_preview_path(project_id, chapter_number)
        if not path.exists():
            return None
        return ChapterBeatCandidatesResult(**json.loads(path.read_text(encoding="utf-8")))

    def discard_chapter_beat_candidates_preview(self, project_id: str, chapter_number: int) -> None:
        s = self._load(project_id)
        if chapter_number not in s.chapters:
            raise ChapterNotFound(chapter_number)
        path = self._chapter_beat_candidates_preview_path(project_id, chapter_number)
        if path.exists():
            path.unlink()

    def make_chapter_beat_candidates_job(
        self,
        project_id: str,
        chapter_number: int,
        *,
        source: str = "best",
        count: int = 10,
    ):
        s = self._load(project_id)
        if chapter_number not in s.chapters:
            raise ChapterNotFound(chapter_number)
        if count < 1 or count > 20:
            raise BadRequest("count must be between 1 and 20")
        if source not in {"best", "draft", "revised", "final"}:
            raise BadRequest("source must be best, draft, revised, or final")

        def fn() -> None:
            result = self.generate_chapter_beat_candidates(
                project_id,
                chapter_number,
                source=source,
                count=count,
            )
            path = self._chapter_beat_candidates_preview_path(project_id, chapter_number)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result.model_dump(), indent=2), encoding="utf-8")

        return fn

    def apply_chapter_beat_candidates(
        self,
        project_id: str,
        chapter_number: int,
        body: ApplyChapterBeatCandidatesRequest,
    ) -> ChapterBriefSummary:
        from chapter_brief_utils import _next_beat_id, migrate_legacy_brief_beats_to_chapter_beats  # noqa: WPS433

        s = self._load(project_id)
        if chapter_number not in s.chapters:
            raise ChapterNotFound(chapter_number)

        selected = [beat.strip() for beat in (body.selected_beats or []) if (beat or "").strip()]
        if not selected:
            raise BadRequest("selected_beats must include at least one beat")

        mode = (body.mode or "append").strip().lower()
        if mode not in {"append", "replace"}:
            raise BadRequest("mode must be append or replace")

        existing = s.get_chapter_brief(chapter_number)
        if existing is None:
            existing = ChapterBrief(chapter_number=chapter_number)
        migrated = migrate_legacy_brief_beats_to_chapter_beats(s, chapter_number, existing)

        if mode == "replace":
            chapter_beats = [b for b in migrated if b.status != "landed"]
        else:
            chapter_beats = list(migrated)

        known_landed = {
            ((b.title or "").strip().lower(), (b.summary or "").strip().lower())
            for b in chapter_beats
            if (b.status or "").strip() == "landed"
        }
        known_ids = {b.id for b in chapter_beats}
        sort_order = max((b.sort_order for b in chapter_beats), default=-1) + 1
        for beat_text in selected:
            key = (beat_text.lower(), beat_text.lower())
            if key in known_landed:
                continue
            chapter_beats.append(
                ChapterBeat(
                    id=_next_beat_id(chapter_number, known_ids),
                    title=beat_text,
                    summary=beat_text,
                    sort_order=sort_order,
                    status="landed",
                )
            )
            known_landed.add(key)
            sort_order += 1

        s.set_chapter_beats(chapter_number, chapter_beats)
        existing.required_beats = []
        existing.landed_beats = []
        s.set_chapter_brief(existing)
        s.save_state()
        self.discard_chapter_beat_candidates_preview(project_id, chapter_number)
        return self._chapter_brief_summary(existing)

    def delete_chapter_brief(self, project_id: str, chapter_number: int) -> None:
        s = self._load(project_id)
        if s.get_chapter_brief(chapter_number) is None:
            raise ChapterBriefNotFound(chapter_number)
        s.delete_chapter_brief(chapter_number)
        s.save_state()

    # ----- Mention-aware story intelligence

    _MENTION_SOURCES = frozenset({"draft", "revised", "final"})

    def _chapter_source_text(self, project_id: str, number: int, source: str) -> str:
        if source not in self._MENTION_SOURCES:
            raise BadRequest("source must be draft, revised, or final")
        self.ensure_chapter(project_id, number)
        p = self._stage_paths(project_id, number)
        text = _read(p[source])
        if not text or not text.strip():
            raise BadRequest(f"No {source} text for chapter {number}")
        return text

    def analyze_mentions(self, project_id: str, number: int, source: str = "revised") -> dict:
        from continuity_engine import (  # noqa: WPS433
            check_mention_state_conflicts,
            check_unresolved_mentions,
        )
        from mention_updates import suggest_conservative_updates  # noqa: WPS433

        text = self._chapter_source_text(project_id, number, source)
        s = self._load(project_id)
        warnings = check_unresolved_mentions(s, text, number)
        warnings.extend(check_mention_state_conflicts(s, text, number))
        bundle = suggest_conservative_updates(s, number, text, source=source)
        return {
            "chapter_number": number,
            "source": source,
            "warnings": [w.to_dict() for w in warnings],
            "suggestions": [asdict(s) for s in bundle.suggestions],
            "generated_at": bundle.generated_at,
        }

    def make_mention_suggest_job(
        self,
        project_id: str,
        number: int,
        *,
        source: str = "revised",
        use_llm: bool = False,
    ) -> Callable[[], None]:
        text = self._chapter_source_text(project_id, number, source)
        proj_path = str(self._project_dir(project_id))

        def fn() -> None:
            from mention_updates import (  # noqa: WPS433
                MentionSuggestionsStore,
                suggest_conservative_updates,
                suggest_with_llm,
            )
            from state_manager import StoryState  # noqa: WPS433

            state = StoryState(proj_path)
            if use_llm:
                bundle = suggest_with_llm(state, number, text, source=source)
            else:
                bundle = suggest_conservative_updates(state, number, text, source=source)
            MentionSuggestionsStore(proj_path).save(bundle)
            print(
                f"Mention suggestions ready: {len(bundle.suggestions)} item(s)",
                flush=True,
            )

        return fn

    def suggest_mentions_sync(
        self,
        project_id: str,
        number: int,
        *,
        source: str = "revised",
    ) -> dict:
        from mention_updates import MentionSuggestionsStore, suggest_conservative_updates  # noqa: WPS433

        text = self._chapter_source_text(project_id, number, source)
        s = self._load(project_id)
        bundle = suggest_conservative_updates(s, number, text, source=source)
        MentionSuggestionsStore(str(self._project_dir(project_id))).save(bundle)
        return bundle.to_dict()

    def get_mention_suggestions(self, project_id: str, number: int) -> dict | None:
        from mention_updates import MentionSuggestionsStore  # noqa: WPS433

        self.ensure_chapter(project_id, number)
        bundle = MentionSuggestionsStore(str(self._project_dir(project_id))).load(number)
        return bundle.to_dict() if bundle else None

    def apply_mention_edits(self, project_id: str, number: int, edits: list[dict]) -> dict:
        from mention_updates import apply_reviewed_edits  # noqa: WPS433

        if not edits:
            raise BadRequest("No edits to apply.")
        self.ensure_chapter(project_id, number)
        s = self._load(project_id)
        try:
            log = apply_reviewed_edits(s, number, edits)
        except ValueError as e:
            raise BadRequest(str(e)) from e
        if log:
            s.save_state()
        return {"log": log, "applied": len(log)}

