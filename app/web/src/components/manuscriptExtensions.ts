import { RangeSetBuilder } from "@codemirror/state";
import { Decoration, EditorView, ViewPlugin, type DecorationSet, type ViewUpdate } from "@codemirror/view";

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function scrollContainerFor(el: HTMLElement): HTMLElement | null {
  let node: HTMLElement | null = el.parentElement;
  while (node) {
    const { overflowY } = getComputedStyle(node);
    if (/(auto|scroll|overlay)/.test(overflowY) && node.scrollHeight > node.clientHeight + 1) {
      return node;
    }
    node = node.parentElement;
  }
  return null;
}

function centerLineInView(view: EditorView) {
  const pos = view.state.selection.main.head;
  const coords = view.coordsAtPos(pos);
  if (!coords) return;

  const lineCenter = (coords.top + coords.bottom) / 2;
  const container = scrollContainerFor(view.dom);
  const useWindow = container == null;

  const top = useWindow ? 0 : container.getBoundingClientRect().top;
  const height = useWindow ? window.innerHeight : container.getBoundingClientRect().height;
  const target = top + height * 0.45;
  const delta = lineCenter - target;

  if (Math.abs(delta) <= 1) return;

  if (useWindow) {
    window.scrollBy({ top: delta, behavior: "auto" });
  } else {
    container.scrollTop += delta;
  }
}

/** Keeps the active cursor line near mid-screen while editing. */
export function typewriterScroll() {
  return ViewPlugin.fromClass(
    class {
      private rafId: number | null = null;

      update(update: ViewUpdate) {
        if (!update.selectionSet && !update.docChanged) return;
        if (this.rafId != null) cancelAnimationFrame(this.rafId);
        this.rafId = requestAnimationFrame(() => {
          this.rafId = null;
          const view = update.view;
          if (prefersReducedMotion()) {
            view.dispatch({
              effects: EditorView.scrollIntoView(view.state.selection.main.head, { y: "center" }),
            });
            return;
          }
          centerLineInView(view);
        });
      }

      destroy() {
        if (this.rafId != null) cancelAnimationFrame(this.rafId);
      }
    },
  );
}

function vanishOpacity(distance: number): number | null {
  if (distance <= 0) return null;
  if (distance === 1) return 0.78;
  if (distance === 2) return 0.58;
  return Math.max(0.1, 0.58 - (distance - 2) * 0.09);
}

/** Fades lines above the active line; never modifies document text. */
export function vanishingLines() {
  return ViewPlugin.fromClass(
    class {
      decorations: DecorationSet = Decoration.none;

      update(update: ViewUpdate) {
        if (!update.docChanged && !update.selectionSet && !update.viewportChanged) return;

        const { state, view } = update;
        const activeLine = state.doc.lineAt(state.selection.main.head).number;
        const builder = new RangeSetBuilder<Decoration>();

        for (const { from, to } of view.visibleRanges) {
          let pos = from;
          while (pos <= to) {
            const line = state.doc.lineAt(pos);
            const opacity = vanishOpacity(activeLine - line.number);
            if (opacity != null) {
              builder.add(
                line.from,
                line.from,
                Decoration.line({ attributes: { style: `opacity:${opacity.toFixed(2)}` } }),
              );
            }
            pos = line.to + 1;
          }
        }
        this.decorations = builder.finish();
      }
    },
    { decorations: (plugin) => plugin.decorations },
  );
}

export const typewriterTheme = EditorView.theme({
  "&.cm-typewriter .cm-scroller": {
    minHeight: "55vh",
  },
});
