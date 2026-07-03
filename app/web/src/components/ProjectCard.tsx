import { Link } from "react-router-dom";
import type { ProjectSummary } from "../api/client";
import StatusPill from "./StatusPill";
import DeleteButton from "./DeleteButton";
import StashButton from "./StashButton";
import ToolTip from "./ToolTip";

export default function ProjectCard({
  p,
  onDelete,
  onStash,
}: {
  p: ProjectSummary;
  onDelete?: (p: ProjectSummary) => void;
  onStash?: (p: ProjectSummary) => void;
}) {
  return (
    <div className="group relative">
      {(onStash || onDelete) && (
        <div className="absolute right-3 top-3 z-10 flex items-center gap-0.5 opacity-70 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
          {onStash && (
            <ToolTip id="library.stashManuscript">
              <StashButton
                label={`Stash ${p.title}`}
                message={`Stash "${p.title}"? It will be removed from your library. Restore it later from Stash in the sidebar.`}
                confirmLabel="Stash manuscript"
                onConfirm={() => onStash(p)}
              />
            </ToolTip>
          )}
          {onDelete && (
            <ToolTip id="library.deleteManuscript">
              <DeleteButton
                label={`Delete ${p.title}`}
                message={`Permanently delete "${p.title}" and all chapters, characters, and files? This cannot be undone.`}
                confirmLabel="Delete manuscript"
                onConfirm={() => onDelete(p)}
              />
            </ToolTip>
          )}
        </div>
      )}
      <ToolTip id="library.openProject">
        <Link
          to={`/projects/${p.id}`}
          className="group/card relative flex flex-col overflow-hidden rounded-xl border border-paper-line bg-paper-card shadow-[var(--shadow-paper)] transition-[transform,box-shadow] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] hover:-translate-y-1 hover:shadow-[var(--shadow-lift)]"
        >
        <span className="absolute inset-y-0 left-0 w-1.5 bg-gradient-to-b from-amber to-amber-deep" />
        <div className="flex flex-1 flex-col p-6 pl-7">
          <span className="mb-3 inline-flex w-fit items-center rounded-md bg-ink/5 px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
            {p.genre || "Untitled genre"}
          </span>
          <h3 className="font-display text-[22px] font-semibold leading-snug tracking-tight text-ink-text transition-colors group-hover/card:text-amber-deep">
            {p.title}
          </h3>
          <div className="mt-auto flex items-center justify-between pt-6">
            <ToolTip id="library.chapterCount">
              <span className="nums text-[13px] font-medium text-ink-muted">{p.chapter_count} chapters</span>
            </ToolTip>
            <ToolTip id="library.statusPill">
              <StatusPill status={p.status} />
            </ToolTip>
          </div>
        </div>
        </Link>
      </ToolTip>
    </div>
  );
}
