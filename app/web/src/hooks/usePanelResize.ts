import { useCallback, useRef, type PointerEvent as ReactPointerEvent } from "react";

export function usePanelResize({
  width,
  onWidthChange,
  onCommit,
  min,
  max,
  side,
}: {
  width: number;
  onWidthChange: (width: number) => void;
  onCommit: (width: number) => void;
  min: number;
  max: number;
  side: "left" | "right";
}) {
  const dragRef = useRef({ active: false, startX: 0, startWidth: width });

  const onPointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      event.preventDefault();
      dragRef.current = { active: true, startX: event.clientX, startWidth: width };
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    [width],
  );

  const onPointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (!dragRef.current.active) return;
      const delta =
        side === "left"
          ? event.clientX - dragRef.current.startX
          : dragRef.current.startX - event.clientX;
      const next = Math.min(max, Math.max(min, dragRef.current.startWidth + delta));
      onWidthChange(next);
    },
    [max, min, onWidthChange, side],
  );

  const onPointerUp = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (!dragRef.current.active) return;
      dragRef.current.active = false;
      event.currentTarget.releasePointerCapture(event.pointerId);
      onCommit(width);
    },
    [onCommit, width],
  );

  return { onPointerDown, onPointerMove, onPointerUp };
}
