"""Relationship role/subrole helpers for legacy string storage."""

from __future__ import annotations

import re
from dataclasses import dataclass


CANONICAL_RELATIONSHIP_ROLES: tuple[str, ...] = (
    "parent",
    "child",
    "sibling",
    "lover",
    "spouse",
    "ex",
    "friend",
    "ally",
    "rival",
    "enemy",
    "teacher",
    "student",
    "caretaker",
    "dependent",
    "employer",
    "employee",
    "household master",
    "servant",
    "provider",
    "client",
    "commander",
    "subordinate",
    "captor",
    "prisoner",
    "dominant",
    "submissive",
)

_ROLE_INVERSES: dict[str, str] = {
    "parent": "child",
    "child": "parent",
    "sibling": "sibling",
    "lover": "lover",
    "spouse": "spouse",
    "ex": "ex",
    "friend": "friend",
    "ally": "ally",
    "rival": "rival",
    "enemy": "enemy",
    "teacher": "student",
    "student": "teacher",
    "caretaker": "dependent",
    "dependent": "caretaker",
    "employer": "employee",
    "employee": "employer",
    "household master": "servant",
    "servant": "household master",
    "provider": "client",
    "client": "provider",
    "commander": "subordinate",
    "subordinate": "commander",
    "captor": "prisoner",
    "prisoner": "captor",
    "dominant": "submissive",
    "submissive": "dominant",
}

_ALIASES: dict[str, str] = {
    "mother": "parent",
    "father": "parent",
    "mom": "parent",
    "dad": "parent",
    "mum": "parent",
    "ma": "parent",
    "pa": "parent",
    "son": "child",
    "daughter": "child",
    "kid": "child",
    "brother": "sibling",
    "sister": "sibling",
    "twin": "sibling",
    "husband": "spouse",
    "wife": "spouse",
    "ex spouse": "ex",
    "ex-spouse": "ex",
    "ex lover": "ex",
    "ex-lover": "ex",
    "best friend": "friend",
    "teammate": "ally",
    "accomplice": "ally",
    "nemesis": "enemy",
    "adversary": "rival",
    "mentor": "teacher",
    "apprentice": "student",
    "guardian": "caretaker",
    "ward": "dependent",
    "boss": "employer",
    "manager": "employer",
    "worker": "employee",
    "staff": "employee",
    "master of house": "household master",
    "domestic servant": "servant",
    "service provider": "provider",
    "doctor": "provider",
    "lawyer": "provider",
    "therapist": "provider",
    "patient": "client",
    "officer": "commander",
    "ruler": "commander",
    "soldier": "subordinate",
    "subject": "subordinate",
    "jailer": "captor",
    "blackmailer": "captor",
    "hostage": "prisoner",
    "victim": "prisoner",
    "dom": "dominant",
    "sub": "submissive",
}

_CANONICAL_BY_KEY = {re.sub(r"[^a-z0-9]+", " ", role).strip(): role for role in CANONICAL_RELATIONSHIP_ROLES}
_AMBIGUOUS_KEYS = {"partner", "master"}


@dataclass(frozen=True)
class RelationshipRole:
    raw: str
    role: str | None
    subrole: str
    note: str = ""

    @property
    def display_label(self) -> str:
        label = self.subrole or self.role or self.raw.strip()
        if self.note:
            return f"{label}: {self.note}"
        return label


def relationship_label_key(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (label or "").strip().lower()).strip()


def _alias_role_for_key(key: str) -> str | None:
    exact = _ALIASES.get(key)
    if exact:
        return exact
    for alias, role in _ALIASES.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", key):
            return role
    return None


def parse_relationship_label(label: str) -> RelationshipRole:
    """
    Parse legacy free text or encoded ``role(subrole): note`` storage.

    ``role`` is the canonical machine-facing value, while ``subrole`` preserves
    the author-facing label. Ambiguous labels such as ``partner`` stay custom so
    they do not create misleading reciprocal edges.
    """
    raw = (label or "").strip()
    if not raw:
        return RelationshipRole(raw="", role=None, subrole="")

    base, sep, note = raw.partition(":")
    base = base.strip()
    note = note.strip() if sep else ""

    match = re.match(r"^\s*([^()]+?)\s*\(([^()]*)\)\s*$", base)
    if match:
        role_key = relationship_label_key(match.group(1))
        role = _CANONICAL_BY_KEY.get(role_key)
        subrole = match.group(2).strip()
        if role:
            return RelationshipRole(raw=raw, role=role, subrole=subrole or role, note=note)

    key = relationship_label_key(base)
    role = _CANONICAL_BY_KEY.get(key)
    if role:
        return RelationshipRole(raw=raw, role=role, subrole=role, note=note)
    if key in _AMBIGUOUS_KEYS:
        return RelationshipRole(raw=raw, role=None, subrole=base, note=note)
    alias_role = _alias_role_for_key(key)
    if alias_role:
        return RelationshipRole(raw=raw, role=alias_role, subrole=base, note=note)
    return RelationshipRole(raw=raw, role=None, subrole=base, note=note)


def stringify_relationship_label(role: str | None, subrole: str | None = None, note: str | None = None) -> str:
    """Encode a canonical role, optional display subrole, and optional note."""
    role_key = relationship_label_key(role or "")
    canonical = _CANONICAL_BY_KEY.get(role_key)
    clean_subrole = (subrole or "").strip()
    clean_note = (note or "").strip()

    if not canonical:
        label = clean_subrole
    elif not clean_subrole or relationship_label_key(clean_subrole) == relationship_label_key(canonical):
        label = canonical
    else:
        label = f"{canonical}({clean_subrole})"

    if clean_note:
        return f"{label}: {clean_note}" if label else clean_note
    return label


def display_relationship_label(label: str) -> str:
    """Return the reader-facing label, hiding the canonical role wrapper."""
    return parse_relationship_label(label).display_label


def canonical_relationship_role(label: str) -> str:
    """Return the canonical role, or an empty string for custom/ambiguous labels."""
    return parse_relationship_label(label).role or ""


def inverse_relationship_label(label: str) -> str:
    """Return the reciprocal canonical label when the relationship is unambiguous."""
    parsed = parse_relationship_label(label)
    if not parsed.role:
        return ""
    return _ROLE_INVERSES.get(parsed.role, "")
