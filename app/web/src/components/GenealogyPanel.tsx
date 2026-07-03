import { useEffect, useMemo, useState } from "react";
import { api, type CharacterDetail, type CharacterSummary } from "../api/client";
import {
  buildFamilyLinks,
  buildGenealogyForest,
  buildRelationshipEdges,
  type GenealogyNode,
} from "../lib/characterRelationships";
import MindMapViewport, { type MindMapSearchItem } from "./MindMapViewport";
import ToolTip from "./ToolTip";

function GenealogyBranch({
  node,
  onSelectCharacter,
  matchedIds,
  activeMatchId,
}: {
  node: GenealogyNode;
  onSelectCharacter: (id: string) => void;
  matchedIds: Set<string>;
  activeMatchId: string | null;
}) {
  const searchMatch = matchedIds.has(node.id);
  const activeSearchMatch = activeMatchId === node.id;

  return (
    <li className="relative pl-4">
      {node.depth > 0 && (
        <span
          className="absolute left-0 top-3 h-px w-3 bg-paper-line"
          aria-hidden
        />
      )}
      <div
        className={`rounded-lg border bg-paper-card px-3 py-2 shadow-[var(--shadow-paper)] ${
          searchMatch ? "border-amber-deep ring-2 ring-amber/30" : "border-paper-line"
        } ${activeSearchMatch ? "bg-amber/10" : ""}`}
      >
        <ToolTip id="codex.genealogyCharacter">
          <button
            type="button"
            data-mindmap-interactive
            onClick={() => onSelectCharacter(node.id)}
            className="font-display text-[14px] font-semibold text-amber-deep hover:underline"
          >
            {node.name}
          </button>
        </ToolTip>
        {node.role && (
          <span className="ml-2 text-[11px] capitalize text-ink-muted">{node.role}</span>
        )}
        {node.spouses.length > 0 && (
          <p className="mt-1 text-[12px] text-ink-muted">
            {node.spouses.map((s, i) => (
              <span key={s.id}>
                {i > 0 ? "; " : ""}
                <span className="text-ink-text">{s.label}</span>
                {" of "}
                <ToolTip id="codex.genealogyCharacter" className="inline">
                  <button
                    type="button"
                    className="font-medium text-amber-deep hover:underline"
                    onClick={() => onSelectCharacter(s.id)}
                  >
                    {s.name}
                  </button>
                </ToolTip>
              </span>
            ))}
          </p>
        )}
      </div>
      {node.children.length > 0 && (
        <ul className="ml-3 mt-2 space-y-2 border-l border-paper-line pl-3">
          {node.children.map((child) => (
            <GenealogyBranch
              key={child.id}
              node={child}
              onSelectCharacter={onSelectCharacter}
              matchedIds={matchedIds}
              activeMatchId={activeMatchId}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

export default function GenealogyPanel({
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

  const cast = useMemo(
    () => details.map((d) => ({
      id: d.id,
      full_name: d.full_name,
      role: d.role,
      relationships: d.relationships ?? {},
    })),
    [details],
  );

  const familyLinks = useMemo(() => {
    const edges = buildRelationshipEdges(cast);
    return buildFamilyLinks(edges);
  }, [cast]);

  const forest = useMemo(
    () => buildGenealogyForest(cast, familyLinks),
    [cast, familyLinks],
  );

  const familyEdgeCount = familyLinks.length;
  const searchItems = useMemo<MindMapSearchItem[]>(
    () =>
      cast.map((character) => ({
        id: character.id,
        label: character.full_name,
        detail: [
          character.role,
          ...Object.entries(character.relationships ?? {}).map(
            ([targetId, label]) => `${label} ${targetId}`,
          ),
        ].join(" "),
      })),
    [cast],
  );

  if (characters.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-10 text-center text-[13.5px] text-ink-muted">
        Add characters in the Cast tab to build a family tree.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="rounded-xl border border-paper-line bg-paper-card px-8 py-10 text-center text-[13.5px] text-ink-muted">
        Loading family relationships…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-[14px] text-red-700">
        Failed to load family data: {error}
      </div>
    );
  }

  if (familyEdgeCount === 0) {
    return (
      <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-10 text-center text-[13.5px] text-ink-muted">
        <p>No family relationship labels found.</p>
        <p className="mt-2">
          In a character editor, add labels such as{" "}
          <span className="font-medium text-ink-text">mother</span>,{" "}
          <span className="font-medium text-ink-text">son</span>, or{" "}
          <span className="font-medium text-ink-text">spouse</span> on the Relationships section.
        </p>
      </div>
    );
  }

  if (forest.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-paper-line bg-paper-card/60 px-8 py-10 text-center text-[13.5px] text-ink-muted">
        Family links exist but could not be arranged into a tree (cycles or only peer links).
        Check the Relationships graph tab for the full map.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-[13px] text-ink-muted">
        {familyEdgeCount} family link{familyEdgeCount === 1 ? "" : "s"} — parent/child links
        form branches; spouse and sibling links appear inline.
      </p>
      <MindMapViewport
        title="Genealogy Mind Map"
        searchItems={searchItems}
        searchPlaceholder="Search family members, roles, labels..."
      >
        {({ matchedIds, activeMatchId }) => (
          <ul className="w-max min-w-[720px] space-y-4 pr-8">
            {forest.map((root) => (
              <GenealogyBranch
                key={root.id}
                node={root}
                onSelectCharacter={onSelectCharacter}
                matchedIds={matchedIds}
                activeMatchId={activeMatchId}
              />
            ))}
          </ul>
        )}
      </MindMapViewport>
    </div>
  );
}
