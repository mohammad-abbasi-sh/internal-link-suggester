"""internal-link-suggester: TF-IDF internal-link suggestions from a sitemap.

Zero-dependency (Python 3.10+ standard library only).
"""

from .suggest import Page, Suggestion, build_suggestions, find_orphans
from .tfidf import cosine_similarity, tfidf_vectors
from .text import tokenize

__version__ = "0.1.0"
__all__ = [
    "Page",
    "Suggestion",
    "build_suggestions",
    "cosine_similarity",
    "find_orphans",
    "tfidf_vectors",
    "tokenize",
]
