"""CMS source - the Medicare/Medicaid open data catalogue (data.cms.gov).

CMS runs its own DCAT-based catalogue rather than Socrata, so this does not
share the Socrata provider. As with CDC, `search` discovers *datasets*; once a
dataset is chosen, request its rows with `rows(dataset_id)`.

For coverage policy specifically - NCDs and LCDs - the Medicare Coverage
Database is a separate system that this does not reach. Coverage determinations
will not appear here; say so rather than implying a search covered them.
"""

from __future__ import annotations

import re
from typing import Any

from .base import Record
from .registry import register
from .rest import JSONSource

SYNTAX = """\
### CMS (data.cms.gov)

Searches the CMS open-data *catalogue*: plain keywords return matching datasets,
not data rows.

    Part D prescriber
    Medicare spending by drug

Useful for utilisation and spend (Part B/D spending dashboards, prescriber
summaries, provider utilisation). Costs are allowed amounts or gross spend, not
net of rebate - never present CMS gross spend as net price.

Coverage determinations (NCD/LCD) live in the Medicare Coverage Database, which
this source does not reach. If asked about coverage policy, say the search did
not cover it.\
"""


class CMS(JSONSource):
    name = "cms"
    id_label = "CMS-DATASET"
    id_patterns = [
        re.compile(r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b")
    ]
    syntax_guide = SYNTAX

    BASE = "https://data.cms.gov/data.json"
    RATE_PER_SECOND = 2.0

    def __init__(self) -> None:
        super().__init__()
        self._catalog: list[dict[str, Any]] | None = None

    def _catalog_items(self) -> list[dict[str, Any]]:
        """The DCAT catalogue, fetched once and reused.

        CMS publishes the whole catalogue as one document with no server-side
        search, so filtering happens here.
        """
        if self._catalog is None:
            payload = self._get(self.BASE)
            self._catalog = payload.get("dataset", []) or []
        return self._catalog

    def search(self, query: str, max_results: int = 25):  # type: ignore[override]
        from .base import SearchOutcome

        terms = [t for t in query.lower().split() if t]
        matches = [
            item
            for item in self._catalog_items()
            if all(
                t in f"{item.get('title', '')} {item.get('description', '')}".lower()
                for t in terms
            )
        ]
        return SearchOutcome(
            source=self.name,
            query=query,
            total_matches=len(matches),
            records=[_to_record(i) for i in matches[: max(1, min(max_results, 100))]],
        )

    def _fetch_one(self, record_id: str) -> Record | None:
        for item in self._catalog_items():
            if _dataset_id(item) == record_id:
                return _to_record(item)
        return None

    def rows(self, dataset_id: str, **params: Any) -> list[dict[str, Any]]:
        """Fetch rows for one dataset."""
        result = self._get(
            f"https://data.cms.gov/data-api/v1/dataset/{dataset_id}/data", params
        )
        return result if isinstance(result, list) else []


def _dataset_id(item: dict[str, Any]) -> str:
    """Pull the dataset id out of the DCAT identifier URL.

    CMS identifiers look like
    `https://data.cms.gov/data-api/v1/dataset/<id>/data`, so the id is the
    segment *after* "dataset" - not the last segment, which is "data".
    """
    identifier = str(item.get("identifier", ""))
    if not identifier:
        return ""
    segments = [s for s in identifier.rstrip("/").split("/") if s]
    if "dataset" in segments:
        index = segments.index("dataset") + 1
        if index < len(segments):
            return segments[index]
    return segments[-1] if segments else ""


def _to_record(item: dict[str, Any]) -> Record:
    modified = str(item.get("modified", ""))
    publisher = (item.get("publisher", {}) or {}).get("name", "")
    dataset_id = _dataset_id(item)
    return Record(
        source="cms",
        id=dataset_id,
        title=item.get("title", ""),
        authors=[publisher] if publisher else [],
        year=modified[:4],
        venue="data.cms.gov",
        doc_types=["dataset"],
        abstract=(item.get("description", "") or "")[:1500],
        url=str(item.get("landingPage", "") or item.get("identifier", "")),
    )


register(CMS(), replace=True)
