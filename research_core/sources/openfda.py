"""openFDA source - FDA drug data (api.fda.gov).

This is also where CDER data lives. CDER is a centre within FDA, not a separate
API: drug approvals, labels, and adverse events published by CDER are served
through the openFDA drug endpoints below. There is no distinct "CDER API" to
point at.

Endpoints, by what you are asking:
  drug/drugsfda   approvals, application numbers, sponsors  (regulatory history)
  drug/label      current structured product labelling      (indications, warnings)
  drug/event      FAERS adverse event reports               (safety signals)

Default here is drugsfda, the one that answers "what was approved, when, to
whom". Construct with endpoint="label" or "event" for the others.
"""

from __future__ import annotations

import re
from typing import Any

from .base import Record
from .registry import register
from .rest import JSONSource, first

SYNTAX = """\
### openFDA (FDA drug data, including CDER)

Lucene-style `search` syntax over FDA drug records. Field:value, quoted phrases,
`AND`/`OR`, `+AND+` ranges on dates:

    openfda.generic_name:"semaglutide"
    sponsor_name:"Novo Nordisk" AND submissions.submission_status_date:[20200101+TO+20261231]

Three endpoints: `drugsfda` (approvals and application history),
`label` (current product labelling), `event` (FAERS adverse event reports).

FAERS is spontaneous reporting: counts are not incidence rates, and a report is
not evidence of causation. Never present an adverse-event count as a rate.\
"""

ENDPOINTS = {"drugsfda", "label", "event"}


class OpenFDA(JSONSource):
    name = "openfda"
    id_label = "FDA-ID"
    # Application numbers (NDA/ANDA/BLA) are the stable public identifier.
    id_patterns = [re.compile(r"\b((?:NDA|ANDA|BLA)\d{6})\b", re.IGNORECASE)]
    syntax_guide = SYNTAX

    BASE = "https://api.fda.gov/drug"
    RATE_PER_SECOND = 3.0
    API_KEY_ENV = "OPENFDA_API_KEY"  # optional: raises the rate limit

    def __init__(self, endpoint: str = "drugsfda") -> None:
        if endpoint not in ENDPOINTS:
            raise ValueError(f"endpoint must be one of {sorted(ENDPOINTS)}")
        self.endpoint = endpoint
        super().__init__()

    def _search_url(self) -> str:
        return f"{self.BASE}/{self.endpoint}.json"

    def _search_params(self, query: str, max_results: int) -> dict[str, Any]:
        params: dict[str, Any] = {"search": query, "limit": max_results}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def _total_from(self, payload: dict[str, Any]) -> int:
        return int((payload.get("meta", {}).get("results", {}) or {}).get("total", 0))

    def _records_from(self, payload: dict[str, Any]) -> list[Record]:
        return [_to_record(r, self.endpoint) for r in payload.get("results", [])]

    def _fetch_one(self, record_id: str) -> Record | None:
        payload = self._get(
            self._search_url(),
            self._search_params(f'application_number:"{record_id.upper()}"', 1),
        )
        records = self._records_from(payload)
        return records[0] if records else None


def _to_record(item: dict[str, Any], endpoint: str) -> Record:
    openfda = item.get("openfda", {}) or {}
    app_no = item.get("application_number") or first(openfda.get("application_number"))

    products = item.get("products") or []
    brand = first(openfda.get("brand_name")) or (
        first(products[0].get("brand_name")) if products else ""
    )
    generic = first(openfda.get("generic_name"))
    sponsor = item.get("sponsor_name", "")

    submissions = item.get("submissions", []) or []
    latest = max(
        (s.get("submission_status_date", "") for s in submissions), default=""
    )

    title = " / ".join(p for p in (brand, generic) if p) or app_no or "(untitled FDA record)"
    detail = [
        f"Sponsor: {sponsor}" if sponsor else "",
        f"Application: {app_no}" if app_no else "",
        f"Submissions: {len(submissions)}" if submissions else "",
        f"Latest action: {latest}" if latest else "",
    ]

    return Record(
        source="openfda",
        id=app_no or first(item.get("safetyreportid")) or "",
        title=title,
        authors=[sponsor] if sponsor else [],
        year=latest[:4],
        venue=f"FDA {endpoint}",
        doc_types=[endpoint],
        abstract=" | ".join(d for d in detail if d),
        url=(
            f"https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process&ApplNo={app_no[-6:]}"
            if app_no
            else ""
        ),
    )


register(OpenFDA(), replace=True)
