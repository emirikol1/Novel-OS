import { useMemo } from "react";
import type { CommentItem } from "../api/client";
import type { AnnotationStage } from "../api/client";
import {
  computeHighlightRanges,
  splitSourceByHighlights,
  commentStage,
} from "../lib/annotations";
import MentionMarkdown from "./MentionMarkdown";
import type { MentionTarget } from "../lib/mentions";

export default function AnnotatedPreview({
  source,
  annotations,
  stage,
  style,
  className = "prose-manuscript",
  bionic = false,
  mentionTargets = [],
  projectId,
  onCharacterMentionAction,
  focusAnnotationId,
}: {
  source: string;
  annotations: CommentItem[];
  stage: AnnotationStage;
  style?: React.CSSProperties;
  className?: string;
  bionic?: boolean;
  mentionTargets?: MentionTarget[];
  projectId?: string;
  onCharacterMentionAction?: (
    parsed: Pick<import("../lib/mentions").ParsedMention, "kind" | "label" | "section">,
    resolved: MentionTarget,
  ) => void;
  focusAnnotationId?: string | null;
}) {
  const stageAnnotations = useMemo(
    () => annotations.filter((a) => !a.resolved && commentStage(a) === stage),
    [annotations, stage],
  );

  const ranges = useMemo(
    () => computeHighlightRanges(source, stageAnnotations, stage),
    [source, stageAnnotations, stage],
  );

  const segments = useMemo(
    () => splitSourceByHighlights(source, ranges),
    [source, ranges],
  );

  if (ranges.length === 0) {
    return (
      <MentionMarkdown
        source={source}
        style={style}
        className={className}
        bionic={bionic}
        mentionTargets={mentionTargets}
        projectId={projectId}
        onCharacterMentionAction={onCharacterMentionAction}
      />
    );
  }

  return (
    <div className={className} style={style}>
      {segments.map((seg, i) => {
        if (seg.highlight) {
          const focused = focusAnnotationId === seg.highlight.id;
          return (
            <mark
              key={`${seg.highlight.id}-${i}`}
              data-annotation-id={seg.highlight.id}
              title={seg.highlight.body}
              className={`rounded-sm px-0.5 decoration-clone ${
                focused
                  ? "bg-amber/35 ring-2 ring-amber-deep"
                  : "bg-amber/18 ring-1 ring-amber/35"
              }`}
            >
              {seg.text}
            </mark>
          );
        }
        if (!seg.text) return null;
        return (
          <MentionMarkdown
            key={`seg-${i}`}
            source={seg.text}
            className="inline"
            bionic={bionic}
            mentionTargets={mentionTargets}
            projectId={projectId}
            onCharacterMentionAction={onCharacterMentionAction}
          />
        );
      })}
    </div>
  );
}
