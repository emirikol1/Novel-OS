from pydantic import BaseModel


class ProjectSummary(BaseModel):
    id: str
    title: str
    genre: str
    chapter_count: int
    status: str


class StashedProjectSummary(BaseModel):
    id: str
    title: str
    genre: str
    chapter_count: int
    stashed_at: str
    filename: str = ""
    size_bytes: int = 0


class ChapterSummary(BaseModel):
    number: int
    display_label: str = ""
    title: str
    title_source: str = ""
    status: str
    word_count: int
    pov: str
    pipeline_step: str = "none"  # none | drafted | revised | validated | approved | final
    has_brief: bool = False
    part_of: int = 0
    part_label: str = ""


class ChapterDetail(ChapterSummary):
    outline: str | None
    draft: str | None


class CharacterSummary(BaseModel):
    id: str
    full_name: str
    role: str
    aliases: list[str] = []
    portrait_url: str | None = None


class PlotThreadSummary(BaseModel):
    id: str
    name: str
    description: str
    thread_type: str
    status: str
    priority: int
    sort_order: int = 0
    subplots: list[str] = []


class ProjectDetail(BaseModel):
    id: str
    title: str
    genre: str
    author: str
    chapter_count: int
    status: str
    style: dict
    project_path: str = ""
    story_state_path: str = ""
    manuscript_path: str = ""


class ChapterStructureIssue(BaseModel):
    severity: str
    chapter: int | None = None
    component: str
    message: str
    path: str | None = None
    resolution: str = ""
    action_url: str | None = None


class ChapterStructureChapter(BaseModel):
    number: int
    title: str
    status: str
    stages_present: list[str] = []
    has_brief: bool = False
    asset_count: int = 0


class ChapterStructureReport(BaseModel):
    ok: bool
    error_count: int
    warning_count: int
    project_path: str
    story_state_path: str
    manuscript_path: str
    issues: list[ChapterStructureIssue] = []
    chapters: list[ChapterStructureChapter] = []


class ChapterStages(BaseModel):
    """The pipeline lineage of a chapter: how outline → draft → revised → final."""
    number: int
    status: str
    outline: str | None
    draft: str | None
    revised: str | None
    final: str | None
    continuity: dict | None


class FinalSave(BaseModel):
    text: str


class FinalResult(BaseModel):
    final: str
    word_count: int


class UnfinalizeResult(BaseModel):
    """Chapter reopened for revision — final removed, validate/approve cleared."""
    number: int
    status: str
    outline: str | None
    draft: str | None
    revised: str | None
    final: str | None
    word_count: int


class CreateProject(BaseModel):
    title: str
    genre: str = ""
    author: str = ""


class AddCharacter(BaseModel):
    name: str
    role: str = "supporting"


class GenerateCharacter(BaseModel):
    prompt: str
    character_id: str | None = None
    hint_name: str = ""
    hint_role: str = ""


class CharacterGeneratePreview(BaseModel):
    character_id: str | None = None
    prompt: str
    hint_name: str = ""
    hint_role: str = ""
    updates: dict
    generated_at: str | None = None


class RunPhase(BaseModel):
    stage: str
    params: dict = {}


class UpdateStyleProfile(BaseModel):
    tone: str | None = None
    point_of_view: str | None = None
    tense: str | None = None
    prose_style: str | None = None
    vocabulary_level: str | None = None
    description: str | None = None


class PlanOutlinePreviewRequest(BaseModel):
    chapters: int = 12
    words: int = 24000


class PlanOutlinePreview(BaseModel):
    outline: dict
    context_summary: list[str]
    output_path: str = "outputs/outline.json"


class SystemPromptSettings(BaseModel):
    prefix: str = ""
    agents_dir: str = ""


class AgentPromptSetting(BaseModel):
    agent: str
    label: str
    selected_variant: str = "current"
    current_default: str = ""
    recommended_default: str = ""
    custom_prompt: str = ""
    contract_guard: str = ""


class AgentPromptSettings(BaseModel):
    prompts: list[AgentPromptSetting]
    agents_dir: str = ""


class UpdateAgentPromptSetting(BaseModel):
    selected_variant: str = "current"
    custom_prompt: str = ""


class LlmQueueEntry(BaseModel):
    id: str
    label: str
    submitted_at: str
    chapter: int | None = None
    project_id: str | None = None
    function: str | None = None
    job_id: str | None = None


class LlmQueueReorder(BaseModel):
    order: list[str]


class LlmQueueMove(BaseModel):
    position: str  # first | last


class RunningJobEntry(BaseModel):
    job_id: str
    kind: str
    label: str
    started_at: str
    project_id: str | None = None
    chapter: int | None = None
    screen: str = "App"
    batch_id: str | None = None
    batch_size: int = 1


class JobCancelResult(BaseModel):
    job_id: str
    kind: str
    status: str
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    project_id: str | None = None
    cancelled_jobs: int = 1
    batch_id: str | None = None
    batch_size: int = 1


class LlmQueueSettings(BaseModel):
    max_concurrent: int = 2
    active: int = 0
    queued: int = 0
    flushed: bool = False
    active_items: list[LlmQueueEntry] = []
    queued_items: list[LlmQueueEntry] = []
    running_jobs: list[RunningJobEntry] = []


class LlmQueueSettingsUpdate(BaseModel):
    max_concurrent: int


class LlmQueueFlushResult(BaseModel):
    cancelled_jobs: int
    queue: LlmQueueSettings
    message: str


class RestartResult(BaseModel):
    status: str
    message: str


class ImportStory(BaseModel):
    chapters_dir: str
    title: str = ""
    genre: str = ""
    author: str = ""
    project_id: str = ""
    synthesize: bool = True
    no_extract: bool = False
    from_chapter: int | None = None
    to_chapter: int | None = None


class ImportEbook(BaseModel):
    source_path: str = ""
    upload_id: str = ""
    title: str = ""
    genre: str = ""
    author: str = ""
    project_id: str = ""
    split_strategy: str = "auto"
    parts: int | None = None
    synthesize: bool = True
    no_extract: bool = False
    from_chapter: int | None = None
    to_chapter: int | None = None


class EbookChapterPreview(BaseModel):
    number: int
    title: str
    word_count: int


class EbookParsePreview(BaseModel):
    upload_id: str
    filename: str
    title: str
    author: str
    language: str
    source_format: str
    split_strategy: str
    chapters: list[EbookChapterPreview]
    total_words: int
    notes: list[str] = []


class Job(BaseModel):
    job_id: str
    kind: str
    status: str
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    project_id: str | None = None


class SnapshotMeta(BaseModel):
    id: str
    label: str
    created_at: str
    word_count: int
    source: str


class SnapshotText(SnapshotMeta):
    text: str


class CreateSnapshot(BaseModel):
    label: str = "Manual"


class Comment(BaseModel):
    id: str
    body: str
    quote: str = ""
    created_at: str
    resolved: bool = False
    stage: str = "comment"
    start_offset: int | None = None
    end_offset: int | None = None
    paragraph_hash: str = ""


class AddComment(BaseModel):
    body: str
    quote: str = ""
    stage: str = "comment"
    start_offset: int | None = None
    end_offset: int | None = None
    paragraph_hash: str = ""


class UpdateComment(BaseModel):
    resolved: bool | None = None
    body: str | None = None
    quote: str | None = None
    stage: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    paragraph_hash: str | None = None


class CreateChapter(BaseModel):
    number: int
    title: str = ""
    text: str = ""
    extract: bool = False


class InsertChapter(BaseModel):
    number: int
    title: str = ""


class DuplicateChapter(BaseModel):
    title: str = ""


class MergeChapter(BaseModel):
    source_number: int


class UpdateChapter(BaseModel):
    title: str | None = None
    status: str | None = None
    pov_character: str | None = None
    location: str | None = None
    time: str | None = None


class ReassignChapter(BaseModel):
    to_number: int


class ReassignChapterResult(BaseModel):
    action: str
    from_number: int
    to_number: int
    chapter: ChapterSummary
    swapped_with: ChapterSummary | None = None


class ChapterNumberMapping(BaseModel):
    from_number: int
    to_number: int


class ChapterSequenceResult(BaseModel):
    action: str
    inserted_number: int | None = None
    mapping: list[ChapterNumberMapping] = []
    chapters: list[ChapterSummary]
    removed_snapshot_count: int = 0


class PasteChapter(BaseModel):
    text: str
    title: str = ""
    extract: bool = False


class OutlineSave(BaseModel):
    text: str


class OutlineResult(BaseModel):
    outline: str
    word_count: int


class DraftSave(BaseModel):
    text: str


class DraftResult(BaseModel):
    draft: str
    word_count: int


class RevisedSave(BaseModel):
    text: str


class RevisedResult(BaseModel):
    revised: str
    word_count: int


class ChapterPasteResult(BaseModel):
    number: int
    word_count: int
    changes: list[str] = []


class CharacterDetail(BaseModel):
    id: str
    full_name: str
    role: str
    portrait_url: str | None = None
    age: int | None = None
    physical_description: str = ""
    internal_desire: str = ""
    external_goal: str = ""
    fear: str = ""
    weakness: str = ""
    strength: str = ""
    secret: str = ""
    arc_stage: str = "beginning"
    arc_progress: int = 0
    current_location: str = ""
    emotional_state: str = ""
    notes: str = ""
    aliases: list[str] = []
    last_appearance_chapter: int = 0
    relationships: dict[str, str] = {}


class UpdateCharacter(BaseModel):
    full_name: str | None = None
    role: str | None = None
    age: int | None = None
    physical_description: str | None = None
    internal_desire: str | None = None
    external_goal: str | None = None
    fear: str | None = None
    weakness: str | None = None
    strength: str | None = None
    secret: str | None = None
    arc_stage: str | None = None
    arc_progress: int | None = None
    current_location: str | None = None
    emotional_state: str | None = None
    notes: str | None = None
    aliases: list[str] | None = None
    last_appearance_chapter: int | None = None
    relationships: dict[str, str] | None = None


class TimelineEventSummary(BaseModel):
    id: str
    description: str
    chapter: int
    day: int | None = None
    time: str | None = None
    location: str = ""
    characters_present: list[str] = []
    event_type: str = "scene"
    significance: str = "minor"


class CreateTimelineEvent(BaseModel):
    description: str
    chapter: int
    day: int | None = None
    time: str | None = None
    location: str = ""
    characters_present: list[str] = []
    event_type: str = "scene"
    significance: str = "minor"


class UpdateTimelineEvent(BaseModel):
    description: str | None = None
    chapter: int | None = None
    day: int | None = None
    time: str | None = None
    location: str | None = None
    characters_present: list[str] | None = None
    event_type: str | None = None
    significance: str | None = None


class GenerateTimelineRequest(BaseModel):
    chapters: list[int] | None = None
    source: str = "best"
    max_events_per_chapter: int = 5


class TimelineGeneratedEvent(BaseModel):
    description: str
    chapter: int
    day: int | None = None
    time: str | None = None
    location: str = ""
    characters_present: list[str] = []
    event_type: str = "scene"
    significance: str = "minor"
    source: str = "best"
    excerpt: str = ""
    score: int = 0
    reason: str = ""


class TimelineSkippedChapter(BaseModel):
    chapter: int
    reason: str


class TimelineGenerationResult(BaseModel):
    source: str
    recommended_per_chapter: int = 5
    chapters_scanned: list[int]
    candidates: list[TimelineGeneratedEvent]
    skipped_chapters: list[TimelineSkippedChapter] = []


class ApplyTimelineGenerationRequest(BaseModel):
    events: list[TimelineGeneratedEvent]


class ApplyTimelineGenerationResult(BaseModel):
    created: list[TimelineEventSummary]


class DeleteTimelineEventsResult(BaseModel):
    deleted: int


class StoryGraphLayoutSummary(BaseModel):
    x: float = 0.0
    y: float = 0.0


class StoryGraphNodeSummary(BaseModel):
    id: str
    kind: str
    title: str
    description: str = ""
    status: str = "active"
    priority: int = 1
    linked_character_ids: list[str] = []
    legacy_plot_thread_id: str = ""
    created_from: str = ""
    sort_order: int = 0
    start_chapter: int = 0
    resolution_chapter: int | None = None
    layout: StoryGraphLayoutSummary | None = None
    act: int = 0
    chapter_pins: list[int] = []


class CreateStoryGraphNode(BaseModel):
    title: str
    kind: str = "beat"
    description: str = ""
    status: str = "active"
    priority: int = 1
    linked_character_ids: list[str] = []
    legacy_plot_thread_id: str = ""
    sort_order: int = 0
    start_chapter: int = 0
    resolution_chapter: int | None = None
    layout: StoryGraphLayoutSummary | None = None
    act: int = 0
    chapter_number: int | None = None
    assign_to_brief: bool = False


class UpdateStoryGraphNode(BaseModel):
    title: str | None = None
    kind: str | None = None
    description: str | None = None
    status: str | None = None
    priority: int | None = None
    linked_character_ids: list[str] | None = None
    legacy_plot_thread_id: str | None = None
    sort_order: int | None = None
    start_chapter: int | None = None
    resolution_chapter: int | None = None
    layout: StoryGraphLayoutSummary | None = None
    act: int | None = None
    chapter_pins: list[int] | None = None


class StoryGraphEdgeSummary(BaseModel):
    id: str
    source_id: str
    target_id: str
    kind: str
    label: str = ""


class CreateStoryGraphEdge(BaseModel):
    source_id: str
    target_id: str
    kind: str = "relates"
    label: str = ""


class UpdateStoryGraphEdge(BaseModel):
    source_id: str | None = None
    target_id: str | None = None
    kind: str | None = None
    label: str | None = None


class StoryGraphMigrateRequest(BaseModel):
    force: bool = False


class StoryGraphMigrateResult(BaseModel):
    nodes_created: int
    edges_created: int
    skipped: bool


class PinStoryGraphNodeRequest(BaseModel):
    chapter_number: int
    pinned: bool = True


class EligibleGraphNodesResult(BaseModel):
    chapter_number: int
    eligible: list[StoryGraphNodeSummary]
    in_effect_ids: list[str] = []
    out_of_range: list[StoryGraphNodeSummary] = []


class ChapterBeatSummary(BaseModel):
    id: str
    title: str
    summary: str = ""
    sort_order: int = 0
    status: str = "planned"
    linked_node_ids: list[str] = []


class ChapterBeatInput(BaseModel):
    id: str = ""
    title: str
    summary: str = ""
    sort_order: int = 0
    status: str = "planned"
    linked_node_ids: list[str] = []


class CreateChapterBeat(BaseModel):
    title: str
    summary: str = ""
    status: str = "planned"
    linked_node_ids: list[str] = []
    sort_order: int | None = None


class UpdateChapterBeat(BaseModel):
    title: str | None = None
    summary: str | None = None
    status: str | None = None
    linked_node_ids: list[str] | None = None
    sort_order: int | None = None


class ReorderChapterBeats(BaseModel):
    ordered_ids: list[str]


class SetChapterBeats(BaseModel):
    beats: list[ChapterBeatInput]


class ChapterBriefSummary(BaseModel):
    chapter_number: int
    pov_character_id: str = ""
    pov_mode: str = ""
    tone: str = ""
    tense: str = ""
    prose_style: str = ""
    vocabulary_level: str = ""
    style_notes: str = ""
    target_word_count: int = 0
    active_character_ids: list[str] = []
    mentioned_character_ids: list[str] = []
    active_node_ids: list[str] = []
    continuity_notes: str = ""
    ending_hook: str = ""


class SaveChapterBrief(BaseModel):
    pov_character_id: str = ""
    pov_mode: str = ""
    tone: str = ""
    tense: str = ""
    prose_style: str = ""
    vocabulary_level: str = ""
    style_notes: str = ""
    target_word_count: int = 0
    active_character_ids: list[str] = []
    mentioned_character_ids: list[str] = []
    active_node_ids: list[str] = []
    continuity_notes: str = ""
    ending_hook: str = ""


class GenerateChapterBeatCandidatesRequest(BaseModel):
    source: str = "best"
    count: int = 10


class ChapterBeatCandidate(BaseModel):
    rank: int
    beat: str
    significance: str
    involved_characters: list[str] = []
    story_relevance: str = ""
    category: str = ""


class ChapterBeatCandidatesResult(BaseModel):
    chapter_number: int
    source_used: str
    candidates: list[ChapterBeatCandidate]


class ApplyChapterBeatCandidatesRequest(BaseModel):
    selected_beats: list[str] = []
    mode: str = "append"  # append | replace


class ChapterMinePreview(BaseModel):
    chapter_number: int
    kind: str
    stage_source: str = "draft"
    source: str = ""
    changes: list[str] = []
    report_path: str = ""
    ui_summary: dict | None = None


class ChapterMinePreviewSummary(BaseModel):
    chapter_number: int
    kind: str
    change_count: int = 0


class ApplyChapterMinePreviewResult(BaseModel):
    chapter_number: int
    kind: str
    changes: list[str] = []


class GenerateChapterBriefRequest(BaseModel):
    source: str = "best"
    max_beats: int = 5


class GenerateChapterBriefsRequest(BaseModel):
    source: str = "best"
    max_beats: int = 5
    overwrite_existing: bool = False


class GenerateChapterBriefsResult(BaseModel):
    generated: list[ChapterBriefSummary]
    skipped: list[dict[str, str | int]]


class GenerateChapterTitlesRequest(BaseModel):
    source: str = "best"
    scope: str = "eligible"  # eligible | auto_only


class ChapterTitleResult(BaseModel):
    chapter: int
    title: str
    title_source: str = "auto"


class GenerateChapterTitlesResult(BaseModel):
    generated: list[ChapterTitleResult]
    skipped: list[dict[str, str | int]]


class BatchExtractRequest(BaseModel):
    source: str = "best"
    skip_existing: bool = True
    auto_accept: bool = False
    chapters: list[int] | None = None


class BatchExtractOutlineStats(BaseModel):
    total_with_prose: int
    missing_count: int
    missing_chapters: list[int]
    secondary_count: int = 0
    secondary_chapters: list[int] = []


class BatchExtractResult(BaseModel):
    generated: list[int | dict[str, int | str]]
    skipped: list[dict[str, str | int]]
    failed: list[dict[str, str | int]]


class ContextPreviewItem(BaseModel):
    key: str = ""
    label: str
    body: str
    reason: str
    score: float = 0.0


class ContextPreviewSection(BaseModel):
    items: list[ContextPreviewItem] = []
    omitted_count: int = 0
    omitted_labels: list[str] = []
    omitted_reason: str = "budget cap"


class ContextPreviewCharacter(BaseModel):
    id: str
    name: str


class ContextPreviewBeat(BaseModel):
    id: str
    title: str
    status: str
    summary: str = ""


class ChapterContextPreview(BaseModel):
    chapter_number: int
    mode: str
    bible: ContextPreviewSection
    graph: ContextPreviewSection
    active_characters: list[ContextPreviewCharacter] = []
    mentioned_characters: list[ContextPreviewCharacter] = []
    beats: list[ContextPreviewBeat] = []


class ChapterContextPreviewRequest(BaseModel):
    mode: str = "draft"
    pov_character_id: str = ""
    pov_mode: str = ""
    active_character_ids: list[str] = []
    active_node_ids: list[str] = []
    continuity_notes: str = ""
    ending_hook: str = ""


class CreatePlotThread(BaseModel):
    name: str
    description: str = ""
    thread_type: str = "main"
    priority: int = 3
    status: str = "active"
    subplots: list[str] = []


class UpdatePlotThread(BaseModel):
    name: str | None = None
    description: str | None = None
    thread_type: str | None = None
    priority: int | None = None
    status: str | None = None
    subplots: list[str] | None = None


class NestPlotThreads(BaseModel):
    parent_id: str
    child_ids: list[str]


class ReorderPlotThreads(BaseModel):
    ordered_ids: list[str]


class StoryBible(BaseModel):
    data: dict


class UpdateStoryBible(BaseModel):
    section: str
    content: str | list | dict


class ExtractBackground(BaseModel):
    text: str
    label: str = "Background"


class ExtractBackgroundResult(BaseModel):
    label: str
    changes: list[str]
    characters: int
    plot_threads: int


class RegenerateChapter(BaseModel):
    source: str = "draft"  # draft | revised | final
    instructions: str = ""


class SplitChapterRequest(BaseModel):
    source: str = "draft"  # draft | revised | final
    max_words: int = 0  # 0 = use target length or NOVEL_OS_CHAPTER_SPLIT_WORDS default
    use_target_length: bool = False  # when max_words=0, use chapter brief / project target
    align_boundaries: bool = False  # after split, auto-align each new internal boundary


class SplitChapterPart(BaseModel):
    number: int
    display_label: str
    word_count: int


class SplitChapterResult(BaseModel):
    parent_number: int
    parts: list[SplitChapterPart]
    total_words: int
    recovered_from_backup: bool = False
    alignments_applied: int = 0
    chapters: list[ChapterSummary] = []


class BoundaryAlignmentPreview(BaseModel):
    chapter_a: int
    chapter_b: int
    source: str
    adjusted: bool
    direction: str | None = None
    move_text: str = ""
    text_a: str
    text_b: str
    original_word_count_a: int
    original_word_count_b: int
    preview_word_count_a: int
    preview_word_count_b: int
    generated_at: str | None = None


class BoundaryAlignmentApply(BaseModel):
    text_a: str
    text_b: str


class BoundaryAlignmentApplyResult(BaseModel):
    chapter_a: int
    chapter_b: int
    source: str
    word_count_a: int
    word_count_b: int


class RegeneratePreview(BaseModel):
    text: str
    source: str
    original_word_count: int
    preview_word_count: int
    generated_at: str | None = None
    instructions: str = ""
    placeholder_count: int | None = None
    scene_break_count: int | None = None


class RegenerateApply(BaseModel):
    text: str
    target: str | None = None  # defaults to source stage from preview meta


class RegenerateApplyResult(BaseModel):
    target: str
    word_count: int


class RedraftFromBriefRequest(BaseModel):
    source: str = "final"
    mode: str = "align"
    instructions: str = ""


class RedraftPreview(BaseModel):
    text: str
    source: str
    mode: str
    original_word_count: int
    preview_word_count: int
    generated_at: str | None = None
    instructions: str = ""


class RedraftApply(BaseModel):
    text: str


class RedraftApplyResult(BaseModel):
    target: str
    word_count: int


class DuplicateMember(BaseModel):
    id: str
    label: str
    role: str | None = None
    thread_type: str | None = None


class DuplicateGroupModel(BaseModel):
    kind: str
    confidence: float
    reason: str
    suggested_keep_id: str
    members: list[DuplicateMember]


class DuplicatesReport(BaseModel):
    characters: list[DuplicateGroupModel]
    plot_threads: list[DuplicateGroupModel]
    source: str = "heuristic"
    ai_scan_completed: bool = False
    scanned_at: str | None = None


class PlotPanelLocation(BaseModel):
    parent_id: str
    parent_name: str
    index: int
    line: str


class PlotPanelIssueModel(BaseModel):
    issue_id: str
    kind: str
    confidence: float
    reason: str
    subplot_line: str
    locations: list[PlotPanelLocation]
    thread_id: str | None = None
    thread_name: str | None = None
    suggested_parent_id: str = ""
    suggested_parent_name: str = ""
    suggested_action: str = "remove_duplicates"


class PlotPanelIssuesReport(BaseModel):
    issues: list[PlotPanelIssueModel]
    source: str = "heuristic"


class ResolvePlotPanelIssue(BaseModel):
    issue_id: str


class PlotPanelResolveResult(BaseModel):
    issue_id: str
    log: list[str]


class PlotPanelAutoResolveResult(BaseModel):
    resolved: int
    log: list[str]


class GeneratePlotThread(BaseModel):
    thread_id: str
    prompt: str = ""


class PlotGeneratePreview(BaseModel):
    thread_id: str
    thread_name: str
    prompt: str
    description: str
    previous_description: str
    bible_suggestions: list[str]
    generated_at: str | None = None


class MergeEntities(BaseModel):
    kind: str  # character | plot_thread
    keep_id: str
    merge_ids: list[str]
    mode: str = "parallel"  # parallel | nest (plot_thread only)
    label_override: str = ""


class MergeResult(BaseModel):
    kind: str
    keep_id: str
    merged: list[str]
    log: list[str]
    mode: str = "parallel"
    keep_label: str = ""


class AutoResolveResult(BaseModel):
    merged_characters: int
    merged_plot_threads: int
    log: list[str]


class BibleDuplicateMember(BaseModel):
    id: str
    section: str
    index: int
    label: str


class BibleDuplicateGroupModel(BaseModel):
    section: str
    confidence: float
    reason: str
    suggested_keep_index: int
    members: list[BibleDuplicateMember]


class BibleDuplicatesReport(BaseModel):
    groups: list[BibleDuplicateGroupModel]
    source: str = "heuristic"


class BibleDedupeMerge(BaseModel):
    keep_section: str
    keep_index: int
    members: list[BibleDuplicateMember]
    text_override: str = ""


class BibleAutoDedupeResult(BaseModel):
    removed: int
    log: list[str]
    keep_text: str = ""


class BibleDedupStatus(BaseModel):
    ai_suggestions_ready: bool
    ai_group_count: int


class GraphDuplicateMember(BaseModel):
    id: str
    label: str
    node_kind: str | None = None
    legacy_plot_thread_id: str | None = None


class GraphDuplicateGroupModel(BaseModel):
    confidence: float
    reason: str
    suggested_keep_id: str
    members: list[GraphDuplicateMember]


class GraphDuplicatesReport(BaseModel):
    groups: list[GraphDuplicateGroupModel]
    source: str = "heuristic"


class GraphDedupeMerge(BaseModel):
    keep_id: str
    merge_ids: list[str]
    title_override: str = ""


class GraphAutoDedupeResult(BaseModel):
    merged: int
    log: list[str]
    keep_label: str = ""


class MentionWarning(BaseModel):
    severity: str
    category: str
    message: str
    suggestion: str = ""
    chapter: int | None = None
    entity_id: str | None = None


class MentionFieldSuggestion(BaseModel):
    character_id: str
    character_name: str
    field: str
    current_value: str | int | list | None = None
    suggested_value: str | int | list | None = None
    reason: str = ""
    explicit_presence: bool = False
    mention_label: str = ""
    mention_raw: str = ""


class MentionAnalysis(BaseModel):
    chapter_number: int
    source: str
    warnings: list[MentionWarning]
    suggestions: list[MentionFieldSuggestion]
    generated_at: str | None = None


class MentionSuggestRequest(BaseModel):
    source: str = "revised"  # draft | revised | final
    use_llm: bool = False


class MentionFieldApply(BaseModel):
    character_id: str
    field: str
    value: str | int | list | None = None
    explicit_presence: bool = False


class MentionApplyRequest(BaseModel):
    edits: list[MentionFieldApply]


class MentionApplyResult(BaseModel):
    log: list[str]
    applied: int


class EntityDedupStatus(BaseModel):
    ai_suggestions_ready: bool
    ai_group_count: int
    has_ai_file: bool = False
    ai_scan_completed: bool = False
    character_group_count: int = 0
    plot_thread_group_count: int = 0


class QuickSlotMeta(BaseModel):
    created_at: str
    size_bytes: int


class QuickBackupMeta(BaseModel):
    current: QuickSlotMeta | None = None
    previous: QuickSlotMeta | None = None
    pre_restore: QuickSlotMeta | None = None


class NamedBackupMeta(BaseModel):
    id: str
    label: str
    created_at: str
    filename: str
    size_bytes: int = 0


class BackupsReport(BaseModel):
    named: list[NamedBackupMeta]
    quick: QuickBackupMeta


class CreateNamedBackup(BaseModel):
    label: str = ""


class BackupActionResult(BaseModel):
    ok: bool = True
    message: str = ""
    quick: QuickBackupMeta | None = None
    backup: NamedBackupMeta | None = None


class ResearchSparkSummary(BaseModel):
    id: str
    title: str
    body: str = ""
    source_url: str = ""
    tags: list[str] = []
    kind: str = "note"
    attachment_ref: str = ""
    link_character_id: str | None = None
    link_chapter: int | None = None
    link_plot_thread_id: str | None = None
    link_bible_section: str | None = None
    created_at: str
    updated_at: str


class CreateResearchSpark(BaseModel):
    title: str
    body: str = ""
    source_url: str = ""
    tags: list[str] = []
    kind: str = "note"
    attachment_ref: str = ""
    link_character_id: str | None = None
    link_chapter: int | None = None
    link_plot_thread_id: str | None = None
    link_bible_section: str | None = None


class UpdateResearchSpark(BaseModel):
    title: str | None = None
    body: str | None = None
    source_url: str | None = None
    tags: list[str] | None = None
    kind: str | None = None
    attachment_ref: str | None = None
    link_character_id: str | None = None
    link_chapter: int | None = None
    link_plot_thread_id: str | None = None
    link_bible_section: str | None = None


class ProjectMapSummary(BaseModel):
    id: str
    name: str
    image_url: str | None = None
    pin_count: int = 0
    created_at: str
    updated_at: str


class MapPinSummary(BaseModel):
    id: str
    map_id: str
    label: str
    x: float
    y: float
    lore_section: str = ""
    lore_label: str = ""
    notes: str = ""
    created_at: str
    updated_at: str


class ProjectMapDetail(BaseModel):
    id: str
    name: str
    image_url: str | None = None
    created_at: str
    updated_at: str
    pins: list[MapPinSummary] = []


class CreateProjectMap(BaseModel):
    name: str = "Main Map"


class UpdateProjectMap(BaseModel):
    name: str | None = None


class CreateMapPin(BaseModel):
    label: str
    x: float
    y: float
    lore_section: str = ""
    lore_label: str = ""
    notes: str = ""


class UpdateMapPin(BaseModel):
    label: str | None = None
    x: float | None = None
    y: float | None = None
    lore_section: str | None = None
    lore_label: str | None = None
    notes: str | None = None
