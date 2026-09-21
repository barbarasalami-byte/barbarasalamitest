"""NIH RePORTER - federally funded research projects.

Upstream of everything else in the stack: a grant precedes a publication,
which precedes a trial, which precedes an approval. RePORTER is where a novel
target shows up years before it has a compound name.

Unlike the other sources this endpoint takes POST with a JSON body, so it
overrides the GET-shaped base rather than extending it.
"""

from __future__ import annotations

import re
from typing import Any

import requests

from .base import RateLimiter, Record, SearchOutcome
from .registry import register

BASE = "https://api.reporter.nih.gov/v2/projects/search"

SYNTAX = """\
### NIH RePORTER

Plain keywords search project titles, abstracts and terms:

    GLP-1 receptor agonist obesity
    CRISPR sickle cell

Returns funded projects with PI, institution, award amount and fiscal year.

A grant is funding, not a finding. It shows what is being pursued and by whom,
never that the work succeeded. Report it as activity, not evidence.\
"""


class NIHReporter:
    name = "nih_reporter"
    id_label = "APPL-ID"
    id_patterns = [re.compile(r"\bAPPL[:\s]\s*(\d{6,9})\b", re.IGNORECASE)]
    syntax_guide = SYNTAX

    def __init__(self) -> None:
        self._limiter = RateLimiter(2.0)  # guidance: <= 5 concurrent
        self._session = requests.Session()
        self._session.headers["Accept"] = "application/json"

    def available(self) -> tuple[bool, str]:
        return True, ""

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        self._limiter.wait()
        response = self._session.post(BASE, json=body, timeout=30)
        response.raise_for_status()
        return response.json()

    def search(self, query: str, max_results: int = 25) -> SearchOutcome:
        payload = self._post(
            {
                "criteria": {"advanced_text_search": {"operator": "and", "search_text": query}},
                "limit": max(1, min(max_results, 500)),
                "offset": 0,
            }
        )
        return SearchOutcome(
            source=self.name,
            query=query,
            total_matches=int((payload.get("meta", {}) or {}).get("total", 0)),
            records=[_to_record(r) for r in payload.get("results", []) or []],
        )

    def fetch(self, ids: list[str]) -> list[Record]:
        payload = self._post(
            {"criteria": {"appl_ids": [int(i) for i in ids[:20] if str(i).isdigit()]},
             "limit": 20}
        )
        return [_to_record(r) for r in payload.get("results", []) or []]

    def exists(self, record_id: str) -> bool:
        try:
            return bool(self.fetch([record_id]))
        except requests.RequestException:
            return False


def _to_record(project: dict[str, Any]) -> Record:
    appl_id = str(project.get("appl_id", ""))
    org = (project.get("organization", {}) or {}).get("org_name", "")
    pis = [
        p.get("full_name", "")
        for p in (project.get("principal_investigators") or [])
        if p.get("full_name")
    ]
    amount = project.get("award_amount")
    fiscal = str(project.get("fiscal_year", ""))

    detail = [
        f"Institution: {org}" if org else "",
        f"Fiscal year: {fiscal}" if fiscal else "",
        f"Award: ${amount:,}" if isinstance(amount, (int, float)) else "",
    ]
    abstract = project.get("abstract_text") or ""
    return Record(
        source="nih_reporter",
        id=appl_id,
        title=project.get("project_title", ""),
        authors=pis or ([org] if org else []),
        year=fiscal,
        venue="NIH RePORTER",
        doc_types=["grant"],
        abstract=" | ".join(d for d in detail if d) + (f"\n\n{abstract}" if abstract else ""),
        url=f"https://reporter.nih.gov/project-details/{appl_id}" if appl_id else "",
    )


register(NIHReporter(), replace=True)
