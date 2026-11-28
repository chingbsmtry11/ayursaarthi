"""Text normalisation shared by ingestion and query time.

Goal: "Guduchi", "guḍūcī" and "गुडूची" all become the same token "guduci".
"""
import re
import unicodedata

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def to_iast(text: str) -> str:
    """Devanagari -> IAST; text with no Devanagari is returned unchanged."""
    if not text:
        return ""
    if DEVANAGARI.search(text):
        return transliterate(text, sanscript.DEVANAGARI, sanscript.IAST)
    return text


def fold(text: str) -> str:
    """Lower-case ASCII form: strip diacritics, unify common spelling variants."""
    t = to_iast(text).lower().replace("ṃ", "n").replace("ṁ", "n")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    # common romanisation variants -> one form
    for a, b in (("chh", "ch"), ("ch", "c"), ("sh", "s"), ("aa", "a"), ("ee", "i"),
                 ("oo", "u"), ("w", "v"), ("ph", "p"), ("th", "t"), ("dh", "d"),
                 ("kh", "k"), ("gh", "g"), ("bh", "b"), ("jh", "j")):
        t = t.replace(a, b)
    return t


TOKEN = re.compile(r"[a-z0-9]+")
STOP = {"the", "a", "an", "of", "and", "or", "is", "are", "in", "to", "for", "what",
        "which", "how", "does", "do", "with", "on", "by", "as", "it", "its", "be",
        "kya", "hai", "ka", "ki", "ke", "me", "aur"}


def _plain(text: str) -> str:
    t = unicodedata.normalize("NFKD", to_iast(text).lower().replace("ṃ", "n").replace("ṁ", "n"))
    return "".join(c for c in t if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    """Drop stop-words on the plain form first, then fold spelling variants."""
    return [fold(t) for t in TOKEN.findall(_plain(text)) if t not in STOP and len(t) > 1]


def phrase(text: str) -> str:
    """Folded, punctuation-free form used for alias (name) matching."""
    # drop a word-final "a" so Hindi/Sanskrit spellings meet: गिलोय (giloya) = Giloy, निम्ब = Nimba
    return " ".join(re.sub(r"(?<=[^aeiou])a$", "", fold(t)) if len(t) > 3 else fold(t)
                    for t in TOKEN.findall(_plain(text)))
