import {
  CHAPTER_TARGET_LENGTH_STEP,
  DEFAULT_PROJECT_STYLE,
  stepChapterTargetWords,
} from "../lib/chapterBrief";
import type { ToolTipId } from "../lib/toolRegistry";
import { fieldClass } from "./Modal";
import ToolTip from "./ToolTip";

const stepBtnClass =
  "shrink-0 border border-paper-line bg-paper px-2.5 py-2.5 text-[15px] font-semibold leading-none text-ink-muted transition-colors hover:bg-ink/5 disabled:opacity-40";

type TargetLengthInputProps = {
  id?: string;
  value: number;
  onChange: (value: number) => void;
  projectDefault?: number;
  /** When true, 0 means inherit project default (blank field). */
  allowBlank?: boolean;
  placeholder?: string;
  tipId?: ToolTipId;
};

export default function TargetLengthInput({
  id,
  value,
  onChange,
  projectDefault = DEFAULT_PROJECT_STYLE.chapter_target_words,
  allowBlank = false,
  placeholder,
  tipId,
}: TargetLengthInputProps) {
  const applyStep = (direction: 1 | -1) => {
    onChange(stepChapterTargetWords(value, projectDefault, direction));
  };

  const handleChange = (raw: string) => {
    if (allowBlank && !raw.trim()) {
      onChange(0);
      return;
    }
    const parsed = Number.parseInt(raw, 10);
    if (!Number.isFinite(parsed)) return;
    onChange(Math.max(CHAPTER_TARGET_LENGTH_STEP, parsed));
  };

  const control = (
    <div className="flex items-stretch">
      <button
        type="button"
        className={`${stepBtnClass} rounded-l-lg border-r-0`}
        aria-label={`Decrease target length by ${CHAPTER_TARGET_LENGTH_STEP} words`}
        onClick={() => applyStep(-1)}
      >
        −
      </button>
      <input
        id={id}
        className={`${fieldClass} min-w-0 flex-1 rounded-none border-x-0 text-center [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none`}
        type="number"
        min={CHAPTER_TARGET_LENGTH_STEP}
        step={CHAPTER_TARGET_LENGTH_STEP}
        value={allowBlank && value <= 0 ? "" : value}
        placeholder={placeholder}
        onChange={(e) => handleChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "ArrowUp") {
            e.preventDefault();
            applyStep(1);
          }
          if (e.key === "ArrowDown") {
            e.preventDefault();
            applyStep(-1);
          }
        }}
      />
      <button
        type="button"
        className={`${stepBtnClass} rounded-r-lg border-l-0`}
        aria-label={`Increase target length by ${CHAPTER_TARGET_LENGTH_STEP} words`}
        onClick={() => applyStep(1)}
      >
        +
      </button>
    </div>
  );

  return tipId ? <ToolTip id={tipId}>{control}</ToolTip> : control;
}
