import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { RelationshipFlowNodeData } from "../../lib/relationshipGraphFlow";

const ROLE_COLOR: Record<string, string> = {
  protagonist: "bg-st-approved/15 text-st-approved",
  antagonist: "bg-st-planned/15 text-st-planned",
  supporting: "bg-st-drafted/15 text-st-drafted",
  minor: "bg-ink/10 text-ink-muted",
};

function RelationshipNodeCard({ data }: NodeProps) {
  const {
    name,
    role,
    selected,
    linkHighlight,
    searchMatch,
    activeSearchMatch,
  } = data as RelationshipFlowNodeData;

  const borderClass = activeSearchMatch || linkHighlight || selected
    ? "border-amber-deep ring-2 ring-amber-deep/30"
    : searchMatch
      ? "border-amber"
      : "border-paper-line";

  const bgClass = searchMatch
    ? "bg-[color-mix(in_srgb,var(--color-amber)_16%,var(--color-paper-card))]"
    : "bg-paper-card";

  return (
    <div
      className={`min-w-[148px] max-w-[168px] rounded-lg border px-3 py-2 shadow-[var(--shadow-paper)] ${bgClass} ${borderClass}`}
    >
      <Handle
        id="target-top"
        type="target"
        position={Position.Top}
        className="!h-1.5 !w-1.5 !border-paper-line !bg-paper-muted"
      />
      <Handle
        id="target-left"
        type="target"
        position={Position.Left}
        className="!h-1.5 !w-1.5 !border-paper-line !bg-paper-muted"
      />
      <div className="flex items-start justify-between gap-1">
        <p className="truncate text-[12px] font-semibold leading-tight text-ink-text" title={name}>
          {name}
        </p>
        <span
          className={`shrink-0 rounded px-1 py-0.5 text-[8px] font-semibold capitalize ${
            ROLE_COLOR[role] ?? ROLE_COLOR.minor
          }`}
        >
          {role}
        </span>
      </div>
      <Handle
        id="source-bottom"
        type="source"
        position={Position.Bottom}
        className="!h-1.5 !w-1.5 !border-paper-line !bg-paper-muted"
      />
      <Handle
        id="source-right"
        type="source"
        position={Position.Right}
        className="!h-1.5 !w-1.5 !border-paper-line !bg-paper-muted"
      />
    </div>
  );
}

export default memo(RelationshipNodeCard);
