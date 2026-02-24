"""CLI entry point for pdftoc."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pymupdf

from .detect import detect_headings
from .extract import extract_spans
from .writer import write_toc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdftoc",
        description="Auto-infer PDF table of contents from font sizes and write as bookmarks.",
    )
    parser.add_argument("input", type=Path, help="Input PDF file")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output PDF path")
    parser.add_argument(
        "--preview", action="store_true",
        help="Print detected TOC to stdout without writing a file",
    )
    parser.add_argument(
        "--max-level", type=int, default=6,
        help="Maximum heading depth to include (default: 6)",
    )
    parser.add_argument(
        "--replace", action="store_true",
        help="Overwrite the input file instead of creating a new one",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Print font histogram and detection details to stderr",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    input_path: Path = args.input
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if args.preview:
        output_path = None
    elif args.replace:
        output_path = input_path
    elif args.output:
        output_path = args.output
    else:
        output_path = input_path.with_stem(input_path.stem + "_toc")

    doc = pymupdf.open(str(input_path))

    # Extract and detect
    spans = extract_spans(doc)
    headings = detect_headings(
        spans,
        total_pages=len(doc),
        max_level=args.max_level,
        debug=args.debug,
    )

    if not headings:
        print("No headings detected.", file=sys.stderr)
        doc.close()
        sys.exit(0)

    # Preview mode: print and exit
    if args.preview:
        for h in headings:
            indent = "  " * (h.level - 1)
            print(f"{indent}{h.text}  (p. {h.page + 1})")
        doc.close()
        sys.exit(0)

    # Write bookmarks
    write_toc(doc, headings, output_path)
    doc.close()
    print(f"Wrote {len(headings)} bookmarks → {output_path}")
