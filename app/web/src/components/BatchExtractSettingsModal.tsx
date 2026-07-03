import { useEffect, useState } from "react";
import type { BatchExtractOutlineStats } from "../api/client";
import Modal from "./Modal";
import ToolTip from "./ToolTip";

export type BatchExtractScope = "missing" | "all";

export type BatchScopeVariant = "missing-all" | "eligible-auto";

export default function BatchExtractSettingsModal({
  open,
  title,
  description,
  loading,
  stats,
  missingLabel,
  runTipId,
  showAutoAccept,
  scopeVariant = "missing-all",
  onClose,
  onRun,
}: {
  open: boolean;
  title: string;
  description: string;
  loading: boolean;
  stats: BatchExtractOutlineStats | null;
  missingLabel: string;
  runTipId:
    | "dashboard.batchExtractOutlines"
    | "dashboard.batchExtractCodex"
    | "dashboard.populateChapterBriefs"
    | "dashboard.autoTitleChapters";
  showAutoAccept?: boolean;
  scopeVariant?: BatchScopeVariant;
  onClose: () => void;
  onRun: (opts: {
    skipExisting: boolean;
    autoAccept: boolean;
    titleScope?: "eligible" | "auto_only";
  }) => void;
}) {
  const [scope, setScope] = useState<BatchExtractScope>("missing");
  const [autoAccept, setAutoAccept] = useState(false);
  const includeAutoAccept = showAutoAccept !== false;
  const isTitleScope = scopeVariant === "eligible-auto";

  useEffect(() => {
    if (!open) return;
    setScope("missing");
    setAutoAccept(false);
  }, [open]);

  const targetCount = isTitleScope
    ? scope === "missing"
      ? stats?.missing_count ?? 0
      : stats?.secondary_count ?? 0
    : scope === "missing"
      ? stats?.missing_count ?? 0
      : stats?.total_with_prose ?? 0;

  const scopeName = isTitleScope ? "batch-title-scope" : "batch-extract-scope";

  return (
    <Modal
      open={open}
      onClose={() => {
        if (loading) return;
        onClose();
      }}
      title={title}
      size="wide"
    >
      <p className="text-[14px] leading-relaxed text-ink-muted">{description}</p>

      {loading ? (
        <p className="mt-4 text-[13px] text-ink-muted">Counting chapters…</p>
      ) : stats ? (
        <p className="mt-4 text-[13px] text-ink-text">
          {stats.total_with_prose} chapter
          {stats.total_with_prose === 1 ? "" : "s"} with prose
          {isTitleScope ? (
            <>
              {" — "}
              <span className="font-semibold">{stats.missing_count} eligible</span> for auto-title
              {(stats.secondary_count ?? 0) > 0 ? (
                <>
                  , <span className="font-semibold">{stats.secondary_count ?? 0}</span> with auto-titles
                </>
              ) : null}
              .
            </>
          ) : (
            <>
              {" — "}
              <span className="font-semibold">{stats.missing_count} missing</span> {missingLabel}.
            </>
          )}
        </p>
      ) : null}

      <fieldset className="mt-5 space-y-2">
        <legend className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-muted">
          Scope
        </legend>
        <label className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-paper-line px-3 py-2.5 hover:bg-ink/[0.02]">
          <input
            type="radio"
            name={scopeName}
            className="mt-0.5"
            checked={scope === "missing"}
            onChange={() => setScope("missing")}
          />
          <span className="text-[13px] text-ink-text">
            <span className="font-semibold">{isTitleScope ? "All" : "Missing"}</span>
            <span className="block text-[12.5px] text-ink-muted">
              {isTitleScope
                ? `Chapters with prose that are not manually titled${stats ? ` (${stats.missing_count})` : ""}.`
                : `Skip chapters that already have saved results or pending previews${stats ? ` (${stats.missing_count})` : ""}.`}
            </span>
          </span>
        </label>
        <label className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-paper-line px-3 py-2.5 hover:bg-ink/[0.02]">
          <input
            type="radio"
            name={scopeName}
            className="mt-0.5"
            checked={scope === "all"}
            onChange={() => setScope("all")}
          />
          <span className="text-[13px] text-ink-text">
            <span className="font-semibold">{isTitleScope ? "All auto-titles" : "All"}</span>
            <span className="block text-[12.5px] text-ink-muted">
              {isTitleScope
                ? `Regenerate only chapters with auto-generated titles${stats ? ` (${stats.secondary_count ?? 0})` : ""}.`
                : `Regenerate for every chapter with prose${stats ? ` (${stats.total_with_prose})` : ""}.`}
            </span>
          </span>
        </label>
      </fieldset>

      {includeAutoAccept ? (
      <label className="mt-4 flex cursor-pointer items-start gap-2.5 rounded-lg border border-paper-line px-3 py-2.5 hover:bg-ink/[0.02]">
        <input
          type="checkbox"
          className="mt-0.5"
          checked={autoAccept}
          onChange={(e) => setAutoAccept(e.target.checked)}
        />
        <span className="text-[13px] text-ink-text">
          <span className="font-semibold">Auto-accept</span>
          <span className="block text-[12.5px] text-ink-muted">
            Save results directly without per-chapter preview review.
          </span>
        </span>
      </label>
      ) : null}

      <div className="mt-6 flex flex-wrap justify-end gap-3">
        <ToolTip id="modal.cancel">
          <button
            type="button"
            disabled={loading}
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-[13.5px] font-semibold text-ink-muted transition-colors hover:bg-ink/5 disabled:opacity-40"
          >
            Cancel
          </button>
        </ToolTip>
        <ToolTip id={runTipId}>
          <button
            type="button"
            disabled={loading || !stats || targetCount === 0}
            onClick={() =>
              onRun({
                skipExisting: scope === "missing",
                autoAccept,
                titleScope: isTitleScope
                  ? scope === "missing"
                    ? "eligible"
                    : "auto_only"
                  : undefined,
              })
            }
            className="rounded-lg bg-ink px-5 py-2 text-[13.5px] font-semibold text-on-ink transition-colors hover:bg-ink-800 disabled:opacity-40"
          >
            Run{targetCount > 0 ? ` (${targetCount})` : ""}
          </button>
        </ToolTip>
      </div>
    </Modal>
  );
}
