"""PubMed / NCBI E-utilities source.

Rate limits: 3 req/sec anonymous, 10 with an API key. Set NCBI_API_KEY and
NCBI_EMAIL; NCBI throttles or blocks anonymous high-volume traffic.
"""

from __future__ import annotations

import os
import re
from typing import Any
from xml.etree import ElementTree

import requests

from .base import RateLimiter, Record, SearchOutcome
from .registry import register

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL_NAME = "research-core"

SYNTAX = """\
### PubMed

Field tags: `[ti]` `[ab]` `[tiab]` `[au]` `[ta]` `[mh]` MeSH `[majr]` major MeSH
`[pt]` publication type `[dp]` date `[la]` language.
Subheadings precede the tag: `diabetes mellitus, type 2/drug therapy[mh]`.
Publication types: `randomized controlled trial[pt]`, `meta-analysis[pt]`,
`systematic review[pt]`, `guideline[pt]`. Dates: `2020:2026[dp]`.

    diabetes mellitus[mh] AND treatment[tiab] AND systematic review[pt] AND 2023:2026[dp]

Prefer MeSH where a controlled term exists; pair with `[tiab]` synonyms for
terminology MeSH has not caught up to. `[majr]` raises precision but drops
relevant work.\
"""


class PubMed:
    name = "pubmed"
    id_label = "PMID"
    id_patterns = [re.compile(r"\bPMID:?\s*(\d{4,8})\b", re.IGNORECASE)]
    syntax_guide = SYNTAX

    def __init__(self, api_key: str | None = None, email: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("NCBI_API_KEY")
        self.email = email or os.environ.get("NCBI_EMAIL", "")
        self._limiter = RateLimiter(8.0 if self.api_key else 2.5)
        self._session = requests.Session()

    def available(self) -> tuple[bool, str]:
        # NCBI works anonymously but asks for an identifying email.
        if not self.email:
            return True, "no NCBI_EMAIL set; NCBI may throttle anonymous traffic"
        return True, ""

    def _params(self, **extra: Any) -> dict[str, Any]:
        params = {"db": "pubmed", "tool": TOOL_NAME, "email": self.email, **extra}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def _get(self, endpoint: str, params: dict[str, Any]) -> requests.Response:
        self._limiter.wait()
        response = self._session.get(f"{BASE}/{endpoint}", params=params, timeout=30)
        response.raise_for_status()
        return response

    def search(self, query: str, max_results: int = 25) -> SearchOutcome:
        response = self._get(
            "esearch.fcgi",
            self._params(
                term=query, retmode="json", retmax=max(1, min(max_results, 100))
            ),
        )
        payload = response.json()["esearchresult"]
        if "ERROR" in payload:
            raise ValueError(f"PubMed rejected {query!r}: {payload['ERROR']}")
        pmids = payload.get("idlist", [])
        return SearchOutcome(
            source=self.name,
            query=query,
            total_matches=int(payload.get("count", 0)),
            records=self.fetch(pmids) if pmids else [],
        )

    def fetch(self, ids: list[str]) -> list[Record]:
        if not ids:
            return []
        response = self._get(
            "efetch.fcgi",
            self._params(id=",".join(ids), retmode="xml", rettype="abstract"),
        )
        return parse_articles(response.text)

    def exists(self, record_id: str) -> bool:
        try:
            return bool(self.fetch([record_id]))
        except (requests.RequestException, ElementTree.ParseError):
            return False


def _text(node: Any, path: str, default: str = "") -> str:
    found = node.find(path)
    return (found.text or default) if found is not None else default


def parse_articles(xml: str) -> list[Record]:
    root = ElementTree.fromstring(xml)
    records: list[Record] = []
    for entry in root.findall(".//PubmedArticle"):
        citation = entry.find("MedlineCitation")
        if citation is None:
            continue
        article = citation.find("Article")
        if article is None:
            continue

        authors = []
        for author in article.findall(".//Author"):
            last, initials = _text(author, "LastName"), _text(author, "Initials")
            if last:
                authors.append(f"{last} {initials}".strip())

        # Structured abstracts split into labeled sections.
        parts = []
        for chunk in article.findall(".//AbstractText"):
            label = chunk.get("Label")
            body = "".join(chunk.itertext()).strip()
            parts.append(f"{label}: {body}" if label else body)

        title_node = article.find("ArticleTitle")
        pmid = _text(citation, "PMID")
        doc_types = [pt.text or "" for pt in article.findall(".//PublicationType")]

        records.append(
            Record(
                source="pubmed",
                id=pmid,
                title="".join(title_node.itertext()).strip()
                if title_node is not None
                else "",
                authors=authors,
                year=_text(article, ".//JournalIssue/PubDate/Year")
                or _text(article, ".//JournalIssue/PubDate/MedlineDate")[:4],
                venue=_text(article, ".//Journal/ISOAbbreviation"),
                doc_types=doc_types,
                abstract="\n\n".join(parts),
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                is_preprint=any("preprint" in t.lower() for t in doc_types),
            )
        )
    return records


register(PubMed(), replace=True)
