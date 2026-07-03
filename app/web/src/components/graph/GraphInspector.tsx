import type { StoryGraphEdgeSummary, StoryGraphNodeSummary } from "../../api/client";
import DeleteButton from "../DeleteButton";
import ToolTip from "../ToolTip";
import { kindLabel } from "../../lib/storyGraph";

const KIND_BADGE: Record<string, string> = {
  main: "bg-st-approved/15 text-st-approved",
  plot_thread: "bg-st-approved/15 text-st-approved",
  subplot: "bg-st-drafted/15 text-st-drafted",
  beat: "bg-amber/15 text-amber-deep",
  character_arc: "bg-st-planned/15 text-st-planned",
  mystery: "bg-ink/10 text-ink-muted",
  theme: "bg-ink/10 text-ink-muted",
  other: "bg-ink/5 text-ink-muted",
};

function badgeClass(kind: string): string {
  return KIND_BADGE[kind] ?? KIND_BADGE.other;
}

export default function GraphInspector({
  node,
  charNames,
  edges,
  nodesMap,
  onEdit,
  onDelete,
  onDeleteEdge,
}: {
  node: StoryGraphNodeSummary | null;
  charNames: Map<string, string>;
  edges: StoryGraphEdgeSummary[];
  nodesMap: Map<string, StoryGraphNodeSummary>;
  onEdit: () => void;
  onDelete: () => void;
  onDeleteEdge: (edgeId: string) => void;
}) {
  if (!node) {
    return (
      <p className="text-[13px] text-ink-muted">
        Select a node to view details, edit fields, or remove connections.
      </p>
    );
  }

  const nodeEdges = edges.filter(
    (e) => e.source_id === node.id || e.target_id === node.id,
  );

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-display text-[16px] font-semibold text-ink-text">{node.title}</h3>
        <span className={`shrink-0 rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${badgeClass(node.kind)}`}>
          {kindLabel(node.kind)}
        </span>
      </div>
      {node.description && (
        <p className="text-[12.5px] leading-relaxed text-ink-muted">{node.description}</p>
      )}
      <dl className="space-y-1 text-[12px]">
        <div className="flex justify-between gap-2">
          <dt className="text-ink-muted">Status</dt>
          <dd className="font-medium text-ink-text">{node.status}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt className="text-ink-muted">Priority</dt>
          <dd className="font-medium text-ink-text">{node.priority}</dd>
        </div>
        {node.start_chapter != null && node.start_chapter > 0 && (
          <div className="flex justify-between gap-2">
            <dt className="text-ink-muted">Lifespan start</dt>
            <dd className="font-medium text-ink-text">Ch. {node.start_chapter}</dd>
          </div>
        )}
        {node.resolution_chapter != null && (
          <div className="flex justify-between gap-2">
            <dt className="text-ink-muted">Resolution</dt>
            <dd className="font-medium text-ink-text">Ch. {node.resolution_chapter}</dd>
          </div>
        )}
        {(node.act ?? 0) > 0 && (
          <div className="flex justify-between gap-2">
            <dt className="text-ink-muted">Act</dt>
            <dd className="font-medium text-ink-text">Act {node.act}</dd>
          </div>
        )}
        {(node.chapter_pins?.length ?? 0) > 0 && (
          <div>
            <dt className="text-ink-muted">Chapter pins</dt>
            <dd className="mt-0.5 font-medium text-ink-text">
              {node.chapter_pins!.map((n) => `Ch. ${n}`).join(", ")}
            </dd>
          </div>
        )}
        {node.linked_character_ids.length > 0 && (
          <div>
            <dt className="text-ink-muted">Characters</dt>
            <dd className="mt-0.5 font-medium text-ink-text">
              {node.linked_character_ids.map((id) => charNames.get(id) ?? id).join(", ")}
            </dd>
          </div>
        )}
        {node.legacy_plot_thread_id && (
          <div className="flex justify-between gap-2">
            <dt className="text-ink-muted">Legacy thread</dt>
            <dd className="truncate font-mono text-[10px] text-ink-muted">{node.legacy_plot_thread_id}</dd>
          </div>
        )}
      </dl>
      {nodeEdges.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Connections</p>
          <ul className="mt-1 space-y-1">
            {nodeEdges.map((e) => {
              const otherId = e.source_id === node.id ? e.target_id : e.source_id;
              const other = nodesMap.get(otherId);
              const dir = e.source_id === node.id ? "→" : "←";
              return (
                <li key={e.id} className="flex items-center justify-between gap-2 text-[12px]">
                  <span className="truncate text-ink-text">
                    {dir} {other?.title ?? otherId}
                    {e.label ? ` (${e.label})` : ` · ${e.kind}`}
                  </span>
                  <ToolTip id="graph.inspectorDeleteEdge">
                    <button
                      type="button"
                      onClick={() => onDeleteEdge(e.id)}
                      className="shrink-0 text-[11px] text-ink-muted hover:text-red-600"
                    >
                      ×
                    </button>
                  </ToolTip>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <div className="flex gap-2 pt-1">
        <ToolTip id="graph.inspectorEdit">
          <button
            type="button"
            onClick={onEdit}
            className="rounded-lg border border-paper-line px-3 py-1.5 text-[12px] font-semibold text-ink-text hover:bg-ink/5"
          >
            Edit
          </button>
        </ToolTip>
        <DeleteButton
          label="Delete node"
          message={`Delete graph node "${node.title}"? Connected edges will also be removed.`}
          onConfirm={onDelete}
          tipId="graph.inspectorDeleteNode"
        />
      </div>
    </div>
  );
}
