"""Build minimal EPUB 3 packages from chapter Final texts (stdlib only)."""

from __future__ import annotations

import html
import re
import uuid
import zipfile
from io import BytesIO

_MENTION_CHAR = re.compile(r"\[\[char:([^\]]+)\]\]")
_MENTION_LORE_SECTION = re.compile(r"\[\[lore:[^:]+:([^\]]+)\]\]")
_MENTION_LORE = re.compile(r"\[\[lore:([^\]]+)\]\]")


def strip_mentions(text: str) -> str:
    """Replace Novel OS mention markup with plain labels."""
    text = _MENTION_CHAR.sub(r"\1", text)
    text = _MENTION_LORE_SECTION.sub(r"\1", text)
    text = _MENTION_LORE.sub(r"\1", text)
    return text


def markdown_to_xhtml_body(text: str) -> str:
    """Convert simple Markdown-ish prose to an XHTML body fragment."""
    text = strip_mentions(text)
    lines = text.splitlines()
    parts: list[str] = []
    para_buf: list[str] = []

    def flush_para() -> None:
        if not para_buf:
            return
        content = html.escape("\n".join(para_buf))
        parts.append(f"<p>{content}</p>")
        para_buf.clear()

    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            flush_para()
            parts.append("<hr/>")
        elif stripped.startswith("## "):
            flush_para()
            parts.append(f"<h2>{html.escape(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            flush_para()
            parts.append(f"<h1>{html.escape(stripped[2:])}</h1>")
        elif not stripped:
            flush_para()
        else:
            para_buf.append(line)
    flush_para()
    return "\n".join(parts)


def _stylesheet(paragraph_format: str) -> str:
    """Return EPUB CSS for manuscript paragraph presentation."""
    if paragraph_format == "indented":
        return (
            "body { line-height: 1.4; }\n"
            "p { margin: 0; text-indent: 1.5em; }\n"
            "h1 + p, h2 + p, h3 + p, hr + p, p:first-of-type { text-indent: 0; }\n"
            "hr { border: 0; margin: 1.5em 0; text-align: center; }\n"
            "hr::before { content: '* * *'; }\n"
        )
    return (
        "body { line-height: 1.4; }\n"
        "p { margin: 0 0 1em; text-indent: 0; }\n"
        "hr { border: 0; margin: 1.5em 0; text-align: center; }\n"
        "hr::before { content: '* * *'; }\n"
    )


def _chapter_xhtml(chapter_title: str, body_html: str) -> str:
    title_esc = html.escape(chapter_title)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">\n'
        "<head>\n"
        f"  <title>{title_esc}</title>\n"
        '  <link rel="stylesheet" type="text/css" href="../style.css"/>\n'
        "</head>\n"
        "<body>\n"
        f"{body_html}\n"
        "</body>\n"
        "</html>\n"
    )


def _nav_xhtml(entries: list[tuple[str, str]]) -> str:
    """entries: (href, label)"""
    items = "\n".join(
        f'      <li><a href="{html.escape(href, quote=True)}">{html.escape(label)}</a></li>'
        for href, label in entries
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops">\n'
        '<head><title>Navigation</title><link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
        "<body>\n"
        '  <nav epub:type="toc" id="toc">\n'
        "    <ol>\n"
        f"{items}\n"
        "    </ol>\n"
        "  </nav>\n"
        "</body>\n"
        "</html>\n"
    )


def _content_opf(
    book_id: str,
    title: str,
    author: str,
    chapter_items: list[tuple[str, str]],
) -> str:
    """chapter_items: (id, href)"""
    title_esc = html.escape(title)
    author_esc = html.escape(author or "Unknown")
    manifest = [
        '    <item id="nav" href="nav.xhtml" '
        'media-type="application/xhtml+xml" properties="nav"/>',
        '    <item id="style" href="style.css" media-type="text/css"/>',
    ]
    spine: list[str] = []
    for item_id, href in chapter_items:
        manifest.append(
            f'    <item id="{item_id}" href="{href}" '
            'media-type="application/xhtml+xml"/>',
        )
        spine.append(f'    <itemref idref="{item_id}"/>')
    manifest_xml = "\n".join(manifest)
    spine_xml = "\n".join(spine)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
        f'unique-identifier="book-id">\n'
        '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'    <dc:identifier id="book-id">{book_id}</dc:identifier>\n'
        f"    <dc:title>{title_esc}</dc:title>\n"
        f"    <dc:creator>{author_esc}</dc:creator>\n"
        '    <dc:language>en</dc:language>\n'
        "  </metadata>\n"
        "  <manifest>\n"
        f"{manifest_xml}\n"
        "  </manifest>\n"
        "  <spine>\n"
        f"{spine_xml}\n"
        "  </spine>\n"
        "</package>\n"
    )


_CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def build_epub(
    title: str,
    author: str,
    chapters: list[tuple[int, str, str]],
    *,
    paragraph_format: str = "block",
) -> bytes:
    """Build EPUB bytes from (number, title, final_text) tuples."""
    if paragraph_format not in {"block", "indented"}:
        paragraph_format = "block"
    book_id = f"urn:uuid:{uuid.uuid4()}"
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zinfo = zipfile.ZipInfo("mimetype")
        zinfo.compress_type = zipfile.ZIP_STORED
        zf.writestr(zinfo, "application/epub+zip")

        zf.writestr("META-INF/container.xml", _CONTAINER_XML)
        zf.writestr("OEBPS/style.css", _stylesheet(paragraph_format))

        chapter_items: list[tuple[str, str]] = []
        nav_entries: list[tuple[str, str]] = []

        for number, ch_title, raw_text in chapters:
            item_id = f"chapter-{number:03d}"
            href = f"chapters/chapter-{number:03d}.xhtml"
            label = ch_title.strip() or f"Chapter {number}"
            body = markdown_to_xhtml_body(raw_text)
            xhtml = _chapter_xhtml(label, body)
            zf.writestr(f"OEBPS/{href}", xhtml)
            chapter_items.append((item_id, href))
            nav_entries.append((href, f"Chapter {number}: {label}"))

        zf.writestr("OEBPS/nav.xhtml", _nav_xhtml(nav_entries))
        zf.writestr(
            "OEBPS/content.opf",
            _content_opf(book_id, title, author, chapter_items),
        )

    return buf.getvalue()
