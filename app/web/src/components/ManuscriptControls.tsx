import type { ReactNode } from "react";
import { useState } from "react";
import { SaveStatus } from "./EditorSaveBar";
import ToolTip from "./ToolTip";
import type { ToolTipId } from "../lib/toolRegistry";

export const SIZES = [0.95, 1.075, 1.2, 1.35] as const;
export const MEASURES = { narrow: "34rem", normal: "42rem", wide: "52rem" } as const;
export type Measure = keyof typeof MEASURES;
export type ManuscriptStage = "draft" | "revised" | "final";
export type EditorMode = "write" | "preview";

function usePersisted<T>(key: string, initial: T): [T, (v: T) => void] {
  const [v, setV] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw != null ? (JSON.parse(raw) as T) : initial;
    } catch {
      return initial;
    }
  });
  return [
    v,
    (nv: T) => {
      setV(nv);
      try {
        localStorage.setItem(key, JSON.stringify(nv));
      } catch {
        /* ignore quota errors */
      }
    },
  ];
}

export function useManuscriptPrefs() {
  const [sizeIdx, setSizeIdx] = usePersisted("novelos-editor-size", 1);
  const [measure, setMeasure] = usePersisted<Measure>("novelos-editor-measure", "normal");
  const [typewriter, setTypewriter] = usePersisted("novelos-editor-typewriter", false);
  const [vanishing, setVanishing] = usePersisted("novelos-editor-vanishing", false);
  const [bionicPreview, setBionicPreview] = usePersisted("novelos-editor-bionic", false);

  const clampedIdx = Math.max(0, Math.min(SIZES.length - 1, sizeIdx));
  const size = SIZES[clampedIdx];

  return {
    sizeIdx: clampedIdx,
    setSizeIdx,
    size,
    measure,
    setMeasure,
    typewriter,
    setTypewriter,
    vanishing,
    setVanishing,
    bionicPreview,
    setBionicPreview,
  };
}

export function ManuscriptFontSizeControls({
  className = "",
  buttonClassName = "",
}: {
  className?: string;
  buttonClassName?: string;
}) {
  const { sizeIdx, setSizeIdx } = useManuscriptPrefs();

  return (
    <div
      className={`flex items-center overflow-hidden rounded-md border border-ink-line ${className}`}
    >
      <ToolTip id="chapter.fontSizeDecrease">
        <button
          type="button"
          onClick={() => setSizeIdx(Math.max(0, sizeIdx - 1))}
          disabled={sizeIdx === 0}
          className={`px-2 py-0.5 text-[11px] transition-colors disabled:opacity-40 ${buttonClassName || "text-[#aab2c4] hover:bg-ink-700"}`}
          aria-label="Smaller text"
        >
          A−
        </button>
      </ToolTip>
      <ToolTip id="chapter.fontSizeIncrease">
        <button
          type="button"
          onClick={() => setSizeIdx(Math.min(SIZES.length - 1, sizeIdx + 1))}
          disabled={sizeIdx === SIZES.length - 1}
          className={`border-l border-ink-line px-2 py-0.5 text-[11px] transition-colors disabled:opacity-40 ${buttonClassName || "text-[#aab2c4] hover:bg-ink-700"}`}
          aria-label="Larger text"
        >
          A+
        </button>
      </ToolTip>
    </div>
  );
}

const STAGE_LABELS: Record<ManuscriptStage, string> = {
  draft: "Draft",
  revised: "Revised",
  final: "Final",
};

function EditorToggleChip({
  active,
  onClick,
  label,
  tipId,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  tipId?: ToolTipId;
}) {
  const button = (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-md px-2 py-1 text-[11.5px] font-medium transition-colors ${
        active
          ? "bg-amber/20 text-amber-deep"
          : "text-ink-muted hover:bg-ink/5 hover:text-ink-text"
      }`}
    >
      {label}
    </button>
  );
  return tipId ? <ToolTip id={tipId}>{button}</ToolTip> : button;
}

export { EditorToggleChip };

export default function ManuscriptControls({
  stage,
  mode,
  onModeChange,
  words,
  dirty,
  saving,
  lastSaved,
  focus,
  measure,
  onMeasureChange,
  bionicPreview,
  onBionicPreviewChange,
  trailing,
  showSaveStatus = true,
}: {
  stage: ManuscriptStage;
  mode: EditorMode;
  onModeChange: (m: EditorMode) => void;
  words: number;
  dirty: boolean;
  saving: boolean;
  lastSaved: string | null;
  focus: boolean;
  measure: Measure;
  onMeasureChange: (m: Measure) => void;
  bionicPreview: boolean;
  onBionicPreviewChange: (v: boolean) => void;
  trailing?: ReactNode;
  showSaveStatus?: boolean;
}) {
  const stageLabel = STAGE_LABELS[stage];

  return (
    <div
      className={`mb-3 flex flex-wrap items-center justify-between gap-3 ${
        focus ? "shrink-0 border-b border-paper-line pb-3" : ""
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-amber-deep">
          <span className="h-1.5 w-1.5 rounded-full bg-amber-deep" />
          {stageLabel} · {mode === "write" ? "editing" : "preview"}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-[12.5px] text-ink-muted">
        <span className="nums">{words.toLocaleString()} words</span>
        {showSaveStatus && <SaveStatus dirty={dirty} saving={saving} lastSaved={lastSaved} />}
        {!focus && (
          <span className="hidden text-[11px] text-ink-muted lg:inline">Autosaves after you stop typing</span>
        )}

        <div className="flex items-center overflow-hidden rounded-lg border border-paper-line">
          <ToolTip id="chapter.readingWidth">
            <button
              type="button"
              onClick={() =>
                onMeasureChange(measure === "wide" ? "narrow" : measure === "narrow" ? "normal" : "wide")
              }
              className="px-2.5 py-1 text-[11px] font-semibold uppercase text-ink-muted hover:bg-ink/5"
            >
              {measure}
            </button>
          </ToolTip>
        </div>

        <ToolTip id="chapter.writePreviewMode">
          <div className="flex overflow-hidden rounded-lg border border-paper-line">
            {(["write", "preview"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => onModeChange(m)}
                className={`px-3 py-1 text-[12.5px] font-medium capitalize transition-colors ${
                  mode === m ? "bg-ink text-on-ink" : "text-ink-muted hover:bg-ink/5"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        </ToolTip>

        {mode === "preview" && (
          <EditorToggleChip
            active={bionicPreview}
            onClick={() => onBionicPreviewChange(!bionicPreview)}
            label="Bionic"
            tipId="chapter.bionicPreview"
          />
        )}

        {trailing}
      </div>
    </div>
  );
}

export function FormatToolbar({
  measure,
  children,
  trailing,
}: {
  measure: Measure;
  children?: ReactNode;
  trailing?: ReactNode;
}) {
  return (
    <div
      className="mb-2 flex flex-wrap items-center gap-1"
      style={{ maxWidth: MEASURES[measure], marginInline: "auto" }}
    >
      {children}
      {trailing ? (
        <div className="ml-auto flex flex-wrap items-center gap-1">
          {trailing}
        </div>
      ) : null}
    </div>
  );
}

export function ToolbarBtn({
  children,
  onClick,
  label,
  tipId,
}: {
  children: ReactNode;
  onClick: () => void;
  label: string;
  tipId?: ToolTipId;
}) {
  const button = (
    <button
      type="button"
      onClick={onClick}
      title={tipId ? undefined : label}
      aria-label={label}
      className="flex h-8 min-w-8 items-center justify-center rounded-md border border-paper-line bg-paper-card px-2 text-[13px] text-ink-text transition-colors hover:bg-ink/5"
    >
      {children}
    </button>
  );
  return tipId ? <ToolTip id={tipId}>{button}</ToolTip> : button;
}
