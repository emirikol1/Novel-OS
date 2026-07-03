import ToolTip from "./ToolTip";
import type { ToolTipId } from "../lib/toolRegistry";

export default function PanelToggle({
  on,
  onClick,
  label,
  border,
  tipId,
}: {
  on: boolean;
  onClick: () => void;
  label: string;
  border?: boolean;
  tipId?: ToolTipId;
}) {
  const button = (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={on}
      className={`flex h-7 items-center px-2.5 text-[12px] font-normal leading-none transition-colors ${border ? "border-l border-paper-line" : ""} ${
        on ? "font-medium text-ink-text" : "text-ink-muted hover:text-ink-text"
      }`}
    >
      {label}
    </button>
  );
  return tipId ? <ToolTip id={tipId} className="inline-flex h-7 items-center">{button}</ToolTip> : button;
}
