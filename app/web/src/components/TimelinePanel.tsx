import { useEffect, useMemo, useState } from "react";
import {
  api,
  type CharacterSummary,
  type ChapterSummary,
  type TimelineGeneratedEvent,
  type TimelineGenerationResult,
  type TimelineEventSummary,
} from "../api/client";
import DeleteButton from "./DeleteButton";
import ToolTip from "./ToolTip";
import { useConfirm } from "./Confirm";
import Modal, { Field } from "./Modal";
import { fieldClass } from "./Modal";
import { useToast } from "./Toaster";

const EVENT_TYPES = ["scene", "backstory", "flashback", "summary"] as const;
const SIGNIFICANCE_LEVELS = ["minor", "major", "turning_point", "climax"] as const;

const SIGNIFICANCE_COLOR: Record<string, string> = {
  minor: "var(--color-ink-muted)",
  major: "var(--color-st-drafted)",
  turning_point: "var(--color-amber-deep)",
  climax: "var(--color-st-planned)",
};

function defaultTimelineSelections(result: TimelineGenerationResult): Set<number> {
  const counts = new Map<number, number>();
  const selected = new Set<number>();
  result.candidates.forEach((event, index) => {
    const count = counts.get(event.chapter) ?? 0;
    if (count < result.recommended_per_chapter) {
      selected.add(index);
      counts.set(event.chapter, count + 1);
    }
  });
  return selected;
}

function formatWhen(event: TimelineEventSummary): string {
  const parts = [`Ch. ${event.chapter}`];
  if (event.day != null) parts.push(`Day ${event.day}`);
  if (event.time) parts.push(event.time);
  return parts.join(" · ");
}

export function TimelineEventModal({
  projectId,
  event,
  open,
  onClose,
  onSaved,
  characters,
  defaultChapter = 1,
}: {
  projectId: string;
  event: TimelineEventSummary | null;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  characters: CharacterSummary[];
  defaultChapter?: number;
}) {
  const toast = useToast();
  const isEdit = event != null;
  const [description, setDescription] = useState("");
  const [chapter, setChapter] = useState(1);
  const [day, setDay] = useState("");
  const [time, setTime] = useState("");
  const [location, setLocation] = useState("");
  const [eventType, setEventType] = useState<string>("scene");
  const [significance, setSignificance] = useState<string>("minor");
  const [selectedChars, setSelectedChars] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const resetForm = () => {
    setDescription(event?.description ?? "");
    setChapter(event?.chapter ?? defaultChapter);
    setDay(event?.day != null ? String(event.day) : "");
    setTime(event?.time ?? "");
    setLocation(event?.location ?? "");
    setEventType(event?.event_type ?? "scene");
    setSignificance(event?.significance ?? "minor");
    setSelectedChars(event?.characters_present ?? []);
  };

  // Reset when modal opens or event changes
  useEffect(() => {
    if (open) resetForm();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, event?.id]);

  function toggleChar(charId: string) {
    setSelectedChars((prev) =>
      prev.includes(charId) ? prev.filter((id) => id !== charId) : [...prev, charId],
    );
  }

  function payload() {
    return {
      description: description.trim(),
      chapter,
      day: day.trim() ? Number(day) : null,
      time: time.trim() || null,
      location,
      characters_present: selectedChars,
      event_type: eventType,
      significance,
    };
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!description.trim()) return;
    setBusy(true);
    try {
      if (isEdit && event) {
        await api.updateTimelineEvent(projectId, event.id, payload());
        toast("Timeline event updated", "success");
      } else {
        await api.createTimelineEvent(projectId, payload());
        toast("Timeline event added", "success");
      }
      onSaved();
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={busy ? () => {} : onClose}
      title={isEdit ? "Edit Timeline Event" : "Add Timeline Event"}
    >
      <form onSubmit={submit}>
        <Field label="Description">
          <textarea
            autoFocus
            className={`${fieldClass} min-h-[80px]`}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What happens in this event?"
          />
        </Field>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Chapter">
            <input
              type="number"
              min={1}
              className={fieldClass}
              value={chapter}
              onChange={(e) => setChapter(Number(e.target.value))}
            />
          </Field>
          <Field label="Day (optional)">
            <input
              type="number"
              min={0}
              className={fieldClass}
              value={day}
              onChange={(e) => setDay(e.target.value)}
              placeholder="—"
            />
          </Field>
          <Field label="Time (optional)">
            <input
              className={fieldClass}
              value={time}
              onChange={(e) => setTime(e.target.value)}
              placeholder="e.g. dawn, 3pm"
            />
          </Field>
        </div>
        <Field label="Location">
          <input
            className={fieldClass}
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Where does this happen?"
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Event type">
            <select
              className={fieldClass}
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
            >
              {EVENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replace("_", " ")}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Significance">
            <select
              className={fieldClass}
              value={significance}
              onChange={(e) => setSignificance(e.target.value)}
            >
              {SIGNIFICANCE_LEVELS.map((s) => (
                <option key={s} value={s}>
                  {s.replace("_", " ")}
                </option>
              ))}
            </select>
          </Field>
        </div>
        {characters.length > 0 && (
          <Field label="Characters present">
            <div className="flex flex-wrap gap-2 rounded-lg border border-paper-line bg-paper-card/60 p-3">
              {characters.map((ch) => {
                const on = selectedChars.includes(ch.id);
                return (
                  <ToolTip key={ch.id} id="codex.editTimelineEvent">
                    <button
                      type="button"
                      onClick={() => toggleChar(ch.id)}
                      className={`rounded-full px-3 py-1 text-[12px] font-medium transition-colors ${
                        on
                          ? "bg-ink text-on-ink"
                          : "border border-paper-line text-ink-muted hover:border-amber/40 hover:text-ink-text"
                      }`}
                    >
                      {ch.full_name}
                    </button>
                  </ToolTip>
                );
              })}
            </div>
          </Field>
        )}
        <div className="mt-6 flex justify-end gap-3">
          <ToolTip id="modal.cancel">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="rounded-lg px-4 py-2 text-[13.5px] font-semibold text-ink-muted hover:bg-ink/5 disabled:opacity-40"
            >
              Cancel
            </button>
          </ToolTip>
          <ToolTip id="codex.saveTimelineEvent">
            <button
              type="submit"
              disabled={!description.trim() || busy}
              className="rounded-lg bg-ink px-5 py-2 text-[13.5px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40"
            >
              {busy ? "Saving…" : isEdit ? "Save changes" : "Add event"}
            </button>
          </ToolTip>
        </div>
      </form>
    </Modal>
  );
}

function TimelineGenerateModal({
  projectId,
  chapters,
  open,
  onClose,
  onApplied,
}: {
  projectId: string;
  chapters: ChapterSummary[];
  open: boolean;
  onClose: () => void;
  onApplied: () => void;
}) {
  const toast = useToast();
  const [source, setSource] = useState("best");
  const [maxEvents, setMaxEvents] = useState(5);
  const [busy, setBusy] = useState(false);
  const [applying, setApplying] = useState(false);
  const [result, setResult] = useState<TimelineGenerationResult | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [selectedChapters, setSelectedChapters] = useState<Set<number>>(
    () => new Set(chapters.map((chapter) => chapter.number)),
  );

  useEffect(() => {
    if (!open) return;
    setResult(null);
    setSelected(new Set());
    setSelectedChapters(new Set(chapters.map((chapter) => chapter.number)));
  }, [open, chapters]);

  async function generate() {
    setBusy(true);
    try {
      const next = await api.generateTimeline(projectId, {
        source,
        max_events_per_chapter: maxEvents,
        chapters: selectedChapters.size === chapters.length ? undefined : [...selectedChapters],
      });
      setResult(next);
      setSelected(defaultTimelineSelections(next));
      if (next.candidates.length === 0) {
        toast("No timeline candidates found in chapter text", "info");
      } else {
        toast(`Found ${next.candidates.length} timeline candidate(s)`, "success");
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  function toggle(index: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  async function applySelected() {
    if (!result) return;
    const events = result.candidates.filter((_, index) => selected.has(index));
    if (events.length === 0) {
      toast("Select at least one generated event to apply", "error");
      return;
    }
    setApplying(true);
    try {
      const applied = await api.applyGeneratedTimelineEvents(projectId, events);
      toast(`Added ${applied.created.length} timeline event(s)`, "success");
      onApplied();
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setApplying(false);
    }
  }

  return (
    <Modal open={open} onClose={busy || applying ? () => {} : onClose} title="Generate Timeline from Chapters" size="wide">
      <div className="space-y-4">
        <p className="rounded-lg border border-amber/25 bg-amber/5 px-4 py-2.5 text-[12.5px] leading-relaxed text-ink-muted">
          This scans chapter manuscript text and creates reviewable candidate events. Nothing is
          added to the saved timeline until you select candidates and apply them. Candidates are ranked
          by turning-point/action cues, named characters, location/time markers, and scene-sized passages.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Text source">
            <select className={fieldClass} value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="best">Best available: final, revised, draft</option>
              <option value="final">Final only</option>
              <option value="revised">Revised only</option>
              <option value="draft">Draft only</option>
            </select>
          </Field>
          <Field label="Max events per chapter">
            <input
              type="number"
              min={1}
              max={12}
              className={fieldClass}
              value={maxEvents}
              onChange={(e) => setMaxEvents(Math.max(1, Math.min(12, Number(e.target.value) || 1)))}
            />
          </Field>
        </div>
        {chapters.length > 0 && (
          <div>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                Chapters to scan
              </p>
              <ToolTip id="codex.timelineSelectCandidates">
                <button
                  type="button"
                  onClick={() =>
                    setSelectedChapters(
                      selectedChapters.size === chapters.length
                        ? new Set()
                        : new Set(chapters.map((chapter) => chapter.number)),
                    )
                  }
                  className="text-[12px] font-semibold text-amber-deep hover:underline"
                >
                  {selectedChapters.size === chapters.length ? "Select none" : "Select all"}
                </button>
              </ToolTip>
            </div>
            <div className="flex max-h-32 flex-wrap gap-2 overflow-auto rounded-lg border border-paper-line bg-paper p-2">
              {chapters.map((chapter) => {
                const checked = selectedChapters.has(chapter.number);
                return (
                  <label
                    key={chapter.number}
                    className={`cursor-pointer rounded-lg border px-2.5 py-1 text-[12px] ${
                      checked ? "border-amber-deep bg-amber/10 text-ink-text" : "border-paper-line text-ink-muted"
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="sr-only"
                      checked={checked}
                      onChange={() =>
                        setSelectedChapters((prev) => {
                          const next = new Set(prev);
                          if (next.has(chapter.number)) next.delete(chapter.number);
                          else next.add(chapter.number);
                          return next;
                        })
                      }
                    />
                    Ch. {chapter.number}{chapter.title ? `: ${chapter.title}` : ""}
                  </label>
                );
              })}
            </div>
          </div>
        )}
        <ToolTip id="codex.timelineEvent">
          <button
            type="button"
            onClick={() => void generate()}
            disabled={busy || selectedChapters.size === 0}
            className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40"
          >
            {busy ? "Scanning chapters..." : "Scan chapter text"}
          </button>
        </ToolTip>

        {result && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-[12.5px] text-ink-muted">
                Scanned {result.chapters_scanned.length} chapter(s); found {result.candidates.length} ranked candidate(s).
                Top {result.recommended_per_chapter} per chapter are preselected; alternates remain available if you reject one.
              </p>
              {result.candidates.length > 0 && (
                <ToolTip id="codex.timelineSelectCandidates">
                  <button
                    type="button"
                    onClick={() =>
                      setSelected(
                        selected.size === result.candidates.length
                          ? new Set()
                          : new Set(result.candidates.map((_, index) => index)),
                      )
                    }
                    className="text-[12px] font-semibold text-amber-deep hover:underline"
                  >
                    {selected.size === result.candidates.length ? "Select none" : "Select all"}
                  </button>
                </ToolTip>
              )}
            </div>
            {result.skipped_chapters.length > 0 && (
              <div className="rounded-lg border border-paper-line bg-paper px-3 py-2 text-[12px] text-ink-muted">
                <span className="font-semibold text-ink-text">Skipped: </span>
                {result.skipped_chapters.map((row) => `Ch. ${row.chapter} (${row.reason})`).join("; ")}
              </div>
            )}
            <ol className="max-h-[46vh] space-y-2 overflow-auto pr-1">
              {result.candidates.map((event, index) => (
                <GeneratedTimelineRow
                  key={`${event.chapter}-${index}-${event.description}`}
                  event={event}
                  selected={selected.has(index)}
                  onToggle={() => toggle(index)}
                />
              ))}
            </ol>
            <div className="flex justify-end gap-2 pt-2">
              <ToolTip id="global.modalClose">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={applying}
                  className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40"
                >
                  Close
                </button>
              </ToolTip>
              <ToolTip id="codex.saveTimelineEvent">
                <button
                  type="button"
                  onClick={() => void applySelected()}
                  disabled={applying || selected.size === 0}
                  className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40"
                >
                  {applying ? "Adding..." : `Add ${selected.size} selected`}
                </button>
              </ToolTip>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

function GeneratedTimelineRow({
  event,
  selected,
  onToggle,
}: {
  event: TimelineGeneratedEvent;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <li className="rounded-lg border border-paper-line bg-paper-card p-3">
      <label className="flex cursor-pointer items-start gap-3">
        <input type="checkbox" checked={selected} onChange={onToggle} className="mt-1" />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-[12px] font-semibold text-amber-deep">
              Ch. {event.chapter} · {event.source} · score {event.score}
            </span>
            <span className="rounded-full bg-ink/5 px-2 py-0.5 text-[11px] capitalize text-ink-muted">
              {event.event_type.replace("_", " ")}
            </span>
            <span className="rounded-full bg-amber/10 px-2 py-0.5 text-[11px] capitalize text-amber-deep">
              {event.significance.replace("_", " ")}
            </span>
          </span>
          <span className="mt-1 block text-[13.5px] leading-snug text-ink-text">{event.description}</span>
          {event.reason && (
            <span className="mt-1 block text-[11.5px] font-medium text-amber-deep">
              Why suggested: {event.reason}
            </span>
          )}
          {(event.location || event.time || event.day != null || event.characters_present.length > 0) && (
            <span className="mt-1 block text-[12px] text-ink-muted">
              {[event.day != null ? `Day ${event.day}` : "", event.time, event.location, event.characters_present.join(", ")]
                .filter(Boolean)
                .join(" · ")}
            </span>
          )}
          {event.excerpt && (
            <span className="mt-1 block line-clamp-2 text-[11.5px] leading-snug text-ink-muted">
              {event.excerpt}
            </span>
          )}
        </span>
      </label>
    </li>
  );
}

export default function TimelinePanel({
  projectId,
  events,
  characters,
  chapters,
  onChange,
  onAdd,
}: {
  projectId: string;
  events: TimelineEventSummary[];
  characters: CharacterSummary[];
  chapters: ChapterSummary[];
  onChange: () => void;
  onAdd: () => void;
}) {
  const toast = useToast();
  const confirm = useConfirm();
  const [filterChapter, setFilterChapter] = useState<string>("all");
  const [filterCharacter, setFilterCharacter] = useState<string>("all");
  const [filterType, setFilterType] = useState<string>("all");
  const [filterSignificance, setFilterSignificance] = useState<string>("all");
  const [editEvent, setEditEvent] = useState<TimelineEventSummary | null>(null);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [expandedChapters, setExpandedChapters] = useState<Set<number>>(() => new Set());

  const charNames = useMemo(() => {
    const map = new Map<string, string>();
    for (const ch of characters) map.set(ch.id, ch.full_name);
    return map;
  }, [characters]);

  const chapterNumbers = useMemo(
    () => [...new Set(chapters.map((c) => c.number))].sort((a, b) => a - b),
    [chapters],
  );

  const filtered = useMemo(() => {
    return events.filter((e) => {
      if (filterChapter !== "all" && e.chapter !== Number(filterChapter)) return false;
      if (filterCharacter !== "all" && !e.characters_present.includes(filterCharacter)) return false;
      if (filterType !== "all" && e.event_type !== filterType) return false;
      if (filterSignificance !== "all" && e.significance !== filterSignificance) return false;
      return true;
    });
  }, [events, filterChapter, filterCharacter, filterType, filterSignificance]);

  const chapterTitleByNumber = useMemo(() => {
    const map = new Map<number, string>();
    for (const chapter of chapters) {
      if (chapter.title) map.set(chapter.number, chapter.title);
    }
    return map;
  }, [chapters]);

  const eventsByChapter = useMemo(() => {
    const map = new Map<number, TimelineEventSummary[]>();
    for (const event of filtered) {
      const list = map.get(event.chapter) ?? [];
      list.push(event);
      map.set(event.chapter, list);
    }
    return [...map.entries()].sort((a, b) => a[0] - b[0]);
  }, [filtered]);

  function toggleChapterExpanded(chapterNumber: number) {
    setExpandedChapters((prev) => {
      const next = new Set(prev);
      if (next.has(chapterNumber)) next.delete(chapterNumber);
      else next.add(chapterNumber);
      return next;
    });
  }

  function renderTimelineEvent(event: TimelineEventSummary) {
    return (
      <li key={event.id} className="group relative pb-6 last:pb-0">
        <span
          className="absolute -left-[9px] top-1.5 h-4 w-4 rounded-full border-2 border-paper-card"
          style={{ backgroundColor: SIGNIFICANCE_COLOR[event.significance] ?? "var(--color-ink-muted)" }}
        />
        <ToolTip id="codex.timelineEvent" className="relative block w-full">
          <div
            role="button"
            tabIndex={0}
            onClick={() => setEditEvent(event)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setEditEvent(event);
              }
            }}
            className="relative w-full cursor-pointer rounded-xl border border-paper-line bg-paper-card p-4 text-left shadow-[var(--shadow-paper)] transition-colors hover:border-amber/40"
          >
            <DeleteButton
              label="Delete timeline event"
              title="Delete event"
              message="Remove this timeline event?"
              onConfirm={() => deleteEvent(event)}
              tipId="codex.deleteTimelineEvent"
              className="absolute right-2 top-2 opacity-0 transition-opacity group-hover:opacity-100"
            />
            <div className="flex flex-wrap items-center gap-2 pr-8">
              <span className="text-[12px] font-semibold text-amber-deep">{formatWhen(event)}</span>
              <span className="rounded-full bg-ink/5 px-2 py-0.5 text-[11px] capitalize text-ink-muted">
                {event.event_type.replace("_", " ")}
              </span>
              <span
                className="rounded-full px-2 py-0.5 text-[11px] capitalize text-on-ink"
                style={{ backgroundColor: SIGNIFICANCE_COLOR[event.significance] ?? "var(--color-ink-muted)" }}
              >
                {event.significance.replace("_", " ")}
              </span>
            </div>
            <p className="mt-2 text-[14px] leading-snug text-ink-text">{event.description}</p>
            {(event.location || event.characters_present.length > 0) && (
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-muted">
                {event.location && <span>📍 {event.location}</span>}
                {event.characters_present.length > 0 && (
                  <span>
                    👤{" "}
                    {event.characters_present
                      .map((id) => charNames.get(id) ?? id)
                      .join(", ")}
                  </span>
                )}
              </div>
            )}
          </div>
        </ToolTip>
      </li>
    );
  }

  const hasFilters =
    filterChapter !== "all" ||
    filterCharacter !== "all" ||
    filterType !== "all" ||
    filterSignificance !== "all";

  async function deleteEvent(event: TimelineEventSummary) {
    try {
      await api.deleteTimelineEvent(projectId, event.id);
      toast("Timeline event removed", "success");
      onChange();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  async function deleteAllEvents() {
    const ok = await confirm({
      title: "Delete all timeline events?",
      message: "This removes every saved timeline entry so you can regenerate from chapter text. Manuscript chapters are not changed.",
      confirmLabel: "Delete all timeline events",
      danger: true,
    });
    if (!ok) return;
    try {
      const result = await api.deleteAllTimelineEvents(projectId);
      toast(`Deleted ${result.deleted} timeline event(s)`, "success");
      onChange();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  if (events.length === 0) {
    return (
      <>
        <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-10 text-center text-[13.5px] text-ink-muted">
          <p>No timeline events yet.</p>
          <p className="mt-2">
            <ToolTip id="codex.timelineEvent" className="inline">
              <button
                type="button"
                onClick={() => setGenerateOpen(true)}
                className="font-semibold text-amber-deep underline-offset-2 hover:underline"
              >
                Generate from chapter text
              </button>
            </ToolTip>{" "}
            or{" "}
            <ToolTip id="codex.timelineEvent" className="inline">
              <button
                type="button"
                onClick={onAdd}
                className="font-semibold text-amber-deep underline-offset-2 hover:underline"
              >
                add your first event
              </button>
            </ToolTip>{" "}
            to track when key story beats happen.
          </p>
        </div>
        <TimelineGenerateModal
          projectId={projectId}
          chapters={chapters}
          open={generateOpen}
          onClose={() => setGenerateOpen(false)}
          onApplied={onChange}
        />
      </>
    );
  }

  return (
    <>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <ToolTip id="codex.timelineEvent">
          <button
            type="button"
            onClick={() => setGenerateOpen(true)}
            className="rounded-lg border border-amber/40 bg-amber/5 px-3.5 py-1.5 text-[12.5px] font-semibold text-ink-text hover:bg-amber/10"
            title="Scan chapter text and review suggested timeline events before saving"
          >
            Generate from chapters
          </button>
        </ToolTip>
        <ToolTip id="codex.deleteTimelineEvent">
          <button
            type="button"
            onClick={() => void deleteAllEvents()}
            className="rounded-lg border border-red-200 px-3.5 py-1.5 text-[12.5px] font-semibold text-red-700 hover:bg-red-50"
            title="Delete all saved timeline events before regenerating"
          >
            Delete all timeline events
          </button>
        </ToolTip>
        <label className="flex flex-col gap-1 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          Chapter
          <select
            className="min-w-[100px] rounded-lg border border-paper-line bg-paper-card px-2.5 py-1.5 text-[13px] font-normal normal-case text-ink-text"
            value={filterChapter}
            onChange={(e) => setFilterChapter(e.target.value)}
          >
            <option value="all">All</option>
            {chapterNumbers.map((n) => (
              <option key={n} value={String(n)}>
                Ch. {n}
              </option>
            ))}
            {[...new Set(events.map((e) => e.chapter))]
              .filter((n) => !chapterNumbers.includes(n))
              .sort((a, b) => a - b)
              .map((n) => (
                <option key={n} value={String(n)}>
                  Ch. {n}
                </option>
              ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          Character
          <select
            className="min-w-[120px] rounded-lg border border-paper-line bg-paper-card px-2.5 py-1.5 text-[13px] font-normal normal-case text-ink-text"
            value={filterCharacter}
            onChange={(e) => setFilterCharacter(e.target.value)}
          >
            <option value="all">All</option>
            {characters.map((ch) => (
              <option key={ch.id} value={ch.id}>
                {ch.full_name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          Type
          <select
            className="min-w-[110px] rounded-lg border border-paper-line bg-paper-card px-2.5 py-1.5 text-[13px] font-normal normal-case text-ink-text"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
          >
            <option value="all">All</option>
            {EVENT_TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace("_", " ")}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          Significance
          <select
            className="min-w-[120px] rounded-lg border border-paper-line bg-paper-card px-2.5 py-1.5 text-[13px] font-normal normal-case text-ink-text"
            value={filterSignificance}
            onChange={(e) => setFilterSignificance(e.target.value)}
          >
            <option value="all">All</option>
            {SIGNIFICANCE_LEVELS.map((s) => (
              <option key={s} value={s}>
                {s.replace("_", " ")}
              </option>
            ))}
          </select>
        </label>
        {hasFilters && (
          <ToolTip id="dashboard.clearFilter">
            <button
              type="button"
              onClick={() => {
                setFilterChapter("all");
                setFilterCharacter("all");
                setFilterType("all");
                setFilterSignificance("all");
              }}
              className="rounded-lg px-2 py-1.5 text-[12px] font-semibold text-amber-deep hover:underline"
            >
              Clear filters
            </button>
          </ToolTip>
        )}
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-8 text-center text-[13.5px] text-ink-muted">
          No events match the current filters.
        </div>
      ) : (
        <div className="space-y-3">
          {eventsByChapter.map(([chapterNumber, chapterEvents]) => {
            const expanded = expandedChapters.has(chapterNumber);
            const chapterTitle = chapterTitleByNumber.get(chapterNumber);
            return (
              <section
                key={chapterNumber}
                className="rounded-xl border border-paper-line bg-paper-card/40"
              >
                <button
                  type="button"
                  onClick={() => toggleChapterExpanded(chapterNumber)}
                  aria-expanded={expanded}
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
                >
                  <span className="text-[14px] font-semibold text-ink-text">
                    Chapter {chapterNumber}
                    {chapterTitle ? `: ${chapterTitle}` : ""}
                  </span>
                  <span className="flex items-center gap-2 text-[12px] text-ink-muted">
                    <span>
                      {chapterEvents.length} event{chapterEvents.length === 1 ? "" : "s"}
                    </span>
                    <span aria-hidden>{expanded ? "▾" : "▸"}</span>
                  </span>
                </button>
                {expanded && (
                  <ol className="relative space-y-0 border-t border-paper-line px-4 pb-4 pt-3 pl-10 border-l-2 border-l-paper-line ml-6">
                    {chapterEvents.map((event) => renderTimelineEvent(event))}
                  </ol>
                )}
              </section>
            );
          })}
        </div>
      )}

      <TimelineEventModal
        projectId={projectId}
        event={editEvent}
        open={editEvent != null}
        onClose={() => setEditEvent(null)}
        onSaved={onChange}
        characters={characters}
      />
      <TimelineGenerateModal
        projectId={projectId}
        chapters={chapters}
        open={generateOpen}
        onClose={() => setGenerateOpen(false)}
        onApplied={onChange}
      />
    </>
  );
}
