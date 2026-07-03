import { useEffect } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

const GETTING_STARTED_STEPS = [
  "Create a project — you get one protagonist, Chapter 1 (Opening), one graph node (Central conflict), and a chapter brief already linked.",
  "Open Chapter 1 — review the brief (POV, active plot node, cast toggles).",
  "Add beats on the beat board or outline notes, then run Outline from notes.",
  "Generate Draft, then Revise, Validate, and Approve.",
  "See Story Graph and Manuscript Studio help for deeper planning and editing.",
];

const WORKFLOW_STEPS = [
  {
    label: "1",
    title: "Establish canon",
    body: "New projects start with a seeded protagonist, Chapter 1, and a graph node. Refine the Story Bible, Cast, and Story Graph from there; migrate legacy plot threads when ready.",
    actions: ["Review seeded protagonist + Central conflict node", "Story Bible: durable rules, setting, themes", "Story Style / Tone on project dashboard", "Story Graph: expand arcs/subplots/relationships", "Timeline: manual chronology"],
  },
  {
    label: "2",
    title: "Bind arc to a chapter",
    body: "Set the chapter brief (POV + active graph nodes), then create or revise the outline. Generate Draft reads the saved outline and chapter-brief context when present.",
    actions: ["Chapter brief: POV and active story nodes", "Plan Chapter or Outline from notes", "Review Outline before drafting"],
  },
  {
    label: "3",
    title: "Generate and revise prose",
    body: "Run the chapter pipeline after the outline is solid. The Scribe expands beats into prose, then the Editor and Guardian tighten and validate it.",
    actions: ["Generate Draft", "Revise and edit Revised manually", "Validate, Approve, then Promote to Final"],
  },
  {
    label: "4",
    title: "Feed discoveries back",
    body: "After prose exists, mine or review updates deliberately. Landed beats remain chapter-local until you intentionally promote durable facts into the Story Bible.",
    actions: ["Extract landed beats for chapter-local events", "Mine plots, characters, or bible facts", "Re-sync Story Graph after plot mining if needed", "Promote only durable canon to Story Bible"],
  },
];

const USE_CASES = [
  {
    title: "Plan Chapter 7 to advance the betrayal arc",
    task: "You know the betrayal must happen soon, but not exactly how.",
    steps: [
      "Open Story Graph and ensure the betrayal arc node (and related beats) is clear.",
      "Set Chapter 7 brief: POV character and active graph nodes for the betrayal thread.",
      "Type outline notes: the betrayal clue, what must change, and the ending hook; run Outline from notes.",
      "Run Generate Draft. If the draft misses the turn, adjust brief/outline and regenerate before drafting again.",
    ],
  },
  {
    title: "Keep a mystery fair across multiple chapters",
    task: "You want clues planted without losing track of what the reader knows.",
    steps: [
      "Create mystery nodes on the Story Graph (or legacy plot threads, then migrate).",
      "Add timeline events for revealed facts and hidden events.",
      "Use Blueprint to check which chapter outlines mention the thread.",
      "After drafting, run Validate and mine Plots & subplots; review before applying, then re-sync the graph if needed.",
    ],
  },
  {
    title: "Turn research into usable story material",
    task: "You collected reference notes but do not want them treated as canon yet.",
    steps: [
      "Save notes in Research Board with tags and optional links.",
      "Promote only chosen facts by copying them into Story Bible, a plot thread, or chapter outline notes.",
      "When writing a chapter, include the selected research point in Outline notes so the Architect can use it.",
      "Leave unused research cards in the board. They do not enter prompts automatically.",
    ],
  },
  {
    title: "Revise a chapter without losing the original draft",
    task: "You want several editing passes while preserving the first draft.",
    steps: [
      "Run Revise. The Editor creates or updates Revised.",
      "Edit Revised directly in Manuscript Studio. It autosaves.",
      "Run Revise again. The next pass reads Revised, not Draft.",
      "When satisfied, Validate, Approve, then Promote to Final.",
    ],
  },
];

const FEATURE_GUIDES = [
  {
    title: "Story Bible",
    role: "Canonical world and rule memory.",
    use: "Put durable rules, setting, themes, and stable facts here. Use Story Style / Tone for writing tone.",
    boundary: "Story Graph handles structure; landed beats are chapter-local and do not update it automatically.",
    link: "/help/story-bible",
  },
  {
    title: "Cast",
    role: "Character memory and visual reference.",
    use: "Track role, desire, fear, arc stage, relationships, and portraits.",
    boundary: "Relationship and portrait changes are author-controlled.",
    link: "/help/cast",
  },
  {
    title: "Plot Threads",
    role: "Legacy arc list (still supported).",
    use: "Original plot-thread editor and duplicate search. Mine Plots still writes here; migrate to Story Graph when ready.",
    boundary: "Chapter briefs prefer Story Graph nodes; legacy threads remain a fallback in prompts.",
    link: "/help/plot-threads",
  },
  {
    title: "Story Graph",
    role: "Primary planning mind map.",
    use: "Arrange arcs, subplots, and beats; link nodes; set chapter brief active nodes for outlines and drafts.",
    boundary: "Use it for structure, not one-fact-per-line worldbuilding canon. Migration copies plot threads without deleting them.",
    link: "/help/story-graph",
  },
  {
    title: "Chapter Briefs",
    role: "Per-chapter POV and active graph scope.",
    use: "Pick POV, active characters, story nodes, required beats, and review landed beats for the chapter.",
    boundary: "Landed beats are chapter-local events; promote durable facts to Story Bible separately.",
    link: "/help/story-graph",
  },
  {
    title: "Blueprint",
    role: "Read-only planning board.",
    use: "Review chapter cards, act lanes, outline snippets, and inferred plot-thread chips.",
    boundary: "It does not write to prompts or reorder chapters.",
    link: "/help/blueprint",
  },
  {
    title: "Timeline",
    role: "Manual chronology.",
    use: "Record events by chapter, day/time, location, character, type, and significance.",
    boundary: "It is not mined into prompts automatically.",
    link: "/help/timeline",
  },
  {
    title: "Research Board",
    role: "Pre-canon idea capture.",
    use: "Store links, notes, quotes, images, and loose ideas by tag/type.",
    boundary: "Research does not feed StoryState or prompts unless you copy it into canon or outline notes.",
    link: "/help/research",
  },
  {
    title: "Map",
    role: "Visual location reference.",
    use: "Upload maps, place normalized pins, and link pins to lore labels.",
    boundary: "Pins do not update Story Bible or character location.",
    link: "/help/map",
  },
  {
    title: "Manuscript Studio",
    role: "Chapter writing surface.",
    use: "Edit Draft, Revised, and Final with focus, typewriter, annotations, mentions, and preview tools.",
    boundary: "Reading aids are display-only and never change saved prose.",
    link: "/help/manuscript-studio",
  },
  {
    title: "Prompt Settings",
    role: "Install-wide AI behavior controls.",
    use: "Choose current, recommended, or custom system prompts for each agent.",
    boundary: "Custom prompts get parser-safe output-contract guards for critical agents.",
    link: "/help/prompt-settings",
  },
];

const HELP_TOPICS: Record<string, {
  title: string;
  subtitle: string;
  purpose: string;
  workflow: string[];
  examples: string[];
  boundaries: string[];
  related: { label: string; href: string }[];
}> = {
  "story-bible": {
    title: "Story Bible",
    subtitle: "Canonical world and rule memory.",
    purpose: "Use the Story Bible for durable facts that should remain true across the manuscript: genre expectations, themes, setting, world rules, factions, technology, magic, and stable relationship facts. Use Story Style / Tone for writing tone and prose style.",
    workflow: [
      "Add high-level canon before planning chapters.",
      "Use lore mentions in prose when a specific bible item matters.",
      "Review mined Story Bible suggestions before applying them; ordinary landed beats stay in the chapter brief.",
      "Return here when the Guardian flags world or continuity drift.",
    ],
    examples: [
      "Add a rule that faster-than-light travel is impossible, then mention that rule in a chapter outline.",
      "Record faction customs before writing a diplomacy scene.",
      "Set tone in Story Style / Tone so drafts stay noir, romantic, comic, or austere.",
    ],
    boundaries: [
      "Research Board items are not canon until copied or applied here.",
      "Story Graph stores plot/subplot structure, not durable one-fact-per-line worldbuilding.",
      "Landed beats are chapter-local events and do not update Story Bible unless promoted through a reviewed bible/mining flow.",
      "Map pins can link to lore, but do not rewrite lore text.",
      "Annotations are revision notes, not Story Bible facts.",
    ],
    related: [{ label: "Research Board", href: "/help/research" }, { label: "Map", href: "/help/map" }],
  },
  cast: {
    title: "Cast",
    subtitle: "Characters, arcs, relationships, and portraits.",
    purpose: "Use Cast to track who characters are, what they want, how they are changing, and how they relate to one another.",
    workflow: [
      "Create important characters before drafting their chapters.",
      "Fill desire, fear, emotional state, current location, and arc stage.",
      "Use Relationships to label links with a role/subrole idea: parent(mother), teacher(mentor), friend(accomplice), employer(boss).",
      "Upload portraits only as display references.",
    ],
    examples: [
      "Before planning a betrayal scene, label one character as teacher(mentor) and another as rival.",
      "After a chapter changes a character's emotional state, review mention updates before applying.",
      "Use the Family Tree to check whether parent/child labels are readable.",
    ],
    boundaries: [
      "Portraits are visual references only and do not affect prompts.",
      "Family tree labels are derived from primary family edges such as parent, child, sibling, and spouse.",
      "Mention-derived character updates require manual review.",
    ],
    related: [{ label: "Relationship Graph", href: "/help/relationships" }, { label: "Manuscript Studio", href: "/help/manuscript-studio" }],
  },
  "plot-threads": {
    title: "Plot Threads",
    subtitle: "Legacy arc list — still mined and deduplicated.",
    purpose: "Plot Threads remain available for older projects and mining workflows. Each thread holds a description, subplot lines, and related characters. Duplicate search and subplot-issue tools still operate here.",
    workflow: [
      "Use Plot Threads when you have not migrated yet, or to review mined plot updates.",
      "Run Resolve Duplicates or Check subplot issues on this tab for legacy data hygiene.",
      "When ready, use Story Graph → Build graph from plots (non-destructive copy).",
      "Prefer chapter briefs + Story Graph for chapter-scoped planning after migration.",
      "Mine Plots & subplots still updates plot threads; re-sync the graph afterward if needed.",
    ],
    examples: [
      "Thread: Betrayal arc with subplot beats before migrating to graph nodes.",
      "Resolve duplicate plot threads after importing an older manuscript.",
      "Mine a drafted chapter, apply plot updates, then Build graph from plots.",
    ],
    boundaries: [
      "Story Graph is the primary planning layer for new work.",
      "Migration does not delete plot threads.",
      "Graph duplicate search is separate from plot-thread duplicate search.",
      "Blueprint chips still infer from outline text on legacy threads.",
    ],
    related: [{ label: "Story Graph", href: "/help/story-graph" }, { label: "Blueprint", href: "/help/blueprint" }],
  },
  "story-graph": {
    title: "Story Graph & Chapter Briefs",
    subtitle: "Mind-map planning and per-chapter scope.",
    purpose: "The Story Graph is the primary structure surface: nodes for arcs, subplots, plot beats, mysteries, and themes; edges for relationships between story elements; chapter briefs for POV and which nodes are active in a given chapter.",
    workflow: [
      "Build graph from plots (copies legacy threads without deleting them) or add nodes manually.",
      "Arrange and link nodes on the mind map; use Find duplicates after migration.",
      "Open a chapter → Chapter brief: set POV, active characters, and active graph nodes.",
      "Use Context preview to see which Story Bible and graph nodes will be sent to AI prompts and what was omitted by the budget.",
      "After prose exists, extract landed beats for chapter-local events; promote only durable facts to Story Bible.",
      "Write or generate the chapter outline (brief context is included when outline exists).",
      "Generate Draft; revise; mine plots if needed and re-sync the graph.",
    ],
    examples: [
      "Migrate 'The Heist' main arc and nest subplot nodes under it with contains edges.",
      "Chapter 5 brief: POV = detective, active nodes = [mystery clue, witness interview beat].",
      "Merge duplicate 'Vault alarm' nodes after migration created overlaps.",
    ],
    boundaries: [
      "Story Bible remains the durable canon store for world rules, setting facts, themes, and stable facts. Writing tone lives in Story Style / Tone.",
      "Landed beats are chapter-local events in the Chapter Brief, not graph nodes or bible canon by default.",
      "Context preview reflects pipeline mode budgets (outline, draft, revise, validation); omitted items are capped, not deleted from your project.",
      "Without a saved outline, brief-only context may be limited — still write outline notes.",
      "Legacy plot threads remain in state and prompts as fallback when the graph is empty.",
      "Plot-thread duplicate search on the Plot Threads tab is unchanged.",
      "Timeline and Research Board do not auto-sync to graph nodes.",
    ],
    related: [
      { label: "Plot Threads (legacy)", href: "/help/plot-threads" },
      { label: "Manuscript Studio", href: "/help/manuscript-studio" },
      { label: "Blueprint", href: "/help/blueprint" },
    ],
  },
  relationships: {
    title: "Relationships and Family Tree",
    subtitle: "Visual views of character links.",
    purpose: "Use Relationships to see the social graph and Family Tree to view role/subrole links between cast members.",
    workflow: [
      "Edit labels in Cast by opening a character.",
      "Use broad roles with optional subroles: parent(mother), child(son), teacher(mentor), employer(boss).",
      "Use custom subroles when the predefined examples do not fit.",
      "Use primary family edges for Family Tree; extended kinship is derived from those edges when possible.",
      "Click nodes or names to return to the character editor.",
    ],
    examples: [
      "Label Mira -> Elias as parent(mother) to show a parent link while displaying mother.",
      "Label Lena -> Dax as rival to show it in Relationships without forcing genealogy.",
      "Label an employer relationship as employer(boss) when the role is work authority but the displayed subrole should be boss.",
    ],
    boundaries: [
      "The role drives graph grouping, inverse mapping, family-tree traversal, and AI normalization.",
      "The subrole is what users see and what writing prompts should use.",
      "Ambiguous labels should remain custom unless context qualifies them.",
    ],
    related: [{ label: "Cast", href: "/help/cast" }, { label: "Plot Threads", href: "/help/plot-threads" }],
  },
  blueprint: {
    title: "Blueprint",
    subtitle: "Read-only plot canvas for reviewing structure.",
    purpose: "Use Blueprint to review chapter cards grouped into act lanes, with outline snippets and plot-thread chips inferred from outline text.",
    workflow: [
      "Create or revise chapter outlines first.",
      "Open Blueprint to see act lanes and chapter sequence.",
      "Click a chapter card to edit that chapter.",
      "Click a thread chip to open the matching plot thread.",
    ],
    examples: [
      "Check whether the midpoint chapter outline mentions the central reversal.",
      "Scan Act II for missing mystery clues.",
      "Compare pipeline dots to see where drafting is ahead of planning.",
    ],
    boundaries: [
      "Blueprint is read-only and does not reorder chapters.",
      "Act lanes are mathematical thirds, not custom act breaks.",
      "Thread chips are text matches, not canonical assignments.",
    ],
    related: [{ label: "Plot Threads", href: "/help/plot-threads" }, { label: "Chapter Pipeline", href: "/help/manuscript-studio" }],
  },
  timeline: {
    title: "Timeline",
    subtitle: "Manual chronology across chapters.",
    purpose: "Use Timeline to record what happened when, where, and to whom. It is especially useful for flashbacks, mysteries, travel, and cause/effect continuity.",
    workflow: [
      "Add events with chapter, optional day/time, location, type, significance, and characters.",
      "Filter by chapter, character, type, or significance.",
      "Use it as reference when writing outline notes.",
      "Update events manually after drafting major turns.",
    ],
    examples: [
      "Record that the murder occurred before Chapter 1 but is revealed in Chapter 8.",
      "Track a character's arrival in a city before a scene depends on them being there.",
      "Mark a climax event as turning point or climax for easy filtering.",
    ],
    boundaries: [
      "Timeline does not feed prompts automatically today.",
      "Locations are free text and not validated against Story Bible.",
      "Timeline events are not map pins.",
    ],
    related: [{ label: "Map", href: "/help/map" }, { label: "Plot Threads", href: "/help/plot-threads" }],
  },
  research: {
    title: "Research Board",
    subtitle: "Pre-canon notes, links, quotes, and loose ideas.",
    purpose: "Use Research Board for material you may want later but are not ready to make canonical: links, quotes, images, notes, and idea sparks.",
    workflow: [
      "Add a spark with title, body, kind, tags, and optional URL.",
      "Link it to a character, chapter, plot thread, or bible section when useful.",
      "Filter by search, tag, or kind.",
      "Copy selected facts into Story Bible, Plot Threads, or Outline notes when ready.",
    ],
    examples: [
      "Save a link about lockpicking techniques and tag it heist.",
      "Store a quote that may inspire a faction motto.",
      "Attach a location reference to a future chapter without making it canon yet.",
    ],
    boundaries: [
      "Research does not enter prompts automatically.",
      "Research is backed up in project packages, but remains separate from StoryState.",
      "External URLs are stored as references; Novel OS does not fetch pages automatically.",
    ],
    related: [{ label: "Story Bible", href: "/help/story-bible" }, { label: "Chapter Pipeline", href: "/help/manuscript-studio" }],
  },
  map: {
    title: "Map",
    subtitle: "Project map images and manual location pins.",
    purpose: "Use Map for visual geography: world maps, city maps, ship layouts, battlefields, or any image where pin placement helps continuity.",
    workflow: [
      "Create or select a map.",
      "Upload an image.",
      "Click or drag to place pins using normalized coordinates.",
      "Optionally link a pin to a lore section and label.",
    ],
    examples: [
      "Pin each city on a world map and link it to a Story Bible location entry.",
      "Use a ship deck plan to track where scenes occur.",
      "Add notes to a battlefield pin before writing a tactical chapter.",
    ],
    boundaries: [
      "Pins do not update Story Bible text.",
      "Pins do not change character current_location.",
      "Maps are visual references, not agent prompt inputs.",
    ],
    related: [{ label: "Timeline", href: "/help/timeline" }, { label: "Story Bible", href: "/help/story-bible" }],
  },
  "manuscript-studio": {
    title: "Manuscript Studio",
    subtitle: "Draft, revise, validate, annotate, and finalize chapters.",
    purpose: "Use Manuscript Studio as the chapter production surface. It holds the Outline, Draft, Revised, and Final stages and connects to the agent pipeline.",
    workflow: [
      "Write outline notes and run Outline from notes before drafting.",
      "Run Generate Draft to create prose from the saved outline.",
      "Run Revise, then edit Revised directly.",
      "Validate, Approve, and Promote to Final when the chapter is ready.",
    ],
    examples: [
      "Use [[expand: add a tense exchange about the missing key]] inside Draft or Revised, then Expand placeholders.",
      "Select a paragraph and add an annotation for a future revision pass.",
      "Use character and lore mentions when a specific canon item should be visible in prompt context.",
    ],
    boundaries: [
      "Focus, Typewriter, Vanishing, and Bionic modes are display-only.",
      "Annotations do not alter manuscript text or exports.",
      "Generate Draft can fall back to a generic prompt if no saved outline exists.",
    ],
    related: [{ label: "Plot Threads", href: "/help/plot-threads" }, { label: "Mentions and canon", href: "/help/story-bible" }],
  },
  "getting-started": {
    title: "Your first manuscript",
    subtitle: "What a new project includes and how to write Chapter 1.",
    purpose:
      "Creating a project seeds a minimal Structure V2 workspace: one protagonist, Chapter 1 (Opening), one Story Graph node (Central conflict), a linked chapter brief, one planned beat, and a starter outline scaffold. This is enough to plan and draft without building cast and graph from zero.",
    workflow: GETTING_STARTED_STEPS,
    examples: [
      "Create a Fantasy project, open Chapter 1, and confirm the brief lists your protagonist as POV and active cast.",
      "Add a beat on the beat board, then run Outline from notes before Generate Draft.",
      "Compare your new project to examples/demo_project for a richer reference manuscript.",
    ],
    boundaries: [
      "Starter seed is minimal — not a full demo story.",
      "Legacy plot threads are not created automatically; use Story Graph for new work.",
      "examples/demo_project is a richer canned reference, not what POST /api/projects creates.",
    ],
    related: [
      { label: "Story Graph", href: "/help/story-graph" },
      { label: "Manuscript Studio", href: "/help/manuscript-studio" },
      { label: "Story Bible", href: "/help/story-bible" },
    ],
  },
  "prompt-settings": {
    title: "Prompt Settings",
    subtitle: "Choose current, recommended, or custom prompts for each agent.",
    purpose: "Use Prompt Settings when you want to change how a specific Novel OS agent behaves without editing prompt files manually.",
    workflow: [
      "Open Sidebar -> AI settings -> Agent prompt presets.",
      "Pick an agent such as Architect, Scribe, Editor, Guardian, Lorekeeper, Archivist, or Style Curator.",
      "Choose Current default, Recommended, or Custom.",
      "Use Copy recommended into custom when you want a safe starting point for your own edits.",
      "Save the prompt, then test it on a small chapter or dry-run before relying on it for long generations.",
    ],
    examples: [
      "Make Scribe more cinematic and sensory while leaving Architect unchanged.",
      "Make Editor more aggressive about cutting exposition.",
      "Make Guardian stricter about travel time, character knowledge, or world-rule violations.",
      "Set a Global system prefix for house rules such as tense, punctuation, or content rating across all agents.",
    ],
    boundaries: [
      "Prompt presets are install-wide, not per project.",
      "Dynamic task prompts are still generated by code because they include chapter text, StoryState, plot context, and author notes.",
      "Custom prompts should not contradict required output blocks such as [SCRIBE_STATE_UPDATE], [REVISED_CHAPTER], or [CONTINUITY_REPORT].",
      "Novel OS appends immutable output-contract guards for parser-critical agents when Custom is selected.",
    ],
    related: [{ label: "Manuscript Studio", href: "/help/manuscript-studio" }, { label: "Plot Threads", href: "/help/plot-threads" }],
  },
};

const PROMPT_TRUTH = [
  ["Strong signal", "Saved chapter outline, outline notes, chapter brief (POV + active graph nodes), recent character state, Story Bible context, explicit mentions."],
  ["Weak or manual signal", "Timeline, Blueprint, Research Board, Map pins, and annotations unless copied into outline notes or canon."],
  ["Best control point", "Outline from notes. New projects include a brief-linked graph node — add beats or outline notes there before Generate Draft."],
];

export default function HelpGuide() {
  const location = useLocation();
  const { topic } = useParams();

  useEffect(() => {
    if (!location.hash) return;
    const target = document.querySelector(location.hash);
    target?.scrollIntoView({ block: "start" });
  }, [location.hash]);

  if (topic) {
    return <HelpTopic topic={topic} />;
  }

  return (
    <div className="mx-auto max-w-6xl px-8 py-10 lg:px-12">
      <header className="mb-10 overflow-hidden rounded-3xl border border-paper-line bg-paper-card shadow-[var(--shadow-paper)]">
        <div className="grid gap-0 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="p-8 lg:p-10">
            <p className="mb-3 text-[12px] font-semibold uppercase tracking-[0.2em] text-amber-deep">
              Novel OS Help
            </p>
            <h1 className="font-display text-[40px] font-semibold leading-tight tracking-tight text-ink-text text-balance">
              From story arc to finished chapter
            </h1>
            <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-ink-muted">
              Novel OS works best when you treat the project codex as story memory and the chapter outline as the handoff from arc planning to prose. This guide shows the intended workflow, what each control affects, and practical tasks you can repeat while drafting.
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              <JumpLink href="#getting-started">First manuscript</JumpLink>
              <JumpLink href="#arc-to-chapter">Arc workflow</JumpLink>
              <JumpLink href="#use-cases">Use cases</JumpLink>
              <JumpLink href="#feature-guides">Feature guide</JumpLink>
              <JumpLink href="#prompt-boundaries">Prompt boundaries</JumpLink>
            </div>
          </div>
          <div className="border-t border-paper-line bg-ink p-8 text-on-ink lg:border-l lg:border-t-0 lg:p-10">
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-amber">
              Key idea
            </p>
            <p className="mt-4 font-display text-[25px] leading-snug">
              The chapter outline is the bridge. Plan there before asking the Scribe to draft.
            </p>
            <ol className="mt-6 space-y-3 text-[13.5px] leading-relaxed text-[#c8cedd]">
              <li><strong className="text-white">1.</strong> Review seeded cast + graph, then refine canon.</li>
              <li><strong className="text-white">2.</strong> Set beats or outline notes for Chapter 1.</li>
              <li><strong className="text-white">3.</strong> Generate Draft from that outline.</li>
              <li><strong className="text-white">4.</strong> Revise, validate, approve, and update memory deliberately.</li>
            </ol>
          </div>
        </div>
      </header>

      <section id="getting-started" className="scroll-mt-8 rounded-2xl border border-paper-line bg-paper-card p-6 shadow-[var(--shadow-paper)]">
        <SectionHeader
          eyebrow="Onboarding"
          title="Your first manuscript (5 minutes)"
          body="New projects ship with enough Structure V2 scaffolding to open Chapter 1 and start planning immediately."
        />
        <ol className="mt-4 space-y-3">
          {GETTING_STARTED_STEPS.map((step, index) => (
            <li key={step} className="flex gap-3 text-[13.5px] leading-relaxed text-ink-muted">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-amber/20 text-[12px] font-semibold text-amber-deep">
                {index + 1}
              </span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
        <p className="mt-5 text-[13.5px] leading-relaxed text-ink-muted">
          For a richer reference project, see <code className="rounded bg-paper/70 px-1.5 py-0.5 text-[12px]">examples/demo_project</code> in the app bundle.
          {" "}
          <Link to="/help/getting-started" className="font-semibold text-amber-deep hover:underline">
            Open full getting-started help
          </Link>
        </p>
      </section>

      <section id="arc-to-chapter" className="scroll-mt-8">
        <SectionHeader
          eyebrow="Primary workflow"
          title="How structured writing is supposed to flow"
          body="Use project-level surfaces to maintain memory. Use the chapter outline to decide exactly what this chapter must do."
        />
        <div className="grid gap-4 lg:grid-cols-4">
          {WORKFLOW_STEPS.map((step) => (
            <article key={step.label} className="rounded-2xl border border-paper-line bg-paper-card p-5 shadow-[var(--shadow-paper)]">
              <div className="mb-4 flex h-9 w-9 items-center justify-center rounded-full bg-amber/20 font-display text-[17px] font-semibold text-amber-deep">
                {step.label}
              </div>
              <h3 className="font-display text-[19px] font-semibold text-ink-text">{step.title}</h3>
              <p className="mt-2 text-[13.5px] leading-relaxed text-ink-muted">{step.body}</p>
              <ul className="mt-4 space-y-2">
                {step.actions.map((action) => (
                  <li key={action} className="flex gap-2 text-[12.5px] leading-relaxed text-ink-muted">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-deep" />
                    <span>{action}</span>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>

      <section id="chapter-pipeline" className="mt-12 scroll-mt-8 rounded-2xl border border-paper-line bg-paper-card p-6 shadow-[var(--shadow-paper)]">
        <SectionHeader
          eyebrow="Chapter pipeline"
          title="What to click when creating a chapter"
          body="The safest order is Outline -> Generate Draft -> Revise -> Validate -> Approve -> Promote to Final."
        />
        <div className="grid gap-3 md:grid-cols-5">
          {["Outline from notes", "Generate Draft", "Revise", "Validate / Approve", "Promote to Final"].map((label, index) => (
            <div key={label} className="rounded-xl border border-paper-line bg-paper/55 p-4">
              <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-paper-muted">Step {index + 1}</p>
              <p className="mt-2 font-semibold text-ink-text">{label}</p>
            </div>
          ))}
        </div>
        <div className="mt-5 rounded-xl border border-amber/30 bg-amber/5 p-4 text-[13.5px] leading-relaxed text-ink-muted">
          <strong className="text-ink-text">Tip:</strong> If Generate Draft feels generic, the chapter probably lacks a strong saved outline. Add specific outline notes: POV, required beats, conflict, thread to advance, continuity constraints, and ending hook.
        </div>
      </section>

      <section id="use-cases" className="mt-12 scroll-mt-8">
        <SectionHeader
          eyebrow="Example tasks"
          title="Repeatable use cases"
          body="These recipes show how the controls fit together for common structured-writing jobs."
        />
        <div className="grid gap-5 md:grid-cols-2">
          {USE_CASES.map((useCase) => (
            <article key={useCase.title} className="rounded-2xl border border-paper-line bg-paper-card p-6 shadow-[var(--shadow-paper)]">
              <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-amber-deep">Use case</p>
              <h3 className="mt-2 font-display text-[21px] font-semibold text-ink-text">{useCase.title}</h3>
              <p className="mt-2 text-[13.5px] italic text-ink-muted">{useCase.task}</p>
              <ol className="mt-5 space-y-3">
                {useCase.steps.map((step, index) => (
                  <li key={step} className="flex gap-3 text-[13.5px] leading-relaxed text-ink-muted">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ink text-[11px] font-semibold text-on-ink">
                      {index + 1}
                    </span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            </article>
          ))}
        </div>
      </section>

      <section id="prompt-boundaries" className="mt-12 scroll-mt-8">
        <SectionHeader
          eyebrow="Prompt behavior"
          title="What affects the agents today"
          body="Some controls are active prompt inputs, while others are planning aids until you copy their content into canon or outline notes."
        />
        <div className="overflow-hidden rounded-2xl border border-paper-line bg-paper-card shadow-[var(--shadow-paper)]">
          {PROMPT_TRUTH.map(([label, body], index) => (
            <div key={label} className={`grid gap-3 p-5 md:grid-cols-[180px_1fr] ${index > 0 ? "border-t border-paper-line" : ""}`}>
              <p className="font-semibold text-ink-text">{label}</p>
              <p className="text-[13.5px] leading-relaxed text-ink-muted">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="feature-guides" className="mt-12 scroll-mt-8">
        <SectionHeader
          eyebrow="Feature guide"
          title="What the rest of the workspace is for"
          body="Each feature has a job. The important distinction is whether it stores canon, prepares a chapter, or simply helps you see and organize the project."
        />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {FEATURE_GUIDES.map((feature) => (
            <Link key={feature.title} to={feature.link} id={slug(feature.title)} className="scroll-mt-8 rounded-2xl border border-paper-line bg-paper-card p-5 shadow-[var(--shadow-paper)] transition-colors hover:border-amber/50 hover:bg-amber/5">
              <h3 className="font-display text-[19px] font-semibold text-ink-text">{feature.title}</h3>
              <p className="mt-2 text-[12px] font-semibold uppercase tracking-[0.12em] text-paper-muted">Role</p>
              <p className="mt-1 text-[13.5px] leading-relaxed text-ink-muted">{feature.role}</p>
              <p className="mt-3 text-[12px] font-semibold uppercase tracking-[0.12em] text-paper-muted">Use it for</p>
              <p className="mt-1 text-[13.5px] leading-relaxed text-ink-muted">{feature.use}</p>
              <p className="mt-3 text-[12px] font-semibold uppercase tracking-[0.12em] text-paper-muted">Boundary</p>
              <p className="mt-1 text-[13.5px] leading-relaxed text-ink-muted">{feature.boundary}</p>
              <p className="mt-4 text-[12.5px] font-semibold text-amber-deep">Open help page</p>
            </Link>
          ))}
        </div>
      </section>

      <section className="mt-12 rounded-2xl border border-paper-line bg-ink p-6 text-on-ink shadow-[var(--shadow-paper)]">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-amber">Start here</p>
            <h2 className="mt-2 font-display text-[25px] font-semibold">Ready to use the workflow?</h2>
            <p className="mt-2 max-w-2xl text-[13.5px] leading-relaxed text-[#c8cedd]">
              Open Chapter 1, set beats or outline notes, then generate prose when the brief and outline match your intent.
            </p>
          </div>
          <Link
            to="/"
            className="inline-flex shrink-0 items-center justify-center rounded-lg bg-amber px-5 py-2.5 text-[13.5px] font-semibold text-ink transition-colors hover:bg-[#f7c969]"
          >
            Go to Library
          </Link>
        </div>
      </section>
    </div>
  );
}

function HelpTopic({ topic }: { topic: string }) {
  const data = HELP_TOPICS[topic];
  if (!data) {
    return (
      <div className="mx-auto max-w-3xl px-8 py-12">
        <Link to="/help" className="text-[13px] font-semibold text-amber-deep hover:underline">
          Back to Help
        </Link>
        <div className="mt-6 rounded-2xl border border-paper-line bg-paper-card p-8 shadow-[var(--shadow-paper)]">
          <h1 className="font-display text-[30px] font-semibold text-ink-text">Help page not found</h1>
          <p className="mt-3 text-[14px] text-ink-muted">This help topic does not exist yet.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-8 py-10 lg:px-12">
      <Link to="/help" className="text-[13px] font-semibold text-amber-deep hover:underline">
        Back to Help
      </Link>
      <header className="mt-5 rounded-3xl border border-paper-line bg-paper-card p-8 shadow-[var(--shadow-paper)]">
        <p className="mb-2 text-[12px] font-semibold uppercase tracking-[0.2em] text-amber-deep">Feature Help</p>
        <h1 className="font-display text-[38px] font-semibold leading-tight tracking-tight text-ink-text">{data.title}</h1>
        <p className="mt-2 text-[16px] text-ink-muted">{data.subtitle}</p>
        <p className="mt-5 max-w-3xl text-[14px] leading-relaxed text-ink-muted">{data.purpose}</p>
      </header>

      <div className="mt-6 grid gap-5 lg:grid-cols-[1fr_0.9fr]">
        <HelpPanel title="Typical workflow" items={data.workflow} numbered />
        <HelpPanel title="Example tasks" items={data.examples} />
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-[1fr_0.9fr]">
        <HelpPanel title="Boundaries to remember" items={data.boundaries} />
        <div className="rounded-2xl border border-paper-line bg-paper-card p-6 shadow-[var(--shadow-paper)]">
          <h2 className="font-display text-[22px] font-semibold text-ink-text">Related help</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            {data.related.map((item) => (
              <Link
                key={item.href}
                to={item.href}
                className="rounded-full border border-paper-line bg-paper px-3.5 py-1.5 text-[12.5px] font-semibold text-ink-text transition-colors hover:border-amber/50 hover:bg-amber/10"
              >
                {item.label}
              </Link>
            ))}
          </div>
          <div className="mt-6 rounded-xl border border-amber/30 bg-amber/5 p-4 text-[13.5px] leading-relaxed text-ink-muted">
            <strong className="text-ink-text">Structured-writing reminder:</strong> if you need an agent to use this feature's information in a specific chapter, put the relevant fact into Story Bible, Plot Threads, or the chapter's Outline notes.
          </div>
        </div>
      </div>
    </div>
  );
}

function HelpPanel({ title, items, numbered = false }: { title: string; items: string[]; numbered?: boolean }) {
  return (
    <section className="rounded-2xl border border-paper-line bg-paper-card p-6 shadow-[var(--shadow-paper)]">
      <h2 className="font-display text-[22px] font-semibold text-ink-text">{title}</h2>
      {numbered ? (
        <ol className="mt-4 space-y-3">
          {items.map((item, index) => (
            <li key={item} className="flex gap-3 text-[13.5px] leading-relaxed text-ink-muted">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ink text-[11px] font-semibold text-on-ink">
                {index + 1}
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ol>
      ) : (
        <ul className="mt-4 space-y-3">
          {items.map((item) => (
            <li key={item} className="flex gap-2 text-[13.5px] leading-relaxed text-ink-muted">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-deep" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function SectionHeader({ eyebrow, title, body }: { eyebrow: string; title: string; body: string }) {
  return (
    <div className="mb-5">
      <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-amber-deep">{eyebrow}</p>
      <h2 className="font-display text-[28px] font-semibold tracking-tight text-ink-text text-balance">{title}</h2>
      <p className="mt-2 max-w-3xl text-[14px] leading-relaxed text-ink-muted">{body}</p>
    </div>
  );
}

function JumpLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      className="rounded-full border border-paper-line bg-paper px-3.5 py-1.5 text-[12.5px] font-semibold text-ink-text transition-colors hover:border-amber/50 hover:bg-amber/10"
    >
      {children}
    </a>
  );
}

function slug(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}
