import { ViewportPortal } from "@xyflow/react";
import type {
  TimelineActColumn,
  TimelineChapterColumn,
} from "../../lib/storyGraphFlow";

export function TimelineActColumns({ columns }: { columns: TimelineActColumn[] }) {
  return (
    <ViewportPortal>
      {columns.map((column) => (
        <div
          key={column.act}
          aria-hidden
          className="pointer-events-none rounded-lg border border-dashed border-paper-line/80 bg-paper-card/30"
          style={{
            position: "absolute",
            left: column.x,
            top: 32,
            width: column.width,
            height: 480,
            zIndex: -1,
          }}
        >
          <span className="block px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            {column.label}
          </span>
        </div>
      ))}
    </ViewportPortal>
  );
}

export function TimelineChapterColumns({ columns }: { columns: TimelineChapterColumn[] }) {
  return (
    <ViewportPortal>
      {columns.map((column) => (
        <div
          key={column.chapterNumber}
          aria-hidden
          className={`pointer-events-none rounded-lg border border-dashed ${
            column.pool
              ? "border-ink/15 bg-ink/5"
              : "border-paper-line/80 bg-paper-card/30"
          }`}
          style={{
            position: "absolute",
            left: column.x,
            top: 32,
            width: column.width,
            height: 480,
            zIndex: -1,
          }}
        >
          <span className="block px-2 py-2 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
            {column.label}
          </span>
        </div>
      ))}
    </ViewportPortal>
  );
}
