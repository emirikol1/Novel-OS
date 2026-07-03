import type { ChapterStages } from "../api/client";
import PendingAiStar from "./PendingAiStar";
import ToolTip from "./ToolTip";
import type { ToolTipId } from "../lib/toolRegistry";

export type StageKey = "outline" | "draft" | "revised" | "final";

const STAGES: { key: StageKey; label: string; agent: string; step: number }[] = [
  { key: "outline", label: "Outline", agent: "Architect", step: 1 },
  { key: "draft", label: "Draft", agent: "Scribe", step: 2 },
  { key: "revised", label: "Revised", agent: "Editor", step: 3 },
  { key: "final", label: "Final", agent: "You", step: 4 },
];

const STAGE_TIP_IDS: Record<StageKey, ToolTipId> = {
  outline: "chapter.stageOutline",
  draft: "chapter.stageDraft",
  revised: "chapter.stageRevised",
  final: "chapter.stageFinal",
};

export default function PipelineFlow({
  stages,
  selected,
  onSelect,
  pendingStages = [],
}: {
  stages: ChapterStages;
  selected: StageKey;
  onSelect: (s: StageKey) => void;
  pendingStages?: StageKey[];
}) {
  return (
    <div className="flex items-stretch gap-0.5">
      {STAGES.map((s, i) => {
        const present = stages[s.key] != null;
        const isSel = selected === s.key;
        const isFinal = s.key === "final";
        return (
          <div key={s.key} className="flex min-w-0 flex-1 items-center">
            <ToolTip id={STAGE_TIP_IDS[s.key]} className="flex min-w-0 flex-1">
              <button
                type="button"
                onClick={() => onSelect(s.key)}
                aria-label={`Step ${s.step}, ${s.label} stage${present ? "" : ", not run"}`}
                aria-current={isSel ? "step" : undefined}
                className={`group flex w-full min-w-0 flex-col items-start rounded-md border px-2 py-1.5 text-left transition-all ${
                  isSel
                    ? isFinal
                      ? "border-amber bg-amber/15 shadow-[var(--shadow-paper)]"
                      : "border-ink/25 bg-ink/[0.04] shadow-[var(--shadow-paper)]"
                    : "border-paper-line bg-paper-card/50 hover:border-ink/20 hover:bg-paper-card"
                }`}
              >
                <span className="flex w-full min-w-0 items-center gap-1">
                  <span
                    className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                      present
                        ? isFinal
                          ? "bg-amber-deep"
                          : "bg-st-approved"
                        : "bg-paper-muted/50"
                    }`}
                  />
                  <span
                    className={`shrink-0 text-[10px] font-bold tabular-nums leading-none ${
                      isSel ? "text-amber-deep" : "text-paper-muted"
                    }`}
                  >
                    {s.step}
                  </span>
                  <span
                    className={`inline-flex min-w-0 items-center gap-1 truncate font-display text-[13px] font-semibold leading-tight tracking-tight ${
                      isSel ? "text-ink-text" : "text-ink-muted"
                    }`}
                  >
                    {s.label}
                    {pendingStages.includes(s.key) && (
                      <PendingAiStar title="AI preview ready to review on this stage" />
                    )}
                  </span>
                </span>
                <span className="mt-0.5 truncate pl-[1.125rem] text-[9.5px] uppercase tracking-[0.08em] text-paper-muted">
                  {present ? s.agent : "not run"}
                </span>
              </button>
            </ToolTip>
            {i < STAGES.length - 1 && (
              <svg width="14" height="10" viewBox="0 0 20 12" className="mx-0.5 shrink-0" aria-hidden>
                <path
                  d="M1 6h15m0 0l-4-4m4 4l-4 4"
                  fill="none"
                  stroke={stages[STAGES[i + 1].key] != null ? "#c98a16" : "#cbc3ad"}
                  strokeWidth="1.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </div>
        );
      })}
    </div>
  );
}
