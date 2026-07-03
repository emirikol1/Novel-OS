import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { kindLabel } from "../../lib/storyGraph";
import type { StoryGraphFlowNodeData } from "../../lib/storyGraphFlow";

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

function StoryGraphNodeCard({ data }: NodeProps) {
  const {
    node,
    charNames,
    selected,
    linkHighlight,
    searchMatch,
    activeSearchMatch,
  } = data as StoryGraphFlowNodeData;

  const borderClass = activeSearchMatch || linkHighlight || selected
    ? "border-amber-deep ring-2 ring-amber-deep/30"
    : searchMatch
      ? "border-amber"
      : "border-paper-line";

  const bgClass = searchMatch
    ? "bg-[color-mix(in_srgb,var(--color-amber)_16%,var(--color-paper-card))]"
    : "bg-paper-card";

  const charLine = node.linked_character_ids
    .map((id) => charNames.get(id) ?? id)
    .join(", ");

  return (
    <div
      className={`min-w-[148px] max-w-[168px] rounded-lg border px-3 py-2 shadow-[var(--shadow-paper)] ${bgClass} ${borderClass}`}
    >
      <Handle type="target" position={Position.Top} className="!h-1.5 !w-1.5 !border-paper-line !bg-paper-muted" />
      <div className="flex items-start justify-between gap-1">
        <p className="truncate text-[12px] font-semibold leading-tight text-ink-text" title={node.title}>
          {node.title}
        </p>
        <span className={`shrink-0 rounded px-1 py-0.5 text-[8px] font-semibold uppercase ${badgeClass(node.kind)}`}>
          {kindLabel(node.kind).split(" ")[0]}
        </span>
      </div>
      <p className="mt-0.5 text-[10px] text-ink-muted">
        {kindLabel(node.kind)} · P{node.priority}
      </p>
      {charLine && (
        <p className="mt-0.5 truncate text-[9px] text-ink-muted" title={charLine}>
          {charLine}
        </p>
      )}
      <Handle type="source" position={Position.Bottom} className="!h-1.5 !w-1.5 !border-paper-line !bg-paper-muted" />
    </div>
  );
}

export default memo(StoryGraphNodeCard);
