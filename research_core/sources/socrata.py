"""Socrata open-data portals (CDC, and many state/federal portals).

A portal is a catalogue of hundreds of datasets, not one searchable corpus, so
`search` here discovers *datasets* - "what CDC data exists about X" - rather
than rows. Once a dataset is chosen, query its rows directly with
`rows(dataset_id, **soql)`.

Point `DOMAIN` at any Socrata host to get another portal.
"""

from __future__ import annotations

import re
from typing import Any

from .base import Record
from .registry import register
from .rest import JSONSource

CATALOG = "https://api.us.socrata.com/api/catalog/v1"

CDC_SYNTAX = """\
### CDC (data.cdc.gov)

Searches the CDC open-data *catalogue*: plain keywords return matching datasets
with their four-by-four identifiers (e.g. `9mfq-cb36`), not data rows.

    obesity prevalence adult
    NNDSS weekly

Once you have an identifier, request rows for it rather than searching again.
Surveillance data are counts as reported, subject to revision and reporting
lag; a recent period is provisional, not final. Say so when citing it.\
"""


class SocrataPortal(JSONSource):
    """Dataset discovery over one Socrata domain."""

    DOMAIN = ""
    BASE = CATALOG
    RATE_PER_SECOND = 3.0

    # Socrata "four-by-four" ids. The negative lookahead rejects all-digit
    # pairs, because a date range like 2020-2026 appears in every search log
    # and would otherwise be extracted as a dataset citation.
    id_patterns = [re.compile(r"\b(?![0-9]{4}-[0-9]{4}\b)([a-z0-9]{4}-[a-z0-9]{4})\b")]
    id_label = "DATASET"

    def _search_params(self, query: str, max_results: int) -> dict[str, Any]:
        return {"q": query, "domains": self.DOMAIN, "limit": max_results}

    def _total_from(self, payload: dict[str, Any]) -> int:
        return int(payload.get("resultSetSize", 0) or 0)

    def _records_from(self, payload: dict[str, Any]) -> list[Record]:
        return [self._to_record(item) for item in payload.get("results", []) or []]

    def _fetch_one(self, record_id: str) -> Record | None:
        payload = self._get(self.BASE, {"ids": record_id, "domains": self.DOMAIN})
        records = self._records_from(payload)
        return records[0] if records else None

    def rows(self, dataset_id: str, **soql: Any) -> list[dict[str, Any]]:
        """Fetch rows from one dataset. SoQL params: $where, $select, $limit."""
        result = self._get(f"https://{self.DOMAIN}/resource/{dataset_id}.json", soql)
        return result if isinstance(result, list) else []

    def _to_record(self, item: dict[str, Any]) -> Record:
        resource = item.get("resource", {}) or {}
        dataset_id = resource.get("id", "")
        updated = str(resource.get("updatedAt", ""))
        return Record(
            source=self.name,
            id=dataset_id,
            title=resource.get("name", ""),
            authors=[(item.get("owner", {}) or {}).get("display_name", "")],
            year=updated[:4],
            venue=self.DOMAIN,
            doc_types=["dataset"],
            abstract=(resource.get("description", "") or "")[:1500],
            url=item.get("permalink", "")
            or (f"https://{self.DOMAIN}/d/{dataset_id}" if dataset_id else ""),
        )


class CDC(SocrataPortal):
    name = "cdc"
    DOMAIN = "data.cdc.gov"
    syntax_guide = CDC_SYNTAX


register(CDC(), replace=True)
