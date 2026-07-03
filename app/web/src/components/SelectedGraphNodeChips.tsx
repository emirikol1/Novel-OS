import { useMemo } from "react";
import type { StoryGraphNodeSummary } from "../api/client";
import { kindLabel, NODE_KIND_COLOR } from "../lib/storyGraph";
import ToolTip from "./ToolTip";

type SelectedGraphNodeChipsProps = {
  nodes: StoryGraphNodeSummary[];
  selectedIds: string[];
  onRemove: (id: string) => void;
  readonly?: boolean;
};

export default function SelectedGraphNodeChips({
  nodes,
  selectedIds,
  onRemove,
  readonly = false,
}: SelectedGraphNodeChipsProps) {
  const nodesById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  const selectedNodes = useMemo(
    () =>
      selectedIds
        .map((id) => nodesById.get(id))
        .filter((node): node is StoryGraphNodeSummary => Boolean(node))
        .sort((a, b) => a.title.localeCompare(b.title)),
    [nodesById, selectedIds],
  );

  if (selectedNodes.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {selectedNodes.map((node) => (
        <span
          key={node.id}
          className="inline-flex max-w-full items-center gap-1 rounded-md border border-amber/25 bg-amber/5 px-2 py-0.5 text-[11px] font-medium text-ink-text"
          title={`${kindLabel(node.kind)} — linked to chapter`}
        >
          <span
            className="h-1.5 w-1.5 shrink-0 rounded-full"
            style={{ backgroundColor: NODE_KIND_COLOR[node.kind] ?? "var(--color-ink-muted)" }}
            aria-hidden
          />
          <span className="truncate">{node.title}</span>
          {!readonly && (
            <ToolTip id="chapter.graphRemoveNode">
              <button
                type="button"
                onClick={() => onRemove(node.id)}
                className="ml-0.5 shrink-0 rounded p-0.5 text-ink-muted hover:bg-ink/10 hover:text-ink-text"
                aria-label={`Remove ${node.title} from chapter`}
              >
                ×
              </button>
            </ToolTip>
          )}
        </span>
      ))}
    </div>
  );
}
