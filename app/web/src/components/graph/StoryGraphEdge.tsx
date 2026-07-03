import { memo } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from "@xyflow/react";
import { edgeStroke } from "../../lib/storyGraph";
import type { StoryGraphFlowEdgeData } from "../../lib/storyGraphFlow";

function StoryGraphEdge({
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
  const edgeData = data as StoryGraphFlowEdgeData | undefined;
  const kind = edgeData?.edge.kind ?? "relates";
  const label = edgeData?.label ?? kind;

  const [path, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        style={{
          stroke: edgeStroke(kind, selected),
          strokeWidth: selected ? 2.5 : 1.5,
        }}
        markerEnd="url(#sg-flow-arrow)"
      />
      {(label || selected) && (
        <EdgeLabelRenderer>
          <div
            className="pointer-events-none rounded bg-paper-card/90 px-1 text-[10px] text-ink-muted"
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
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

export default memo(StoryGraphEdge);
