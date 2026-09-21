"""CMS spending and Open Payments.

Two sources, both Socrata-shaped, both about money:

    cms_spending      Part D / Part B / Medicaid drug spending dashboards
    cms_open_payments industry payments to physicians and teaching hospitals

`cms.py` remains the dataset-catalogue provider. These two query rows.
"""

from __future__ import annotations

import re
from typing import Any

from .base import Record
from .registry import register
from .rest import JSONSource

SPEND_SYNTAX = """\
### CMS drug spending

Socrata SoQL over the Medicare/Medicaid drug spending datasets. Filter with
`$where`, or pass plain keywords to match brand and generic name:

    semaglutide
    $where=Brnd_Name like '%WEGOVY%'

Per drug per year: total spending, claims, beneficiaries, dosage units,
average spend per dosage unit.

**Spending is gross, not net of rebate.** Confidential rebates are material in
this market, so CMS gross spend is an upper bound on what was actually paid,
not a price. Never present it as net. Year-over-year change in gross spend
also moves with utilisation, not only price.\
"""

PAYMENTS_SYNTAX = """\
### CMS Open Payments

Socrata SoQL over industry payments to physicians and teaching hospitals.

    $where=Applicable_Manufacturer_or_GPO_Making_Payment_Name like '%Novo%'

Shows who a manufacturer paid, how much, and under what nature of payment -
consulting, speaking, travel, research.

A payment is a commercial relationship, not evidence of bias or wrongdoing.
Research payments in particular are ordinary trial funding. Naming individual
physicians carries real reputational weight: report aggregates unless the
question genuinely requires a named recipient.\
"""


class _SocrataRows(JSONSource):
    """Query rows from one Socrata dataset."""

    DOMAIN = ""
    DATASET = ""
    APP_TOKEN_ENV = "SOCRATA_APP_TOKEN"

    def __init__(self) -> None:
        self.API_KEY_ENV = self.APP_TOKEN_ENV
        super().__init__()
        if self.api_key:
            self._session.headers["X-App-Token"] = self.api_key

    def available(self) -> tuple[bool, str]:
        if not self.DATASET:
            return False, f"{self.name}: no dataset id configured (see VERIFICATION.md)"
        if not self.api_key:
            return True, "no SOCRATA_APP_TOKEN; subject to shared rate throttles"
        return True, ""

    def _search_url(self) -> str:
        return f"https://{self.DOMAIN}/resource/{self.DATASET}.json"

    def _search_params(self, query: str, max_results: int) -> dict[str, Any]:
        # A raw SoQL fragment passes through; anything else is full-text search.
        if query.strip().startswith("$"):
            key, _, value = query.partition("=")
            return {key.strip(): value.strip(), "$limit": max_results}
        return {"$q": query, "$limit": max_results}

    def _total_from(self, payload: Any) -> int:
        return len(payload) if isinstance(payload, list) else 0

    def _get_rows(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        result = self._get(self._search_url(), params)
        return result if isinstance(result, list) else []

    def search(self, query: str, max_results: int = 25):  # type: ignore[override]
        from .base import SearchOutcome

        rows = self._get_rows(self._search_params(query, max(1, min(max_results, 100))))
        return SearchOutcome(
            source=self.name,
            query=query,
            total_matches=len(rows),
            records=[self._row_record(r, i) for i, r in enumerate(rows)],
        )

    def _row_record(self, row: dict[str, Any], index: int) -> Record:
        raise NotImplementedError

    def _records_from(self, payload: dict[str, Any]) -> list[Record]:
        return []

    def _fetch_one(self, record_id: str) -> Record | None:
        return None

    def fetch(self, ids: list[str]) -> list[Record]:
        return []

    def exists(self, record_id: str) -> bool:
        # Rows have no stable public identifier; a cited figure is verified by
        # re-running the query, which the search log records verbatim.
        return False


class CMSSpending(_SocrataRows):
    name = "cms_spending"
    id_label = "CMS-SPEND"
    id_patterns: list[re.Pattern[str]] = []
    syntax_guide = SPEND_SYNTAX
    DOMAIN = "data.cms.gov"
    DATASET = ""  # set per dashboard year; see VERIFICATION.md

    def _row_record(self, row: dict[str, Any], index: int) -> Record:
        brand = row.get("Brnd_Name") or row.get("brand_name") or ""
        generic = row.get("Gnrc_Name") or row.get("generic_name") or ""
        return Record(
            source=self.name,
            id=f"{brand or generic}:{index}",
            title=" / ".join(p for p in (brand, generic) if p) or "(row)",
            venue="CMS drug spending",
            doc_types=["spending row"],
            abstract=" | ".join(f"{k}: {v}" for k, v in list(row.items())[:12]),
        )


class CMSOpenPayments(_SocrataRows):
    name = "cms_open_payments"
    id_label = "PAYMENT-ID"
    id_patterns = [re.compile(r"\bOPID[:\s]\s*(\d{6,12})\b", re.IGNORECASE)]
    syntax_guide = PAYMENTS_SYNTAX
    DOMAIN = "openpaymentsdata.cms.gov"
    DATASET = ""  # set per program year; see VERIFICATION.md

    def _row_record(self, row: dict[str, Any], index: int) -> Record:
        manufacturer = row.get("applicable_manufacturer_or_gpo_making_payment_name", "")
        amount = row.get("total_amount_of_payment_usdollars", "")
        nature = row.get("nature_of_payment_or_transfer_of_value", "")
        return Record(
            source=self.name,
            id=str(row.get("record_id", index)),
            title=f"{manufacturer} payment" if manufacturer else "(payment)",
            authors=[manufacturer] if manufacturer else [],
            year=str(row.get("program_year", ""))[:4],
            venue="CMS Open Payments",
            doc_types=["payment"],
            abstract=f"Amount: {amount} | Nature: {nature}",
        )


register(CMSSpending(), replace=True)
register(CMSOpenPayments(), replace=True)
