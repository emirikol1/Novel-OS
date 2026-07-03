import type { KeyboardEvent, ReactNode } from "react";
import { Link } from "react-router-dom";
import { STUDIO_BANNER_TEXT_CLASS } from "../lib/studioBanner";

const crumbText = `${STUDIO_BANNER_TEXT_CLASS} text-ink-muted`;

export default function Breadcrumbs({
  items,
  className,
  titleEdit,
}: {
  items: { label: string; to?: string }[];
  className?: string;
  /** Inline editable chapter title as the final breadcrumb segment. */
  titleEdit?: {
    value: string;
    onChange: (value: string) => void;
    onFocus?: () => void;
    onBlur?: () => void;
    onKeyDown?: (e: KeyboardEvent<HTMLInputElement>) => void;
    disabled?: boolean;
    placeholder?: string;
    trailing?: ReactNode;
  };
}) {
  return (
    <nav
      aria-label="Breadcrumb"
      className={`flex h-7 min-w-0 items-center gap-1.5 ${STUDIO_BANNER_TEXT_CLASS} ${className ?? ""}`}
    >
      {items.map((it, i) => (
        <span key={i} className="flex shrink-0 items-center gap-1.5">
          {it.to ? (
            <Link to={it.to} className={`${crumbText} transition-colors hover:text-amber-deep`}>
              {it.label}
            </Link>
          ) : (
            <span className={crumbText}>{it.label}</span>
          )}
          {(i < items.length - 1 || titleEdit) && (
            <span className="text-paper-muted">/</span>
          )}
        </span>
      ))}
      {titleEdit && (
        <span className="inline-flex min-w-0 items-center gap-1.5">
          <input
            type="text"
            value={titleEdit.value}
            onChange={(e) => titleEdit.onChange(e.target.value)}
            onFocus={titleEdit.onFocus}
            onBlur={titleEdit.onBlur}
            onKeyDown={titleEdit.onKeyDown}
            placeholder={titleEdit.placeholder}
            disabled={titleEdit.disabled}
            aria-label="Chapter title"
            className={`h-7 min-w-[6rem] max-w-[min(18rem,40vw)] border-0 bg-transparent p-0 ${STUDIO_BANNER_TEXT_CLASS} text-ink-text outline-none transition-colors placeholder:font-normal placeholder:text-ink-muted/70 hover:text-amber-deep focus:text-amber-deep disabled:opacity-60`}
          />
          {titleEdit.trailing}
        </span>
      )}
    </nav>
  );
}
