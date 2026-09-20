"""The contract a research source implements.

Add a source by writing one class that satisfies `SourceProvider` and
registering it. The agent builds its tools, its prompt guidance, and its
citation checks from whatever is registered - no other file changes.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class Record:
    """One retrieved item, normalized across sources."""

    source: str
    id: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: str = ""
    venue: str = ""
    doc_types: list[str] = field(default_factory=list)
    abstract: str = ""
    url: str = ""
    is_preprint: bool = False

    def citation_key(self) -> str:
        """Stable cross-source identity for deduplication."""
        return f"{self.source}:{self.id}"

    def summary_line(self) -> str:
        types = f" | {'; '.join(self.doc_types)}" if self.doc_types else ""
        preprint = " [PREPRINT]" if self.is_preprint else ""
        return f"{self.venue} {self.year}{types}{preprint}".strip()


@dataclass
class SearchOutcome:
    source: str
    query: str
    total_matches: int
    records: list[Record]
    searched_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d"))


@runtime_checkable
class SourceProvider(Protocol):
    """A searchable corpus."""

    name: str
    id_label: str
    """What this source calls its identifier, e.g. 'PMID' or 'DOI'."""

    id_patterns: list[re.Pattern[str]]
    """Regexes matching this source's IDs in prose. Group 1 is the bare ID."""

    syntax_guide: str
    """Markdown query guidance, injected into the prompt only when registered."""

    def available(self) -> tuple[bool, str]:
        """(usable, reason). Reason explains what is missing when unusable."""
        ...

    def search(self, query: str, max_results: int) -> SearchOutcome: ...

    def fetch(self, ids: list[str]) -> list[Record]: ...

    def exists(self, record_id: str) -> bool:
        """Whether the ID resolves. Used to catch fabricated citations."""
        ...


class RateLimiter:
    """Serializes calls to at most `per_second`, across threads."""

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
