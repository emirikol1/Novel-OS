/** Single source of truth for structured tooltips across Novel OS. */

export type ToolTipEntry = {
  label: string;
  function: string;
  worksOn: string;
  modifies: string;
  workflow: string;
  detail?: string;
};

export type ToolTipId =
  | "library.newManuscript"
  | "library.importProject"
  | "library.importEbook"
  | "library.help"
  | "library.togglePanel"
  | "library.openProject"
  | "library.stashManuscript"
  | "library.deleteManuscript"
  | "library.chapterCount"
  | "library.statusPill"
  | "dashboard.backToLibrary"
  | "dashboard.writingProgress"
  | "dashboard.validateStructure"
  | "dashboard.pipelineFilter"
  | "dashboard.exportManuscript"
  | "dashboard.exportEpub"
  | "dashboard.exportProject"
  | "dashboard.stashManuscript"
  | "dashboard.backups"
  | "dashboard.toggleLibrary"
  | "dashboard.deleteManuscript"
  | "dashboard.tabImporter"
  | "dashboard.tabChapters"
  | "dashboard.tabCast"
  | "dashboard.tabRelationships"
  | "dashboard.tabFamily"
  | "dashboard.tabPlots"
  | "dashboard.tabStoryGraph"
  | "dashboard.tabBlueprint"
  | "dashboard.tabTimeline"
  | "dashboard.tabResearch"
  | "dashboard.tabMap"
  | "dashboard.tabBible"
  | "dashboard.chapterStatusFilter"
  | "dashboard.clearFilter"
  | "dashboard.removeGaps"
  | "dashboard.chapterBoard"
  | "dashboard.chapterOutliner"
  | "dashboard.pasteChapter"
  | "dashboard.chapterStyleDefaults"
  | "dashboard.chapterTargetDefault"
  | "dashboard.planOutline"
  | "dashboard.planChapter"
  | "dashboard.generateChapterBriefs"
  | "dashboard.batchExtractOutlines"
  | "dashboard.batchExtractCodex"
  | "dashboard.populateChapterBriefs"
  | "dashboard.autoTitleChapters"
  | "dashboard.mineAll"
  | "dashboard.tabReviewableChanges"
  | "dashboard.reviewGraphSuggestions"
  | "dashboard.nextAction"
  | "chapter.generateDraft"
  | "chapter.revise"
  | "chapter.validate"
  | "chapter.approve"
  | "chapter.reviewMentions"
  | "chapter.reopen"
  | "chapter.regenerate"
  | "chapter.redraftFromBrief"
  | "chapter.redraftModeAlign"
  | "chapter.redraftModePreserve"
  | "chapter.expandPlaceholders"
  | "chapter.formatParagraphs"
  | "chapter.checkDialogueQuotes"
  | "chapter.alignBoundary"
  | "chapter.outlineFromNotes"
  | "chapter.outlineFromText"
  | "chapter.splitChapter"
  | "chapter.splitAtTargetAlign"
  | "chapter.minePlots"
  | "chapter.mineCharacters"
  | "chapter.mineBible"
  | "chapter.revisionNotes"
  | "chapter.applyNotesToOutline"
  | "chapter.outlineNotes"
  | "chapter.workflowHelp"
  | "chapter.promoteToFinal"
  | "chapter.copyRevisedToDraft"
  | "chapter.stageOutline"
  | "chapter.stageDraft"
  | "chapter.stageRevised"
  | "chapter.stageFinal"
  | "chapter.toggleBinder"
  | "chapter.toggleInspector"
  | "chapter.toggleLibrary"
  | "chapter.renumberChapter"
  | "chapter.insertBefore"
  | "chapter.insertAfter"
  | "chapter.duplicateChapter"
  | "chapter.mergeNext"
  | "chapter.extractMetadata"
  | "chapter.saveBrief"
  | "chapter.deleteBrief"
  | "chapter.previewKeep"
  | "chapter.previewDiscard"
  | "chapter.fontSizeDecrease"
  | "chapter.fontSizeIncrease"
  | "chapter.formatBold"
  | "chapter.formatItalic"
  | "chapter.formatHeading"
  | "chapter.formatQuote"
  | "chapter.formatSceneBreak"
  | "chapter.formatCharacter"
  | "chapter.formatLore"
  | "chapter.formatFind"
  | "chapter.formatAnnotate"
  | "chapter.mentionTips"
  | "chapter.inspectorSnapshots"
  | "chapter.inspectorNotes"
  | "chapter.saveSnapshot"
  | "chapter.snapshotDiff"
  | "chapter.snapshotRestore"
  | "chapter.snapshotDelete"
  | "chapter.addComment"
  | "chapter.resolveComment"
  | "chapter.deleteChapter"
  | "chapter.focusMode"
  | "chapter.typewriter"
  | "chapter.vanishing"
  | "chapter.readingWidth"
  | "chapter.writePreviewMode"
  | "chapter.bionicPreview"
  | "chapter.outlineEditor"
  | "chapter.contextPreview"
  | "chapter.generateBrief"
  | "chapter.landedBeats"
  | "chapter.resumeWorkflow"
  | "chapter.aiPreviewPending"
  | "chapter.mergeNextChapter"
  | "chapter.briefCharacterToggle"
  | "chapter.mentionRefresh"
  | "chapter.mentionApply"
  | "chapter.mentionClose"
  | "chapter.snapshotSave"
  | "chapter.commentAdd"
  | "chapter.commentResolve"
  | "chapter.commentDelete"
  | "chapter.commentFocusQuote"
  | "chapter.inspectorSnapshotsTab"
  | "chapter.inspectorCastTab"
  | "chapter.inspectorNotesTab"
  | "chapter.commentStageFilter"
  | "chapter.beatAdd"
  | "chapter.beatReorder"
  | "chapter.beatStatusToggle"
  | "chapter.beatDelete"
  | "chapter.graphAddPlot"
  | "chapter.graphNewPlot"
  | "chapter.graphPickerDone"
  | "chapter.landedBeatsApply"
  | "chapter.landedBeatsDiscard"
  | "chapter.landedBeatsGenerate"
  | "chapter.landedBeatsSelectAll"
  | "chapter.contextPreviewClose"
  | "chapter.briefCollapse"
  | "chapter.briefTargetLength"
  | "chapter.editorSave"
  | "chapter.graphRemoveNode"
  | "chapter.formatCharMention"
  | "chapter.formatLoreMention"
  | "chapter.formatFindReplace"
  | "codex.genericImporter"
  | "codex.addCharacter"
  | "codex.mergeCharactersManual"
  | "codex.resolveDuplicates"
  | "codex.addPlotThread"
  | "codex.mergePlotsParallel"
  | "codex.mergePlotsNest"
  | "codex.storyBibleDedup"
  | "codex.storyBibleSection"
  | "codex.timelineEvent"
  | "codex.researchSpark"
  | "codex.mapPin"
  | "codex.deleteCharacter"
  | "codex.deletePlotThread"
  | "codex.generatePlotSummary"
  | "codex.subplotIssues"
  | "codex.expandPlotThread"
  | "codex.editTimelineEvent"
  | "codex.uploadMap"
  | "codex.createMap"
  | "codex.deleteMap"
  | "codex.saveMapPin"
  | "codex.editMapPin"
  | "codex.saveResearchSpark"
  | "codex.removeCharacterPortrait"
  | "codex.removeCharacterRelationship"
  | "codex.plotThreadReorder"
  | "codex.timelineSelectCandidates"
  | "codex.createPlotFromBrief"
  | "codex.plotThreadExpand"
  | "codex.plotThreadDelete"
  | "codex.plotGenerateSummary"
  | "codex.deleteTimelineEvent"
  | "codex.deleteResearchSpark"
  | "codex.deleteMapPin"
  | "codex.saveTimelineEvent"
  | "codex.genealogyCharacter"
  | "codex.generateCharacter"
  | "graph.addNode"
  | "graph.linkNodes"
  | "graph.findDuplicates"
  | "graph.migrateFromPlots"
  | "graph.viewRadial"
  | "graph.viewActs"
  | "graph.viewTimeline"
  | "graph.fitView"
  | "graph.searchNodes"
  | "graph.chapterDrillDown"
  | "graph.inspector"
  | "graph.blueprintCanvas"
  | "graph.blueprintFilterNode"
  | "graph.addRelationship"
  | "graph.legacyPlotThreads"
  | "graph.editNode"
  | "graph.deleteEdge"
  | "graph.searchNodesPrevNext"
  | "graph.blueprintViewMode"
  | "graph.searchRelationships"
  | "graph.searchPrevNext"
  | "graph.inspectorEdit"
  | "graph.inspectorDeleteNode"
  | "graph.inspectorDeleteEdge"
  | "graph.linkCharacters"
  | "graph.mindMapZoom"
  | "graph.mindMapSearch"
  | "graph.mindMapFullscreen"
  | "graph.focusPicker"
  | "graph.editCharacter"
  | "global.sidebarLibrary"
  | "global.sidebarHelp"
  | "global.commandPalette"
  | "global.themeToggle"
  | "global.stashPanel"
  | "global.systemSettings"
  | "global.flushQueue"
  | "global.jobQueue"
  | "global.agentPrompts"
  | "global.unstashProject"
  | "global.testConnection"
  | "global.saveSettings"
  | "global.modalClose"
  | "global.retry"
  | "modal.dedupAiScan"
  | "modal.dedupMerge"
  | "modal.dedupManual"
  | "modal.pasteChapter"
  | "modal.planOutline"
  | "modal.backups"
  | "modal.minePreviewReview"
  | "modal.renumberChapter"
  | "modal.ebookImport"
  | "modal.cancel"
  | "modal.confirm"
  | "modal.dedupQuickScan"
  | "modal.dedupAutoMerge";

export const TOOL_REGISTRY: Record<ToolTipId, ToolTipEntry> = {
  // ── Library ──────────────────────────────────────────────────────────────
  "library.newManuscript": {
    label: "New Manuscript",
    function: "Creates a new project workspace with seeded Chapter 1, protagonist, and story-graph node.",
    worksOn: "Library — no project selected.",
    modifies: "Adds a project folder and navigates to its dashboard.",
    workflow: "Step 1 of getting started — establish canon before opening Manuscript Studio.",
  },
  "library.importProject": {
    label: "Import project",
    function: "Restores a Novel OS project package (.zip) exported from another install.",
    worksOn: "Library — uploads a zip archive.",
    modifies: "Creates a full project copy on disk and opens the dashboard.",
    workflow: "Use for backups, migration, or sharing project structure — not for raw manuscript paste.",
  },
  "library.importEbook": {
    label: "Import ebook",
    function: "Starts a background job to split an EPUB/MOBI into chapters inside a new or existing project.",
    worksOn: "Library — ebook file picker.",
    modifies: "Creates or fills chapter files; may add cast/worldbuilding stubs depending on import options.",
    workflow: "Bootstrap an existing draft — then refine outlines and run the pipeline per chapter.",
  },
  "library.help": {
    label: "Help",
    function: "Opens the workflow guide with chapter-pipeline order and feature boundaries.",
    worksOn: "Library header.",
    modifies: "Navigation only.",
    workflow: "Reference when unsure which control runs next in Outline → Draft → Revise → Validate → Approve → Final.",
  },
  "library.togglePanel": {
    label: "Library panel",
    function: "Shows or hides the global sidebar navigation strip.",
    worksOn: "Library and dashboard workspace chrome.",
    modifies: "Layout preference stored locally.",
    workflow: "Toggle for focused writing — binder and chapter content stay available in Manuscript Studio.",
  },
  "library.openProject": {
    label: "Open manuscript",
    function: "Navigates to the project dashboard for planning, codex tabs, and chapter board.",
    worksOn: "Project card in the library grid.",
    modifies: "Navigation only.",
    workflow: "Dashboard is the hub — open a chapter from the board when ready to draft.",
  },
  "library.stashManuscript": {
    label: "Stash manuscript",
    function: "Removes the project from the library grid while keeping files in the sidebar Stash lockbox.",
    worksOn: "Project card hover actions.",
    modifies: "Project visibility — files remain on disk until unstash or delete.",
    workflow: "Archive inactive drafts without deleting; restore from Stash in the sidebar.",
  },
  "library.deleteManuscript": {
    label: "Delete manuscript",
    function: "Permanently removes the project and all chapters, cast, and files.",
    worksOn: "Project card hover actions.",
    modifies: "Deletes project data — irreversible.",
    workflow: "Prefer Stash or Export project first if you might need the work later.",
  },
  "library.chapterCount": {
    label: "Chapter count",
    function: "Shows how many chapter records exist in the project summary.",
    worksOn: "Project card footer.",
    modifies: "Read-only indicator.",
    workflow: "Quick sanity check before opening the dashboard chapter board.",
  },
  "library.statusPill": {
    label: "Project status",
    function: "Displays coarse project lifecycle state from the project summary.",
    worksOn: "Project card footer.",
    modifies: "Read-only indicator.",
    workflow: "Complements per-chapter pipeline dots on the dashboard.",
  },

  // ── Dashboard ────────────────────────────────────────────────────────────
  "dashboard.backToLibrary": {
    label: "Back to Library",
    function: "Returns to the manuscript library grid.",
    worksOn: "Project dashboard header.",
    modifies: "Navigation only.",
    workflow: "Switch projects or create a new manuscript.",
  },
  "dashboard.writingProgress": {
    label: "Writing progress",
    function: "Summarizes completion percentage and finalized chapter count against total chapters.",
    worksOn: "Project dashboard — progress section.",
    modifies: "Read-only aggregate from chapter pipeline states.",
    workflow: "Use pipeline bucket chips below to jump to chapters at a specific stage.",
  },
  "dashboard.validateStructure": {
    label: "Validate structure",
    function: "Runs a project-wide check for chapter numbering gaps, missing files, and structural inconsistencies.",
    worksOn: "All chapters and on-disk manuscript layout.",
    modifies: "Read-only report — lists errors and warnings with links to fix.",
    workflow: "Run after renumbering, imports, or when health signals show gaps.",
  },
  "dashboard.pipelineFilter": {
    label: "Pipeline bucket",
    function: "Filters the chapter board to chapters at a specific pipeline step.",
    worksOn: "Chapter summaries grouped by pipeline_step.",
    modifies: "UI filter on the Chapters tab — does not change chapter data.",
    workflow: "Find chapters stuck at Draft, Revised, etc., then open each in Manuscript Studio.",
  },
  "dashboard.exportManuscript": {
    label: "Export manuscript",
    function: "Downloads a single Markdown file concatenating finalized chapter prose.",
    worksOn: "Final-stage chapter text on disk.",
    modifies: "Read-only export — no project changes.",
    workflow: "Share or archive the readable manuscript after Promote to Final.",
  },
  "dashboard.exportEpub": {
    label: "Export EPUB",
    function: "Builds an EPUB ebook from finalized chapters and project metadata.",
    worksOn: "Final chapters and project title/author.",
    modifies: "Read-only export.",
    workflow: "Proofreading and distribution — ensure Final exists for chapters you include.",
  },
  "dashboard.exportProject": {
    label: "Export project",
    function: "Downloads a full project package zip for backup or import on another machine.",
    worksOn: "Entire project folder.",
    modifies: "Read-only export.",
    workflow: "Backup before destructive operations or before major restructuring.",
  },
  "dashboard.stashManuscript": {
    label: "Stash manuscript",
    function: "Removes this project from the library and stores it in the sidebar Stash.",
    worksOn: "Current project.",
    modifies: "Library visibility — project files preserved.",
    workflow: "Same as library stash — use when pausing a draft without deleting.",
  },
  "dashboard.backups": {
    label: "Backups",
    function: "Opens the backup manager to list, create, or restore timestamped project snapshots.",
    worksOn: "Project backup store.",
    modifies: "Can restore prior project state when you confirm.",
    workflow: "Safety net before bulk renumber, import, or experimental AI runs.",
  },
  "dashboard.toggleLibrary": {
    label: "Library sidebar",
    function: "Shows or hides the global sidebar from the project workspace.",
    worksOn: "Layout chrome.",
    modifies: "Local layout preference.",
    workflow: "Maximize codex tab space on smaller screens.",
  },
  "dashboard.deleteManuscript": {
    label: "Delete manuscript",
    function: "Permanently deletes this project and all contained data.",
    worksOn: "Current project.",
    modifies: "Irreversible deletion.",
    workflow: "Export project or create a backup first unless you are certain.",
  },
  "dashboard.tabImporter": {
    label: "Generic Importer",
    function: "Paste unstructured text and extract characters, plot threads, bible entries, or chapter outlines.",
    worksOn: "Free-form pasted prose or notes.",
    modifies: "Creates or updates codex entities depending on extraction mode.",
    workflow: "Bootstrap cast and worldbuilding before binding arcs to chapter briefs.",
  },
  "dashboard.tabChapters": {
    label: "Chapters",
    function: "Chapter board and outliner — status, renumber, paste, and plan actions.",
    worksOn: "Chapter summaries and order.",
    modifies: "Chapter list UI; actions here change chapter records.",
    workflow: "Plan Chapter or open Manuscript Studio — compare pipeline dots to see drafting vs planning.",
  },
  "dashboard.tabCast": {
    label: "Cast",
    function: "Character roster with portraits, roles, and merge/dedup tools.",
    worksOn: "Character records.",
    modifies: "Cast entries — used in briefs, mentions, and prompts.",
    workflow: "Establish canon characters before mining or mention review in chapters.",
  },
  "dashboard.tabRelationships": {
    label: "Relationships",
    function: "Visual graph of labeled links between cast members.",
    worksOn: "Character relationship edges.",
    modifies: "Relationship records — edit labels in character editors.",
    workflow: "Planning aid — does not auto-enter chapter prompts unless copied to brief or bible.",
  },
  "dashboard.tabFamily": {
    label: "Family Tree",
    function: "Genealogy view of parent/child and family links between characters.",
    worksOn: "Character family fields.",
    modifies: "Family structure display — edit in character editors.",
    workflow: "Continuity reference for dynasty or lineage-heavy stories.",
  },
  "dashboard.tabPlots": {
    label: "Plot Threads (legacy)",
    function: "Original arc/subplot list — still written by Mine Plots; migrate to Story Graph when ready.",
    worksOn: "Legacy plot thread records.",
    modifies: "Plot thread entries.",
    workflow: "Fallback in prompts — chapter briefs prefer active Story Graph nodes.",
  },
  "dashboard.tabStoryGraph": {
    label: "Story Graph",
    function: "Primary planning mind map for arcs, subplots, beats, and chapter pins.",
    worksOn: "Graph nodes and edges.",
    modifies: "Story graph structure — active nodes feed chapter briefs and outlines.",
    workflow: "Bind arc to chapter via brief, then Outline from notes → Generate Draft.",
  },
  "dashboard.tabBlueprint": {
    label: "Blueprint",
    function: "Read-only board mapping chapters to outlines, briefs, and graph node coverage.",
    worksOn: "Chapter outlines, briefs, and graph nodes.",
    modifies: "Read-only planning view.",
    workflow: "Check which chapters mention a thread before drafting the next beat.",
  },
  "dashboard.tabTimeline": {
    label: "Timeline",
    function: "Manual chronology of in-story events with optional chapter links.",
    worksOn: "Timeline event records.",
    modifies: "Timeline entries — planning aid, not auto-injected into drafts.",
    workflow: "Track revealed vs hidden facts for fair mystery plotting.",
  },
  "dashboard.tabResearch": {
    label: "Research Board",
    function: "Tagged reference cards — promote chosen facts into bible or outline notes deliberately.",
    worksOn: "Research spark records.",
    modifies: "Research cards only — unused cards stay out of prompts.",
    workflow: "Copy selected research into outline notes when writing a chapter.",
  },
  "dashboard.tabMap": {
    label: "Map",
    function: "Pin locations on a project map image for geographic continuity.",
    worksOn: "Map pin records tied to places or scenes.",
    modifies: "Map annotations — reference for author, not automatic prompt input.",
    workflow: "Cross-check setting details when validating continuity.",
  },
  "dashboard.tabBible": {
    label: "Story Bible",
    function: "Canonical world rules, setting, themes, and durable facts.",
    worksOn: "Story bible sections.",
    modifies: "Canon memory used in context preview and validation.",
    workflow: "Promote only durable facts from mining — landed beats stay chapter-local.",
  },
  "dashboard.chapterStatusFilter": {
    label: "Status filter",
    function: "Narrows the chapter board/outliner to one pipeline step or shows all.",
    worksOn: "Chapter list on the Chapters tab.",
    modifies: "UI filter only.",
    workflow: "Pair with pipeline bucket chips on the progress section for quick triage.",
  },
  "dashboard.clearFilter": {
    label: "Clear filter",
    function: "Resets the chapter status filter to show all chapters again.",
    worksOn: "Chapter board/outliner on the Chapters tab.",
    modifies: "UI filter only.",
    workflow: "Use after triaging a pipeline bucket — returns to the full chapter list.",
  },
  "dashboard.removeGaps": {
    label: "Remove Gaps",
    function: "Renumbers chapters sequentially from 1 while preserving order; aborts if file collisions would occur.",
    worksOn: "Chapter numbers and on-disk chapter files.",
    modifies: "Chapter numbering and workflow/preview markers remapped.",
    workflow: "Fix gap warnings before Validate structure and export.",
  },
  "dashboard.chapterBoard": {
    label: "Board",
    function: "Kanban-style grid of chapter cards with pipeline status and quick actions.",
    worksOn: "Chapter summaries.",
    modifies: "Navigation and chapter management entry points.",
    workflow: "Default view for seeing draft progress across the manuscript.",
  },
  "dashboard.chapterOutliner": {
    label: "Outliner",
    function: "Compact list view of chapters with titles, status, and reorder controls.",
    worksOn: "Chapter summaries.",
    modifies: "Navigation — same data as Board, different layout.",
    workflow: "Use when scanning many chapters or checking consecutive numbering.",
  },
  "dashboard.pasteChapter": {
    label: "Paste Chapter",
    function: "Inserts pasted prose as a new chapter file at a chosen number.",
    worksOn: "Clipboard text.",
    modifies: "Creates chapter draft/outline files on disk.",
    workflow: "Import external prose — then run Outline from text or Revise in Manuscript Studio.",
  },
  "dashboard.chapterStyleDefaults": {
    label: "Chapter style defaults",
    function: "Sets project-wide POV, tense, tone, prose, and vocabulary defaults for new chapter briefs.",
    worksOn: "Project style defaults.",
    modifies: "Default brief fields — individual chapters can override.",
    workflow: "Configure once after creating the project, before Plan Chapter.",
  },
  "dashboard.chapterTargetDefault": {
    label: "Target length default",
    function: "Sets the default chapter word-count target used when a brief leaves target length blank.",
    worksOn: "Project style defaults modal.",
    modifies: "Default target_word_count for new chapter briefs.",
    workflow: "Set once at project setup — override per chapter in the brief panel.",
  },
  "dashboard.planOutline": {
    label: "Plan Outline…",
    function: "Runs the Architect to generate a multi-chapter outline preview for the whole book structure.",
    worksOn: "Project metadata, cast, and existing plans.",
    modifies: "Preview first — keep applies outline beats to chapter records.",
    workflow: "Macro planning before per-chapter Outline from notes in Manuscript Studio.",
  },
  "dashboard.planChapter": {
    label: "Plan Chapter",
    function: "Architect pass for the next chapter number — creates outline and brief scaffolding.",
    worksOn: "Project state and target chapter slot.",
    modifies: "Chapter outline/notes and may update brief.",
    workflow: "Bind arc to chapter — step 2 of structured workflow before Generate Draft.",
  },
  "dashboard.generateChapterBriefs": {
    label: "Generate chapter briefs",
    function: "AI-generates missing briefs from chapter text, cast, and graph nodes; skips existing briefs.",
    worksOn: "Chapters lacking saved briefs.",
    modifies: "Chapter brief records and graph-to-chapter mappings.",
    workflow: "Run after importing ebook or when briefs were never set — review before Redraft from brief.",
  },
  "dashboard.batchExtractOutlines": {
    label: "Extract all outlines",
    function: "Runs outline-from-text on every chapter with prose, one chapter at a time, saving previews for review.",
    worksOn: "All chapters with prose, or only those missing a saved outline / preview.",
    modifies: "Outline previews in outputs/feedback — apply from each chapter page.",
    workflow: "After import — choose Missing only or All chapters; long background job.",
    detail:
      "Sequential Architect passes per chapter. Long chapters use segmented outline extraction. " +
      "Nothing is written to canonical outline files until you keep a preview.",
  },
  "dashboard.batchExtractCodex": {
    label: "Extract all codex",
    function: "Mines plot threads, characters, and story bible from each chapter sequentially (3 passes per chapter).",
    worksOn: "All chapters with draft/revised/final text.",
    modifies: "Mine previews per chapter — apply from chapter page or dashboard review banners.",
    workflow: "Feed-back loop after import — expect hours on a full manuscript; review before applying.",
    detail:
      "Order per chapter: plots → characters → bible. Skips previews that already exist. " +
      "Use Cast, Plot Threads, and Story Bible tabs to review applied changes.",
  },
  "dashboard.populateChapterBriefs": {
    label: "Populate all chapter briefs",
    function: "AI-generates and saves chapter briefs from prose, cast, and Story Graph nodes for every chapter with text.",
    worksOn: "Chapters with prose — Missing skips chapters that already have a saved brief.",
    modifies: "Chapter brief records and graph-to-chapter mappings (saved directly, no preview step).",
    workflow: "After import or outline work — choose Missing or All, then confirm before running.",
  },
  "dashboard.autoTitleChapters": {
    label: "Auto-title chapters",
    function: "AI-generates short chapter titles from prose and saves them with title_source=auto.",
    worksOn: "Chapters with prose — All skips manually titled chapters; All auto-titles regenerates only prior auto titles.",
    modifies: "Chapter title and title_source in story state.",
    workflow: "After import — choose All eligible or All auto-titles, then confirm before running.",
  },
  "dashboard.mineAll": {
    label: "Mine All",
    function: "Runs the project-wide reviewable-changes mining foundation for missing outlines, missing briefs, or all supported suggestions.",
    worksOn: "Project chapters and structured planning data.",
    modifies: "Creates reviewable changes; auto-accept can apply suggestions that still need Review tab confirmation.",
    workflow: "Use after import or major drafting passes, then triage generated changes in Review.",
  },
  "dashboard.tabReviewableChanges": {
    label: "Review",
    function: "Opens the central inbox for pending, applied, reviewed, dismissed, reverted, and blocked AI-suggested changes.",
    worksOn: "Reviewable changes created by mining and graph suggestion jobs.",
    modifies: "Navigation only until you apply, dismiss, mark reviewed, or revert a change.",
    workflow: "Review before trusting generated graph, codex, outline, or brief updates as project memory.",
  },
  "dashboard.reviewGraphSuggestions": {
    label: "Generate graph suggestions",
    function: "Creates reviewable Story Graph suggestions from mined or inferred project structure.",
    worksOn: "Project graph and reviewable-change queue.",
    modifies: "Adds pending suggestions, or auto-applies them as applied-needs-review when enabled.",
    workflow: "Generate, inspect before/after fields, apply or mark reviewed from the Review tab.",
  },
  "dashboard.nextAction": {
    label: "Next action",
    function: "Suggests the highest-priority chapter and action from pipeline state.",
    worksOn: "Writing stats aggregate.",
    modifies: "Navigation link to Manuscript Studio.",
    workflow: "Follow the suggested chapter through Outline → Draft → Revise → Validate → Approve → Final.",
  },

  // ── Chapter (Manuscript Studio) ────────────────────────────────────────
  "chapter.generateDraft": {
    label: "Generate Draft",
    function: "Scribe agent expands the saved outline and chapter-brief context into first-pass prose.",
    worksOn: "Outline, chapter brief, and context preview selections.",
    modifies: "Draft stage text and pipeline status.",
    workflow: "Step 3 after outline is solid — safest order: Outline from notes → Generate Draft → Revise.",
  },
  "chapter.revise": {
    label: "Revise",
    function: "Editor agent line- and developmentally edits the best available prose into Revised.",
    worksOn: "Revised if present, otherwise Draft.",
    modifies: "Revised stage — Draft preserved as provenance snapshot.",
    workflow: "Run repeatedly — each pass reads your saved Revised, not Draft.",
  },
  "chapter.validate": {
    label: "Validate",
    function: "Continuity Guardian checks character, timeline, world, and plot consistency against canon.",
    worksOn: "Revised or Draft prose plus Story Bible and history.",
    modifies: "Validation report — may flag issues without changing prose.",
    workflow: "After editing Revised manually — before Approve and Promote to Final.",
  },
  "chapter.approve": {
    label: "Approve",
    function: "Marks the chapter as approved after validation passes your review.",
    worksOn: "Current chapter pipeline state.",
    modifies: "Pipeline status to Approved — prerequisite for treating prose as commit-ready.",
    workflow: "Validate → Approve → Promote to Final.",
  },
  "chapter.reviewMentions": {
    label: "Review mentions",
    function: "Opens mention-based memory updates and continuity warnings detected in chapter text.",
    worksOn: "@-mentions and guardian-detected entity references.",
    modifies: "Can apply cast/bible updates when you confirm each suggestion.",
    workflow: "After drafting — feed discoveries back without auto-writing canon.",
  },
  "chapter.reopen": {
    label: "Reopen for revision",
    function: "Clears Final lock and restores editable Revised/Draft workflow for an approved chapter.",
    worksOn: "Chapters with Final on file.",
    modifies: "Pipeline/final state — allows another Revise cycle.",
    workflow: "Use when Final needs another pass without losing prior draft provenance.",
  },
  "chapter.regenerate": {
    label: "Regenerate",
    function: "Scribe rewrite of existing prose using outline, brief, and optional revision notes — preview before keep.",
    worksOn: "Draft, Revised, or Final source text.",
    modifies: "Preview in outputs/feedback — Keep replaces target stage; Discard leaves canon unchanged.",
    workflow: "When Generate Draft missed the mark — adjust outline/brief first, then regenerate.",
    detail:
      "Destructive AI op with preview → keep/discard. Revision notes (and “apply to outline” when checked) steer the rewrite. " +
      "Review the side-by-side preview, edit if needed, then Keep to write the canonical artifact or Discard to abort.",
  },
  "chapter.redraftFromBrief": {
    label: "Redraft from brief",
    function: "Rewrites chapter prose to align with the saved chapter brief beats and active graph nodes.",
    worksOn: "Existing draft/revised/final text plus saved brief.",
    modifies: "Preview only until kept — replaces prose at chosen stage.",
    workflow: "When prose drifted from brief — save brief first, pick Align or Preserve mode, review preview.",
    detail:
      "Requires a saved brief with content. Align mode pushes prose toward brief beats; Preserve keeps more original wording. " +
      "Output lands in a redraft preview panel — edit, then Keep or Discard like Regenerate.",
  },
  "chapter.redraftModeAlign": {
    label: "Align",
    function: "Redraft mode that prioritizes matching brief beats, POV scope, and active graph nodes.",
    worksOn: "Redraft from brief job input.",
    modifies: "Influences redraft preview content only.",
    workflow: "Use when the draft missed structural intent but you want a fresh pass anchored to the brief.",
  },
  "chapter.redraftModePreserve": {
    label: "Preserve",
    function: "Redraft mode that keeps more of the existing prose while nudging toward brief requirements.",
    worksOn: "Redraft from brief job input.",
    modifies: "Influences redraft preview content only.",
    workflow: "Use for light realignment — less aggressive than Align.",
  },
  "chapter.expandPlaceholders": {
    label: "Expand placeholders",
    function: "Finds [[expand:…]] markers in prose and fills them with generated scene content.",
    worksOn: "Draft or Revised text containing expand markers.",
    modifies: "Preview until kept — replaces marked spans with expanded prose.",
    workflow: "Insert markers where you want the Scribe to elaborate, then expand and review.",
    detail:
      "Counts markers in the toolbar label. Each [[expand: hint]] becomes a targeted generation. " +
      "Preview shows the full chapter with expansions — edit, Keep to save, or Discard to revert.",
  },
  "chapter.formatParagraphs": {
    label: "AI Paragraphs",
    function: "Inserts paragraph breaks and optional scene-break lines (... on their own line) without changing any wording.",
    worksOn: "Draft, Revised, or Final prose for the active stage.",
    modifies: "Preview until kept — formatting only; rejects output that alters manuscript text.",
    workflow: "Run after import on dense blocks — review preview, then keep or discard. Do this before Fix chapter alignment.",
    detail:
      "Never fixes spelling or modernizes language. Scene breaks appear as a standalone line with three periods. "
      + "Validation blocks keep if the model changed any characters.",
  },
  "chapter.checkDialogueQuotes": {
    label: "Check dialogue quotes",
    function: "Checks dialogue quotation marks and broken source line-wrap hyphenation.",
    worksOn: "Draft, Revised, or Final prose for the active stage.",
    modifies: "Preview until kept — only double quotation marks, broken line-wrap hyphens, and related whitespace are allowed.",
    workflow: "Run near AI Paragraphs after imports or chapter splits, then review preview and keep or discard.",
    detail:
      "The model is told chapter edges may be cut off and must not complete fragments. "
      + "Validation blocks keep if words, normal hyphens, or non-quote punctuation changed.",
  },
  "chapter.alignBoundary": {
    label: "Fix chapter alignment",
    function: "Moves prose across the boundary with the next chapter so neither side breaks mid-sentence, mid-paragraph, or mid-thought.",
    worksOn: "End of this chapter and start of the next (same stage: draft, revised, or final).",
    modifies: "Preview until kept — updates both chapters; wording must stay identical.",
    workflow: "Run after AI Paragraphs or manual paragraph breaks — review both sides, then keep or discard.",
    detail:
      "The model sees only a few paragraphs around the split, not full chapters. Exact word counts may shift slightly. "
      + "Use when imports or mechanical splits landed in the middle of a sentence.",
  },
  "chapter.outlineFromNotes": {
    label: "From notes",
    function: "Regenerate outline source — uses outline notes and optional revision notes when “apply to outline” is checked.",
    worksOn: "Outline notes field in the Plan section.",
    modifies: "Outline preview — keep to replace the saved beat sheet.",
    workflow: "Choose From notes, then Regenerate outline and confirm.",
  },
  "chapter.outlineFromText": {
    label: "From text",
    function: "Regenerate outline source — reverse-engineers beats from existing draft, revised, or final prose.",
    worksOn: "Draft, Revised, or Final chapter text.",
    modifies: "Outline preview — keep to replace the saved beat sheet.",
    workflow: "Choose From text when prose exists but the beat sheet is stale — then Regenerate outline and confirm.",
  },
  "chapter.splitChapter": {
    label: "Split into parts",
    function: "Splits long chapter prose into sub-parts (1a, 1b…) at ~6,000 words each.",
    worksOn: "Current chapter draft/revised/final text.",
    modifies: "Creates new chapter parts and shifts numbering — briefs need regeneration.",
    workflow: "Oversized chapters only — expect to regenerate briefs and review part boundaries.",
  },
  "chapter.splitAtTargetAlign": {
    label: "Split at target & align",
    function: "Splits at the chapter brief / project target word count, then automatically aligns each new part boundary with AI.",
    worksOn: "Current chapter draft/revised/final text.",
    modifies: "Creates parts, shifts numbering, and rewrites boundaries between parts — run after paragraphs are set.",
    workflow: "Automatic — no preview. Best after AI Paragraphs. Regenerate briefs for new parts afterward.",
    detail:
      "Uses target length from the chapter brief (or project default). Each internal split is followed by boundary alignment "
      + "so parts do not break mid-thought. Exact word counts are approximate.",
  },
  "chapter.minePlots": {
    label: "Mine plots & subplots",
    function: "Extracts plot-thread updates from chapter prose into a reviewable preview.",
    worksOn: "Chapter text and existing plot threads.",
    modifies: "Preview — apply writes legacy plot threads; graph may need re-sync.",
    workflow: "Step 4 feed-back loop — review before apply, then migrate or sync Story Graph if needed.",
    detail:
      "Background job produces a chapter-scoped preview modal. Select which extractions to apply. " +
      "Plot mining writes to legacy Plot Threads — re-sync or migrate to Story Graph for structural planning.",
  },
  "chapter.mineCharacters": {
    label: "Mine characters",
    function: "Extracts character bio updates and arc notes from chapter prose.",
    worksOn: "Chapter text and cast records.",
    modifies: "Preview — apply updates matching character entries.",
    workflow: "After drafting — deliberate canon updates, not automatic on every chapter.",
    detail:
      "Opens ChapterMinePreviewModal when complete. Check each proposed change — only applied rows touch cast memory.",
  },
  "chapter.mineBible": {
    label: "Mine story bible",
    function: "Extracts durable world facts from chapter prose into bible sections.",
    worksOn: "Chapter text and Story Bible sections.",
    modifies: "Preview — apply merges into bible sections you confirm.",
    workflow: "Promote only stable facts — ephemeral beat details belong in landed beats, not bible.",
    detail:
      "Same preview → apply pattern as other mine tools. Bible entries persist across all future prompts and validation.",
  },
  "chapter.revisionNotes": {
    label: "Revision notes",
    function: "Free-text instructions fed to Revise, Regenerate, and optionally outline generation.",
    worksOn: "Pipeline AI jobs for this chapter.",
    modifies: "Prompt input only — does not change files until a job runs.",
    workflow: "E.g. “cut exposition, fix the ending” — pair with Revise or Regenerate.",
  },
  "chapter.applyNotesToOutline": {
    label: "Also apply revision notes to outline",
    function: "Appends revision notes to outline notes for Revise, Regenerate, and outline-from-notes/text jobs.",
    worksOn: "Combined notes payload sent to agents.",
    modifies: "Prompt input — can steer outline regeneration when checked.",
    workflow: "Use when structural fixes belong in the beat sheet, not just prose.",
  },
  "chapter.outlineNotes": {
    label: "Outline notes",
    function: "Author direction for beats, conflict, pacing, and ending hook — POV/style live on the brief.",
    worksOn: "Outline-from-notes and context for drafting.",
    modifies: "Saved with chapter — feeds Outline from notes and Generate Draft context.",
    workflow: "If Generate Draft feels generic, strengthen notes: POV, required beats, thread to advance, hook.",
  },
  "chapter.workflowHelp": {
    label: "Workflow help",
    function: "Jumps to Help guide chapter-pipeline section with step order and tips.",
    worksOn: "Navigation.",
    modifies: "None.",
    workflow: "Safest order: Outline from notes → Generate Draft → Revise → Validate → Approve → Promote to Final.",
  },
  "chapter.promoteToFinal": {
    label: "Promote to Final",
    function: "Copies the best AI stage (Revised preferred, else Draft) into the human-reviewed Final artifact.",
    worksOn: "Revised or Draft prose.",
    modifies: "Final stage — canonical manuscript for export.",
    workflow: "Last pipeline step after Approve — Final autosaves and supports direct editing.",
  },
  "chapter.copyRevisedToDraft": {
    label: "Copy Revised → Draft",
    function: "Optional one-way copy if you explicitly want Draft to match Revised.",
    worksOn: "Revised stage text.",
    modifies: "Overwrites Draft snapshot — Revise already prefers Revised without this.",
    workflow: "Rare — only when you need Draft and Revised synchronized for provenance.",
  },
  "chapter.stageOutline": {
    label: "Outline stage",
    function: "Beat-sheet outline editor — autosaves even after Final exists.",
    worksOn: "Chapter outline markdown.",
    modifies: "Outline artifact.",
    workflow: "Plan beats here before Generate Draft — edit anytime planning changes.",
  },
  "chapter.stageDraft": {
    label: "Draft stage",
    function: "First Scribe output — preserved as original snapshot during revision loops.",
    worksOn: "Draft prose.",
    modifies: "Draft text via editor or Generate Draft/Regenerate.",
    workflow: "Revise reads Revised when present — Draft stays as provenance.",
  },
  "chapter.stageRevised": {
    label: "Revised stage",
    function: "Editor output and your manual edits — source for subsequent Revise passes.",
    worksOn: "Revised prose.",
    modifies: "Revised text — autosaves on edit.",
    workflow: "Edit directly, then Revise again or Validate when satisfied.",
  },
  "chapter.stageFinal": {
    label: "Final stage",
    function: "Human-reviewed canonical chapter used in exports.",
    worksOn: "Final prose.",
    modifies: "Final text — promote from AI stages or edit directly.",
    workflow: "Validate → Approve → Promote — then export manuscript or EPUB from dashboard.",
  },
  "chapter.toggleBinder": {
    label: "Binder",
    function: "Shows or hides the chapter list sidebar in Manuscript Studio.",
    worksOn: "Layout.",
    modifies: "Local layout preference.",
    workflow: "Blue dot marks last-accessed chapter in the binder.",
  },
  "chapter.toggleInspector": {
    label: "Notes panel",
    function: "Opens snapshots and margin notes/comments for the current chapter.",
    worksOn: "Version history and annotations.",
    modifies: "Can restore snapshots or add comments.",
    workflow: "Snapshots for rollback — Notes for editorial comments tied to stages.",
  },
  "chapter.toggleLibrary": {
    label: "Library panel",
    function: "Toggles global sidebar visibility from Manuscript Studio.",
    worksOn: "Layout chrome.",
    modifies: "Local preference.",
    workflow: "Pair with Focus mode for distraction-free drafting.",
  },
  "chapter.renumberChapter": {
    label: "Renumber chapter",
    function: "Changes this chapter's number and shifts colliding chapters.",
    worksOn: "Single chapter file and order.",
    modifies: "Chapter numbering and on-disk paths — workflow markers remap.",
    workflow: "Use for insertions — or Remove Gaps on dashboard for bulk fix.",
  },
  "chapter.deleteChapter": {
    label: "Delete chapter",
    function: "Removes the chapter and its files from the project.",
    worksOn: "Current chapter record.",
    modifies: "Irreversible deletion of chapter artifacts.",
    workflow: "Confirm no Final export dependency before deleting.",
  },
  "chapter.focusMode": {
    label: "Focus mode",
    function: "Hides binder, pipeline, and side panels for full-width editing.",
    worksOn: "Manuscript editor layout.",
    modifies: "UI only.",
    workflow: "Exit focus to reach pipeline buttons or brief panel.",
  },
  "chapter.typewriter": {
    label: "Typewriter",
    function: "Keeps the cursor line near mid-screen while typing.",
    worksOn: "Manuscript editor scroll behavior.",
    modifies: "UI preference stored locally.",
    workflow: "Comfort feature during long drafting sessions.",
  },
  "chapter.vanishing": {
    label: "Vanishing",
    function: "Fades lines above the cursor for deep-focus writing.",
    worksOn: "Manuscript editor display.",
    modifies: "UI preference.",
    workflow: "Combine with Focus mode for minimal distraction.",
  },
  "chapter.readingWidth": {
    label: "Reading width",
    function: "Cycles column measure between narrow, normal, and wide.",
    worksOn: "Editor typography layout.",
    modifies: "Local display preference.",
    workflow: "Adjust for monitor size or proofreading comfort.",
  },
  "chapter.writePreviewMode": {
    label: "Write / Preview",
    function: "Switches between markdown editing and rendered preview.",
    worksOn: "Manuscript editor surface.",
    modifies: "UI mode — text unchanged.",
    workflow: "Preview to check formatting; Bionic available in preview mode.",
  },
  "chapter.bionicPreview": {
    label: "Bionic preview",
    function: "Emphasizes word starts in preview for faster reading.",
    worksOn: "Preview rendering only.",
    modifies: "Display — not saved to manuscript.",
    workflow: "Proofreading aid in preview mode.",
  },
  "chapter.outlineEditor": {
    label: "Chapter outline editor",
    function: "Direct beat-sheet editing with autosave and outline regeneration actions.",
    worksOn: "Outline markdown.",
    modifies: "Outline file.",
    workflow: "Regenerate from notes/text from toolbar when beats need AI refresh.",
  },
  "chapter.contextPreview": {
    label: "Context preview",
    function: "Shows which bible, graph, cast, and thread excerpts will enter the next agent prompt.",
    worksOn: "Chapter brief and pipeline mode budget.",
    modifies: "Read-only — omitted items are capped, not deleted from project.",
    workflow: "Check before Generate Draft when context feels thin or overloaded.",
  },
  "chapter.generateBrief": {
    label: "Generate chapter brief",
    function: "AI draft of POV, beats, cast toggles, and graph focus from chapter content.",
    worksOn: "Chapter text and project graph.",
    modifies: "Chapter brief when saved.",
    workflow: "Set before Redraft from brief or when opening a imported chapter.",
  },
  "chapter.landedBeats": {
    label: "Landed beats",
    function: "Chapter-local beat candidates extracted during writing — not global canon until promoted.",
    worksOn: "Chapter beat candidate preview.",
    modifies: "Chapter-local beat board when applied.",
    workflow: "Review landed beats — promote durable facts to Story Bible separately.",
  },
  "chapter.resumeWorkflow": {
    label: "Resume marker",
    function: "Blue dot on the last pipeline function you ran for this chapter.",
    worksOn: "Local workflow memory per chapter.",
    modifies: "UI indicator only.",
    workflow: "Pick up where you left off in Outline → Draft → Revise flow.",
  },
  "chapter.aiPreviewPending": {
    label: "AI preview pending",
    function: "Indicates a regenerate, outline, expand, or redraft preview awaits keep/discard review.",
    worksOn: "Pending preview files in outputs/feedback.",
    modifies: "Reminder only — chapter canon unchanged until you Keep.",
    workflow: "Finish review before starting conflicting pipeline jobs.",
  },
  "chapter.previewKeep": {
    label: "Keep preview",
    function: "Writes the edited preview text to the canonical chapter artifact (outline, draft, revised, or expanded prose).",
    worksOn: "Active AI preview panel for this chapter.",
    modifies: "Target stage file on disk — irreversible without snapshots or another AI pass.",
    workflow: "Edit preview if needed, then Keep — or Discard to leave canon unchanged.",
  },
  "chapter.previewDiscard": {
    label: "Discard preview",
    function: "Deletes the pending preview without changing saved outline or prose.",
    worksOn: "Active AI preview in outputs/feedback.",
    modifies: "Removes preview file only.",
    workflow: "Use when the AI pass missed the mark — adjust notes/brief and rerun the job.",
  },
  "chapter.insertBefore": {
    label: "Insert before",
    function: "Creates a blank chapter immediately before this one and shifts later numbers.",
    worksOn: "Chapter order and on-disk chapter files.",
    modifies: "Inserts empty chapter record — add outline and brief before drafting.",
    workflow: "Use when you need a new scene earlier in the sequence.",
  },
  "chapter.insertAfter": {
    label: "Insert after",
    function: "Creates a blank chapter immediately after this one.",
    worksOn: "Chapter order and on-disk chapter files.",
    modifies: "Inserts empty chapter record at the next slot.",
    workflow: "Split story structure without merging prose — pair with Plan Chapter or outline notes.",
  },
  "chapter.duplicateChapter": {
    label: "Duplicate chapter",
    function: "Copies this chapter's files and metadata into a new chapter inserted after it.",
    worksOn: "Current chapter artifacts (outline, draft, brief, etc.).",
    modifies: "Creates a sibling chapter — review numbering and brief bindings.",
    workflow: "Template a similar scene — then edit outline and brief for the copy.",
  },
  "chapter.mergeNextChapter": {
    label: "Merge next chapter",
    function: "Combines the next chapter's prose into this one and removes the next chapter.",
    worksOn: "This chapter and the immediately following chapter.",
    modifies: "Destructive merge — both chapters' snapshots are cleared; renumber if gaps remain.",
    workflow: "Last resort for accidental splits — export or snapshot first.",
  },
  "chapter.mergeNext": {
    label: "Merge next chapter",
    function: "Combines the next chapter's prose into this one and removes the next chapter.",
    worksOn: "This chapter and the immediately following chapter.",
    modifies: "Destructive merge — both chapters' snapshots are cleared; renumber if gaps remain.",
    workflow: "Last resort for accidental splits — export or snapshot first.",
  },
  "chapter.extractMetadata": {
    label: "Extract metadata (legacy)",
    function: "Retired from the draft editor — use Codex sync under Chapter Brief and Operations instead.",
    worksOn: "Was draft-only one-shot extract.",
    modifies: "Codex sync mines run per domain with a review modal before anything is applied.",
    workflow: "Open brief → Codex sync → Plots, Characters, or Story bible.",
  },
  "chapter.saveBrief": {
    label: "Save brief",
    function: "Persists POV, style, cast toggles, graph focus, and beat board selections for prompts.",
    worksOn: "Chapter brief draft fields.",
    modifies: "Saved brief — required before Redraft from brief and context preview.",
    workflow: "Set brief after Plan Chapter or import — save before Generate Draft.",
  },
  "chapter.briefCollapse": {
    label: "Chapter brief and operations",
    function: "Expands or collapses the chapter brief editor and chapter operations (insert, duplicate, renumber, merge, delete). When expanded, hides the pipeline, workflow toolbar, and manuscript editor until collapsed again.",
    worksOn: "Brief panel visibility and studio layout.",
    modifies: "UI only — brief content unchanged.",
    workflow: "Click Expand to edit POV, cast, graph focus, and chapter structure — Collapse to return to drafting.",
  },
  "chapter.briefTargetLength": {
    label: "Brief target length",
    function: "Sets this chapter's word-count target for drafting prompts — blank inherits project default.",
    worksOn: "Chapter brief target_word_count field.",
    modifies: "Brief only — affects Generate Draft and Redraft length guidance.",
    workflow: "Override project default for unusually short or long chapters.",
  },
  "chapter.editorSave": {
    label: "Manual save",
    function: "Immediately persists unsaved editor changes instead of waiting for autosave.",
    worksOn: "Dirty beat board or plot thread editor state.",
    modifies: "Writes current draft to disk on demand.",
    workflow: "Use before switching tabs if you need changes saved right away.",
  },
  "chapter.deleteBrief": {
    label: "Delete brief",
    function: "Removes the saved chapter brief for this chapter.",
    worksOn: "Chapter brief record.",
    modifies: "Clears brief — outline/draft prompts lose POV and graph context until regenerated.",
    workflow: "Use when rebinding from scratch — Generate chapter brief to recreate.",
  },
  "chapter.briefCharacterToggle": {
    label: "Cast presence toggle",
    function: "Cycles each character: not in chapter → mentioned → active → not in chapter.",
    worksOn: "Chapter brief cast presence fields.",
    modifies: "Brief only — does not edit cast bios.",
    workflow: "Mark who is on-page vs referenced — active cast feeds drafting prompts.",
  },
  "chapter.mentionRefresh": {
    label: "Refresh mention suggestions",
    function: "Re-scans chapter prose for @-mentions and heuristic memory update suggestions.",
    worksOn: "Resolved mentions in draft/revised/final text.",
    modifies: "Refreshes suggestion table — nothing applied until you confirm.",
    workflow: "Run after editing mentions inline — then review and apply approved rows.",
  },
  "chapter.mentionApply": {
    label: "Apply mention edits",
    function: "Writes approved field updates to cast memory from the mention review table.",
    worksOn: "Checked rows in mention review.",
    modifies: "Character fields (appearance, knowledge, last chapter, etc.).",
    workflow: "Deliberate canon updates — step after Review mentions opens this panel.",
  },
  "chapter.mentionClose": {
    label: "Close mention review",
    function: "Hides the mention review panel without applying pending edits.",
    worksOn: "Mention review UI.",
    modifies: "Navigation only.",
    workflow: "Reopen via Review mentions when ready to apply changes.",
  },
  "chapter.snapshotSave": {
    label: "Save version snapshot",
    function: "Captures the current Final text as a labeled rollback point.",
    worksOn: "Final-stage prose after flush.",
    modifies: "Adds snapshot to version history in the Notes panel.",
    workflow: "Before risky Final edits or promote — restore replaces Final and saves prior as snapshot.",
  },
  "chapter.saveSnapshot": {
    label: "Save version snapshot",
    function: "Captures the current Final text as a labeled rollback point.",
    worksOn: "Final-stage prose after flush.",
    modifies: "Adds snapshot to version history in the Notes panel.",
    workflow: "Before risky Final edits or promote — restore replaces Final and saves prior as snapshot.",
  },
  "chapter.snapshotDiff": {
    label: "Diff snapshot",
    function: "Shows side-by-side diff between a saved snapshot and current Final text.",
    worksOn: "Selected snapshot vs live Final.",
    modifies: "Read-only comparison.",
    workflow: "Verify changes before restore or after a long editing session.",
  },
  "chapter.snapshotRestore": {
    label: "Restore snapshot",
    function: "Replaces Final prose with a saved snapshot; current Final is preserved as a new snapshot.",
    worksOn: "Selected version snapshot.",
    modifies: "Final text on disk.",
    workflow: "Rollback after bad edits — previous Final remains recoverable as a snapshot.",
  },
  "chapter.snapshotDelete": {
    label: "Delete snapshot",
    function: "Permanently removes a saved version from history.",
    worksOn: "Selected snapshot record.",
    modifies: "Irreversible deletion of that snapshot.",
    workflow: "Prune old versions after confirming you no longer need rollback.",
  },
  "chapter.commentAdd": {
    label: "Add note",
    function: "Creates a margin note or manuscript annotation tied to optional quoted text.",
    worksOn: "Notes panel composer.",
    modifies: "Chapter comments/annotations list.",
    workflow: "Editorial notes for yourself — manuscript annotations link to preview offsets.",
  },
  "chapter.addComment": {
    label: "Add note",
    function: "Creates a margin note or manuscript annotation tied to optional quoted text.",
    worksOn: "Notes panel composer.",
    modifies: "Chapter comments/annotations list.",
    workflow: "Editorial notes for yourself — manuscript annotations link to preview offsets.",
  },
  "chapter.commentResolve": {
    label: "Resolve note",
    function: "Marks a note as resolved or reopens it for follow-up.",
    worksOn: "Individual note records.",
    modifies: "Resolved flag — note text preserved.",
    workflow: "Triage editorial feedback without deleting history.",
  },
  "chapter.resolveComment": {
    label: "Resolve note",
    function: "Marks a note as resolved or reopens it for follow-up.",
    worksOn: "Individual note records.",
    modifies: "Resolved flag — note text preserved.",
    workflow: "Triage editorial feedback without deleting history.",
  },
  "chapter.commentDelete": {
    label: "Delete note",
    function: "Permanently removes a note or annotation.",
    worksOn: "Individual note record.",
    modifies: "Irreversible deletion.",
    workflow: "Clean up resolved or mistaken notes.",
  },
  "chapter.commentFocusQuote": {
    label: "Focus quoted passage",
    function: "Jumps manuscript preview to the annotated text range for this note.",
    worksOn: "Manuscript annotations with offsets.",
    modifies: "UI focus and stage selection.",
    workflow: "Navigate from Notes panel back to the passage in preview.",
  },
  "chapter.inspectorSnapshotsTab": {
    label: "Snapshots tab",
    function: "Shows version history and rollback controls for Final prose.",
    worksOn: "Notes panel (inspector).",
    modifies: "Tab selection only.",
    workflow: "Save versions before major Final edits — pair with Restore.",
  },
  "chapter.inspectorCastTab": {
    label: "Cast tab",
    function: "Browse project cast and open character bios while you write.",
    worksOn: "Notes panel (inspector).",
    modifies: "Tab selection only.",
    workflow: "Check appearance, goals, and relationships without leaving the chapter.",
  },
  "chapter.inspectorSnapshots": {
    label: "Snapshots tab",
    function: "Shows version history and rollback controls for Final prose.",
    worksOn: "Notes panel (inspector).",
    modifies: "Tab selection only.",
    workflow: "Save versions before major Final edits — pair with Restore.",
  },
  "chapter.inspectorNotesTab": {
    label: "Notes tab",
    function: "Shows chapter comments, annotations, and stage filters.",
    worksOn: "Notes panel (inspector).",
    modifies: "Tab selection only.",
    workflow: "Track editorial feedback across Draft, Revised, and Final.",
  },
  "chapter.inspectorNotes": {
    label: "Notes tab",
    function: "Shows chapter comments, annotations, and stage filters.",
    worksOn: "Notes panel (inspector).",
    modifies: "Tab selection only.",
    workflow: "Track editorial feedback across Draft, Revised, and Final.",
  },
  "chapter.commentStageFilter": {
    label: "Note stage filter",
    function: "Narrows the notes list to one manuscript stage or shows all.",
    worksOn: "Chapter comments list.",
    modifies: "UI filter only.",
    workflow: "Focus on Revised notes while editing that stage.",
  },
  "chapter.beatAdd": {
    label: "Add beat",
    function: "Creates a new planned beat on the chapter-local beat board.",
    worksOn: "Chapter beat board.",
    modifies: "Adds beat record — autosaves title and summary.",
    workflow: "Plan must-happen events before Generate Draft — distinct from global Story Graph.",
  },
  "chapter.beatReorder": {
    label: "Reorder beat",
    function: "Drag handle to change beat order on the chapter board.",
    worksOn: "Chapter beat sort order.",
    modifies: "Beat sequence — feeds brief and prompt ordering.",
    workflow: "Align beat order with outline before drafting.",
  },
  "chapter.beatStatusToggle": {
    label: "Beat status",
    function: "Switches a beat between planned (intent) and landed (already on the page).",
    worksOn: "Individual chapter beat.",
    modifies: "Beat status field.",
    workflow: "Mark beats as landed after writing — or keep planned for upcoming drafts.",
  },
  "chapter.beatDelete": {
    label: "Delete beat",
    function: "Removes a beat from the chapter board.",
    worksOn: "Individual chapter beat.",
    modifies: "Irreversible beat deletion.",
    workflow: "Prune beats that no longer belong in this chapter.",
  },
  "chapter.graphAddPlot": {
    label: "Add plot to chapter",
    function: "Opens picker to attach existing Story Graph nodes to this chapter brief.",
    worksOn: "Active graph node selection on brief.",
    modifies: "Brief graph focus — nodes feed outline and draft prompts.",
    workflow: "Bind arcs before Outline from notes — requires graph nodes to exist.",
  },
  "chapter.graphNewPlot": {
    label: "New plot from brief",
    function: "Creates a new Story Graph node and adds it to this chapter's active plots.",
    worksOn: "Story Graph and chapter brief.",
    modifies: "New graph node plus brief selection.",
    workflow: "Quick-add a subplot while planning — refine node in Story Graph tab later.",
  },
  "chapter.graphPickerDone": {
    label: "Done adding plots",
    function: "Closes the plot picker modal and keeps current selections.",
    worksOn: "Graph focus picker modal.",
    modifies: "Modal only — selections already saved on brief.",
    workflow: "After checking active nodes — save brief to persist.",
  },
  "chapter.graphRemoveNode": {
    label: "Remove graph node from brief",
    function: "Detaches a Story Graph node from this chapter's active plot focus.",
    worksOn: "Chapter brief graph node chips.",
    modifies: "Brief active_nodes — node remains in Story Graph.",
    workflow: "Narrow chapter scope without deleting the arc from the project graph.",
  },
  "chapter.landedBeatsApply": {
    label: "Apply landed beats",
    function: "Adds selected beat candidates from prose scan to the chapter beat board as landed.",
    worksOn: "Landed beat candidate preview.",
    modifies: "Chapter beat board — append mode.",
    workflow: "Review Archivist candidates — promote durable facts to Story Bible separately.",
  },
  "chapter.landedBeatsDiscard": {
    label: "Discard landed beats preview",
    function: "Closes landed beat candidate preview without adding beats to the board.",
    worksOn: "Beat candidate preview file.",
    modifies: "Deletes preview — beat board unchanged.",
    workflow: "Regenerate or edit prose before re-extracting.",
  },
  "chapter.landedBeatsGenerate": {
    label: "Extract landed beats",
    function: "Queues Archivist scan for beats already present in chapter prose.",
    worksOn: "Draft, revised, or final manuscript text.",
    modifies: "Preview candidates — apply to beat board when ready.",
    workflow: "Feed-back after drafting — does not auto-update Story Bible.",
  },
  "chapter.landedBeatsSelectAll": {
    label: "Select all landed beat candidates",
    function: "Toggles selection of all extracted beat candidates for apply.",
    worksOn: "Landed beat candidate checklist.",
    modifies: "Selection state only.",
    workflow: "Bulk-apply when every candidate looks correct.",
  },
  "chapter.contextPreviewClose": {
    label: "Close context preview",
    function: "Closes the read-only modal showing prompt budget excerpts.",
    worksOn: "Context preview modal.",
    modifies: "Navigation only.",
    workflow: "Return to brief editing — adjust cast or graph focus if context looks thin.",
  },
  "chapter.formatBold": {
    label: "Bold",
    function: "Wraps selection with Markdown bold (**text**).",
    worksOn: "Manuscript editor selection in write mode.",
    modifies: "Draft, revised, or final text at cursor.",
    workflow: "Inline formatting — preview mode shows rendered bold.",
  },
  "chapter.formatItalic": {
    label: "Italic",
    function: "Wraps selection with Markdown italic (*text*).",
    worksOn: "Manuscript editor selection.",
    modifies: "Prose at cursor.",
    workflow: "Emphasis and interior thought — pair with preview to verify rendering.",
  },
  "chapter.formatHeading": {
    label: "Heading",
    function: "Prefixes the current line with a level-2 Markdown heading (## ).",
    worksOn: "Current line in manuscript editor.",
    modifies: "Line prefix in prose.",
    workflow: "Scene or section breaks within a chapter.",
  },
  "chapter.formatQuote": {
    label: "Block quote",
    function: "Prefixes the current line with Markdown blockquote (> ).",
    worksOn: "Current line in manuscript editor.",
    modifies: "Line prefix in prose.",
    workflow: "Letters, documents, or excerpted text in scene.",
  },
  "chapter.formatSceneBreak": {
    label: "Scene break",
    function: "Inserts a horizontal rule (---) with surrounding blank lines.",
    worksOn: "Cursor position in manuscript editor.",
    modifies: "Inserts scene break marker.",
    workflow: "Separate scenes within one chapter file.",
  },
  "chapter.formatCharMention": {
    label: "Character mention",
    function: "Wraps selection with [[char:Name]] mention syntax for cast-linked context.",
    worksOn: "Manuscript editor selection.",
    modifies: "Inserts or wraps mention token.",
    workflow: "Links prose to cast — triggers mention review and prompt context.",
  },
  "chapter.formatCharacter": {
    label: "Character mention",
    function: "Wraps selection with [[char:Name]] mention syntax for cast-linked context.",
    worksOn: "Manuscript editor selection.",
    modifies: "Inserts or wraps mention token.",
    workflow: "Links prose to cast — triggers mention review and prompt context.",
  },
  "chapter.formatLoreMention": {
    label: "Lore mention",
    function: "Wraps selection with [[lore:Label]] for bible-linked context.",
    worksOn: "Manuscript editor selection.",
    modifies: "Inserts or wraps mention token.",
    workflow: "Reference world facts — use [[lore:section:Label]] for specific bible sections.",
  },
  "chapter.formatLore": {
    label: "Lore mention",
    function: "Wraps selection with [[lore:Label]] for bible-linked context.",
    worksOn: "Manuscript editor selection.",
    modifies: "Inserts or wraps mention token.",
    workflow: "Reference world facts — use [[lore:section:Label]] for specific bible sections.",
  },
  "chapter.formatFindReplace": {
    label: "Find & replace",
    function: "Opens CodeMirror search panel for find and replace in the manuscript.",
    worksOn: "Current manuscript editor buffer.",
    modifies: "Text matches you confirm in the search panel.",
    workflow: "Bulk rename or fix repeated phrases during revision.",
  },
  "chapter.formatFind": {
    label: "Find & replace",
    function: "Opens CodeMirror search panel for find and replace in the manuscript.",
    worksOn: "Current manuscript editor buffer.",
    modifies: "Text matches you confirm in the search panel.",
    workflow: "Bulk rename or fix repeated phrases during revision.",
  },
  "chapter.formatAnnotate": {
    label: "Annotate selection",
    function: "Opens inline composer to attach a note to the selected passage.",
    worksOn: "Selected text range in write mode.",
    modifies: "Creates manuscript annotation on save.",
    workflow: "Flag a passage for revision — view in Notes panel and preview.",
  },
  "chapter.mentionTips": {
    label: "Mention syntax help",
    function: "Shows cheat sheet for [[char:]], [[lore:]], and @ autocomplete.",
    worksOn: "Manuscript editor toolbar.",
    modifies: "UI popover only.",
    workflow: "Reference when adding inline mentions — memory changes still need Review mentions.",
  },
  "chapter.fontSizeDecrease": {
    label: "Smaller text",
    function: "Decreases editor and preview font size one step.",
    worksOn: "Manuscript editor typography.",
    modifies: "Local display preference stored in browser.",
    workflow: "Comfort adjustment — does not affect exported manuscript.",
  },
  "chapter.fontSizeIncrease": {
    label: "Larger text",
    function: "Increases editor and preview font size one step.",
    worksOn: "Manuscript editor typography.",
    modifies: "Local display preference.",
    workflow: "Pair with reading width for proofreading comfort.",
  },

  // ── Codex ────────────────────────────────────────────────────────────────
  "codex.genericImporter": {
    label: "Generic Importer",
    function: "Extracts structured entities from pasted prose into cast, plots, bible, or chapters.",
    worksOn: "Unstructured pasted text.",
    modifies: "Target codex tables depending on import mode.",
    workflow: "First pass for external notes — refine in dedicated codex tabs afterward.",
  },
  "codex.addCharacter": {
    label: "Add Character",
    function: "Creates a new cast entry with role, bio fields, and optional portrait.",
    worksOn: "Cast list.",
    modifies: "New character record.",
    workflow: "Seed cast before chapter briefs and mention autocomplete.",
  },
  "codex.mergeCharactersManual": {
    label: "Merge manually",
    function: "Pick two characters and merge fields into one surviving record.",
    worksOn: "Selected character pair.",
    modifies: "Destructive merge — secondary character removed.",
    workflow: "Use when AI dedup suggestions are wrong or for obvious duplicates.",
  },
  "codex.resolveDuplicates": {
    label: "Resolve duplicates",
    function: "Heuristic or AI-suggested duplicate groups for characters or plot threads.",
    worksOn: "Cast or plot thread names and bios.",
    modifies: "Merges on confirm — see modal detail for scan workflow.",
    workflow: "Run AI scan, review groups, pick keeper, merge — check Cast tab star when ready.",
  },
  "codex.addPlotThread": {
    label: "Add plot thread",
    function: "Creates a legacy arc or subplot record.",
    worksOn: "Plot Threads list.",
    modifies: "New plot thread.",
    workflow: "Prefer Story Graph for new planning — threads remain for mine output and migration.",
  },
  "codex.mergePlotsParallel": {
    label: "Merge plots (parallel)",
    function: "Combines two plot threads as parallel arcs under one heading.",
    worksOn: "Selected plot thread pair.",
    modifies: "Plot thread records.",
    workflow: "Cleanup legacy threads before or after graph migration.",
  },
  "codex.mergePlotsNest": {
    label: "Nest subplot",
    function: "Makes one plot thread a child subplot of another.",
    worksOn: "Selected plot thread pair.",
    modifies: "Parent/child plot structure.",
    workflow: "Organize legacy list — mirror structure in Story Graph for prompts.",
  },
  "codex.storyBibleDedup": {
    label: "Story bible dedup",
    function: "Finds similar bible entries for merge or cleanup.",
    worksOn: "Story bible sections.",
    modifies: "Bible content on merge.",
    workflow: "After bulk import or mining — review before merging nuanced rules.",
  },
  "codex.storyBibleSection": {
    label: "Bible section",
    function: "Editable canonical section (rules, setting, themes, etc.).",
    worksOn: "Story bible markdown fields.",
    modifies: "Persistent canon used in validation and context preview.",
    workflow: "Durable facts only — not chapter-local landed beats.",
  },
  "codex.timelineEvent": {
    label: "Timeline event",
    function: "Manual chronology entry with date, description, and optional chapter link.",
    worksOn: "Timeline list.",
    modifies: "Timeline records.",
    workflow: "Track clue releases vs hidden events for mystery fairness.",
  },
  "codex.researchSpark": {
    label: "Research spark",
    function: "Reference card with tags and optional links — not auto-canon.",
    worksOn: "Research board.",
    modifies: "Research records only.",
    workflow: "Copy into outline notes or bible when a fact should affect drafting.",
  },
  "codex.mapPin": {
    label: "Map pin",
    function: "Location marker on the project map image.",
    worksOn: "Map overlay.",
    modifies: "Pin records.",
    workflow: "Geographic continuity reference during validation planning.",
  },
  "codex.deleteCharacter": {
    label: "Delete character",
    function: "Removes a cast member and their portrait after confirmation.",
    worksOn: "Selected character record.",
    modifies: "Deletes character — irreversible; check brief toggles and mentions first.",
    workflow: "Prefer merge for duplicates — delete only when the entry was created in error.",
  },
  "codex.deletePlotThread": {
    label: "Delete plot thread",
    function: "Removes a legacy plot thread after confirmation.",
    worksOn: "Selected plot thread record.",
    modifies: "Deletes thread — irreversible; graph nodes may need cleanup.",
    workflow: "Prefer Story Graph for planning — delete obsolete legacy threads after migration.",
  },
  "codex.generatePlotSummary": {
    label: "Generate plot summary",
    function: "AI writes a parent-thread description from current subplot lines and story bible context.",
    worksOn: "Expanded plot thread with subplots.",
    modifies: "Description field on keep — does not create new threads.",
    workflow: "After editing subplots — review generated summary before saving.",
  },
  "codex.expandPlotThread": {
    label: "Expand plot thread",
    function: "Opens the inline editor for a legacy plot thread row.",
    worksOn: "Plot Threads list row.",
    modifies: "UI expand state — edits autosave when expanded.",
    workflow: "Edit name, type, status, and subplots before mining or graph migration.",
  },
  "codex.editTimelineEvent": {
    label: "Edit timeline event",
    function: "Opens the modal to create or update a manual chronology entry.",
    worksOn: "Timeline event fields.",
    modifies: "Timeline records on save.",
    workflow: "Track in-story dates and chapter links for mystery fairness.",
  },
  "codex.uploadMap": {
    label: "Upload map image",
    function: "Sets or replaces the project map background image for location pins.",
    worksOn: "Map panel file picker.",
    modifies: "Map image on disk — pins remain unless you move them.",
    workflow: "Add geographic reference before pinning scenes and locations.",
  },
  "codex.createMap": {
    label: "Create map",
    function: "Adds a new named map layer to the project for location pins.",
    worksOn: "Project maps list.",
    modifies: "Creates empty map record — upload an image before adding pins.",
    workflow: "Start here when the story spans multiple regions or eras.",
  },
  "codex.deleteMap": {
    label: "Delete map",
    function: "Removes the entire map layer, its image, and all pins after confirmation.",
    worksOn: "Active project map.",
    modifies: "Deletes map and pin records — irreversible.",
    workflow: "Use when replacing a map layer — export pin notes first if needed.",
  },
  "codex.saveMapPin": {
    label: "Save map pin",
    function: "Creates or updates a location pin with label, lore link, and notes.",
    worksOn: "Map pin modal fields.",
    modifies: "Pin records on the active map.",
    workflow: "Link pins to bible sections for geographic continuity checks.",
  },
  "codex.editMapPin": {
    label: "Edit map pin",
    function: "Opens the pin editor for label, lore reference, and notes.",
    worksOn: "Selected map pin.",
    modifies: "Pin record on save.",
    workflow: "Update when a location is renamed or lore section changes.",
  },
  "codex.saveResearchSpark": {
    label: "Save research spark",
    function: "Creates or updates a research card with tags, links, and notes.",
    worksOn: "Research spark modal fields.",
    modifies: "Research board records only — not auto-canon.",
    workflow: "Promote facts to bible or outlines when they should affect drafting.",
  },
  "codex.removeCharacterPortrait": {
    label: "Remove portrait",
    function: "Deletes the cast member's uploaded portrait image.",
    worksOn: "Character portrait on disk.",
    modifies: "Clears portrait — character record remains.",
    workflow: "Replace with a new upload or leave blank for text-only cast cards.",
  },
  "codex.removeCharacterRelationship": {
    label: "Remove relationship",
    function: "Deletes the relationship label between this character and another cast member.",
    worksOn: "Character relationship map.",
    modifies: "Removes edge — both characters remain.",
    workflow: "Update when ties change — check relationship graph after edits.",
  },
  "codex.plotThreadReorder": {
    label: "Reorder plot thread",
    function: "Drag handle to change display order of legacy plot threads.",
    worksOn: "Plot Threads list row.",
    modifies: "Thread sort order — content unchanged until expanded and edited.",
    workflow: "Group related threads before nesting subplots via drag-and-drop.",
  },
  "codex.timelineSelectCandidates": {
    label: "Select timeline candidates",
    function: "Toggles selection of all AI-scanned timeline event candidates at once.",
    worksOn: "Timeline generation preview list.",
    modifies: "Selection UI only — events added on confirm.",
    workflow: "Bulk-select top candidates, then deselect outliers before adding.",
  },
  "codex.plotThreadExpand": {
    label: "Expand plot thread",
    function: "Opens the inline editor for a legacy plot thread row.",
    worksOn: "Plot Threads list row.",
    modifies: "UI expand state — edits autosave when expanded.",
    workflow: "Edit name, type, status, and subplots before mining or graph migration.",
  },
  "codex.plotThreadDelete": {
    label: "Delete plot thread",
    function: "Removes a legacy plot thread after confirmation.",
    worksOn: "Selected plot thread record.",
    modifies: "Deletes thread — irreversible; graph nodes may need cleanup.",
    workflow: "Prefer Story Graph for planning — delete obsolete legacy threads after migration.",
  },
  "codex.plotGenerateSummary": {
    label: "Generate plot summary",
    function: "AI writes a parent-thread description from current subplot lines and story bible context.",
    worksOn: "Expanded plot thread with subplots.",
    modifies: "Description field on keep — does not create new threads.",
    workflow: "After editing subplots — review generated summary before saving.",
  },
  "codex.deleteTimelineEvent": {
    label: "Delete timeline event",
    function: "Removes a chronology entry after confirmation.",
    worksOn: "Timeline event record.",
    modifies: "Deletes event — planning aid only.",
    workflow: "Use when correcting mistaken or duplicate timeline rows.",
  },
  "codex.deleteResearchSpark": {
    label: "Delete research spark",
    function: "Removes a research card after confirmation.",
    worksOn: "Research board spark.",
    modifies: "Deletes card — not canon unless copied elsewhere.",
    workflow: "Prune stale references after promoting facts to bible or outlines.",
  },
  "codex.deleteMapPin": {
    label: "Delete map pin",
    function: "Removes a location pin from the project map.",
    worksOn: "Map pin record.",
    modifies: "Deletes pin annotation.",
    workflow: "Update map when locations are renamed or removed from canon.",
  },
  "codex.saveTimelineEvent": {
    label: "Save timeline event",
    function: "Creates or updates a manual chronology entry.",
    worksOn: "Timeline event modal fields.",
    modifies: "Timeline records on disk.",
    workflow: "Track in-story dates and chapter links for mystery fairness.",
  },
  "codex.genealogyCharacter": {
    label: "Family tree character",
    function: "Opens the selected cast member from the genealogy view.",
    worksOn: "Genealogy mind map nodes.",
    modifies: "Navigation to character editor.",
    workflow: "Cross-check lineage labels against character relationship fields.",
  },
  "codex.generateCharacter": {
    label: "Generate character properties",
    function: "AI fills bio fields from your prompt in the character editor.",
    worksOn: "Character editor AI prompt.",
    modifies: "Character fields — autosaves after generation.",
    workflow: "Seed a new cast member or refresh bios before chapter briefs.",
  },
  "codex.createPlotFromBrief": {
    label: "Create plot from brief",
    function: "Adds a new story-graph node from the chapter brief panel with optional parent link.",
    worksOn: "Chapter brief graph focus.",
    modifies: "Story graph node and optional contains edge.",
    workflow: "Spin up a missing subplot mid-chapter planning without leaving Manuscript Studio.",
  },
  "codex.subplotIssues": {
    label: "Plot & subplot issues",
    function: "Scans legacy plot threads for duplicate subplots and misplaced parent/child structure.",
    worksOn: "Plot thread list fields.",
    modifies: "Can auto-fix or resolve individual issues on confirm.",
    workflow: "Cleanup after imports or manual subplot edits — does not touch story bible.",
  },

  // ── Graph & Blueprint ────────────────────────────────────────────────────
  "graph.addNode": {
    label: "Add node",
    function: "Creates a story-graph node (arc, subplot, beat, etc.).",
    worksOn: "Story Graph canvas.",
    modifies: "Graph node list.",
    workflow: "Build structure here — activate nodes in chapter brief before outlining.",
  },
  "graph.linkNodes": {
    label: "Link nodes",
    function: "Two-click mode to add a directed edge between graph nodes.",
    worksOn: "Selected node pair.",
    modifies: "Graph edges.",
    workflow: "Model dependencies and beat order — chapter pins optional on nodes.",
  },
  "graph.findDuplicates": {
    label: "Find duplicates",
    function: "AI/heuristic merge suggestions for similarly titled graph nodes.",
    worksOn: "Story graph node titles.",
    modifies: "Graph on merge confirm.",
    workflow: "Cleanup after migration from plot threads or rapid brainstorming.",
    detail:
      "Opens StoryGraphDedupPanel — review similar titles, pick survivor, merge descriptions and links. " +
      "Non-destructive until you confirm each merge.",
  },
  "graph.migrateFromPlots": {
    label: "Build graph from plots",
    function: "Copies legacy plot threads into graph nodes and edges; originals stay intact.",
    worksOn: "Plot thread list.",
    modifies: "Adds graph nodes — skipped if graph already has nodes.",
    workflow: "One-time migration bridge — then plan in Story Graph, mine still writes threads.",
  },
  "graph.viewRadial": {
    label: "Radial view",
    function: "Freeform radial layout — drag nodes; positions persist.",
    worksOn: "Graph workbench canvas.",
    modifies: "Node layout coordinates.",
    workflow: "Exploratory planning and relationship sketching.",
  },
  "graph.viewActs": {
    label: "Acts view",
    function: "Layers nodes into act bands aligned to chapter count.",
    worksOn: "Graph nodes with act metadata.",
    modifies: "Layout display — act assignments on nodes.",
    workflow: "Macro structure pass — compare to Blueprint chapter coverage.",
  },
  "graph.viewTimeline": {
    label: "Timeline view",
    function: "Columns by act or chapter pins showing node placement across the book.",
    worksOn: "Graph nodes with chapter pin metadata.",
    modifies: "Layout only.",
    workflow: "See which beats land where — drill down to chapter pins for fine placement.",
  },
  "graph.fitView": {
    label: "Fit view",
    function: "Zooms and pans to frame all visible graph nodes.",
    worksOn: "Canvas viewport.",
    modifies: "UI only.",
    workflow: "After search or adding nodes off-screen.",
  },
  "graph.searchNodes": {
    label: "Search nodes",
    function: "Finds graph nodes by title with prev/next match navigation.",
    worksOn: "Node titles on canvas.",
    modifies: "Selection/focus UI.",
    workflow: "Locate a beat quickly in large graphs.",
  },
  "graph.chapterDrillDown": {
    label: "Chapter drill-down",
    function: "Timeline sub-view listing nodes pinned to specific chapters.",
    worksOn: "Chapter pin fields on nodes.",
    modifies: "Timeline scope UI.",
    workflow: "Verify chapter brief active nodes match pins before drafting.",
  },
  "graph.inspector": {
    label: "Graph inspector",
    function: "Edit node title, kind, status, description, links, and chapter pins for selection.",
    worksOn: "Selected graph node or edge.",
    modifies: "Node/edge records on save.",
    workflow: "Primary detail editor — resize panel from the drag handle.",
  },
  "graph.blueprintCanvas": {
    label: "Blueprint canvas",
    function: "Read-only grid of chapters vs active graph nodes and outline snippets.",
    worksOn: "Outlines, briefs, and graph.",
    modifies: "Read-only — filter highlights matching chapters.",
    workflow: "Answer “which chapters touch this arc?” before writing the next beat.",
  },
  "graph.blueprintFilterNode": {
    label: "Filter by graph node",
    function: "Highlights chapters whose brief or outline references the chosen node.",
    worksOn: "Blueprint chapter cards.",
    modifies: "UI filter.",
    workflow: "Cross-check coverage when advancing a subplot across the book.",
  },
  "graph.addRelationship": {
    label: "Add relationship",
    function: "Creates a labeled edge between two cast members in the relationship graph.",
    worksOn: "Character pair.",
    modifies: "Relationship records.",
    workflow: "Visual cast planning — edit label text in character editor.",
  },
  "graph.searchPrevNext": {
    label: "Search match navigation",
    function: "Steps to the previous or next graph node matching the search query.",
    worksOn: "Search results on canvas.",
    modifies: "Selection/focus UI only.",
    workflow: "Walk through multiple title matches in large graphs.",
  },
  "graph.searchNodesPrevNext": {
    label: "Search match navigation",
    function: "Steps to the previous or next graph node matching the search query.",
    worksOn: "Search results on canvas.",
    modifies: "Selection/focus UI only.",
    workflow: "Walk through multiple title matches in large graphs.",
  },
  "graph.inspectorEdit": {
    label: "Edit graph node",
    function: "Opens the node editor for title, kind, status, and description.",
    worksOn: "Selected story-graph node.",
    modifies: "Node record on save.",
    workflow: "Primary detail edit path — use after selecting a node on canvas.",
  },
  "graph.inspectorDeleteNode": {
    label: "Delete graph node",
    function: "Removes the selected node and its connected edges after confirmation.",
    worksOn: "Selected story-graph node.",
    modifies: "Deletes node and edges — may affect chapter brief active nodes.",
    workflow: "Prune obsolete beats — re-check brief graph focus before drafting.",
  },
  "graph.inspectorDeleteEdge": {
    label: "Remove graph connection",
    function: "Deletes a single edge between two nodes.",
    worksOn: "Selected connection in inspector.",
    modifies: "Removes edge only — nodes remain.",
    workflow: "Fix mistaken links without deleting whole nodes.",
  },
  "graph.deleteEdge": {
    label: "Remove graph connection",
    function: "Deletes a single edge between two nodes.",
    worksOn: "Selected connection in inspector.",
    modifies: "Removes edge only — nodes remain.",
    workflow: "Fix mistaken links without deleting whole nodes.",
  },
  "graph.editNode": {
    label: "Save graph node",
    function: "Creates or updates a story-graph node from the modal editor.",
    worksOn: "Node modal fields.",
    modifies: "Graph node list.",
    workflow: "Set kind, status, and linked cast before activating in chapter briefs.",
  },
  "graph.linkCharacters": {
    label: "Link characters",
    function: "Two-click mode to add a labeled relationship between cast members.",
    worksOn: "Relationship graph canvas.",
    modifies: "Opens label modal — stores on source character profile.",
    workflow: "Build the cast relationship map before family tree and brief toggles.",
  },
  "graph.legacyPlotThreads": {
    label: "Legacy plot threads",
    function: "Jumps to the original plot-thread list tab.",
    worksOn: "Navigation.",
    modifies: "None.",
    workflow: "Compare or migrate legacy threads after building the story graph.",
  },
  "graph.blueprintViewMode": {
    label: "Blueprint view mode",
    function: "Switches chapter cards between detailed and compact layout.",
    worksOn: "Blueprint canvas display.",
    modifies: "UI layout only.",
    workflow: "Compact for overview — detailed when checking outline snippets.",
  },
  "graph.mindMapZoom": {
    label: "Mind map zoom",
    function: "Zooms in, out, or resets scale on genealogy and relationship mind maps.",
    worksOn: "Mind map viewport.",
    modifies: "UI zoom level.",
    workflow: "Adjust for large family trees or dense relationship maps.",
  },
  "graph.mindMapSearch": {
    label: "Mind map search",
    function: "Finds characters in the mind map by name, role, or relationship labels.",
    worksOn: "Mind map node list.",
    modifies: "Highlights matches — UI only.",
    workflow: "Locate a family member quickly in deep trees.",
  },
  "graph.mindMapFullscreen": {
    label: "Full browser mode",
    function: "Expands the mind map to use the full browser window.",
    worksOn: "Mind map layout.",
    modifies: "UI chrome only.",
    workflow: "Use for complex genealogy or relationship exploration.",
  },
  "graph.focusPicker": {
    label: "Graph focus picker",
    function: "Selects which story-graph nodes are in effect or eligible for this chapter brief.",
    worksOn: "Chapter brief active graph nodes.",
    modifies: "Brief graph focus when saved.",
    workflow: "Bind arcs before Outline from notes — gold = in effect, silver = eligible.",
  },
  "graph.searchRelationships": {
    label: "Search relationships",
    function: "Finds characters on the relationship graph by name, role, or edge labels.",
    worksOn: "Relationship graph canvas.",
    modifies: "Selection/focus UI.",
    workflow: "Locate a cast member in large relationship maps.",
  },
  "graph.editCharacter": {
    label: "Edit character",
    function: "Opens the full character editor from the relationship graph inspector.",
    worksOn: "Selected cast member.",
    modifies: "Navigation to character editor.",
    workflow: "Adjust relationship labels and bios after inspecting the graph.",
  },

  // ── Global ───────────────────────────────────────────────────────────────
  "global.sidebarLibrary": {
    label: "Library",
    function: "Navigate to the manuscript library grid.",
    worksOn: "Global sidebar.",
    modifies: "Navigation.",
    workflow: "Switch projects from anywhere with sidebar visible.",
  },
  "global.sidebarHelp": {
    label: "Help",
    function: "Opens workflow and feature guides.",
    worksOn: "Global sidebar.",
    modifies: "Navigation.",
    workflow: "Chapter pipeline section documents safest click order.",
  },
  "global.commandPalette": {
    label: "Search",
    function: "Command palette for quick navigation and actions (⌘K).",
    worksOn: "Global keyboard shortcut.",
    modifies: "Navigation and shortcuts.",
    workflow: "Fast jump to chapters, tabs, or settings without mouse.",
  },
  "global.themeToggle": {
    label: "Theme",
    function: "Switches light/dark appearance.",
    worksOn: "UI theme preference.",
    modifies: "Local stored theme.",
    workflow: "Comfort — does not affect manuscript content.",
  },
  "global.stashPanel": {
    label: "Stash",
    function: "Lists stashed projects and restores them to the library.",
    worksOn: "Stashed project archives.",
    modifies: "Library membership on unstash.",
    workflow: "Recover archived manuscripts without re-importing zips.",
  },
  "global.systemSettings": {
    label: "System settings",
    function: "LLM endpoint, model selection, job queue, and agent prompt overrides.",
    worksOn: "Application configuration.",
    modifies: "Server connection and prompt configuration when saved.",
    workflow: "Configure LM Studio connection before running pipeline jobs.",
  },
  "global.flushQueue": {
    label: "Flush queue & restart",
    function: "Clears the LLM job queue, cancels background jobs, and restarts the server.",
    worksOn: "Active and queued jobs.",
    modifies: "Aborts in-flight work — use when jobs hang.",
    workflow: "Last resort recovery — confirm no previews need saving first.",
  },
  "global.jobQueue": {
    label: "Job queue",
    function: "Shows in-progress and waiting background jobs with cancel/remove controls.",
    worksOn: "Background job list.",
    modifies: "Can cancel queued jobs.",
    workflow: "Monitor long mine, dedup, or import tasks.",
  },
  "global.agentPrompts": {
    label: "Agent prompts",
    function: "View or edit system prompts for Architect, Scribe, Editor, Guardian, etc.",
    worksOn: "Agent prompt templates.",
    modifies: "Prompt text used on next job.",
    workflow: "Advanced tuning — defaults match AGENTS.md specifications.",
  },
  "global.unstashProject": {
    label: "Unstash project",
    function: "Restores a stashed manuscript to the library grid.",
    worksOn: "Stashed project in the sidebar lockbox.",
    modifies: "Library visibility — project files unchanged on disk.",
    workflow: "Resume work on an archived draft without re-importing a zip.",
  },
  "global.testConnection": {
    label: "Test connection",
    function: "Pings the configured LLM endpoint to verify reachability and model listing.",
    worksOn: "System settings LLM URL.",
    modifies: "Read-only status message.",
    workflow: "Run after changing LM Studio host or port before pipeline jobs.",
  },
  "global.saveSettings": {
    label: "Save settings",
    function: "Persists LLM endpoint, model, and related system configuration.",
    worksOn: "System settings form fields.",
    modifies: "Application config used by the next background job.",
    workflow: "Save after Test connection succeeds — then run a short pipeline job to verify.",
  },
  "global.modalClose": {
    label: "Close dialog",
    function: "Dismisses the current modal without saving pending changes.",
    worksOn: "Open modal dialog.",
    modifies: "UI only — unsaved modal edits are discarded.",
    workflow: "Use Cancel or Close when you do not want to apply modal actions.",
  },
  "global.retry": {
    label: "Reload page",
    function: "Reloads the browser tab after an unexpected render error.",
    worksOn: "Failed React view.",
    modifies: "Full page refresh — saved project data on disk is unaffected.",
    workflow: "Recovery when a view crashes — your manuscript files remain safe.",
  },

  // ── Modals ───────────────────────────────────────────────────────────────
  "modal.dedupAiScan": {
    label: "AI duplicate scan",
    function: "Background job clustering similar characters or plot threads for merge review.",
    worksOn: "Full cast or plot thread corpus.",
    modifies: "Writes suggestions file — merges only when you confirm in modal.",
    workflow: "Start scan, keep working, return when star appears on Cast/Plots tab.",
    detail:
      "Scan runs async — toast notifies on completion. Heuristic groups show immediately; AI groups replace or augment after scan. " +
      "Pick keeper per group, optionally override display name, then Merge. Manual merge available for edge cases.",
  },
  "modal.dedupMerge": {
    label: "Merge duplicate group",
    function: "Combines duplicate entities into the selected keeper record.",
    worksOn: "One duplicate group.",
    modifies: "Survivor record enriched — duplicates removed.",
    workflow: "Review bios carefully — merge is destructive for secondary records.",
    detail:
      "Keeper inherits combined fields per merge rules. Plot merges may offer parallel vs nest strategies from dashboard. " +
      "Refresh status after merge to clear badges.",
  },
  "modal.dedupManual": {
    label: "Manual merge",
    function: "Author-picked pair merge outside AI suggestions.",
    worksOn: "Two selected entities.",
    modifies: "Single surviving record.",
    workflow: "When suggestions miss obvious duplicates or names differ slightly.",
  },
  "modal.pasteChapter": {
    label: "Paste Chapter",
    function: "Creates a chapter from pasted text at a chosen number.",
    worksOn: "Clipboard markdown or prose.",
    modifies: "New chapter files.",
    workflow: "Import external draft — then Outline from text or Revise in studio.",
  },
  "modal.planOutline": {
    label: "Plan Outline",
    function: "Architect generates whole-book outline preview from project metadata.",
    worksOn: "Project-level planning inputs.",
    modifies: "Preview → apply writes multiple chapter outlines.",
    workflow: "Macro plan before per-chapter Plan Chapter shortcuts.",
  },
  "modal.backups": {
    label: "Backups",
    function: "Create, list, or restore timestamped snapshots of the project folder.",
    worksOn: "Project files on disk.",
    modifies: "Restore replaces current project state with snapshot.",
    workflow: "Before risky bulk operations or experimental settings.",
  },
  "modal.minePreviewReview": {
    label: "Review mine results",
    function: "Per-chapter modal to accept or reject mined plot, character, or bible updates.",
    worksOn: "Mine job output for one chapter.",
    modifies: "Codex targets only for checked rows on Apply.",
    workflow: "Feed discoveries back deliberately — step 4 of structured workflow.",
    detail:
      "Rows show extracted fact, target entity, and success/skipped status. Apply disabled when nothing selected. " +
      "Discard closes without writing; partial apply is supported.",
  },
  "modal.renumberChapter": {
    label: "Renumber chapter",
    function: "Assign a new chapter number with collision shifting.",
    worksOn: "Single chapter from board/outliner.",
    modifies: "Filenames and order.",
    workflow: "Prefer Remove Gaps after many inserts.",
  },
  "modal.ebookImport": {
    label: "Import ebook",
    function: "Configure ebook import target project and chapter splitting options.",
    worksOn: "Ebook file.",
    modifies: "Creates/populates chapters in background.",
    workflow: "Let job finish — then generate briefs and run pipeline per chapter.",
  },
  "modal.cancel": {
    label: "Cancel",
    function: "Closes the dialog without applying changes.",
    worksOn: "Current modal.",
    modifies: "None.",
    workflow: "Use when you want to back out of a destructive or irreversible action.",
  },
  "modal.confirm": {
    label: "Confirm",
    function: "Accepts the confirmation prompt and runs the requested action.",
    worksOn: "Confirm dialog message.",
    modifies: "Depends on the action — may delete or overwrite data.",
    workflow: "Read the message carefully before confirming destructive operations.",
  },
  "modal.dedupQuickScan": {
    label: "Quick duplicate scan",
    function: "Heuristic name-similarity scan for duplicate characters or plot threads.",
    worksOn: "Full cast or plot thread list.",
    modifies: "Read-only suggestions until you merge.",
    workflow: "Fast first pass — follow with AI scan for ambiguous names.",
  },
  "modal.dedupAutoMerge": {
    label: "Auto-merge duplicates",
    function: "Merges all high-confidence duplicate groups in one pass.",
    worksOn: "Current duplicate scan results.",
    modifies: "Survivor records enriched — secondary entries removed.",
    workflow: "Use only when suggestions look correct — review groups first when unsure.",
  },
};

/** Returns structured tooltip copy for a registered control id. */
export function getToolTip(id: ToolTipId): ToolTipEntry {
  return TOOL_REGISTRY[id];
}
