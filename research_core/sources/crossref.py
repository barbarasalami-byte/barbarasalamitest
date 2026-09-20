"""Crossref source - DOI-indexed scholarly works across every discipline.

No API key. Crossref asks for a contact email in the User-Agent ("polite
pool") and gives those requests better service; set CROSSREF_EMAIL.

This provider exists as much to prove the extension point as to be useful:
it is ~90 lines, shares no code with PubMed, and the agent picks it up with
no change anywhere else.
"""

from __future__ import annotations

import os
import re
from typing import Any

import requests

from .base import RateLimiter, Record, SearchOutcome
from .registry import register

BASE = "https://api.crossref.org/works"

SYNTAX = """\
### Crossref

Free-text bibliographic search across all disciplines, keyed by DOI. Filters:
`from-pub-date:2020-01-01`, `until-pub-date:2026-12-31`, `type:journal-article`,
`type:posted-content` (preprints), `has-abstract:true`.

Crossref has no controlled vocabulary - use natural-language phrases, not field
tags. It is the authority for confirming a DOI exists and resolves.\
"""


class Crossref:
    name = "crossref"
    id_label = "DOI"
    # DOIs are 10.<registrant>/<suffix>; the suffix may contain almost anything,
    # so stop at whitespace and trailing sentence punctuation.
    id_patterns = [re.compile(r"\b(10\.\d{4,9}/[^\s,;)\]]*[^\s,;.)\]])", re.IGNORECASE)]
    syntax_guide = SYNTAX

    def __init__(self, email: str | None = None) -> None:
        self.email = email or os.environ.get("CROSSREF_EMAIL", "")
        self._limiter = RateLimiter(5.0)
        self._session = requests.Session()
        agent = "research-core/1.0"
        if self.email:
            agent += f" (mailto:{self.email})"
        self._session.headers["User-Agent"] = agent

    def available(self) -> tuple[bool, str]:
        return True, "" if self.email else "no CROSSREF_EMAIL; using the public pool"

    def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._limiter.wait()
        response = self._session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def search(self, query: str, max_results: int = 25) -> SearchOutcome:
        payload = self._get(
            BASE,
            {
                "query.bibliographic": query,
                "rows": max(1, min(max_results, 100)),
                "select": "DOI,title,author,issued,container-title,type,abstract,URL",
            },
        )["message"]
        return SearchOutcome(
            source=self.name,
            query=query,
            total_matches=int(payload.get("total-results", 0)),
            records=[_to_record(item) for item in payload.get("items", [])],
        )

    def fetch(self, ids: list[str]) -> list[Record]:
        # Crossref has no batch endpoint; fetch one DOI at a time.
        records = []
        for doi in ids[:20]:
            try:
                payload = self._get(f"{BASE}/{requests.utils.quote(doi, safe='')}")
            except requests.HTTPError:
                continue
            records.append(_to_record(payload["message"]))
        return records

    def exists(self, record_id: str) -> bool:
        try:
            self._get(f"{BASE}/{requests.utils.quote(record_id, safe='')}")
        except requests.RequestException:
            return False
        return True


def _to_record(item: dict[str, Any]) -> Record:
    authors = [
        " ".join(filter(None, [a.get("family", ""), a.get("given", "")[:1]])).strip()
        for a in item.get("author", [])
    ]
    date_parts = item.get("issued", {}).get("date-parts", [[]])
    year = str(date_parts[0][0]) if date_parts and date_parts[0] else ""
    doc_type = item.get("type", "")
    container = item.get("container-title") or [""]
    title = item.get("title") or [""]

    return Record(
        source="crossref",
        id=item.get("DOI", ""),
        title=title[0] if title else "",
        authors=[a for a in authors if a],
        year=year,
        venue=container[0] if container else "",
        doc_types=[doc_type] if doc_type else [],
        # Crossref abstracts arrive as JATS XML when present at all.
        abstract=re.sub(r"<[^>]+>", "", item.get("abstract", "")).strip(),
        url=item.get("URL", ""),
        is_preprint=doc_type == "posted-content",
    )


register(Crossref(), replace=True)
