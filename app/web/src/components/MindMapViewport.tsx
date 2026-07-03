import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";
import ToolTip from "./ToolTip";

export type MindMapSearchItem = {
  id: string;
  label: string;
  detail?: string;
};

type MindMapRenderState = {
  query: string;
  matchedIds: Set<string>;
  activeMatchId: string | null;
  isFullscreen: boolean;
};

export default function MindMapViewport({
  title,
  searchPlaceholder = "Search this map...",
  searchItems,
  children,
}: {
  title: string;
  searchPlaceholder?: string;
  searchItems: MindMapSearchItem[];
  children: (state: MindMapRenderState) => ReactNode;
}) {
  const [fullscreen, setFullscreen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [query, setQuery] = useState("");
  const [matchIndex, setMatchIndex] = useState(0);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const panRef = useRef({
    active: false,
    pointerId: 0,
    startX: 0,
    startY: 0,
    scrollLeft: 0,
    scrollTop: 0,
    moved: false,
  });

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return searchItems.filter((item) =>
      `${item.label} ${item.detail ?? ""}`.toLowerCase().includes(q),
    );
  }, [query, searchItems]);

  useEffect(() => {
    setMatchIndex(0);
  }, [query]);

  useEffect(() => {
    if (!fullscreen) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setFullscreen(false);
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [fullscreen]);

  const matchedIds = useMemo(() => new Set(matches.map((item) => item.id)), [matches]);
  const activeMatchId = matches.length > 0 ? matches[matchIndex % matches.length].id : null;

  function changeZoom(next: number) {
    setZoom(Math.min(2.5, Math.max(0.5, Number(next.toFixed(2)))));
  }

  function startPan(event: React.PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    const target = event.target as HTMLElement;
    if (target.closest('button,input,select,textarea,a,label,[data-mindmap-interactive],[role="button"]')) return;
    const el = scrollRef.current;
    if (!el) return;
    panRef.current = {
      active: true,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      scrollLeft: el.scrollLeft,
      scrollTop: el.scrollTop,
      moved: false,
    };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }

  function movePan(event: React.PointerEvent<HTMLDivElement>) {
    const pan = panRef.current;
    const el = scrollRef.current;
    if (!pan.active || pan.pointerId !== event.pointerId || !el) return;
    const dx = event.clientX - pan.startX;
    const dy = event.clientY - pan.startY;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) pan.moved = true;
    el.scrollLeft = pan.scrollLeft - dx;
    el.scrollTop = pan.scrollTop - dy;
  }

  function stopPan(event: React.PointerEvent<HTMLDivElement>) {
    if (panRef.current.pointerId === event.pointerId) {
      panRef.current.active = false;
    }
  }

  function stopDraggedClick(event: React.MouseEvent<HTMLDivElement>) {
    if (!panRef.current.moved) return;
    event.preventDefault();
    event.stopPropagation();
    panRef.current.moved = false;
  }

  const content = (
    <div
      className={`flex h-full min-h-[420px] flex-col rounded-xl border border-paper-line bg-paper-card shadow-[var(--shadow-paper)] ${
        fullscreen ? "min-h-0" : ""
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-paper-line px-3 py-2">
        <div className="min-w-0">
          <p className="truncate text-[12px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
            {title}
          </p>
          <p className="text-[11.5px] text-ink-muted">
            Drag the scrollbars to move around. Zoom and search work in full-browser mode too.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="sr-only" htmlFor={`mind-map-search-${title}`}>
            Search {title}
          </label>
          <ToolTip id="graph.mindMapSearch" className="min-w-0">
            <input
              id={`mind-map-search-${title}`}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={searchPlaceholder}
              className="w-48 rounded-lg border border-paper-line bg-paper px-3 py-1.5 text-[12.5px] text-ink-text placeholder:text-ink-muted/70"
            />
          </ToolTip>
          {query && (
            <span className="nums text-[11.5px] text-ink-muted">
              {matches.length === 0 ? "No matches" : `${matchIndex + 1}/${matches.length}`}
            </span>
          )}
          {matches.length > 1 && (
            <ToolTip id="graph.searchPrevNext">
              <button
                type="button"
                onClick={() => setMatchIndex((i) => (i + 1) % matches.length)}
                className="rounded-lg border border-paper-line px-2.5 py-1.5 text-[12px] font-semibold text-ink-text hover:bg-ink/5"
              >
                Next
              </button>
            </ToolTip>
          )}
          <div className="flex overflow-hidden rounded-lg border border-paper-line">
            <ToolTip id="graph.mindMapZoom">
              <button
                type="button"
                onClick={() => changeZoom(zoom - 0.1)}
                className="px-2.5 py-1.5 text-[12px] font-semibold text-ink-text hover:bg-ink/5"
                aria-label={`Zoom out ${title}`}
              >
                -
              </button>
            </ToolTip>
            <ToolTip id="graph.mindMapZoom">
              <button
                type="button"
                onClick={() => changeZoom(1)}
                className="nums border-x border-paper-line px-2.5 py-1.5 text-[12px] font-semibold text-ink-muted hover:bg-ink/5"
                title="Reset zoom"
              >
                {Math.round(zoom * 100)}%
              </button>
            </ToolTip>
            <ToolTip id="graph.mindMapZoom">
              <button
                type="button"
                onClick={() => changeZoom(zoom + 0.1)}
                className="px-2.5 py-1.5 text-[12px] font-semibold text-ink-text hover:bg-ink/5"
                aria-label={`Zoom in ${title}`}
              >
                +
              </button>
            </ToolTip>
          </div>
          <ToolTip id="graph.mindMapFullscreen">
            <button
              type="button"
              onClick={() => setFullscreen((value) => !value)}
              className="rounded-lg border border-paper-line px-3 py-1.5 text-[12px] font-semibold text-ink-text hover:bg-ink/5"
            >
              {fullscreen ? "Exit full browser" : "Full browser"}
            </button>
          </ToolTip>
        </div>
      </div>
      <div
        ref={scrollRef}
        className="min-h-0 flex-1 cursor-grab overflow-auto bg-paper/60 p-4 active:cursor-grabbing"
        onPointerDown={startPan}
        onPointerMove={movePan}
        onPointerUp={stopPan}
        onPointerCancel={stopPan}
        onClickCapture={stopDraggedClick}
        title="Drag the map background to pan; use scrollbars or zoom controls for large maps."
      >
        <div
          className={`inline-block min-w-full align-top ${fullscreen ? "h-full" : ""}`}
          style={{ zoom } as CSSProperties & { zoom: number }}
        >
          {children({ query, matchedIds, activeMatchId, isFullscreen: fullscreen })}
        </div>
      </div>
    </div>
  );

  if (!fullscreen) return content;

  return createPortal(
    <div className="fixed inset-0 z-[100] bg-paper p-3">
      <div className="h-full">{content}</div>
    </div>,
    document.body,
  );
}
