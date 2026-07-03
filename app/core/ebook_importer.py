"""
Flexible ebook / manuscript importer for Novel OS.

Accepts:
  - A directory of chapter .txt files (delegates to import_pipeline.discover_chapters)
  - A single plain-text file (Project Gutenberg, OCR scans, etc.)
  - An EPUB file (stdlib zip + XML only)

Splits monolithic texts using detectable structure (Gutenberg chapters, Part/Book
headings, volume counts) or equal word-count parts as a fallback.

Use ``import_ebook()`` to parse a source and load chapters into a project via
``ImportPipeline`` (optionally skipping LLM extraction).
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree as ET

from import_pipeline import TEXT_EXTENSIONS, ChapterFile, discover_chapters


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

_WORD_PARTS = {
    1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six",
    7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
}


@dataclass
class EbookMetadata:
    title: str = ""
    author: str = ""
    language: str = ""
    source_format: str = ""  # directory | txt | epub
    source_path: str = ""
    split_strategy: str = ""
    notes: List[str] = field(default_factory=list)


@dataclass
class EbookChapter:
    number: int
    title: str
    text: str
    source_label: str = ""


@dataclass
class EbookParseResult:
    metadata: EbookMetadata
    chapters: List[EbookChapter]
    front_matter: str = ""
    back_matter: str = ""


# ---------------------------------------------------------------------------
# Regex / heuristics
# ---------------------------------------------------------------------------

_GUTENBERG_START = re.compile(
    r"^\*\*\* START OF (?:THE )?PROJECT GUTENBERG EBOOK .+ \*\*\*\s*$",
    re.I | re.M,
)
_GUTENBERG_END = re.compile(
    r"^\*\*\* END OF (?:THE )?PROJECT GUTENBERG EBOOK .+ \*\*\*\s*$",
    re.I | re.M,
)
_PG_TITLE = re.compile(r"^Title:\s*(.+)$", re.I | re.M)
_PG_AUTHOR = re.compile(r"^Author:\s*(.+)$", re.I | re.M)
_PG_LANGUAGE = re.compile(r"^Language:\s*(.+)$", re.I | re.M)

_VOLUME_COUNT = re.compile(
    r"\b(\d+|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)\s+VOLUMES?\b",
    re.I,
)
_WORD_TO_INT = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

_CHAPTER_HEADING_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("gutenberg_chapter", re.compile(r"^CHAPTER\s+[IVXLCDM]+\.?\s*$", re.M)),
    ("chapter_numbered", re.compile(r"^Chapter\s+\d+\s*$", re.M | re.I)),
    (
        "part_word",
        re.compile(
            r"^Part\s+(?:One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|\d+)\s*$",
            re.M | re.I,
        ),
    ),
    (
        "book_word",
        re.compile(
            r"^Book\s+(?:One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|\d+)\s*$",
            re.M | re.I,
        ),
    ),
    ("part_roman", re.compile(r"^PART\s+[IVXLCDM]+\s*$", re.M)),
]

_STORY_OPENERS = [
    re.compile(r"^Twas at Panthemont", re.M),
    re.compile(r"^It was a ", re.M),
    re.compile(r"^In the ", re.M),
    re.compile(r"^The [A-Z]", re.M),
]

_BACK_MATTER_MARKERS = [
    re.compile(r"^Bibliography\s*$", re.M | re.I),
    re.compile(r"^APPENDIX\s*$", re.M | re.I),
    re.compile(r"^NOTES\s*$", re.M | re.I),
    re.compile(r"^INDEX\s*$", re.M | re.I),
]

_PAGE_HEADER = re.compile(r"^\d+\s*&\s*.+$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_path(source: Path | str) -> Path:
    return Path(source).expanduser().resolve()


def _word_count(text: str) -> int:
    return len(text.split())


def _split_by_word_budget(text: str, parts: int, *, title_prefix: str = "Part") -> List[EbookChapter]:
    words = text.split()
    if not words:
        return []
    if parts <= 1:
        return [EbookChapter(1, title_prefix or "Full text", text.strip())]
    total = len(words)
    base, extra = divmod(total, parts)
    chapters: List[EbookChapter] = []
    idx = 0
    for n in range(1, parts + 1):
        size = base + (1 if n <= extra else 0)
        chunk = " ".join(words[idx: idx + size])
        idx += size
        label = _WORD_PARTS.get(n, str(n))
        chapters.append(
            EbookChapter(
                number=n,
                title=f"{title_prefix} {label}",
                text=chunk.strip(),
                source_label=f"{title_prefix.lower()}_{n}",
            )
        )
    return chapters


def _extract_gutenberg_metadata(header: str) -> Tuple[str, str, str]:
    title_m = _PG_TITLE.search(header)
    author_m = _PG_AUTHOR.search(header)
    lang_m = _PG_LANGUAGE.search(header)
    return (
        title_m.group(1).strip() if title_m else "",
        author_m.group(1).strip() if author_m else "",
        lang_m.group(1).strip() if lang_m else "",
    )


def _detect_volume_count(text: str) -> Optional[int]:
    m = _VOLUME_COUNT.search(text[:8000])
    if not m:
        return None
    token = m.group(1).lower()
    if token.isdigit():
        return int(token)
    return _WORD_TO_INT.get(token)


def _strip_page_headers(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if _PAGE_HEADER.match(line.strip()):
            continue
        lines.append(line)
    return "\n".join(lines)


def _gutenberg_body_start(after_start: str) -> int:
    """Skip PG table of contents; return offset into *after_start* where body begins."""
    pat = re.compile(r"^CHAPTER\s+[IVXLCDM]+\.\s*$", re.M)
    matches = list(pat.finditer(after_start))
    if not matches:
        return 0

    # Duplicate CHAPTER I (etc.): second occurrence is the body after inline TOC.
    first_label = matches[0].group().strip()
    duplicates = [m for m in matches if m.group().strip() == first_label]
    if len(duplicates) >= 2:
        return duplicates[1].start()

    # Otherwise use the first large gap between consecutive headings.
    if len(matches) >= 2:
        best_idx = 0
        best_gap = 0
        for i in range(len(matches) - 1):
            gap = matches[i + 1].start() - matches[i].start()
            if gap > best_gap:
                best_gap = gap
                best_idx = i
        if best_gap > 800:
            return matches[best_idx + 1].start()

    return matches[0].start()


def _find_story_start(text: str) -> int:
    start_m = _GUTENBERG_START.search(text)
    if start_m:
        after = text[start_m.end():]
        return start_m.end() + _gutenberg_body_start(after)

    for pat in _STORY_OPENERS:
        m = pat.search(text)
        if m and m.start() > 100:
            return m.start()
    return 0


def _find_story_end(text: str, *, from_index: int = 0) -> int:
    body = text[from_index:]
    end_m = _GUTENBERG_END.search(body)
    if end_m:
        return from_index + end_m.start()

    # Back matter only in the last 15% of the file.
    tail_start = from_index + int(len(body) * 0.85)
    tail = text[tail_start:]
    for pat in _BACK_MATTER_MARKERS:
        m = pat.search(tail)
        if m:
            return tail_start + m.start()
    return len(text)


def _split_on_pattern(
    text: str,
    pattern: re.Pattern[str],
    *,
    strategy_name: str,
    min_words: int,
) -> Optional[List[EbookChapter]]:
    matches = list(pattern.finditer(text))
    if len(matches) < 2:
        return None

    # If matches are too dense (likely a TOC), require spacing.
    if len(matches) > 4:
        gaps = [matches[i + 1].start() - matches[i].start() for i in range(len(matches) - 1)]
        if gaps and max(gaps) < 500:
            return None

    chapters: List[EbookChapter] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        if _word_count(chunk) < min_words:
            continue
        title = m.group(0).strip()
        chapters.append(
            EbookChapter(
                number=len(chapters) + 1,
                title=title,
                text=chunk,
                source_label=f"{strategy_name}_{len(chapters) + 1}",
            )
        )
    return chapters if len(chapters) >= 2 else None


def _guess_title_from_filename(path: Path) -> str:
    stem = path.stem.replace("_", " ").replace("-", " ")
    return stem.title()


def _guess_title_author_from_header(text: str) -> Tuple[str, str]:
    lines = [ln.strip() for ln in text.splitlines()[:120] if ln.strip()]
    title = ""
    author = ""
    for i, line in enumerate(lines):
        low = line.lower()
        if low in {"juliette", "justine"} and not title:
            title = line
        if "marquis" in low and "sade" in low:
            author = "Marquis de Sade"
        if line.startswith("translated by") and i > 0:
            pass
        if re.match(r"^Title:\s*", line, re.I):
            title = re.sub(r"^Title:\s*", "", line, flags=re.I).strip()
        if re.match(r"^Author:\s*", line, re.I):
            author = re.sub(r"^Author:\s*", "", line, flags=re.I).strip()
    return title, author


# ---------------------------------------------------------------------------
# EPUB (stdlib)
# ---------------------------------------------------------------------------

class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: List[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in ("script", "style"):
            self._skip = True
        elif tag in ("p", "br", "div", "h1", "h2", "h3", "li", "tr"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = False
        elif tag in ("p", "div", "h1", "h2", "h3", "li"):
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


def _xml_text(el: Optional[ET.Element], default: str = "") -> str:
    if el is None or el.text is None:
        return default
    return el.text.strip()


def _parse_epub(path: Path) -> EbookParseResult:
    meta = EbookMetadata(source_format="epub", source_path=str(path))
    chapters: List[EbookChapter] = []

    with zipfile.ZipFile(path) as zf:
        container_xml = zf.read("META-INF/container.xml")
        container = ET.fromstring(container_xml)
        rootfile_el = container.find(".//{*}rootfile")
        if rootfile_el is None:
            raise ValueError(f"Invalid EPUB (no rootfile): {path}")
        opf_path = rootfile_el.attrib["full-path"]
        opf_dir = Path(opf_path).parent
        opf = ET.fromstring(zf.read(opf_path))

        for el in opf.findall(".//{*}metadata/{*}title"):
            if not meta.title:
                meta.title = (el.text or "").strip()
        for el in opf.findall(".//{*}metadata/{*}creator"):
            if not meta.author:
                meta.author = (el.text or "").strip()
        for el in opf.findall(".//{*}metadata/{*}language"):
            if not meta.language:
                meta.language = (el.text or "").strip()

        manifest: dict[str, str] = {}
        for item in opf.findall(".//{*}manifest/{*}item"):
            manifest[item.attrib["id"]] = item.attrib["href"]

        spine_ids: List[str] = []
        for itemref in opf.findall(".//{*}spine/{*}itemref"):
            spine_ids.append(itemref.attrib["idref"])

        for i, item_id in enumerate(spine_ids, start=1):
            href = manifest.get(item_id)
            if not href:
                continue
            inner = str(opf_dir / href) if opf_dir != Path(".") else href
            inner = inner.replace("\\", "/")
            try:
                raw_html = zf.read(inner).decode("utf-8", errors="replace")
            except KeyError:
                meta.notes.append(f"Spine item missing: {inner}")
                continue
            text = _html_to_text(raw_html)
            if not text or _word_count(text) < 30:
                continue
            title_line = text.splitlines()[0][:80] if text.splitlines() else f"Section {i}"
            chapters.append(
                EbookChapter(
                    number=len(chapters) + 1,
                    title=title_line,
                    text=text,
                    source_label=Path(href).name,
                )
            )

    if not meta.title:
        meta.title = _guess_title_from_filename(path)
    meta.split_strategy = "epub_spine"
    if not chapters:
        raise ValueError(f"No readable spine content in EPUB: {path}")
    return EbookParseResult(metadata=meta, chapters=chapters)


# ---------------------------------------------------------------------------
# Plain text
# ---------------------------------------------------------------------------

def _parse_plain_text(
    path: Path,
    *,
    split_strategy: str = "auto",
    parts: Optional[int] = None,
    heading_pattern: Optional[str] = None,
    min_chapter_words: int = 200,
    strip_headers: bool = True,
) -> EbookParseResult:
    raw = path.read_text(encoding="utf-8", errors="replace")
    meta = EbookMetadata(source_format="txt", source_path=str(path))

    pg_title, pg_author, pg_lang = _extract_gutenberg_metadata(raw[:12000])
    guess_title, guess_author = _guess_title_author_from_header(raw[:12000])
    meta.title = pg_title or guess_title or _guess_title_from_filename(path)
    meta.author = pg_author or guess_author
    meta.language = pg_lang

    story_start = _find_story_start(raw)
    story_end = _find_story_end(raw, from_index=story_start)
    front_matter = raw[:story_start].strip()
    back_matter = raw[story_end:].strip()
    body = raw[story_start:story_end].strip()
    if strip_headers:
        body = _strip_page_headers(body)

    volume_parts = parts or _detect_volume_count(raw[:8000])
    chapters: Optional[List[EbookChapter]] = None
    strategy = split_strategy

    if strategy == "auto" or strategy == "heading":
        if heading_pattern:
            pat = re.compile(heading_pattern, re.M)
            chapters = _split_on_pattern(
                body, pat, strategy_name="custom", min_words=min_chapter_words,
            )
            if chapters:
                strategy = "custom_heading"
        if chapters is None:
            for name, pat in _CHAPTER_HEADING_PATTERNS:
                chapters = _split_on_pattern(
                    body, pat, strategy_name=name, min_words=min_chapter_words,
                )
                if chapters:
                    strategy = name
                    break

    if chapters is None and strategy in ("auto", "parts", "word_parts"):
        n_parts = volume_parts or parts
        if n_parts and n_parts > 1 and _word_count(body) >= min_chapter_words * n_parts:
            chapters = _split_by_word_budget(body, n_parts, title_prefix="Part")
            strategy = f"word_parts_{n_parts}"

    if chapters is None:
        chapters = [
            EbookChapter(
                number=1,
                title=meta.title or path.stem,
                text=body,
                source_label=path.name,
            )
        ]
        strategy = "single_file"

    meta.split_strategy = strategy
    if volume_parts:
        meta.notes.append(f"Detected {volume_parts} volume(s) in front matter")
    return EbookParseResult(
        metadata=meta,
        chapters=chapters,
        front_matter=front_matter,
        back_matter=back_matter,
    )


def _parse_directory(path: Path, *, start: int = 1) -> EbookParseResult:
    files = discover_chapters(path)
    meta = EbookMetadata(
        source_format="directory",
        source_path=str(path),
        split_strategy="directory",
    )
    chapters: List[EbookChapter] = []
    for cf in files:
        text = cf.path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        title = ""
        first = text.splitlines()[0].strip() if text.splitlines() else ""
        if first and len(first) < 120:
            title = first.lstrip("#").strip()
        chapters.append(
            EbookChapter(
                number=cf.number,
                title=title or f"Chapter {cf.number}",
                text=text,
                source_label=cf.path.name,
            )
        )
    if chapters and not meta.title:
        meta.title = path.parent.name.replace("-", " ").title()
    return EbookParseResult(metadata=meta, chapters=chapters)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_ebook(
    source: Path | str,
    *,
    split_strategy: str = "auto",
    parts: Optional[int] = None,
    heading_pattern: Optional[str] = None,
    min_chapter_words: int = 200,
    strip_headers: bool = True,
    chapter_start: int = 1,
) -> EbookParseResult:
    """
    Parse an ebook source into metadata + chapter sections.

    ``split_strategy``: auto | directory | heading | parts | single
    """
    path = _normalize_path(source)
    if not path.exists():
        raise FileNotFoundError(f"Source not found: {path}")

    if path.is_dir():
        result = _parse_directory(path, start=chapter_start)
    elif path.suffix.lower() == ".epub":
        result = _parse_epub(path)
    elif path.suffix.lower() in TEXT_EXTENSIONS or path.suffix == "":
        result = _parse_plain_text(
            path,
            split_strategy=split_strategy,
            parts=parts,
            heading_pattern=heading_pattern,
            min_chapter_words=min_chapter_words,
            strip_headers=strip_headers,
        )
    else:
        raise ValueError(
            f"Unsupported source type '{path.suffix}' — use .txt, .epub, or a chapters directory"
        )

    # Renumber from chapter_start if needed.
    if chapter_start != 1:
        for i, ch in enumerate(result.chapters):
            ch.number = chapter_start + i

    return result


def import_ebook(
    source: Path | str,
    project_path: Path | str,
    *,
    title: str = "",
    genre: str = "",
    author: str = "",
    split_strategy: str = "auto",
    parts: Optional[int] = None,
    heading_pattern: Optional[str] = None,
    min_chapter_words: int = 200,
    extract: bool = True,
    dry_run: bool = False,
    from_chapter: Optional[int] = None,
    to_chapter: Optional[int] = None,
    on_progress: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Parse *source* and import all chapters into an existing Novel OS project.

    Returns a summary dict (chapters_imported, total_words, split_strategy, …).
    """
    from import_pipeline import ImportPipeline  # noqa: WPS433

    parsed = parse_ebook(
        source,
        split_strategy=split_strategy,
        parts=parts,
        heading_pattern=heading_pattern,
        min_chapter_words=min_chapter_words,
    )
    log_fn = on_progress or (lambda msg: None)

    # Apply parsed metadata to project state when fields are empty.
    pipe = ImportPipeline(str(project_path))
    if title or author or parsed.metadata.title:
        pipe.state._load_state()
        if title.strip():
            pipe.state.set_metadata("title", title.strip())
        elif parsed.metadata.title and not pipe.state.metadata.get("title"):
            pipe.state.set_metadata("title", parsed.metadata.title)
        resolved_author = author.strip() or parsed.metadata.author
        if resolved_author:
            pipe.state.set_metadata("author", resolved_author)
        if genre.strip():
            pipe.state.set_metadata("genre", genre.strip())
            pipe.state.update_story_bible("genre", genre.strip())
        pipe.state.set_metadata("import_source", str(Path(source).resolve()))
        pipe.state.set_metadata("import_split_strategy", parsed.metadata.split_strategy)
        pipe.state.save_state()

    selected = parsed.chapters
    if from_chapter is not None:
        selected = [c for c in selected if c.number >= from_chapter]
    if to_chapter is not None:
        selected = [c for c in selected if c.number <= to_chapter]
    if not selected:
        raise ValueError("No chapters in selected range")

    total_words = 0
    all_changes = 0
    for ch in selected:
        from job_control import check_job_cancelled  # noqa: WPS433

        check_job_cancelled()
        wc, changes = pipe.import_chapter_text(
            ch.number,
            ch.text,
            title=ch.title,
            source_label=ch.source_label or ch.title,
            extract=extract,
            dry_run=dry_run,
            on_progress=log_fn,
        )
        total_words += wc
        all_changes += len(changes)

    summary = {
        "chapters_imported": len(selected),
        "total_words": total_words,
        "state_updates": all_changes,
        "characters": len(pipe.state.characters),
        "plot_threads": len(pipe.state.plot_threads),
        "split_strategy": parsed.metadata.split_strategy,
        "detected_title": parsed.metadata.title,
        "detected_author": parsed.metadata.author,
    }
    log_fn(
        f"=== EBOOK IMPORT DONE: {summary['chapters_imported']} chapters, "
        f"{summary['total_words']} words, strategy={summary['split_strategy']} ==="
    )
    return summary


def prepare_chapter_files(parsed: EbookParseResult) -> List[ChapterFile]:
    """Convert parse result to ImportPipeline ChapterFile list (for dry inspection)."""
    return [
        ChapterFile(path=Path(f"<parsed:{ch.source_label or ch.number}>"), number=ch.number)
        for ch in parsed.chapters
    ]
