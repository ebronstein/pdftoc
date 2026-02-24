"""Detect headings from extracted spans using font analysis."""

from __future__ import annotations

import math
import re
import sys
from collections import Counter
from dataclasses import dataclass

from .extract import Span


@dataclass
class Heading:
    text: str
    level: int  # 1-based
    page: int   # 0-indexed


def _char_count_by_size(spans: list[Span]) -> Counter:
    """Count total characters per font size."""
    counts: Counter = Counter()
    for s in spans:
        counts[s.size] += len(s.text)
    return counts


def _find_body_size(spans: list[Span]) -> float:
    """The most common font size (by character count) is body text."""
    counts = _char_count_by_size(spans)
    return counts.most_common(1)[0][0]


def _find_recurring_texts(
    spans: list[Span], total_pages: int, zone_frac: float = 0.08, threshold: float = 0.3
) -> set[str]:
    """Find text that appears in the top/bottom zone on many pages (headers/footers)."""
    if total_pages < 3:
        return set()

    page_height_cache: dict[int, float] = {}
    zone_texts: Counter = Counter()
    seen_per_page: dict[int, set[str]] = {}

    for s in spans:
        pg = s.page
        if pg not in seen_per_page:
            seen_per_page[pg] = set()

        # We need page height; approximate from bbox max y seen on that page
        if pg not in page_height_cache:
            page_height_cache[pg] = 842.0  # A4 default, updated below

        y_top = s.bbox[1]
        y_bot = s.bbox[3]
        page_h = page_height_cache[pg]
        top_zone = page_h * zone_frac
        bot_zone = page_h * (1 - zone_frac)

        if y_top < top_zone or y_bot > bot_zone:
            normalized = s.text.strip().lower()
            # Skip pure numbers (page numbers)
            if normalized and normalized not in seen_per_page[pg]:
                seen_per_page[pg].add(normalized)
                zone_texts[normalized] += 1

    min_count = max(2, int(total_pages * threshold))
    return {t for t, c in zone_texts.items() if c >= min_count}


def _is_page_number(text: str) -> bool:
    """Check if text looks like a page number."""
    stripped = text.strip()
    # Pure digits, or roman numerals, or "Page X"
    if re.fullmatch(r"\d+", stripped):
        return True
    if re.fullmatch(r"[ivxlcdm]+", stripped, re.IGNORECASE):
        return True
    if re.fullmatch(r"page\s+\d+", stripped, re.IGNORECASE):
        return True
    return False


def _is_caption(text: str) -> bool:
    """Check if text looks like a figure/table caption."""
    return bool(re.match(r"^(Figure|Fig\.|Table|Listing|Algorithm)\s+\d", text, re.IGNORECASE))


def _effective_score(size: float, bold: bool) -> float:
    """Score for ranking heading candidates."""
    return size + (2.0 if bold else 0.0)


def _cluster_levels(scores: list[float]) -> dict[float, int]:
    """Map distinct heading scores to levels 1, 2, 3, ...

    Scores are sorted descending — highest score = level 1.
    Scores within 0.5 of each other are merged into the same level.
    """
    unique = sorted(set(scores), reverse=True)
    if not unique:
        return {}

    mapping: dict[float, int] = {}
    level = 1
    mapping[unique[0]] = level
    for i in range(1, len(unique)):
        if unique[i - 1] - unique[i] > 0.5:
            level += 1
        mapping[unique[i]] = level
    return mapping


def _merge_spans_on_same_line(candidates: list[dict]) -> list[dict]:
    """Merge heading spans that are on the same page and roughly the same y-position."""
    if not candidates:
        return []

    merged: list[dict] = [candidates[0]]
    for c in candidates[1:]:
        prev = merged[-1]
        # Same page and y-centers within 2pt
        if (c["page"] == prev["page"]
                and abs((c["bbox"][1] + c["bbox"][3]) / 2
                        - (prev["bbox"][1] + prev["bbox"][3]) / 2) < 2.0):
            prev["text"] = prev["text"] + " " + c["text"]
            # Extend bbox
            prev["bbox"] = (
                min(prev["bbox"][0], c["bbox"][0]),
                min(prev["bbox"][1], c["bbox"][1]),
                max(prev["bbox"][2], c["bbox"][2]),
                max(prev["bbox"][3], c["bbox"][3]),
            )
        else:
            merged.append(c)
    return merged


def _fix_level_gaps(headings: list[Heading]) -> list[Heading]:
    """Ensure levels increment by at most 1 (no jumps from 1 to 3)."""
    if not headings:
        return headings

    fixed: list[Heading] = []
    level_stack: list[int] = []

    for h in headings:
        if not level_stack:
            fixed.append(Heading(h.text, 1, h.page))
            level_stack.append(h.level)
        else:
            # Find the correct output level
            while level_stack and level_stack[-1] >= h.level:
                level_stack.pop()
            out_level = len(level_stack) + 1
            fixed.append(Heading(h.text, out_level, h.page))
            level_stack.append(h.level)

    return fixed


def detect_headings(
    spans: list[Span],
    total_pages: int,
    max_level: int = 6,
    debug: bool = False,
) -> list[Heading]:
    """Detect headings from spans using font size analysis.

    Returns headings in document order with 1-based levels.
    """
    if not spans:
        return []

    # Step 1: Find body font size
    body_size = _find_body_size(spans)
    char_counts = _char_count_by_size(spans)

    if debug:
        print("=== Font Histogram (chars per size) ===", file=sys.stderr)
        for size, count in sorted(char_counts.items(), reverse=True):
            marker = " <-- body" if size == body_size else ""
            print(f"  {size:6.1f}pt: {count:>6d} chars{marker}", file=sys.stderr)
        print(file=sys.stderr)

    # Step 2: Find recurring header/footer text
    recurring = _find_recurring_texts(spans, total_pages)
    if debug and recurring:
        print(f"=== Filtered recurring text ({len(recurring)}) ===", file=sys.stderr)
        for t in sorted(recurring):
            print(f"  \"{t}\"", file=sys.stderr)
        print(file=sys.stderr)

    # Step 3: Identify heading candidates
    candidates: list[dict] = []
    for s in spans:
        # Skip noise
        if s.text.strip().lower() in recurring:
            continue
        if _is_page_number(s.text):
            continue
        if _is_caption(s.text):
            continue

        # Heading criteria: larger than body, OR bold at body size
        score = _effective_score(s.size, s.bold)
        body_score = _effective_score(body_size, False)

        if score <= body_score:
            continue

        # Skip very short text (likely noise) unless it looks like a section number
        if len(s.text.strip()) < 2 and not re.match(r"^\d", s.text.strip()):
            continue

        candidates.append({
            "text": s.text.strip(),
            "size": s.size,
            "bold": s.bold,
            "score": score,
            "bbox": s.bbox,
            "page": s.page,
        })

    # Step 4: Merge spans on same line
    candidates = _merge_spans_on_same_line(candidates)

    if not candidates:
        return []

    # Step 5: Cluster scores into levels
    scores = [c["score"] for c in candidates]
    score_to_level = _cluster_levels(scores)

    if debug:
        print("=== Score → Level mapping ===", file=sys.stderr)
        for sc in sorted(score_to_level, reverse=True):
            print(f"  score {sc:.1f} → level {score_to_level[sc]}", file=sys.stderr)
        print(file=sys.stderr)

    # Step 6: Build headings
    headings: list[Heading] = []
    for c in candidates:
        level = score_to_level[c["score"]]
        if level > max_level:
            continue
        headings.append(Heading(
            text=c["text"],
            level=level,
            page=c["page"],
        ))

    # Step 7: Fix level gaps
    headings = _fix_level_gaps(headings)

    # Reapply max_level after fixing
    headings = [h for h in headings if h.level <= max_level]

    if debug:
        print(f"=== Detected {len(headings)} headings ===", file=sys.stderr)
        for h in headings:
            indent = "  " * (h.level - 1)
            print(f"  {indent}L{h.level}: \"{h.text}\" (p.{h.page + 1})", file=sys.stderr)
        print(file=sys.stderr)

    return headings
