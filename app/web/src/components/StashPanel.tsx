import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type StashedProjectSummary } from "../api/client";
import { useConfirm } from "./Confirm";
import { useToast } from "./Toaster";
import ToolTip from "./ToolTip";

export const STASH_CHANGED_EVENT = "novel-os-stash-changed";

export function notifyStashChanged() {
  window.dispatchEvent(new Event(STASH_CHANGED_EVENT));
}

function fmtStashedAt(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function StashPanel() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<StashedProjectSummary[] | null>(null);
  const [loading, setLoading] = useState(false);
  const confirm = useConfirm();
  const toast = useToast();
  const navigate = useNavigate();

  const reload = useCallback(() => {
    setLoading(true);
    api
      .stashed()
      .then(setItems)
      .catch((e) => toast(e instanceof Error ? e.message : String(e), "error"))
      .finally(() => setLoading(false));
  }, [toast]);

  useEffect(() => {
    if (open) reload();
  }, [open, reload]);

  useEffect(() => {
    function onChanged() {
      if (open) reload();
    }
    window.addEventListener(STASH_CHANGED_EVENT, onChanged);
    return () => window.removeEventListener(STASH_CHANGED_EVENT, onChanged);
  }, [open, reload]);

  async function restore(s: StashedProjectSummary) {
    const ok = await confirm({
      title: "Unstash project",
      message: `Move ${s.filename} back to your library? To discard it, unstash first, then delete the manuscript from the library.`,
      confirmLabel: "Unstash",
    });
    if (!ok) return;
    try {
      const p = await api.restoreStashed(s.id);
      toast(`Unstashed ${s.filename}`, "success");
      reload();
      notifyStashChanged();
      navigate(`/projects/${p.id}`);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  const count = items?.length ?? 0;

  return (
    <div className="border-t border-ink-line/70 pt-4">
      <ToolTip id="global.stashPanel">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-[12.5px] font-medium text-[#aab2c4] transition-colors hover:bg-ink-800 hover:text-white"
        >
          <span className="flex items-center gap-1.5">
            Stash
            {count > 0 && !open && (
              <span className="rounded-full bg-ink-line/80 px-1.5 py-0.5 text-[9px] font-bold text-[#c8cedd]">
                {count}
              </span>
            )}
          </span>
          <span className="text-[10px] text-[#8b93a8]">{open ? "▾" : "▸"}</span>
        </button>
      </ToolTip>

      {open && (
        <div className="mt-2 px-1">
          {loading && items === null && (
            <p className="text-[10.5px] text-[#8b93a8]">Loading…</p>
          )}
          {!loading && items && items.length === 0 && (
            <p className="text-[10.5px] leading-relaxed text-[#8b93a8]">
              No stashed projects. Stashed zips stay here until you unstash them.
            </p>
          )}
          {items && items.length > 0 && (
            <ul className="max-h-48 space-y-1 overflow-y-auto">
              {items.map((s) => (
                <li
                  key={s.id}
                  className="rounded-md border border-ink-line/60 bg-ink-800/40 px-2 py-1.5"
                >
                  <p
                    className="truncate font-mono text-[10px] text-[#d8dce8]"
                    title={s.filename}
                  >
                    {s.filename}
                  </p>
                  <div className="mt-0.5 flex items-center justify-between gap-2">
                    <span className="truncate text-[10px] text-[#8b93a8]">
                      {fmtStashedAt(s.stashed_at)} · {fmtSize(s.size_bytes)}
                    </span>
                    <ToolTip id="global.unstashProject">
                      <button
                        type="button"
                        aria-label={`Unstash ${s.filename}`}
                        onClick={() => void restore(s)}
                        className="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold text-[#c8cedd] hover:bg-ink-700"
                      >
                        Unstash
                      </button>
                    </ToolTip>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
