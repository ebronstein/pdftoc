"""Write headings as PDF bookmarks (outline)."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from .detect import Heading


def write_toc(doc: pymupdf.Document, headings: list[Heading], output: Path) -> None:
    """Write headings as PDF bookmarks and save to output path.

    Each TOC entry is [level, title, page_number] where page_number is 1-based.
    """
    toc = [[h.level, h.text, h.page + 1] for h in headings]
    doc.set_toc(toc)
    doc.save(str(output), garbage=4, deflate=True)
