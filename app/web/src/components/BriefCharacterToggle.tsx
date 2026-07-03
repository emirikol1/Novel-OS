import type { CharacterSummary } from "../api/client";
import {
  characterPresence,
  cycleCharacterPresence,
  type ChapterBriefDraft,
  type CharacterBriefPresence,
} from "../lib/chapterBrief";
import ToolTip from "./ToolTip";

type BriefCharacterToggleProps = {
  characters: CharacterSummary[];
  draft: ChapterBriefDraft;
  onChange: (draft: ChapterBriefDraft) => void;
};

const PRESENCE_LABEL: Record<CharacterBriefPresence, string> = {
  none: "not in chapter",
  mentioned: "mentioned",
  active: "active",
};

function chipClass(presence: CharacterBriefPresence): string {
  if (presence === "active") {
    return "border-amber-deep bg-amber/10 text-ink-text";
  }
  if (presence === "mentioned") {
    return "border-ink/20 bg-ink/[0.04] text-ink-text";
  }
  return "border-paper-line text-ink-muted";
}

export default function BriefCharacterToggle({
  characters,
  draft,
  onChange,
}: BriefCharacterToggleProps) {
  function handleCycle(characterId: string) {
    let next = cycleCharacterPresence(draft, characterId);
    if (draft.pov_character_id === characterId && !next.active_character_ids.includes(characterId)) {
      next = { ...next, pov_character_id: "" };
    }
    onChange(next);
  }

  return (
    <div className="space-y-2" data-testid="brief-character-toggle">
      <p className="text-[11px] text-ink-muted">
        Click to cycle: none → mentioned → active → none
      </p>
      <div className="flex flex-wrap gap-2">
        {characters.map((character) => {
          const presence = characterPresence(draft, character.id);
          return (
            <ToolTip key={character.id} id="chapter.briefCharacterToggle">
              <button
                type="button"
                data-testid={`brief-character-toggle-${character.id}`}
                aria-pressed={presence !== "none"}
                aria-label={`${character.full_name}: ${PRESENCE_LABEL[presence]}`}
                onClick={() => handleCycle(character.id)}
                className={`rounded-lg border px-2.5 py-1 text-[12px] font-medium transition-colors hover:opacity-90 ${chipClass(presence)}`}
              >
                {character.full_name}
              </button>
            </ToolTip>
          );
        })}
      </div>
    </div>
  );
}
