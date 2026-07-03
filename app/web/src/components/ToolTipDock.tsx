import { useEffect, useState } from "react";
import { useToolTipContext } from "../context/ToolTipContext";
import { getToolTip } from "../lib/toolRegistry";

export const TOOLTIP_DOCK_ID = "novel-os-tooltip-dock";

export default function ToolTipDock() {
  const { activeId, holdActive, scheduleDismissActive } = useToolTipContext();
  const [detailOpen, setDetailOpen] = useState(false);

  useEffect(() => {
    setDetailOpen(false);
  }, [activeId]);

  if (!activeId) return null;

  const entry = getToolTip(activeId);

  return (
    <div
      id={TOOLTIP_DOCK_ID}
      role="tooltip"
      onMouseEnter={holdActive}
      onMouseLeave={scheduleDismissActive}
      className="pointer-events-auto fixed bottom-4 left-4 z-[9999] max-w-[320px] rounded-lg border border-paper-line bg-paper-card px-3 py-2.5 text-[12px] leading-relaxed shadow-[var(--shadow-lift)]"
    >
      <p className="mb-1.5 font-semibold text-ink-text">{entry.label}</p>
      <dl className="space-y-1 text-ink-muted">
        <div>
          <dt className="font-medium text-ink-text">Function</dt>
          <dd>{entry.function}</dd>
        </div>
        <div>
          <dt className="font-medium text-ink-text">Works on</dt>
          <dd>{entry.worksOn}</dd>
        </div>
        <div>
          <dt className="font-medium text-ink-text">Modifies</dt>
          <dd>{entry.modifies}</dd>
        </div>
        <div>
          <dt className="font-medium text-ink-text">Workflow</dt>
          <dd>{entry.workflow}</dd>
        </div>
      </dl>
      {entry.detail && (
        <div className="mt-2 border-t border-paper-line pt-2">
          <button
            type="button"
            className="text-[11px] font-semibold text-amber-deep hover:underline"
            aria-expanded={detailOpen}
            onClick={() => setDetailOpen((v) => !v)}
          >
            {detailOpen ? "Less detail" : "More details"}
          </button>
          {detailOpen && (
            <p className="mt-1.5 text-ink-text">{entry.detail}</p>
          )}
        </div>
      )}
    </div>
  );
}
