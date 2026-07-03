import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  api,
  type AgentPromptSetting,
  type AgentPromptVariant,
  type LlmQueueSettings,
} from "../api/client";
import { SaveStatus, formatSavedAt } from "./EditorSaveBar";
import { useConfirm } from "./Confirm";
import { useToast } from "./Toaster";
import { waitForApiHealth } from "../lib/apiHealth";
import Modal from "./Modal";
import ToolTip from "./ToolTip";

function formatSubmittedAt(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

type DisplayRow = {
  id: string;
  label: string;
  submittedAt: string;
  chapter?: number | null;
  state: "active" | "queued";
  removable: boolean;
  reorderable: boolean;
  batchSize: number;
};

function batchSizeForJob(jobId: string, running: LlmQueueSettings["running_jobs"]): number {
  const row = (running ?? []).find((r) => r.job_id === jobId);
  return row?.batch_size && row.batch_size > 0 ? row.batch_size : 1;
}

function buildRows(queue: LlmQueueSettings): { active: DisplayRow[]; queued: DisplayRow[] } {
  const running = queue.running_jobs ?? [];
  const runningLabels = new Set(running.map((r) => r.label));
  const activeItems = queue.active_items ?? [];
  const queuedItems = queue.queued_items ?? [];

  const active: DisplayRow[] = [
    ...running.map((r) => ({
      id: `job-${r.job_id}`,
      label: r.label,
      submittedAt: r.started_at,
      chapter: r.chapter,
      state: "active" as const,
      removable: true,
      reorderable: false,
      batchSize: r.batch_size && r.batch_size > 0 ? r.batch_size : 1,
    })),
    ...activeItems
      .filter((a) => !runningLabels.has(a.label))
      .map((a) => ({
        id: a.id,
        label: a.label,
        submittedAt: a.submitted_at,
        chapter: a.chapter,
        state: "active" as const,
        removable: true,
        reorderable: false,
        batchSize: a.job_id ? batchSizeForJob(a.job_id, running) : 1,
      })),
  ];

  const queued: DisplayRow[] = queuedItems.map((q) => ({
    id: q.id,
    label: q.label,
    submittedAt: q.submitted_at,
    chapter: q.chapter,
    state: "queued" as const,
    removable: true,
    reorderable: true,
    batchSize: q.job_id ? batchSizeForJob(q.job_id, running) : 1,
  }));

  return { active, queued };
}

function chapterBadge(chapter?: number | null) {
  if (chapter == null) return null;
  return (
    <span className="shrink-0 rounded bg-sky-500/20 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-sky-300">
      Ch.{chapter}
    </span>
  );
}

export function QueueJobPopover({
  queue,
  compact = false,
  onQueueChange,
}: {
  queue: LlmQueueSettings;
  compact?: boolean;
  onQueueChange?: (q: LlmQueueSettings) => void;
}) {
  const confirm = useConfirm();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [dragId, setDragId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const { active, queued } = buildRows(queue);
  const hasWork = active.length > 0 || queued.length > 0;

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const applyQueue = useCallback(
    (next: LlmQueueSettings) => {
      onQueueChange?.(next);
    },
    [onQueueChange],
  );

  async function reorderQueued(ids: string[]) {
    try {
      const next = await api.reorderLlmQueue(ids);
      applyQueue(next);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function moveEntry(id: string, position: "first" | "last") {
    try {
      const next = await api.moveLlmQueueEntry(id, position);
      applyQueue(next);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  async function removeEntry(row: DisplayRow) {
    const isBackgroundJob = row.id.startsWith("job-");
    const batchNote = row.batchSize > 1
      ? `\n\nThis will also cancel ${row.batchSize - 1} related job${row.batchSize - 1 === 1 ? "" : "s"} in the same batch.`
      : "";
    const ok = await confirm({
      title: row.state === "queued" ? "Remove from queue?" : "Cancel job?",
      message: row.state === "queued"
        ? `Cancel this waiting request?${batchNote}\n\n${row.label}`
        : `Stop this job and abort the in-flight API call?${batchNote}\n\n${row.label}`,
      confirmLabel: row.state === "queued" ? "Remove" : "Cancel",
      danger: true,
    });
    if (!ok) return;
    try {
      if (isBackgroundJob) {
        const result = await api.cancelJob(row.id.slice(4));
        const next = await api.llmQueueSettings();
        applyQueue(next);
        toast(
          result.cancelled_jobs > 1
            ? `Cancelled ${result.cancelled_jobs} related jobs`
            : "Job cancelled",
          "success",
        );
        return;
      }
      await api.cancelLlmQueueEntry(row.id);
      const next = await api.llmQueueSettings();
      applyQueue(next);
      toast(row.state === "queued" ? "Removed from queue" : "Job cancelled", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  function onDropQueued(targetId: string) {
    if (!dragId || dragId === targetId) {
      setDragId(null);
      setOverId(null);
      return;
    }
    const ids = queued.map((r) => r.id);
    const from = ids.indexOf(dragId);
    const to = ids.indexOf(targetId);
    if (from < 0 || to < 0) {
      setDragId(null);
      setOverId(null);
      return;
    }
    ids.splice(from, 1);
    ids.splice(to, 0, dragId);
    setDragId(null);
    setOverId(null);
    void reorderQueued(ids);
  }

  function RowActions({ row }: { row: DisplayRow }) {
    return (
      <div className="flex shrink-0 items-center gap-0.5">
        {row.reorderable && (
          <>
            <ToolTip id="global.jobQueue">
              <button
                type="button"
                onClick={() => void moveEntry(row.id, "first")}
                className="rounded px-1 py-0.5 text-[10px] text-[#9aa3b8] hover:bg-white/10 hover:text-white"
              >
                1st
              </button>
            </ToolTip>
            <ToolTip id="global.jobQueue">
              <button
                type="button"
                onClick={() => void moveEntry(row.id, "last")}
                className="rounded px-1 py-0.5 text-[10px] text-[#9aa3b8] hover:bg-white/10 hover:text-white"
              >
                Last
              </button>
            </ToolTip>
          </>
        )}
        {row.removable && (
          <ToolTip id="global.jobQueue">
            <button
              type="button"
              onClick={() => void removeEntry(row)}
              className="rounded px-1 py-0.5 text-[10px] text-red-300 hover:bg-red-500/20"
            >
              ×
            </button>
          </ToolTip>
        )}
      </div>
    );
  }

  function JobList({
    title,
    items,
  }: {
    title: string;
    items: DisplayRow[];
  }) {
    if (items.length === 0) return null;
    return (
      <div className="mb-2 last:mb-0">
        <p className="mb-1 text-[9.5px] font-bold uppercase tracking-wider text-[#9aa3b8]">{title}</p>
        <ul className="flex flex-col gap-1">
          {items.map((row) => (
            <li
              key={row.id}
              draggable={row.reorderable}
              onDragStart={() => row.reorderable && setDragId(row.id)}
              onDragEnd={() => { setDragId(null); setOverId(null); }}
              onDragOver={(e) => {
                if (!row.reorderable || !dragId) return;
                e.preventDefault();
                setOverId(row.id);
              }}
              onDrop={() => row.reorderable && onDropQueued(row.id)}
              className={`rounded-md border px-2 py-1.5 ${
                overId === row.id && dragId
                  ? "border-amber/50 bg-amber/10"
                  : "border-[#2a3348] bg-[#121826]"
              } ${dragId === row.id ? "opacity-50" : ""}`}
            >
              <div className="flex items-start gap-1.5">
                {row.reorderable && (
                  <span
                    className="mt-0.5 shrink-0 cursor-grab text-[#6b7280] active:cursor-grabbing"
                    aria-hidden="true"
                  >
                    ≡
                  </span>
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    {chapterBadge(row.chapter)}
                    {row.batchSize > 1 && (
                      <span className="shrink-0 rounded bg-violet-500/20 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-violet-200">
                        batch ×{row.batchSize}
                      </span>
                    )}
                    <p className="text-[11px] font-medium leading-snug text-[#e8ebf2]">{row.label}</p>
                  </div>
                  <p className="mt-0.5 text-[10px] text-[#8b93a8]">
                    {formatSubmittedAt(row.submittedAt)}
                  </p>
                </div>
                <RowActions row={row} />
              </div>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  const summaryParts: string[] = [];
  if (active.length > 0) summaryParts.push(`${active.length} active`);
  if (queued.length > 0) summaryParts.push(`${queued.length} queued`);

  return (
    <div ref={rootRef} className="relative mt-2 inline-block max-w-full">
      <ToolTip id="global.jobQueue">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className={`cursor-pointer text-left text-[#8b93a8] underline decoration-dotted decoration-[#6b7280] underline-offset-2 hover:text-[#c8cedd] ${
            compact ? "text-[10px]" : "text-[10.5px]"
          }`}
          aria-expanded={open}
          aria-haspopup="dialog"
        >
          {hasWork ? summaryParts.join(" · ") : `${queue.active} active · ${queue.queued} queued`}
          {queue.flushed ? " · flushed" : ""}
        </button>
      </ToolTip>
      {open && (
        <div
          role="dialog"
          aria-label="Job queue"
          className="absolute bottom-full left-0 z-[200] mb-2 w-80 max-w-[calc(100vw-2rem)] rounded-lg border border-[#3d4659] bg-[#0a0f18] px-3 py-2.5 text-left shadow-[0_12px_32px_rgba(0,0,0,0.65)]"
        >
          <div className="max-h-64 overflow-y-auto overscroll-contain pr-0.5">
            {!hasWork ? (
              <p className="text-[11px] text-[#8b93a8]">No jobs running.</p>
            ) : (
              <>
                <JobList title="In progress" items={active} />
                <JobList title="Waiting for slot" items={queued} />
              </>
            )}
          </div>
          {(queued.some((r) => r.reorderable) || active.some((r) => r.removable)) && (
            <p className="mt-2 border-t border-[#2a3348] pt-2 text-[9.5px] leading-snug text-[#6b7280]">
              Drag queued items to reorder · × cancels active or waiting jobs (stops in-flight API calls)
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function SystemSettingsPanel() {
  const toast = useToast();
  const confirm = useConfirm();
  const [open, setOpen] = useState(false);
  const [prefix, setPrefix] = useState("");
  const [agentsDir, setAgentsDir] = useState("");
  const [promptSettings, setPromptSettings] = useState<AgentPromptSetting[]>([]);
  const [promptEditor, setPromptEditor] = useState<AgentPromptSetting | null>(null);
  const [promptVariant, setPromptVariant] = useState<AgentPromptVariant>("current");
  const [customPrompt, setCustomPrompt] = useState("");
  const [promptSaving, setPromptSaving] = useState(false);
  const [maxConcurrent, setMaxConcurrent] = useState(2);
  const [queue, setQueue] = useState<LlmQueueSettings | null>(null);
  const [busy, setBusy] = useState<null | "restart">(null);
  const [prefixDirty, setPrefixDirty] = useState(false);
  const [prefixSaving, setPrefixSaving] = useState(false);
  const [prefixLastSaved, setPrefixLastSaved] = useState<string | null>(null);
  const [concurrencyDirty, setConcurrencyDirty] = useState(false);
  const [concurrencySaving, setConcurrencySaving] = useState(false);
  const [concurrencyLastSaved, setConcurrencyLastSaved] = useState<string | null>(null);
  const prefixLoaded = useRef(false);
  const concurrencyLoaded = useRef(false);
  const savedPrefix = useRef("");
  const savedConcurrency = useRef(2);

  const refreshQueue = useCallback(() => {
    api.llmQueueSettings().then((s) => {
      setQueue(s);
      if (!concurrencyLoaded.current || !concurrencyDirty) {
        setMaxConcurrent(s.max_concurrent);
        savedConcurrency.current = s.max_concurrent;
        concurrencyLoaded.current = true;
      }
    }).catch(() => {});
  }, [concurrencyDirty]);

  const load = useCallback(() => {
    api.systemPromptSettings().then((s) => {
      setPrefix(s.prefix);
      savedPrefix.current = s.prefix;
      setAgentsDir(s.agents_dir);
      prefixLoaded.current = true;
      if (s.prefix) setPrefixLastSaved(formatSavedAt());
    }).catch(() => {});
    api.agentPromptSettings().then((s) => {
      setPromptSettings(s.prompts);
      if (!agentsDir && s.agents_dir) setAgentsDir(s.agents_dir);
    }).catch(() => {});
    refreshQueue();
  }, [agentsDir, refreshQueue]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const timer = window.setInterval(refreshQueue, 2000);
    return () => window.clearInterval(timer);
  }, [refreshQueue]);

  useEffect(() => {
    if (!prefixLoaded.current || !prefixDirty) return;
    const t = window.setTimeout(() => {
      if (prefix === savedPrefix.current) {
        setPrefixDirty(false);
        return;
      }
      setPrefixSaving(true);
      api.saveSystemPromptSettings(prefix)
        .then((s) => {
          setPrefix(s.prefix);
          savedPrefix.current = s.prefix;
          setPrefixDirty(false);
          setPrefixLastSaved(formatSavedAt());
        })
        .catch((e) => toast(e instanceof Error ? e.message : String(e), "error"))
        .finally(() => setPrefixSaving(false));
    }, 700);
    return () => window.clearTimeout(t);
  }, [prefix, prefixDirty, toast]);

  useEffect(() => {
    if (!concurrencyLoaded.current || !concurrencyDirty) return;
    const n = Math.max(1, Math.min(32, maxConcurrent));
    if (Number.isNaN(n)) return;
    const t = window.setTimeout(() => {
      if (n === savedConcurrency.current) {
        setConcurrencyDirty(false);
        return;
      }
      setConcurrencySaving(true);
      api.saveLlmQueueSettings(n)
        .then((s) => {
          setQueue(s);
          setMaxConcurrent(s.max_concurrent);
          savedConcurrency.current = s.max_concurrent;
          setConcurrencyDirty(false);
          setConcurrencyLastSaved(formatSavedAt());
        })
        .catch((e) => toast(e instanceof Error ? e.message : String(e), "error"))
        .finally(() => setConcurrencySaving(false));
    }, 600);
    return () => window.clearTimeout(t);
  }, [maxConcurrent, concurrencyDirty, toast]);

  const hasWork = queue != null && (
    (queue.running_jobs?.length ?? 0) > 0
    || queue.active > 0
    || queue.queued > 0
  );

  async function restart() {
    let latest = queue;
    try {
      latest = await api.llmQueueSettings();
      setQueue(latest);
    } catch {
      /* use cached queue state */
    }

    const running = latest?.running_jobs?.length ?? 0;
    const active = latest?.active ?? 0;
    const queued = latest?.queued ?? 0;
    const jobsBusy = running > 0 || active > 0 || queued > 0;

    if (jobsBusy) {
      const parts: string[] = [];
      if (running > 0) parts.push(`${running} background job${running === 1 ? "" : "s"}`);
      if (active > 0) parts.push(`${active} active LLM call${active === 1 ? "" : "s"}`);
      if (queued > 0) parts.push(`${queued} queued LLM request${queued === 1 ? "" : "s"}`);
      const ok = await confirm({
        title: "Restart while jobs are running?",
        message: `${parts.join(", ")} will be cancelled and the server will restart. In-flight API calls may fail.`,
        confirmLabel: "Restart anyway",
        danger: true,
      });
      if (!ok) return;
    }

    setBusy("restart");
    try {
      const r = await api.restartNovelOs();
      toast(r.message, "success");
      const ready = await waitForApiHealth(90_000);
      if (ready) {
        window.location.reload();
      } else {
        toast("API did not become ready in time — try refreshing manually.", "error");
      }
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(null);
    }
  }

  function openPromptEditor(prompt: AgentPromptSetting) {
    setPromptEditor(prompt);
    setPromptVariant(prompt.selected_variant);
    setCustomPrompt(prompt.custom_prompt || prompt.recommended_default || prompt.current_default);
  }

  async function savePromptEditor() {
    if (!promptEditor) return;
    setPromptSaving(true);
    try {
      const next = await api.saveAgentPromptSetting(promptEditor.agent, {
        selected_variant: promptVariant,
        custom_prompt: customPrompt,
      });
      setPromptSettings(next.prompts);
      const updated = next.prompts.find((p) => p.agent === promptEditor.agent) ?? null;
      setPromptEditor(updated);
      if (updated) {
        setPromptVariant(updated.selected_variant);
        setCustomPrompt(updated.custom_prompt);
      }
      toast("Prompt settings saved", "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setPromptSaving(false);
    }
  }

  const previewPrompt = promptVariant === "recommended"
    ? promptEditor?.recommended_default
    : promptVariant === "custom"
      ? customPrompt
      : promptEditor?.current_default;

  return (
    <>
    <div className="border-t border-ink-line/70 pt-4">
      <ToolTip id="global.systemSettings">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-[12.5px] font-medium text-[#aab2c4] transition-colors hover:bg-ink-800 hover:text-white"
        >
          <span className="flex items-center gap-1.5">
            AI settings
            {hasWork && !open && (
              <span className="rounded-full bg-amber/25 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-amber">
                busy
              </span>
            )}
          </span>
          <span className="text-[10px] text-[#8b93a8]">{open ? "▾" : "▸"}</span>
        </button>
      </ToolTip>

      {!open && hasWork && queue && (
        <div className="mt-1.5 px-1">
          <QueueJobPopover queue={queue} compact onQueueChange={setQueue} />
        </div>
      )}

      {open && (
        <div className="mt-2 space-y-3 px-1">
          <div>
            <label className="mb-1 block text-[10.5px] font-semibold uppercase tracking-wider text-[#8b93a8]">
              Concurrent LLM requests
            </label>
            <p className="mb-1.5 text-[10.5px] leading-relaxed text-[#8b93a8]">
              Maximum simultaneous API calls to LM Studio. Additional jobs wait in a FIFO queue.
              Click the status line for job details (screen · project · chapter · function · time).
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <input
                type="number"
                min={1}
                max={32}
                value={maxConcurrent}
                onChange={(e) => {
                  setMaxConcurrent(Number(e.target.value));
                  setConcurrencyDirty(true);
                }}
                disabled={busy != null}
                className="w-20 rounded-md border border-ink-line bg-ink-800/80 px-2 py-1.5 text-[12px] text-[#d8dce8] focus:border-amber/50 focus:outline-none disabled:opacity-40"
              />
              <SaveStatus
                dirty={concurrencyDirty}
                saving={concurrencySaving}
                lastSaved={concurrencyLastSaved}
                className="text-[#aab2c4]"
              />
            </div>
            {queue && <QueueJobPopover queue={queue} onQueueChange={setQueue} />}
          </div>

          <div>
            <label className="mb-1 block text-[10.5px] font-semibold uppercase tracking-wider text-[#8b93a8]">
              Global system prefix
            </label>
            <p className="mb-1.5 text-[10.5px] leading-relaxed text-[#8b93a8]">
              Prepended to every agent system prompt before the API call. Per-agent prompts live in{" "}
              <code className="text-[10px] text-amber/90">agents/*/prompt.md</code>.
            </p>
            <textarea
              value={prefix}
              onChange={(e) => {
                setPrefix(e.target.value);
                setPrefixDirty(true);
              }}
              rows={5}
              placeholder="e.g. Always write literary past tense. No em dashes. R-rated violence OK."
              className="w-full resize-y rounded-md border border-ink-line bg-ink-800/80 px-2.5 py-2 font-mono text-[11px] leading-relaxed text-[#d8dce8] placeholder:text-[#6b7280] focus:border-amber/50 focus:outline-none"
            />
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <SaveStatus
                dirty={prefixDirty}
                saving={prefixSaving}
                lastSaved={prefixLastSaved}
                className="text-[#aab2c4]"
              />
              <ToolTip id="global.flushQueue">
                <button
                  type="button"
                  onClick={() => void restart()}
                  disabled={busy != null}
                  className="rounded-md border border-ink-line px-2.5 py-1 text-[11px] font-semibold text-[#c8cedd] transition-colors hover:bg-ink-800 disabled:opacity-40"
                >
                  {busy === "restart" ? "Restarting…" : "Restart (flush queue)"}
                </button>
              </ToolTip>
            </div>
          </div>

          <div>
            <div className="mb-1 flex items-center justify-between gap-2">
              <label className="block text-[10.5px] font-semibold uppercase tracking-wider text-[#8b93a8]">
                Agent prompt presets
              </label>
              <span className="text-[10px] text-[#6b7280]">
                current · recommended · custom
              </span>
            </div>
            <p className="mb-2 text-[10.5px] leading-relaxed text-[#8b93a8]">
              Choose the system prompt variant for each agent. Custom prompts get parser-safe output contracts appended automatically.
              {" "}
              <Link to="/help/prompt-settings" className="font-semibold text-amber/90 hover:underline">
                Help
              </Link>
            </p>
            <div className="space-y-1.5">
              {promptSettings.length === 0 ? (
                <p className="rounded-md border border-ink-line bg-ink-800/60 px-2.5 py-2 text-[10.5px] text-[#8b93a8]">
                  Prompt settings unavailable.
                </p>
              ) : promptSettings.map((prompt) => (
                <ToolTip key={prompt.agent} id="global.agentPrompts">
                  <button
                    type="button"
                    onClick={() => openPromptEditor(prompt)}
                    className="flex w-full items-center justify-between gap-2 rounded-md border border-ink-line bg-ink-800/60 px-2.5 py-2 text-left transition-colors hover:border-amber/40 hover:bg-ink-800"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-[12px] font-semibold text-[#d8dce8]">{prompt.label}</span>
                      <span className="block text-[10px] text-[#8b93a8]">{prompt.agent}</span>
                    </span>
                    <span className="shrink-0 rounded-full bg-amber/15 px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wide text-amber">
                      {prompt.selected_variant}
                    </span>
                  </button>
                </ToolTip>
              ))}
            </div>
          </div>
          {agentsDir && (
            <p className="text-[10px] leading-relaxed text-[#6b7280]">
              Agent prompts: <span className="break-all text-[#8b93a8]">{agentsDir}</span>
            </p>
          )}
        </div>
      )}
    </div>
    <Modal
      open={promptEditor != null}
      onClose={() => setPromptEditor(null)}
      title={promptEditor ? `${promptEditor.label} prompt` : "Agent prompt"}
      size="wide"
    >
      {promptEditor && (
        <div className="space-y-5">
          <div className="rounded-xl border border-amber/30 bg-amber/5 px-4 py-3 text-[13px] leading-relaxed text-ink-muted">
            <strong className="text-ink-text">Safe editing:</strong> Custom prompts can change voice, priorities, and behavior, but Novel OS appends an immutable output contract for parser-critical agents.
          </div>

          <div>
            <label className="mb-1.5 block text-[12px] font-semibold uppercase tracking-[0.1em] text-ink-muted">
              Variant
            </label>
            <div className="flex flex-wrap overflow-hidden rounded-lg border border-paper-line">
              {(["current", "recommended", "custom"] as AgentPromptVariant[]).map((variant) => (
                <ToolTip key={variant} id="global.agentPrompts">
                  <button
                    type="button"
                    onClick={() => setPromptVariant(variant)}
                    className={`px-4 py-2 text-[13px] font-semibold capitalize transition-colors ${
                      promptVariant === variant
                        ? "bg-ink text-on-ink"
                        : "bg-paper-card text-ink-muted hover:bg-ink/5 hover:text-ink-text"
                    }`}
                  >
                    {variant === "current" ? "Current default" : variant}
                  </button>
                </ToolTip>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-[12px] font-semibold uppercase tracking-[0.1em] text-ink-muted">
              Custom prompt
            </label>
            <textarea
              value={customPrompt}
              onChange={(e) => {
                setCustomPrompt(e.target.value);
                if (promptVariant !== "custom") setPromptVariant("custom");
              }}
              rows={13}
              className="w-full resize-y rounded-lg border border-paper-line bg-paper px-3.5 py-3 font-mono text-[12px] leading-relaxed text-ink-text placeholder:text-paper-muted"
              placeholder="Write a custom system prompt for this agent…"
            />
            {promptEditor.contract_guard && (
              <p className="mt-1.5 text-[12px] text-ink-muted">
                A protected output contract is appended when Custom is selected.
              </p>
            )}
          </div>

          <div>
            <label className="mb-1.5 block text-[12px] font-semibold uppercase tracking-[0.1em] text-ink-muted">
              Effective preview
            </label>
            <pre className="max-h-56 overflow-auto rounded-lg border border-paper-line bg-paper px-3.5 py-3 whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-ink-muted">
              {previewPrompt || "No prompt text."}
            </pre>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <ToolTip id="global.agentPrompts">
              <button
                type="button"
                onClick={() => {
                  setCustomPrompt(promptEditor.recommended_default);
                  setPromptVariant("custom");
                }}
                className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5"
              >
                Copy recommended into custom
              </button>
            </ToolTip>
            <div className="flex gap-2">
              <ToolTip id="global.modalClose">
                <button
                  type="button"
                  onClick={() => setPromptEditor(null)}
                  className="rounded-lg px-4 py-2 text-[13px] font-semibold text-ink-muted transition-colors hover:bg-ink/5"
                >
                  Close
                </button>
              </ToolTip>
              <ToolTip id="global.saveSettings">
                <button
                  type="button"
                  onClick={() => void savePromptEditor()}
                  disabled={promptSaving}
                  className="rounded-lg bg-ink px-5 py-2 text-[13px] font-semibold text-on-ink transition-colors hover:bg-ink-800 disabled:opacity-40"
                >
                  {promptSaving ? "Saving…" : "Save prompt"}
                </button>
              </ToolTip>
            </div>
          </div>
        </div>
      )}
    </Modal>
    </>
  );
}
