#!/usr/bin/env python3
"""internal-link-suggester: suggest internal links from a sitemap or a folder of HTML.

Usage:
    python ils.py --sitemap https://example.com/sitemap.xml
    python ils.py --sitemap https://example.com/sitemap.xml --json -o report.json
    python ils.py --dir ./site-html --md -o report.md
    python ils.py --dir ./site-html --base-url https://example.com --top 5 --min-score 0.10

Zero dependencies -- Python 3.10+ standard library only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from internal_link_suggester.extract import (
    extract_page,
    fetch_url,
    is_sitemap_index,
    parse_sitemap,
    parse_sitemap_index,
)
from internal_link_suggester.suggest import (
    Page,
    build_suggestions,
    find_orphans,
    render_json,
    render_markdown,
)


def collect_from_sitemap(sitemap_url: str, limit: int, timeout: float) -> list[Page]:
    """Fetch a sitemap (following an index), then fetch each listed page."""
    xml_text = fetch_url(sitemap_url, timeout=timeout)
    if is_sitemap_index(xml_text):
        child_sitemaps = parse_sitemap_index(xml_text)
        urls: list[str] = []
        for child in child_sitemaps:
            urls.extend(parse_sitemap(fetch_url(child, timeout=timeout)))
    else:
        urls = parse_sitemap(xml_text)

    pages: list[Page] = []
    failures: list[str] = []
    for url in urls[:limit]:
        try:
            pages.append(Page.from_extracted(extract_page(url, fetch_url(url, timeout=timeout))))
        except RuntimeError as exc:
            failures.append(str(exc))
    for failure in failures:
        print(f"warning: skipped {failure}", file=sys.stderr)
    print(f"fetched {len(pages)}/{len(urls[:limit])} pages from sitemap", file=sys.stderr)
    return pages


def collect_from_dir(directory: Path, limit: int, base_url: str | None = None) -> list[Page]:
    """Read local *.html files; the URL is the file path by default.

    With --base-url, local paths map to public URLs (e.g. a local mirror
    of a site), so the report links to real pages instead of file:// paths.
    """
    import urllib.parse

    files = sorted(directory.rglob("*.html"))[:limit]
    pages: list[Page] = []
    for path in files:
        html = path.read_text(encoding="utf-8", errors="replace")
        if base_url:
            url = urllib.parse.urljoin(base_url.rstrip("/") + "/", path.relative_to(directory).as_posix())
        else:
            url = path.resolve().as_uri()
        pages.append(Page.from_extracted(extract_page(url, html)))
    print(f"read {len(pages)} HTML files from {directory}", file=sys.stderr)
    return pages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Suggest internal links between pages using TF-IDF similarity."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--sitemap", metavar="URL", help="sitemap.xml URL (index followed)")
    source.add_argument("--dir", metavar="DIR", help="folder of .html files to analyze locally")
    parser.add_argument("--top", type=int, default=3, help="suggestions per page (default: 3)")
    parser.add_argument("--min-score", type=float, default=0.05, help="minimum cosine similarity (default: 0.05)")
    parser.add_argument("--limit", type=int, default=200, help="max pages to analyze (default: 200)")
    parser.add_argument("--base-url", metavar="URL", help="map local --dir files to public URLs under this base")
    parser.add_argument("--timeout", type=float, default=15.0, help="fetch timeout in seconds (default: 15)")
    parser.add_argument("--json", action="store_true", help="output JSON instead of Markdown")
    parser.add_argument("--md", action="store_true", help="output Markdown (default)")
    parser.add_argument("-o", "--output", metavar="FILE", help="write report to FILE instead of stdout")
    args = parser.parse_args(argv)

    if args.sitemap:
        pages = collect_from_sitemap(args.sitemap, args.limit, args.timeout)
    else:
        pages = collect_from_dir(Path(args.dir), args.limit, args.base_url)

    if len(pages) < 2:
        print("error: need at least 2 pages to suggest links", file=sys.stderr)
        return 2

    suggestions = build_suggestions(pages, top_n=args.top, min_score=args.min_score)
    orphans = find_orphans(pages, suggestions)
    report = render_json(pages, suggestions, orphans) if args.json else render_markdown(pages, suggestions, orphans)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"wrote {args.output} ({len(suggestions)} suggestions, {len(orphans)} orphans)", file=sys.stderr)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
