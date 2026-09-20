"""ClinicalTrials.gov source (API v2).

Why this one matters for evidence work: trials that were registered and
completed but never published are invisible to a journal-only search. That gap
is publication bias, and it is exactly what a market-access or medical-affairs
reader is exposed to. A trial with `results_posted=False` and a completion date
years past is itself a finding.
"""

from __future__ import annotations

import re
from typing import Any

from .base import Record
from .registry import register
from .rest import JSONSource

SYNTAX = """\
### ClinicalTrials.gov

Registry of clinical studies, keyed by NCT number. Natural-language or field
queries; no controlled vocabulary. Useful shapes:

    semaglutide obesity cardiovascular
    AREA[InterventionName]semaglutide AND AREA[Phase]PHASE3

Every record carries status, phase, enrollment, sponsor, completion date, and
whether results were posted. A completed trial with no posted results and no
publication is evidence of publication bias - report it as such rather than
omitting it.\
"""


class ClinicalTrials(JSONSource):
    name = "clinicaltrials"
    id_label = "NCT"
    id_patterns = [re.compile(r"\b(NCT\d{8})\b", re.IGNORECASE)]
    syntax_guide = SYNTAX

    BASE = "https://clinicaltrials.gov/api/v2/studies"
    RATE_PER_SECOND = 4.0

    def _search_params(self, query: str, max_results: int) -> dict[str, Any]:
        return {
            "query.term": query,
            "pageSize": max_results,
            "countTotal": "true",
            "format": "json",
        }

    def _total_from(self, payload: dict[str, Any]) -> int:
        return int(payload.get("totalCount", 0) or 0)

    def _records_from(self, payload: dict[str, Any]) -> list[Record]:
        return [_to_record(s) for s in payload.get("studies", [])]

    def _fetch_one(self, record_id: str) -> Record | None:
        payload = self._get(f"{self.BASE}/{record_id.upper()}", {"format": "json"})
        return _to_record(payload) if payload.get("protocolSection") else None


def _to_record(study: dict[str, Any]) -> Record:
    protocol = study.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    design = protocol.get("designModule", {})
    sponsor = protocol.get("sponsorCollaboratorsModule", {})
    desc = protocol.get("descriptionModule", {})

    nct = ident.get("nctId", "")
    phases = design.get("phases", []) or []
    overall = status.get("overallStatus", "")
    completion = (status.get("completionDateStruct", {}) or {}).get("date", "")
    results_posted = bool(study.get("hasResults"))
    enrollment = (design.get("enrollmentInfo", {}) or {}).get("count")

    # Surfaced in the abstract because it drives screening decisions: the model
    # should see "completed, no results posted" without a second call.
    header = [
        f"Status: {overall}" if overall else "",
        f"Phase: {', '.join(phases)}" if phases else "",
        f"Enrollment: {enrollment}" if enrollment is not None else "",
        f"Completion: {completion}" if completion else "",
        f"Results posted: {'yes' if results_posted else 'NO'}",
    ]
    summary = desc.get("briefSummary", "")

    return Record(
        source="clinicaltrials",
        id=nct,
        title=ident.get("briefTitle", "") or ident.get("officialTitle", ""),
        authors=[(sponsor.get("leadSponsor", {}) or {}).get("name", "")] if sponsor else [],
        year=(status.get("startDateStruct", {}) or {}).get("date", "")[:4],
        venue="ClinicalTrials.gov",
        doc_types=[t for t in ([design.get("studyType", "")] + phases) if t],
        abstract=" | ".join(h for h in header if h) + (f"\n\n{summary}" if summary else ""),
        url=f"https://clinicaltrials.gov/study/{nct}" if nct else "",
    )


register(ClinicalTrials(), replace=True)
