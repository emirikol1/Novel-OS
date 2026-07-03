"""Synthetic tests for relationship role/subrole parsing and storage."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from relationship_roles import (  # noqa: E402
    canonical_relationship_role,
    display_relationship_label,
    inverse_relationship_label,
    parse_relationship_label,
    stringify_relationship_label,
)


def test_parse_legacy_alias_as_canonical_role_with_subrole():
    parsed = parse_relationship_label("mentor")

    assert parsed.role == "teacher"
    assert parsed.subrole == "mentor"
    assert parsed.display_label == "mentor"
    assert canonical_relationship_role("mentor") == "teacher"


def test_parse_encoded_role_subrole_for_display():
    parsed = parse_relationship_label("parent(mother)")

    assert parsed.role == "parent"
    assert parsed.subrole == "mother"
    assert display_relationship_label("parent(mother)") == "mother"


def test_stringify_preserves_legacy_string_storage_shape():
    assert stringify_relationship_label("employer", "boss") == "employer(boss)"
    assert stringify_relationship_label("employer", "employer") == "employer"
    assert stringify_relationship_label(None, "secret informant") == "secret informant"


def test_ambiguous_labels_remain_custom():
    assert parse_relationship_label("partner").role is None
    assert parse_relationship_label("master").role is None
    assert inverse_relationship_label("partner") == ""


def test_servant_is_canonical_household_service_role():
    parsed = parse_relationship_label("servant")

    assert parsed.role == "servant"
    assert parsed.subrole == "servant"
    assert inverse_relationship_label("servant") == "household master"


def test_inverse_mapping_uses_active_canonical_roles():
    assert inverse_relationship_label("parent(mother)") == "child"
    assert inverse_relationship_label("teacher(mentor)") == "student"
    assert inverse_relationship_label("employer(boss)") == "employee"
    assert inverse_relationship_label("captor(jailer)") == "prisoner"
    assert inverse_relationship_label("dominant(dom)") == "submissive"
