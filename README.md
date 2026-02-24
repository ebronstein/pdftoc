# pdftoc

Auto-infer a PDF's table of contents from font sizes and boldness, then write it as PDF bookmarks (outline metadata). This makes the TOC show up in Mac Preview's sidebar, Paperpile's reader, Acrobat, and any other viewer that supports PDF outlines.

Many PDFs — academic papers, textbook chapters, reports — have visually obvious headings but no bookmarks. `pdftoc` fixes that automatically.

## How it works

1. Extracts all text spans with font size, boldness, and position using PyMuPDF
2. Builds a character-count histogram to identify the body text size
3. Filters out noise (recurring headers/footers, page numbers, figure captions)
4. Identifies headings as text larger than body size (or bold at body size), clusters into levels
5. Writes standard PDF `/Outlines` bookmarks

## Installation

Requires Python 3.10+.

Clone and install:

```sh
git clone <repo-url>
uv tool install pdftoc
```

This will install `pdftoc` to `~/.local/bin/` by default and make it available globally.
Make sure `~/.local/bin/` is in your `PATH`.

## Usage

```sh
pdftoc input.pdf                  # writes input_toc.pdf
pdftoc input.pdf -o output.pdf    # explicit output path
pdftoc input.pdf --preview        # print detected TOC to stdout, don't write
pdftoc input.pdf --max-level 2    # only level 1-2 headings
pdftoc input.pdf --replace        # overwrite input file in place
pdftoc input.pdf --debug          # show font histogram + detection details
pdftoc input.pdf --edit           # edit detected TOC in $EDITOR before writing
pdftoc input.pdf --toc toc.txt    # import TOC from a text file
```

## Manual editing

When the auto-detected TOC isn't quite right, you can manually edit it. Two workflows:

**Interactive editing** — review and tweak in your editor:

```sh
pdftoc input.pdf --edit
```

This auto-detects headings, opens them in `$EDITOR` (default: `vi`), and writes bookmarks from your saved edits. Delete all lines to abort.

**File-based editing** — export, edit offline, then import:

```sh
pdftoc input.pdf --preview > toc.txt
# edit toc.txt (add, remove, reorder, re-indent headings)
pdftoc input.pdf --toc toc.txt -o output.pdf
```

The TOC format uses 2-space indentation per level with a `(p. N)` page suffix:

```
Chapter 1  (p. 1)
  Section 1.1  (p. 3)
    Subsection 1.1.1  (p. 5)
  Section 1.2  (p. 10)
Chapter 2  (p. 15)
```

## Development

```sh
# Install globally in editable mode
uv tool install -e pdftoc

# Or install locally
uv venv && uv pip install -e .

# Or with pip
pip install -e .
```
