import type { ReactNode } from "react";
import type { GraphViewMode } from "../../lib/storyGraphFlow";
import type { ToolTipId } from "../../lib/toolRegistry";
import ToolTip from "../ToolTip";

const VIEW_TIP_IDS: Record<GraphViewMode, ToolTipId> = {
  radial: "graph.viewRadial",
  acts: "graph.viewActs",
  timeline: "graph.viewTimeline",
};

export type { GraphViewMode };

export default function GraphViewToolbar({
  viewMode,
  onViewModeChange,
  onFitView,
  searchQuery,
  onSearchQueryChange,
  matchCount,
  matchIndex,
  onPrevMatch,
  onNextMatch,
  timelineBreadcrumb,
}: {
  viewMode: GraphViewMode;
  onViewModeChange: (mode: GraphViewMode) => void;
  onFitView: () => void;
  searchQuery: string;
  onSearchQueryChange: (query: string) => void;
  matchCount: number;
  matchIndex: number;
  onPrevMatch: () => void;
  onNextMatch: () => void;
  timelineBreadcrumb?: ReactNode;
}) {
  const modes: { id: GraphViewMode; label: string }[] = [
    { id: "radial", label: "Radial" },
    { id: "acts", label: "Acts" },
    { id: "timeline", label: "Timeline" },
  ];

  return (
    <div className="border-b border-paper-line bg-paper-card/80">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2">
        <div className="flex items-center gap-1 rounded-lg border border-paper-line p-0.5">
          {modes.map((mode) => (
            <ToolTip key={mode.id} id={VIEW_TIP_IDS[mode.id]}>
              <button
                type="button"
                onClick={() => onViewModeChange(mode.id)}
                className={`rounded-md px-2.5 py-1 text-[11.5px] font-semibold transition-colors ${
                  viewMode === mode.id
                    ? "bg-ink text-on-ink"
                    : "text-ink-muted hover:bg-ink/5 hover:text-ink-text"
                }`}
              >
                {mode.label}
              </button>
            </ToolTip>
          ))}
        </div>

        <div className="flex min-w-[180px] flex-1 items-center gap-1">
          <ToolTip id="graph.searchNodes" className="min-w-0 flex-1">
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => onSearchQueryChange(e.target.value)}
              placeholder="Search nodes…"
              className="w-full max-w-xs rounded-lg border border-paper-line bg-paper px-2.5 py-1 text-[12px] text-ink-text placeholder:text-ink-muted"
              aria-label="Search graph nodes"
            />
          </ToolTip>
          {matchCount > 0 && (
            <div className="flex items-center gap-0.5 text-[11px] text-ink-muted">
              <ToolTip id="graph.searchPrevNext">
                <button type="button" onClick={onPrevMatch} className="rounded px-1 hover:bg-ink/5" aria-label="Previous match">
                  ‹
                </button>
              </ToolTip>
              <span>{matchIndex + 1}/{matchCount}</span>
              <ToolTip id="graph.searchPrevNext">
                <button type="button" onClick={onNextMatch} className="rounded px-1 hover:bg-ink/5" aria-label="Next match">
                  ›
                </button>
              </ToolTip>
            </div>
          )}
        </div>

        <ToolTip id="graph.fitView">
          <button
            type="button"
            onClick={onFitView}
            className="rounded-lg border border-paper-line px-2.5 py-1 text-[11.5px] font-semibold text-ink-text hover:bg-ink/5"
          >
            Fit view
          </button>
        </ToolTip>
      </div>
      {timelineBreadcrumb}
    </div>
  );
}
