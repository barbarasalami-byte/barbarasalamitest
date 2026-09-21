"""Offline tests for the sources added from the engineering matrix."""

import unittest

from research_core import extract_citations
from research_core.agent import ReviewResult
from research_core.normalize import DrugIdentity, expand_query
from research_core.sources import Record, all_sources
from research_core.sources.nih_reporter import _to_record as nih_record
from research_core.sources.openfda import (
    _enforcement_record,
    _faers_record,
    _ndc_record,
)
from research_core.sources.sec_edgar import _submission_records
from research_core.sources.uspto_assignments import _to_record as assignment_record
from research_core.verify import audit_citations


class OpenFDAFamilyTests(unittest.TestCase):
    def test_each_endpoint_is_its_own_source_with_its_own_identifier(self):
        sources = all_sources()
        labels = {n: sources[n].id_label for n in sources if n.startswith(("fda_", "openfda"))}
        self.assertEqual(
            labels,
            {
                "openfda": "FDA-APP",
                "fda_label": "SPL-ID",
                "fda_faers": "FAERS-ID",
                "fda_ndc": "NDC",
                "fda_enforcement": "RECALL",
            },
        )

    def test_faers_surfaces_seriousness_and_reactions(self):
        r = _faers_record(
            {
                "safetyreportid": "12345678",
                "serious": "1",
                "seriousnessdeath": "1",
                "receiptdate": "20240115",
                "patient": {
                    "drug": [{"medicinalproduct": "WEGOVY"}],
                    "reaction": [{"reactionmeddrapt": "Pancreatitis"}],
                },
            }
        )
        self.assertEqual(r.id, "12345678")
        self.assertEqual(r.year, "2024")
        self.assertIn("Serious: yes", r.abstract)
        self.assertIn("Outcome: death", r.abstract)
        self.assertIn("Pancreatitis", r.abstract)

    def test_faers_without_patient_block_does_not_raise(self):
        self.assertEqual(_faers_record({"safetyreportid": "1"}).id, "1")

    def test_ndc_record(self):
        r = _ndc_record(
            {
                "product_ndc": "0169-4060",
                "brand_name": "OZEMPIC",
                "labeler_name": "Novo Nordisk",
                "dosage_form": "INJECTION",
                "route": ["SUBCUTANEOUS"],
                "active_ingredients": [{"name": "SEMAGLUTIDE"}],
                "marketing_start_date": "20171205",
            }
        )
        self.assertEqual(r.id, "0169-4060")
        self.assertEqual(r.year, "2017")
        self.assertIn("Labeler: Novo Nordisk", r.abstract)

    def test_enforcement_record_carries_classification(self):
        r = _enforcement_record(
            {
                "recall_number": "D-1234-2024",
                "classification": "Class II",
                "status": "Ongoing",
                "recalling_firm": "Acme Pharma",
                "product_description": "Tablets, 10mg",
                "recall_initiation_date": "20240301",
            }
        )
        self.assertEqual(r.id, "D-1234-2024")
        self.assertIn("Classification: Class II", r.abstract)


class SECSubmissionsTests(unittest.TestCase):
    PAYLOAD = {
        "cik": "353278",
        "name": "NOVO NORDISK A/S",
        "filings": {
            "recent": {
                "accessionNumber": ["0001564590-21-032395", "0001564590-21-000001"],
                "form": ["10-K", "4"],
                "filingDate": ["2021-06-04", "2021-01-05"],
                "primaryDocument": ["d123.htm", "form4.xml"],
            }
        },
    }

    def test_parallel_arrays_flatten_into_records(self):
        records = _submission_records(self.PAYLOAD, 25)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].id, "0001564590-21-032395")
        self.assertEqual(records[0].doc_types, ["10-K"])
        self.assertIn("/data/353278/000156459021032395/d123.htm", records[0].url)

    def test_ragged_arrays_do_not_raise(self):
        payload = {
            "cik": "1",
            "name": "X",
            "filings": {"recent": {"accessionNumber": ["0001-21-000001"], "form": []}},
        }
        self.assertEqual(len(_submission_records(payload, 25)), 1)

    def test_limit_is_respected(self):
        self.assertEqual(len(_submission_records(self.PAYLOAD, 1)), 1)


class NIHReporterTests(unittest.TestCase):
    def test_record(self):
        r = nih_record(
            {
                "appl_id": 10554321,
                "project_title": "GLP-1 signalling in obesity",
                "fiscal_year": 2024,
                "award_amount": 512000,
                "organization": {"org_name": "Stanford University"},
                "principal_investigators": [{"full_name": "Doe, Jane"}],
                "abstract_text": "An abstract.",
            }
        )
        self.assertEqual(r.id, "10554321")
        self.assertEqual(r.year, "2024")
        self.assertEqual(r.authors, ["Doe, Jane"])
        self.assertIn("Award: $512,000", r.abstract)
        self.assertIn("reporter.nih.gov/project-details/10554321", r.url)

    def test_missing_pi_falls_back_to_institution(self):
        r = nih_record({"appl_id": 1, "organization": {"org_name": "MIT"}})
        self.assertEqual(r.authors, ["MIT"])


class AssignmentTests(unittest.TestCase):
    def test_record_shows_direction_of_transfer(self):
        r = assignment_record(
            {
                "reelNo": "58234",
                "frameNo": "0912",
                "assignorName": ["SmallBio Inc"],
                "assigneeName": ["BigPharma AG"],
                "patNum": ["10335464"],
                "conveyanceText": "ASSIGNMENT OF ASSIGNORS INTEREST",
                "recordedDate": "2024-05-02",
            }
        )
        self.assertEqual(r.id, "58234/0912")
        self.assertIn("SmallBio Inc", r.title)
        self.assertIn("BigPharma AG", r.title)
        self.assertIn("Conveyance: ASSIGNMENT", r.abstract)

    def test_scalar_fields_are_accepted_as_well_as_lists(self):
        r = assignment_record(
            {"reelNo": "1", "frameNo": "2", "assigneeName": "Solo Corp"}
        )
        self.assertEqual(r.authors, ["Solo Corp"])


class NamespaceTests(unittest.TestCase):
    """Sources sharing an id_label share an identifier namespace."""

    def test_one_accession_yields_one_citation_not_three(self):
        # Regression: sec_edgar, sec_submissions and sec_insider all match
        # accession numbers; three citations meant two always failed the audit.
        found = extract_citations("Filing 0001234567-24-000123 discloses risk.")
        self.assertEqual(len(found), 1)

    def test_retrieval_by_a_namespace_peer_satisfies_the_citation(self):
        result = ReviewResult(
            report="See 0001234567-24-000123.",
            records={
                "sec_submissions:0001234567-24-000123": Record(
                    source="sec_submissions", id="0001234567-24-000123", title="t"
                )
            },
        )
        self.assertTrue(audit_citations(result).ok)

    def test_unrelated_sources_do_not_pool_identifiers(self):
        result = ReviewResult(
            report="See PMID: 37356941.",
            records={
                "clinicaltrials:37356941": Record(
                    source="clinicaltrials", id="37356941", title="t"
                )
            },
        )
        self.assertFalse(audit_citations(result).ok)

    def test_ndc_requires_its_label_so_date_ranges_are_safe(self):
        self.assertEqual(extract_citations("Window 2020-2026 applied."), set())
        self.assertEqual(
            {c.id for c in extract_citations("NDC 0169-4060 listed.")}, {"0169-4060"}
        )


class NormalizerTests(unittest.TestCase):
    def test_aliases_are_ordered_and_deduplicated(self):
        identity = DrugIdentity(
            rxcui="1991302",
            name="semaglutide",
            brand_names=["Ozempic", "Wegovy"],
            ingredients=["semaglutide"],
            synonyms=["Semaglutide 1 MG/ML"],
        )
        self.assertEqual(
            identity.query_aliases(),
            ["semaglutide", "Ozempic", "Wegovy", "Semaglutide 1 MG/ML"],
        )

    def test_unknown_drug_falls_back_to_the_raw_name(self):
        # Investigational compounds often have no RxCUI; that is an answer,
        # not an error, and callers should not have to branch on it.
        class NoMatch:
            def resolve(self, name):
                return None

        self.assertEqual(expand_query("XYZ-1234", NoMatch()), ["XYZ-1234"])

    def test_normalizer_is_not_registered_as_a_source(self):
        self.assertNotIn("rxnorm", all_sources())


if __name__ == "__main__":
    unittest.main()
