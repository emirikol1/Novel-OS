"""Database layer — SQLite via SQLModel.

The agent engine (core/) stays file-based; this DB is the API's system-of-record.
Engine-produced files are mirrored in via `ingest_project`; human-owned content
(Final text, snapshots, comments) is written here directly. All helpers open a
short-lived session from the process-wide engine — fine for a single-process,
single-user local app.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import or_, text
from sqlmodel import Field, Session, SQLModel, create_engine, delete, select

STAGES = ("outline", "draft", "revised", "final")
ANNOTATION_STAGES = frozenset({"draft", "revised", "final", "comment"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _wc(text: str) -> int:
    return len(text.split())


# --------------------------------------------------------------------------- tables

class Project(SQLModel, table=True):
    id: str = Field(primary_key=True)
    title: str = ""
    genre: str = ""
    author: str = ""
    status: str = "in_progress"
    updated_at: str = Field(default_factory=_now)


class Chapter(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    project_id: str = Field(index=True)
    number: int = Field(index=True)
    title: str = ""
    status: str = ""
    pov: str = ""
    word_count: int = 0
    updated_at: str = Field(default_factory=_now)


class Artifact(SQLModel, table=True):
    """One row per (project, chapter, stage) holding the stage's text."""
    id: str = Field(default_factory=_new_id, primary_key=True)
    project_id: str = Field(index=True)
    chapter: int = Field(index=True)
    stage: str = Field(index=True)  # outline | draft | revised | final
    text: str = ""
    word_count: int = 0
    updated_at: str = Field(default_factory=_now)


class Snapshot(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    project_id: str = Field(index=True)
    chapter: int = Field(index=True)
    label: str = "Manual"
    source: str = "final"
    text: str = ""
    word_count: int = 0
    created_at: str = Field(default_factory=_now)


class Comment(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    project_id: str = Field(index=True)
    chapter: int = Field(index=True)
    body: str = ""
    quote: str = ""
    resolved: bool = False
    created_at: str = Field(default_factory=_now)
    stage: str = "comment"
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    paragraph_hash: str = ""


class ResearchSpark(SQLModel, table=True):
    """Pre-canon research notes — DB-only, never mirrored into story_state.json."""
    id: str = Field(default_factory=_new_id, primary_key=True)
    project_id: str = Field(index=True)
    title: str = ""
    body: str = ""
    source_url: str = ""
    tags_json: str = "[]"
    kind: str = "note"  # note | link | quote | image | idea
    attachment_ref: str = ""
    link_character_id: str = ""
    link_chapter: Optional[int] = None
    link_plot_thread_id: str = ""
    link_bible_section: str = ""
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class ProjectMap(SQLModel, table=True):
    """Author map assets — DB metadata + image file on disk under project assets/."""
    id: str = Field(default_factory=_new_id, primary_key=True)
    project_id: str = Field(index=True)
    name: str = ""
    image_filename: str = ""
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class MapPin(SQLModel, table=True):
    """Normalized-coordinate pin on a project map."""
    id: str = Field(default_factory=_new_id, primary_key=True)
    project_id: str = Field(index=True)
    map_id: str = Field(index=True)
    label: str = ""
    x: float = 0.5
    y: float = 0.5
    lore_section: str = ""
    lore_label: str = ""
    notes: str = ""
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


# --------------------------------------------------------------------------- engine

_engine = None


def paragraph_anchor_hash(text: str) -> str:
    """Stable short hash for paragraph/block anchoring (whitespace-normalized)."""
    normalized = " ".join(text.split())
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _migrate_comment_columns() -> None:
    """Add annotation columns to existing SQLite comment tables."""
    if _engine is None:
        return
    with _engine.connect() as conn:
        rows = conn.execute(text("PRAGMA table_info(comment)")).fetchall()
        if not rows:
            return
        cols = {row[1] for row in rows}
        additions = (
            ("stage", "TEXT DEFAULT 'comment'"),
            ("start_offset", "INTEGER"),
            ("end_offset", "INTEGER"),
            ("paragraph_hash", "TEXT DEFAULT ''"),
        )
        for name, col_type in additions:
            if name not in cols:
                conn.execute(text(f"ALTER TABLE comment ADD COLUMN {name} {col_type}"))
        conn.commit()


def configure(db_url: str) -> None:
    global _engine
    _engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(_engine)
    _migrate_comment_columns()


def _session() -> Session:
    if _engine is None:
        raise RuntimeError("DB not configured. Call db.configure(url) first.")
    return Session(_engine)


# --------------------------------------------------------------------------- ingest

def _stage_file(project_dir: Path, number: int, stage: str) -> Path:
    nnn = f"{number:03d}"
    out = project_dir / "outputs"
    if stage == "outline":
        return out / f"chapter_{nnn}_outline.md"
    return out / "manuscript" / f"chapter_{nnn}_{stage}.md"


def ingest_project(root: Path, project_id: str) -> None:
    """Mirror a project's filesystem state + stage files into the DB (upsert)."""
    project_dir = Path(root) / project_id
    state_file = project_dir / "outputs" / "state" / "story_state.json"
    if not state_file.exists():
        return
    data = json.loads(state_file.read_text(encoding="utf-8"))
    meta = data.get("metadata", {})
    chapters = data.get("chapters", {})

    with _session() as s:
        proj = s.get(Project, project_id)
        if proj is None:
            proj = Project(id=project_id)
        proj.title = meta.get("title", project_id)
        proj.genre = meta.get("genre", "")
        proj.author = meta.get("author", "")
        proj.status = meta.get("status", "in_progress")
        proj.updated_at = _now()
        s.add(proj)

        for key, ch in chapters.items():
            number = int(ch.get("number", key))
            row = s.exec(
                select(Chapter).where(Chapter.project_id == project_id, Chapter.number == number)
            ).first()
            if row is None:
                row = Chapter(project_id=project_id, number=number)
            row.title = ch.get("title", "") or ""
            row.status = ch.get("status", "") or ""
            row.pov = ch.get("pov_character", "") or ""
            row.word_count = int(ch.get("word_count", 0) or 0)
            row.updated_at = _now()
            s.add(row)

            for stage in STAGES:
                # Final is DB-owned: don't let an (older) file clobber a saved Final.
                f = _stage_file(project_dir, number, stage)
                if not f.exists():
                    continue
                text = f.read_text(encoding="utf-8")
                art = _get_artifact(s, project_id, number, stage)
                if stage == "final" and art is not None:
                    continue
                if art is None:
                    art = Artifact(project_id=project_id, chapter=number, stage=stage)
                art.text = text
                art.word_count = _wc(text)
                art.updated_at = _now()
                s.add(art)
        s.commit()


def _get_artifact(s: Session, project_id: str, chapter: int, stage: str) -> Optional[Artifact]:
    return s.exec(
        select(Artifact).where(
            Artifact.project_id == project_id,
            Artifact.chapter == chapter,
            Artifact.stage == stage,
        )
    ).first()


def upsert_artifact(project_id: str, chapter: int, stage: str, text: str) -> None:
    with _session() as s:
        art = _get_artifact(s, project_id, chapter, stage)
        if art is None:
            art = Artifact(project_id=project_id, chapter=chapter, stage=stage)
        art.text = text
        art.word_count = _wc(text)
        art.updated_at = _now()
        s.add(art)
        s.commit()


def delete_artifact(project_id: str, chapter: int, stage: str) -> None:
    with _session() as s:
        art = _get_artifact(s, project_id, chapter, stage)
        if art is not None:
            s.delete(art)
            s.commit()


def get_artifact_text(project_id: str, chapter: int, stage: str) -> Optional[str]:
    with _session() as s:
        art = _get_artifact(s, project_id, chapter, stage)
        return art.text if art else None


# --------------------------------------------------------------------------- snapshots

def snapshots_list(project_id: str, chapter: int) -> list[Snapshot]:
    with _session() as s:
        rows = s.exec(
            select(Snapshot)
            .where(Snapshot.project_id == project_id, Snapshot.chapter == chapter)
            .order_by(Snapshot.created_at.desc())
        ).all()
        return list(rows)


def snapshot_create(project_id: str, chapter: int, text: str, label: str, source: str) -> Snapshot:
    with _session() as s:
        snap = Snapshot(
            project_id=project_id, chapter=chapter, text=text,
            label=label, source=source, word_count=_wc(text),
        )
        s.add(snap)
        s.commit()
        s.refresh(snap)
        return snap


def snapshot_get(project_id: str, chapter: int, snap_id: str) -> Optional[Snapshot]:
    with _session() as s:
        snap = s.get(Snapshot, snap_id)
        if snap and snap.project_id == project_id and snap.chapter == chapter:
            return snap
        return None


def snapshot_delete(project_id: str, chapter: int, snap_id: str) -> bool:
    with _session() as s:
        snap = s.get(Snapshot, snap_id)
        if not snap or snap.project_id != project_id or snap.chapter != chapter:
            return False
        s.delete(snap)
        s.commit()
        return True


# --------------------------------------------------------------------------- comments

def comments_list(project_id: str, chapter: int) -> list[Comment]:
    with _session() as s:
        rows = s.exec(
            select(Comment)
            .where(Comment.project_id == project_id, Comment.chapter == chapter)
            .order_by(Comment.created_at.desc())
        ).all()
        return list(rows)


def comment_add(
    project_id: str,
    chapter: int,
    body: str,
    quote: str = "",
    *,
    stage: str = "comment",
    start_offset: int | None = None,
    end_offset: int | None = None,
    paragraph_hash: str = "",
) -> Comment:
    anchor = paragraph_hash.strip()
    if not anchor and quote.strip():
        anchor = paragraph_anchor_hash(quote)
    with _session() as s:
        c = Comment(
            project_id=project_id,
            chapter=chapter,
            body=body,
            quote=quote,
            stage=stage,
            start_offset=start_offset,
            end_offset=end_offset,
            paragraph_hash=anchor,
        )
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


def comment_update(
    project_id: str,
    chapter: int,
    cid: str,
    *,
    resolved: bool | None = None,
    body: str | None = None,
    quote: str | None = None,
    stage: str | None = None,
    start_offset: int | None = None,
    end_offset: int | None = None,
    paragraph_hash: str | None = None,
) -> Optional[Comment]:
    with _session() as s:
        c = s.get(Comment, cid)
        if not c or c.project_id != project_id or c.chapter != chapter:
            return None
        if resolved is not None:
            c.resolved = resolved
        if body is not None:
            c.body = body
        if quote is not None:
            c.quote = quote
            if paragraph_hash is None and quote.strip():
                c.paragraph_hash = paragraph_anchor_hash(quote)
        if stage is not None:
            c.stage = stage
        if start_offset is not None:
            c.start_offset = start_offset
        if end_offset is not None:
            c.end_offset = end_offset
        if paragraph_hash is not None:
            c.paragraph_hash = paragraph_hash.strip()
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


def comment_delete(project_id: str, chapter: int, cid: str) -> bool:
    with _session() as s:
        c = s.get(Comment, cid)
        if not c or c.project_id != project_id or c.chapter != chapter:
            return False
        s.delete(c)
        s.commit()
        return True


# --------------------------------------------------------------------------- research sparks (pre-canon, DB-only)

def _spark_tags_decode(tags_json: str) -> list[str]:
    try:
        raw = json.loads(tags_json or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    return [str(t).strip() for t in raw if str(t).strip()]


def _spark_tags_encode(tags: list[str]) -> str:
    cleaned = [t.strip() for t in tags if t and t.strip()]
    return json.dumps(cleaned, ensure_ascii=False)


def research_sparks_list(project_id: str) -> list[ResearchSpark]:
    with _session() as s:
        rows = s.exec(
            select(ResearchSpark)
            .where(ResearchSpark.project_id == project_id)
            .order_by(ResearchSpark.updated_at.desc())
        ).all()
        return list(rows)


def research_spark_get(project_id: str, spark_id: str) -> Optional[ResearchSpark]:
    with _session() as s:
        row = s.get(ResearchSpark, spark_id)
        if row and row.project_id == project_id:
            return row
        return None


def research_spark_create(
    project_id: str,
    *,
    title: str,
    body: str = "",
    source_url: str = "",
    tags: list[str] | None = None,
    kind: str = "note",
    attachment_ref: str = "",
    link_character_id: str = "",
    link_chapter: int | None = None,
    link_plot_thread_id: str = "",
    link_bible_section: str = "",
) -> ResearchSpark:
    with _session() as s:
        row = ResearchSpark(
            project_id=project_id,
            title=title,
            body=body,
            source_url=source_url,
            tags_json=_spark_tags_encode(tags or []),
            kind=kind,
            attachment_ref=attachment_ref,
            link_character_id=link_character_id,
            link_chapter=link_chapter,
            link_plot_thread_id=link_plot_thread_id,
            link_bible_section=link_bible_section,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


def research_spark_update(
    project_id: str,
    spark_id: str,
    *,
    title: str | None = None,
    body: str | None = None,
    source_url: str | None = None,
    tags: list[str] | None = None,
    kind: str | None = None,
    attachment_ref: str | None = None,
    link_character_id: str | None = None,
    link_chapter: int | None = None,
    link_plot_thread_id: str | None = None,
    link_bible_section: str | None = None,
) -> Optional[ResearchSpark]:
    with _session() as s:
        row = s.get(ResearchSpark, spark_id)
        if not row or row.project_id != project_id:
            return None
        if title is not None:
            row.title = title
        if body is not None:
            row.body = body
        if source_url is not None:
            row.source_url = source_url
        if tags is not None:
            row.tags_json = _spark_tags_encode(tags)
        if kind is not None:
            row.kind = kind
        if attachment_ref is not None:
            row.attachment_ref = attachment_ref
        if link_character_id is not None:
            row.link_character_id = link_character_id
        if link_chapter is not None:
            row.link_chapter = link_chapter
        if link_plot_thread_id is not None:
            row.link_plot_thread_id = link_plot_thread_id
        if link_bible_section is not None:
            row.link_bible_section = link_bible_section
        row.updated_at = _now()
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


def research_spark_delete(project_id: str, spark_id: str) -> bool:
    with _session() as s:
        row = s.get(ResearchSpark, spark_id)
        if not row or row.project_id != project_id:
            return False
        s.delete(row)
        s.commit()
        return True


# --------------------------------------------------------------------------- project maps (DB-only)

def _clamp_coord(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def project_maps_list(project_id: str) -> list[ProjectMap]:
    with _session() as s:
        rows = s.exec(
            select(ProjectMap)
            .where(ProjectMap.project_id == project_id)
            .order_by(ProjectMap.created_at.asc())
        ).all()
        return list(rows)


def project_map_get(project_id: str, map_id: str) -> Optional[ProjectMap]:
    with _session() as s:
        row = s.get(ProjectMap, map_id)
        if row and row.project_id == project_id:
            return row
        return None


def project_map_create(project_id: str, *, name: str) -> ProjectMap:
    with _session() as s:
        row = ProjectMap(project_id=project_id, name=name)
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


def project_map_update(project_id: str, map_id: str, *, name: str | None = None) -> Optional[ProjectMap]:
    with _session() as s:
        row = s.get(ProjectMap, map_id)
        if not row or row.project_id != project_id:
            return None
        if name is not None:
            row.name = name
        row.updated_at = _now()
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


def project_map_set_image(project_id: str, map_id: str, image_filename: str) -> Optional[ProjectMap]:
    with _session() as s:
        row = s.get(ProjectMap, map_id)
        if not row or row.project_id != project_id:
            return None
        row.image_filename = image_filename
        row.updated_at = _now()
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


def project_map_delete(project_id: str, map_id: str) -> bool:
    with _session() as s:
        row = s.get(ProjectMap, map_id)
        if not row or row.project_id != project_id:
            return False
        s.exec(delete(MapPin).where(MapPin.project_id == project_id, MapPin.map_id == map_id))
        s.delete(row)
        s.commit()
        return True


def map_pins_list(project_id: str, map_id: str) -> list[MapPin]:
    with _session() as s:
        rows = s.exec(
            select(MapPin)
            .where(MapPin.project_id == project_id, MapPin.map_id == map_id)
            .order_by(MapPin.created_at.asc())
        ).all()
        return list(rows)


def map_pin_get(project_id: str, map_id: str, pin_id: str) -> Optional[MapPin]:
    with _session() as s:
        row = s.get(MapPin, pin_id)
        if row and row.project_id == project_id and row.map_id == map_id:
            return row
        return None


def map_pin_create(
    project_id: str,
    map_id: str,
    *,
    label: str,
    x: float,
    y: float,
    lore_section: str = "",
    lore_label: str = "",
    notes: str = "",
) -> MapPin:
    with _session() as s:
        row = MapPin(
            project_id=project_id,
            map_id=map_id,
            label=label,
            x=_clamp_coord(x),
            y=_clamp_coord(y),
            lore_section=lore_section,
            lore_label=lore_label,
            notes=notes,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


def map_pin_update(
    project_id: str,
    map_id: str,
    pin_id: str,
    *,
    label: str | None = None,
    x: float | None = None,
    y: float | None = None,
    lore_section: str | None = None,
    lore_label: str | None = None,
    notes: str | None = None,
) -> Optional[MapPin]:
    with _session() as s:
        row = s.get(MapPin, pin_id)
        if not row or row.project_id != project_id or row.map_id != map_id:
            return None
        if label is not None:
            row.label = label
        if x is not None:
            row.x = _clamp_coord(x)
        if y is not None:
            row.y = _clamp_coord(y)
        if lore_section is not None:
            row.lore_section = lore_section
        if lore_label is not None:
            row.lore_label = lore_label
        if notes is not None:
            row.notes = notes
        row.updated_at = _now()
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


def map_pin_delete(project_id: str, map_id: str, pin_id: str) -> bool:
    with _session() as s:
        row = s.get(MapPin, pin_id)
        if not row or row.project_id != project_id or row.map_id != map_id:
            return False
        s.delete(row)
        s.commit()
        return True


def chapter_delete_all(project_id: str, number: int) -> None:
    """Remove DB rows for one chapter (artifacts, snapshots, comments, chapter row)."""
    with _session() as s:
        s.exec(delete(Artifact).where(
            Artifact.project_id == project_id, Artifact.chapter == number,
        ))
        s.exec(delete(Snapshot).where(
            Snapshot.project_id == project_id, Snapshot.chapter == number,
        ))
        s.exec(delete(Comment).where(
            Comment.project_id == project_id, Comment.chapter == number,
        ))
        s.exec(delete(Chapter).where(
            Chapter.project_id == project_id, Chapter.number == number,
        ))
        s.commit()


def chapter_merge_cleanup(project_id: str, source_num: int, keep_num: int) -> int:
    """Remap source comments, drop version snapshots, then remove source chapter/artifacts."""
    with _session() as s:
        snapshot_rows = s.exec(
            select(Snapshot).where(
                Snapshot.project_id == project_id,
                or_(Snapshot.chapter == keep_num, Snapshot.chapter == source_num),
            )
        ).all()
        removed_snapshots = len(snapshot_rows)
        for row in snapshot_rows:
            s.delete(row)

        comment_rows = s.exec(
            select(Comment).where(
                Comment.project_id == project_id, Comment.chapter == source_num,
            )
        ).all()
        for row in comment_rows:
            row.chapter = keep_num
            s.add(row)

        s.exec(delete(Artifact).where(
            Artifact.project_id == project_id, Artifact.chapter == source_num,
        ))
        s.exec(delete(Chapter).where(
            Chapter.project_id == project_id, Chapter.number == source_num,
        ))
        s.commit()
        return removed_snapshots


def _set_chapter_number(s: Session, project_id: str, from_num: int, to_num: int) -> None:
    for model in (Artifact, Snapshot, Comment):
        rows = s.exec(
            select(model).where(model.project_id == project_id, model.chapter == from_num)
        ).all()
        for row in rows:
            row.chapter = to_num
            s.add(row)
    ch_row = s.exec(
        select(Chapter).where(Chapter.project_id == project_id, Chapter.number == from_num)
    ).first()
    if ch_row is not None:
        ch_row.number = to_num
        s.add(ch_row)


def chapter_reassign(project_id: str, from_num: int, to_num: int, *, swap: bool = False) -> None:
    """Update DB rows when a chapter number changes (move or swap)."""
    with _session() as s:
        if swap:
            sentinel = -(max(from_num, to_num) + 100000)
            _set_chapter_number(s, project_id, from_num, sentinel)
            _set_chapter_number(s, project_id, to_num, from_num)
            _set_chapter_number(s, project_id, sentinel, to_num)
        else:
            _set_chapter_number(s, project_id, from_num, to_num)
        s.commit()


def project_delete(project_id: str) -> None:
    """Remove all DB rows for a project."""
    with _session() as s:
        s.exec(delete(Artifact).where(Artifact.project_id == project_id))
        s.exec(delete(Snapshot).where(Snapshot.project_id == project_id))
        s.exec(delete(Comment).where(Comment.project_id == project_id))
        s.exec(delete(MapPin).where(MapPin.project_id == project_id))
        s.exec(delete(ProjectMap).where(ProjectMap.project_id == project_id))
        s.exec(delete(ResearchSpark).where(ResearchSpark.project_id == project_id))
        s.exec(delete(Chapter).where(Chapter.project_id == project_id))
        s.exec(delete(Project).where(Project.id == project_id))
        s.commit()


def export_project_data(project_id: str) -> dict:
    """Serialize all DB rows for a project (for backup archives)."""
    empty = {
        "version": 1,
        "project_id": project_id,
        "project": None,
        "chapters": [],
        "artifacts": [],
        "snapshots": [],
        "comments": [],
        "research_sparks": [],
        "project_maps": [],
        "map_pins": [],
    }
    with _session() as s:
        proj = s.get(Project, project_id)
        if proj is None:
            return empty
        chapters = list(s.exec(select(Chapter).where(Chapter.project_id == project_id)).all())
        artifacts = list(s.exec(select(Artifact).where(Artifact.project_id == project_id)).all())
        snapshots = list(s.exec(select(Snapshot).where(Snapshot.project_id == project_id)).all())
        comments = list(s.exec(select(Comment).where(Comment.project_id == project_id)).all())
        research_sparks = list(
            s.exec(select(ResearchSpark).where(ResearchSpark.project_id == project_id)).all()
        )
        project_maps = list(
            s.exec(select(ProjectMap).where(ProjectMap.project_id == project_id)).all()
        )
        map_pins = list(s.exec(select(MapPin).where(MapPin.project_id == project_id)).all())
        return {
            "version": 1,
            "project_id": project_id,
            "project": proj.model_dump(),
            "chapters": [c.model_dump() for c in chapters],
            "artifacts": [a.model_dump() for a in artifacts],
            "snapshots": [sn.model_dump() for sn in snapshots],
            "comments": [c.model_dump() for c in comments],
            "research_sparks": [r.model_dump() for r in research_sparks],
            "project_maps": [m.model_dump() for m in project_maps],
            "map_pins": [p.model_dump() for p in map_pins],
        }


def import_project_data(
    project_id: str,
    data: dict,
    *,
    allow_id_mismatch: bool = False,
    remap_ids: bool = False,
) -> dict[str, str]:
    """Replace all DB rows for a project from a backup export.

    Returns map_id remapping when remap_ids=True (old id -> new id).
    """
    if (
        not allow_id_mismatch
        and data.get("project_id")
        and data["project_id"] != project_id
    ):
        raise ValueError(
            f"Backup belongs to project {data['project_id']!r}, not {project_id!r}"
        )
    map_id_remap: dict[str, str] = {}
    with _session() as s:
        s.exec(delete(Artifact).where(Artifact.project_id == project_id))
        s.exec(delete(Snapshot).where(Snapshot.project_id == project_id))
        s.exec(delete(Comment).where(Comment.project_id == project_id))
        s.exec(delete(MapPin).where(MapPin.project_id == project_id))
        s.exec(delete(ProjectMap).where(ProjectMap.project_id == project_id))
        s.exec(delete(ResearchSpark).where(ResearchSpark.project_id == project_id))
        s.exec(delete(Chapter).where(Chapter.project_id == project_id))
        s.exec(delete(Project).where(Project.id == project_id))

        proj_data = data.get("project")
        if proj_data:
            proj = Project(**proj_data)
            proj.id = project_id
            s.add(proj)

        for row in data.get("chapters", []):
            ch = Chapter(**row)
            if remap_ids:
                ch.id = _new_id()
            ch.project_id = project_id
            s.add(ch)
        for row in data.get("artifacts", []):
            art = Artifact(**row)
            if remap_ids:
                art.id = _new_id()
            art.project_id = project_id
            s.add(art)
        for row in data.get("snapshots", []):
            snap = Snapshot(**row)
            if remap_ids:
                snap.id = _new_id()
            snap.project_id = project_id
            s.add(snap)
        for row in data.get("comments", []):
            com = Comment(**row)
            if remap_ids:
                com.id = _new_id()
            com.project_id = project_id
            s.add(com)
        for row in data.get("research_sparks", []):
            spark = ResearchSpark(**row)
            if remap_ids:
                spark.id = _new_id()
            spark.project_id = project_id
            s.add(spark)
        for row in data.get("project_maps", []):
            pmap = ProjectMap(**row)
            old_map_id = pmap.id
            if remap_ids:
                pmap.id = _new_id()
                map_id_remap[old_map_id] = pmap.id
            pmap.project_id = project_id
            s.add(pmap)
        for row in data.get("map_pins", []):
            pin = MapPin(**row)
            if remap_ids:
                pin.id = _new_id()
                if pin.map_id in map_id_remap:
                    pin.map_id = map_id_remap[pin.map_id]
            pin.project_id = project_id
            s.add(pin)
        s.commit()
    return map_id_remap


def sync_artifacts_to_files(root: Path, project_id: str) -> None:
    """Write DB artifact text back to stage files on disk."""
    project_dir = root / project_id
    with _session() as s:
        arts = list(s.exec(select(Artifact).where(Artifact.project_id == project_id)).all())
    for art in arts:
        path = _stage_file(project_dir, art.chapter, art.stage)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(art.text, encoding="utf-8")
        os.replace(tmp, path)


def _clear_all() -> None:
    """Test helper — wipe every table."""
    with _session() as s:
        for model in (Artifact, Snapshot, Comment, MapPin, ProjectMap, ResearchSpark, Chapter, Project):
            s.exec(delete(model))
        s.commit()
