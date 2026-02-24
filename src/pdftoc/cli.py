"""CLI entry point for pdftoc."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pymupdf

from .detect import detect_headings, Heading
from .extract import extract_spans
from .writer import write_toc


def format_toc(headings: list[Heading]) -> str:
    """Format headings as human-readable/editable text.

    Each line has 2-space indentation per level and a (p. N) suffix (1-indexed).
    """
    lines: list[str] = []
    for h in headings:
        indent = "  " * (h.level - 1)
        lines.append(f"{indent}{h.text}  (p. {h.page + 1})")
    return "\n".join(lines) + "\n"


def parse_toc(text: str) -> list[Heading]:
    """Parse a TOC text file back into a list of Heading objects.

    Inverse of format_toc. Expected format per line:
      <indentation><title>  (p. <page>)
    where indentation is multiples of 2 spaces.
    """
    pattern = re.compile(r"^( *)(.*?)\s{2,}\(p\.\s*(\d+)\)\s*$")
    headings: list[Heading] = []

    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        m = pattern.match(line)
        if not m:
            print(f"Error: malformed TOC line {lineno}: {line!r}", file=sys.stderr)
            sys.exit(1)
        spaces = len(m.group(1))
        if spaces % 2 != 0:
            print(
                f"Error: odd indentation ({spaces} spaces) on line {lineno}: {line!r}",
                file=sys.stderr,
            )
            sys.exit(1)
        level = spaces // 2 + 1
        title = m.group(2).strip()
        page = int(m.group(3)) - 1  # convert to 0-indexed
        headings.append(Heading(text=title, level=level, page=page))

    return headings


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
    parser.add_argument(
        "--edit", action="store_true",
        help="Open auto-detected TOC in $EDITOR for manual editing before writing",
    )
    parser.add_argument(
        "--toc", type=Path, default=None, metavar="FILE",
        help="Import TOC from a text file instead of auto-detecting",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Validate mutually exclusive flags
    if args.edit and args.toc:
        print("Error: --edit and --toc are mutually exclusive", file=sys.stderr)
        sys.exit(1)
    if args.preview and (args.edit or args.toc):
        flag = "--edit" if args.edit else "--toc"
        print(f"Error: --preview and {flag} are mutually exclusive", file=sys.stderr)
        sys.exit(1)

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

    # Get headings
    if args.toc:
        if not args.toc.exists():
            print(f"Error: TOC file not found: {args.toc}", file=sys.stderr)
            doc.close()
            sys.exit(1)
        headings = parse_toc(args.toc.read_text())
        if not headings:
            print("Error: TOC file is empty or contains no headings", file=sys.stderr)
            doc.close()
            sys.exit(1)
    else:
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
        print(format_toc(headings), end="")
        doc.close()
        sys.exit(0)

    # Edit mode: open in $EDITOR
    if args.edit:
        editor = os.environ.get("EDITOR", "vi")
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", prefix="pdftoc_", delete=False,
        )
        try:
            tmp.write(format_toc(headings))
            tmp.close()
            try:
                result = subprocess.run([editor, tmp.name])
            except FileNotFoundError:
                print(f"Error: editor not found: {editor}", file=sys.stderr)
                os.unlink(tmp.name)
                doc.close()
                sys.exit(1)
            if result.returncode != 0:
                print(f"Error: editor exited with code {result.returncode}", file=sys.stderr)
                os.unlink(tmp.name)
                doc.close()
                sys.exit(1)
            edited_text = Path(tmp.name).read_text()
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

        headings = parse_toc(edited_text)
        if not headings:
            print("No headings after editing. Aborted.", file=sys.stderr)
            doc.close()
            sys.exit(0)

    # Validate page numbers
    num_pages = len(doc)
    for h in headings:
        if h.page < 0 or h.page >= num_pages:
            print(
                f"Error: page {h.page + 1} out of range (document has {num_pages} pages): "
                f"{h.text!r}",
                file=sys.stderr,
            )
            doc.close()
            sys.exit(1)

    # Write bookmarks
    write_toc(doc, headings, output_path)
    doc.close()
    print(f"Wrote {len(headings)} bookmarks → {output_path}")
