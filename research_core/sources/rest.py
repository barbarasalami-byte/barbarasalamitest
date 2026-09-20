"""Shared base for JSON-over-HTTP sources.

Every provider below ClinicalTrials.gov-style is a thin subclass: point it at a
base URL, map the response to `Record`, done. Keeping the HTTP mechanics here
means correcting a wrong endpoint or field path is a one-line change in one
small file rather than surgery on a bespoke client.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

from .base import RateLimiter, Record, SearchOutcome

log = logging.getLogger(__name__)


class JSONSource:
    """A source that speaks JSON over HTTP GET.

    Subclasses set `name`, `id_label`, `id_patterns`, `syntax_guide`, `BASE`,
    and implement `_search_params`, `_records_from`, and `_fetch_one`.
    """

    BASE: str = ""
    RATE_PER_SECOND: float = 4.0
    CONTACT_ENV: str | None = None
    """Env var holding a contact email, where the service asks for one."""
    API_KEY_ENV: str | None = None
    """Env var holding an API key, where the service requires one."""
    API_KEY_REQUIRED: bool = False

    def __init__(self) -> None:
        self.contact = os.environ.get(self.CONTACT_ENV, "") if self.CONTACT_ENV else ""
        self.api_key = os.environ.get(self.API_KEY_ENV, "") if self.API_KEY_ENV else ""
        self._limiter = RateLimiter(self.RATE_PER_SECOND)
        self._session = requests.Session()
        agent = "research-core/1.0"
        if self.contact:
            agent += f" ({self.contact})"
        self._session.headers["User-Agent"] = agent
        self._session.headers["Accept"] = "application/json"

    def available(self) -> tuple[bool, str]:
        if self.API_KEY_REQUIRED and not self.api_key:
            return False, f"{self.API_KEY_ENV} not set"
        if self.CONTACT_ENV and not self.contact:
            return True, f"{self.CONTACT_ENV} not set; the service may throttle"
        return True, ""

    def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._limiter.wait()
        response = self._session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    # --- subclass hooks -------------------------------------------------

    def _search_params(self, query: str, max_results: int) -> dict[str, Any]:
        raise NotImplementedError

    def _search_url(self) -> str:
        return self.BASE

    def _records_from(self, payload: dict[str, Any]) -> list[Record]:
        raise NotImplementedError

    def _total_from(self, payload: dict[str, Any]) -> int:
        return len(self._records_from(payload))

    def _fetch_one(self, record_id: str) -> Record | None:
        raise NotImplementedError

    # --- SourceProvider -------------------------------------------------

    def search(self, query: str, max_results: int = 25) -> SearchOutcome:
        capped = max(1, min(max_results, 100))
        payload = self._get(self._search_url(), self._search_params(query, capped))
        return SearchOutcome(
            source=self.name,
            query=query,
            total_matches=self._total_from(payload),
            records=self._records_from(payload)[:capped],
        )

    def fetch(self, ids: list[str]) -> list[Record]:
        records = []
        for record_id in ids[:20]:
            try:
                record = self._fetch_one(record_id)
            except requests.RequestException as exc:
                log.info("%s: fetch of %r failed: %s", self.name, record_id, exc)
                continue
            if record is not None:
                records.append(record)
        return records

    def exists(self, record_id: str) -> bool:
        try:
            return self._fetch_one(record_id) is not None
        except requests.RequestException:
            return False


def first(value: Any, default: str = "") -> str:
    """Take the first item of a maybe-list, as a string."""
    if isinstance(value, list):
        return str(value[0]) if value else default
    return str(value) if value not in (None, "") else default
