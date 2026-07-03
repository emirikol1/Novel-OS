import type { PointerEvent as ReactPointerEvent } from "react";

export default function PanelResizeHandle({
  label,
  onPointerDown,
  onPointerMove,
  onPointerUp,
}: {
  label: string;
  onPointerDown: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onPointerMove: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onPointerUp: (event: ReactPointerEvent<HTMLDivElement>) => void;
}) {
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      className="w-1 shrink-0 cursor-col-resize bg-paper-line hover:bg-amber/40 active:bg-amber/60"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    />
  );
}
