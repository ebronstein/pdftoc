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
