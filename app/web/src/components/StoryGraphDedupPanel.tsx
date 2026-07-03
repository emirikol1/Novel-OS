import { useCallback, useEffect, useRef, useState } from "react";
import { api, type GraphDuplicateGroup } from "../api/client";
import Modal, { fieldClass } from "./Modal";
import ToolTip from "./ToolTip";
import { useToast } from "./Toaster";

function groupKey(g: GraphDuplicateGroup): string {
  return g.members.map((m) => m.id).sort().join("|");
}

export default function StoryGraphDedupPanel({
  projectId,
  open,
  onClose,
  onDone,
}: {
  projectId: string;
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const listRef = useRef<HTMLDivElement>(null);
  const [groups, setGroups] = useState<GraphDuplicateGroup[]>([]);
  const [keep, setKeep] = useState<Record<string, string>>({});
  const [titleOverrides, setTitleOverrides] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [merging, setMerging] = useState<string | null>(null);
  const [autoBusy, setAutoBusy] = useState(false);

  const applyReport = useCallback((r: Awaited<ReturnType<typeof api.graphDuplicates>>) => {
    setGroups(r.groups);
    const defaults: Record<string, string> = {};
    for (const g of r.groups) {
      defaults[groupKey(g)] = g.suggested_keep_id;
    }
    setKeep(defaults);
    setTitleOverrides({});
  }, []);

  const load = useCallback(async (opts?: { silent?: boolean }) => {
    const silent = opts?.silent ?? false;
    const scrollTop = silent ? listRef.current?.scrollTop ?? 0 : 0;
    if (!silent) setLoading(true);
    try {
      const r = await api.graphDuplicates(projectId);
      applyReport(r);
      if (silent) {
        requestAnimationFrame(() => {
          if (listRef.current) listRef.current.scrollTop = scrollTop;
        });
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [projectId, toast, applyReport]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  function removeGroup(g: GraphDuplicateGroup) {
    const key = groupKey(g);
    setGroups((prev) => prev.filter((x) => groupKey(x) !== key));
    setKeep((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
    setTitleOverrides((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  async function autoDedupe() {
    setAutoBusy(true);
    try {
      const r = await api.autoResolveGraphDuplicates(projectId);
      toast(`Saved — merged ${r.merged} duplicate graph node(s)`, "success");
      onDone();
      await load({ silent: false });
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setAutoBusy(false);
    }
  }

  async function mergeGroup(g: GraphDuplicateGroup) {
    const key = groupKey(g);
    const keepId = keep[key] ?? g.suggested_keep_id;
    const mergeIds = g.members.map((m) => m.id).filter((id) => id !== keepId);
    if (mergeIds.length === 0) return;
    const scrollTop = listRef.current?.scrollTop ?? 0;
    setMerging(key);
    try {
      const result = await api.mergeGraphDuplicates(projectId, {
        keep_id: keepId,
        merge_ids: mergeIds,
        title_override: titleOverrides[key]?.trim() ?? "",
      });
      removeGroup(g);
      onDone();
      const label = result.keep_label || titleOverrides[key]?.trim() || "merged node";
      toast(`Saved — merged into: ${label}`, "success");
      await load({ silent: true });
      requestAnimationFrame(() => {
        if (listRef.current) listRef.current.scrollTop = scrollTop;
      });
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setMerging(null);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Find duplicate graph nodes" size="wide">
      <p className="mb-4 text-[13.5px] leading-relaxed text-ink-muted">
        Scan story graph nodes for similar titles (and matching kinds/descriptions). Merges
        rewire edges and chapter-brief active nodes. Legacy plot-thread duplicate search on the
        Plot Threads tab is unchanged — use both when migrating from older projects.
      </p>

      <div className="mb-4 flex flex-wrap gap-2">
        <ToolTip id="graph.findDuplicates">
          <button
            type="button"
            onClick={() => load()}
            disabled={loading}
            className="rounded-lg border border-paper-line px-3 py-1.5 text-[12.5px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40"
          >
            Scan graph
          </button>
        </ToolTip>
        <ToolTip id="modal.dedupAutoMerge">
          <button
            type="button"
            onClick={autoDedupe}
            disabled={autoBusy || groups.length === 0}
            className="rounded-lg bg-ink px-3 py-1.5 text-[12.5px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40"
          >
            {autoBusy ? "Merging…" : "Auto-merge exact title matches"}
          </button>
        </ToolTip>
      </div>

      {loading ? (
        <p className="py-8 text-center text-[13px] text-ink-muted">Scanning…</p>
      ) : groups.length === 0 ? (
        <p className="rounded-lg border border-dashed border-paper-line px-5 py-8 text-center text-[13.5px] text-ink-muted">
          No duplicate graph nodes found. Run migration from plot threads first if you expect
          overlap with manually added nodes.
        </p>
      ) : (
        <div ref={listRef} className="flex max-h-[55vh] flex-col gap-3 overflow-y-auto pr-1">
          {groups.map((g) => {
            const key = groupKey(g);
            const keepId = keep[key] ?? g.suggested_keep_id;
            const keepMember = g.members.find((m) => m.id === keepId) ?? g.members[0];
            return (
              <div
                key={key}
                className="rounded-xl border border-paper-line bg-paper-card p-4 shadow-[var(--shadow-paper)]"
              >
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-[13px] font-semibold text-ink-text">
                    {Math.round(g.confidence * 100)}% match
                  </p>
                  <p className="text-[12px] text-ink-muted">{g.reason}</p>
                </div>
                <ul className="mb-3 space-y-1.5">
                  {g.members.map((m) => (
                    <li key={m.id} className="flex items-center gap-2 text-[13px]">
                      <input
                        type="radio"
                        name={`keep-${key}`}
                        checked={keepId === m.id}
                        onChange={() => setKeep((prev) => ({ ...prev, [key]: m.id }))}
                      />
                      <span className="font-medium text-ink-text">{m.label}</span>
                      {m.node_kind && (
                        <span className="rounded bg-ink/5 px-1.5 py-0.5 text-[11px] text-ink-muted">
                          {m.node_kind}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
                <div className="mb-3">
                  <label className="mb-1 block text-[12px] font-medium text-ink-muted">
                    Optional merged title (defaults to keep node)
                  </label>
                  <input
                    className={fieldClass}
                    placeholder={keepMember?.label ?? ""}
                    value={titleOverrides[key] ?? ""}
                    onChange={(e) =>
                      setTitleOverrides((prev) => ({ ...prev, [key]: e.target.value }))
                    }
                  />
                </div>
                <ToolTip id="modal.dedupMerge">
                  <button
                    type="button"
                    onClick={() => mergeGroup(g)}
                    disabled={merging === key}
                    className="rounded-lg border border-amber/40 bg-amber/10 px-3 py-1.5 text-[12.5px] font-semibold text-ink-text hover:bg-amber/15 disabled:opacity-40"
                  >
                    {merging === key ? "Merging…" : "Merge group"}
                  </button>
                </ToolTip>
              </div>
            );
          })}
        </div>
      )}
    </Modal>
  );
}
