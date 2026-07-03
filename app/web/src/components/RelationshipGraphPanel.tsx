import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { api, type CharacterDetail, type CharacterSummary } from "../api/client";
import {
  CANONICAL_RELATIONSHIP_ROLES,
  RELATIONSHIP_SUBROLE_SUGGESTIONS,
  buildRelationshipEdges,
  stringifyRelationshipLabel,
} from "../lib/characterRelationships";
import Modal, { Field, fieldClass } from "./Modal";
import ToolTip from "./ToolTip";
import { useToast } from "./Toaster";

const RelationshipGraphWorkbench = lazy(() => import("./RelationshipGraphWorkbench"));

function RelationshipLinkModal({
  projectId,
  draft,
  open,
  onClose,
  onSaved,
  nameById,
}: {
  projectId: string;
  draft: { sourceId: string; targetId: string } | null;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  nameById: Map<string, string>;
}) {
  const toast = useToast();
  const [role, setRole] = useState("");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setRole("");
      setLabel("");
    }
  }, [open, draft?.sourceId, draft?.targetId]);

  async function save() {
    if (!draft || (!role && !label.trim())) return;
    setBusy(true);
    try {
      const source = await api.character(projectId, draft.sourceId);
      const relationshipLabel = role
        ? stringifyRelationshipLabel(role, label.trim() || role)
        : label.trim();
      const relationships = {
        ...(source.relationships ?? {}),
        [draft.targetId]: relationshipLabel,
      };
      await api.updateCharacter(projectId, draft.sourceId, {
        ...source,
        relationships,
      });
      toast("Relationship added", "success");
      onSaved();
    } catch (e) {
      toast(String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  if (!draft) return null;
  const src = nameById.get(draft.sourceId) ?? draft.sourceId;
  const tgt = nameById.get(draft.targetId) ?? draft.targetId;

  return (
    <Modal open={open} onClose={onClose} title="Add relationship">
      <p className="mb-4 text-[13px] text-ink-muted">
        From <span className="font-semibold text-ink-text">{src}</span> to{" "}
        <span className="font-semibold text-ink-text">{tgt}</span>
      </p>
      <div className="space-y-4">
        <Field label="Relationship role">
          <select
            className={fieldClass}
            value={role}
            onChange={(e) => setRole(e.target.value)}
            autoFocus
          >
            <option value="">Custom</option>
            {CANONICAL_RELATIONSHIP_ROLES.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
        </Field>
        <Field label="Subrole / custom label">
          <input
            className={fieldClass}
            list="rel-link-suggestions"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. mother, boss, custom label"
          />
          <datalist id="rel-link-suggestions">
            {RELATIONSHIP_SUBROLE_SUGGESTIONS.map((s) => <option key={s} value={s} />)}
          </datalist>
          <p className="mt-1 text-[11.5px] text-ink-muted">
            Role drives grouping and inverse defaults. Subrole/custom label is what displays.
          </p>
        </Field>
        <div className="flex justify-end gap-2">
          <ToolTip id="modal.cancel">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-paper-line px-4 py-2 text-[13px] font-semibold text-ink-text hover:bg-ink/5"
            >
              Cancel
            </button>
          </ToolTip>
          <ToolTip id="graph.addRelationship">
            <button
              type="button"
              onClick={() => void save()}
              disabled={busy || (!role && !label.trim())}
              className="rounded-lg bg-ink px-4 py-2 text-[13px] font-semibold text-on-ink hover:bg-ink-800 disabled:opacity-40"
            >
              {busy ? "Saving…" : "Add relationship"}
            </button>
          </ToolTip>
        </div>
      </div>
    </Modal>
  );
}

export default function RelationshipGraphPanel({
  projectId,
  characters,
  onSelectCharacter,
}: {
  projectId: string;
  characters: CharacterSummary[];
  onSelectCharacter: (id: string) => void;
}) {
  const [details, setDetails] = useState<CharacterDetail[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [linkMode, setLinkMode] = useState(false);
  const [linkSource, setLinkSource] = useState<string | null>(null);
  const [linkModal, setLinkModal] = useState<{ sourceId: string; targetId: string } | null>(null);

  const load = useCallback(() => {
    if (characters.length === 0) {
      setDetails([]);
      return;
    }
    setLoading(true);
    setError(null);
    Promise.all(characters.map((c) => api.character(projectId, c.id)))
      .then((rows) => setDetails(rows))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [projectId, characters]);

  useEffect(() => {
    if (characters.length === 0) {
      setDetails([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all(characters.map((c) => api.character(projectId, c.id)))
      .then((rows) => {
        if (!cancelled) setDetails(rows);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [projectId, characters]);

  const edges = useMemo(
    () => buildRelationshipEdges(details.map((d) => ({
      id: d.id,
      full_name: d.full_name,
      role: d.role,
      relationships: d.relationships ?? {},
    }))),
    [details],
  );

  const nameById = useMemo(() => {
    const m = new Map<string, string>();
    for (const c of characters) m.set(c.id, c.full_name);
    return m;
  }, [characters]);

  function handleNodeClick(id: string) {
    if (linkMode) {
      if (!linkSource) {
        setLinkSource(id);
        setSelectedId(id);
        return;
      }
      if (linkSource === id) {
        setLinkSource(null);
        return;
      }
      setLinkModal({ sourceId: linkSource, targetId: id });
      setLinkMode(false);
      setLinkSource(null);
      return;
    }
    setSelectedId(id);
    onSelectCharacter(id);
  }

  if (characters.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-10 text-center text-[13.5px] text-ink-muted">
        Add characters in the Cast tab to map relationships.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-paper-line bg-paper-card px-8 py-10 text-center text-[13.5px] text-ink-muted">
        Loading relationship data…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-[14px] text-red-700">
        Failed to load relationships: {error}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[13px] text-ink-muted">
          {edges.length} link{edges.length === 1 ? "" : "s"} across {characters.length} character
          {characters.length === 1 ? "" : "s"}. Drag nodes to arrange; click to inspect or edit.
        </p>
        <ToolTip id="graph.linkCharacters">
          <button
            type="button"
            onClick={() => {
              setLinkMode((m) => !m);
              setLinkSource(null);
            }}
            className={`rounded-lg border px-3.5 py-1.5 text-[12.5px] font-semibold transition-colors ${
              linkMode
                ? "border-amber-deep bg-amber/10 text-amber-deep"
                : "border-paper-line text-ink-text hover:bg-ink/5"
            }`}
          >
            {linkMode ? (linkSource ? "Pick target…" : "Pick source…") : "Link characters"}
          </button>
        </ToolTip>
      </div>

      <Suspense
        fallback={
          <div className="rounded-xl border border-paper-line bg-paper-card px-8 py-10 text-center text-[13.5px] text-ink-muted">
            Loading relationship map…
          </div>
        }
      >
        <RelationshipGraphWorkbench
          projectId={projectId}
          characters={characters}
          edges={edges}
          selectedId={selectedId}
          linkSourceId={linkSource}
          onSelectCharacter={setSelectedId}
          onNodeClick={handleNodeClick}
          onEditCharacter={onSelectCharacter}
        />
      </Suspense>

      <RelationshipLinkModal
        projectId={projectId}
        draft={linkModal}
        open={linkModal != null}
        onClose={() => setLinkModal(null)}
        onSaved={() => {
          setLinkModal(null);
          load();
        }}
        nameById={nameById}
      />
    </div>
  );
}
