import { Fragment, cloneElement, isValidElement, type ReactElement, type ReactNode } from "react";
import { Link } from "react-router-dom";
import ReactMarkdown, { type Components } from "react-markdown";
import {
  type MentionTarget,
  parseMentionHref,
  preprocessMentionsForMarkdown,
  resolveMention,
} from "../lib/mentions";
import ToolTip from "./ToolTip";

function bionicizeText(text: string): ReactNode {
  return text.split(/(\s+)/).map((part, i) => {
    if (/^\s+$/.test(part)) return part;
    if (part.length <= 1) return part;
    const cut = Math.max(1, Math.ceil(part.length * 0.45));
    return (
      <span key={i} className="bionic-word">
        <strong className="font-semibold text-ink-text">{part.slice(0, cut)}</strong>
        <span className="text-ink-muted">{part.slice(cut)}</span>
      </span>
    );
  });
}

function transformNode(node: ReactNode): ReactNode {
  if (typeof node === "string") return bionicizeText(node);
  if (typeof node === "number") return String(node);
  if (Array.isArray(node)) {
    return node.map((child, i) => <Fragment key={i}>{transformNode(child)}</Fragment>);
  }
  if (isValidElement<{ children?: ReactNode }>(node)) {
    const el = node as ReactElement<{ children?: ReactNode }>;
    if (el.props.children == null) return el;
    return cloneElement(el, el.props, transformNode(el.props.children));
  }
  return node;
}

function mentionNavUrl(
  projectId: string,
  parsed: ReturnType<typeof parseMentionHref>,
  resolved: MentionTarget | null,
): string {
  if (!parsed) return `/projects/${projectId}`;
  if (parsed.kind === "char" && resolved?.id) {
    return `/projects/${projectId}?tab=cast&character=${encodeURIComponent(resolved.id)}`;
  }
  if (parsed.kind === "lore") {
    const section = parsed.section ?? resolved?.section;
    if (section) {
      return `/projects/${projectId}?tab=bible&section=${encodeURIComponent(section)}`;
    }
    return `/projects/${projectId}?tab=bible`;
  }
  return `/projects/${projectId}?tab=cast`;
}

function buildComponents(
  projectId: string | undefined,
  targets: MentionTarget[],
  bionic: boolean,
  onCharacterMentionAction?: (parsed: NonNullable<ReturnType<typeof parseMentionHref>>, resolved: MentionTarget) => void,
): Components {
  const bionicWrap = (children: ReactNode) => (bionic ? transformNode(children) : children);

  return {
    p: ({ children }) => <p>{bionicWrap(children)}</p>,
    li: ({ children }) => <li>{bionicWrap(children)}</li>,
    h1: ({ children }) => <h1>{bionicWrap(children)}</h1>,
    h2: ({ children }) => <h2>{bionicWrap(children)}</h2>,
    h3: ({ children }) => <h3>{bionicWrap(children)}</h3>,
    blockquote: ({ children }) => <blockquote>{bionicWrap(children)}</blockquote>,
    strong: ({ children }) => <strong>{bionicWrap(children)}</strong>,
    em: ({ children }) => <em>{bionicWrap(children)}</em>,
    a: ({ href, children }) => {
      const parsed = href ? parseMentionHref(href) : null;
      if (!parsed) {
        return (
          <a href={href} className="text-amber-deep underline-offset-2 hover:underline">
            {children}
          </a>
        );
      }

      const resolved = resolveMention(parsed, targets);
      const broken = !resolved || (parsed.kind === "char" && !resolved.id);
      const kindClass =
        parsed.kind === "char" ? "mention-char" : "mention-lore";
      const className = broken
        ? "mention mention-broken"
        : `mention ${kindClass}`;
      const title = broken
        ? parsed.kind === "char"
          ? `Unresolved character: ${parsed.label}`
          : `Unresolved lore: ${parsed.label}`
        : parsed.kind === "char"
          ? `Character: ${parsed.label}`
          : parsed.section
            ? `Lore (${parsed.section}): ${parsed.label}`
            : `Lore: ${parsed.label}`;

      const label = typeof children === "string" ? children : parsed.label;

      if (!projectId || broken) {
        return (
          <span className={className} title={title}>
            {label}
          </span>
        );
      }

      const inner = (
        <Link to={mentionNavUrl(projectId, parsed, resolved)} className={className} title={title}>
          {label}
        </Link>
      );

      if (parsed.kind === "char" && resolved?.id && onCharacterMentionAction) {
        return (
          <span className="mention-wrap inline-flex items-center gap-0.5">
            {inner}
            <ToolTip id="chapter.reviewMentions">
              <button
                type="button"
                className="mention-action rounded px-1 text-[10px] text-ink-muted hover:bg-ink/10 hover:text-ink-text"
                title="Review memory update for this character"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onCharacterMentionAction(parsed, resolved);
                }}
              >
                ↗
              </button>
            </ToolTip>
          </span>
        );
      }

      return inner;
    },
  };
}

export default function MentionMarkdown({
  source,
  className = "prose-manuscript",
  style,
  bionic = false,
  mentionTargets = [],
  projectId,
  onCharacterMentionAction,
}: {
  source: string;
  className?: string;
  style?: React.CSSProperties;
  bionic?: boolean;
  mentionTargets?: MentionTarget[];
  projectId?: string;
  onCharacterMentionAction?: (parsed: NonNullable<ReturnType<typeof parseMentionHref>>, resolved: MentionTarget) => void;
}) {
  const processed = preprocessMentionsForMarkdown(source || "*Nothing to preview yet.*");
  const components = buildComponents(projectId, mentionTargets, bionic, onCharacterMentionAction);

  return (
    <div className={className} style={style}>
      <ReactMarkdown components={components}>{processed}</ReactMarkdown>
    </div>
  );
}
