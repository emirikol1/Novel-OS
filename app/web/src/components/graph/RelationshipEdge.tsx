import { memo } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from "@xyflow/react";
import type { RelationshipFlowEdgeData } from "../../lib/relationshipGraphFlow";
import { LABEL_OFFSET_PX } from "../../lib/relationshipGraphFlow";

function relationshipLabelPosition(
  sourceX: number,
  sourceY: number,
  targetX: number,
  targetY: number,
  pathLabelX: number,
  pathLabelY: number,
  labelPosition: number,
  labelSide: number,
): { x: number; y: number } {
  const t = Math.min(0.82, Math.max(0.18, labelPosition));
  const alongX = sourceX + (targetX - sourceX) * t;
  const alongY = sourceY + (targetY - sourceY) * t;
  const blend = labelSide === 0 ? 0 : 0.35;
  let x = pathLabelX * (1 - blend) + alongX * blend;
  let y = pathLabelY * (1 - blend) + alongY * blend;

  if (labelSide !== 0) {
    const dx = targetX - sourceX;
    const dy = targetY - sourceY;
    const len = Math.hypot(dx, dy) || 1;
    const pad = LABEL_OFFSET_PX * labelSide;
    x += (-dy / len) * pad;
    y += (dx / len) * pad;
  }
  return { x, y };
}

function RelationshipEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  selected,
  data,
}: EdgeProps) {
  const edgeData = data as RelationshipFlowEdgeData | undefined;
  const label = edgeData?.label ?? "";
  const curvature = edgeData?.curvature ?? 0.25;
  const labelSide = edgeData?.labelSide ?? 0;
  const labelPosition = edgeData?.labelPosition ?? 0.5;

  const [path, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    curvature,
  });

  const { x: lx, y: ly } = relationshipLabelPosition(
    sourceX,
    sourceY,
    targetX,
    targetY,
    labelX,
    labelY,
    labelPosition,
    labelSide,
  );

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        style={{
          stroke: selected ? "var(--color-amber-deep)" : "var(--color-paper-line)",
          strokeWidth: selected ? 2.5 : 1.5,
        }}
        markerEnd="url(#rel-flow-arrow)"
      />
      {label && (
        <EdgeLabelRenderer>
          <div
            className="pointer-events-none z-[1001] whitespace-nowrap rounded border border-paper-line/80 bg-paper-card px-1.5 py-0.5 text-[10px] text-ink-muted shadow-sm"
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${lx}px, ${ly}px)`,
              fontWeight: selected ? 600 : 400,
            }}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

export default memo(RelationshipEdge);
