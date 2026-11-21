# internal-link-suggester

[🇮🇷 توضیحات فارسی](README-fa.md)

**Suggest internal links from your sitemap — TF-IDF similarity, zero dependencies.**

```bash
python ils.py --sitemap https://example.com/sitemap.xml
python ils.py --sitemap https://example.com/sitemap.xml --json -o report.json
python ils.py --dir ./site-html --base-url https://example.com --md -o report.md
```

No `pip install`, no API key. Python 3.10+ standard library only.

## What it does

Internal links are one of the cheapest on-page SEO wins — and the most
often skipped, because nobody wants to read 500 pages to find what links
to what. This tool does the reading:

1. **Collects pages** — from a `sitemap.xml` (a sitemap index is followed)
   or from a folder of local `.html` files.
2. **Extracts text** — title (weighted ×2), headings and body text;
   nav, footer, scripts and styles are ignored.
3. **Ranks by TF-IDF cosine similarity** — sublinear TF + smoothed IDF,
   the same weighting scikit-learn uses by default, reimplemented in
   stdlib so the tool has no install step.
4. **Suggests anchors that already exist** — the anchor for a target page
   is picked from the target's most characteristic terms that already
   occur in the source page, so you can add the link without rewriting
   the paragraph.
5. **Finds orphans** — pages no other page would naturally link to.

Two things it deliberately does **not** suggest:

- **Near-duplicates** (similarity ≥ 0.95) — linking two copies of the same
  content to each other is a canonicalization problem, not a linking
  opportunity.
- **Unrelated pages** — anything below `--min-score` (default 0.05) is
  dropped, so an astronomy page on a coffee site gets no suggestions.

Persian text works out of the box: Arabic Yeh/Kaf are normalized to
Persian forms and a built-in Persian stopword list is applied (see
`internal_link_suggester/text.py`). The normalization is lightweight —
it is not a replacement for Hazm, it just makes common spelling variants
of a word count as one token.

## Example — real run on the bundled demo site

The demo site in `examples/demo-site/` is 8 small pages: 7 about home
coffee brewing, 1 about stargazing. One command:

```bash
python ils.py --dir examples/demo-site --base-url https://demo.example/ --md
```

produces [`examples/demo-output.md`](examples/demo-output.md) —
**8 pages analyzed, 21 suggestions, 2 orphans** (also as
[`demo-output.json`](examples/demo-output.json)):

| Source page | Best suggestion | Score | Suggested anchor |
| --- | --- | ---: | --- |
| Espresso at Home | Home Coffee Brewing | 0.32 | `home`, `water`, `coffee` |
| French Press Guide | Coffee Grinder Guide | 0.32 | `grinder`, `coffee`, `size` |
| Pour Over Guide | Coffee Grinder Guide | 0.32 | `grinder`, `coffee`, `size` |
| Coffee Beans Guide | Coffee Grinder Guide | 0.24 | `grinder`, `coffee`, `press` |

The orphans are exactly the two pages you would expect:

- **Stargazing Basics** — off-topic on a coffee site; no page is similar
  enough to link to it (max similarity 0.02).
- **Coffee Beans Guide** — on-topic but under-linked: it ranks 4th for
  every other page, so a top-3 cutoff never picks it. That is a real
  finding — the page needs stronger topical overlap to earn links.

## Options

| Flag | Default | Meaning |
| --- | --- | --- |
| `--sitemap URL` | — | sitemap.xml URL (index followed) |
| `--dir DIR` | — | folder of `.html` files to analyze locally |
| `--base-url URL` | — | map local `--dir` files to public URLs under this base |
| `--top N` | 3 | suggestions per page |
| `--min-score X` | 0.05 | minimum cosine similarity (0–1) |
| `--limit N` | 200 | max pages to analyze |
| `--timeout S` | 15 | fetch timeout in seconds |
| `--json` / `--md` | Markdown | report format |
| `-o FILE` | stdout | write the report to a file |

## Tests

```bash
python -m unittest discover -s tests -v
```

15 tests, all passing: tokenization (English + Persian), TF-IDF
weighting, HTML extraction, sitemap parsing, suggestion ranking,
near-duplicate exclusion, orphan detection, and an end-to-end run over
the demo site that asserts the exact output — 21 suggestions, 2 orphans.

## How it fits the 12-week series

Week 5 of 12 — *internal-link-suggester*. Programmatic / on-page SEO at
scale: the same technique behind the internal-linking passes on large
content sites, packaged as a one-command tool. Earlier weeks:
[seo-audit-cli](https://github.com/mohammad-abbasi-sh/seo-audit-cli) (week 1),
[striking-distance](https://github.com/mohammad-abbasi-sh/agent-seo-skills/tree/main/skills/striking-distance)
(week 2),
[persian-keyword-tools](https://github.com/mohammad-abbasi-sh/persian-keyword-tools)
(week 3),
[schema-forge](https://github.com/mohammad-abbasi-sh/agent-seo-skills/tree/main/skills/schema-forge)
(week 4).

## License

MIT — see [LICENSE](LICENSE).
