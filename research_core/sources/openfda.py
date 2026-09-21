"""openFDA sources - the FDA drug endpoints at api.fda.gov.

This is where CDER data lives. CDER is a centre within FDA, not a separate
API: drug approvals, labelling, adverse events, NDC and enforcement records
published by CDER are all served here.

Each endpoint is registered as its own source because each answers a different
question with a different identifier - and a distinct identifier is what lets
the citation audit tell them apart.

    openfda          drug/drugsfda     approvals, application history, TE codes
    fda_label        drug/label        current structured product labelling
    fda_faers        drug/event        adverse event reports (spontaneous)
    fda_ndc          drug/ndc          National Drug Code directory
    fda_enforcement  drug/enforcement  recalls and enforcement actions

Not covered here: CBER biologics and the Purple Book, which FDA publishes as
bulk CSV rather than through this API. See VERIFICATION.md.
"""

from __future__ import annotations

import re
from typing import Any

from .base import Record
from .registry import register
from .rest import JSONSource, first

BASE = "https://api.fda.gov/drug"

_SHARED_NOTE = """\
Lucene-style `search` syntax: field:value, quoted phrases, AND/OR, and
`[start+TO+end]` ranges on dates.

    openfda.generic_name:"semaglutide"
    sponsor_name:"Novo Nordisk" AND submissions.submission_status_date:[20200101+TO+20261231]\
"""


class _OpenFDABase(JSONSource):
    ENDPOINT = ""
    RATE_PER_SECOND = 3.0
    API_KEY_ENV = "OPENFDA_API_KEY"  # optional; raises 1k/day to 240/min

    def _search_url(self) -> str:
        return f"{BASE}/{self.ENDPOINT}.json"

    def _search_params(self, query: str, max_results: int) -> dict[str, Any]:
        params: dict[str, Any] = {"search": query, "limit": max_results}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def _total_from(self, payload: dict[str, Any]) -> int:
        return int((payload.get("meta", {}).get("results", {}) or {}).get("total", 0))

    def _id_field(self) -> str:
        raise NotImplementedError

    def _fetch_one(self, record_id: str) -> Record | None:
        payload = self._get(
            self._search_url(),
            self._search_params(f'{self._id_field()}:"{record_id}"', 1),
        )
        records = self._records_from(payload)
        return records[0] if records else None


class DrugsFDA(_OpenFDABase):
    """Approvals and application history, with Orange Book TE codes."""

    name = "openfda"
    id_label = "FDA-APP"
    id_patterns = [re.compile(r"\b((?:NDA|ANDA|BLA)\d{6})\b", re.IGNORECASE)]
    ENDPOINT = "drugsfda"
    syntax_guide = f"""\
### openFDA drugsfda (approvals, CDER)

{_SHARED_NOTE}

Records carry application number, sponsor, products, and submission history.
Orange Book therapeutic-equivalence codes appear per product as `te_code`; use
them for generic substitutability, not as a claim about clinical equivalence.\
"""

    def _id_field(self) -> str:
        return "application_number"

    def _records_from(self, payload: dict[str, Any]) -> list[Record]:
        return [_approval_record(r) for r in payload.get("results", [])]


class DrugLabel(_OpenFDABase):
    """Current structured product labelling."""

    name = "fda_label"
    id_label = "SPL-ID"
    id_patterns = [
        re.compile(r"\bSPL[:\s]\s*([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b")
    ]
    ENDPOINT = "label"
    syntax_guide = f"""\
### openFDA label (structured product labelling)

{_SHARED_NOTE}

Returns the *current* label. It is not a history: a label that has changed
shows only today's text, so it cannot answer "when did the warning appear".
For that, compare against an archived copy.\
"""

    def _id_field(self) -> str:
        return "id"

    def _records_from(self, payload: dict[str, Any]) -> list[Record]:
        return [_label_record(r) for r in payload.get("results", [])]


class FAERS(_OpenFDABase):
    """Adverse event reports."""

    name = "fda_faers"
    id_label = "FAERS-ID"
    id_patterns = [re.compile(r"\bFAERS[:\s]\s*(\d{6,12})\b", re.IGNORECASE)]
    ENDPOINT = "event"
    syntax_guide = f"""\
### openFDA event (FAERS adverse event reports)

{_SHARED_NOTE}

**FAERS is spontaneous reporting.** A count has no denominator, so it is not an
incidence rate, and a report is not evidence of causation. Reporting volume
tracks publicity and market size as much as risk. Never present a FAERS count
as a rate, and never compare raw counts between drugs with different exposure.\
"""

    def _id_field(self) -> str:
        return "safetyreportid"

    def _records_from(self, payload: dict[str, Any]) -> list[Record]:
        return [_faers_record(r) for r in payload.get("results", [])]


class NDC(_OpenFDABase):
    """National Drug Code directory."""

    name = "fda_ndc"
    id_label = "NDC"
    # A bare NDC is indistinguishable from a year range (2020-2026) or the tail
    # of a recall number (D-1234-2024), so the label is required. The syntax
    # guide tells the model to cite NDCs that way.
    id_patterns = [
        re.compile(r"\bNDC[:\s]\s*(\d{4,5}-\d{3,4}(?:-\d{1,2})?)\b", re.IGNORECASE)
    ]
    ENDPOINT = "ndc"
    syntax_guide = f"""\
### openFDA ndc (National Drug Code directory)

{_SHARED_NOTE}

The labeler code (the first segment of an NDC) maps a product back to its
manufacturing parent. That mapping is the join key between marketed products
and corporate entities - useful, but labeler codes are reassigned over time,
so treat a historical NDC's labeler with care.

Always write an NDC with its label - `NDC 0169-4060` - never bare. A bare
number cannot be told apart from a date range and will not be verified.\
"""

    def _id_field(self) -> str:
        return "product_ndc"

    def _records_from(self, payload: dict[str, Any]) -> list[Record]:
        return [_ndc_record(r) for r in payload.get("results", [])]


class Enforcement(_OpenFDABase):
    """Recalls and enforcement actions."""

    name = "fda_enforcement"
    id_label = "RECALL"
    id_patterns = [re.compile(r"\b([DFZ]-\d{3,4}-\d{4})\b")]
    ENDPOINT = "enforcement"
    syntax_guide = f"""\
### openFDA enforcement (recalls)

{_SHARED_NOTE}

Classification is FDA's judgement of hazard: Class I (serious harm or death),
II (temporary or reversible), III (unlikely harm). A recall is a supply and
quality signal, not by itself evidence of patient harm.

This endpoint covers recalls. Inspection classifications (NAI/VAI/OAI) and
warning letters come from the FDA Data Dashboard, a separate bulk source this
provider does not reach.\
"""

    def _id_field(self) -> str:
        return "recall_number"

    def _records_from(self, payload: dict[str, Any]) -> list[Record]:
        return [_enforcement_record(r) for r in payload.get("results", [])]


# --- record mapping -------------------------------------------------------


def _approval_record(item: dict[str, Any]) -> Record:
    openfda = item.get("openfda", {}) or {}
    app_no = item.get("application_number") or first(openfda.get("application_number"))
    products = item.get("products") or []
    brand = first(openfda.get("brand_name")) or (
        first(products[0].get("brand_name")) if products else ""
    )
    generic = first(openfda.get("generic_name"))
    sponsor = item.get("sponsor_name", "")
    submissions = item.get("submissions", []) or []
    latest = max((s.get("submission_status_date", "") for s in submissions), default="")
    te_codes = sorted({p.get("te_code", "") for p in products if p.get("te_code")})

    detail = [
        f"Sponsor: {sponsor}" if sponsor else "",
        f"Application: {app_no}" if app_no else "",
        f"Products: {len(products)}" if products else "",
        f"TE codes: {', '.join(te_codes)}" if te_codes else "",
        f"Submissions: {len(submissions)}" if submissions else "",
        f"Latest action: {latest}" if latest else "",
    ]
    return Record(
        source="openfda",
        id=app_no or "",
        title=" / ".join(p for p in (brand, generic) if p) or app_no or "(untitled)",
        authors=[sponsor] if sponsor else [],
        year=latest[:4],
        venue="FDA Drugs@FDA",
        doc_types=["approval"],
        abstract=" | ".join(d for d in detail if d),
        url=(
            "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
            f"?event=overview.process&ApplNo={app_no[-6:]}"
            if app_no
            else ""
        ),
    )


def _label_record(item: dict[str, Any]) -> Record:
    openfda = item.get("openfda", {}) or {}
    label_id = item.get("id", "")
    indications = first(item.get("indications_and_usage"))
    return Record(
        source="fda_label",
        id=label_id,
        title=first(openfda.get("brand_name")) or first(openfda.get("generic_name")) or label_id,
        authors=[first(openfda.get("manufacturer_name"))] if openfda.get("manufacturer_name") else [],
        year=str(item.get("effective_time", ""))[:4],
        venue="FDA SPL",
        doc_types=["label"],
        abstract=indications[:2000],
        url=f"https://labels.fda.gov/{label_id}" if label_id else "",
    )


def _faers_record(item: dict[str, Any]) -> Record:
    patient = item.get("patient", {}) or {}
    drugs = [
        d.get("medicinalproduct", "")
        for d in (patient.get("drug") or [])
        if d.get("medicinalproduct")
    ]
    reactions = [
        r.get("reactionmeddrapt", "")
        for r in (patient.get("reaction") or [])
        if r.get("reactionmeddrapt")
    ]
    report_id = str(item.get("safetyreportid", ""))
    serious = item.get("serious")
    detail = [
        f"Serious: {'yes' if str(serious) == '1' else 'no'}" if serious is not None else "",
        "Outcome: death" if str(item.get("seriousnessdeath", "")) == "1" else "",
        f"Drugs: {', '.join(drugs[:6])}" if drugs else "",
        f"Reactions: {', '.join(reactions[:8])}" if reactions else "",
    ]
    return Record(
        source="fda_faers",
        id=report_id,
        title=f"FAERS report {report_id}" + (f" - {reactions[0]}" if reactions else ""),
        authors=[],
        year=str(item.get("receiptdate", ""))[:4],
        venue="FDA FAERS",
        doc_types=["adverse event report"],
        abstract=" | ".join(d for d in detail if d),
        url="",
    )


def _ndc_record(item: dict[str, Any]) -> Record:
    ndc = item.get("product_ndc", "")
    ingredients = [
        a.get("name", "") for a in (item.get("active_ingredients") or []) if a.get("name")
    ]
    labeler = item.get("labeler_name", "")
    detail = [
        f"Labeler: {labeler}" if labeler else "",
        f"Dosage form: {item.get('dosage_form', '')}" if item.get("dosage_form") else "",
        f"Route: {first(item.get('route'))}" if item.get("route") else "",
        f"Active: {', '.join(ingredients)}" if ingredients else "",
    ]
    return Record(
        source="fda_ndc",
        id=ndc,
        title=item.get("brand_name", "") or item.get("generic_name", "") or ndc,
        authors=[labeler] if labeler else [],
        year=str(item.get("marketing_start_date", ""))[:4],
        venue="FDA NDC Directory",
        doc_types=["ndc"],
        abstract=" | ".join(d for d in detail if d),
        url="",
    )


def _enforcement_record(item: dict[str, Any]) -> Record:
    recall = item.get("recall_number", "")
    detail = [
        f"Classification: {item.get('classification', '')}" if item.get("classification") else "",
        f"Status: {item.get('status', '')}" if item.get("status") else "",
        f"Firm: {item.get('recalling_firm', '')}" if item.get("recalling_firm") else "",
        f"Reason: {item.get('reason_for_recall', '')}" if item.get("reason_for_recall") else "",
    ]
    return Record(
        source="fda_enforcement",
        id=recall,
        title=(item.get("product_description", "") or recall)[:200],
        authors=[item.get("recalling_firm", "")] if item.get("recalling_firm") else [],
        year=str(item.get("recall_initiation_date", ""))[:4],
        venue="FDA Enforcement",
        doc_types=["recall"],
        abstract=" | ".join(d for d in detail if d),
        url="",
    )


for _provider in (DrugsFDA(), DrugLabel(), FAERS(), NDC(), Enforcement()):
    register(_provider, replace=True)
