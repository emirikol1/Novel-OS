import { useEffect, useMemo, useState } from "react";
import {
  api,
  type CharacterSummary,
  type ChapterSummary,
  type PlotThreadSummary,
  type ResearchSparkSummary,
} from "../api/client";
import DeleteButton from "./DeleteButton";
import Modal, { Field, fieldClass } from "./Modal";
import ToolTip from "./ToolTip";
import { useToast } from "./Toaster";
import {
  RESEARCH_KINDS,
  RESEARCH_KIND_LABELS,
  collectAllTags,
  filterResearchSparks,
  formatTagsInput,
  parseTagsInput,
  type ResearchKind,
} from "../lib/researchSparks";

const KIND_COLOR: Record<ResearchKind, string> = {
  note: "var(--color-st-drafted)",
  link: "var(--color-amber-deep)",
  quote: "var(--color-st-approved)",
  image: "var(--color-st-planned)",
  idea: "var(--color-ink-muted)",
};

function SparkLinks({
  spark,
  charNames,
  plotNames,
}: {
  spark: ResearchSparkSummary;
  charNames: Map<string, string>;
  plotNames: Map<string, string>;
}) {
  const links: string[] = [];
  if (spark.link_character_id) {
    links.push(`Character: ${charNames.get(spark.link_character_id) ?? spark.link_character_id}`);
  }
  if (spark.link_chapter != null) links.push(`Ch. ${spark.link_chapter}`);
  if (spark.link_plot_thread_id) {
    links.push(`Plot: ${plotNames.get(spark.link_plot_thread_id) ?? spark.link_plot_thread_id}`);
  }
  if (spark.link_bible_section) links.push(`Bible: ${spark.link_bible_section}`);
  if (links.length === 0) return null;
  return (
    <p className="mt-2 text-[11px] text-ink-muted">
      {links.join(" · ")}
    </p>
  );
}

export function ResearchSparkModal({
  projectId,
  spark,
  open,
  onClose,
  onSaved,
  characters,
  chapters,
  plotThreads,
}: {
  projectId: string;
  spark: ResearchSparkSummary | null;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  characters: CharacterSummary[];
  chapters: ChapterSummary[];
  plotThreads: PlotThreadSummary[];
}) {
  const toast = useToast();
  const isEdit = spark != null;
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [tagsText, setTagsText] = useState("");
  const [kind, setKind] = useState<ResearchKind>("note");
  const [attachmentRef, setAttachmentRef] = useState("");
  const [linkCharacterId, setLinkCharacterId] = useState("");
  const [linkChapter, setLinkChapter] = useState("");
  const [linkPlotThreadId, setLinkPlotThreadId] = useState("");
  const [linkBibleSection, setLinkBibleSection] = useState("");
  const [busy, setBusy] = useState(false);

  const resetForm = () => {
    setTitle(spark?.title ?? "");
    setBody(spark?.body ?? "");
    setSourceUrl(spark?.source_url ?? "");
    setTagsText(formatTagsInput(spark?.tags ?? []));
    setKind((spark?.kind as ResearchKind) ?? "note");
    setAttachmentRef(spark?.attachment_ref ?? "");
    setLinkCharacterId(spark?.link_character_id ?? "");
    setLinkChapter(spark?.link_chapter != null ? String(spark.link_chapter) : "");
    setLinkPlotThreadId(spark?.link_plot_thread_id ?? "");
    setLinkBibleSection(spark?.link_bible_section ?? "");
  };

  useEffect(() => {
    if (open) resetForm();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, spark?.id]);

  function payload() {
    return {
      title: title.trim(),
      body: body.trim(),
      source_url: sourceUrl.trim(),
      tags: parseTagsInput(tagsText),
      kind,
      attachment_ref: attachmentRef.trim(),
      link_character_id: linkCharacterId || null,
      link_chapter: linkChapter.trim() ? Number(linkChapter) : null,
      link_plot_thread_id: linkPlotThreadId || null,
      link_bible_section: linkBibleSection.trim() || null,
    };
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try {
      if (isEdit && spark) {
        await api.updateResearchSpark(projectId, spark.id, payload());
        toast("Research spark updated", "success");
      } else {
        await api.createResearchSpark(projectId, payload());
        toast("Research spark added", "success");
      }
      onSaved();
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  const chapterNumbers = useMemo(
    () => [...new Set(chapters.map((c) => c.number))].sort((a, b) => a - b),
    [chapters],
  );

  return (
    <Modal
      open={open}
      onClose={busy ? () => {} : onClose}
      title={isEdit ? "Edit Research Spark" : "Add Research Spark"}
    >
      <form onSubmit={submit}>
        <Field label="Title">
          <input
            autoFocus
            className={fieldClass}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Short label for this spark"
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Type">
            <select className={fieldClass} value={kind} onChange={(e) => setKind(e.target.value as ResearchKind)}>
              {RESEARCH_KINDS.map((k) => (
                <option key={k} value={k}>{RESEARCH_KIND_LABELS[k]}</option>
              ))}
            </select>
          </Field>
          <Field label="Tags (comma-separated)">
            <input
              className={fieldClass}
              value={tagsText}
              onChange={(e) => setTagsText(e.target.value)}
              placeholder="history, mood, reference"
            />
          </Field>
        </div>
        <Field label="Notes">
          <textarea
            className={`${fieldClass} min-h-[100px]`}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Ideas, quotes, observations — pre-canon only"
          />
        </Field>
        <Field label="Source URL (optional)">
          <input
            className={fieldClass}
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            placeholder="https://..."
          />
        </Field>
        <Field label="Attachment / reference text (optional)">
          <textarea
            className={`${fieldClass} min-h-[60px]`}
            value={attachmentRef}
            onChange={(e) => setAttachmentRef(e.target.value)}
            placeholder="Filename, caption, or pasted excerpt — not uploaded as binary"
          />
        </Field>
        <p className="mb-3 text-[12px] text-ink-muted">
          Optional links to canon entities (for your reference only — sparks never auto-enter prompts).
        </p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Link character">
            <select className={fieldClass} value={linkCharacterId} onChange={(e) => setLinkCharacterId(e.target.value)}>
              <option value="">—</option>
              {characters.map((ch) => (
                <option key={ch.id} value={ch.id}>{ch.full_name}</option>
              ))}
            </select>
          </Field>
          <Field label="Link chapter">
            <select className={fieldClass} value={linkChapter} onChange={(e) => setLinkChapter(e.target.value)}>
              <option value="">—</option>
              {chapterNumbers.map((n) => (
                <option key={n} value={String(n)}>Ch. {n}</option>
              ))}
            </select>
          </Field>
          <Field label="Link plot thread">
            <select className={fieldClass} value={linkPlotThreadId} onChange={(e) => setLinkPlotThreadId(e.target.value)}>
              <option value="">—</option>
              {plotThreads.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </Field>
          <Field label="Link bible section">
            <input
              className={fieldClass}
              value={linkBibleSection}
              onChange={(e) => setLinkBibleSection(e.target.value)}
              placeholder="e.g. world_building"
            />
          </Field>
        </div>
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
          <ToolTip id="codex.saveResearchSpark">
            <button
              type="submit"
              disabled={!title.trim() || busy}
              className="rounded-lg bg-ink px-5 py-2 text-[13.5px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40"
            >
              {busy ? "Saving…" : isEdit ? "Save changes" : "Add spark"}
            </button>
          </ToolTip>
        </div>
      </form>
    </Modal>
  );
}

export default function ResearchBoardPanel({
  projectId,
  sparks,
  characters,
  chapters,
  plotThreads,
  onChange,
  onAdd,
}: {
  projectId: string;
  sparks: ResearchSparkSummary[];
  characters: CharacterSummary[];
  chapters: ChapterSummary[];
  plotThreads: PlotThreadSummary[];
  onChange: () => void;
  onAdd: () => void;
}) {
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [filterTag, setFilterTag] = useState("all");
  const [filterKind, setFilterKind] = useState("all");
  const [editSpark, setEditSpark] = useState<ResearchSparkSummary | null>(null);

  const charNames = useMemo(() => {
    const map = new Map<string, string>();
    for (const ch of characters) map.set(ch.id, ch.full_name);
    return map;
  }, [characters]);

  const plotNames = useMemo(() => {
    const map = new Map<string, string>();
    for (const t of plotThreads) map.set(t.id, t.name);
    return map;
  }, [plotThreads]);

  const allTags = useMemo(() => collectAllTags(sparks), [sparks]);

  const filtered = useMemo(
    () => filterResearchSparks(sparks, {
      q: search,
      tag: filterTag === "all" ? undefined : filterTag,
      kind: filterKind === "all" ? undefined : filterKind,
    }),
    [sparks, search, filterTag, filterKind],
  );

  const hasFilters = search.trim() !== "" || filterTag !== "all" || filterKind !== "all";

  async function deleteSpark(spark: ResearchSparkSummary) {
    try {
      await api.deleteResearchSpark(projectId, spark.id);
      toast("Research spark removed", "success");
      onChange();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    }
  }

  if (sparks.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-10 text-center text-[13.5px] text-ink-muted">
        No research sparks yet.{" "}
        <ToolTip id="codex.researchSpark" className="inline">
          <button
            type="button"
            onClick={onAdd}
            className="font-semibold text-amber-deep underline-offset-2 hover:underline"
          >
            Add your first spark
          </button>
        </ToolTip>{" "}
        to collect pre-canon notes, links, and references.
      </div>
    );
  }

  return (
    <>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="flex min-w-[180px] flex-1 flex-col gap-1 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          Search
          <input
            className="rounded-lg border border-paper-line bg-paper-card px-2.5 py-1.5 text-[13px] font-normal normal-case text-ink-text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Title, notes, tags…"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          Tag
          <select
            className="min-w-[120px] rounded-lg border border-paper-line bg-paper-card px-2.5 py-1.5 text-[13px] font-normal normal-case text-ink-text"
            value={filterTag}
            onChange={(e) => setFilterTag(e.target.value)}
          >
            <option value="all">All</option>
            {allTags.map((tag) => (
              <option key={tag} value={tag}>{tag}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
          Type
          <select
            className="min-w-[100px] rounded-lg border border-paper-line bg-paper-card px-2.5 py-1.5 text-[13px] font-normal normal-case text-ink-text"
            value={filterKind}
            onChange={(e) => setFilterKind(e.target.value)}
          >
            <option value="all">All</option>
            {RESEARCH_KINDS.map((k) => (
              <option key={k} value={k}>{RESEARCH_KIND_LABELS[k]}</option>
            ))}
          </select>
        </label>
        {hasFilters && (
          <ToolTip id="dashboard.clearFilter">
            <button
              type="button"
              onClick={() => { setSearch(""); setFilterTag("all"); setFilterKind("all"); }}
              className="rounded-lg px-2 py-1.5 text-[12px] font-medium text-ink-muted hover:bg-ink/5"
            >
              Clear filters
            </button>
          </ToolTip>
        )}
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-8 text-center text-[13.5px] text-ink-muted">
          No sparks match your filters.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {filtered.map((spark) => (
            <article
              key={spark.id}
              className="group relative rounded-xl border border-paper-line bg-paper-card p-4 shadow-[var(--shadow-paper)]"
            >
              <DeleteButton
                label={`Delete ${spark.title}`}
                title="Delete spark"
                message={`Remove "${spark.title}" from research?`}
                onConfirm={() => deleteSpark(spark)}
                tipId="codex.deleteResearchSpark"
                className="absolute right-2 top-2 opacity-0 transition-opacity group-hover:opacity-100"
              />
              <ToolTip id="codex.researchSpark" className="block w-full">
                <button
                  type="button"
                  onClick={() => setEditSpark(spark)}
                  className="w-full text-left"
                >
                <div className="flex items-start gap-2 pr-8">
                  <span
                    className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: KIND_COLOR[spark.kind as ResearchKind] ?? KIND_COLOR.note }}
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    <p className="font-display text-[15px] font-medium text-ink-text">{spark.title}</p>
                    <p className="mt-0.5 text-[11px] capitalize text-ink-muted">
                      {RESEARCH_KIND_LABELS[spark.kind as ResearchKind] ?? spark.kind}
                    </p>
                  </div>
                </div>
                {spark.body && (
                  <p className="mt-2 line-clamp-4 whitespace-pre-wrap text-[13px] text-ink-muted">
                    {spark.body}
                  </p>
                )}
                {spark.source_url && (
                  <p className="mt-2 truncate text-[12px]">
                    <a
                      href={spark.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-amber-deep hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {spark.source_url}
                    </a>
                  </p>
                )}
                {spark.attachment_ref && (
                  <p className="mt-2 line-clamp-2 text-[12px] italic text-ink-muted">
                    Ref: {spark.attachment_ref}
                  </p>
                )}
                {spark.tags.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {spark.tags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full bg-ink/6 px-2 py-0.5 text-[11px] font-medium text-ink-muted"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                <SparkLinks spark={spark} charNames={charNames} plotNames={plotNames} />
                </button>
              </ToolTip>
            </article>
          ))}
        </div>
      )}

      <ResearchSparkModal
        projectId={projectId}
        spark={editSpark}
        open={editSpark != null}
        onClose={() => setEditSpark(null)}
        onSaved={onChange}
        characters={characters}
        chapters={chapters}
        plotThreads={plotThreads}
      />
    </>
  );
}
