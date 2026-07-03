import { useEffect, useMemo, useState } from "react";
import {
  api,
  characterPortraitUrl,
  type CharacterDetail,
  type CharacterSummary,
} from "../api/client";

const ROLE_COLOR: Record<string, string> = {
  protagonist: "#c98a16",
  antagonist: "#8b3a3a",
  supporting: "#4a6fa5",
  minor: "#6b6560",
};

const DETAIL_FIELDS: { key: keyof CharacterDetail; label: string }[] = [
  { key: "physical_description", label: "Appearance" },
  { key: "internal_desire", label: "Internal desire" },
  { key: "external_goal", label: "External goal" },
  { key: "fear", label: "Fear" },
  { key: "weakness", label: "Weakness" },
  { key: "strength", label: "Strength" },
  { key: "secret", label: "Secret" },
  { key: "current_location", label: "Location" },
  { key: "emotional_state", label: "Emotional state" },
  { key: "notes", label: "Notes" },
];

function CharacterAvatar({
  projectId,
  character,
  size = "md",
}: {
  projectId: string;
  character: CharacterSummary;
  size?: "sm" | "md";
}) {
  const dim = size === "sm" ? "h-8 w-8 text-[12px]" : "h-10 w-10 text-[15px]";
  return (
    <span
      className={`flex ${dim} shrink-0 items-center justify-center overflow-hidden rounded-full font-display font-semibold text-on-ink`}
      style={
        character.portrait_url
          ? undefined
          : { backgroundColor: ROLE_COLOR[character.role] ?? "var(--color-ink-muted)" }
      }
    >
      {character.portrait_url ? (
        <img
          src={characterPortraitUrl(projectId, character.id)}
          alt=""
          className="h-full w-full object-cover"
        />
      ) : (
        character.full_name.charAt(0).toUpperCase()
      )}
    </span>
  );
}

function CharacterListRow({
  projectId,
  character,
  badge,
  selected,
  onSelect,
}: {
  projectId: string;
  character: CharacterSummary;
  badge?: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`flex w-full items-center gap-2.5 rounded-lg border px-2.5 py-2 text-left transition-colors ${
        selected
          ? "border-amber/40 bg-amber/10"
          : "border-paper-line bg-paper-card hover:border-amber/25 hover:bg-ink/[0.03]"
      }`}
    >
      <CharacterAvatar projectId={projectId} character={character} size="sm" />
      <span className="min-w-0 flex-1">
        <span className="block truncate font-display text-[13px] font-medium text-ink-text">
          {character.full_name}
        </span>
        <span className="block truncate text-[11px] capitalize text-ink-muted">{character.role}</span>
      </span>
      {badge && (
        <span className="shrink-0 rounded-full bg-amber/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-deep">
          {badge}
        </span>
      )}
    </button>
  );
}

function CharacterDetailView({
  projectId,
  character,
  detail,
  loading,
  nameById,
  onBack,
}: {
  projectId: string;
  character: CharacterSummary;
  detail: CharacterDetail | null;
  loading: boolean;
  nameById: Map<string, string>;
  onBack: () => void;
}) {
  const relationships = useMemo(() => {
    if (!detail?.relationships) return [];
    return Object.entries(detail.relationships).map(([targetId, label]) => ({
      targetId,
      label,
      targetName: nameById.get(targetId) ?? targetId,
    }));
  }, [detail?.relationships, nameById]);

  return (
    <div className="flex flex-col gap-3 p-4">
      <button
        type="button"
        onClick={onBack}
        className="self-start text-[12px] font-semibold text-amber-deep hover:underline"
      >
        ← Back to cast
      </button>

      <div className="flex items-start gap-3">
        <CharacterAvatar projectId={projectId} character={character} />
        <div className="min-w-0">
          <h3 className="font-display text-[17px] font-semibold leading-tight text-ink-text">
            {character.full_name}
          </h3>
          <p className="mt-0.5 text-[12px] capitalize text-ink-muted">{character.role}</p>
          {character.aliases && character.aliases.length > 0 && (
            <p className="mt-1 text-[11px] text-ink-muted">
              aka {character.aliases.join(", ")}
            </p>
          )}
        </div>
      </div>

      {loading && <p className="text-[12px] text-ink-muted">Loading…</p>}

      {!loading && detail && (
        <div className="space-y-3">
          {(detail.arc_stage || detail.arc_progress > 0) && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-muted">Arc</p>
              <p className="mt-1 text-[12.5px] text-ink-text">
                {detail.arc_stage || "—"}
                {detail.arc_progress > 0 ? ` · ${detail.arc_progress}%` : ""}
              </p>
            </div>
          )}

          {DETAIL_FIELDS.map(({ key, label }) => {
            const value = detail[key];
            if (typeof value !== "string" || !value.trim()) return null;
            return (
              <div key={key}>
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
                  {label}
                </p>
                <p className="mt-1 whitespace-pre-wrap text-[12.5px] leading-relaxed text-ink-text">
                  {value}
                </p>
              </div>
            );
          })}

          {relationships.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
                Relationships
              </p>
              <ul className="mt-1 space-y-1">
                {relationships.map((rel) => (
                  <li key={rel.targetId} className="text-[12.5px] text-ink-text">
                    <span className="font-medium">{rel.targetName}</span>
                    <span className="text-ink-muted"> — {rel.label}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {!loading && !detail && (
        <p className="text-[12px] text-ink-muted">Could not load character details.</p>
      )}
    </div>
  );
}

export default function InspectorCastPanel({
  projectId,
  chapterNumber,
  characters,
  refreshToken,
}: {
  projectId: string;
  chapterNumber: number;
  characters: CharacterSummary[];
  refreshToken?: number;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CharacterDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [filter, setFilter] = useState("");
  const [briefActiveIds, setBriefActiveIds] = useState<string[]>([]);
  const [briefMentionedIds, setBriefMentionedIds] = useState<string[]>([]);

  useEffect(() => {
    api.getChapterBrief(projectId, chapterNumber)
      .then((brief) => {
        if (!brief) {
          setBriefActiveIds([]);
          setBriefMentionedIds([]);
          return;
        }
        setBriefActiveIds(brief.active_character_ids ?? []);
        setBriefMentionedIds(brief.mentioned_character_ids ?? []);
      })
      .catch(() => {
        setBriefActiveIds([]);
        setBriefMentionedIds([]);
      });
  }, [projectId, chapterNumber, refreshToken]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setLoadingDetail(true);
    api.character(projectId, selectedId)
      .then((row) => {
        if (!cancelled) setDetail(row);
      })
      .catch(() => {
        if (!cancelled) setDetail(null);
      })
      .finally(() => {
        if (!cancelled) setLoadingDetail(false);
      });
    return () => { cancelled = true; };
  }, [projectId, selectedId]);

  const nameById = useMemo(
    () => new Map(characters.map((c) => [c.id, c.full_name])),
    [characters],
  );

  const selected = characters.find((c) => c.id === selectedId) ?? null;

  const normalizedFilter = filter.trim().toLowerCase();
  const matchesFilter = (c: CharacterSummary) => {
    if (!normalizedFilter) return true;
    const hay = [
      c.full_name,
      c.role,
      ...(c.aliases ?? []),
    ].join(" ").toLowerCase();
    return hay.includes(normalizedFilter);
  };

  const chapterCast = useMemo(() => {
    const ids = new Set([...briefActiveIds, ...briefMentionedIds]);
    return characters.filter((c) => ids.has(c.id) && matchesFilter(c));
  }, [briefActiveIds, briefMentionedIds, characters, normalizedFilter]);

  const otherCast = useMemo(() => {
    const chapterIds = new Set([...briefActiveIds, ...briefMentionedIds]);
    return characters.filter((c) => !chapterIds.has(c.id) && matchesFilter(c));
  }, [briefActiveIds, briefMentionedIds, characters, normalizedFilter]);

  const badgeFor = (id: string) => {
    if (briefActiveIds.includes(id)) return "active";
    if (briefMentionedIds.includes(id)) return "mentioned";
    return undefined;
  };

  if (characters.length === 0) {
    return (
      <div className="p-4 text-center text-[12.5px] text-ink-muted">
        No characters in the cast yet. Add them from the project codex.
      </div>
    );
  }

  if (selected) {
    return (
      <CharacterDetailView
        projectId={projectId}
        character={selected}
        detail={detail}
        loading={loadingDetail}
        nameById={nameById}
        onBack={() => setSelectedId(null)}
      />
    );
  }

  return (
    <div className="flex flex-col gap-3 p-4">
      <input
        type="search"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Search cast…"
        aria-label="Search cast"
        className="w-full rounded-lg border border-paper-line bg-paper-card px-3 py-2 text-[13px] text-ink-text placeholder:text-ink-muted"
      />

      {chapterCast.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
            In this chapter
          </p>
          <div className="space-y-1.5">
            {chapterCast.map((c) => (
              <CharacterListRow
                key={c.id}
                projectId={projectId}
                character={c}
                badge={badgeFor(c.id)}
                selected={false}
                onSelect={() => setSelectedId(c.id)}
              />
            ))}
          </div>
        </div>
      )}

      {otherCast.length > 0 && (
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-muted">
            {chapterCast.length > 0 ? "All cast" : "Cast"}
          </p>
          <div className="space-y-1.5">
            {otherCast.map((c) => (
              <CharacterListRow
                key={c.id}
                projectId={projectId}
                character={c}
                selected={false}
                onSelect={() => setSelectedId(c.id)}
              />
            ))}
          </div>
        </div>
      )}

      {chapterCast.length === 0 && otherCast.length === 0 && (
        <p className="text-center text-[12.5px] text-ink-muted">No characters match your search.</p>
      )}
    </div>
  );
}
