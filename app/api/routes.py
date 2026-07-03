import os
import subprocess
import sys
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from fastapi import Response
from fastapi.responses import PlainTextResponse, FileResponse

from . import db
from .jobs import runner
from .models import (
    AddCharacter, AddComment, ChapterDetail, ChapterPasteResult, ChapterSequenceResult,
    ChapterStages, ChapterStructureReport, ChapterSummary,
    CharacterDetail, CharacterGeneratePreview, CharacterSummary, Comment, CreateChapter,
    CreatePlotThread, CreateProject, DuplicateChapter, GenerateCharacter, InsertChapter, MergeChapter,
    CreateSnapshot, DraftResult, DraftSave, OutlineResult, OutlineSave, RevisedResult, RevisedSave, FinalResult, FinalSave, UnfinalizeResult, ImportStory, ImportEbook, EbookParsePreview, Job,
    PasteChapter, PlotThreadSummary, ProjectDetail, ProjectSummary, ReassignChapter,
    ReassignChapterResult, RunPhase, SnapshotMeta,
    UpdateStyleProfile, PlanOutlinePreviewRequest, PlanOutlinePreview,
    SnapshotText,     StoryBible, UpdateChapter, UpdateCharacter, UpdateComment, UpdatePlotThread,
    UpdateStoryBible, ExtractBackground, ExtractBackgroundResult,
    RegenerateChapter, RegeneratePreview, RegenerateApply, RegenerateApplyResult,
    SplitChapterRequest, SplitChapterResult,
    BoundaryAlignmentPreview, BoundaryAlignmentApply, BoundaryAlignmentApplyResult,
    RedraftFromBriefRequest, RedraftPreview, RedraftApply, RedraftApplyResult,
    DuplicateGroupModel, DuplicatesReport, EntityDedupStatus, MergeEntities, MergeResult, AutoResolveResult,
    BibleDuplicatesReport, BibleDedupeMerge, BibleAutoDedupeResult, BibleDedupStatus,
    BackupsReport, BackupActionResult, CreateNamedBackup, NamedBackupMeta, ReorderPlotThreads,
    NestPlotThreads, SystemPromptSettings, AgentPromptSettings, UpdateAgentPromptSetting,
    LlmConnectionSettings, UpdateLlmConnectionSettings, LlmConnectionTestResult, LlmModelListResult,
    LlmQueueEntry, RunningJobEntry, LlmQueueSettings, LlmQueueSettingsUpdate, LlmQueueFlushResult, LlmQueueReorder, LlmQueueMove,
    RestartResult, JobCancelResult,
    PlotPanelIssuesReport, ResolvePlotPanelIssue, PlotPanelResolveResult, PlotPanelAutoResolveResult,
    GeneratePlotThread, PlotGeneratePreview,
    MentionAnalysis, MentionSuggestRequest, MentionApplyRequest, MentionApplyResult,
    TimelineEventSummary, CreateTimelineEvent, UpdateTimelineEvent,
    GenerateTimelineRequest, TimelineGenerationResult, ApplyTimelineGenerationRequest,
    ApplyTimelineGenerationResult, DeleteTimelineEventsResult,
    StoryGraphNodeSummary, CreateStoryGraphNode, UpdateStoryGraphNode,
    StoryGraphEdgeSummary, CreateStoryGraphEdge, UpdateStoryGraphEdge,
    StoryGraphMigrateRequest, StoryGraphMigrateResult,
    ReviewableChangeModel, GenerateGraphSuggestionsRequest, GenerateGraphSuggestionsResult,
    MineAllRequest,
    PinStoryGraphNodeRequest, EligibleGraphNodesResult,
    ChapterBeatSummary, CreateChapterBeat, UpdateChapterBeat,
    ReorderChapterBeats, SetChapterBeats,
    GraphDuplicatesReport, GraphDedupeMerge, GraphAutoDedupeResult,
    ChapterBriefSummary, SaveChapterBrief, GenerateChapterBriefRequest,
    GenerateChapterBriefsRequest, GenerateChapterBriefsResult,
    GenerateChapterTitlesRequest, GenerateChapterTitlesResult,
    BatchExtractRequest,
    BatchExtractOutlineStats,
    BatchExtractOutlineStats,
    ChapterContextPreview, ChapterContextPreviewRequest,
    GenerateChapterBeatCandidatesRequest, ChapterBeatCandidatesResult,
    ApplyChapterBeatCandidatesRequest,
    ChapterMinePreview, ChapterMinePreviewSummary, ApplyChapterMinePreviewResult,
    ResearchSparkSummary, CreateResearchSpark, UpdateResearchSpark,
    ProjectMapSummary, ProjectMapDetail, CreateProjectMap, UpdateProjectMap,
    MapPinSummary, CreateMapPin, UpdateMapPin,
    StashedProjectSummary,
)
from .services import (
    BadRequest, ChapterNotFound, CharacterNotFound, NoSourceArtifact, NothingToUnfinalize,
    PlotThreadNotFound, ProjectNotFound, ProjectService, TimelineEventNotFound,
    StoryGraphNodeNotFound, StoryGraphEdgeNotFound, ChapterBriefNotFound,
    ChapterBeatNotFound, ReviewableChangeNotFound,
    ResearchSparkNotFound, ProjectMapNotFound, MapPinNotFound,
)

router = APIRouter(prefix="/api")
_CORE = Path(__file__).resolve().parent.parent / "core"


def get_service() -> ProjectService:
    root = Path(os.environ.get("NOVEL_OS_PROJECTS_DIR", "./projects"))
    return ProjectService(root)


@router.get("/health")
def health() -> dict:
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from version import APP_VERSION  # noqa: WPS433
    return {"status": "ok", "version": APP_VERSION}


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(svc: ProjectService = Depends(get_service)):
    return svc.list_projects()


@router.post("/projects", response_model=ProjectSummary, status_code=201)
def create_project(body: CreateProject, svc: ProjectService = Depends(get_service)):
    try:
        return svc.create_project(body.title, body.genre, body.author)
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_project(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return Response(status_code=204)


@router.patch("/projects/{project_id}/style", response_model=ProjectDetail)
def update_project_style(project_id: str, body: UpdateStyleProfile, svc: ProjectService = Depends(get_service)):
    try:
        return svc.update_style_profile(project_id, body.model_dump())
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/outline/preview", response_model=PlanOutlinePreview)
def preview_plan_outline(project_id: str, body: PlanOutlinePreviewRequest,
                         svc: ProjectService = Depends(get_service)):
    try:
        return svc.preview_plan_outline(project_id, body.chapters, body.words)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/outline/apply", response_model=PlanOutlinePreview)
def apply_plan_outline(project_id: str, body: PlanOutlinePreviewRequest,
                       svc: ProjectService = Depends(get_service)):
    try:
        return svc.apply_plan_outline(project_id, body.chapters, body.words)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/characters", response_model=list[CharacterSummary], status_code=201)
def add_character(project_id: str, body: AddCharacter, svc: ProjectService = Depends(get_service)):
    try:
        return svc.add_character(project_id, body.name, body.role)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/run", response_model=Job, status_code=202)
def run_phase(project_id: str, body: RunPhase, svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_phase_job(project_id, body.stage, body.params)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit(body.stage, fn, meta={"project_id": project_id})
    return runner.get(job_id)


@router.post("/import", response_model=Job, status_code=202)
def import_story(body: ImportStory, svc: ProjectService = Depends(get_service)):
    """Import .txt chapters from a local folder into a new or existing project."""
    try:
        fn, project_id = svc.make_import_job(
            body.chapters_dir,
            title=body.title,
            genre=body.genre,
            author=body.author,
            project_id=body.project_id,
            synthesize=body.synthesize,
            no_extract=body.no_extract,
            from_chapter=body.from_chapter,
            to_chapter=body.to_chapter,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{body.project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("import", fn, meta={"project_id": project_id})
    return runner.get(job_id)


@router.post("/import/ebook/preview", response_model=EbookParsePreview)
async def preview_import_ebook(
    request: Request,
    svc: ProjectService = Depends(get_service),
):
    """Upload an ebook file and return detected title, chapters, and split strategy."""
    content = await request.body()
    filename = (request.headers.get("X-Filename") or "upload.txt").strip()
    try:
        return svc.preview_ebook_upload(content, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import/ebook", response_model=Job, status_code=202)
def import_ebook(body: ImportEbook, svc: ProjectService = Depends(get_service)):
    """Import a staged upload or local path into a new or existing project."""
    try:
        fn, project_id = svc.make_ebook_import_job(
            body.source_path,
            upload_id=body.upload_id,
            title=body.title,
            genre=body.genre,
            author=body.author,
            project_id=body.project_id,
            split_strategy=body.split_strategy,
            parts=body.parts,
            synthesize=body.synthesize,
            no_extract=body.no_extract,
            from_chapter=body.from_chapter,
            to_chapter=body.to_chapter,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{body.project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("import", fn, meta={"project_id": project_id})
    return runner.get(job_id)


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str):
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/cancel", response_model=JobCancelResult)
def cancel_job(job_id: str):
    result = runner.cancel(job_id)
    if result["cancelled_jobs"] <= 0:
        raise HTTPException(status_code=404, detail="Job not found or not running")
    job = result["job"]
    assert job is not None
    return JobCancelResult(
        job_id=job["job_id"],
        kind=job.get("kind", ""),
        status=job.get("status", "error"),
        error=job.get("error"),
        started_at=job.get("started_at"),
        finished_at=job.get("finished_at"),
        project_id=job.get("project_id"),
        cancelled_jobs=int(result["cancelled_jobs"]),
        batch_id=result.get("batch_id"),
        batch_size=int(result.get("batch_size") or result["cancelled_jobs"]),
    )


@router.get("/projects/{project_id}/export", response_class=PlainTextResponse)
def export_markdown(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.export_markdown(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/export.epub")
def export_epub(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        filename, data = svc.export_epub(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(
        content=data,
        media_type="application/epub+zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/projects/{project_id}/export-package")
def export_project_package(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        filename, data = svc.export_project_package(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/projects/import-package", response_model=ProjectSummary, status_code=201)
async def import_project_package(
    request: Request,
    svc: ProjectService = Depends(get_service),
):
    content = await request.body()
    if not content:
        raise HTTPException(status_code=400, detail="Empty request body.")
    try:
        return svc.import_project_package(content)
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid zip file.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/stashed", response_model=list[StashedProjectSummary])
def list_stashed_projects(svc: ProjectService = Depends(get_service)):
    return svc.list_stashed_projects()


@router.post("/projects/{project_id}/stash", response_model=StashedProjectSummary, status_code=201)
def stash_project(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.stash_project(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stashed/{stash_id}/restore", response_model=ProjectSummary, status_code=201)
def restore_stashed_project(stash_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.restore_stashed_project(stash_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----- Tier 1: snapshots (version history) — DB-backed

def _ensure_chapter_or_404(svc: ProjectService, project_id: str, number: int):
    try:
        svc.ensure_chapter(project_id, number)
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)


@router.get("/projects/{project_id}/chapters/{number}/snapshots", response_model=list[SnapshotMeta])
def list_snapshots(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    return db.snapshots_list(project_id, number)


@router.post("/projects/{project_id}/chapters/{number}/snapshots", response_model=SnapshotMeta, status_code=201)
def create_snapshot(project_id: str, number: int, body: CreateSnapshot,
                    svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    text = svc.get_final_text(project_id, number)
    if text is None:
        raise HTTPException(status_code=409, detail="No Final to snapshot yet.")
    return db.snapshot_create(project_id, number, text, body.label, "final")


@router.get("/projects/{project_id}/chapters/{number}/snapshots/{snap_id}", response_model=SnapshotText)
def get_snapshot(project_id: str, number: int, snap_id: str,
                 svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    snap = db.snapshot_get(project_id, number, snap_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snap


@router.post("/projects/{project_id}/chapters/{number}/snapshots/{snap_id}/restore", response_model=FinalResult)
def restore_snapshot(project_id: str, number: int, snap_id: str,
                     svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    snap = db.snapshot_get(project_id, number, snap_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    current = svc.get_final_text(project_id, number)
    if current is not None:
        db.snapshot_create(project_id, number, current, "Before restore", "final")
    wc = svc.save_final(project_id, number, snap.text)
    return FinalResult(final=snap.text, word_count=wc)


@router.delete("/projects/{project_id}/chapters/{number}/snapshots/{snap_id}", status_code=204)
def delete_snapshot(project_id: str, number: int, snap_id: str,
                    svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    if not db.snapshot_delete(project_id, number, snap_id):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return Response(status_code=204)


# ----- Tier 1: comments / annotations — DB-backed

def _validate_annotation_stage(stage: str) -> None:
    if stage not in db.ANNOTATION_STAGES:
        raise HTTPException(
            status_code=400,
            detail=f"stage must be one of {sorted(db.ANNOTATION_STAGES)}",
        )


def _validate_annotation_offsets(start_offset: int | None, end_offset: int | None) -> None:
    if start_offset is not None and start_offset < 0:
        raise HTTPException(status_code=400, detail="start_offset must be >= 0")
    if end_offset is not None and end_offset < 0:
        raise HTTPException(status_code=400, detail="end_offset must be >= 0")
    if start_offset is not None and end_offset is not None and end_offset < start_offset:
        raise HTTPException(status_code=400, detail="end_offset must be >= start_offset")


@router.get("/projects/{project_id}/chapters/{number}/comments", response_model=list[Comment])
def list_comments(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    return db.comments_list(project_id, number)


@router.post("/projects/{project_id}/chapters/{number}/comments", response_model=Comment, status_code=201)
def add_comment(project_id: str, number: int, body: AddComment,
                svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    if not body.body.strip():
        raise HTTPException(status_code=400, detail="Comment body is required.")
    _validate_annotation_stage(body.stage)
    _validate_annotation_offsets(body.start_offset, body.end_offset)
    return db.comment_add(
        project_id,
        number,
        body.body,
        body.quote,
        stage=body.stage,
        start_offset=body.start_offset,
        end_offset=body.end_offset,
        paragraph_hash=body.paragraph_hash,
    )


@router.patch("/projects/{project_id}/chapters/{number}/comments/{cid}", response_model=Comment)
def update_comment(project_id: str, number: int, cid: str, body: UpdateComment,
                   svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    if body.stage is not None:
        _validate_annotation_stage(body.stage)
    _validate_annotation_offsets(body.start_offset, body.end_offset)
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    c = db.comment_update(project_id, number, cid, **updates)
    if c is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    return c


@router.delete("/projects/{project_id}/chapters/{number}/comments/{cid}", status_code=204)
def delete_comment(project_id: str, number: int, cid: str,
                   svc: ProjectService = Depends(get_service)):
    _ensure_chapter_or_404(svc, project_id, number)
    if not db.comment_delete(project_id, number, cid):
        raise HTTPException(status_code=404, detail="Comment not found")
    return Response(status_code=204)


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def project_detail(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.project_detail(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/chapter-structure", response_model=ChapterStructureReport)
def validate_chapter_structure(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.validate_chapter_structure(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/chapters", response_model=list[ChapterSummary])
def list_chapters(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_chapters(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/chapters/insert", response_model=ChapterSequenceResult)
def insert_chapter(project_id: str, body: InsertChapter, svc: ProjectService = Depends(get_service)):
    try:
        return svc.insert_chapter_at(project_id, body.number, body.title)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/chapters/renumber-sequential", response_model=ChapterSequenceResult)
def renumber_chapters_sequential(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.renumber_chapters_sequential(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/chapters/{number}", response_model=ChapterDetail)
def chapter_detail(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        return svc.chapter_detail(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")


@router.delete("/projects/{project_id}/chapters/{number}", status_code=204)
def delete_chapter(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_chapter(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    return Response(status_code=204)


@router.get("/projects/{project_id}/characters", response_model=list[CharacterSummary])
def list_characters(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_characters(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.delete("/projects/{project_id}/characters/{character_id}", status_code=204)
def delete_character(project_id: str, character_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_character(project_id, character_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except CharacterNotFound:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")
    return Response(status_code=204)


@router.get("/projects/{project_id}/plot-threads", response_model=list[PlotThreadSummary])
def list_plot_threads(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_plot_threads(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.delete("/projects/{project_id}/plot-threads/{thread_id}", status_code=204)
def delete_plot_thread(project_id: str, thread_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_plot_thread(project_id, thread_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except PlotThreadNotFound:
        raise HTTPException(status_code=404, detail=f"Plot thread '{thread_id}' not found")
    return Response(status_code=204)


@router.get("/projects/{project_id}/characters/{character_id}", response_model=CharacterDetail)
def get_character(project_id: str, character_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.get_character(project_id, character_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except CharacterNotFound:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")


@router.patch("/projects/{project_id}/characters/{character_id}", response_model=CharacterDetail)
def update_character(project_id: str, character_id: str, body: UpdateCharacter,
                     svc: ProjectService = Depends(get_service)):
    try:
        return svc.update_character(project_id, character_id, body.model_dump())
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except CharacterNotFound:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")


@router.post("/projects/{project_id}/characters/{character_id}/portrait", response_model=CharacterDetail)
async def upload_character_portrait(
    project_id: str,
    character_id: str,
    request: Request,
    svc: ProjectService = Depends(get_service),
):
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    allowed = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
    if content_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Content-Type must be image/png, image/jpeg, image/webp, or image/gif",
        )
    data = await request.body()
    try:
        return svc.upload_character_portrait(project_id, character_id, data)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except CharacterNotFound:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/projects/{project_id}/characters/{character_id}/portrait", response_model=CharacterDetail)
def remove_character_portrait(
    project_id: str,
    character_id: str,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.remove_character_portrait(project_id, character_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except CharacterNotFound:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")


@router.get("/projects/{project_id}/characters/{character_id}/portrait")
def get_character_portrait(
    project_id: str,
    character_id: str,
    svc: ProjectService = Depends(get_service),
):
    try:
        path, media_type = svc.resolve_character_portrait_path(project_id, character_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except CharacterNotFound:
        raise HTTPException(status_code=404, detail=f"Character '{character_id}' not found")
    return FileResponse(path, media_type=media_type)


@router.post("/projects/{project_id}/characters/generate", response_model=Job, status_code=202)
def generate_character_profile(project_id: str, body: GenerateCharacter,
                               svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_character_generate_job(
            project_id,
            body.prompt,
            character_id=body.character_id,
            hint_name=body.hint_name,
            hint_role=body.hint_role,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except CharacterNotFound:
        raise HTTPException(status_code=404, detail=f"Character '{body.character_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit(
        "character_generate",
        fn,
        meta={"project_id": project_id, "character_id": body.character_id},
    )
    return runner.get(job_id)


@router.get("/projects/{project_id}/characters/generate/preview",
            response_model=CharacterGeneratePreview)
def get_character_generate_preview(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        preview = svc.get_character_generate_preview(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    if preview is None:
        raise HTTPException(status_code=404, detail="No character generate preview")
    return preview


@router.delete("/projects/{project_id}/characters/generate/preview", status_code=204)
def discard_character_generate_preview(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.discard_character_generate_preview(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return Response(status_code=204)


@router.put("/projects/{project_id}/plot-threads/reorder", response_model=list[PlotThreadSummary])
def reorder_plot_threads(project_id: str, body: ReorderPlotThreads,
                         svc: ProjectService = Depends(get_service)):
    try:
        return svc.reorder_plot_threads(project_id, body.ordered_ids)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/plot-threads", response_model=PlotThreadSummary, status_code=201)
def create_plot_thread(project_id: str, body: CreatePlotThread, svc: ProjectService = Depends(get_service)):
    try:
        return svc.create_plot_thread(
            project_id, body.name, body.description, body.thread_type, body.priority, body.status,
            subplots=body.subplots,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/projects/{project_id}/plot-threads/{thread_id}", response_model=PlotThreadSummary)
def update_plot_thread(project_id: str, thread_id: str, body: UpdatePlotThread,
                       svc: ProjectService = Depends(get_service)):
    try:
        return svc.update_plot_thread(project_id, thread_id, body.model_dump())
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except PlotThreadNotFound:
        raise HTTPException(status_code=404, detail=f"Plot thread '{thread_id}' not found")


@router.get("/projects/{project_id}/timeline", response_model=list[TimelineEventSummary])
def list_timeline_events(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_timeline_events(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/timeline", response_model=TimelineEventSummary, status_code=201)
def create_timeline_event(project_id: str, body: CreateTimelineEvent,
                          svc: ProjectService = Depends(get_service)):
    try:
        return svc.create_timeline_event(
            project_id,
            description=body.description,
            chapter=body.chapter,
            day=body.day,
            time=body.time,
            location=body.location,
            characters_present=body.characters_present,
            event_type=body.event_type,
            significance=body.significance,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CharacterNotFound as e:
        raise HTTPException(status_code=404, detail=f"Character '{e.args[0]}' not found")


@router.post("/projects/{project_id}/timeline/generate", response_model=TimelineGenerationResult)
def generate_timeline_from_chapters(project_id: str, body: GenerateTimelineRequest,
                                    svc: ProjectService = Depends(get_service)):
    try:
        return svc.generate_timeline_from_chapters(
            project_id,
            chapters=body.chapters,
            source=body.source,
            max_events_per_chapter=body.max_events_per_chapter,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound as e:
        raise HTTPException(status_code=404, detail=f"Chapter '{e.args[0]}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/projects/{project_id}/timeline/generated-events",
    response_model=ApplyTimelineGenerationResult,
)
def apply_generated_timeline_events(project_id: str, body: ApplyTimelineGenerationRequest,
                                    svc: ProjectService = Depends(get_service)):
    try:
        return ApplyTimelineGenerationResult(
            created=svc.apply_generated_timeline_events(
                project_id,
                [event.model_dump() for event in body.events],
            ),
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound as e:
        raise HTTPException(status_code=404, detail=f"Chapter '{e.args[0]}' not found")
    except CharacterNotFound as e:
        raise HTTPException(status_code=404, detail=f"Character '{e.args[0]}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/projects/{project_id}/timeline/{event_id}", response_model=TimelineEventSummary)
def update_timeline_event(project_id: str, event_id: str, body: UpdateTimelineEvent,
                          svc: ProjectService = Depends(get_service)):
    try:
        return svc.update_timeline_event(project_id, event_id, body.model_dump())
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except TimelineEventNotFound:
        raise HTTPException(status_code=404, detail=f"Timeline event '{event_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CharacterNotFound as e:
        raise HTTPException(status_code=404, detail=f"Character '{e.args[0]}' not found")


@router.delete("/projects/{project_id}/timeline", response_model=DeleteTimelineEventsResult)
def delete_all_timeline_events(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return DeleteTimelineEventsResult(deleted=svc.delete_all_timeline_events(project_id))
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.delete("/projects/{project_id}/timeline/{event_id}", status_code=204)
def delete_timeline_event(project_id: str, event_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_timeline_event(project_id, event_id)
        return Response(status_code=204)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except TimelineEventNotFound:
        raise HTTPException(status_code=404, detail=f"Timeline event '{event_id}' not found")


@router.get("/projects/{project_id}/reviewable-changes", response_model=list[ReviewableChangeModel])
def list_reviewable_changes(
    project_id: str,
    status: str | None = None,
    type: str | None = None,
    source: str | None = None,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.list_reviewable_changes(project_id, status=status, kind=type, source=source)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post(
    "/projects/{project_id}/reviewable-changes/generate-graph-suggestions",
    response_model=GenerateGraphSuggestionsResult,
)
def generate_graph_suggestions(
    project_id: str,
    body: GenerateGraphSuggestionsRequest,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.generate_graph_suggestions(project_id, auto_apply=body.auto_apply)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/reviewable-changes/{change_id}/apply", response_model=ReviewableChangeModel)
def apply_reviewable_change(project_id: str, change_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.apply_reviewable_change(project_id, change_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ReviewableChangeNotFound:
        raise HTTPException(status_code=404, detail=f"Reviewable change '{change_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/reviewable-changes/{change_id}/dismiss", response_model=ReviewableChangeModel)
def dismiss_reviewable_change(project_id: str, change_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.dismiss_reviewable_change(project_id, change_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ReviewableChangeNotFound:
        raise HTTPException(status_code=404, detail=f"Reviewable change '{change_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/projects/{project_id}/reviewable-changes/{change_id}/mark-reviewed",
    response_model=ReviewableChangeModel,
)
def mark_reviewable_change_reviewed(
    project_id: str,
    change_id: str,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.mark_reviewable_change_reviewed(project_id, change_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ReviewableChangeNotFound:
        raise HTTPException(status_code=404, detail=f"Reviewable change '{change_id}' not found")


@router.post("/projects/{project_id}/reviewable-changes/{change_id}/revert", response_model=ReviewableChangeModel)
def revert_reviewable_change(project_id: str, change_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.revert_reviewable_change(project_id, change_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ReviewableChangeNotFound:
        raise HTTPException(status_code=404, detail=f"Reviewable change '{change_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/mine-all", response_model=Job, status_code=202)
def mine_all(project_id: str, body: MineAllRequest, svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_mine_all_job(
            project_id,
            mode=body.mode,
            auto_apply=body.auto_apply,
            chapters=body.chapters,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("mine-all", fn, meta={"project_id": project_id})
    return runner.get(job_id)


@router.get("/projects/{project_id}/story-graph/nodes", response_model=list[StoryGraphNodeSummary])
def list_story_graph_nodes(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_story_graph_nodes(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/story-graph/nodes", response_model=StoryGraphNodeSummary, status_code=201)
def create_story_graph_node(project_id: str, body: CreateStoryGraphNode,
                            svc: ProjectService = Depends(get_service)):
    try:
        return svc.create_story_graph_node(
            project_id,
            title=body.title,
            kind=body.kind,
            description=body.description,
            status=body.status,
            priority=body.priority,
            linked_character_ids=body.linked_character_ids,
            legacy_plot_thread_id=body.legacy_plot_thread_id,
            sort_order=body.sort_order,
            start_chapter=body.start_chapter,
            resolution_chapter=body.resolution_chapter,
            layout=body.layout.model_dump() if body.layout else None,
            act=body.act,
            chapter_number=body.chapter_number,
            assign_to_brief=body.assign_to_brief,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CharacterNotFound as e:
        raise HTTPException(status_code=404, detail=f"Character '{e.args[0]}' not found")
    except PlotThreadNotFound as e:
        raise HTTPException(status_code=404, detail=f"Plot thread '{e.args[0]}' not found")


@router.patch("/projects/{project_id}/story-graph/nodes/{node_id}", response_model=StoryGraphNodeSummary)
def update_story_graph_node(project_id: str, node_id: str, body: UpdateStoryGraphNode,
                            svc: ProjectService = Depends(get_service)):
    try:
        return svc.update_story_graph_node(project_id, node_id, body.model_dump())
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except StoryGraphNodeNotFound:
        raise HTTPException(status_code=404, detail=f"Story graph node '{node_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CharacterNotFound as e:
        raise HTTPException(status_code=404, detail=f"Character '{e.args[0]}' not found")
    except PlotThreadNotFound as e:
        raise HTTPException(status_code=404, detail=f"Plot thread '{e.args[0]}' not found")


@router.delete("/projects/{project_id}/story-graph/nodes/{node_id}", status_code=204)
def delete_story_graph_node(project_id: str, node_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_story_graph_node(project_id, node_id)
        return Response(status_code=204)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except StoryGraphNodeNotFound:
        raise HTTPException(status_code=404, detail=f"Story graph node '{node_id}' not found")


@router.get(
    "/projects/{project_id}/chapters/{chapter_number}/story-graph/eligible-nodes",
    response_model=EligibleGraphNodesResult,
)
def get_eligible_graph_nodes(
    project_id: str,
    chapter_number: int,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.get_eligible_graph_nodes(project_id, chapter_number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/projects/{project_id}/story-graph/nodes/{node_id}/pin",
    response_model=StoryGraphNodeSummary,
)
def pin_story_graph_node(
    project_id: str,
    node_id: str,
    body: PinStoryGraphNodeRequest,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.pin_story_graph_node(
            project_id,
            node_id,
            body.chapter_number,
            pinned=body.pinned,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except StoryGraphNodeNotFound:
        raise HTTPException(status_code=404, detail=f"Story graph node '{node_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/projects/{project_id}/chapters/{chapter_number}/beats",
    response_model=list[ChapterBeatSummary],
)
def list_chapter_beats(
    project_id: str,
    chapter_number: int,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.list_chapter_beats(project_id, chapter_number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/projects/{project_id}/chapters/{chapter_number}/beats",
    response_model=ChapterBeatSummary,
    status_code=201,
)
def create_chapter_beat(
    project_id: str,
    chapter_number: int,
    body: CreateChapterBeat,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.create_chapter_beat(
            project_id,
            chapter_number,
            title=body.title,
            summary=body.summary,
            status=body.status,
            linked_node_ids=body.linked_node_ids,
            sort_order=body.sort_order,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except StoryGraphNodeNotFound as e:
        raise HTTPException(status_code=404, detail=f"Story graph node '{e.args[0]}' not found")


@router.put(
    "/projects/{project_id}/chapters/{chapter_number}/beats",
    response_model=list[ChapterBeatSummary],
)
def set_chapter_beats(
    project_id: str,
    chapter_number: int,
    body: SetChapterBeats,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.set_chapter_beats(
            project_id,
            chapter_number,
            [b.model_dump() for b in body.beats],
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except StoryGraphNodeNotFound as e:
        raise HTTPException(status_code=404, detail=f"Story graph node '{e.args[0]}' not found")


@router.put(
    "/projects/{project_id}/chapters/{chapter_number}/beats/reorder",
    response_model=list[ChapterBeatSummary],
)
def reorder_chapter_beats(
    project_id: str,
    chapter_number: int,
    body: ReorderChapterBeats,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.reorder_chapter_beats(project_id, chapter_number, body.ordered_ids)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ChapterBeatNotFound as e:
        raise HTTPException(status_code=404, detail=f"Chapter beat '{e.args[0]}' not found")


@router.patch(
    "/projects/{project_id}/chapters/{chapter_number}/beats/{beat_id}",
    response_model=ChapterBeatSummary,
)
def update_chapter_beat(
    project_id: str,
    chapter_number: int,
    beat_id: str,
    body: UpdateChapterBeat,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.update_chapter_beat(
            project_id, chapter_number, beat_id, body.model_dump(),
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterBeatNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter beat '{beat_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except StoryGraphNodeNotFound as e:
        raise HTTPException(status_code=404, detail=f"Story graph node '{e.args[0]}' not found")


@router.delete(
    "/projects/{project_id}/chapters/{chapter_number}/beats/{beat_id}",
    status_code=204,
)
def delete_chapter_beat(
    project_id: str,
    chapter_number: int,
    beat_id: str,
    svc: ProjectService = Depends(get_service),
):
    try:
        svc.delete_chapter_beat(project_id, chapter_number, beat_id)
        return Response(status_code=204)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterBeatNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter beat '{beat_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/story-graph/edges", response_model=list[StoryGraphEdgeSummary])
def list_story_graph_edges(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_story_graph_edges(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/story-graph/edges", response_model=StoryGraphEdgeSummary, status_code=201)
def create_story_graph_edge(project_id: str, body: CreateStoryGraphEdge,
                            svc: ProjectService = Depends(get_service)):
    try:
        return svc.create_story_graph_edge(
            project_id,
            source_id=body.source_id,
            target_id=body.target_id,
            kind=body.kind,
            label=body.label,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except StoryGraphNodeNotFound as e:
        raise HTTPException(status_code=404, detail=f"Story graph node '{e.args[0]}' not found")
    except CharacterNotFound as e:
        raise HTTPException(status_code=404, detail=f"Character '{e.args[0]}' not found")


@router.patch("/projects/{project_id}/story-graph/edges/{edge_id}", response_model=StoryGraphEdgeSummary)
def update_story_graph_edge(project_id: str, edge_id: str, body: UpdateStoryGraphEdge,
                            svc: ProjectService = Depends(get_service)):
    try:
        return svc.update_story_graph_edge(project_id, edge_id, body.model_dump())
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except StoryGraphEdgeNotFound:
        raise HTTPException(status_code=404, detail=f"Story graph edge '{edge_id}' not found")
    except StoryGraphNodeNotFound as e:
        raise HTTPException(status_code=404, detail=f"Story graph node '{e.args[0]}' not found")
    except CharacterNotFound as e:
        raise HTTPException(status_code=404, detail=f"Character '{e.args[0]}' not found")


@router.delete("/projects/{project_id}/story-graph/edges/{edge_id}", status_code=204)
def delete_story_graph_edge(project_id: str, edge_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_story_graph_edge(project_id, edge_id)
        return Response(status_code=204)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except StoryGraphEdgeNotFound:
        raise HTTPException(status_code=404, detail=f"Story graph edge '{edge_id}' not found")


@router.post("/projects/{project_id}/story-graph/migrate", response_model=StoryGraphMigrateResult)
def migrate_story_graph(project_id: str, body: StoryGraphMigrateRequest,
                        svc: ProjectService = Depends(get_service)):
    try:
        return svc.migrate_story_graph(project_id, force=body.force)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/story-graph/duplicates", response_model=GraphDuplicatesReport)
def list_graph_duplicates(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.get_graph_duplicates(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/story-graph/duplicates/merge", response_model=GraphAutoDedupeResult)
def merge_graph_duplicates(project_id: str, body: GraphDedupeMerge,
                           svc: ProjectService = Depends(get_service)):
    try:
        return svc.merge_graph_duplicates(
            project_id, body.keep_id, body.merge_ids, title_override=body.title_override,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except StoryGraphNodeNotFound as e:
        raise HTTPException(status_code=404, detail=f"Story graph node '{e.args[0]}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/story-graph/duplicates/auto-resolve", response_model=GraphAutoDedupeResult)
def auto_resolve_graph_duplicates(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.auto_resolve_graph_duplicates(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/chapters/{chapter_number}/brief", response_model=ChapterBriefSummary)
def get_chapter_brief(project_id: str, chapter_number: int, svc: ProjectService = Depends(get_service)):
    try:
        return svc.get_chapter_brief(project_id, chapter_number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterBriefNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter brief for chapter {chapter_number} not found")


@router.post("/projects/{project_id}/chapters/{chapter_number}/brief/generate", response_model=ChapterBriefSummary)
def generate_chapter_brief(project_id: str, chapter_number: int, body: GenerateChapterBriefRequest,
                           svc: ProjectService = Depends(get_service)):
    try:
        return svc.generate_chapter_brief(
            project_id,
            chapter_number,
            source=body.source,
            max_beats=body.max_beats,
            beat_importance_threshold=body.beat_importance_threshold,
            current_brief=body.current_brief.model_dump() if body.current_brief else None,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/projects/{project_id}/chapters/{chapter_number}/brief/generate/async",
    response_model=Job,
    status_code=202,
)
def generate_chapter_brief_async(
    project_id: str,
    chapter_number: int,
    body: GenerateChapterBriefRequest,
    svc: ProjectService = Depends(get_service),
):
    try:
        fn = svc.make_chapter_brief_job(
            project_id,
            chapter_number,
            source=body.source,
            max_beats=body.max_beats,
            beat_importance_threshold=body.beat_importance_threshold,
            current_brief=body.current_brief.model_dump() if body.current_brief else None,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit(
        "chapter_brief",
        fn,
        meta={"project_id": project_id, "chapter": chapter_number},
    )
    return runner.get(job_id)


@router.post("/projects/{project_id}/chapters/briefs/generate", response_model=GenerateChapterBriefsResult)
def generate_chapter_briefs(project_id: str, body: GenerateChapterBriefsRequest,
                            svc: ProjectService = Depends(get_service)):
    try:
        return svc.generate_chapter_briefs(
            project_id,
            source=body.source,
            max_beats=body.max_beats,
            beat_importance_threshold=body.beat_importance_threshold,
            overwrite_existing=body.overwrite_existing,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/projects/{project_id}/chapters/briefs/generate/async",
    response_model=Job,
    status_code=202,
)
def generate_chapter_briefs_async(
    project_id: str,
    body: GenerateChapterBriefsRequest,
    svc: ProjectService = Depends(get_service),
):
    try:
        fn = svc.make_chapter_briefs_job(
            project_id,
            source=body.source,
            max_beats=body.max_beats,
            beat_importance_threshold=body.beat_importance_threshold,
            overwrite_existing=body.overwrite_existing,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit(
        "chapter_briefs",
        fn,
        meta={"project_id": project_id},
    )
    return runner.get(job_id)


@router.get(
    "/projects/{project_id}/batch/auto-title/stats",
    response_model=BatchExtractOutlineStats,
)
def auto_title_chapter_stats(
    project_id: str,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.auto_title_chapter_stats(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post(
    "/projects/{project_id}/chapters/titles/generate",
    response_model=GenerateChapterTitlesResult,
)
def generate_chapter_titles(
    project_id: str,
    body: GenerateChapterTitlesRequest,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.generate_chapter_titles(
            project_id,
            source=body.source,
            scope=body.scope,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/projects/{project_id}/chapters/titles/generate/async",
    response_model=Job,
    status_code=202,
)
def generate_chapter_titles_async(
    project_id: str,
    body: GenerateChapterTitlesRequest,
    svc: ProjectService = Depends(get_service),
):
    try:
        fn = svc.make_chapter_titles_job(
            project_id,
            source=body.source,
            scope=body.scope,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit(
        "chapter_titles",
        fn,
        meta={"project_id": project_id},
    )
    return runner.get(job_id)


@router.get(
    "/projects/{project_id}/batch/extract-outlines/stats",
    response_model=BatchExtractOutlineStats,
)
def batch_extract_outlines_stats(
    project_id: str,
    source: str = "best",
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.batch_extract_outlines_stats(project_id, source=source)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/batch/extract-outlines", response_model=Job, status_code=202)
def batch_extract_outlines(project_id: str, body: BatchExtractRequest,
                           svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_batch_extract_outlines_job(
            project_id,
            source=body.source,
            skip_existing=body.skip_existing,
            auto_accept=body.auto_accept,
            chapters=body.chapters,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound as e:
        raise HTTPException(status_code=404, detail=f"Chapter {e.args[0]} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit(
        "batch_extract_outlines",
        fn,
        meta={"project_id": project_id},
    )
    return runner.get(job_id)


@router.get(
    "/projects/{project_id}/batch/extract-codex/stats",
    response_model=BatchExtractOutlineStats,
)
def batch_extract_codex_stats(
    project_id: str,
    source: str = "best",
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.batch_extract_codex_stats(project_id, source=source)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/batch/extract-codex", response_model=Job, status_code=202)
def batch_extract_codex(project_id: str, body: BatchExtractRequest,
                        svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_batch_extract_codex_job(
            project_id,
            source=body.source,
            skip_existing=body.skip_existing,
            auto_accept=body.auto_accept,
            chapters=body.chapters,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound as e:
        raise HTTPException(status_code=404, detail=f"Chapter {e.args[0]} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit(
        "batch_extract_codex",
        fn,
        meta={"project_id": project_id},
    )
    return runner.get(job_id)


@router.put("/projects/{project_id}/chapters/{chapter_number}/brief", response_model=ChapterBriefSummary)
def save_chapter_brief(project_id: str, chapter_number: int, body: SaveChapterBrief,
                       svc: ProjectService = Depends(get_service)):
    try:
        return svc.save_chapter_brief(project_id, chapter_number, body.model_dump())
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CharacterNotFound as e:
        raise HTTPException(status_code=404, detail=f"Character '{e.args[0]}' not found")
    except StoryGraphNodeNotFound as e:
        raise HTTPException(status_code=404, detail=f"Story graph node '{e.args[0]}' not found")


@router.delete("/projects/{project_id}/chapters/{chapter_number}/brief", status_code=204)
def delete_chapter_brief(project_id: str, chapter_number: int, svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_chapter_brief(project_id, chapter_number)
        return Response(status_code=204)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterBriefNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter brief for chapter {chapter_number} not found")


@router.get(
    "/projects/{project_id}/chapters/{chapter_number}/context-preview",
    response_model=ChapterContextPreview,
)
def get_chapter_context_preview(
    project_id: str,
    chapter_number: int,
    mode: str = "draft",
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.get_chapter_context_preview(project_id, chapter_number, mode=mode)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/projects/{project_id}/chapters/{chapter_number}/context-preview",
    response_model=ChapterContextPreview,
)
def post_chapter_context_preview(
    project_id: str,
    chapter_number: int,
    body: ChapterContextPreviewRequest,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.get_chapter_context_preview(
            project_id,
            chapter_number,
            mode=body.mode,
            brief_data=body.model_dump(exclude={"mode"}),
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/projects/{project_id}/chapters/{chapter_number}/brief/beat-candidates",
    response_model=ChapterBeatCandidatesResult,
)
def generate_chapter_beat_candidates(
    project_id: str,
    chapter_number: int,
    body: GenerateChapterBeatCandidatesRequest,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.generate_chapter_beat_candidates(
            project_id,
            chapter_number,
            source=body.source,
            count=body.count,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/projects/{project_id}/chapters/{chapter_number}/brief/beat-candidates/async",
    response_model=Job,
    status_code=202,
)
def generate_chapter_beat_candidates_async(
    project_id: str,
    chapter_number: int,
    body: GenerateChapterBeatCandidatesRequest,
    svc: ProjectService = Depends(get_service),
):
    try:
        fn = svc.make_chapter_beat_candidates_job(
            project_id,
            chapter_number,
            source=body.source,
            count=body.count,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit(
        "landed_beats",
        fn,
        meta={"project_id": project_id, "chapter": chapter_number},
    )
    return runner.get(job_id)


@router.get(
    "/projects/{project_id}/chapters/{chapter_number}/brief/beat-candidates/preview",
    response_model=ChapterBeatCandidatesResult,
)
def get_chapter_beat_candidates_preview(
    project_id: str,
    chapter_number: int,
    svc: ProjectService = Depends(get_service),
):
    try:
        preview = svc.get_chapter_beat_candidates_preview(project_id, chapter_number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} not found")
    if preview is None:
        raise HTTPException(status_code=404, detail="No landed beat candidates for this chapter")
    return preview


@router.delete(
    "/projects/{project_id}/chapters/{chapter_number}/brief/beat-candidates/preview",
    status_code=204,
)
def discard_chapter_beat_candidates_preview(
    project_id: str,
    chapter_number: int,
    svc: ProjectService = Depends(get_service),
):
    try:
        svc.discard_chapter_beat_candidates_preview(project_id, chapter_number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} not found")
    return Response(status_code=204)


@router.post(
    "/projects/{project_id}/chapters/{chapter_number}/brief/beat-candidates/apply",
    response_model=ChapterBriefSummary,
)
def apply_chapter_beat_candidates(
    project_id: str,
    chapter_number: int,
    body: ApplyChapterBeatCandidatesRequest,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.apply_chapter_beat_candidates(project_id, chapter_number, body)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {chapter_number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/research", response_model=list[ResearchSparkSummary])
def list_research_sparks(
    project_id: str,
    q: str | None = None,
    tag: str | None = None,
    kind: str | None = None,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.list_research_sparks(project_id, q=q, tag=tag, kind=kind)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/research", response_model=ResearchSparkSummary, status_code=201)
def create_research_spark(
    project_id: str,
    body: CreateResearchSpark,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.create_research_spark(
            project_id,
            title=body.title,
            body=body.body,
            source_url=body.source_url,
            tags=body.tags,
            kind=body.kind,
            attachment_ref=body.attachment_ref,
            link_character_id=body.link_character_id,
            link_chapter=body.link_chapter,
            link_plot_thread_id=body.link_plot_thread_id,
            link_bible_section=body.link_bible_section,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CharacterNotFound as e:
        raise HTTPException(status_code=404, detail=f"Character '{e.args[0]}' not found")
    except PlotThreadNotFound as e:
        raise HTTPException(status_code=404, detail=f"Plot thread '{e.args[0]}' not found")


@router.patch("/projects/{project_id}/research/{spark_id}", response_model=ResearchSparkSummary)
def update_research_spark(
    project_id: str,
    spark_id: str,
    body: UpdateResearchSpark,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.update_research_spark(project_id, spark_id, body.model_dump())
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ResearchSparkNotFound:
        raise HTTPException(status_code=404, detail=f"Research spark '{spark_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CharacterNotFound as e:
        raise HTTPException(status_code=404, detail=f"Character '{e.args[0]}' not found")
    except PlotThreadNotFound as e:
        raise HTTPException(status_code=404, detail=f"Plot thread '{e.args[0]}' not found")


@router.delete("/projects/{project_id}/research/{spark_id}", status_code=204)
def delete_research_spark(
    project_id: str,
    spark_id: str,
    svc: ProjectService = Depends(get_service),
):
    try:
        svc.delete_research_spark(project_id, spark_id)
        return Response(status_code=204)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ResearchSparkNotFound:
        raise HTTPException(status_code=404, detail=f"Research spark '{spark_id}' not found")


@router.get("/projects/{project_id}/maps", response_model=list[ProjectMapSummary])
def list_project_maps(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_project_maps(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/maps", response_model=ProjectMapSummary, status_code=201)
def create_project_map(
    project_id: str,
    body: CreateProjectMap,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.create_project_map(project_id, body.name)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/maps/{map_id}", response_model=ProjectMapDetail)
def get_project_map(project_id: str, map_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.get_project_map(project_id, map_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ProjectMapNotFound:
        raise HTTPException(status_code=404, detail=f"Map '{map_id}' not found")


@router.patch("/projects/{project_id}/maps/{map_id}", response_model=ProjectMapSummary)
def update_project_map(
    project_id: str,
    map_id: str,
    body: UpdateProjectMap,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.update_project_map(project_id, map_id, body.model_dump())
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ProjectMapNotFound:
        raise HTTPException(status_code=404, detail=f"Map '{map_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/projects/{project_id}/maps/{map_id}", status_code=204)
def delete_project_map(project_id: str, map_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_project_map(project_id, map_id)
        return Response(status_code=204)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ProjectMapNotFound:
        raise HTTPException(status_code=404, detail=f"Map '{map_id}' not found")


@router.post("/projects/{project_id}/maps/{map_id}/image", response_model=ProjectMapSummary)
async def upload_map_image(
    project_id: str,
    map_id: str,
    request: Request,
    svc: ProjectService = Depends(get_service),
):
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    allowed = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
    if content_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Content-Type must be image/png, image/jpeg, image/webp, or image/gif",
        )
    data = await request.body()
    try:
        return svc.upload_map_image(project_id, map_id, data)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ProjectMapNotFound:
        raise HTTPException(status_code=404, detail=f"Map '{map_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/maps/{map_id}/image")
def get_map_image(project_id: str, map_id: str, svc: ProjectService = Depends(get_service)):
    try:
        path, media_type = svc.resolve_map_image_path(project_id, map_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ProjectMapNotFound:
        raise HTTPException(status_code=404, detail=f"Map '{map_id}' not found")
    return FileResponse(path, media_type=media_type)


@router.get("/projects/{project_id}/maps/{map_id}/pins", response_model=list[MapPinSummary])
def list_map_pins(project_id: str, map_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_map_pins(project_id, map_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ProjectMapNotFound:
        raise HTTPException(status_code=404, detail=f"Map '{map_id}' not found")


@router.post("/projects/{project_id}/maps/{map_id}/pins", response_model=MapPinSummary, status_code=201)
def create_map_pin(
    project_id: str,
    map_id: str,
    body: CreateMapPin,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.create_map_pin(
            project_id,
            map_id,
            label=body.label,
            x=body.x,
            y=body.y,
            lore_section=body.lore_section,
            lore_label=body.lore_label,
            notes=body.notes,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ProjectMapNotFound:
        raise HTTPException(status_code=404, detail=f"Map '{map_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/projects/{project_id}/maps/{map_id}/pins/{pin_id}", response_model=MapPinSummary)
def update_map_pin(
    project_id: str,
    map_id: str,
    pin_id: str,
    body: UpdateMapPin,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.update_map_pin(project_id, map_id, pin_id, body.model_dump())
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ProjectMapNotFound:
        raise HTTPException(status_code=404, detail=f"Map '{map_id}' not found")
    except MapPinNotFound:
        raise HTTPException(status_code=404, detail=f"Map pin '{pin_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/projects/{project_id}/maps/{map_id}/pins/{pin_id}", status_code=204)
def delete_map_pin(
    project_id: str,
    map_id: str,
    pin_id: str,
    svc: ProjectService = Depends(get_service),
):
    try:
        svc.delete_map_pin(project_id, map_id, pin_id)
        return Response(status_code=204)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ProjectMapNotFound:
        raise HTTPException(status_code=404, detail=f"Map '{map_id}' not found")
    except MapPinNotFound:
        raise HTTPException(status_code=404, detail=f"Map pin '{pin_id}' not found")


@router.get("/projects/{project_id}/plot-threads/panel-issues", response_model=PlotPanelIssuesReport)
def list_plot_panel_issues(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.get_plot_panel_issues(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/plot-threads/panel-issues/resolve",
             response_model=PlotPanelResolveResult)
def resolve_plot_panel_issue(project_id: str, body: ResolvePlotPanelIssue,
                             svc: ProjectService = Depends(get_service)):
    try:
        return svc.resolve_plot_panel_issue(project_id, body.issue_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/plot-threads/panel-issues/auto-resolve",
             response_model=PlotPanelAutoResolveResult)
def auto_resolve_plot_panel_issues(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.auto_resolve_plot_panel_issues(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/plot-threads/{thread_id}/generate", response_model=Job,
             status_code=202)
def generate_plot_thread(project_id: str, thread_id: str, body: GeneratePlotThread,
                         svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_plot_generate_job(project_id, thread_id, body.prompt)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except PlotThreadNotFound:
        raise HTTPException(status_code=404, detail=f"Plot thread '{thread_id}' not found")
    job_id = runner.submit(
        "plot_generate",
        fn,
        meta={"project_id": project_id, "thread_id": thread_id},
    )
    return runner.get(job_id)


@router.get("/projects/{project_id}/plot-threads/{thread_id}/generate/preview",
            response_model=PlotGeneratePreview)
def get_plot_generate_preview(project_id: str, thread_id: str,
                              svc: ProjectService = Depends(get_service)):
    try:
        preview = svc.get_plot_generate_preview(project_id, thread_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    if preview is None:
        raise HTTPException(status_code=404, detail="No plot generate preview")
    return preview


@router.delete("/projects/{project_id}/plot-threads/{thread_id}/generate/preview", status_code=204)
def discard_plot_generate_preview(project_id: str, thread_id: str,
                                  svc: ProjectService = Depends(get_service)):
    try:
        svc.discard_plot_generate_preview(project_id, thread_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return Response(status_code=204)


@router.get("/projects/{project_id}/story-bible", response_model=StoryBible)
def get_story_bible(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return StoryBible(data=svc.get_story_bible(project_id))
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.patch("/projects/{project_id}/story-bible", response_model=StoryBible)
def update_story_bible(project_id: str, body: UpdateStoryBible, svc: ProjectService = Depends(get_service)):
    try:
        data = svc.update_story_bible_section(project_id, body.section, body.content)
        return StoryBible(data=data)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/story-bible/duplicates/status", response_model=BibleDedupStatus)
def bible_dedup_status(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.get_bible_dedup_status(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/story-bible/duplicates", response_model=BibleDuplicatesReport)
def list_bible_duplicates(project_id: str, ai: bool = False, svc: ProjectService = Depends(get_service)):
    try:
        return svc.get_bible_duplicates(project_id, prefer_ai=ai)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/story-bible/duplicates/ai-scan", response_model=Job, status_code=202)
def ai_scan_bible_duplicates(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_bible_ai_dedup_job(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    job_id = runner.submit("bible_dedup_ai", fn, meta={"project_id": project_id})
    return runner.get(job_id)


@router.post("/projects/{project_id}/story-bible/duplicates/auto-resolve", response_model=BibleAutoDedupeResult)
def auto_resolve_bible_duplicates(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.auto_dedupe_bible(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/story-bible/duplicates/merge", response_model=BibleAutoDedupeResult)
def merge_bible_duplicates(project_id: str, body: BibleDedupeMerge, svc: ProjectService = Depends(get_service)):
    try:
        return svc.merge_bible_duplicates(project_id, body)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/extract-background", response_model=Job, status_code=202)
def extract_background(project_id: str, body: ExtractBackground,
                       svc: ProjectService = Depends(get_service)):
    """Run Lorekeeper on a background/worldbuilding text block (story-level extraction)."""
    try:
        fn = svc.make_background_extract_job(project_id, body.text, body.label)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("extract_background", fn, meta={"project_id": project_id})
    return runner.get(job_id)


@router.post("/projects/{project_id}/chapters")
def create_chapter(project_id: str, body: CreateChapter, svc: ProjectService = Depends(get_service)):
    try:
        result = svc.create_chapter(
            project_id, body.number, body.title, body.text, body.extract,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    if isinstance(result, tuple):
        fn, pid, num = result
        job_id = runner.submit("extract", fn, meta={"project_id": pid, "chapter": num})
        return runner.get(job_id)
    return result


@router.patch("/projects/{project_id}/chapters/{number}", response_model=ChapterSummary)
def update_chapter(project_id: str, number: int, body: UpdateChapter,
                   svc: ProjectService = Depends(get_service)):
    try:
        return svc.update_chapter(project_id, number, body.model_dump())
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")


@router.post("/projects/{project_id}/chapters/{number}/reassign", response_model=ReassignChapterResult)
def reassign_chapter(project_id: str, number: int, body: ReassignChapter,
                     svc: ProjectService = Depends(get_service)):
    try:
        return svc.reassign_chapter(project_id, number, body.to_number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/chapters/{number}/duplicate", response_model=ChapterSequenceResult)
def duplicate_chapter(project_id: str, number: int, body: DuplicateChapter,
                      svc: ProjectService = Depends(get_service)):
    try:
        return svc.duplicate_chapter(project_id, number, body.title)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/chapters/{number}/merge", response_model=ChapterSequenceResult)
def merge_chapter(project_id: str, number: int, body: MergeChapter,
                  svc: ProjectService = Depends(get_service)):
    try:
        return svc.merge_chapter(project_id, number, body.source_number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound as e:
        raise HTTPException(status_code=404, detail=f"Chapter {e} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/chapters/{number}/paste")
def paste_chapter(project_id: str, number: int, body: PasteChapter,
                  svc: ProjectService = Depends(get_service)):
    try:
        result = svc.paste_chapter(project_id, number, body.text, body.title, body.extract)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    if isinstance(result, tuple):
        fn, pid, num = result
        job_id = runner.submit("extract", fn, meta={"project_id": pid, "chapter": num})
        return runner.get(job_id)
    return result


@router.put("/projects/{project_id}/chapters/{number}/outline", response_model=OutlineResult)
def save_outline(project_id: str, number: int, body: OutlineSave,
                 svc: ProjectService = Depends(get_service)):
    try:
        wc = svc.save_outline(project_id, number, body.text)
        return OutlineResult(outline=body.text, word_count=wc)
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")


@router.put("/projects/{project_id}/chapters/{number}/draft", response_model=DraftResult)
def save_draft(project_id: str, number: int, body: DraftSave,
               svc: ProjectService = Depends(get_service)):
    try:
        wc = svc.save_draft(project_id, number, body.text)
        return DraftResult(draft=body.text, word_count=wc)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.put("/projects/{project_id}/chapters/{number}/revised", response_model=RevisedResult)
def save_revised(project_id: str, number: int, body: RevisedSave,
                 svc: ProjectService = Depends(get_service)):
    try:
        wc = svc.save_revised(project_id, number, body.text)
        return RevisedResult(revised=body.text, word_count=wc)
    except (ProjectNotFound, ChapterNotFound) as e:
        if isinstance(e, ProjectNotFound):
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")


@router.post("/projects/{project_id}/chapters/{number}/extract", response_model=Job, status_code=202)
def extract_chapter(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_extract_job(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("extract", fn, meta={"project_id": project_id, "chapter": number})
    return runner.get(job_id)


@router.post("/projects/{project_id}/chapters/{number}/mine/{kind}", response_model=Job, status_code=202)
def mine_chapter(
    project_id: str,
    number: int,
    kind: str,
    source: str = "draft",
    svc: ProjectService = Depends(get_service),
):
    """Mine chapter prose for plots, characters, or story bible (focused extract)."""
    try:
        fn = svc.make_mine_job(project_id, number, kind, source=source)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit(f"mine_{kind}", fn, meta={"project_id": project_id, "chapter": number})
    return runner.get(job_id)


@router.get(
    "/projects/{project_id}/chapters/mine-previews",
    response_model=list[ChapterMinePreviewSummary],
)
def list_chapter_mine_previews(
    project_id: str,
    kind: str | None = None,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.list_chapter_mine_previews(project_id, kind=kind)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get(
    "/projects/{project_id}/chapters/{number}/mine/{kind}/preview",
    response_model=ChapterMinePreview,
)
def get_chapter_mine_preview(
    project_id: str,
    number: int,
    kind: str,
    svc: ProjectService = Depends(get_service),
):
    try:
        preview = svc.get_chapter_mine_preview(project_id, number, kind)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    if preview is None:
        raise HTTPException(status_code=404, detail="No mine preview for this chapter")
    return preview


@router.delete(
    "/projects/{project_id}/chapters/{number}/mine/{kind}/preview",
    status_code=204,
)
def discard_chapter_mine_preview(
    project_id: str,
    number: int,
    kind: str,
    svc: ProjectService = Depends(get_service),
):
    try:
        svc.discard_chapter_mine_preview(project_id, number, kind)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(status_code=204)


@router.post(
    "/projects/{project_id}/chapters/{number}/mine/{kind}/apply",
    response_model=ApplyChapterMinePreviewResult,
)
def apply_chapter_mine_preview(
    project_id: str,
    number: int,
    kind: str,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.apply_chapter_mine_preview(project_id, number, kind)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/chapters/{number}/regenerate", response_model=Job, status_code=202)
def regenerate_chapter(project_id: str, number: int, body: RegenerateChapter,
                       svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_regenerate_job(
            project_id, number, source=body.source, instructions=body.instructions,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except (BadRequest, ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("regenerate", fn, meta={"project_id": project_id, "chapter": number})
    return runner.get(job_id)


@router.get("/projects/{project_id}/chapters/{number}/regenerate/preview",
            response_model=RegeneratePreview)
def get_regenerate_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        preview = svc.get_regenerate_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    if preview is None:
        raise HTTPException(status_code=404, detail="No regenerate preview for this chapter")
    return preview


@router.post("/projects/{project_id}/chapters/{number}/regenerate/apply",
             response_model=RegenerateApplyResult)
def apply_regenerate_preview(project_id: str, number: int, body: RegenerateApply,
                             svc: ProjectService = Depends(get_service)):
    try:
        target, wc = svc.apply_regenerate_preview(
            project_id, number, body.text, target=body.target,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RegenerateApplyResult(target=target, word_count=wc)


@router.delete("/projects/{project_id}/chapters/{number}/regenerate/preview", status_code=204)
def discard_regenerate_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        svc.discard_regenerate_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    return Response(status_code=204)


@router.post("/projects/{project_id}/chapters/{number}/redraft-from-brief", response_model=Job, status_code=202)
def redraft_from_brief(project_id: str, number: int, body: RedraftFromBriefRequest,
                       svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_redraft_job(
            project_id, number, source=body.source, mode=body.mode, instructions=body.instructions,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except (BadRequest, ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("redraft_from_brief", fn, meta={"project_id": project_id, "chapter": number})
    return runner.get(job_id)


@router.get("/projects/{project_id}/chapters/{number}/redraft-from-brief/preview",
            response_model=RedraftPreview)
def get_redraft_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        preview = svc.get_redraft_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    if preview is None:
        raise HTTPException(status_code=404, detail="No redraft preview for this chapter")
    return preview


@router.post("/projects/{project_id}/chapters/{number}/redraft-from-brief/apply",
             response_model=RedraftApplyResult)
def apply_redraft_preview(project_id: str, number: int, body: RedraftApply,
                          svc: ProjectService = Depends(get_service)):
    try:
        target, wc = svc.apply_redraft_preview(project_id, number, body.text)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedraftApplyResult(target=target, word_count=wc)


@router.delete("/projects/{project_id}/chapters/{number}/redraft-from-brief/preview", status_code=204)
def discard_redraft_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        svc.discard_redraft_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    return Response(status_code=204)


@router.post("/projects/{project_id}/chapters/{number}/expand-placeholders", response_model=Job, status_code=202)
def expand_placeholders(project_id: str, number: int, body: RegenerateChapter,
                        svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_expand_job(
            project_id, number, source=body.source, instructions=body.instructions,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("expand_placeholders", fn, meta={"project_id": project_id, "chapter": number})
    return runner.get(job_id)


@router.get("/projects/{project_id}/chapters/{number}/expand/preview",
            response_model=RegeneratePreview)
def get_expand_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        preview = svc.get_expand_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    if preview is None:
        raise HTTPException(status_code=404, detail="No expand preview for this chapter")
    return preview


@router.post("/projects/{project_id}/chapters/{number}/expand/apply",
             response_model=RegenerateApplyResult)
def apply_expand_preview(project_id: str, number: int, body: RegenerateApply,
                         svc: ProjectService = Depends(get_service)):
    try:
        target, wc = svc.apply_expand_preview(
            project_id, number, body.text, target=body.target,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RegenerateApplyResult(target=target, word_count=wc)


@router.delete("/projects/{project_id}/chapters/{number}/expand/preview", status_code=204)
def discard_expand_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        svc.discard_expand_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    return Response(status_code=204)


@router.post("/projects/{project_id}/chapters/{number}/format-paragraphs", response_model=Job, status_code=202)
def format_paragraphs(project_id: str, number: int, body: RegenerateChapter,
                      svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_format_paragraphs_job(project_id, number, source=body.source)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("format_paragraphs", fn, meta={"project_id": project_id, "chapter": number})
    return runner.get(job_id)


@router.get("/projects/{project_id}/chapters/{number}/paragraphs/preview",
            response_model=RegeneratePreview)
def get_paragraphs_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        preview = svc.get_paragraphs_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    if preview is None:
        raise HTTPException(status_code=404, detail="No paragraph-format preview for this chapter")
    return preview


@router.post("/projects/{project_id}/chapters/{number}/paragraphs/apply",
             response_model=RegenerateApplyResult)
def apply_paragraphs_preview(project_id: str, number: int, body: RegenerateApply,
                            svc: ProjectService = Depends(get_service)):
    try:
        target, wc = svc.apply_paragraphs_preview(
            project_id, number, body.text, target=body.target,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RegenerateApplyResult(target=target, word_count=wc)


@router.delete("/projects/{project_id}/chapters/{number}/paragraphs/preview", status_code=204)
def discard_paragraphs_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        svc.discard_paragraphs_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    return Response(status_code=204)


@router.post("/projects/{project_id}/chapters/{number}/check-dialogue-quotes", response_model=Job, status_code=202)
def check_dialogue_quotes(project_id: str, number: int, body: RegenerateChapter,
                          svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_check_dialogue_quotes_job(project_id, number, source=body.source)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("check_dialogue_quotes", fn, meta={"project_id": project_id, "chapter": number})
    return runner.get(job_id)


@router.get("/projects/{project_id}/chapters/{number}/dialogue-quotes/preview",
            response_model=RegeneratePreview)
def get_dialogue_quotes_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        preview = svc.get_dialogue_quotes_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    if preview is None:
        raise HTTPException(status_code=404, detail="No dialogue quote preview for this chapter")
    return preview


@router.post("/projects/{project_id}/chapters/{number}/dialogue-quotes/apply",
             response_model=RegenerateApplyResult)
def apply_dialogue_quotes_preview(project_id: str, number: int, body: RegenerateApply,
                                  svc: ProjectService = Depends(get_service)):
    try:
        target, wc = svc.apply_dialogue_quotes_preview(
            project_id, number, body.text, target=body.target,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RegenerateApplyResult(target=target, word_count=wc)


@router.delete("/projects/{project_id}/chapters/{number}/dialogue-quotes/preview", status_code=204)
def discard_dialogue_quotes_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        svc.discard_dialogue_quotes_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    return Response(status_code=204)


@router.post("/projects/{project_id}/chapters/{number}/align-boundary", response_model=Job, status_code=202)
def align_chapter_boundary(project_id: str, number: int, body: RegenerateChapter,
                           svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_align_boundary_job(project_id, number, source=body.source)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("align_boundary", fn, meta={"project_id": project_id, "chapter": number})
    return runner.get(job_id)


@router.get("/projects/{project_id}/chapters/{number}/alignment/preview",
            response_model=BoundaryAlignmentPreview)
def get_alignment_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        preview = svc.get_alignment_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    if preview is None:
        raise HTTPException(status_code=404, detail="No boundary alignment preview for this chapter")
    return preview


@router.post("/projects/{project_id}/chapters/{number}/alignment/apply",
             response_model=BoundaryAlignmentApplyResult)
def apply_alignment_preview(project_id: str, number: int, body: BoundaryAlignmentApply,
                            svc: ProjectService = Depends(get_service)):
    try:
        result = svc.apply_alignment_preview(
            project_id, number, body.text_a, body.text_b,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return BoundaryAlignmentApplyResult(**result)


@router.delete("/projects/{project_id}/chapters/{number}/alignment/preview", status_code=204)
def discard_alignment_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        svc.discard_alignment_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    return Response(status_code=204)


@router.post("/projects/{project_id}/chapters/{number}/generate-outline", response_model=Job, status_code=202)
def generate_outline_from_text(project_id: str, number: int, body: RegenerateChapter,
                             svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_generate_outline_job(
            project_id, number, source=body.source, instructions=body.instructions,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except (BadRequest, ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    job_id = runner.submit("generate_outline", fn, meta={"project_id": project_id, "chapter": number})
    return runner.get(job_id)


@router.get("/projects/{project_id}/chapters/{number}/generate-outline/preview",
             response_model=RegeneratePreview)
def get_outline_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        preview = svc.get_outline_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    if preview is None:
        raise HTTPException(status_code=404, detail="No outline preview for this chapter")
    return preview


@router.post("/projects/{project_id}/chapters/{number}/generate-outline/apply",
             response_model=RegenerateApplyResult)
def apply_outline_preview(project_id: str, number: int, body: RegenerateApply,
                          svc: ProjectService = Depends(get_service)):
    try:
        wc = svc.apply_outline_preview(project_id, number, body.text)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RegenerateApplyResult(target="outline", word_count=wc)


@router.post("/projects/{project_id}/chapters/{number}/split", response_model=SplitChapterResult)
def split_oversized_chapter(
    project_id: str,
    number: int,
    body: SplitChapterRequest,
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.split_oversized_chapter(
            project_id,
            number,
            source=body.source,
            max_words=body.max_words,
            use_target_length=body.use_target_length,
            align_boundaries=body.align_boundaries,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except (BadRequest, ValueError, FileNotFoundError, FileExistsError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/projects/{project_id}/chapters/{number}/generate-outline/preview", status_code=204)
def discard_outline_preview(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        svc.discard_outline_preview(project_id, number)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    return Response(status_code=204)


@router.get("/projects/{project_id}/chapters/{number}/mentions/analysis", response_model=MentionAnalysis)
def mention_analysis(
    project_id: str,
    number: int,
    source: str = "revised",
    svc: ProjectService = Depends(get_service),
):
    try:
        return svc.analyze_mentions(project_id, number, source=source)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/chapters/{number}/mentions/suggest")
def mention_suggest(
    project_id: str,
    number: int,
    body: MentionSuggestRequest,
    svc: ProjectService = Depends(get_service),
):
    """Generate mention memory suggestions. use_llm=true submits an async job (202)."""
    try:
        if body.use_llm:
            fn = svc.make_mention_suggest_job(
                project_id, number, source=body.source, use_llm=True,
            )
            job_id = runner.submit("mention_suggest", fn, meta={"project_id": project_id, "chapter": number})
            return runner.get(job_id)
        return svc.suggest_mentions_sync(project_id, number, source=body.source)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/chapters/{number}/mentions/suggestions")
def get_mention_suggestions(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        data = svc.get_mention_suggestions(project_id, number)
        if data is None:
            raise HTTPException(status_code=404, detail="No mention suggestions for this chapter")
        return data
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")


@router.post("/projects/{project_id}/chapters/{number}/mentions/apply", response_model=MentionApplyResult)
def apply_mention_edits(
    project_id: str,
    number: int,
    body: MentionApplyRequest,
    svc: ProjectService = Depends(get_service),
):
    try:
        edits = [e.model_dump() for e in body.edits]
        return svc.apply_mention_edits(project_id, number, edits)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ChapterNotFound:
        raise HTTPException(status_code=404, detail=f"Chapter {number} not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/projects/{project_id}/duplicates/status", response_model=EntityDedupStatus)
def duplicates_status(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.get_duplicates_status(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.get("/projects/{project_id}/duplicates", response_model=DuplicatesReport)
def list_duplicates(project_id: str, ai: bool = False, svc: ProjectService = Depends(get_service)):
    try:
        return svc.get_duplicates(project_id, prefer_ai=ai)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/duplicates/ai-scan", response_model=Job, status_code=202)
def ai_scan_duplicates(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        fn = svc.make_ai_duplicate_scan_job(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    job_id = runner.submit("dedup_ai", fn, meta={"project_id": project_id})
    return runner.get(job_id)


@router.post("/projects/{project_id}/duplicates/auto-resolve", response_model=AutoResolveResult)
def auto_resolve_duplicates(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.auto_resolve_duplicates(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/plot-threads/nest", response_model=MergeResult)
def nest_plot_threads(project_id: str, body: NestPlotThreads, svc: ProjectService = Depends(get_service)):
    try:
        return svc.nest_plot_threads(project_id, body.parent_id, body.child_ids)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/duplicates/merge", response_model=MergeResult)
def merge_duplicate_entities(project_id: str, body: MergeEntities, svc: ProjectService = Depends(get_service)):
    try:
        return svc.merge_entities(
            project_id, body.kind, body.keep_id, body.merge_ids,
            mode=body.mode, label_override=body.label_override,
        )
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/projects/{project_id}/duplicates/ai-suggestions", status_code=204)
def clear_ai_duplicate_suggestions(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.clear_ai_duplicate_suggestions(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return Response(status_code=204)


# ----- Project backups (full story state)

@router.get("/projects/{project_id}/backups", response_model=BackupsReport)
def list_project_backups(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.list_backups(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


@router.post("/projects/{project_id}/backups", response_model=NamedBackupMeta, status_code=201)
def create_project_backup(project_id: str, body: CreateNamedBackup,
                          svc: ProjectService = Depends(get_service)):
    try:
        return svc.create_named_backup(project_id, body.label)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/backups/{backup_id}/restore", response_model=BackupActionResult)
def restore_project_backup(project_id: str, backup_id: str, svc: ProjectService = Depends(get_service)):
    try:
        entry = svc.restore_named_backup(project_id, backup_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return BackupActionResult(message=f"Restored backup: {entry.get('label', backup_id)}")


@router.delete("/projects/{project_id}/backups/{backup_id}", status_code=204)
def delete_project_backup(project_id: str, backup_id: str, svc: ProjectService = Depends(get_service)):
    try:
        svc.delete_named_backup(project_id, backup_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except BadRequest as e:
        raise HTTPException(status_code=404, detail=str(e))
    return Response(status_code=204)


@router.post("/projects/{project_id}/backups/quick-save", response_model=BackupActionResult)
def quick_save_project_backup(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        result = svc.quick_save_backup(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return BackupActionResult(
        message="Quick save complete",
        quick=result.get("quick"),
    )


@router.post("/projects/{project_id}/backups/quick-restore", response_model=BackupActionResult)
def quick_restore_project_backup(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        result = svc.quick_restore_backup(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return BackupActionResult(
        message="Restored from quick save (current state saved as pre-restore snapshot)",
        quick=result.get("quick"),
    )


@router.post("/projects/{project_id}/backups/undo-restore", response_model=BackupActionResult)
def undo_project_backup_restore(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        result = svc.undo_backup_restore(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return BackupActionResult(
        message="Undid restore — reverted to pre-restore snapshot",
        quick=result.get("quick"),
    )


@router.get("/projects/{project_id}/state")
def raw_state(project_id: str, svc: ProjectService = Depends(get_service)):
    try:
        return svc.raw_state(project_id)
    except ProjectNotFound:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")


# ----- M2: pipeline stages + editable Final

def _not_found(project_id: str, number: int, e: Exception):
    if isinstance(e, ProjectNotFound):
        return HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return HTTPException(status_code=404, detail=f"Chapter {number} not found")


@router.get("/projects/{project_id}/chapters/{number}/stages", response_model=ChapterStages)
def chapter_stages(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        return svc.chapter_stages(project_id, number)
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)


@router.post("/projects/{project_id}/chapters/{number}/final/promote", response_model=FinalResult)
def promote_final(project_id: str, number: int, force: bool = False,
                  svc: ProjectService = Depends(get_service)):
    try:
        text = svc.promote_final(project_id, number, force=force)
        return FinalResult(final=text, word_count=len(text.split()))
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)
    except NoSourceArtifact:
        raise HTTPException(
            status_code=409,
            detail="Nothing to promote — no draft or revised text exists yet.",
        )


@router.put("/projects/{project_id}/chapters/{number}/final", response_model=FinalResult)
def save_final(project_id: str, number: int, body: FinalSave,
               svc: ProjectService = Depends(get_service)):
    try:
        wc = svc.save_final(project_id, number, body.text)
        return FinalResult(final=body.text, word_count=wc)
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)


@router.post("/projects/{project_id}/chapters/{number}/final/unfinalize", response_model=UnfinalizeResult)
def unfinalize_chapter(project_id: str, number: int, svc: ProjectService = Depends(get_service)):
    try:
        stages = svc.unfinalize_chapter(project_id, number)
        ch = svc.chapter_detail(project_id, number)
        return UnfinalizeResult(
            number=stages.number,
            status=stages.status,
            outline=stages.outline,
            draft=stages.draft,
            revised=stages.revised,
            final=stages.final,
            word_count=ch.word_count,
        )
    except (ProjectNotFound, ChapterNotFound) as e:
        raise _not_found(project_id, number, e)
    except NothingToUnfinalize:
        raise HTTPException(
            status_code=409,
            detail="Nothing to reopen — chapter is not validated, approved, or finalized.",
        )


# ----- Install settings (global, not per-project)

@router.get("/settings/system-prompt", response_model=SystemPromptSettings)
def get_system_prompt_settings():
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from app_settings import read_global_system_prefix  # noqa: WPS433

    agents = Path(__file__).resolve().parent.parent / "agents"
    return SystemPromptSettings(
        prefix=read_global_system_prefix(),
        agents_dir=str(agents),
    )


@router.put("/settings/system-prompt", response_model=SystemPromptSettings)
def put_system_prompt_settings(body: SystemPromptSettings):
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from app_settings import write_global_system_prefix, read_global_system_prefix  # noqa: WPS433

    write_global_system_prefix(body.prefix)
    agents = Path(__file__).resolve().parent.parent / "agents"
    return SystemPromptSettings(prefix=read_global_system_prefix(), agents_dir=str(agents))


@router.get("/settings/agent-prompts", response_model=AgentPromptSettings)
def get_agent_prompt_settings():
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from app_settings import agent_prompt_settings  # noqa: WPS433

    agents = Path(__file__).resolve().parent.parent / "agents"
    return AgentPromptSettings(prompts=agent_prompt_settings(), agents_dir=str(agents))


@router.put("/settings/agent-prompts/{agent_name}", response_model=AgentPromptSettings)
def put_agent_prompt_settings(agent_name: str, body: UpdateAgentPromptSetting):
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from app_settings import (  # noqa: WPS433
        agent_prompt_settings,
        write_agent_prompt_variant,
        write_custom_agent_prompt,
    )

    try:
        write_custom_agent_prompt(agent_name, body.custom_prompt)
        write_agent_prompt_variant(agent_name, body.selected_variant)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    agents = Path(__file__).resolve().parent.parent / "agents"
    return AgentPromptSettings(prompts=agent_prompt_settings(), agents_dir=str(agents))


@router.get("/settings/llm-connection", response_model=LlmConnectionSettings)
def get_llm_connection_settings():
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from app_settings import read_llm_connection_settings  # noqa: WPS433

    return LlmConnectionSettings(**read_llm_connection_settings())


@router.put("/settings/llm-connection", response_model=LlmConnectionSettings)
def put_llm_connection_settings(body: UpdateLlmConnectionSettings):
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from app_settings import write_llm_connection_settings  # noqa: WPS433

    try:
        return LlmConnectionSettings(**write_llm_connection_settings(body.model_dump()))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/settings/llm-connection/test", response_model=LlmConnectionTestResult)
def test_llm_connection_settings(body: UpdateLlmConnectionSettings):
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from app_settings import resolve_llm_connection_api_key  # noqa: WPS433
    from llm_client import LLMClient, LLMError  # noqa: WPS433

    try:
        api_key = resolve_llm_connection_api_key(body.model_dump())
        client = LLMClient(
            provider=body.provider,
            model=body.model or None,
            base_url=body.base_url or None,
            api_key=api_key or None,
        )
        return LlmConnectionTestResult(
            ok=True,
            message="Connection settings are valid.",
            provider=client.provider,
            model=client.model,
            base_url=client.base_url,
        )
    except (LLMError, ValueError) as e:
        return LlmConnectionTestResult(
            ok=False,
            message=str(e),
            provider=body.provider,
            model=body.model,
            base_url=body.base_url,
        )


@router.get("/settings/llm-connection/models", response_model=LlmModelListResult)
def list_llm_connection_models():
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from llm_client import LLMClient, LLMError  # noqa: WPS433

    try:
        return LlmModelListResult(models=LLMClient().list_models())
    except LLMError as e:
        return LlmModelListResult(models=[], message=str(e))


def _llm_queue_settings() -> LlmQueueSettings:
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from llm_queue import get_llm_queue  # noqa: WPS433

    s = get_llm_queue().status()
    running = runner.list_running()
    return LlmQueueSettings(
        max_concurrent=int(s["max_concurrent"]),
        active=int(s["active"]),
        queued=int(s["queued"]),
        flushed=bool(s["flushed"]),
        active_items=[LlmQueueEntry(**e) for e in s.get("active_items") or []],
        queued_items=[LlmQueueEntry(**e) for e in s.get("queued_items") or []],
        running_jobs=[RunningJobEntry(**j) for j in running],
    )


@router.get("/settings/llm-queue", response_model=LlmQueueSettings)
def get_llm_queue_settings():
    return _llm_queue_settings()


@router.put("/settings/llm-queue", response_model=LlmQueueSettings)
def put_llm_queue_settings(body: LlmQueueSettingsUpdate):
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from app_settings import write_max_concurrent_llm  # noqa: WPS433
    from llm_queue import configure_llm_queue  # noqa: WPS433

    n = write_max_concurrent_llm(body.max_concurrent)
    configure_llm_queue(n)
    return _llm_queue_settings()


@router.post("/settings/llm-queue/reorder", response_model=LlmQueueSettings)
def reorder_llm_queue(body: LlmQueueReorder):
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from llm_queue import get_llm_queue  # noqa: WPS433

    try:
        get_llm_queue().reorder_queued(body.order)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _llm_queue_settings()


@router.post("/settings/llm-queue/{entry_id}/move", response_model=LlmQueueSettings)
def move_llm_queue_entry(entry_id: str, body: LlmQueueMove):
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from llm_queue import get_llm_queue  # noqa: WPS433

    try:
        get_llm_queue().move_queued(entry_id, body.position)
    except KeyError:
        raise HTTPException(status_code=404, detail="Queued entry not found") from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _llm_queue_settings()


@router.delete("/settings/llm-queue/{entry_id}", response_model=LlmQueueSettings)
def cancel_llm_queue_entry(entry_id: str):
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from llm_queue import get_llm_queue  # noqa: WPS433

    queue = get_llm_queue()
    entry = queue.find_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Queue entry not found")
    job_id = (entry.get("job_id") or "").strip()
    if job_id:
        runner.cancel(job_id)
    else:
        try:
            if entry["state"] == "queued":
                queue.cancel_queued(entry_id)
            else:
                queue.cancel_active(entry_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Queue entry not found") from None
    return _llm_queue_settings()


def _flush_llm_work(reason: str, reject_new_jobs: bool = False) -> LlmQueueFlushResult:
    if str(_CORE) not in sys.path:
        sys.path.insert(0, str(_CORE))
    from llm_queue import flush_llm_queue  # noqa: WPS433

    cancelled_jobs = runner.flush(reason, reject_new=reject_new_jobs)
    queue_status = flush_llm_queue(reason)
    return LlmQueueFlushResult(
        cancelled_jobs=cancelled_jobs,
        queue=LlmQueueSettings(
            max_concurrent=int(queue_status["max_concurrent"]),
            active=int(queue_status["active"]),
            queued=int(queue_status["queued"]),
            flushed=bool(queue_status["flushed"]),
            active_items=[LlmQueueEntry(**e) for e in queue_status.get("active_items") or []],
            queued_items=[LlmQueueEntry(**e) for e in queue_status.get("queued_items") or []],
            running_jobs=[RunningJobEntry(**j) for j in runner.list_running()],
        ),
        message=reason,
    )


@router.post("/settings/llm-queue/flush", response_model=LlmQueueFlushResult)
def flush_llm_queue_endpoint():
    return _flush_llm_work("Queue flushed")


@router.post("/system/restart", response_model=RestartResult)
def restart_novel_os():
    _flush_llm_work("Cancelled by restart", reject_new_jobs=True)
    install = Path(os.environ.get("NOVEL_OS_HOME", Path.home() / ".local/share/novel-os"))
    script = install / "bin" / "novel-os-restart.sh"
    if not script.is_file():
        raise HTTPException(status_code=500, detail=f"Restart script not found: {script}")
    subprocess.Popen(  # noqa: S603
        ["/bin/bash", str(script)],
        cwd=str(install),
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return RestartResult(
        status="restarting",
        message="Restarting Novel OS — queued LLM requests cancelled and in-flight API calls stopped.",
    )
