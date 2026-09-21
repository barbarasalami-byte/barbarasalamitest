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


class SECSubmissions(JSONSource):
    """A company's filing history from the documented submissions API.

    Complements full-text search rather than replacing it. Full-text answers
    "which filings mention semaglutide"; this answers "every filing Novo
    Nordisk made". Queries take a CIK (10 digits, zero-padded) or a ticker.
    """

    name = "sec_submissions"
    id_label = "ACCESSION"
    id_patterns = [re.compile(r"\b(\d{10}-\d{2}-\d{6})\b")]
    syntax_guide = """\
### SEC EDGAR submissions (company filing history)

Query by CIK or ticker, not by text:

    CIK0000353278
    NVO

Returns the filer's recent filings with form type, date, and accession number.
Use this when the question is about one company; use full-text search when the
question is about a phrase. Forms worth knowing: 10-K annual, 10-Q quarterly,
8-K material events (trial results, regulatory actions), 20-F/40-F foreign
issuers, S-1 registration.

A filing is the company's own assertion, made under legal obligation but not
independently verified. Attribute it to the filer.\
"""

    BASE = "https://data.sec.gov/submissions"
    RATE_PER_SECOND = 8.0
    CONTACT_ENV = "SEC_CONTACT_EMAIL"

    def available(self) -> tuple[bool, str]:
        if not self.contact:
            return False, "SEC_CONTACT_EMAIL not set; the SEC blocks anonymous traffic"
        return True, ""

    def _cik_url(self, identifier: str) -> str:
        digits = "".join(c for c in str(identifier) if c.isdigit())
        return f"{self.BASE}/CIK{digits.zfill(10)}.json"

    def search(self, query: str, max_results: int = 25):  # type: ignore[override]
        from .base import SearchOutcome

        payload = self._get(self._cik_url(query))
        records = _submission_records(payload, max_results)
        recent = (payload.get("filings", {}) or {}).get("recent", {}) or {}
        return SearchOutcome(
            source=self.name,
            query=query,
            total_matches=len(recent.get("accessionNumber", []) or []),
            records=records,
        )

    def fetch(self, ids: list[str]) -> list[Record]:
        # Accession numbers are not addressable on their own here; the caller
        # already holds the metadata from search.
        return []

    def exists(self, record_id: str) -> bool:
        # Structural check only: this API is keyed by company, not accession.
        return bool(re.fullmatch(r"\d{10}-\d{2}-\d{6}", record_id))

    def _search_params(self, query: str, max_results: int) -> dict[str, Any]:
        raise NotImplementedError  # search() is overridden

    def _records_from(self, payload: dict[str, Any]) -> list[Record]:
        return _submission_records(payload, 25)

    def _fetch_one(self, record_id: str) -> Record | None:
        return None


def _submission_records(payload: dict[str, Any], limit: int) -> list[Record]:
    """Flatten the parallel-array `filings.recent` structure into records."""
    name = payload.get("name", "")
    cik = str(payload.get("cik", ""))
    recent = (payload.get("filings", {}) or {}).get("recent", {}) or {}

    accessions = recent.get("accessionNumber", []) or []
    forms = recent.get("form", []) or []
    dates = recent.get("filingDate", []) or []
    docs = recent.get("primaryDocument", []) or []

    records = []
    for i, accession in enumerate(accessions[:limit]):
        form = forms[i] if i < len(forms) else ""
        filed = dates[i] if i < len(dates) else ""
        doc = docs[i] if i < len(docs) else ""
        bare = accession.replace("-", "")
        records.append(
            Record(
                source="sec_submissions",
                id=accession,
                title=f"{form} - {name}" if form and name else (name or form),
                authors=[name] if name else [],
                year=str(filed)[:4],
                venue="SEC EDGAR",
                doc_types=[form] if form else [],
                abstract=f"Filed: {filed} | Form: {form} | CIK: {cik}",
                url=(
                    f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{bare}/{doc}"
                    if cik and doc
                    else ""
                ),
            )
        )
    return records


class SECInsider(SECSubmissions):
    """Insider transactions - Forms 3, 4 and 5 from a company's submissions.

    Form 4 filings cluster before clinical readouts and earnings. The signal is
    in the pattern, not one filing: a single sale may be a scheduled 10b5-1
    disposal with no informational content at all.
    """

    name = "sec_insider"
    syntax_guide = """\
### SEC insider transactions (Forms 3, 4, 5)

Query by CIK or ticker; results are filtered to ownership forms. Form 3 is an
initial statement, Form 4 a change in ownership, Form 5 an annual catch-up.

Never read a single Form 4 as a signal. Many sales are pre-scheduled 10b5-1
plans with no relation to non-public information. A cluster of unscheduled
purchases ahead of a readout is a pattern worth reporting; one disposal is not.\
"""

    FORMS = {"3", "4", "5", "3/A", "4/A", "5/A"}

    def search(self, query: str, max_results: int = 25):  # type: ignore[override]
        outcome = super().search(query, max_results * 4)
        filtered = [
            r for r in outcome.records if any(f in self.FORMS for f in r.doc_types)
        ][:max_results]
        for record in filtered:
            record.source = self.name
        outcome.source = self.name
        outcome.records = filtered
        outcome.total_matches = len(filtered)
        return outcome


register(SECSubmissions(), replace=True)
register(SECInsider(), replace=True)
