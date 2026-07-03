import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

type ToolTipDetailProps = {
  detail: string;
  label: string;
};

export default function ToolTipDetail({ detail, label }: ToolTipDetailProps) {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });

  useLayoutEffect(() => {
    if (!open || !triggerRef.current || !panelRef.current) return;
    const trigger = triggerRef.current.getBoundingClientRect();
    const panel = panelRef.current.getBoundingClientRect();
    const margin = 8;
    const offset = 6;

    let top = trigger.bottom + offset;
    let left = trigger.left + trigger.width / 2 - panel.width / 2;

    if (top + panel.height > window.innerHeight - margin) {
      top = trigger.top - panel.height - offset;
    }
    if (left < margin) left = margin;
    if (left + panel.width > window.innerWidth - margin) {
      left = window.innerWidth - panel.width - margin;
    }

    setPosition({ top, left });
  }, [open, detail]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onPointerDown = (e: MouseEvent) => {
      const target = e.target as Node;
      if (triggerRef.current?.contains(target) || panelRef.current?.contains(target)) return;
      setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [open]);

  const popoverId = `tooltip-detail-${label.replace(/\s+/g, "-").toLowerCase()}`;

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="pointer-events-auto inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-paper-line bg-paper text-[10px] font-bold leading-none text-ink-muted transition-colors hover:bg-ink/5 hover:text-ink-text"
        aria-label={`More about ${label}`}
        aria-expanded={open}
        aria-controls={open ? popoverId : undefined}
        onClick={(e) => {
          e.stopPropagation();
          e.preventDefault();
          setOpen((v) => !v);
        }}
      >
        ?
      </button>
      {open &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            ref={panelRef}
            id={popoverId}
            role="tooltip"
            className="pointer-events-auto fixed z-[10000] max-w-[280px] rounded-lg border border-paper-line bg-paper-card px-3 py-2.5 text-[12px] leading-relaxed text-ink-text shadow-[var(--shadow-lift)]"
            style={{ top: position.top, left: position.left }}
          >
            {detail}
          </div>,
          document.body,
        )}
    </>
  );
}
