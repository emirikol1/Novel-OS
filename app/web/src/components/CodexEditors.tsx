import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, characterPortraitUrl, type CharacterDetail, type CharacterSummary, type PlotThreadSummary } from "../api/client";
import { fieldClass } from "./Modal";
import Modal, { Field } from "./Modal";
import { SaveStatus, formatSavedAt } from "./EditorSaveBar";
import StoryBibleDedupPanel from "./StoryBibleDedupPanel";
import ToolTip from "./ToolTip";
import { useBackgroundJob } from "../hooks/useBackgroundJob";
import PendingAiStar from "./PendingAiStar";
import { useToast } from "./Toaster";
import { reassignChapterPreviewPending } from "../lib/chapterPreviewPending";
import { reassignChapterWorkflowMarker } from "../lib/chapterWorkflow";
import { isJobCancelledError, pollJob } from "../lib/jobPolling";
import {
  CANONICAL_RELATIONSHIP_ROLES,
  RELATIONSHIP_SUBROLE_SUGGESTIONS,
  parseRelationshipLabel,
  stringifyRelationshipLabel,
} from "../lib/characterRelationships";

const ROLES = ["protagonist", "antagonist", "supporting", "minor"];
const THREAD_TYPES = ["main", "subplot", "character_arc", "mystery"];
const STATUSES = ["active", "resolved", "foreshadowed", "abandoned"];

function mergeCharacterUpdates(
  base: CharacterDetail,
  updates: Partial<CharacterDetail>,
): CharacterDetail {
  return { ...base, ...updates };
}

export function RenumberChapterModal({
  projectId, chapter, open, onClose, onDone, onBeforeReassign,
}: {
  projectId: string;
  chapter: { number: number; title: string } | null;
  open: boolean;
  onClose: () => void;
  onDone: (newNumber: number) => void;
  onBeforeReassign?: () => Promise<void> | void;
}) {
  const toast = useToast();
  const [toNumber, setToNumber] = useState(chapter?.number ?? 1);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open && chapter) setToNumber(chapter.number);
  }, [open, chapter]);

  if (!chapter) return null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (toNumber === chapter!.number) {
      onClose();
      return;
    }
    setBusy(true);
    try {
      await onBeforeReassign?.();
      const r = await api.reassignChapter(projectId, chapter!.number, toNumber);
      reassignChapterPreviewPending(projectId, r.from_number, r.to_number, r.action === "swapped");
      reassignChapterWorkflowMarker(projectId, r.from_number, r.to_number, r.action === "swapped");
      if (r.action === "swapped") {
        toast(`Swapped chapters ${r.from_number} and ${r.to_number}`, "success");
      } else {
        toast(`Chapter renumbered to ${r.to_number}`, "success");
      }
      onClose();
      onDone(r.to_number);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={busy ? () => {} : onClose} title={`Renumber Chapter ${chapter.number}`}>
      <p className="mb-4 text-[13.5px] leading-relaxed text-ink-muted">
        Assign a new chapter number. Draft, outline, and manuscript files move with it.
        If chapter {toNumber || "…"} already exists, the two chapters will <strong>swap</strong> numbers.
      </p>
      <form onSubmit={submit}>
        <Field label="New chapter number">
          <input type="number" min={1} autoFocus className={fieldClass} value={toNumber}
                 onChange={(e) => setToNumber(Number(e.target.value))} disabled={busy} />
        </Field>
        {chapter.title && (
          <p className="text-[13px] text-ink-muted">“{chapter.title}”</p>
        )}
        <div className="mt-6 flex justify-end gap-3">
          <ToolTip id="modal.cancel">
            <button type="button" onClick={onClose} disabled={busy}
                    className="rounded-lg px-4 py-2 text-[13.5px] font-semibold text-ink-muted hover:bg-ink/5 disabled:opacity-40">
              Cancel
            </button>
          </ToolTip>
          <ToolTip id="modal.renumberChapter">
            <button type="submit" disabled={busy || toNumber < 1}
                    className="rounded-lg bg-ink px-5 py-2 text-[13.5px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
              {busy ? "Renumbering…" : "Renumber"}
            </button>
          </ToolTip>
        </div>
      </form>
    </Modal>
  );
}

export function PasteChapterModal({
  projectId, open, onClose, onDone, defaultNumber = 1,
}: {
  projectId: string; open: boolean; onClose: () => void; onDone: () => void;
  defaultNumber?: number;
}) {
  const toast = useToast();
  const navigate = useNavigate();
  const [number, setNumber] = useState(defaultNumber);
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [extract, setExtract] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) setNumber(defaultNumber);
  }, [open, defaultNumber]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    try {
      const result = await api.createChapter(projectId, {
        number, title: title.trim(), text: text.trim(), extract,
      });
      if ("job_id" in result) {
        toast("Extracting characters & plot…", "success");
        await pollJob(result.job_id);
      }
      toast(`Chapter ${number} saved`, "success");
      onDone();
      onClose();
      navigate(`/projects/${projectId}/chapters/${number}?stage=draft`);
    } catch (err) {
      if (isJobCancelledError(err)) toast("Cancelled", "success");
      else toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={busy ? () => {} : onClose} title="Add Chapter (paste prose)">
      <p className="mb-4 text-[13.5px] leading-relaxed text-ink-muted">
        Paste one chapter at a time. Save as draft, then optionally run the Archivist to pull out
        characters, plot threads, and story bible notes.
      </p>
      <form onSubmit={submit}>
        <div className="mb-4 flex gap-3">
          <Field label="Chapter #">
            <input type="number" min={1} className={fieldClass} value={number}
                   onChange={(e) => setNumber(Number(e.target.value))} disabled={busy} />
          </Field>
          <Field label="Title (optional)">
            <input className={fieldClass} value={title} onChange={(e) => setTitle(e.target.value)}
                   placeholder="e.g. The Archive" disabled={busy} />
          </Field>
        </div>
        <Field label="Chapter text">
          <textarea className={`${fieldClass} min-h-[220px] font-[family-name:var(--font-prose)] leading-relaxed`}
                    value={text} onChange={(e) => setText(e.target.value)}
                    placeholder="Paste your chapter here…" disabled={busy} />
        </Field>
        <label className="mt-2 flex items-center gap-2 text-[13px] text-ink-text">
          <input type="checkbox" checked={extract} onChange={(e) => setExtract(e.target.checked)} disabled={busy} />
          Extract characters, plot &amp; world facts (LM Studio)
        </label>
        <div className="mt-6 flex justify-end gap-3">
          <ToolTip id="modal.cancel">
            <button type="button" onClick={onClose} disabled={busy}
                    className="rounded-lg px-4 py-2 text-[13.5px] font-semibold text-ink-muted hover:bg-ink/5 disabled:opacity-40">
              Cancel
            </button>
          </ToolTip>
          <ToolTip id="modal.pasteChapter">
            <button type="submit" disabled={!text.trim() || busy}
                    className="rounded-lg bg-ink px-5 py-2 text-[13.5px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
              {busy ? "Working…" : extract ? "Save & Extract" : "Save Chapter"}
            </button>
          </ToolTip>
        </div>
      </form>
    </Modal>
  );
}

export function CharacterEditorModal({
  projectId, characterId, open, onClose, onSaved,
}: {
  projectId: string; characterId: string | null; open: boolean;
  onClose: () => void; onSaved: () => void;
}) {
  const toast = useToast();
  const [data, setData] = useState<CharacterDetail | null>(null);
  const [cast, setCast] = useState<CharacterSummary[]>([]);
  const [aliasesText, setAliasesText] = useState("");
  const [relationships, setRelationships] = useState<Record<string, string>>({});
  const [newRelTarget, setNewRelTarget] = useState("");
  const [newRelRole, setNewRelRole] = useState("");
  const [newRelLabel, setNewRelLabel] = useState("");
  const [genPrompt, setGenPrompt] = useState("");
  const [generating, setGenerating] = useState(false);
  const [portraitUploading, setPortraitUploading] = useState(false);
  const [portraitVersion, setPortraitVersion] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<string | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dataRef = useRef<CharacterDetail | null>(null);
  const aliasesRef = useRef("");
  const relationshipsRef = useRef<Record<string, string>>({});
  const loadedSnapshot = useRef("");

  const load = useCallback(() => {
    if (!characterId) return;
    api.character(projectId, characterId).then((d) => {
      setData(d);
      dataRef.current = d;
      const aliases = (d.aliases ?? []).join("\n");
      setAliasesText(aliases);
      aliasesRef.current = aliases;
      const rels = { ...(d.relationships ?? {}) };
      setRelationships(rels);
      relationshipsRef.current = rels;
      loadedSnapshot.current = JSON.stringify({ ...d, aliases: d.aliases ?? [], relationships: rels });
      setDirty(false);
    }).catch(() => setData(null));
    api.characters(projectId).then(setCast).catch(() => setCast([]));
  }, [projectId, characterId]);

  useEffect(() => {
    if (open) {
      load();
      setGenPrompt("");
      setPortraitVersion(0);
    }
  }, [open, load]);

  const persistCharacter = useCallback(async (opts?: { silent?: boolean }) => {
    if (!dataRef.current || !characterId) return;
    const aliases = aliasesRef.current
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    const payload = { ...dataRef.current, aliases, relationships: relationshipsRef.current };
    const snap = JSON.stringify(payload);
    if (snap === loadedSnapshot.current) {
      setDirty(false);
      return;
    }
    setSaving(true);
    try {
      await api.updateCharacter(projectId, characterId, payload);
      loadedSnapshot.current = snap;
      setDirty(false);
      setLastSaved(formatSavedAt());
      onSaved();
      if (!opts?.silent) toast("Character saved", "success");
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setSaving(false);
    }
  }, [projectId, characterId, onSaved, toast]);

  function queueSave() {
    setDirty(true);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      void persistCharacter({ silent: true });
    }, 700);
  }

  function set(field: keyof CharacterDetail, value: string | number) {
    setData((d) => {
      const next = d ? { ...d, [field]: value } : d;
      dataRef.current = next;
      return next;
    });
    queueSave();
  }

  function setAliases(value: string) {
    setAliasesText(value);
    aliasesRef.current = value;
    queueSave();
  }

  function setRelationshipTarget(targetId: string, label: string) {
    const next = { ...relationshipsRef.current };
    if (label.trim()) next[targetId] = label.trim();
    else delete next[targetId];
    setRelationships(next);
    relationshipsRef.current = next;
    queueSave();
  }

  function setRelationshipParts(targetId: string, role: string, label: string) {
    const value = role
      ? stringifyRelationshipLabel(role, label.trim() || role)
      : label.trim();
    setRelationshipTarget(targetId, value);
  }

  function removeRelationship(targetId: string) {
    const next = { ...relationshipsRef.current };
    delete next[targetId];
    setRelationships(next);
    relationshipsRef.current = next;
    queueSave();
  }

  function addRelationship() {
    if (!newRelTarget || (!newRelRole && !newRelLabel.trim())) return;
    const label = newRelRole
      ? stringifyRelationshipLabel(newRelRole, newRelLabel.trim() || newRelRole)
      : newRelLabel.trim();
    setRelationshipTarget(newRelTarget, label);
    setNewRelTarget("");
    setNewRelRole("");
    setNewRelLabel("");
  }

  const otherCast = cast.filter((c) => c.id !== characterId);
  const relSuggestions = [...RELATIONSHIP_SUBROLE_SUGGESTIONS];

  const portraitSrc = data?.portrait_url && characterId
    ? `${characterPortraitUrl(projectId, characterId)}?v=${portraitVersion}`
    : null;

  async function handleClose() {
    if (saveTimer.current) {
      clearTimeout(saveTimer.current);
      saveTimer.current = null;
    }
    if (dirty) await persistCharacter({ silent: true });
    onClose();
  }

  async function uploadPortrait(file: File) {
    if (!characterId) return;
    setPortraitUploading(true);
    try {
      const updated = await api.uploadCharacterPortrait(projectId, characterId, file);
      setData(updated);
      dataRef.current = updated;
      setPortraitVersion((v) => v + 1);
      onSaved();
      toast("Portrait uploaded", "success");
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setPortraitUploading(false);
    }
  }

  async function removePortrait() {
    if (!characterId || !data?.portrait_url) return;
    setPortraitUploading(true);
    try {
      const updated = await api.removeCharacterPortrait(projectId, characterId);
      setData(updated);
      dataRef.current = updated;
      setPortraitVersion((v) => v + 1);
      onSaved();
      toast("Portrait removed", "success");
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setPortraitUploading(false);
    }
  }

  async function generateProps() {
    if (!characterId || !genPrompt.trim()) return;
    setGenerating(true);
    try {
      const job = await api.generateCharacter(projectId, {
        prompt: genPrompt.trim(),
        character_id: characterId,
      });
      toast("Generating character properties…", "success");
      await pollJob(job.job_id);
      const preview = await api.getCharacterGeneratePreview(projectId);
      if (!preview?.updates || Object.keys(preview.updates).length === 0) {
        throw new Error("No character profile was generated.");
      }
      setData((d) => {
        const next = d ? mergeCharacterUpdates(d, preview.updates) : d;
        dataRef.current = next;
        return next;
      });
      if (preview.updates.aliases?.length) {
        const a = preview.updates.aliases.join("\n");
        setAliasesText(a);
        aliasesRef.current = a;
      }
      await api.discardCharacterGeneratePreview(projectId);
      queueSave();
      toast("Properties generated — review fields below", "success");
    } catch (err) {
      if (isJobCancelledError(err)) toast("Cancelled", "success");
      else toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setGenerating(false);
    }
  }

  if (!data) return null;

  return (
    <Modal open={open} onClose={generating || saving || portraitUploading ? () => {} : () => void handleClose()} title={data.full_name}>
      <div className="max-h-[70vh] overflow-y-auto pr-1">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <SaveStatus dirty={dirty} saving={saving} lastSaved={lastSaved} />
          <span className="text-[11px] text-ink-muted">Autosaves after you stop typing</span>
        </div>
        <section className="mb-5 rounded-xl border border-paper-line bg-paper-card/60 p-4">
          <Field label="Portrait">
            <div className="flex flex-wrap items-start gap-4">
              <div className="flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-paper-line bg-paper-bg">
                {portraitSrc ? (
                  <img
                    src={portraitSrc}
                    alt={`Portrait of ${data.full_name}`}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <span className="font-display text-[28px] font-semibold text-ink-muted">
                    {data.full_name.charAt(0).toUpperCase()}
                  </span>
                )}
              </div>
              <div className="flex min-w-[10rem] flex-1 flex-col gap-2">
                <label className="inline-flex w-fit cursor-pointer items-center rounded-lg border border-paper-line px-3 py-2 text-[13px] font-semibold text-ink-text transition-colors hover:bg-ink/5">
                  {portraitUploading ? "Uploading…" : portraitSrc ? "Replace portrait" : "Upload portrait"}
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/gif"
                    className="sr-only"
                    disabled={portraitUploading || generating || saving}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      e.target.value = "";
                      if (file) void uploadPortrait(file);
                    }}
                  />
                </label>
                {portraitSrc && (
                  <ToolTip id="codex.removeCharacterPortrait">
                    <button
                      type="button"
                      disabled={portraitUploading || generating || saving}
                      onClick={() => void removePortrait()}
                      className="w-fit text-[12px] font-semibold text-red-600 hover:underline disabled:opacity-40"
                    >
                      Remove portrait
                    </button>
                  </ToolTip>
                )}
                <p className="text-[11.5px] text-ink-muted">
                  Reference image for cast cards and editing. PNG, JPEG, WebP, or GIF up to 20 MB.
                </p>
              </div>
            </div>
          </Field>
        </section>
        <section className="mb-5 rounded-xl border border-amber/30 bg-amber/5 p-4">
          <Field label="AI prompt">
            <textarea
              className={`${fieldClass} min-h-[88px] font-[family-name:var(--font-prose)] leading-relaxed`}
              rows={4}
              placeholder="Describe who this character is — role in the story, personality, backstory, secrets, appearance…"
              value={genPrompt}
              onChange={(e) => setGenPrompt(e.target.value)}
              disabled={generating || saving}
            />
          </Field>
          <ToolTip id="codex.generateCharacter">
            <button
              type="button"
              disabled={!genPrompt.trim() || generating || saving}
              onClick={() => void generateProps()}
              className="mt-2 rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40"
            >
              {generating ? "Generating…" : "Generate properties"}
            </button>
          </ToolTip>
          <p className="mt-2 text-[11.5px] text-ink-muted">
            Fills the fields below from your prompt. Changes autosave.
          </p>
        </section>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Full name">
            <input className={fieldClass} value={data.full_name}
                   onChange={(e) => set("full_name", e.target.value)} />
          </Field>
          <Field label="Role">
            <select className={fieldClass} value={data.role} onChange={(e) => set("role", e.target.value)}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </Field>
        </div>
        <Field label="Also known as">
          <textarea
            className={`${fieldClass} min-h-[72px]`}
            rows={3}
            placeholder={"One name per line — e.g. Nickname, Ms. Lee, Mrs Quinn"}
            value={aliasesText}
            onChange={(e) => setAliases(e.target.value)}
          />
          <p className="mt-1 text-[11.5px] text-ink-muted">
            Alternate names for imports and chapter updates to match this character.
          </p>
        </Field>
        <Field label="Relationships">
          <p className="mb-2 text-[11.5px] text-ink-muted">
            Pick a broad role for grouping/inverses, then use a subrole or custom label for display and prompts.
          </p>
          {Object.keys(relationships).length === 0 ? (
            <p className="mb-2 text-[12px] text-ink-muted">No relationships yet.</p>
          ) : (
            <ul className="mb-3 space-y-2">
              {Object.entries(relationships).map(([targetId, label]) => {
                const target = cast.find((c) => c.id === targetId);
                const parsed = parseRelationshipLabel(label);
                return (
                  <li key={targetId} className="flex flex-wrap items-center gap-2">
                    <span className="min-w-[6rem] text-[13px] font-medium text-ink-text">
                      {target?.full_name ?? targetId}
                    </span>
                    <select
                      className={`${fieldClass} max-w-[11rem] flex-1`}
                      value={parsed.role ?? ""}
                      onChange={(e) => setRelationshipParts(targetId, e.target.value, parsed.subrole)}
                      aria-label="Relationship role"
                    >
                      <option value="">Custom</option>
                      {CANONICAL_RELATIONSHIP_ROLES.map((role) => (
                        <option key={role} value={role}>{role}</option>
                      ))}
                    </select>
                    <input
                      className={`${fieldClass} max-w-[12rem] flex-1`}
                      list="rel-label-suggestions"
                      value={parsed.subrole}
                      onChange={(e) => setRelationshipParts(targetId, parsed.role ?? "", e.target.value)}
                      placeholder="subrole or custom label"
                    />
                    <ToolTip id="codex.removeCharacterRelationship">
                      <button
                        type="button"
                        onClick={() => removeRelationship(targetId)}
                        className="text-[12px] font-semibold text-red-600 hover:underline"
                      >
                        Remove
                      </button>
                    </ToolTip>
                  </li>
                );
              })}
            </ul>
          )}
          {otherCast.length > 0 && (
            <div className="flex flex-wrap items-end gap-2">
              <div className="min-w-[10rem] flex-1">
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  Character
                </label>
                <select
                  className={fieldClass}
                  value={newRelTarget}
                  onChange={(e) => setNewRelTarget(e.target.value)}
                >
                  <option value="">Select…</option>
                  {otherCast
                    .filter((c) => !(c.id in relationships))
                    .map((c) => (
                      <option key={c.id} value={c.id}>{c.full_name}</option>
                    ))}
                </select>
              </div>
              <div className="min-w-[10rem] flex-1">
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  Role
                </label>
                <select
                  className={fieldClass}
                  value={newRelRole}
                  onChange={(e) => setNewRelRole(e.target.value)}
                >
                  <option value="">Custom</option>
                  {CANONICAL_RELATIONSHIP_ROLES.map((role) => (
                    <option key={role} value={role}>{role}</option>
                  ))}
                </select>
              </div>
              <div className="min-w-[10rem] flex-1">
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  Subrole / label
                </label>
                <input
                  className={fieldClass}
                  list="rel-label-suggestions"
                  value={newRelLabel}
                  onChange={(e) => setNewRelLabel(e.target.value)}
                  placeholder="e.g. mother, boss, custom label"
                />
                <datalist id="rel-label-suggestions">
                  {relSuggestions.map((s) => <option key={s} value={s} />)}
                </datalist>
              </div>
              <ToolTip id="graph.addRelationship">
                <button
                  type="button"
                  disabled={!newRelTarget || (!newRelRole && !newRelLabel.trim())}
                  onClick={addRelationship}
                  className="rounded-lg border border-paper-line px-3 py-2 text-[12.5px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40"
                >
                  Add
                </button>
              </ToolTip>
            </div>
          )}
        </Field>
        {([
          ["internal_desire", "Internal desire"],
          ["external_goal", "External goal"],
          ["fear", "Fear"],
          ["weakness", "Weakness"],
          ["strength", "Strength"],
          ["secret", "Secret"],
          ["physical_description", "Physical description"],
          ["current_location", "Current location"],
          ["emotional_state", "Emotional state"],
          ["notes", "Notes"],
        ] as const).map(([key, label]) => (
          <Field key={key} label={label}>
            <textarea className={`${fieldClass} min-h-[60px]`} rows={key === "notes" ? 4 : 2}
                      value={data[key]} onChange={(e) => set(key, e.target.value)} />
          </Field>
        ))}
        <div className="mt-6 flex justify-end">
          <ToolTip id="global.modalClose">
            <button type="button" onClick={() => void handleClose()} disabled={generating || saving}
                    className="rounded-lg px-4 py-2 text-[13.5px] font-semibold text-ink-muted hover:bg-ink/5 disabled:opacity-40">
              Close
            </button>
          </ToolTip>
        </div>
      </div>
    </Modal>
  );
}

export function PlotThreadModal({
  projectId, thread, open, onClose, onSaved,
}: {
  projectId: string; thread: PlotThreadSummary | null; open: boolean;
  onClose: () => void; onSaved: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [threadType, setThreadType] = useState("main");
  const [priority, setPriority] = useState(3);
  const [status, setStatus] = useState("active");
  const [subplotsText, setSubplotsText] = useState("");
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<string | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const loadedSnapshot = useRef("");
  const isEdit = thread != null;

  useEffect(() => {
    if (open) {
      setName(thread?.name ?? "");
      setDescription(thread?.description ?? "");
      setThreadType(thread?.thread_type ?? "main");
      setPriority(thread?.priority ?? 3);
      setStatus(thread?.status ?? "active");
      setSubplotsText((thread?.subplots ?? []).join("\n"));
      loadedSnapshot.current = JSON.stringify({
        name: thread?.name ?? "",
        description: thread?.description ?? "",
        thread_type: thread?.thread_type ?? "main",
        priority: thread?.priority ?? 3,
        status: thread?.status ?? "active",
        subplots: thread?.subplots ?? [],
      });
      setDirty(false);
    }
  }, [open, thread]);

  const currentPayload = useCallback(() => ({
    name: name.trim(),
    description,
    thread_type: threadType,
    priority,
    status,
    subplots: subplotsText.split("\n").map((s) => s.trim()).filter(Boolean),
  }), [name, description, threadType, priority, status, subplotsText]);

  const persistEdit = useCallback(async (opts?: { silent?: boolean }) => {
    if (!thread || !name.trim()) return;
    const payload = currentPayload();
    const snap = JSON.stringify(payload);
    if (snap === loadedSnapshot.current) {
      setDirty(false);
      return;
    }
    setSaving(true);
    try {
      await api.updatePlotThread(projectId, thread.id, payload);
      loadedSnapshot.current = snap;
      setDirty(false);
      setLastSaved(formatSavedAt());
      onSaved();
      if (!opts?.silent) toast("Plot thread updated", "success");
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setSaving(false);
    }
  }, [thread, name, currentPayload, projectId, onSaved, toast]);

  function queueSave() {
    if (!isEdit) return;
    setDirty(true);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      void persistEdit({ silent: true });
    }, 700);
  }

  function patch(field: "name" | "description" | "subplotsText", value: string) {
    if (field === "name") setName(value);
    else if (field === "description") setDescription(value);
    else setSubplotsText(value);
    queueSave();
  }

  function patchSelect(field: "threadType" | "status", value: string) {
    if (field === "threadType") setThreadType(value);
    else setStatus(value);
    queueSave();
  }

  function patchPriority(value: number) {
    setPriority(value);
    queueSave();
  }

  async function submitCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      await api.createPlotThread(projectId, currentPayload());
      toast("Plot thread added", "success");
      onSaved();
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  async function handleClose() {
    if (saveTimer.current) {
      clearTimeout(saveTimer.current);
      saveTimer.current = null;
    }
    if (isEdit && dirty) await persistEdit({ silent: true });
    onClose();
  }

  return (
    <Modal open={open} onClose={busy || saving ? () => {} : () => void handleClose()}
           title={isEdit ? "Edit Plot Thread" : "Add Plot Thread"}>
      {isEdit && (
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <SaveStatus dirty={dirty} saving={saving} lastSaved={lastSaved} />
          <span className="text-[11px] text-ink-muted">Autosaves after you stop typing</span>
        </div>
      )}
      <form onSubmit={isEdit ? (e) => e.preventDefault() : submitCreate}>
        <Field label="Name">
          <input autoFocus className={fieldClass} value={name}
                 onChange={(e) => isEdit ? patch("name", e.target.value) : setName(e.target.value)} />
        </Field>
        <Field label="Description">
          <textarea className={`${fieldClass} min-h-[80px]`} value={description}
                    onChange={(e) => isEdit ? patch("description", e.target.value) : setDescription(e.target.value)} />
        </Field>
        <Field label="Subplots (one per line)">
          <textarea className={`${fieldClass} min-h-[72px] font-mono text-[12.5px]`} value={subplotsText}
                    onChange={(e) => isEdit ? patch("subplotsText", e.target.value) : setSubplotsText(e.target.value)}
                    placeholder="One subplot beat per line" />
        </Field>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Type">
            <select className={fieldClass} value={threadType}
                    onChange={(e) => isEdit ? patchSelect("threadType", e.target.value) : setThreadType(e.target.value)}>
              {THREAD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </Field>
          <Field label="Priority">
            <input type="number" min={1} max={5} className={fieldClass} value={priority}
                   onChange={(e) => isEdit ? patchPriority(Number(e.target.value)) : setPriority(Number(e.target.value))} />
          </Field>
          <Field label="Status">
            <select className={fieldClass} value={status}
                    onChange={(e) => isEdit ? patchSelect("status", e.target.value) : setStatus(e.target.value)}>
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </Field>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          {isEdit ? (
            <ToolTip id="global.modalClose">
              <button type="button" onClick={() => void handleClose()} disabled={saving}
                      className="rounded-lg px-4 py-2 text-[13.5px] font-semibold text-ink-muted hover:bg-ink/5 disabled:opacity-40">
                Close
              </button>
            </ToolTip>
          ) : (
            <>
              <ToolTip id="modal.cancel">
                <button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-[13.5px] font-semibold text-ink-muted hover:bg-ink/5">
                  Cancel
                </button>
              </ToolTip>
              <ToolTip id="codex.addPlotThread">
                <button type="submit" disabled={!name.trim() || busy}
                        className="rounded-lg bg-ink px-5 py-2 text-[13.5px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
                  {busy ? "Adding…" : "Add thread"}
                </button>
              </ToolTip>
            </>
          )}
        </div>
      </form>
    </Modal>
  );
}

const BIBLE_SECTIONS: {
  key: string;
  label: string;
  multiline: boolean;
  asList?: boolean;
  hint?: string;
}[] = [
  {
    key: "logline",
    label: "Logline",
    multiline: true,
    hint: "One sentence pitching the whole story — protagonist, central conflict, and stakes.",
  },
  {
    key: "themes",
    label: "Themes (one per line)",
    multiline: true,
    asList: true,
    hint: "Durable story-wide ideas the prose should keep honoring (e.g. truth vs. loyalty, grief, power).",
  },
  {
    key: "setting_summary",
    label: "Setting (one fact per line)",
    multiline: true,
    asList: true,
    hint: "Durable canon facts about where and when the story lives. Use Story Graph for arcs and landed beats for one-chapter events.",
  },
  {
    key: "historical_context",
    label: "Historical context (one per line)",
    multiline: true,
    asList: true,
    hint: "Durable real or in-world history that future chapters must respect.",
  },
  {
    key: "premise_beats",
    label: "Premise beats (one per line)",
    multiline: true,
    asList: true,
    hint: "High-level premise beats for the whole novel. Use Story Graph for detailed arc/subplot structure.",
  },
  { key: "world_rules", label: "World rules", multiline: true, hint: "Durable magic, technology, society, culture, or geography rules the prose must obey." },
  { key: "import_notes", label: "Story notes", multiline: true, hint: "Reviewed durable bible notes from imports or research. Do not use for ordinary landed chapter beats." },
];

function formatBibleValue(v: unknown): string {
  if (Array.isArray(v)) {
    return v.map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        const o = item as Record<string, string>;
        return o.note ?? o.fact ?? o.relationship ?? JSON.stringify(item);
      }
      return String(item);
    }).join("\n");
  }
  if (v && typeof v === "object") return JSON.stringify(v, null, 2);
  return typeof v === "string" ? v : "";
}

export function GenericImporterPanel({
  projectId, onExtracted,
}: {
  projectId: string;
  onExtracted?: () => void;
}) {
  const toast = useToast();
  const [blocks, setBlocks] = useState<{ label: string; summary: string; extracted_at?: string }[]>([]);
  const [bgLabel, setBgLabel] = useState("Background notes");
  const [bgText, setBgText] = useState("");
  const [extracting, setExtracting] = useState(false);

  const loadBlocks = useCallback(() => {
    api.storyBible(projectId).then((r) => {
      const raw = r.data.background_blocks;
      setBlocks(Array.isArray(raw) ? raw as typeof blocks : []);
    }).catch(() => setBlocks([]));
  }, [projectId]);

  useEffect(() => { loadBlocks(); }, [loadBlocks]);

  async function extractBackground(e: React.FormEvent) {
    e.preventDefault();
    if (!bgText.trim()) return;
    setExtracting(true);
    try {
      const job = await api.extractBackground(projectId, bgText.trim(), bgLabel.trim() || "Background notes");
      toast("Extracting cast, plot threads & story bible…", "success");
      await pollJob(job.job_id);
      toast("Generic import complete", "success");
      setBgText("");
      loadBlocks();
      onExtracted?.();
    } catch (err) {
      if (isJobCancelledError(err)) toast("Cancelled", "success");
      else toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setExtracting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="font-display text-[22px] font-semibold tracking-tight text-ink-text">
          Generic Importer
        </h2>
        <p className="mt-2 max-w-2xl text-[14px] leading-relaxed text-ink-muted">
          Paste anything that is <strong>not</strong> chapter prose — character sheets, worldbuilding,
          relationship notes, author outlines. LM Studio extracts cast, plot threads, and story bible
          fields at the story level (separate from chapter paste + extract).
        </p>
      </div>

      <section className="rounded-xl border border-amber/30 bg-amber/5 p-5">
        <form onSubmit={extractBackground}>
          <Field label="Source label">
            <input className={fieldClass} value={bgLabel} onChange={(e) => setBgLabel(e.target.value)}
                   placeholder="e.g. Character bios, World notes" disabled={extracting} />
          </Field>
          <Field label="Text to import">
            <textarea
              className={`${fieldClass} min-h-[240px] font-[family-name:var(--font-prose)] leading-relaxed`}
              value={bgText}
              onChange={(e) => setBgText(e.target.value)}
              placeholder="Paste character sheets, world rules, backstory, relationship history, premise notes…"
              disabled={extracting}
            />
          </Field>
          <ToolTip id="codex.genericImporter">
            <button type="submit" disabled={!bgText.trim() || extracting}
                    className="rounded-lg bg-ink px-5 py-2.5 text-[13.5px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
              {extracting ? "Extracting…" : "Extract to Cast, Plot & Story Bible"}
            </button>
          </ToolTip>
        </form>
        {blocks.length > 0 && (
          <div className="mt-5 border-t border-amber/20 pt-4">
            <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-ink-muted">
              Previous imports
            </p>
            <ul className="flex flex-col gap-1.5">
              {blocks.slice().reverse().map((b, i) => (
                <li key={i} className="text-[13px] text-ink-muted">
                  <span className="font-medium text-ink-text">{b.label}</span>
                  {b.summary && <> — {b.summary}</>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}

export function StoryBiblePanel({
  projectId,
  scrollToSection,
}: {
  projectId: string;
  scrollToSection?: string | null;
}) {
  const toast = useToast();
  const [data, setData] = useState<Record<string, unknown>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<string | null>(null);
  const [dedupOpen, setDedupOpen] = useState(false);
  const [bibleDedupStatus, setBibleDedupStatus] = useState({ ai_suggestions_ready: false, ai_group_count: 0 });
  const { isProjectJobRunning } = useBackgroundJob();
  const bibleScanning = isProjectJobRunning("bible-dedup", projectId);
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const dataRef = useRef(data);
  dataRef.current = data;

  const load = useCallback(() => {
    api.storyBible(projectId).then((r) => {
      setData(r.data);
      const next: Record<string, string> = {};
      for (const { key } of BIBLE_SECTIONS) {
        next[key] = formatBibleValue(r.data[key]);
      }
      setDrafts(next);
      setDirty(false);
    }).catch(() => {
      setData({});
      setDrafts({});
    });
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!scrollToSection) return;
    const el = document.getElementById(`bible-section-${scrollToSection}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [scrollToSection, data]);

  const refreshBibleDedupStatus = useCallback(() => {
    api.bibleDedupStatus(projectId).then(setBibleDedupStatus).catch(() => {
      setBibleDedupStatus({ ai_suggestions_ready: false, ai_group_count: 0 });
    });
  }, [projectId]);

  useEffect(() => { refreshBibleDedupStatus(); }, [refreshBibleDedupStatus]);

  async function saveSection(key: string, raw: string, asList: boolean) {
    setSaving(true);
    try {
      const content = asList
        ? raw.split("\n").map((l) => l.trim()).filter(Boolean)
        : raw.trim();
      const updated = await api.updateStoryBible(projectId, key, content);
      setData(updated.data);
      setLastSaved(formatSavedAt());
      setDirty(false);
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setSaving(false);
    }
  }

  function queueSave(key: string, raw: string, asList: boolean) {
    setDirty(true);
    clearTimeout(timers.current[key]);
    timers.current[key] = setTimeout(() => {
      const orig = formatBibleValue(dataRef.current[key]);
      if (raw === orig) {
        setDirty(false);
        return;
      }
      void saveSection(key, raw, asList);
    }, 700);
  }

  function onDraftChange(key: string, value: string, asList: boolean) {
    setDrafts((d) => ({ ...d, [key]: value }));
    queueSave(key, value, asList);
  }

  return (
    <div className="flex flex-col gap-8">
      <section>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h3 className="font-display text-[18px] font-semibold text-ink-text">
            Story Bible
          </h3>
          <div className="flex flex-wrap items-center gap-3">
            <SaveStatus dirty={dirty} saving={saving} lastSaved={lastSaved} />
            <span className="hidden text-[11px] text-ink-muted sm:inline">Autosaves after you stop typing</span>
            <ToolTip id="codex.storyBibleDedup">
              <button type="button" onClick={() => setDedupOpen(true)}
                      className="rounded-lg border border-amber/40 bg-amber/10 px-3 py-1.5 text-[12.5px] font-semibold text-ink-text hover:bg-amber/15">
                Deduplicate bible…
                {(bibleScanning || bibleDedupStatus.ai_suggestions_ready) && (
                  <span className="ml-1.5 rounded-full bg-amber/25 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-deep">
                    {bibleScanning ? "scanning" : `${bibleDedupStatus.ai_group_count} AI`}
                  </span>
                )}
                {bibleDedupStatus.ai_suggestions_ready && !bibleScanning && (
                  <PendingAiStar title="AI dedup results ready to review" />
                )}
              </button>
            </ToolTip>
          </div>
        </div>
        <div className="flex flex-col gap-4">
          {BIBLE_SECTIONS.map(({ key, label, multiline, asList, hint }) => {
            const listMode = asList ?? (key !== "logline" && key !== "tone");
            return (
              <ToolTip key={key} id="codex.storyBibleSection" className="block">
                <div id={`bible-section-${key}`} className="rounded-xl border border-paper-line bg-paper-card p-4">
                  <label className="mb-1 block text-[12px] font-semibold uppercase tracking-[0.1em] text-ink-muted">
                    {label}
                  </label>
                  {hint && (
                    <p className="mb-2 text-[12px] leading-relaxed text-ink-muted">{hint}</p>
                  )}
                  {multiline ? (
                    <textarea
                      className={`${fieldClass} min-h-[72px] font-[family-name:var(--font-prose)]`}
                      value={drafts[key] ?? ""}
                      onChange={(e) => onDraftChange(key, e.target.value, listMode)}
                    />
                  ) : (
                    <input
                      className={fieldClass}
                      value={drafts[key] ?? ""}
                      onChange={(e) => onDraftChange(key, e.target.value, false)}
                    />
                  )}
                </div>
              </ToolTip>
            );
          })}
        </div>
      </section>
      <StoryBibleDedupPanel
        projectId={projectId}
        open={dedupOpen}
        onClose={() => setDedupOpen(false)}
        onDone={load}
        onStatusChange={refreshBibleDedupStatus}
      />
      {!dedupOpen && bibleScanning && (
        <p className="rounded-lg border border-amber/30 bg-amber/10 px-4 py-2 text-[12.5px] text-ink-text">
          Story bible AI scan running —{" "}
          <ToolTip id="codex.storyBibleDedup" className="inline">
            <button type="button" onClick={() => setDedupOpen(true)} className="font-semibold text-amber-deep underline-offset-2 hover:underline">
              open dedupe panel
            </button>
          </ToolTip>
        </p>
      )}
    </div>
  );
}

export function QuickAddCharacterModal({
  projectId, open, onClose, onAdded,
}: {
  projectId: string; open: boolean; onClose: () => void; onAdded: (c: CharacterSummary) => void;
}) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [role, setRole] = useState("supporting");
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);

  async function generateAndAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!prompt.trim()) return;
    setBusy(true);
    try {
      const job = await api.generateCharacter(projectId, {
        prompt: prompt.trim(),
        hint_name: name.trim(),
        hint_role: role,
      });
      toast("Generating character profile…", "success");
      await pollJob(job.job_id);
      const preview = await api.getCharacterGeneratePreview(projectId);
      if (!preview?.updates || Object.keys(preview.updates).length === 0) {
        throw new Error("No character profile was generated.");
      }
      const charName = (preview.updates.full_name ?? name.trim()).trim();
      const charRole = preview.updates.role ?? role;
      if (!charName) throw new Error("Character name is required.");
      const list = await api.addCharacter(projectId, charName, charRole);
      const added = list.find((c) => c.full_name === charName) ?? list[list.length - 1];
      await api.updateCharacter(projectId, added.id, preview.updates);
      await api.discardCharacterGeneratePreview(projectId);
      onAdded(added);
      setName("");
      setPrompt("");
      toast("Character added with generated profile", "success");
      onClose();
    } catch (err) {
      if (isJobCancelledError(err)) toast("Cancelled", "success");
      else toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const list = await api.addCharacter(projectId, name, role);
      const added = list.find((c) => c.full_name === name.trim()) ?? list[list.length - 1];
      onAdded(added);
      setName("");
      onClose();
    } catch (err) {
      toast(err instanceof Error ? err.message : String(err), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Add Character">
      <form onSubmit={submit}>
        <Field label="Full name">
          <input autoFocus className={fieldClass} value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Role">
          <select className={fieldClass} value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </Field>
        <Field label="AI prompt (optional — for Generate & add)">
          <textarea
            className={`${fieldClass} min-h-[100px] font-[family-name:var(--font-prose)] leading-relaxed`}
            rows={4}
            placeholder="Describe the character — personality, goals, secrets, appearance. Name and role above are hints if provided."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={busy}
          />
        </Field>
        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <ToolTip id="modal.cancel">
            <button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-[13.5px] font-semibold text-ink-muted hover:bg-ink/5">Cancel</button>
          </ToolTip>
          <ToolTip id="codex.addCharacter">
            <button type="submit" disabled={!name.trim() || busy}
                    className="rounded-lg border border-paper-line px-5 py-2 text-[13.5px] font-semibold text-ink-text hover:bg-ink/5 disabled:opacity-40">
              {busy ? "Adding…" : "Add blank"}
            </button>
          </ToolTip>
          <ToolTip id="codex.generateCharacter">
            <button type="button" disabled={!prompt.trim() || busy}
                    onClick={(e) => void generateAndAdd(e)}
                    className="rounded-lg bg-ink px-5 py-2 text-[13.5px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40">
              {busy ? "Working…" : "Generate & add"}
            </button>
          </ToolTip>
        </div>
      </form>
    </Modal>
  );
}
