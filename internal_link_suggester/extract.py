"""Page fetching, HTML text extraction and sitemap parsing.

Only the standard library: ``html.parser`` for text, ``xml.etree`` for
sitemaps, ``urllib`` for fetching. JavaScript-rendered pages are out of
scope -- this is a content-similarity tool, not a crawler.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html.parser import HTMLParser

from .text import tokenize

__all__ = ["PageData", "extract_page", "fetch_url", "parse_sitemap", "parse_sitemap_index"]

_SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header"}
_HEADING_TAGS = {"h1", "h2", "h3"}
_WS_RE = re.compile(r"\s+")


@dataclass
class PageData:
    url: str
    title: str = ""
    headings: list[str] = field(default_factory=list)
    text: str = ""
    outgoing_links: list[str] = field(default_factory=list)

    @property
    def tokens(self) -> list[str]:
        # Title + headings count double: they carry the page's topic.
        weighted = f"{self.title} {self.title} "
        weighted += " ".join(self.headings) + " "
        weighted += self.text
        return tokenize(weighted)


class _TextExtractor(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title = ""
        self.headings: list[str] = []
        self.chunks: list[str] = []
        self.links: list[str] = []
        self._skip_depth = 0
        self._current: str | None = None
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag in ("title", *_HEADING_TAGS, "p", "li"):
            self._current = tag
            self._buf = []
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href:
                self.links.append(urllib.parse.urljoin(self.base_url, href))

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._current == tag:
            text = _WS_RE.sub(" ", "".join(self._buf)).strip()
            if text:
                if tag == "title":
                    self.title = text
                elif tag in _HEADING_TAGS:
                    self.headings.append(text)
                else:
                    self.chunks.append(text)
            self._current = None
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._current is not None:
            self._buf.append(data)


def extract_page(url: str, html: str) -> PageData:
    """Extract title, headings, body text and links from one HTML page."""
    parser = _TextExtractor(url)
    parser.feed(html)
    parser.close()
    return PageData(
        url=url,
        title=parser.title,
        headings=parser.headings,
        text=" ".join(parser.chunks),
        outgoing_links=parser.links,
    )


def fetch_url(url: str, timeout: float = 15.0) -> str:
    """Fetch a page and return its decoded HTML (raises on HTTP error)."""
    request = urllib.request.Request(url, headers={"User-Agent": "internal-link-suggester/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{url}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{url}: {exc.reason}") from exc


def parse_sitemap(xml_text: str) -> list[str]:
    """Return the <loc> URLs of a sitemap.xml (urlset)."""
    root = ET.fromstring(xml_text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
    if not urls:  # tolerate sitemaps without a namespace
        urls = [loc.text.strip() for loc in root.iter("loc") if loc.text]
    return urls


def parse_sitemap_index(xml_text: str) -> list[str]:
    """Return the child-sitemap <loc> URLs of a sitemap index."""
    root = ET.fromstring(xml_text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
    if not urls:
        urls = [loc.text.strip() for loc in root.iter("loc") if loc.text]
    return urls


def is_sitemap_index(xml_text: str) -> bool:
    return "<sitemapindex" in xml_text[:2000]
