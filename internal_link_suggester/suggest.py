"""Build internal-link suggestions from a set of pages.

For every source page, rank all other pages by TF-IDF cosine similarity
of their text and suggest the top N above a threshold. Anchor text is
derived from the target page's most characteristic terms that already
occur in the source page -- so the suggested anchor exists in the source
text and can be linked without rewriting the paragraph.

Pages that receive no suggestion from anyone are reported as orphans
(pages no other page would naturally link to).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field

from .extract import PageData
from .tfidf import cosine_similarity, tfidf_vectors

# Above this, two pages are near-duplicates (same content, different URL):
# linking them to each other adds nothing -- they are a canonicalization
# problem, not an internal-linking opportunity.
NEAR_DUPLICATE = 0.95


@dataclass
class Suggestion:
    source_url: str
    target_url: str
    target_title: str
    score: float
    anchors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "source_url": self.source_url,
            "target_url": self.target_url,
            "target_title": self.target_title,
            "score": round(self.score, 3),
            "anchors": self.anchors,
        }


@dataclass
class Page:
    """A page with its extracted text, ready for suggestion building."""

    url: str
    title: str
    text: str
    tokens: list[str]

    @classmethod
    def from_extracted(cls, data: PageData) -> "Page":
        return cls(url=data.url, title=data.title or data.url, text=data.text, tokens=data.tokens)


def _anchor_terms(
    source_tokens: list[str],
    target_vector: dict[str, float],
    *,
    max_anchors: int = 3,
) -> list[str]:
    """Top target terms (by TF-IDF weight) that appear in the source text."""
    source_set = set(source_tokens)
    ranked = sorted(
        ((weight, term) for term, weight in target_vector.items() if term in source_set),
        reverse=True,
    )
    return [term for _, term in ranked[:max_anchors]]


def build_suggestions(
    pages: list[Page],
    *,
    top_n: int = 3,
    min_score: float = 0.05,
    max_anchors: int = 3,
) -> list[Suggestion]:
    """Suggest up to ``top_n`` internal links per page.

    Skips the page itself, near-duplicates (score >= 0.95) and pairs
    below ``min_score``. Suggestions are sorted by score, best first.
    """
    if len(pages) < 2:
        return []
    vectors = tfidf_vectors([page.tokens for page in pages])
    suggestions: list[Suggestion] = []
    for i, source in enumerate(pages):
        ranked: list[tuple[float, int]] = []
        for j, target in enumerate(pages):
            if i == j:
                continue
            score = cosine_similarity(vectors[i], vectors[j])
            if score < min_score or score >= NEAR_DUPLICATE:
                continue
            ranked.append((score, j))
        ranked.sort(reverse=True)
        for score, j in ranked[:top_n]:
            target = pages[j]
            suggestions.append(
                Suggestion(
                    source_url=source.url,
                    target_url=target.url,
                    target_title=target.title,
                    score=score,
                    anchors=_anchor_terms(source.tokens, vectors[j], max_anchors=max_anchors),
                )
            )
    return suggestions


def find_orphans(pages: list[Page], suggestions: list[Suggestion]) -> list[Page]:
    """Pages that no other page suggests linking to."""
    linked_to = {s.target_url for s in suggestions}
    return [page for page in pages if page.url not in linked_to]


def suggestions_by_source(suggestions: list[Suggestion]) -> dict[str, list[Suggestion]]:
    grouped: dict[str, list[Suggestion]] = {}
    for suggestion in suggestions:
        grouped.setdefault(suggestion.source_url, []).append(suggestion)
    return grouped


def render_markdown(
    pages: list[Page],
    suggestions: list[Suggestion],
    orphans: list[Page],
) -> str:
    """A human-readable report: one section per source page."""
    lines = [
        "# Internal-link suggestions",
        "",
        f"Pages analyzed: **{len(pages)}** — suggestions: **{len(suggestions)}**"
        f" — orphans: **{len(orphans)}**",
        "",
    ]
    by_source = suggestions_by_source(suggestions)
    for page in pages:
        lines.append(f"## {page.title}")
        lines.append("")
        lines.append(f"<{page.url}>")
        lines.append("")
        page_suggestions = by_source.get(page.url, [])
        if not page_suggestions:
            lines.append("_No link suggestion above the similarity threshold._")
            lines.append("")
            continue
        lines.append("| Target | Score | Suggested anchor |")
        lines.append("| --- | ---: | --- |")
        for s in page_suggestions:
            anchors = ", ".join(f"`{a}`" for a in s.anchors) or "—"
            lines.append(f"| [{s.target_title}]({s.target_url}) | {s.score:.2f} | {anchors} |")
        lines.append("")
    if orphans:
        lines.append("## Orphans — no page suggests linking to these")
        lines.append("")
        for page in orphans:
            lines.append(f"- [{page.title}]({page.url})")
        lines.append("")
    return "\n".join(lines)


def render_json(
    pages: list[Page],
    suggestions: list[Suggestion],
    orphans: list[Page],
) -> str:
    """Machine-readable report (same content as the Markdown one)."""
    return json.dumps(
        {
            "pages": len(pages),
            "suggestions": len(suggestions),
            "orphans": [page.url for page in orphans],
            "results": {
                page.url: [s.as_dict() for s in suggestions_by_source(suggestions).get(page.url, [])]
                for page in pages
            },
        },
        ensure_ascii=False,
        indent=2,
    )
