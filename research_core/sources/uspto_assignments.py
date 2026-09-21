"""USPTO Patent Assignment Search - who owns a patent, and who owned it before.

Distinct from the granted-patent search in `patentsview.py`, and registered
alongside it. PatentsView answers "what patents exist"; this answers "who
transferred what to whom, and when".

The commercial signal: an early-stage biotech assigning or collateralising
patents to a large pharma is often visible here before any announcement.
"""

from __future__ import annotations

import re
from typing import Any

from .base import Record
from .registry import register
from .rest import JSONSource

SYNTAX = """\
### USPTO Patent Assignments

Searches recorded assignment transactions, not patents themselves. Keywords
match assignor, assignee, and patent metadata:

    Novo Nordisk
    semaglutide

Each record is a recorded conveyance: reel and frame number, assignor,
assignee, and conveyance text.

Two cautions. Recordation is not instantaneous - there is a lag between
execution and appearance, so absence is not evidence of no transfer. And the
conveyance text matters: a security interest is collateral, not a sale, and
reading one as the other inverts the commercial meaning.\
"""


class PatentAssignments(JSONSource):
    name = "uspto_assignments"
    id_label = "REEL/FRAME"
    id_patterns = [re.compile(r"\b(\d{5,6}/\d{4,6})\b")]
    syntax_guide = SYNTAX

    BASE = "https://developer.uspto.gov/ds-api/patent/assignment/v1/records"
    RATE_PER_SECOND = 1.5  # ~100 req/min quota
    API_KEY_ENV = "USPTO_API_KEY"
    API_KEY_REQUIRED = True

    def __init__(self) -> None:
        super().__init__()
        if self.api_key:
            self._session.headers["x-api-key"] = self.api_key

    def _search_params(self, query: str, max_results: int) -> dict[str, Any]:
        return {"criteria": query, "start": 0, "rows": max_results}

    def _total_from(self, payload: dict[str, Any]) -> int:
        return int((payload.get("response", {}) or {}).get("numFound", 0) or 0)

    def _records_from(self, payload: dict[str, Any]) -> list[Record]:
        docs = (payload.get("response", {}) or {}).get("docs", []) or []
        return [_to_record(d) for d in docs]

    def _fetch_one(self, record_id: str) -> Record | None:
        reel, _, frame = record_id.partition("/")
        payload = self._get(
            self.BASE, {"criteria": f"reelNo:{reel} AND frameNo:{frame}", "rows": 1}
        )
        records = self._records_from(payload)
        return records[0] if records else None


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v]
    return [str(value)] if value else []


def _to_record(doc: dict[str, Any]) -> Record:
    reel = str(doc.get("reelNo", ""))
    frame = str(doc.get("frameNo", ""))
    assignors = _as_list(doc.get("assignorName") or doc.get("assignors"))
    assignees = _as_list(doc.get("assigneeName") or doc.get("assignees"))
    patents = _as_list(doc.get("patNum") or doc.get("patentNumber"))
    conveyance = str(doc.get("conveyanceText", ""))
    recorded = str(doc.get("recordedDate", ""))

    detail = [
        f"From: {'; '.join(assignors)}" if assignors else "",
        f"To: {'; '.join(assignees)}" if assignees else "",
        f"Conveyance: {conveyance}" if conveyance else "",
        f"Patents: {', '.join(patents[:8])}" if patents else "",
        f"Recorded: {recorded}" if recorded else "",
    ]
    return Record(
        source="uspto_assignments",
        id=f"{reel}/{frame}" if reel and frame else reel or frame,
        title=(
            f"{'; '.join(assignors[:2])} → {'; '.join(assignees[:2])}"
            if assignors and assignees
            else conveyance or "(assignment)"
        ),
        authors=assignees,
        year=recorded[:4],
        venue="USPTO Assignments",
        doc_types=["assignment"],
        abstract=" | ".join(d for d in detail if d),
        url=(
            f"https://assignment.uspto.gov/patent/index.html#/patent/search/resultAbstract?reelFrame={reel}-{frame}"
            if reel and frame
            else ""
        ),
    )


register(PatentAssignments(), replace=True)
