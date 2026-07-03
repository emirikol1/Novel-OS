// Same-origin in dev (Vite proxies /api → backend). Override with VITE_API_BASE if needed.
import { activeJobBatchId } from "../lib/jobBatch";

const BASE = import.meta.env.VITE_API_BASE ?? "";

export function mapImageUrl(projectId: string, mapId: string): string {
  return `${BASE}/api/projects/${projectId}/maps/${mapId}/image`;
}

export function characterPortraitUrl(projectId: string, characterId: string): string {
  return `${BASE}/api/projects/${projectId}/characters/${characterId}/portrait`;
}

export interface ProjectSummary {
  id: string; title: string; genre: string; chapter_count: number; status: string;
}
export interface StashedProjectSummary {
  id: string; title: string; genre: string; chapter_count: number;
  stashed_at: string; filename: string; size_bytes: number;
}
export interface ChapterSummary {
  number: number;
  display_label?: string;
  title: string;
  title_source?: string;
  status: string;
  word_count: number;
  pov: string;
  pipeline_step: string;
  has_brief?: boolean;
  part_of?: number;
  part_label?: string;
}
export interface ChapterNumberMapping {
  from_number: number; to_number: number;
}
export interface ChapterSequenceResult {
  action: string;
  inserted_number: number | null;
  mapping: ChapterNumberMapping[];
  chapters: ChapterSummary[];
  removed_snapshot_count?: number;
}
export interface ChapterDetail extends ChapterSummary {
  outline: string | null; draft: string | null;
}
export interface ProjectDetail {
  id: string; title: string; genre: string; author: string;
  chapter_count: number; status: string; style: Record<string, string>;
  project_path: string; story_state_path: string; manuscript_path: string;
}
export interface ChapterStructureIssue {
  severity: string; chapter: number | null; component: string; message: string; path: string | null;
  resolution: string; action_url: string | null;
}
export interface ChapterStructureChapter {
  number: number; title: string; status: string; stages_present: string[]; has_brief: boolean; asset_count: number;
}
export interface ChapterStructureReport {
  ok: boolean; error_count: number; warning_count: number;
  project_path: string; story_state_path: string; manuscript_path: string;
  issues: ChapterStructureIssue[]; chapters: ChapterStructureChapter[];
}
export interface PlanOutlinePreview {
  outline: Record<string, unknown>;
  context_summary: string[];
  output_path: string;
}
export interface ChapterStages {
  number: number; status: string;
  outline: string | null; draft: string | null;
  revised: string | null; final: string | null;
  continuity: Record<string, unknown> | null;
}
export interface FinalResult {
  final: string; word_count: number;
}
export interface UnfinalizeResult {
  number: number; status: string;
  outline: string | null; draft: string | null;
  revised: string | null; final: string | null;
  word_count: number;
}
export interface EbookChapterPreview {
  number: number;
  title: string;
  word_count: number;
}

export interface EbookParsePreview {
  upload_id: string;
  filename: string;
  title: string;
  author: string;
  language: string;
  source_format: string;
  split_strategy: string;
  chapters: EbookChapterPreview[];
  total_words: number;
  notes: string[];
}

export interface ImportEbookBody {
  upload_id?: string;
  source_path?: string;
  title?: string;
  genre?: string;
  author?: string;
  project_id?: string;
  split_strategy?: string;
  parts?: number | null;
  synthesize?: boolean;
  no_extract?: boolean;
  from_chapter?: number | null;
  to_chapter?: number | null;
}
export interface JobStatus {
  job_id: string; kind: string;
  status: "running" | "done" | "error"; error: string | null;
  project_id?: string;
}
export interface JobCancelResult extends JobStatus {
  cancelled_jobs: number;
  batch_id?: string | null;
  batch_size?: number;
  started_at?: string | null;
  finished_at?: string | null;
}
export interface RegeneratePreview {
  text: string;
  source: string;
  original_word_count: number;
  preview_word_count: number;
  generated_at: string | null;
  instructions: string;
  placeholder_count?: number | null;
  scene_break_count?: number | null;
}
export interface SplitChapterPart {
  number: number;
  display_label: string;
  word_count: number;
}
export interface SplitChapterResult {
  parent_number: number;
  parts: SplitChapterPart[];
  total_words: number;
  recovered_from_backup?: boolean;
  alignments_applied?: number;
  chapters: ChapterSummary[];
}
export interface BoundaryAlignmentPreview {
  chapter_a: number;
  chapter_b: number;
  source: string;
  adjusted: boolean;
  direction: string | null;
  move_text: string;
  text_a: string;
  text_b: string;
  original_word_count_a: number;
  original_word_count_b: number;
  preview_word_count_a: number;
  preview_word_count_b: number;
  generated_at: string | null;
}
export interface RedraftPreview extends RegeneratePreview {
  mode: "align" | "preserve";
}
export interface RedraftFromBriefRequest {
  source: "final" | "draft" | "revised";
  mode: "align" | "preserve";
  instructions?: string;
}
export interface DuplicateMember {
  id: string;
  label: string;
  role?: string | null;
  thread_type?: string | null;
}
export interface DuplicateGroupModel {
  kind: string;
  confidence: number;
  reason: string;
  suggested_keep_id: string;
  members: DuplicateMember[];
}
export interface DuplicatesReport {
  characters: DuplicateGroupModel[];
  plot_threads: DuplicateGroupModel[];
  source: string;
  ai_scan_completed?: boolean;
  scanned_at?: string | null;
}
export interface SnapshotMeta {
  id: string; label: string; created_at: string; word_count: number; source: string;
}
export interface SnapshotText extends SnapshotMeta { text: string; }
export type AnnotationStage = "draft" | "revised" | "final" | "comment";

export interface CommentItem {
  id: string; body: string; quote: string; created_at: string; resolved: boolean;
  stage?: AnnotationStage;
  start_offset?: number | null;
  end_offset?: number | null;
  paragraph_hash?: string;
}

export interface AddCommentPayload {
  body: string;
  quote?: string;
  stage?: AnnotationStage;
  start_offset?: number | null;
  end_offset?: number | null;
  paragraph_hash?: string;
}
export interface CharacterSummary {
  id: string; full_name: string; role: string; aliases?: string[];
  portrait_url?: string | null;
}
export interface CharacterDetail extends CharacterSummary {
  age: number | null;
  physical_description: string;
  internal_desire: string;
  external_goal: string;
  fear: string;
  weakness: string;
  strength: string;
  secret: string;
  arc_stage: string;
  arc_progress: number;
  current_location: string;
  emotional_state: string;
  notes: string;
  aliases: string[];
  last_appearance_chapter: number;
  relationships?: Record<string, string>;
}
export interface MentionWarning {
  severity: string;
  category: string;
  message: string;
  suggestion?: string;
  chapter?: number | null;
  entity_id?: string | null;
}

export interface MentionFieldSuggestion {
  character_id: string;
  character_name: string;
  field: string;
  current_value?: string | number | string[] | null;
  suggested_value?: string | number | string[] | null;
  reason?: string;
  explicit_presence?: boolean;
  mention_label?: string;
  mention_raw?: string;
}

export interface MentionAnalysis {
  chapter_number: number;
  source: string;
  warnings: MentionWarning[];
  suggestions: MentionFieldSuggestion[];
  generated_at?: string | null;
}

export interface MentionApplyResult {
  log: string[];
  applied: number;
}

export interface CharacterGeneratePreview {
  character_id: string | null;
  prompt: string;
  hint_name: string;
  hint_role: string;
  updates: Partial<CharacterDetail>;
  generated_at: string | null;
}
export interface BibleDuplicateMember {
  id: string;
  section: string;
  index: number;
  label: string;
}
export interface BibleDuplicateGroup {
  section: string;
  confidence: number;
  reason: string;
  suggested_keep_index: number;
  members: BibleDuplicateMember[];
}
export interface BibleDuplicatesReport {
  groups: BibleDuplicateGroup[];
  source: string;
}
export interface BibleDedupeMerge {
  keep_section: string;
  keep_index: number;
  members: BibleDuplicateMember[];
  text_override?: string;
}
export interface BibleAutoDedupeResult {
  removed: number;
  log: string[];
  keep_text?: string;
}
export interface BibleDedupStatus {
  ai_suggestions_ready: boolean;
  ai_group_count: number;
}
export interface EntityDedupStatus {
  ai_suggestions_ready: boolean;
  ai_group_count: number;
  has_ai_file?: boolean;
  ai_scan_completed?: boolean;
  character_group_count?: number;
  plot_thread_group_count?: number;
}
export interface PlotThreadSummary {
  id: string; name: string; description: string;
  thread_type: string; status: string; priority: number;
  sort_order: number;
  subplots: string[];
}

export interface StoryGraphLayoutSummary {
  x: number;
  y: number;
}

export interface StoryGraphNodeSummary {
  id: string;
  kind: string;
  title: string;
  description: string;
  status: string;
  priority: number;
  linked_character_ids: string[];
  legacy_plot_thread_id: string;
  created_from: string;
  sort_order: number;
  start_chapter?: number;
  resolution_chapter?: number | null;
  layout?: StoryGraphLayoutSummary | null;
  act?: number;
  chapter_pins?: number[];
}

export interface StoryGraphEdgeSummary {
  id: string;
  source_id: string;
  target_id: string;
  kind: string;
  label: string;
}

export interface StoryGraphMigrateResult {
  nodes_created: number;
  edges_created: number;
  skipped: boolean;
}

export interface GraphDuplicateMember {
  id: string;
  label: string;
  node_kind?: string | null;
  legacy_plot_thread_id?: string | null;
}

export interface GraphDuplicateGroup {
  confidence: number;
  reason: string;
  suggested_keep_id: string;
  members: GraphDuplicateMember[];
}

export interface GraphDuplicatesReport {
  groups: GraphDuplicateGroup[];
  source: string;
}

export interface GraphDedupeMerge {
  keep_id: string;
  merge_ids: string[];
  title_override?: string;
}

export interface GraphAutoDedupeResult {
  merged: number;
  log: string[];
  keep_label?: string;
}

export interface EligibleGraphNodesResult {
  chapter_number: number;
  eligible: StoryGraphNodeSummary[];
  in_effect_ids: string[];
  out_of_range: StoryGraphNodeSummary[];
}

export interface ChapterBeatSummary {
  id: string;
  title: string;
  summary: string;
  sort_order: number;
  status: "planned" | "landed";
  linked_node_ids: string[];
}

export type CreateChapterBeatPayload = {
  title: string;
  summary?: string;
  status?: "planned" | "landed";
  linked_node_ids?: string[];
  sort_order?: number;
};

export type UpdateChapterBeatPayload = Partial<CreateChapterBeatPayload>;

export interface ChapterBriefSummary {
  chapter_number: number;
  pov_character_id: string;
  pov_mode: string;
  tone: string;
  tense: string;
  prose_style: string;
  vocabulary_level: string;
  style_notes: string;
  target_word_count: number;
  active_character_ids: string[];
  mentioned_character_ids?: string[];
  active_node_ids: string[];
  continuity_notes: string;
  ending_hook: string;
}

export type SaveChapterBriefPayload = Omit<ChapterBriefSummary, "chapter_number">;

export type ChapterContextPreviewMode = "outline" | "draft" | "revise" | "validation";

export interface ContextPreviewItem {
  key: string;
  label: string;
  body: string;
  reason: string;
  score: number;
}

export interface ContextPreviewSection {
  items: ContextPreviewItem[];
  omitted_count: number;
  omitted_labels: string[];
  omitted_reason: string;
}

export interface ContextPreviewCharacter {
  id: string;
  name: string;
}

export interface ContextPreviewBeat {
  id: string;
  title: string;
  status: "planned" | "landed" | string;
  summary: string;
}

export interface ChapterContextPreview {
  chapter_number: number;
  mode: string;
  bible: ContextPreviewSection;
  graph: ContextPreviewSection;
  active_characters: ContextPreviewCharacter[];
  mentioned_characters?: ContextPreviewCharacter[];
  beats: ContextPreviewBeat[];
}

export interface ChapterBeatCandidate {
  rank: number;
  beat: string;
  significance: string;
  involved_characters: string[];
  story_relevance: string;
  category: string;
}

export interface ChapterBeatCandidatesResult {
  chapter_number: number;
  source_used: string;
  candidates: ChapterBeatCandidate[];
}

export type MineKind = "plots" | "characters" | "bible";

export interface ChapterMinePreviewUiSummary {
  will_apply: string[];
  skipped: string[];
  proposed: string[];
  can_apply: boolean;
  advice: string;
}

export interface ChapterMinePreview {
  chapter_number: number;
  kind: MineKind;
  stage_source: string;
  source: string;
  changes: string[];
  report_path: string;
  ui_summary?: ChapterMinePreviewUiSummary | null;
}

export interface ChapterMinePreviewSummary {
  chapter_number: number;
  kind: MineKind;
  change_count: number;
}

export interface ApplyChapterMinePreviewResult {
  chapter_number: number;
  kind: MineKind;
  changes: string[];
}
export interface GenerateChapterBriefsResult {
  generated: ChapterBriefSummary[];
  skipped: { chapter: number; reason: string }[];
}
export interface GenerateChapterTitlesResult {
  generated: { chapter: number; title: string; title_source: string }[];
  skipped: { chapter: number; reason: string }[];
}
export interface BatchExtractOutlineStats {
  total_with_prose: number;
  missing_count: number;
  missing_chapters: number[];
  secondary_count?: number;
  secondary_chapters?: number[];
}
export interface TimelineEventSummary {
  id: string;
  description: string;
  chapter: number;
  day: number | null;
  time: string | null;
  location: string;
  characters_present: string[];
  event_type: string;
  significance: string;
}
export interface TimelineGeneratedEvent {
  description: string;
  chapter: number;
  day: number | null;
  time: string | null;
  location: string;
  characters_present: string[];
  event_type: string;
  significance: string;
  source: string;
  excerpt: string;
  score: number;
  reason: string;
}
export interface TimelineGenerationResult {
  source: string;
  recommended_per_chapter: number;
  chapters_scanned: number[];
  candidates: TimelineGeneratedEvent[];
  skipped_chapters: { chapter: number; reason: string }[];
}
export interface ResearchSparkSummary {
  id: string;
  title: string;
  body: string;
  source_url: string;
  tags: string[];
  kind: string;
  attachment_ref: string;
  link_character_id: string | null;
  link_chapter: number | null;
  link_plot_thread_id: string | null;
  link_bible_section: string | null;
  created_at: string;
  updated_at: string;
}
export interface ProjectMapSummary {
  id: string;
  name: string;
  image_url: string | null;
  pin_count: number;
  created_at: string;
  updated_at: string;
}
export interface MapPinSummary {
  id: string;
  map_id: string;
  label: string;
  x: number;
  y: number;
  lore_section: string;
  lore_label: string;
  notes: string;
  created_at: string;
  updated_at: string;
}
export interface ProjectMapDetail {
  id: string;
  name: string;
  image_url: string | null;
  created_at: string;
  updated_at: string;
  pins: MapPinSummary[];
}
export interface PlotPanelLocation {
  parent_id: string;
  parent_name: string;
  index: number;
  line: string;
}
export interface PlotPanelIssue {
  issue_id: string;
  kind: string;
  confidence: number;
  reason: string;
  subplot_line: string;
  locations: PlotPanelLocation[];
  thread_id: string | null;
  thread_name: string | null;
  suggested_parent_id: string;
  suggested_parent_name: string;
  suggested_action: string;
}
export interface PlotPanelIssuesReport {
  issues: PlotPanelIssue[];
  source: string;
}
export interface PlotGeneratePreview {
  thread_id: string;
  thread_name: string;
  prompt: string;
  description: string;
  previous_description: string;
  bible_suggestions: string[];
  generated_at: string | null;
}
export interface QuickSlotMeta {
  created_at: string;
  size_bytes: number;
}
export interface QuickBackupMeta {
  current?: QuickSlotMeta | null;
  previous?: QuickSlotMeta | null;
  pre_restore?: QuickSlotMeta | null;
}
export interface NamedBackupMeta {
  id: string;
  label: string;
  created_at: string;
  filename: string;
  size_bytes: number;
}
export interface BackupsReport {
  named: NamedBackupMeta[];
  quick: QuickBackupMeta;
}
export interface BackupActionResult {
  ok: boolean;
  message: string;
  quick?: QuickBackupMeta;
  backup?: NamedBackupMeta;
}

export interface SystemPromptSettings {
  prefix: string;
  agents_dir: string;
}

export type AgentPromptVariant = "current" | "recommended" | "custom";

export interface AgentPromptSetting {
  agent: string;
  label: string;
  selected_variant: AgentPromptVariant;
  current_default: string;
  recommended_default: string;
  custom_prompt: string;
  contract_guard: string;
}

export interface AgentPromptSettings {
  prompts: AgentPromptSetting[];
  agents_dir: string;
}

export interface LlmQueueEntry {
  id: string;
  label: string;
  submitted_at: string;
  chapter?: number | null;
  project_id?: string | null;
  function?: string | null;
  job_id?: string | null;
}

export interface RunningJobEntry {
  job_id: string;
  kind: string;
  label: string;
  started_at: string;
  project_id?: string | null;
  chapter?: number | null;
  screen?: string;
  batch_id?: string | null;
  batch_size?: number;
}

export interface LlmQueueSettings {
  max_concurrent: number;
  active: number;
  queued: number;
  flushed: boolean;
  active_items?: LlmQueueEntry[];
  queued_items?: LlmQueueEntry[];
  running_jobs?: RunningJobEntry[];
}

export interface RestartResult {
  status: string;
  message: string;
}

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json() as Promise<T>;
}

async function getOptional<T>(path: string): Promise<T | null> {
  const resp = await fetch(`${BASE}${path}`);
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json() as Promise<T>;
}

function jobBatchHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const batch = activeJobBatchId();
  if (batch) return { ...extra, "X-Job-Batch": batch };
  return extra;
}

async function send<T>(path: string, method: "POST" | "PUT" | "PATCH" | "DELETE", body?: unknown): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    method,
    headers: jobBatchHeaders(body ? { "Content-Type": "application/json" } : {}),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const j = await resp.json();
      if (j?.detail) detail = j.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return resp.json() as Promise<T>;
}

async function del(path: string): Promise<void> {
  const resp = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!resp.ok && resp.status !== 204) throw new Error(`${resp.status} ${resp.statusText}`);
}

export const api = {
  projects: () => get<ProjectSummary[]>("/api/projects"),
  project: (id: string) => get<ProjectDetail>(`/api/projects/${id}`),
  validateChapterStructure: (id: string) =>
    get<ChapterStructureReport>(`/api/projects/${id}/chapter-structure`),
  chapters: (id: string) => get<ChapterSummary[]>(`/api/projects/${id}/chapters`),
  chapter: (id: string, n: number) => get<ChapterDetail>(`/api/projects/${id}/chapters/${n}`),
  stages: (id: string, n: number) => get<ChapterStages>(`/api/projects/${id}/chapters/${n}/stages`),
  promoteFinal: (id: string, n: number) =>
    send<FinalResult>(`/api/projects/${id}/chapters/${n}/final/promote`, "POST"),
  saveFinal: (id: string, n: number, text: string) =>
    send<FinalResult>(`/api/projects/${id}/chapters/${n}/final`, "PUT", { text }),
  unfinalizeChapter: (id: string, n: number) =>
    send<UnfinalizeResult>(`/api/projects/${id}/chapters/${n}/final/unfinalize`, "POST"),
  createProject: (body: { title: string; genre: string; author: string }) =>
    send<ProjectSummary>("/api/projects", "POST", body),
  importStory: (body: {
    chapters_dir: string; title: string; genre: string; author?: string;
    project_id?: string; synthesize?: boolean; no_extract?: boolean;
  }) => send<JobStatus>("/api/import", "POST", body),
  previewImportEbook: async (file: File): Promise<EbookParsePreview> => {
    const resp = await fetch(`${BASE}/api/import/ebook/preview`, {
      method: "POST",
      headers: {
        "Content-Type": file.type || "text/plain",
        "X-Filename": file.name,
      },
      body: file,
    });
    if (!resp.ok) {
      let detail = `${resp.status} ${resp.statusText}`;
      try {
        const j = await resp.json();
        if (j?.detail) detail = j.detail;
      } catch { /* ignore */ }
      throw new Error(detail);
    }
    return resp.json() as Promise<EbookParsePreview>;
  },
  importEbook: (body: ImportEbookBody) =>
    send<JobStatus>("/api/import/ebook", "POST", body),
  deleteProject: (id: string) => del(`/api/projects/${id}`),
  stashed: () => get<StashedProjectSummary[]>("/api/stashed"),
  stashProject: (id: string) =>
    send<StashedProjectSummary>(`/api/projects/${id}/stash`, "POST"),
  restoreStashed: (id: string) =>
    send<ProjectSummary>(`/api/stashed/${id}/restore`, "POST"),
  updateProjectStyle: (id: string, body: Record<string, string>) =>
    send<ProjectDetail>(`/api/projects/${id}/style`, "PATCH", body),
  previewPlanOutline: (id: string, body: { chapters: number; words: number }) =>
    send<PlanOutlinePreview>(`/api/projects/${id}/outline/preview`, "POST", body),
  applyPlanOutline: (id: string, body: { chapters: number; words: number }) =>
    send<PlanOutlinePreview>(`/api/projects/${id}/outline/apply`, "POST", body),
  character: (id: string, charId: string) => get<CharacterDetail>(`/api/projects/${id}/characters/${charId}`),
  updateCharacter: (id: string, charId: string, body: Partial<CharacterDetail>) =>
    send<CharacterDetail>(`/api/projects/${id}/characters/${charId}`, "PATCH", body),
  uploadCharacterPortrait: async (id: string, charId: string, file: File): Promise<CharacterDetail> => {
    const resp = await fetch(`${BASE}/api/projects/${id}/characters/${charId}/portrait`, {
      method: "POST",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
    });
    if (!resp.ok) {
      let detail = `${resp.status} ${resp.statusText}`;
      try {
        const j = await resp.json();
        if (j?.detail) detail = j.detail;
      } catch { /* ignore */ }
      throw new Error(detail);
    }
    return resp.json() as Promise<CharacterDetail>;
  },
  removeCharacterPortrait: (id: string, charId: string) =>
    send<CharacterDetail>(`/api/projects/${id}/characters/${charId}/portrait`, "DELETE"),
  createChapter: (id: string, body: {
    number: number; title?: string; text?: string; extract?: boolean;
  }) => send<JobStatus | { number: number; word_count: number; changes: string[] }>(
    `/api/projects/${id}/chapters`, "POST", body,
  ),
  updateChapter: (id: string, n: number, body: Record<string, string>) =>
    send<ChapterSummary>(`/api/projects/${id}/chapters/${n}`, "PATCH", body),
  reassignChapter: (id: string, from: number, to: number) =>
    send<{
      action: string; from_number: number; to_number: number;
      chapter: ChapterSummary; swapped_with?: ChapterSummary;
    }>(`/api/projects/${id}/chapters/${from}/reassign`, "POST", { to_number: to }),
  insertChapterAt: (id: string, n: number, title = "") =>
    send<ChapterSequenceResult>(`/api/projects/${id}/chapters/insert`, "POST", { number: n, title }),
  duplicateChapter: (id: string, n: number, title = "") =>
    send<ChapterSequenceResult>(`/api/projects/${id}/chapters/${n}/duplicate`, "POST", { title }),
  mergeChapter: (id: string, keep: number, source: number) =>
    send<ChapterSequenceResult>(`/api/projects/${id}/chapters/${keep}/merge`, "POST", { source_number: source }),
  renumberChaptersSequential: (id: string) =>
    send<ChapterSequenceResult>(`/api/projects/${id}/chapters/renumber-sequential`, "POST"),
  saveDraft: (id: string, n: number, text: string) =>
    send<{ draft: string; word_count: number }>(`/api/projects/${id}/chapters/${n}/draft`, "PUT", { text }),
  saveOutline: (id: string, n: number, text: string) =>
    send<{ outline: string; word_count: number }>(`/api/projects/${id}/chapters/${n}/outline`, "PUT", { text }),
  saveRevised: (id: string, n: number, text: string) =>
    send<{ revised: string; word_count: number }>(`/api/projects/${id}/chapters/${n}/revised`, "PUT", { text }),
  extractChapter: (id: string, n: number) =>
    send<JobStatus>(`/api/projects/${id}/chapters/${n}/extract`, "POST"),
  mineChapter: (id: string, n: number, kind: MineKind, source = "draft") =>
    send<JobStatus>(`/api/projects/${id}/chapters/${n}/mine/${kind}?source=${encodeURIComponent(source)}`, "POST"),
  listChapterMinePreviews: (id: string, kind?: MineKind) =>
    get<ChapterMinePreviewSummary[]>(
      `/api/projects/${id}/chapters/mine-previews${kind ? `?kind=${encodeURIComponent(kind)}` : ""}`,
    ),
  getChapterMinePreview: (id: string, n: number, kind: MineKind) =>
    getOptional<ChapterMinePreview>(`/api/projects/${id}/chapters/${n}/mine/${kind}/preview`),
  discardChapterMinePreview: (id: string, n: number, kind: MineKind) =>
    del(`/api/projects/${id}/chapters/${n}/mine/${kind}/preview`),
  applyChapterMinePreview: (id: string, n: number, kind: MineKind) =>
    send<ApplyChapterMinePreviewResult>(`/api/projects/${id}/chapters/${n}/mine/${kind}/apply`, "POST"),
  regenerateChapter: (id: string, n: number, body: { source: string; instructions?: string }) =>
    send<JobStatus>(`/api/projects/${id}/chapters/${n}/regenerate`, "POST", body),
  getRegeneratePreview: (id: string, n: number) =>
    getOptional<RegeneratePreview>(`/api/projects/${id}/chapters/${n}/regenerate/preview`),
  applyRegenerate: (id: string, n: number, body: { text: string; target?: string }) =>
    send<{ target: string; word_count: number }>(
      `/api/projects/${id}/chapters/${n}/regenerate/apply`, "POST", body,
    ),
  discardRegenerate: (id: string, n: number) =>
    del(`/api/projects/${id}/chapters/${n}/regenerate/preview`),
  redraftFromBrief: (id: string, n: number, body: RedraftFromBriefRequest) =>
    send<JobStatus>(`/api/projects/${id}/chapters/${n}/redraft-from-brief`, "POST", body),
  getRedraftPreview: (id: string, n: number) =>
    getOptional<RedraftPreview>(`/api/projects/${id}/chapters/${n}/redraft-from-brief/preview`),
  applyRedraftPreview: (id: string, n: number, body: { text: string }) =>
    send<{ target: string; word_count: number }>(
      `/api/projects/${id}/chapters/${n}/redraft-from-brief/apply`, "POST", body,
    ),
  discardRedraftPreview: (id: string, n: number) =>
    del(`/api/projects/${id}/chapters/${n}/redraft-from-brief/preview`),
  expandPlaceholders: (id: string, n: number, body: { source: string; instructions?: string }) =>
    send<JobStatus>(`/api/projects/${id}/chapters/${n}/expand-placeholders`, "POST", body),
  getExpandPreview: (id: string, n: number) =>
    getOptional<RegeneratePreview>(`/api/projects/${id}/chapters/${n}/expand/preview`),
  applyExpandPreview: (id: string, n: number, body: { text: string; target?: string }) =>
    send<{ target: string; word_count: number }>(
      `/api/projects/${id}/chapters/${n}/expand/apply`, "POST", body,
    ),
  discardExpandPreview: (id: string, n: number) =>
    del(`/api/projects/${id}/chapters/${n}/expand/preview`),
  formatParagraphs: (id: string, n: number, body: { source: string }) =>
    send<JobStatus>(`/api/projects/${id}/chapters/${n}/format-paragraphs`, "POST", body),
  getParagraphsPreview: (id: string, n: number) =>
    getOptional<RegeneratePreview>(`/api/projects/${id}/chapters/${n}/paragraphs/preview`),
  applyParagraphsPreview: (id: string, n: number, body: { text: string; target?: string }) =>
    send<{ target: string; word_count: number }>(
      `/api/projects/${id}/chapters/${n}/paragraphs/apply`, "POST", body,
    ),
  discardParagraphsPreview: (id: string, n: number) =>
    del(`/api/projects/${id}/chapters/${n}/paragraphs/preview`),
  generateOutline: (id: string, n: number, body: { source: string; instructions?: string }) =>
    send<JobStatus>(`/api/projects/${id}/chapters/${n}/generate-outline`, "POST", body),
  getOutlinePreview: (id: string, n: number) =>
    getOptional<RegeneratePreview>(`/api/projects/${id}/chapters/${n}/generate-outline/preview`),
  applyOutlinePreview: (id: string, n: number, body: { text: string }) =>
    send<{ target: string; word_count: number }>(
      `/api/projects/${id}/chapters/${n}/generate-outline/apply`, "POST", body,
    ),
  discardOutlinePreview: (id: string, n: number) =>
    del(`/api/projects/${id}/chapters/${n}/generate-outline/preview`),
  splitChapter: (id: string, n: number, body: {
    source: string;
    max_words?: number;
    use_target_length?: boolean;
    align_boundaries?: boolean;
  }) =>
    send<SplitChapterResult>(`/api/projects/${id}/chapters/${n}/split`, "POST", body),

  alignBoundary: (id: string, n: number, body: { source: string }) =>
    send<JobStatus>(`/api/projects/${id}/chapters/${n}/align-boundary`, "POST", body),

  getAlignmentPreview: (id: string, n: number) =>
    getOptional<BoundaryAlignmentPreview>(`/api/projects/${id}/chapters/${n}/alignment/preview`),

  applyAlignmentPreview: (id: string, n: number, body: { text_a: string; text_b: string }) =>
    send<{ chapter_a: number; chapter_b: number; source: string; word_count_a: number; word_count_b: number }>(
      `/api/projects/${id}/chapters/${n}/alignment/apply`,
      "POST",
      body,
    ),

  discardAlignmentPreview: (id: string, n: number) =>
    del(`/api/projects/${id}/chapters/${n}/alignment/preview`),
  duplicates: (id: string, ai = false) =>
    get<DuplicatesReport>(`/api/projects/${id}/duplicates${ai ? "?ai=true" : ""}`),
  duplicatesStatus: (id: string) =>
    get<EntityDedupStatus>(`/api/projects/${id}/duplicates/status`),
  aiScanDuplicates: (id: string) =>
    send<JobStatus>(`/api/projects/${id}/duplicates/ai-scan`, "POST"),
  autoResolveDuplicates: (id: string) =>
    send<{ merged_characters: number; merged_plot_threads: number; log: string[] }>(
      `/api/projects/${id}/duplicates/auto-resolve`, "POST",
    ),
  mergeDuplicates: (id: string, body: {
    kind: string; keep_id: string; merge_ids: string[]; mode?: string; label_override?: string;
  }) =>
    send<{ kind: string; keep_id: string; merged: string[]; log: string[]; mode?: string; keep_label?: string }>(
      `/api/projects/${id}/duplicates/merge`, "POST", body,
    ),
  nestPlotThreads: (id: string, parentId: string, childIds: string[]) =>
    send<{ kind: string; keep_id: string; merged: string[]; log: string[]; mode?: string }>(
      `/api/projects/${id}/plot-threads/nest`, "POST", { parent_id: parentId, child_ids: childIds },
    ),
  backups: (id: string) => get<BackupsReport>(`/api/projects/${id}/backups`),
  createBackup: (id: string, label: string) =>
    send<NamedBackupMeta>(`/api/projects/${id}/backups`, "POST", { label }),
  restoreBackup: (id: string, backupId: string) =>
    send<BackupActionResult>(`/api/projects/${id}/backups/${backupId}/restore`, "POST"),
  deleteBackup: (id: string, backupId: string) =>
    del(`/api/projects/${id}/backups/${backupId}`),
  quickSaveBackup: (id: string) =>
    send<BackupActionResult>(`/api/projects/${id}/backups/quick-save`, "POST"),
  quickRestoreBackup: (id: string) =>
    send<BackupActionResult>(`/api/projects/${id}/backups/quick-restore`, "POST"),
  undoRestoreBackup: (id: string) =>
    send<BackupActionResult>(`/api/projects/${id}/backups/undo-restore`, "POST"),
  createPlotThread: (id: string, body: Record<string, unknown>) =>
    send<PlotThreadSummary>(`/api/projects/${id}/plot-threads`, "POST", body),
  updatePlotThread: (id: string, tid: string, body: Record<string, unknown>) =>
    send<PlotThreadSummary>(`/api/projects/${id}/plot-threads/${tid}`, "PATCH", body),
  reorderPlotThreads: (id: string, orderedIds: string[]) =>
    send<PlotThreadSummary[]>(`/api/projects/${id}/plot-threads/reorder`, "PUT", { ordered_ids: orderedIds }),
  storyBible: (id: string) => get<{ data: Record<string, unknown> }>(`/api/projects/${id}/story-bible`),
  updateStoryBible: (id: string, section: string, content: unknown) =>
    send<{ data: Record<string, unknown> }>(`/api/projects/${id}/story-bible`, "PATCH", { section, content }),
  extractBackground: (id: string, text: string, label: string) =>
    send<JobStatus>(`/api/projects/${id}/extract-background`, "POST", { text, label }),
  characters: (id: string) => get<CharacterSummary[]>(`/api/projects/${id}/characters`),
  addCharacter: (id: string, name: string, role: string) =>
    send<CharacterSummary[]>(`/api/projects/${id}/characters`, "POST", { name, role }),
  generateCharacter: (id: string, body: {
    prompt: string; character_id?: string; hint_name?: string; hint_role?: string;
  }) => send<JobStatus>(`/api/projects/${id}/characters/generate`, "POST", body),
  getCharacterGeneratePreview: (id: string) =>
    getOptional<CharacterGeneratePreview>(`/api/projects/${id}/characters/generate/preview`),
  discardCharacterGeneratePreview: (id: string) =>
    del(`/api/projects/${id}/characters/generate/preview`),
  bibleDuplicates: (id: string, ai = false) =>
    get<BibleDuplicatesReport>(`/api/projects/${id}/story-bible/duplicates${ai ? "?ai=true" : ""}`),
  bibleDedupStatus: (id: string) =>
    get<BibleDedupStatus>(`/api/projects/${id}/story-bible/duplicates/status`),
  aiScanBibleDuplicates: (id: string) =>
    send<JobStatus>(`/api/projects/${id}/story-bible/duplicates/ai-scan`, "POST"),
  autoDedupeBible: (id: string) =>
    send<BibleAutoDedupeResult>(`/api/projects/${id}/story-bible/duplicates/auto-resolve`, "POST"),
  mergeBibleDuplicates: (id: string, body: BibleDedupeMerge) =>
    send<BibleAutoDedupeResult>(`/api/projects/${id}/story-bible/duplicates/merge`, "POST", body),
  deleteCharacter: (id: string, charId: string) =>
    del(`/api/projects/${id}/characters/${charId}`),
  plotThreads: (id: string) => get<PlotThreadSummary[]>(`/api/projects/${id}/plot-threads`),
  storyGraphNodes: (id: string) =>
    get<StoryGraphNodeSummary[]>(`/api/projects/${id}/story-graph/nodes`),
  createStoryGraphNode: (id: string, body: {
    title: string;
    kind?: string;
    description?: string;
    status?: string;
    priority?: number;
    linked_character_ids?: string[];
    legacy_plot_thread_id?: string;
    sort_order?: number;
    start_chapter?: number;
    resolution_chapter?: number | null;
    layout?: StoryGraphLayoutSummary | null;
    act?: number;
    chapter_number?: number;
    assign_to_brief?: boolean;
  }) => send<StoryGraphNodeSummary>(`/api/projects/${id}/story-graph/nodes`, "POST", body),
  updateStoryGraphNode: (id: string, nodeId: string, body: Record<string, unknown>) =>
    send<StoryGraphNodeSummary>(`/api/projects/${id}/story-graph/nodes/${nodeId}`, "PATCH", body),
  deleteStoryGraphNode: (id: string, nodeId: string) =>
    del(`/api/projects/${id}/story-graph/nodes/${nodeId}`),
  storyGraphEdges: (id: string) =>
    get<StoryGraphEdgeSummary[]>(`/api/projects/${id}/story-graph/edges`),
  createStoryGraphEdge: (id: string, body: {
    source_id: string;
    target_id: string;
    kind?: string;
    label?: string;
  }) => send<StoryGraphEdgeSummary>(`/api/projects/${id}/story-graph/edges`, "POST", body),
  updateStoryGraphEdge: (id: string, edgeId: string, body: Record<string, unknown>) =>
    send<StoryGraphEdgeSummary>(`/api/projects/${id}/story-graph/edges/${edgeId}`, "PATCH", body),
  deleteStoryGraphEdge: (id: string, edgeId: string) =>
    del(`/api/projects/${id}/story-graph/edges/${edgeId}`),
  migrateStoryGraph: (id: string, force = false) =>
    send<StoryGraphMigrateResult>(`/api/projects/${id}/story-graph/migrate`, "POST", { force }),
  graphDuplicates: (id: string) =>
    get<GraphDuplicatesReport>(`/api/projects/${id}/story-graph/duplicates`),
  mergeGraphDuplicates: (id: string, body: GraphDedupeMerge) =>
    send<GraphAutoDedupeResult>(`/api/projects/${id}/story-graph/duplicates/merge`, "POST", body),
  autoResolveGraphDuplicates: (id: string) =>
    send<GraphAutoDedupeResult>(`/api/projects/${id}/story-graph/duplicates/auto-resolve`, "POST"),
  getEligibleGraphNodes: (id: string, chapterNumber: number) =>
    get<EligibleGraphNodesResult>(
      `/api/projects/${id}/chapters/${chapterNumber}/story-graph/eligible-nodes`,
    ),
  pinStoryGraphNode: (
    id: string,
    nodeId: string,
    body: { chapter_number: number; pinned?: boolean },
  ) =>
    send<StoryGraphNodeSummary>(
      `/api/projects/${id}/story-graph/nodes/${nodeId}/pin`,
      "POST",
      body,
    ),
  listChapterBeats: (id: string, chapterNumber: number) =>
    get<ChapterBeatSummary[]>(`/api/projects/${id}/chapters/${chapterNumber}/beats`),
  createChapterBeat: (id: string, chapterNumber: number, body: CreateChapterBeatPayload) =>
    send<ChapterBeatSummary>(
      `/api/projects/${id}/chapters/${chapterNumber}/beats`,
      "POST",
      body,
    ),
  updateChapterBeat: (
    id: string,
    chapterNumber: number,
    beatId: string,
    body: UpdateChapterBeatPayload,
  ) =>
    send<ChapterBeatSummary>(
      `/api/projects/${id}/chapters/${chapterNumber}/beats/${beatId}`,
      "PATCH",
      body,
    ),
  deleteChapterBeat: (id: string, chapterNumber: number, beatId: string) =>
    del(`/api/projects/${id}/chapters/${chapterNumber}/beats/${beatId}`),
  reorderChapterBeats: (id: string, chapterNumber: number, orderedIds: string[]) =>
    send<ChapterBeatSummary[]>(
      `/api/projects/${id}/chapters/${chapterNumber}/beats/reorder`,
      "PUT",
      { ordered_ids: orderedIds },
    ),
  setChapterBeats: (id: string, chapterNumber: number, beats: ChapterBeatSummary[]) =>
    send<ChapterBeatSummary[]>(
      `/api/projects/${id}/chapters/${chapterNumber}/beats`,
      "PUT",
      { beats },
    ),
  getChapterBrief: (id: string, chapterNumber: number) =>
    getOptional<ChapterBriefSummary>(`/api/projects/${id}/chapters/${chapterNumber}/brief`),
  saveChapterBrief: (id: string, chapterNumber: number, body: SaveChapterBriefPayload) =>
    send<ChapterBriefSummary>(`/api/projects/${id}/chapters/${chapterNumber}/brief`, "PUT", body),
  generateChapterBrief: (id: string, chapterNumber: number, body?: { source?: string; max_beats?: number }) =>
    send<ChapterBriefSummary>(`/api/projects/${id}/chapters/${chapterNumber}/brief/generate`, "POST", body ?? {}),
  generateChapterBriefs: (id: string, body?: {
    source?: string;
    max_beats?: number;
    overwrite_existing?: boolean;
  }) => send<GenerateChapterBriefsResult>(`/api/projects/${id}/chapters/briefs/generate`, "POST", body ?? {}),
  autoTitleChapterStats: (id: string) =>
    get<BatchExtractOutlineStats>(`/api/projects/${id}/batch/auto-title/stats`),
  generateChapterTitles: (id: string, body?: { source?: string; scope?: "eligible" | "auto_only" }) =>
    send<GenerateChapterTitlesResult>(`/api/projects/${id}/chapters/titles/generate`, "POST", body ?? {}),
  batchExtractOutlinesStats: (id: string, source = "best") =>
    get<BatchExtractOutlineStats>(
      `/api/projects/${id}/batch/extract-outlines/stats?source=${encodeURIComponent(source)}`,
    ),
  batchExtractCodexStats: (id: string, source = "best") =>
    get<BatchExtractOutlineStats>(
      `/api/projects/${id}/batch/extract-codex/stats?source=${encodeURIComponent(source)}`,
    ),
  batchExtractOutlines: (id: string, body?: {
    source?: string;
    skip_existing?: boolean;
    auto_accept?: boolean;
    chapters?: number[];
  }) => send<JobStatus>(`/api/projects/${id}/batch/extract-outlines`, "POST", body ?? {}),
  batchExtractCodex: (id: string, body?: {
    source?: string;
    skip_existing?: boolean;
    auto_accept?: boolean;
    chapters?: number[];
  }) => send<JobStatus>(`/api/projects/${id}/batch/extract-codex`, "POST", body ?? {}),
  deleteChapterBrief: (id: string, chapterNumber: number) =>
    del(`/api/projects/${id}/chapters/${chapterNumber}/brief`),
  getChapterContextPreview: (
    id: string,
    chapterNumber: number,
    mode: ChapterContextPreviewMode = "draft",
    brief?: SaveChapterBriefPayload,
  ) =>
    brief
      ? send<ChapterContextPreview>(
          `/api/projects/${id}/chapters/${chapterNumber}/context-preview`,
          "POST",
          { mode, ...brief },
        )
      : get<ChapterContextPreview>(
          `/api/projects/${id}/chapters/${chapterNumber}/context-preview?mode=${encodeURIComponent(mode)}`,
        ),
  generateChapterBeatCandidates: (id: string, chapterNumber: number, body?: {
    source?: string;
    count?: number;
  }) =>
    send<ChapterBeatCandidatesResult>(
      `/api/projects/${id}/chapters/${chapterNumber}/brief/beat-candidates`,
      "POST",
      body ?? {},
    ),
  generateChapterBeatCandidatesAsync: (id: string, chapterNumber: number, body?: {
    source?: string;
    count?: number;
  }) =>
    send<JobStatus>(
      `/api/projects/${id}/chapters/${chapterNumber}/brief/beat-candidates/async`,
      "POST",
      body ?? {},
    ),
  getChapterBeatCandidatesPreview: (id: string, chapterNumber: number) =>
    getOptional<ChapterBeatCandidatesResult>(
      `/api/projects/${id}/chapters/${chapterNumber}/brief/beat-candidates/preview`,
    ),
  discardChapterBeatCandidatesPreview: (id: string, chapterNumber: number) =>
    del(`/api/projects/${id}/chapters/${chapterNumber}/brief/beat-candidates/preview`),
  applyChapterBeatCandidates: (id: string, chapterNumber: number, body: {
    selected_beats: string[];
    mode?: "append" | "replace";
  }) =>
    send<ChapterBriefSummary>(
      `/api/projects/${id}/chapters/${chapterNumber}/brief/beat-candidates/apply`,
      "POST",
      body,
    ),
  timelineEvents: (id: string) => get<TimelineEventSummary[]>(`/api/projects/${id}/timeline`),
  createTimelineEvent: (id: string, body: Record<string, unknown>) =>
    send<TimelineEventSummary>(`/api/projects/${id}/timeline`, "POST", body),
  generateTimeline: (id: string, body: {
    chapters?: number[];
    source?: string;
    max_events_per_chapter?: number;
  }) => send<TimelineGenerationResult>(`/api/projects/${id}/timeline/generate`, "POST", body),
  applyGeneratedTimelineEvents: (id: string, events: TimelineGeneratedEvent[]) =>
    send<{ created: TimelineEventSummary[] }>(
      `/api/projects/${id}/timeline/generated-events`,
      "POST",
      { events },
    ),
  updateTimelineEvent: (id: string, eventId: string, body: Record<string, unknown>) =>
    send<TimelineEventSummary>(`/api/projects/${id}/timeline/${eventId}`, "PATCH", body),
  deleteAllTimelineEvents: (id: string) =>
    send<{ deleted: number }>(`/api/projects/${id}/timeline`, "DELETE"),
  deleteTimelineEvent: (id: string, eventId: string) =>
    del(`/api/projects/${id}/timeline/${eventId}`),
  researchSparks: (id: string, params?: { q?: string; tag?: string; kind?: string }) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.tag) qs.set("tag", params.tag);
    if (params?.kind) qs.set("kind", params.kind);
    const query = qs.toString();
    return get<ResearchSparkSummary[]>(
      `/api/projects/${id}/research${query ? `?${query}` : ""}`,
    );
  },
  createResearchSpark: (id: string, body: Record<string, unknown>) =>
    send<ResearchSparkSummary>(`/api/projects/${id}/research`, "POST", body),
  updateResearchSpark: (id: string, sparkId: string, body: Record<string, unknown>) =>
    send<ResearchSparkSummary>(`/api/projects/${id}/research/${sparkId}`, "PATCH", body),
  deleteResearchSpark: (id: string, sparkId: string) =>
    del(`/api/projects/${id}/research/${sparkId}`),
  projectMaps: (id: string) => get<ProjectMapSummary[]>(`/api/projects/${id}/maps`),
  createProjectMap: (id: string, body: { name?: string }) =>
    send<ProjectMapSummary>(`/api/projects/${id}/maps`, "POST", body),
  projectMap: (id: string, mapId: string) =>
    get<ProjectMapDetail>(`/api/projects/${id}/maps/${mapId}`),
  updateProjectMap: (id: string, mapId: string, body: Record<string, unknown>) =>
    send<ProjectMapSummary>(`/api/projects/${id}/maps/${mapId}`, "PATCH", body),
  deleteProjectMap: (id: string, mapId: string) =>
    del(`/api/projects/${id}/maps/${mapId}`),
  uploadMapImage: async (id: string, mapId: string, file: File): Promise<ProjectMapSummary> => {
    const resp = await fetch(`${BASE}/api/projects/${id}/maps/${mapId}/image`, {
      method: "POST",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
    });
    if (!resp.ok) {
      let detail = `${resp.status} ${resp.statusText}`;
      try {
        const j = await resp.json();
        if (j?.detail) detail = j.detail;
      } catch { /* ignore */ }
      throw new Error(detail);
    }
    return resp.json() as Promise<ProjectMapSummary>;
  },
  createMapPin: (id: string, mapId: string, body: Record<string, unknown>) =>
    send<MapPinSummary>(`/api/projects/${id}/maps/${mapId}/pins`, "POST", body),
  updateMapPin: (id: string, mapId: string, pinId: string, body: Record<string, unknown>) =>
    send<MapPinSummary>(`/api/projects/${id}/maps/${mapId}/pins/${pinId}`, "PATCH", body),
  deleteMapPin: (id: string, mapId: string, pinId: string) =>
    del(`/api/projects/${id}/maps/${mapId}/pins/${pinId}`),
  plotPanelIssues: (id: string) =>
    get<PlotPanelIssuesReport>(`/api/projects/${id}/plot-threads/panel-issues`),
  resolvePlotPanelIssue: (id: string, issueId: string) =>
    send<{ issue_id: string; log: string[] }>(
      `/api/projects/${id}/plot-threads/panel-issues/resolve`, "POST", { issue_id: issueId },
    ),
  autoResolvePlotPanelIssues: (id: string) =>
    send<{ resolved: number; log: string[] }>(
      `/api/projects/${id}/plot-threads/panel-issues/auto-resolve`, "POST",
    ),
  generatePlotThread: (id: string, threadId: string, body: { prompt?: string }) =>
    send<JobStatus>(`/api/projects/${id}/plot-threads/${threadId}/generate`, "POST", body),
  getPlotGeneratePreview: (id: string, threadId: string) =>
    getOptional<PlotGeneratePreview>(`/api/projects/${id}/plot-threads/${threadId}/generate/preview`),
  discardPlotGeneratePreview: (id: string, threadId: string) =>
    del(`/api/projects/${id}/plot-threads/${threadId}/generate/preview`),
  deletePlotThread: (id: string, threadId: string) =>
    del(`/api/projects/${id}/plot-threads/${threadId}`),
  deleteChapter: (id: string, n: number) => del(`/api/projects/${id}/chapters/${n}`),
  runPhase: (id: string, stage: string, params: Record<string, unknown> = {}) =>
    send<JobStatus>(`/api/projects/${id}/run`, "POST", { stage, params }),
  getJob: (jobId: string) => get<JobStatus>(`/api/jobs/${jobId}`),
  cancelJob: (jobId: string) => send<JobCancelResult>(`/api/jobs/${jobId}/cancel`, "POST"),
  exportUrl: (id: string) => `${BASE}/api/projects/${id}/export`,
  exportEpubUrl: (id: string) => `${BASE}/api/projects/${id}/export.epub`,
  exportProjectPackageUrl: (id: string) => `${BASE}/api/projects/${id}/export-package`,
  importProjectPackage: async (file: File): Promise<ProjectSummary> => {
    const resp = await fetch(`${BASE}/api/projects/import-package`, {
      method: "POST",
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": `attachment; filename="${file.name}"`,
      },
      body: file,
    });
    if (!resp.ok) {
      let detail = `${resp.status} ${resp.statusText}`;
      try {
        const j = await resp.json();
        if (j?.detail) detail = j.detail;
      } catch { /* ignore */ }
      throw new Error(detail);
    }
    return resp.json() as Promise<ProjectSummary>;
  },
  // snapshots
  snapshots: (id: string, n: number) =>
    get<SnapshotMeta[]>(`/api/projects/${id}/chapters/${n}/snapshots`),
  createSnapshot: (id: string, n: number, label: string) =>
    send<SnapshotMeta>(`/api/projects/${id}/chapters/${n}/snapshots`, "POST", { label }),
  getSnapshot: (id: string, n: number, sid: string) =>
    get<SnapshotText>(`/api/projects/${id}/chapters/${n}/snapshots/${sid}`),
  restoreSnapshot: (id: string, n: number, sid: string) =>
    send<FinalResult>(`/api/projects/${id}/chapters/${n}/snapshots/${sid}/restore`, "POST"),
  deleteSnapshot: (id: string, n: number, sid: string) =>
    del(`/api/projects/${id}/chapters/${n}/snapshots/${sid}`),
  // comments
  comments: (id: string, n: number) =>
    get<CommentItem[]>(`/api/projects/${id}/chapters/${n}/comments`),
  addComment: (
    id: string,
    n: number,
    bodyOrPayload: string | AddCommentPayload,
    quote = "",
  ) => {
    const payload: AddCommentPayload =
      typeof bodyOrPayload === "string"
        ? { body: bodyOrPayload, quote }
        : bodyOrPayload;
    return send<CommentItem>(`/api/projects/${id}/chapters/${n}/comments`, "POST", payload);
  },
  updateComment: (id: string, n: number, cid: string, resolved: boolean) =>
    send<CommentItem>(`/api/projects/${id}/chapters/${n}/comments/${cid}`, "PATCH", { resolved }),
  deleteComment: (id: string, n: number, cid: string) =>
    del(`/api/projects/${id}/chapters/${n}/comments/${cid}`),
  systemPromptSettings: () => get<SystemPromptSettings>("/api/settings/system-prompt"),
  saveSystemPromptSettings: (prefix: string) =>
    send<SystemPromptSettings>("/api/settings/system-prompt", "PUT", { prefix, agents_dir: "" }),
  agentPromptSettings: () => get<AgentPromptSettings>("/api/settings/agent-prompts"),
  saveAgentPromptSetting: (
    agent: string,
    body: { selected_variant: AgentPromptVariant; custom_prompt: string },
  ) => send<AgentPromptSettings>(`/api/settings/agent-prompts/${agent}`, "PUT", body),
  llmQueueSettings: () => get<LlmQueueSettings>("/api/settings/llm-queue"),
  saveLlmQueueSettings: (max_concurrent: number) =>
    send<LlmQueueSettings>("/api/settings/llm-queue", "PUT", { max_concurrent }),
  reorderLlmQueue: (order: string[]) =>
    send<LlmQueueSettings>("/api/settings/llm-queue/reorder", "POST", { order }),
  moveLlmQueueEntry: (entryId: string, position: "first" | "last") =>
    send<LlmQueueSettings>(`/api/settings/llm-queue/${entryId}/move`, "POST", { position }),
  cancelLlmQueueEntry: (entryId: string) =>
    send<LlmQueueSettings>(`/api/settings/llm-queue/${entryId}`, "DELETE"),
  restartNovelOs: () => send<RestartResult>("/api/system/restart", "POST"),
  mentionAnalysis: (id: string, n: number, source = "revised") =>
    get<MentionAnalysis>(`/api/projects/${id}/chapters/${n}/mentions/analysis?source=${encodeURIComponent(source)}`),
  suggestMentions: (id: string, n: number, body: { source?: string; use_llm?: boolean }) =>
    send<Record<string, unknown> | JobStatus>(
      `/api/projects/${id}/chapters/${n}/mentions/suggest`, "POST", body,
    ),
  getMentionSuggestions: (id: string, n: number) =>
    getOptional<Record<string, unknown>>(`/api/projects/${id}/chapters/${n}/mentions/suggestions`),
  applyMentionEdits: (id: string, n: number, edits: {
    character_id: string;
    field: string;
    value: string | number | string[] | null;
    explicit_presence?: boolean;
  }[]) =>
    send<MentionApplyResult>(`/api/projects/${id}/chapters/${n}/mentions/apply`, "POST", { edits }),
};

