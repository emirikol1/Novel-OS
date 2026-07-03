import MentionMarkdown from "./MentionMarkdown";
import type { MentionTarget } from "../lib/mentions";

/** Preview-only bionic reading render — source markdown is unchanged. */
export default function BionicMarkdown({
  source,
  className = "prose-manuscript",
  style,
  mentionTargets,
  projectId,
}: {
  source: string;
  className?: string;
  style?: React.CSSProperties;
  mentionTargets?: MentionTarget[];
  projectId?: string;
}) {
  return (
    <MentionMarkdown
      source={source}
      className={className}
      style={style}
      bionic
      mentionTargets={mentionTargets}
      projectId={projectId}
    />
  );
}
