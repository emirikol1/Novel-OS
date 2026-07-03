import type { ChapterMinePreviewUiSummary, MineKind } from "../api/client";

const SKIP_RE =
  /no plot thread|not found|unknown graph node|no parent|skipped malformed|skipped duplicate/i;

function humanizeApply(kind: MineKind, line: string): string {
  const low = line.toLowerCase();
  if (kind === "plots" && low.includes("plot event")) {
    const match = line.match(/\+(\d+)\s+new/i);
    if (match) {
      return `Add ${match[1]} plot-event note(s) to this chapter's internal metadata.`;
    }
    return "Add a plot-event note to this chapter's internal metadata.";
  }
  if (low.includes("plot thread updated")) return "Update an existing legacy Plot Thread.";
  if (low.includes("new plot thread")) return "Create a new legacy Plot Thread.";
  if (low.includes("graph node lifespan")) return "Update a Story Graph node's chapter lifespan.";
  return line.includes("]") ? line.split("]").slice(1).join("]").trim() : line;
}

function humanizeSkip(_kind: MineKind, line: string): string {
  const low = line.toLowerCase();
  if (low.includes("no plot thread for subplot beat")) {
    return "Subplot beat skipped — parent plot not found as a legacy Plot Thread.";
  }
  if (low.includes("unknown graph node")) {
    return "Story Graph lifespan change skipped — node title didn't match your graph.";
  }
  if (low.includes("resolved subplot not found")) {
    return "Resolve-subplot skipped — subplot not found under that parent.";
  }
  return line.includes("]") ? line.split("]").slice(1).join("]").trim() : line;
}

/** Client-side fallback when older previews lack ui_summary from the API. */
export function fallbackMinePreviewUi(
  kind: MineKind,
  changes: string[],
): ChapterMinePreviewUiSummary {
  const will_apply: string[] = [];
  const skipped: string[] = [];
  for (const line of changes) {
    if (SKIP_RE.test(line)) skipped.push(humanizeSkip(kind, line));
    else will_apply.push(humanizeApply(kind, line));
  }
  const can_apply = will_apply.length > 0;
  let advice =
    "Review the lists below. Apply writes successful updates; Discard closes without saving.";
  if (!can_apply && skipped.length > 0) {
    advice =
      kind === "plots"
        ? "Nothing here can be applied. Mine plots targets legacy Plot Threads, but your structure may live on Story Graph instead. Discard and edit Story Graph / chapter beats directly."
        : "Nothing here can be applied — names didn't match your project. Discard to close.";
  }
  return {
    will_apply,
    skipped,
    proposed: [],
    can_apply,
    advice,
  };
}
