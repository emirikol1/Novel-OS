import type { MouseEvent } from "react";
import type { ToolTipId } from "../lib/toolRegistry";
import { useConfirm } from "./Confirm";
import ToolTip from "./ToolTip";

/** Archive icon — prompts before running `onConfirm`. */
export default function StashButton({
  label,
  message,
  title = "Stash manuscript",
  confirmLabel = "Stash manuscript",
  onConfirm,
  className = "",
  tipId,
}: {
  label: string;
  message: string;
  title?: string;
  confirmLabel?: string;
  onConfirm: () => void | Promise<void>;
  className?: string;
  tipId?: ToolTipId;
}) {
  const confirm = useConfirm();

  async function handleClick(e: MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    const ok = await confirm({ title, message, confirmLabel });
    if (!ok) return;
    await onConfirm();
  }

  const button = (
    <button
      type="button"
      aria-label={label}
      title={tipId ? undefined : label}
      onClick={handleClick}
      className={`rounded-md p-1.5 text-ink-muted transition-colors hover:bg-amber/10 hover:text-amber-deep ${className}`}
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M4 7h16M6 7V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v2m-3 4v6m-6-6v6M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2l1-12"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );

  return tipId ? <ToolTip id={tipId}>{button}</ToolTip> : button;
}
