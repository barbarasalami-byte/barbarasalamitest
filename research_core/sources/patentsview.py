"""USPTO source via the PatentsView search API.

PatentsView requires a free API key (request at patentsview.org); without one
the source registers but reports itself unavailable, so a review degrades to
the other sources rather than failing.

For prior art, priority date matters more than publication date, and patent
families are duplicates - deduplicate by family, not document number.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .base import Record
from .registry import register
from .rest import JSONSource

SYNTAX = """\
### USPTO (PatentsView)

Structured JSON queries over granted US patents. The query goes in `q` as a
JSON object:

    {"_text_any": {"patent_title": "semaglutide"}}
    {"_and": [{"_gte": {"patent_date": "2015-01-01"}},
              {"_text_any": {"patent_title": "GLP-1"}}]}

Search claims and CPC classification, not just titles - a patent's scope lives
in its claims. Priority date governs prior art. Family members are duplicates.\
"""


class PatentsView(JSONSource):
    name = "uspto"
    id_label = "PATENT"
    id_patterns = [re.compile(r"\bUS[- ]?(\d{7,8})(?:\s?B[12])?\b")]
    syntax_guide = SYNTAX

    BASE = "https://search.patentsview.org/api/v1/patent/"
    RATE_PER_SECOND = 0.7  # PatentsView allows 45 req/min
    API_KEY_ENV = "PATENTSVIEW_API_KEY"
    API_KEY_REQUIRED = True

    FIELDS = [
        "patent_id",
        "patent_title",
        "patent_date",
        "patent_abstract",
        "assignees.assignee_organization",
    ]

    def __init__(self) -> None:
        super().__init__()
        if self.api_key:
            self._session.headers["X-Api-Key"] = self.api_key

    def _search_params(self, query: str, max_results: int) -> dict[str, Any]:
        # Accept either a raw PatentsView JSON query or plain keywords.
        try:
            parsed = json.loads(query)
        except (json.JSONDecodeError, TypeError):
            parsed = {"_text_any": {"patent_title": query}}
        return {
            "q": json.dumps(parsed),
            "f": json.dumps(self.FIELDS),
            "o": json.dumps({"size": max_results}),
        }

    def _total_from(self, payload: dict[str, Any]) -> int:
        return int(payload.get("total_hits", 0) or 0)

    def _records_from(self, payload: dict[str, Any]) -> list[Record]:
        return [_to_record(p) for p in payload.get("patents", []) or []]

    def _fetch_one(self, record_id: str) -> Record | None:
        payload = self._get(
            self.BASE,
            {
                "q": json.dumps({"patent_id": str(record_id)}),
                "f": json.dumps(self.FIELDS),
            },
        )
        records = self._records_from(payload)
        return records[0] if records else None


def _to_record(patent: dict[str, Any]) -> Record:
    patent_id = str(patent.get("patent_id", ""))
    assignees = [
        a.get("assignee_organization", "")
        for a in (patent.get("assignees") or [])
        if a.get("assignee_organization")
    ]
    date = patent.get("patent_date", "") or ""

    return Record(
        source="uspto",
        id=patent_id,
        title=patent.get("patent_title", ""),
        authors=assignees,
        year=date[:4],
        venue="USPTO",
        doc_types=["patent"],
        abstract=patent.get("patent_abstract", "") or "",
        url=f"https://patents.google.com/patent/US{patent_id}" if patent_id else "",
    )


register(PatentsView(), replace=True)
