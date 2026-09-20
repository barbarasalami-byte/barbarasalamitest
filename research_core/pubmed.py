"""Thin NCBI E-utilities client.

Rate limits: NCBI allows 3 requests/second without an API key and 10/second
with one. Set NCBI_API_KEY and NCBI_EMAIL in the environment; NCBI will
throttle or block anonymous high-volume traffic.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree

import requests

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL_NAME = "research-core"


class _RateLimiter:
    """Serializes calls to at most `per_second` across threads."""

    def __init__(self, per_second: float) -> None:
        self._interval = 1.0 / per_second
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            delta = time.monotonic() - self._last
            if delta < self._interval:
                time.sleep(self._interval - delta)
            self._last = time.monotonic()


@dataclass
class SearchResult:
    query: str
    count: int
    pmids: list[str]
    searched_at: str


@dataclass
class Article:
    pmid: str
    title: str
    journal: str
    year: str
    authors: list[str]
    publication_types: list[str] = field(default_factory=list)
    abstract: str = ""

    @property
    def url(self) -> str:
        return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"


class PubMed:
    def __init__(self, api_key: str | None = None, email: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("NCBI_API_KEY")
        self.email = email or os.environ.get("NCBI_EMAIL", "")
        # NCBI's documented ceilings, minus a margin.
        self._limiter = _RateLimiter(8.0 if self.api_key else 2.5)
        self._session = requests.Session()

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

    def esearch(self, query: str, retmax: int = 50) -> SearchResult:
        """Run a PubMed query and return matching PMIDs."""
        response = self._get(
            "esearch.fcgi",
            self._params(term=query, retmode="json", retmax=retmax),
        )
        payload = response.json()["esearchresult"]
        if "ERROR" in payload:
            raise ValueError(f"PubMed rejected the query {query!r}: {payload['ERROR']}")
        return SearchResult(
            query=query,
            count=int(payload.get("count", 0)),
            pmids=payload.get("idlist", []),
            searched_at=time.strftime("%Y-%m-%d"),
        )

    def efetch(self, pmids: list[str]) -> list[Article]:
        """Fetch article metadata and abstracts for a list of PMIDs."""
        if not pmids:
            return []
        response = self._get(
            "efetch.fcgi",
            self._params(id=",".join(pmids), retmode="xml", rettype="abstract"),
        )
        return _parse_articles(response.text)

    def exists(self, pmid: str) -> bool:
        """True if the PMID resolves to a real record. Used for citation checks."""
        try:
            return bool(self.efetch([pmid]))
        except (requests.HTTPError, ElementTree.ParseError):
            return False


def _text(node: Any, path: str, default: str = "") -> str:
    found = node.find(path)
    return (found.text or default) if found is not None else default


def _parse_articles(xml: str) -> list[Article]:
    root = ElementTree.fromstring(xml)
    articles: list[Article] = []
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

        # Abstracts are split into labeled sections (BACKGROUND, METHODS, ...).
        parts = []
        for chunk in article.findall(".//AbstractText"):
            label = chunk.get("Label")
            body = "".join(chunk.itertext()).strip()
            parts.append(f"{label}: {body}" if label else body)

        articles.append(
            Article(
                pmid=_text(citation, "PMID"),
                title="".join(article.find("ArticleTitle").itertext()).strip()
                if article.find("ArticleTitle") is not None
                else "",
                journal=_text(article, ".//Journal/ISOAbbreviation"),
                year=_text(article, ".//JournalIssue/PubDate/Year")
                or _text(article, ".//JournalIssue/PubDate/MedlineDate")[:4],
                authors=authors,
                publication_types=[
                    pt.text or "" for pt in article.findall(".//PublicationType")
                ],
                abstract="\n\n".join(parts),
            )
        )
    return articles
