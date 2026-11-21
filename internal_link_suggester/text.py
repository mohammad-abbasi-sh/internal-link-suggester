"""Tokenization and normalization for internal-link suggestion.

Language-agnostic core (Unicode word characters) with small built-in
stopword lists for English and Persian, plus Persian orthography
normalization (Arabic Yeh/Kaf -> Persian Yeh/Kaf).

No external dependencies: Persian normalization here is intentionally
lightweight -- it is not a replacement for Hazm, it just makes the
common variants of a word count as one token.
"""

from __future__ import annotations

import re
import unicodedata

# Arabic Yeh U+064A / Arabic Kaf U+0643 -> Persian Yeh U+06CC / Kaf U+06A9.
_ARABIC_TO_PERSIAN = str.maketrans({"ي": "ی", "ك": "ک", "ة": "ه"})

# Tatweel (kashida) and Arabic diacritics are stripped; ZWNJ (U+200C) is
# kept inside tokens where the regex allows it (see _WORD_RE).
_STRIP_CHARS = "".join(chr(c) for c in range(0x064B, 0x0653)) + "ـ"

_EN_STOPWORDS = frozenset(
    """
    a an the and or but of to in on for with by at from as is are was were be
    been being have has had do does did will would can could should may might
    this that these those it its it’s there here what when where which who whom
    how why not no yes if then than so such very just only also more most other
    some any all each every both between into through after before over under
    about against per via you your we our they their he she his her i me my
    """.split()
)

_FA_STOPWORDS = frozenset(
    """
    و در به از که این آن با برای است می ها های را بر تا یا اگر اما چون هم نه
    چه کسی کجا وقتی چرا چطور شود شد شده کنند کند بود بودند باشد هست نیست
    خود من تو او ما شما آنها اینها آنها را یک دو سه درون بیرون روی زیر
    میان بین پس پیش بعد قبل هنوز همواره فقط بلکه ولی زیرا مگر
    """.split()
)

STOPWORDS = _EN_STOPWORDS | _FA_STOPWORDS

# A "word" is a run of Unicode letters/digits, optionally joined by ZWNJ
# or hyphen so Persian half-space compounds (می‌شود) and hyphenated
# English words (pour-over) stay one token.
_WORD_RE = re.compile(r"[\w\u200c]+(?:-[\w\u200c]+)?", re.UNICODE)


def normalize_persian(text: str) -> str:
    """Map Arabic Yeh/Kaf/Teh-marbuta to Persian forms, strip diacritics."""
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(_ARABIC_TO_PERSIAN)
    return text.translate(str.maketrans("", "", _STRIP_CHARS))


def tokenize(text: str, *, stopwords: frozenset = STOPWORDS) -> list[str]:
    """Lowercase, normalize, split into tokens, drop stopwords.

    Pure digits are dropped too: they carry no topical signal for
    internal linking ("2026" links everything to everything).
    """
    text = normalize_persian(text).lower()
    tokens = []
    for match in _WORD_RE.finditer(text):
        token = match.group(0).strip("-\u200c")
        if not token or token in stopwords:
            continue
        if token.isdigit():
            continue
        # Drop tokens that are only 1 latin char ("a", "I" leftovers).
        if len(token) == 1 and token.isascii():
            continue
        tokens.append(token)
    return tokens
