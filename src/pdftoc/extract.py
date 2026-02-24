"""Extract text spans with font metadata from a PDF."""

from __future__ import annotations

from dataclasses import dataclass

import pymupdf


@dataclass
class Span:
    text: str
    size: float
    bold: bool
    font: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1
    page: int  # 0-indexed


def extract_spans(doc: pymupdf.Document) -> list[Span]:
    """Return every text span in document order with font metadata."""
    spans: list[Span] = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)["blocks"]
        for block in blocks:
            if block["type"] != 0:  # text block
                continue
            for line in block["lines"]:
                for s in line["spans"]:
                    text = s["text"].strip()
                    if not text:
                        continue
                    bold = bool(s["flags"] & (1 << 4))
                    spans.append(Span(
                        text=text,
                        size=round(s["size"], 2),
                        bold=bold,
                        font=s["font"],
                        bbox=tuple(s["bbox"]),
                        page=page_num,
                    ))
    return spans
