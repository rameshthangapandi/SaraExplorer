"""Keyword retrieval with Indian name normalisation (MVP). The planned upgrade is hybrid search
(Postgres full-text + pgvector with BGE-M3) and re-ranking; this module keeps the same interface."""

import re

from app.data.geo import ALIASES
from app.knowledge.docs import DOCS, VERIFIED

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "to", "for", "of", "in", "on", "and", "is", "do", "i", "need", "what", "how", "can",
         "my", "me", "are", "it", "with", "at", "be", "there", "any", "does", "should", "about", "visit", "go"}


def _terms(text: str) -> list[str]:
    text = text.lower()
    for alias, canonical in ALIASES.items():
        if alias in text:
            text += " " + canonical
    return [w for w in _WORD.findall(text) if w not in _STOP]


def search(query: str, k: int = 3) -> list[dict]:
    q = _terms(query)
    if not q:
        return []
    scored = []
    for doc in DOCS:
        tags = " ".join(doc["tags"])
        title = doc["title"].lower()
        body = doc["text"].lower()
        score = sum(3 * (t in tags) + 2 * (t in title) + body.count(t) for t in q)
        if score:
            scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{"id": d["id"], "title": d["title"], "text": d["text"], "source": d["source"], "verified": VERIFIED}
            for _, d in scored[:k]]
