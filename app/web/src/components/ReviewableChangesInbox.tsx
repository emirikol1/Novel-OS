import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, type ReviewableChange, type ReviewableChangeStatus } from "../api/client";
import { useBackgroundJob } from "../hooks/useBackgroundJob";
import ToolTip from "./ToolTip";
import { useToast } from "./Toaster";

type ChangeFilter = "all" | ReviewableChangeStatus;
type ChangeAction = "apply" | "dismiss" | "review" | "revert";

const STATUS_ORDER: ReviewableChangeStatus[] = [
  "pending",
  "applied_needs_review",
  "reviewed",
  "dismissed",
  "reverted",
  "blocked",
];

const STATUS_LABELS: Record<ReviewableChangeStatus, string> = {
  pending: "Pending",
  applied_needs_review: "Applied",
  reviewed: "Reviewed",
  dismissed: "Dismissed",
  reverted: "Reverted",
  blocked: "Blocked",
};

const STATUS_DESCRIPTIONS: Record<ReviewableChangeStatus, string> = {
  pending: "Waiting for accept or dismiss",
  applied_needs_review: "Applied automatically; needs review",
  reviewed: "Reviewed and kept",
  dismissed: "Rejected",
  reverted: "Rolled back",
  blocked: "Needs conflict resolution",
};

const STATUS_BADGE_CLASS: Record<ReviewableChangeStatus, string> = {
  pending: "border-amber/30 bg-amber/10 text-amber-deep",
  applied_needs_review: "border-blue-500/25 bg-blue-50 text-blue-700",
  reviewed: "border-st-approved/30 bg-st-approved/10 text-st-approved",
  dismissed: "border-paper-line bg-paper text-ink-muted",
  reverted: "border-purple-400/30 bg-purple-50 text-purple-700",
  blocked: "border-red-500/30 bg-red-50 text-red-700",
};

function isJobStatus(value: unknown): value is { job_id: string } {
  return Boolean(value && typeof value === "object" && "job_id" in value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function formatCompact(value: unknown): string {
  if (value == null || value === "") return "None";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function ValueBlock({ value, muted }: { value: unknown; muted?: boolean }) {
  const text = formatCompact(value);
  return (
    <pre
      className={`max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-paper-line bg-paper/70 p-3 text-[12px] leading-relaxed ${
        muted ? "text-ink-muted" : "text-ink-text"
      }`}
    >
      {text}
    </pre>
  );
}

function ChangeDiff({ before, after }: { before: unknown; after: unknown }) {
  if (isRecord(before) && isRecord(after)) {
    const fields = Array.from(new Set([...Object.keys(before), ...Object.keys(after)])).sort();
    if (fields.length > 0) {
      return (
        <div className="overflow-hidden rounded-lg border border-paper-line">
          <div className="grid grid-cols-[0.7fr_1fr_1fr] bg-paper/80 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            <div className="border-r border-paper-line px-3 py-2">Field</div>
            <div className="border-r border-paper-line px-3 py-2">Before</div>
            <div className="px-3 py-2">After</div>
          </div>
          {fields.map((field) => (
            <div key={field} className="grid grid-cols-[0.7fr_1fr_1fr] border-t border-paper-line text-[12.5px]">
              <div className="border-r border-paper-line px-3 py-2 font-mono text-[11.5px] text-ink-muted">
                {field}
              </div>
              <div className="min-w-0 border-r border-paper-line px-3 py-2 text-ink-muted">
                {formatCompact(before[field])}
              </div>
              <div className="min-w-0 px-3 py-2 text-ink-text">
                {formatCompact(after[field])}
              </div>
            </div>
          ))}
        </div>
      );
    }
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      <div>
        <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Before</p>
        <ValueBlock value={before} muted />
      </div>
      <div>
        <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">After</p>
        <ValueBlock value={after} />
      </div>
    </div>
  );
}

function ActionButton({
  children,
  disabled,
  busy,
  onClick,
  variant = "default",
}: {
  children: ReactNode;
  disabled?: boolean;
  busy?: boolean;
  onClick: () => void;
  variant?: "default" | "primary" | "danger";
}) {
  const className =
    variant === "primary"
      ? "rounded-lg bg-ink px-3.5 py-2 text-[12.5px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40"
      : variant === "danger"
        ? "rounded-lg border border-red-500/30 bg-red-50 px-3.5 py-2 text-[12.5px] font-semibold text-red-700 hover:bg-red-100 disabled:opacity-40"
        : "rounded-lg border border-paper-line bg-paper px-3.5 py-2 text-[12.5px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40";

  return (
    <button type="button" disabled={disabled || busy} onClick={onClick} className={className}>
      {busy ? "Working..." : children}
    </button>
  );
}

export default function ReviewableChangesInbox({ projectId }: { projectId: string }) {
  const toast = useToast();
  const { watchBackgroundJob } = useBackgroundJob();
  const [changes, setChanges] = useState<ReviewableChange[]>([]);
  const [filter, setFilter] = useState<ChangeFilter>("pending");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoApplyGraph, setAutoApplyGraph] = useState(false);
  const [generatingGraph, setGeneratingGraph] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);

  const loadChanges = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setChanges(await api.reviewableChanges(projectId));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      toast(message, "error");
    } finally {
      setLoading(false);
    }
  }, [projectId, toast]);

  useEffect(() => {
    void loadChanges();
  }, [loadChanges]);

  const counts = useMemo(() => {
    const next: Record<ReviewableChangeStatus, number> = {
      pending: 0,
      applied_needs_review: 0,
      reviewed: 0,
      dismissed: 0,
      reverted: 0,
      blocked: 0,
    };
    changes.forEach((change) => {
      next[change.status] += 1;
    });
    return next;
  }, [changes]);

  const filteredChanges = useMemo(() => (
    filter === "all" ? changes : changes.filter((change) => change.status === filter)
  ), [changes, filter]);

  async function generateGraphSuggestions() {
    setGeneratingGraph(true);
    try {
      const result = await api.generateGraphSuggestions(projectId, { auto_apply: autoApplyGraph });
      if ("changes" in result) {
        await loadChanges();
        toast(
          autoApplyGraph
            ? `Generated ${result.generated} graph suggestion(s); auto-applied ${result.applied}`
            : `Generated ${result.generated} graph suggestion(s)`,
          "success",
        );
      } else if (isJobStatus(result)) {
        toast("Generating graph suggestions in the background", "success");
        watchBackgroundJob(result.job_id, {
          kind: "reviewable-graph-suggestions",
          projectId,
          label: "Generate graph suggestions",
          successMessage: autoApplyGraph
            ? "Graph suggestions generated and auto-applied for review"
            : "Graph suggestions ready to review",
          onSuccess: () => {
            void loadChanges();
          },
        });
      } else {
        await loadChanges();
        toast("Graph suggestion request finished", "success");
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setGeneratingGraph(false);
    }
  }

  async function runAction(change: ReviewableChange, action: ChangeAction) {
    const busyKey = `${change.id}:${action}`;
    setBusyAction(busyKey);
    try {
      const updated = await (action === "apply"
        ? api.applyReviewableChange(projectId, change.id)
        : action === "dismiss"
          ? api.dismissReviewableChange(projectId, change.id)
          : action === "review"
            ? api.markReviewableChangeReviewed(projectId, change.id)
            : api.revertReviewableChange(projectId, change.id));
      setChanges((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      toast(
        action === "apply"
          ? "Change applied"
          : action === "dismiss"
            ? "Change dismissed"
            : action === "review"
              ? "Change marked reviewed"
              : "Change reverted",
        "success",
      );
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusyAction(null);
    }
  }

  const totalActive = counts.pending + counts.applied_needs_review + counts.blocked;

  return (
    <section className="space-y-5">
      <div className="rounded-xl border border-paper-line bg-paper-card p-5 shadow-[var(--shadow-paper)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
              Reviewable Changes
            </h2>
            <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-ink-muted">
              Review mined or generated structural updates before they become trusted project memory.
              Auto-applied changes stay here until you mark them reviewed.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2 rounded-lg border border-paper-line bg-paper px-3 py-2 text-[12.5px] font-medium text-ink-text">
              <input
                type="checkbox"
                checked={autoApplyGraph}
                onChange={(event) => setAutoApplyGraph(event.target.checked)}
              />
              Auto-apply graph suggestions
            </label>
            <ToolTip id="dashboard.reviewGraphSuggestions">
              <button
                type="button"
                onClick={() => void generateGraphSuggestions()}
                disabled={generatingGraph}
                className="rounded-lg border border-amber/40 bg-amber/5 px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-amber/10 disabled:opacity-40"
              >
                {generatingGraph ? "Generating..." : "Generate graph suggestions"}
              </button>
            </ToolTip>
            <ToolTip id="global.retry">
              <button
                type="button"
                onClick={() => void loadChanges()}
                disabled={loading}
                className="rounded-lg border border-paper-line bg-paper px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5 disabled:opacity-40"
              >
                {loading ? "Loading..." : "Refresh"}
              </button>
            </ToolTip>
          </div>
        </div>

        <div className="mt-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <button
            type="button"
            onClick={() => setFilter("all")}
            className={`rounded-xl border px-4 py-3 text-left transition-colors ${
              filter === "all" ? "border-amber/40 bg-amber/5" : "border-paper-line bg-paper/70 hover:bg-ink/[0.03]"
            }`}
          >
            <span className="block text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
              All
            </span>
            <span className="mt-1 block text-[22px] font-semibold text-ink-text">{changes.length}</span>
            <span className="text-[12px] text-ink-muted">{totalActive} need attention</span>
          </button>
          {STATUS_ORDER.map((status) => (
            <button
              key={status}
              type="button"
              onClick={() => setFilter(status)}
              className={`rounded-xl border px-4 py-3 text-left transition-colors ${
                filter === status ? "border-amber/40 bg-amber/5" : "border-paper-line bg-paper/70 hover:bg-ink/[0.03]"
              }`}
            >
              <span className="block text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
                {STATUS_LABELS[status]}
              </span>
              <span className="mt-1 block text-[22px] font-semibold text-ink-text">{counts[status]}</span>
              <span className="text-[12px] text-ink-muted">{STATUS_DESCRIPTIONS[status]}</span>
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
          Failed to load reviewable changes: {error}
        </p>
      )}

      {loading && changes.length === 0 ? (
        <div className="rounded-xl border border-paper-line bg-paper-card p-8 text-center text-[13.5px] text-ink-muted">
          Loading reviewable changes...
        </div>
      ) : filteredChanges.length === 0 ? (
        <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-10 text-center text-[13.5px] text-ink-muted">
          No {filter === "all" ? "" : `${STATUS_LABELS[filter].toLowerCase()} `}reviewable changes.
        </div>
      ) : (
        <div className="space-y-4">
          {filteredChanges.map((change) => {
            const conflicts = change.conflicts ?? [];
            const canApply = change.status === "pending" && conflicts.length === 0;
            const canDismiss = change.status === "pending" || change.status === "blocked";
            const canReview = change.status === "applied_needs_review";
            const canRevert = change.revert_available && change.status !== "reverted";
            return (
              <article key={change.id} className="rounded-xl border border-paper-line bg-paper-card p-5 shadow-[var(--shadow-paper)]">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${STATUS_BADGE_CLASS[change.status]}`}>
                        {STATUS_LABELS[change.status]}
                      </span>
                      <span className="rounded-full border border-paper-line bg-paper px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                        {change.kind}
                      </span>
                      {change.confidence != null && (
                        <span className="text-[12px] text-ink-muted">
                          {Math.round(change.confidence * 100)}% confidence
                        </span>
                      )}
                    </div>
                    <h3 className="font-display text-[18px] font-semibold tracking-tight text-ink-text">
                      {change.title}
                    </h3>
                    {(change.summary || change.reason) && (
                      <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">
                        {change.summary || change.reason}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <ToolTip id="modal.minePreviewReview">
                      <ActionButton
                        variant="primary"
                        disabled={!canApply}
                        busy={busyAction === `${change.id}:apply`}
                        onClick={() => void runAction(change, "apply")}
                      >
                        Apply
                      </ActionButton>
                    </ToolTip>
                    <ToolTip id="modal.minePreviewReview">
                      <ActionButton
                        disabled={!canReview}
                        busy={busyAction === `${change.id}:review`}
                        onClick={() => void runAction(change, "review")}
                      >
                        Mark reviewed
                      </ActionButton>
                    </ToolTip>
                    <ToolTip id="modal.minePreviewReview">
                      <ActionButton
                        disabled={!canDismiss}
                        busy={busyAction === `${change.id}:dismiss`}
                        onClick={() => void runAction(change, "dismiss")}
                      >
                        Dismiss
                      </ActionButton>
                    </ToolTip>
                    <ToolTip id="modal.minePreviewReview">
                      <ActionButton
                        variant="danger"
                        disabled={!canRevert}
                        busy={busyAction === `${change.id}:revert`}
                        onClick={() => void runAction(change, "revert")}
                      >
                        Revert
                      </ActionButton>
                    </ToolTip>
                  </div>
                </div>

                <dl className="mt-4 grid gap-3 text-[12.5px] text-ink-muted sm:grid-cols-3">
                  <div>
                    <dt className="font-semibold uppercase tracking-wide">Source</dt>
                    <dd className="mt-1 text-ink-text">{change.source || "Unknown"}</dd>
                  </div>
                  <div>
                    <dt className="font-semibold uppercase tracking-wide">Target</dt>
                    <dd className="mt-1 break-words text-ink-text">{formatCompact(change.target)}</dd>
                  </div>
                  <div>
                    <dt className="font-semibold uppercase tracking-wide">Updated</dt>
                    <dd className="mt-1 text-ink-text">{new Date(change.updated_at).toLocaleString()}</dd>
                  </div>
                </dl>

                {conflicts.length > 0 && (
                  <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
                    <p className="font-semibold">Conflicts need review before applying:</p>
                    <ul className="mt-1 list-disc space-y-1 pl-5">
                      {conflicts.map((conflict) => (
                        <li key={conflict}>{conflict}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="mt-4">
                  <ChangeDiff before={change.before} after={change.after} />
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
