import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  type CharacterSummary,
  type ChapterSummary,
  type StoryGraphEdgeSummary,
  type StoryGraphNodeSummary,
} from "../api/client";
import Modal, { Field, fieldClass } from "./Modal";
import StoryGraphDedupPanel from "./StoryGraphDedupPanel";
import ToolTip from "./ToolTip";
import { useToast } from "./Toaster";
import {
  EDGE_KINDS,
  NODE_KINDS,
  NODE_STATUSES,
  kindLabel,
  nodeById,
} from "../lib/storyGraph";

const GraphWorkbench = lazy(() => import("./GraphWorkbench"));

type NodeForm = {
  title: string;
  kind: string;
  description: string;
  status: string;
  priority: number;
  linked_character_ids: string[];
};

const EMPTY_NODE: NodeForm = {
  title: "",
  kind: "beat",
  description: "",
  status: "active",
  priority: 1,
  linked_character_ids: [],
};

export default function StoryGraphPanel({
  projectId,
  characters,
  chapters,
  onGoToPlotThreads,
}: {
  projectId: string;
  characters: CharacterSummary[];
  chapters?: ChapterSummary[];
  onGoToPlotThreads?: () => void;
}) {
  const toast = useToast();
  const [nodes, setNodes] = useState<StoryGraphNodeSummary[]>([]);
  const [edges, setEdges] = useState<StoryGraphEdgeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [linkMode, setLinkMode] = useState(false);
  const [linkSource, setLinkSource] = useState<string | null>(null);
  const [nodeModal, setNodeModal] = useState<"new" | StoryGraphNodeSummary | null>(null);
  const [edgeModal, setEdgeModal] = useState<{
    source_id: string;
    target_id: string;
  } | null>(null);
  const [migrating, setMigrating] = useState(false);
  const [dedupOpen, setDedupOpen] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      api.storyGraphNodes(projectId),
      api.storyGraphEdges(projectId),
    ])
      .then(([n, e]) => {
        setNodes(n);
        setEdges(e);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const nodesMap = useMemo(() => nodeById(nodes), [nodes]);

  function handleNodeClick(id: string) {
    if (linkMode) {
      if (!linkSource) {
        setLinkSource(id);
        return;
      }
      if (linkSource === id) {
        setLinkSource(null);
        return;
      }
      setEdgeModal({ source_id: linkSource, target_id: id });
      setLinkMode(false);
      setLinkSource(null);
      return;
    }
    setSelectedId(id);
  }

  async function handleMigrate() {
    setMigrating(true);
    try {
      const result = await api.migrateStoryGraph(projectId);
      if (result.skipped) {
        toast("Graph already has nodes — migration skipped (plot threads unchanged)", "info");
      } else {
        toast(
          `Added ${result.nodes_created} node(s) and ${result.edges_created} edge(s) from plot threads`,
          "success",
        );
      }
      load();
    } catch (e) {
      toast(String(e), "error");
    } finally {
      setMigrating(false);
    }
  }

  async function deleteNode(id: string) {
    try {
      await api.deleteStoryGraphNode(projectId, id);
      if (selectedId === id) setSelectedId(null);
      toast("Node deleted", "success");
      load();
    } catch (e) {
      toast(String(e), "error");
    }
  }

  async function deleteEdge(edgeId: string) {
    try {
      await api.deleteStoryGraphEdge(projectId, edgeId);
      toast("Edge deleted", "success");
      load();
    } catch (e) {
      toast(String(e), "error");
    }
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-paper-line bg-paper-card px-8 py-10 text-center text-[13.5px] text-ink-muted">
        Loading story graph…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-[14px] text-red-700">
        Failed to load story graph: {error}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-2xl">
          <p className="text-[13px] leading-relaxed text-ink-muted">
            Primary planning surface for plots, subplots, and beats. Chapter briefs and outline
            generation read active nodes from here. Legacy plot threads remain available as a fallback.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ToolTip id="graph.addNode">
            <button
              type="button"
              onClick={() => setNodeModal("new")}
              className="rounded-lg border border-paper-line px-3.5 py-1.5 text-[12.5px] font-semibold text-ink-text hover:bg-ink/5"
            >
              + Add node
            </button>
          </ToolTip>
          <ToolTip id="graph.linkNodes">
            <button
              type="button"
              onClick={() => {
                setLinkMode((m) => !m);
                setLinkSource(null);
              }}
              className={`rounded-lg border px-3.5 py-1.5 text-[12.5px] font-semibold transition-colors ${
                linkMode
                  ? "border-amber-deep bg-amber/10 text-amber-deep"
                  : "border-paper-line text-ink-text hover:bg-ink/5"
              }`}
            >
              {linkMode ? (linkSource ? "Pick target…" : "Pick source…") : "Link nodes"}
            </button>
          </ToolTip>
          <ToolTip id="graph.findDuplicates">
            <button
              type="button"
              data-testid="find-graph-duplicates"
              onClick={() => setDedupOpen(true)}
              className="rounded-lg border border-paper-line px-3.5 py-1.5 text-[12.5px] font-semibold text-ink-text hover:bg-ink/5"
            >
              Find duplicates
            </button>
          </ToolTip>
          <ToolTip id="graph.migrateFromPlots">
            <button
              type="button"
              data-testid="migrate-story-graph"
              onClick={handleMigrate}
              disabled={migrating}
              className="rounded-lg border border-amber/40 bg-amber/5 px-3.5 py-1.5 text-[12.5px] font-semibold text-ink-text hover:bg-amber/10 disabled:opacity-40"
            >
              {migrating ? "Building…" : "Build graph from plots"}
            </button>
          </ToolTip>
          {onGoToPlotThreads && (
            <ToolTip id="graph.legacyPlotThreads">
              <button
                type="button"
                onClick={onGoToPlotThreads}
                className="rounded-lg border border-paper-line px-3.5 py-1.5 text-[12.5px] font-medium text-ink-muted hover:bg-ink/5"
              >
                Legacy plot threads
              </button>
            </ToolTip>
          )}
        </div>
      </div>

      <p className="rounded-lg border border-amber/25 bg-amber/5 px-4 py-2.5 text-[12.5px] leading-relaxed text-ink-muted">
        <strong className="font-semibold text-ink-text">Build graph from plots</strong> is
        non-destructive: it copies existing plot threads and subplots into graph nodes and leaves
        the original plot-thread list unchanged. Skipped automatically if the graph already has nodes.
      </p>

      {nodes.length === 0 ? (
        <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-12 text-center">
          <p className="font-display text-[18px] text-ink-text">No story graph yet</p>
          <p className="mt-2 text-[13px] text-ink-muted">
            Add nodes manually or build from your existing plot threads.
          </p>
        </div>
      ) : (
        <Suspense
          fallback={
            <div className="rounded-xl border border-paper-line bg-paper-card px-8 py-10 text-center text-[13.5px] text-ink-muted">
              Loading graph workbench…
            </div>
          }
        >
          <GraphWorkbench
            projectId={projectId}
            nodes={nodes}
            edges={edges}
            characters={characters}
            chapters={chapters}
            selectedId={selectedId}
            linkSourceId={linkSource}
            onSelectNode={setSelectedId}
            onNodeClick={handleNodeClick}
            onEditNode={(node) => setNodeModal(node)}
            onDeleteNode={(id) => void deleteNode(id)}
            onDeleteEdge={(eid) => void deleteEdge(eid)}
            onNodesChange={setNodes}
          />
        </Suspense>
      )}

      <StoryGraphNodeModal
        projectId={projectId}
        characters={characters}
        node={nodeModal === "new" ? null : nodeModal}
        open={nodeModal != null}
        onClose={() => setNodeModal(null)}
        onSaved={() => {
          setNodeModal(null);
          load();
        }}
      />

      <StoryGraphEdgeModal
        projectId={projectId}
        draft={edgeModal}
        open={edgeModal != null}
        onClose={() => setEdgeModal(null)}
        onSaved={() => {
          setEdgeModal(null);
          load();
        }}
        nodesMap={nodesMap}
      />

      <StoryGraphDedupPanel
        projectId={projectId}
        open={dedupOpen}
        onClose={() => setDedupOpen(false)}
        onDone={() => load()}
      />
    </div>
  );
}

function StoryGraphNodeModal({
  projectId,
  characters,
  node,
  open,
  onClose,
  onSaved,
}: {
  projectId: string;
  characters: CharacterSummary[];
  node: StoryGraphNodeSummary | null;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const isEdit = node != null;
  const [form, setForm] = useState<NodeForm>(EMPTY_NODE);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (node) {
      setForm({
        title: node.title,
        kind: node.kind,
        description: node.description,
        status: node.status,
        priority: node.priority,
        linked_character_ids: [...node.linked_character_ids],
      });
    } else {
      setForm(EMPTY_NODE);
    }
  }, [open, node]);

  function toggleChar(charId: string) {
    setForm((f) => ({
      ...f,
      linked_character_ids: f.linked_character_ids.includes(charId)
        ? f.linked_character_ids.filter((id) => id !== charId)
        : [...f.linked_character_ids, charId],
    }));
  }

  async function save() {
    if (!form.title.trim()) {
      toast("Title is required", "error");
      return;
    }
    setBusy(true);
    try {
      const body = {
        title: form.title.trim(),
        kind: form.kind,
        description: form.description,
        status: form.status,
        priority: form.priority,
        linked_character_ids: form.linked_character_ids,
      };
      if (isEdit && node) {
        await api.updateStoryGraphNode(projectId, node.id, body);
        toast("Node updated", "success");
      } else {
        await api.createStoryGraphNode(projectId, body);
        toast("Node created", "success");
      }
      onSaved();
    } catch (e) {
      toast(String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? "Edit graph node" : "New graph node"} size="wide">
      <div className="space-y-4">
        <Field label="Title">
          <input
            className={fieldClass}
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
          />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Kind">
            <select
              className={fieldClass}
              value={form.kind}
              onChange={(e) => setForm((f) => ({ ...f, kind: e.target.value }))}
            >
              {NODE_KINDS.map((k) => (
                <option key={k} value={k}>{kindLabel(k)}</option>
              ))}
            </select>
          </Field>
          <Field label="Status">
            <select
              className={fieldClass}
              value={form.status}
              onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
            >
              {NODE_STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </Field>
        </div>
        <Field label="Priority (higher = more important)">
          <input
            type="number"
            min={1}
            max={10}
            className={fieldClass}
            value={form.priority}
            onChange={(e) => setForm((f) => ({ ...f, priority: Number(e.target.value) || 1 }))}
          />
        </Field>
        <Field label="Description">
          <textarea
            className={fieldClass}
            rows={3}
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
          />
        </Field>
        {characters.length > 0 && (
          <Field label="Linked characters">
            <div className="flex flex-wrap gap-2">
              {characters.map((c) => (
                <label
                  key={c.id}
                  className={`cursor-pointer rounded-lg border px-2.5 py-1 text-[12px] ${
                    form.linked_character_ids.includes(c.id)
                      ? "border-amber-deep bg-amber/10 text-ink-text"
                      : "border-paper-line text-ink-muted"
                  }`}
                >
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={form.linked_character_ids.includes(c.id)}
                    onChange={() => toggleChar(c.id)}
                  />
                  {c.full_name}
                </label>
              ))}
            </div>
          </Field>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <ToolTip id="modal.cancel">
            <button type="button" onClick={onClose} className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5">
              Cancel
            </button>
          </ToolTip>
          <ToolTip id="graph.editNode">
            <button type="button" onClick={() => void save()} disabled={busy}
                    className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
              {busy ? "Saving…" : isEdit ? "Save" : "Create"}
            </button>
          </ToolTip>
        </div>
      </div>
    </Modal>
  );
}

function StoryGraphEdgeModal({
  projectId,
  draft,
  open,
  onClose,
  onSaved,
  nodesMap,
}: {
  projectId: string;
  draft: { source_id: string; target_id: string } | null;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  nodesMap: Map<string, StoryGraphNodeSummary>;
}) {
  const toast = useToast();
  const [kind, setKind] = useState("relates");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setKind("relates");
      setLabel("");
    }
  }, [open, draft?.source_id, draft?.target_id]);

  async function save() {
    if (!draft) return;
    setBusy(true);
    try {
      await api.createStoryGraphEdge(projectId, {
        source_id: draft.source_id,
        target_id: draft.target_id,
        kind,
        label: label.trim(),
      });
      toast("Edge created", "success");
      onSaved();
    } catch (e) {
      toast(String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  if (!draft) return null;
  const src = nodesMap.get(draft.source_id)?.title ?? draft.source_id;
  const tgt = nodesMap.get(draft.target_id)?.title ?? draft.target_id;

  return (
    <Modal open={open} onClose={onClose} title="Link nodes">
      <p className="mb-4 text-[13px] text-ink-muted">
        {src} → {tgt}
      </p>
      <div className="space-y-4">
        <Field label="Edge kind">
          <select className={fieldClass} value={kind} onChange={(e) => setKind(e.target.value)}>
            {EDGE_KINDS.map((k) => (
              <option key={k} value={k}>{kindLabel(k)}</option>
            ))}
          </select>
        </Field>
        <Field label="Label (optional)">
          <input className={fieldClass} value={label} onChange={(e) => setLabel(e.target.value)} />
        </Field>
        <div className="flex justify-end gap-2">
          <ToolTip id="modal.cancel">
            <button type="button" onClick={onClose} className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5">
              Cancel
            </button>
          </ToolTip>
          <ToolTip id="graph.linkNodes">
            <button type="button" onClick={() => void save()} disabled={busy}
                    className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
              {busy ? "Saving…" : "Create link"}
            </button>
          </ToolTip>
        </div>
      </div>
    </Modal>
  );
}
