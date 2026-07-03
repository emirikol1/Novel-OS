import { useEffect, useMemo, useState } from "react";
import {
  api,
  type CharacterSummary,
  type StoryGraphEdgeSummary,
  type StoryGraphNodeSummary,
} from "../api/client";
import { NODE_KINDS, NODE_STATUSES, kindLabel } from "../lib/storyGraph";
import Modal, { fieldClass } from "./Modal";
import ToolTip from "./ToolTip";
import { useToast } from "./Toaster";

type CreatePlotFromBriefModalProps = {
  open: boolean;
  onClose: () => void;
  projectId: string;
  chapterNumber: number;
  characters: CharacterSummary[];
  graphNodes: StoryGraphNodeSummary[];
  graphEdges: StoryGraphEdgeSummary[];
  onCreated: (node: StoryGraphNodeSummary) => void;
};

type CreatePlotForm = {
  title: string;
  kind: string;
  description: string;
  status: string;
  start_chapter: number;
  resolution_chapter: number | "";
  linked_character_ids: string[];
  parent_id: string;
  assign_to_brief: boolean;
};

function emptyForm(chapterNumber: number): CreatePlotForm {
  return {
    title: "",
    kind: "subplot",
    description: "",
    status: "active",
    start_chapter: chapterNumber,
    resolution_chapter: "",
    linked_character_ids: [],
    parent_id: "",
    assign_to_brief: true,
  };
}

export default function CreatePlotFromBriefModal({
  open,
  onClose,
  projectId,
  chapterNumber,
  characters,
  graphNodes,
  graphEdges,
  onCreated,
}: CreatePlotFromBriefModalProps) {
  const toast = useToast();
  const [form, setForm] = useState<CreatePlotForm>(() => emptyForm(chapterNumber));
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(emptyForm(chapterNumber));
  }, [open, chapterNumber]);

  const parentOptions = useMemo(
    () =>
      [...graphNodes]
        .filter((node) => node.kind === "main" || node.kind === "plot_thread" || node.kind === "subplot")
        .sort((a, b) => a.title.localeCompare(b.title)),
    [graphNodes],
  );

  function toggleCharacter(charId: string) {
    setForm((current) => ({
      ...current,
      linked_character_ids: current.linked_character_ids.includes(charId)
        ? current.linked_character_ids.filter((id) => id !== charId)
        : [...current.linked_character_ids, charId],
    }));
  }

  async function createPlot() {
    if (!form.title.trim()) {
      toast("Title is required", "error");
      return;
    }
    if (form.resolution_chapter !== "" && form.resolution_chapter < form.start_chapter) {
      toast("Resolution chapter must be on or after the start chapter", "error");
      return;
    }

    setBusy(true);
    try {
      const node = await api.createStoryGraphNode(projectId, {
        title: form.title.trim(),
        kind: form.kind,
        description: form.description,
        status: form.status,
        linked_character_ids: form.linked_character_ids,
        start_chapter: form.start_chapter,
        resolution_chapter: form.resolution_chapter === "" ? null : form.resolution_chapter,
        chapter_number: chapterNumber,
        assign_to_brief: form.assign_to_brief,
      });

      if (form.parent_id) {
        const hasEdge = graphEdges.some(
          (edge) =>
            edge.kind === "contains"
            && edge.source_id === form.parent_id
            && edge.target_id === node.id,
        );
        if (!hasEdge) {
          await api.createStoryGraphEdge(projectId, {
            source_id: form.parent_id,
            target_id: node.id,
            kind: "contains",
          });
        }
      }

      toast("Plot created", "success");
      onCreated(node);
      onClose();
    } catch (e) {
      toast(String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={busy ? () => {} : onClose}
      title={`New plot/subplot for chapter ${chapterNumber}`}
      size="wide"
    >
      <div className="space-y-4" data-testid="create-plot-from-brief-modal">
        <label className="block">
          <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            Title *
          </span>
          <input
            className={fieldClass}
            value={form.title}
            onChange={(e) => setForm((current) => ({ ...current, title: e.target.value }))}
            placeholder="Plot or subplot title"
          />
        </label>

        <div className="grid gap-4 md:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
              Kind
            </span>
            <select
              className={fieldClass}
              value={form.kind}
              onChange={(e) => setForm((current) => ({ ...current, kind: e.target.value }))}
            >
              {NODE_KINDS.map((kind) => (
                <option key={kind} value={kind}>{kindLabel(kind)}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
              Status
            </span>
            <select
              className={fieldClass}
              value={form.status}
              onChange={(e) => setForm((current) => ({ ...current, status: e.target.value }))}
            >
              {NODE_STATUSES.map((status) => (
                <option key={status} value={status}>{status}</option>
              ))}
            </select>
          </label>
        </div>

        <label className="block">
          <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            Description
          </span>
          <textarea
            className={fieldClass}
            rows={2}
            value={form.description}
            onChange={(e) => setForm((current) => ({ ...current, description: e.target.value }))}
          />
        </label>

        <div className="grid gap-4 md:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
              Lifespan start
            </span>
            <input
              type="number"
              min={1}
              className={fieldClass}
              value={form.start_chapter}
              onChange={(e) =>
                setForm((current) => ({
                  ...current,
                  start_chapter: Math.max(1, Number.parseInt(e.target.value, 10) || 1),
                }))
              }
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
              Resolution chapter
            </span>
            <input
              type="number"
              min={1}
              className={fieldClass}
              value={form.resolution_chapter}
              placeholder="Open-ended"
              onChange={(e) => {
                const raw = e.target.value.trim();
                setForm((current) => ({
                  ...current,
                  resolution_chapter: raw === "" ? "" : Math.max(1, Number.parseInt(raw, 10) || 1),
                }));
              }}
            />
          </label>
        </div>

        {characters.length > 0 && (
          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
              Linked cast
            </p>
            <div className="flex flex-wrap gap-2">
              {characters.map((character) => (
                <label
                  key={character.id}
                  className={`cursor-pointer rounded-lg border px-2.5 py-1 text-[12px] ${
                    form.linked_character_ids.includes(character.id)
                      ? "border-amber-deep bg-amber/10 text-ink-text"
                      : "border-paper-line text-ink-muted"
                  }`}
                >
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={form.linked_character_ids.includes(character.id)}
                    onChange={() => toggleCharacter(character.id)}
                  />
                  {character.full_name}
                </label>
              ))}
            </div>
          </div>
        )}

        {parentOptions.length > 0 && (
          <label className="block">
            <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
              Parent plot (optional)
            </span>
            <select
              className={fieldClass}
              value={form.parent_id}
              onChange={(e) => setForm((current) => ({ ...current, parent_id: e.target.value }))}
            >
              <option value="">— none —</option>
              {parentOptions.map((node) => (
                <option key={node.id} value={node.id}>{node.title}</option>
              ))}
            </select>
          </label>
        )}

        <label className="flex items-center gap-2 text-[13px] text-ink-text">
          <input
            type="checkbox"
            checked={form.assign_to_brief}
            onChange={(e) => setForm((current) => ({ ...current, assign_to_brief: e.target.checked }))}
          />
          Add to this chapter (in effect)
        </label>

        <div className="flex justify-end gap-2 border-t border-paper-line/60 pt-3">
          <ToolTip id="modal.cancel">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40"
            >
              Cancel
            </button>
          </ToolTip>
          <ToolTip id="codex.createPlotFromBrief">
            <button
              type="button"
              onClick={() => void createPlot()}
              disabled={busy}
              className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40"
            >
              {busy ? "Creating…" : "Create plot"}
            </button>
          </ToolTip>
        </div>
      </div>
    </Modal>
  );
}
