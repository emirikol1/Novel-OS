import { useCallback, useEffect, useState } from "react";
import {
  api,
  type MentionAnalysis,
  type MentionFieldSuggestion,
} from "../api/client";
import ToolTip from "./ToolTip";

type EditableSuggestion = MentionFieldSuggestion & {
  approved: boolean;
  editedValue: string;
};

function formatValue(v: unknown): string {
  if (Array.isArray(v)) return v.join("; ");
  if (v == null) return "";
  return String(v);
}

function parseEditedValue(field: string, raw: string): string | number | string[] {
  if (field === "last_appearance_chapter") {
    const n = parseInt(raw, 10);
    return Number.isFinite(n) ? n : 0;
  }
  if (field === "knowledge") {
    return raw.split(";").map((s) => s.trim()).filter(Boolean);
  }
  return raw;
}

export default function MentionReviewPanel({
  projectId,
  chapterNumber,
  source,
  open,
  onClose,
  focusCharacterId,
  onApplied,
}: {
  projectId: string;
  chapterNumber: number;
  source: string;
  open: boolean;
  onClose: () => void;
  focusCharacterId?: string | null;
  onApplied?: () => void;
}) {
  const [analysis, setAnalysis] = useState<MentionAnalysis | null>(null);
  const [edits, setEdits] = useState<EditableSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.mentionAnalysis(projectId, chapterNumber, source);
      setAnalysis(data);
      let suggestions = data.suggestions;
      if (focusCharacterId) {
        suggestions = suggestions.filter((s) => s.character_id === focusCharacterId);
      }
      setEdits(
        suggestions.map((s) => ({
          ...s,
          approved: true,
          editedValue: formatValue(s.suggested_value),
        })),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [projectId, chapterNumber, source, focusCharacterId]);

  const refreshSuggestions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await api.suggestMentions(projectId, chapterNumber, { source, use_llm: false });
      const stored = await api.getMentionSuggestions(projectId, chapterNumber);
      if (stored?.suggestions) {
        let suggestions = stored.suggestions as MentionFieldSuggestion[];
        if (focusCharacterId) {
          suggestions = suggestions.filter((s) => s.character_id === focusCharacterId);
        }
        setEdits(
          suggestions.map((s) => ({
            ...s,
            approved: true,
            editedValue: formatValue(s.suggested_value),
          })),
        );
      }
      await loadAnalysis();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [projectId, chapterNumber, source, focusCharacterId, loadAnalysis]);

  useEffect(() => {
    if (open) void loadAnalysis();
  }, [open, loadAnalysis]);

  async function applyApproved() {
    const payload = edits
      .filter((e) => e.approved)
      .map((e) => ({
        character_id: e.character_id,
        field: e.field,
        value: parseEditedValue(e.field, e.editedValue),
        explicit_presence: e.field === "last_appearance_chapter" ? e.explicit_presence : false,
      }));
    if (!payload.length) {
      setError("Select at least one edit to apply.");
      return;
    }
    setApplying(true);
    setError(null);
    try {
      const result = await api.applyMentionEdits(projectId, chapterNumber, payload);
      onApplied?.();
      if (result.applied > 0) {
        await loadAnalysis();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setApplying(false);
    }
  }

  if (!open) return null;

  return (
    <div className="mt-4 rounded-lg border border-paper-line bg-paper-card/80 p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-[14px] font-semibold text-ink-text">Review mention updates</h3>
          <p className="text-[12px] text-ink-muted">
            Suggestions are signals from prose — edit values and approve before applying to cast memory.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ToolTip id="chapter.mentionRefresh">
            <button
              type="button"
              onClick={() => void refreshSuggestions()}
              disabled={loading}
              className="rounded-lg border border-paper-line px-3 py-1.5 text-[12px] font-medium text-ink-text hover:bg-ink/5 disabled:opacity-40"
            >
              {loading ? "Loading…" : "Refresh suggestions"}
            </button>
          </ToolTip>
          <ToolTip id="chapter.mentionClose">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-paper-line px-3 py-1.5 text-[12px] text-ink-muted hover:bg-ink/5"
            >
              Close
            </button>
          </ToolTip>
        </div>
      </div>

      {error && (
        <p className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          {error}
        </p>
      )}

      {analysis && analysis.warnings.length > 0 && (
        <div className="mt-3 space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-deep">
            Continuity warnings (non-blocking)
          </p>
          <ul className="space-y-1.5">
            {analysis.warnings.map((w, i) => (
              <li
                key={`${w.category}-${i}`}
                className="rounded border border-amber-200/60 bg-amber-50/50 px-3 py-2 text-[12px] text-ink-text"
              >
                <span className="font-medium">{w.category}</span>: {w.message}
                {w.suggestion && (
                  <span className="mt-0.5 block text-ink-muted">{w.suggestion}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {edits.length === 0 && !loading && (
        <p className="mt-3 text-[12px] text-ink-muted">
          No memory updates suggested for resolved mentions in this chapter. Try Refresh after editing mentions,
          or add explicit on-page presence for cast members.
        </p>
      )}

      {edits.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-[12px]">
            <thead>
              <tr className="border-b border-paper-line text-ink-muted">
                <th className="py-2 pr-2">Apply</th>
                <th className="py-2 pr-2">Character</th>
                <th className="py-2 pr-2">Field</th>
                <th className="py-2 pr-2">Current</th>
                <th className="py-2 pr-2">Proposed</th>
              </tr>
            </thead>
            <tbody>
              {edits.map((row, idx) => (
                <tr key={`${row.character_id}-${row.field}-${idx}`} className="border-b border-paper-line/50">
                  <td className="py-2 pr-2 align-top">
                    <input
                      type="checkbox"
                      checked={row.approved}
                      onChange={(e) => {
                        const next = [...edits];
                        next[idx] = { ...row, approved: e.target.checked };
                        setEdits(next);
                      }}
                    />
                  </td>
                  <td className="py-2 pr-2 align-top font-medium text-ink-text">
                    {row.character_name}
                    {row.mention_raw && (
                      <span className="mt-0.5 block font-normal text-ink-muted">{row.mention_raw}</span>
                    )}
                  </td>
                  <td className="py-2 pr-2 align-top text-ink-muted">{row.field}</td>
                  <td className="py-2 pr-2 align-top text-ink-muted">{formatValue(row.current_value)}</td>
                  <td className="py-2 align-top">
                    <input
                      className="w-full min-w-[140px] rounded border border-paper-line bg-paper px-2 py-1 text-ink-text"
                      value={row.editedValue}
                      onChange={(e) => {
                        const next = [...edits];
                        next[idx] = { ...row, editedValue: e.target.value };
                        setEdits(next);
                      }}
                    />
                    {row.reason && (
                      <span className="mt-1 block text-[11px] text-ink-muted">{row.reason}</span>
                    )}
                    {row.field === "last_appearance_chapter" && row.explicit_presence && (
                      <span className="mt-1 block text-[11px] text-amber-deep">
                        Requires explicit on-page presence
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <ToolTip id="chapter.mentionApply">
            <button
              type="button"
              onClick={() => void applyApproved()}
              disabled={applying}
              className="mt-3 rounded-lg bg-amber-deep px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-40"
            >
              {applying ? "Applying…" : "Apply approved edits"}
            </button>
          </ToolTip>
        </div>
      )}
    </div>
  );
}
