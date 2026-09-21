"""Drug identity normalisation via RxNorm / RxNav.

**This is deliberately not a source provider.** Every other module in
`sources/` answers a research question and produces citable evidence. RxNorm
answers none: an RxCUI is not a finding and nobody cites one in a report. It is
a join key.

That distinction matters for the architecture. Sources fan out and their
results get audited; the normaliser sits underneath and makes the results
joinable in the first place. Forcing it into `SourceProvider` would have
given the model two search tools that look alike and do unrelated things.

Why it is needed: every source names drugs differently. FDA has brand and
generic names plus application numbers; CMS has its own brand/generic columns;
ClinicalTrials.gov has free-text intervention names; PubMed has MeSH terms;
patents use chemical names. Joining across them on a name string fails on
salt forms, combinations, and spelling. RxCUI is the identifier that holds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import requests

from .sources.base import RateLimiter

BASE = "https://rxnav.nlm.nih.gov/REST"

log = logging.getLogger(__name__)


@dataclass
class DrugIdentity:
    """One normalised drug, with the aliases each source is likely to use."""

    rxcui: str
    name: str
    term_type: str = ""
    synonyms: list[str] = field(default_factory=list)
    brand_names: list[str] = field(default_factory=list)
    ingredients: list[str] = field(default_factory=list)
    atc_codes: list[str] = field(default_factory=list)

    def query_aliases(self) -> list[str]:
        """Names worth searching across sources, most specific first."""
        seen, out = set(), []
        for candidate in [self.name, *self.brand_names, *self.ingredients, *self.synonyms]:
            key = candidate.strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(candidate.strip())
        return out


class RxNorm:
    """Resolve drug names to RxCUIs. Open access, no key."""

    def __init__(self) -> None:
        self._limiter = RateLimiter(15.0)  # guidance: <= 20/s
        self._session = requests.Session()
        self._session.headers["Accept"] = "application/json"
        self._cache: dict[str, DrugIdentity | None] = {}

    def _get(self, path: str, **params: str) -> dict:
        self._limiter.wait()
        response = self._session.get(f"{BASE}/{path}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def resolve(self, name: str) -> DrugIdentity | None:
        """Resolve a drug name to its identity, or None if RxNorm does not know it.

        None is a real answer, not an error: investigational compounds that have
        no approved product often have no RxCUI. Treat it as "not yet marketed"
        rather than "not a drug", and fall back to the raw name for searching.
        """
        key = name.strip().lower()
        if key in self._cache:
            return self._cache[key]

        try:
            payload = self._get("rxcui.json", name=name, search="2")
            ids = ((payload.get("idGroup", {}) or {}).get("rxnormId") or [])
            identity = self._hydrate(ids[0], name) if ids else None
        except requests.RequestException as exc:
            log.warning("RxNorm lookup of %r failed: %s", name, exc)
            return None

        self._cache[key] = identity
        return identity

    def _hydrate(self, rxcui: str, fallback_name: str) -> DrugIdentity:
        identity = DrugIdentity(rxcui=rxcui, name=fallback_name)
        try:
            props = self._get(f"rxcui/{rxcui}/properties.json").get("properties", {}) or {}
            identity.name = props.get("name", fallback_name)
            identity.term_type = props.get("tty", "")

            related = self._get(f"rxcui/{rxcui}/related.json", tty="IN+BN+SCD")
            for group in (related.get("relatedGroup", {}) or {}).get("conceptGroup", []) or []:
                names = [
                    c.get("name", "")
                    for c in (group.get("conceptProperties") or [])
                    if c.get("name")
                ]
                if group.get("tty") == "IN":
                    identity.ingredients = names
                elif group.get("tty") == "BN":
                    identity.brand_names = names
                else:
                    identity.synonyms.extend(names)
        except requests.RequestException as exc:
            log.info("RxNorm enrichment of %s incomplete: %s", rxcui, exc)
        return identity

    def ndcs(self, rxcui: str) -> list[str]:
        """NDCs for an RxCUI - the join to FDA NDC and to CMS utilisation."""
        try:
            payload = self._get(f"rxcui/{rxcui}/ndcs.json")
        except requests.RequestException:
            return []
        return list((payload.get("ndcGroup", {}) or {}).get("ndcList", {}).get("ndc", []) or [])


def expand_query(name: str, rxnorm: RxNorm | None = None) -> list[str]:
    """Aliases to search across sources for one drug name.

    Returns `[name]` unchanged when RxNorm has no entry, so a caller never has
    to branch on the miss.
    """
    identity = (rxnorm or RxNorm()).resolve(name)
    return identity.query_aliases() if identity else [name]
