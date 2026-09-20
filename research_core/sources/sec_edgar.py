"""SEC EDGAR source - company filings full-text search.

The SEC requires a declared User-Agent with a contact email on every request
and blocks traffic without one. Set SEC_CONTACT_EMAIL.

Full-text search covers 2001-present. For a company's complete filing history
regardless of text match, the submissions API at
data.sec.gov/submissions/CIK##########.json is the better route.
"""

from __future__ import annotations

import re
from typing import Any

from .base import Record
from .registry import register
from .rest import JSONSource

SYNTAX = """\
### SEC EDGAR

Full-text search over company filings. Quote phrases; narrow by form type and
date:

    "accelerated approval" forms=10-K dateRange=custom
    "semaglutide" forms=8-K

Useful forms: `10-K` (annual), `10-Q` (quarterly), `8-K` (material events),
`S-1` (registration), `DEF 14A` (proxy). For pharma, 8-K carries trial results
and regulatory actions; 10-K risk factors carry pipeline and patent exposure.

A filing is a company's own assertion, made under legal obligation but not
independently verified. Attribute claims to the filer, never as fact.\
"""


class SECEdgar(JSONSource):
    name = "sec_edgar"
    id_label = "ACCESSION"
    # Accession numbers: 0001234567-24-000123
    id_patterns = [re.compile(r"\b(\d{10}-\d{2}-\d{6})\b")]
    syntax_guide = SYNTAX

    BASE = "https://efts.sec.gov/LATEST/search-index"
    RATE_PER_SECOND = 8.0  # SEC asks for <= 10 req/sec
    CONTACT_ENV = "SEC_CONTACT_EMAIL"

    def available(self) -> tuple[bool, str]:
        if not self.contact:
            return False, "SEC_CONTACT_EMAIL not set; the SEC blocks anonymous traffic"
        return True, ""

    def _search_params(self, query: str, max_results: int) -> dict[str, Any]:
        return {"q": query, "from": 0, "size": max_results}

    def _total_from(self, payload: dict[str, Any]) -> int:
        total = (payload.get("hits", {}) or {}).get("total", {})
        return int(total.get("value", 0)) if isinstance(total, dict) else int(total or 0)

    def _records_from(self, payload: dict[str, Any]) -> list[Record]:
        return [_to_record(h) for h in (payload.get("hits", {}) or {}).get("hits", [])]

    def _fetch_one(self, record_id: str) -> Record | None:
        payload = self._get(self.BASE, self._search_params(f'"{record_id}"', 1))
        records = self._records_from(payload)
        return records[0] if records else None


def _to_record(hit: dict[str, Any]) -> Record:
    src = hit.get("_source", {}) or {}
    # _id is "<accession-no-dashes>:<document>.htm"
    raw_id = str(hit.get("_id", ""))
    accession_raw = raw_id.split(":")[0]
    accession = (
        f"{accession_raw[:10]}-{accession_raw[10:12]}-{accession_raw[12:]}"
        if len(accession_raw) == 18 and "-" not in accession_raw
        else accession_raw
    )
    names = src.get("display_names") or []
    ciks = src.get("ciks") or []
    form = src.get("file_type") or src.get("root_form") or ""
    filed = src.get("file_date", "")

    url = ""
    if ciks and accession_raw:
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{str(ciks[0]).lstrip('0')}/"
            f"{accession_raw.replace('-', '')}/{accession}-index.htm"
        )

    return Record(
        source="sec_edgar",
        id=accession,
        title=f"{form} - {names[0]}" if names and form else (names[0] if names else form),
        authors=list(names),
        year=str(filed)[:4],
        venue="SEC EDGAR",
        doc_types=[form] if form else [],
        abstract=f"Filed: {filed} | Form: {form} | Filer: {'; '.join(names) or 'n/a'}",
        url=url,
    )


register(SECEdgar(), replace=True)
