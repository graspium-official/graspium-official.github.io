#!/usr/bin/env python3
"""Fetch arXiv paper metadata and generate a YAML entry for papers.yml.

Usage:
    python fetch_papers.py 2410.24164
    python fetch_papers.py 2410.24164 --field manipulation --lang eng --presenter "Jane Doe"
    python fetch_papers.py 2410.24164 --id-prefix 2025 --id-seq 10

Examples:
    # Basic usage - prints YAML to stdout
    python fetch_papers.py 2301.00001

    # With optional flags
    python fetch_papers.py 2301.00001 --field vla --presenter "Alice Kim"

    # Append directly to papers.yml
    python fetch_papers.py 2301.00001 >> ../_data/papers.yml
"""

import argparse
import re
import sys
import textwrap
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

ARXIV_API_URL = "https://export.arxiv.org/api/query?id_list={arxiv_id}"

# Atom / arXiv XML namespaces
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def fetch_arxiv_metadata(arxiv_id: str) -> ET.Element:
    """Fetch and return the first <entry> element from the arXiv API."""
    url = ARXIV_API_URL.format(arxiv_id=arxiv_id)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read()
    except urllib.error.URLError as exc:
        sys.exit(f"Error: failed to reach arXiv API: {exc}")
    except urllib.error.HTTPError as exc:
        sys.exit(f"Error: arXiv API returned HTTP {exc.code}")

    root = ET.fromstring(data)
    entry = root.find("atom:entry", NS)
    if entry is None:
        sys.exit("Error: no entry found in arXiv response. Check the arXiv ID.")

    # arXiv returns an entry even for invalid IDs, but the <id> will not
    # contain the expected arxiv id – detect that case.
    entry_id = entry.findtext("atom:id", default="", namespaces=NS)
    if arxiv_id not in entry_id:
        sys.exit(
            f"Error: arXiv returned no matching paper for ID '{arxiv_id}'. "
            "Please verify the ID."
        )

    return entry


def parse_entry(entry: ET.Element, arxiv_id: str):
    """Extract relevant fields from an arXiv Atom entry."""
    title = entry.findtext("atom:title", default="", namespaces=NS)
    # Normalise whitespace (arXiv titles often contain newlines)
    title = " ".join(title.split()).strip()

    # Authors
    author_els = entry.findall("atom:author", NS)
    author_names = []
    for a in author_els:
        name = a.findtext("atom:name", default="", namespaces=NS).strip()
        if name:
            author_names.append(name)

    if len(author_names) <= 3:
        authors_str = ", ".join(author_names)
    else:
        # Abbreviate to first-initial + last-name for first 3, then "et al."
        short = []
        for name in author_names[:3]:
            parts = name.split()
            if len(parts) >= 2:
                short.append(f"{parts[0][0]}. {parts[-1]}")
            else:
                short.append(name)
        authors_str = ", ".join(short) + " et al."

    # Abstract -> tldr (first two sentences)
    abstract = entry.findtext("atom:summary", default="", namespaces=NS)
    abstract = " ".join(abstract.split()).strip()
    tldr = _first_n_sentences(abstract, 2)

    # Published date
    published = entry.findtext("atom:published", default="", namespaces=NS)
    try:
        pub_date = datetime.fromisoformat(published.replace("Z", "+00:00"))
        date_str = pub_date.strftime("%Y-%m-%d")
        year_str = pub_date.strftime("%Y")
    except (ValueError, AttributeError):
        date_str = "UNKNOWN"
        year_str = "UNKNOWN"

    return {
        "title": title,
        "authors": authors_str,
        "abstract": abstract,
        "tldr": tldr,
        "date": date_str,
        "year": year_str,
    }


def _first_n_sentences(text: str, n: int) -> str:
    """Return the first *n* sentences from *text*.

    Uses a simple regex split that handles common abbreviations reasonably well.
    """
    # Split on sentence-ending punctuation followed by a space and uppercase
    # letter, or end of string.  This is intentionally simple.
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    sentences = parts[:n]
    result = " ".join(sentences)
    # Ensure it ends with a period
    if result and not result.endswith((".", "!", "?")):
        result += "."
    return result


def _yaml_escape(value: str) -> str:
    """Wrap a string in double quotes, escaping internal double quotes."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def generate_yaml(
    arxiv_id: str,
    metadata: dict,
    *,
    field: str,
    lang: str,
    presenter: str,
    id_prefix: str | None = None,
    id_seq: int | None = None,
) -> str:
    """Return a YAML block for papers.yml."""
    year = metadata["year"]
    prefix = id_prefix if id_prefix else year
    seq = f"{id_seq:03d}" if id_seq is not None else "NNN"
    entry_id = f"{prefix}-{seq}"

    venue = f"arXiv {year}"

    lines = [
        f"- id: {_yaml_escape(entry_id)}",
        f"  title: {_yaml_escape(metadata['title'])}",
        f"  authors: {_yaml_escape(metadata['authors'])}",
        f"  venue: {_yaml_escape(venue)}",
        f"  date: {_yaml_escape(metadata['date'])}",
        f"  field: {_yaml_escape(field)}",
        f"  lang: {_yaml_escape(lang)}",
        f"  keywords: []",
        f"  presenter: {_yaml_escape(presenter)}",
        f'  status: "reviewed"',
        f"  tldr: {_yaml_escape(metadata['tldr'])}",
        f"  paper: {_yaml_escape(f'https://arxiv.org/abs/{arxiv_id}')}",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch arXiv paper metadata and generate a papers.yml YAML entry.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              %(prog)s 2410.24164
              %(prog)s 2410.24164 --field manipulation --presenter "Jane Doe"
              %(prog)s 2301.00001 --id-prefix 2025 --id-seq 5
              %(prog)s 2301.00001 >> _data/papers.yml
        """),
    )
    parser.add_argument(
        "arxiv_id",
        help='arXiv paper ID (e.g. "2410.24164" or "2301.00001v2")',
    )
    parser.add_argument(
        "--field",
        default="manipulation",
        help='Research field for the entry (default: "manipulation")',
    )
    parser.add_argument(
        "--lang",
        default="eng",
        help='Language tag (default: "eng")',
    )
    parser.add_argument(
        "--presenter",
        default="TBD",
        help='Presenter name (default: "TBD")',
    )
    parser.add_argument(
        "--id-prefix",
        default=None,
        help="Year prefix for the entry id (default: paper's published year)",
    )
    parser.add_argument(
        "--id-seq",
        type=int,
        default=None,
        help='Sequence number for the entry id (default: "NNN" placeholder)',
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    arxiv_id = args.arxiv_id.strip()
    # Strip a leading "arXiv:" prefix if present
    if arxiv_id.lower().startswith("arxiv:"):
        arxiv_id = arxiv_id[6:]

    entry = fetch_arxiv_metadata(arxiv_id)
    metadata = parse_entry(entry, arxiv_id)
    yaml_block = generate_yaml(
        arxiv_id,
        metadata,
        field=args.field,
        lang=args.lang,
        presenter=args.presenter,
        id_prefix=args.id_prefix,
        id_seq=args.id_seq,
    )
    print(yaml_block)


if __name__ == "__main__":
    main()
