"""Offline tests for the regulatory and registry sources.

No network: each test drives the response-mapping functions with a fixture
shaped like the upstream payload. This verifies the parsing, not the endpoint
contract - see research_core/sources/VERIFICATION.md for what remains unproven.
"""

import unittest

from research_core.sources.clinicaltrials import _to_record as ctg_record
from research_core.sources.cms import _to_record as cms_record
from research_core.sources.openfda import _to_record as fda_record
from research_core.sources.patentsview import _to_record as patent_record
from research_core.sources.sec_edgar import _to_record as sec_record
from research_core.sources.socrata import CDC
from research_core.verify import extract_citations


class ClinicalTrialsTests(unittest.TestCase):
    STUDY = {
        "hasResults": False,
        "protocolSection": {
            "identificationModule": {"nctId": "NCT03574597", "briefTitle": "SELECT"},
            "statusModule": {
                "overallStatus": "COMPLETED",
                "startDateStruct": {"date": "2018-10-31"},
                "completionDateStruct": {"date": "2023-09-27"},
            },
            "designModule": {
                "studyType": "INTERVENTIONAL",
                "phases": ["PHASE3"],
                "enrollmentInfo": {"count": 17604},
            },
            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Novo Nordisk"}},
            "descriptionModule": {"briefSummary": "A trial of semaglutide."},
        },
    }

    def test_core_fields(self):
        r = ctg_record(self.STUDY)
        self.assertEqual(r.id, "NCT03574597")
        self.assertEqual(r.title, "SELECT")
        self.assertEqual(r.year, "2018")
        self.assertEqual(r.authors, ["Novo Nordisk"])
        self.assertEqual(r.url, "https://clinicaltrials.gov/study/NCT03574597")

    def test_unposted_results_are_surfaced_not_hidden(self):
        # The publication-bias signal must be visible without a second call.
        r = ctg_record(self.STUDY)
        self.assertIn("Results posted: NO", r.abstract)
        self.assertIn("Status: COMPLETED", r.abstract)
        self.assertIn("Enrollment: 17604", r.abstract)

    def test_posted_results_flip_the_flag(self):
        study = {**self.STUDY, "hasResults": True}
        self.assertIn("Results posted: yes", ctg_record(study).abstract)

    def test_missing_modules_do_not_raise(self):
        r = ctg_record({"protocolSection": {}})
        self.assertEqual(r.id, "")
        self.assertIn("Results posted: NO", r.abstract)


class OpenFDATests(unittest.TestCase):
    def test_drugsfda_record(self):
        r = fda_record(
            {
                "application_number": "NDA215256",
                "sponsor_name": "Novo Nordisk",
                "products": [{"brand_name": "WEGOVY"}],
                "openfda": {"generic_name": ["SEMAGLUTIDE"]},
                "submissions": [{"submission_status_date": "20210604"}],
            },
            "drugsfda",
        )
        self.assertEqual(r.id, "NDA215256")
        self.assertEqual(r.title, "WEGOVY / SEMAGLUTIDE")
        self.assertEqual(r.year, "2021")
        self.assertIn("ApplNo=215256", r.url)

    def test_empty_products_does_not_crash(self):
        # Regression: products may be absent or empty on label/event records.
        r = fda_record({"application_number": "NDA1", "products": []}, "drugsfda")
        self.assertEqual(r.id, "NDA1")

    def test_record_with_no_identifiers_is_still_titled(self):
        r = fda_record({}, "event")
        self.assertEqual(r.title, "(untitled FDA record)")


class SECEdgarTests(unittest.TestCase):
    HIT = {
        "_id": "000156459021032395:d123456d10k.htm",
        "_source": {
            "display_names": ["NOVO NORDISK A/S (NVO)"],
            "ciks": ["0000353278"],
            "file_type": "10-K",
            "file_date": "2021-06-04",
        },
    }

    def test_accession_is_reformatted_with_dashes(self):
        self.assertEqual(sec_record(self.HIT).id, "0001564590-21-032395")

    def test_url_strips_leading_zeros_from_cik(self):
        self.assertIn("/data/353278/", sec_record(self.HIT).url)

    def test_title_combines_form_and_filer(self):
        r = sec_record(self.HIT)
        self.assertEqual(r.title, "10-K - NOVO NORDISK A/S (NVO)")
        self.assertEqual(r.year, "2021")

    def test_missing_source_does_not_raise(self):
        self.assertEqual(sec_record({"_id": "x"}).id, "x")


class PatentsViewTests(unittest.TestCase):
    def test_record(self):
        r = patent_record(
            {
                "patent_id": "10335464",
                "patent_title": "GLP-1 formulations",
                "patent_date": "2019-07-02",
                "patent_abstract": "An abstract.",
                "assignees": [{"assignee_organization": "Novo Nordisk A/S"}],
            }
        )
        self.assertEqual(r.id, "10335464")
        self.assertEqual(r.year, "2019")
        self.assertEqual(r.authors, ["Novo Nordisk A/S"])
        self.assertEqual(r.url, "https://patents.google.com/patent/US10335464")

    def test_assignee_without_organization_is_dropped(self):
        r = patent_record({"patent_id": "1", "assignees": [{"assignee_id": "x"}]})
        self.assertEqual(r.authors, [])


class CMSTests(unittest.TestCase):
    def test_dataset_id_taken_from_identifier_url(self):
        r = cms_record(
            {
                "identifier": "https://data.cms.gov/data-api/v1/dataset/abc-123/data",
                "title": "Medicare Part D Prescribers",
                "description": "Spend by prescriber.",
                "modified": "2026-03-01",
                "publisher": {"name": "CMS"},
            }
        )
        self.assertEqual(r.id, "abc-123")
        self.assertEqual(r.year, "2026")
        self.assertEqual(r.authors, ["CMS"])

    def test_missing_identifier_is_empty_not_an_error(self):
        self.assertEqual(cms_record({"title": "x"}).id, "")


class SocrataTests(unittest.TestCase):
    def test_catalog_item_maps_to_dataset_record(self):
        r = CDC()._to_record(
            {
                "resource": {
                    "id": "9mfq-cb36",
                    "name": "COVID-19 Case Surveillance",
                    "description": "Weekly counts.",
                    "updatedAt": "2026-01-15T00:00:00.000Z",
                },
                "owner": {"display_name": "CDC"},
                "permalink": "https://data.cdc.gov/d/9mfq-cb36",
            }
        )
        self.assertEqual(r.id, "9mfq-cb36")
        self.assertEqual(r.doc_types, ["dataset"])
        self.assertEqual(r.year, "2026")


class CrossSourcePatternTests(unittest.TestCase):
    """Identifier patterns must not claim each other's text."""

    def test_date_range_is_not_a_dataset_id(self):
        # Regression: every search log contains a range like this.
        self.assertEqual(extract_citations("Window 2020-2026 applied."), set())

    def test_each_identifier_maps_to_exactly_one_source(self):
        for text, expected in [
            ("PMID: 37356941", {"pubmed:37356941"}),
            ("10.1056/NEJMoa2307563", {"crossref:10.1056/NEJMoa2307563"}),
            ("NCT05198934", {"clinicaltrials:NCT05198934"}),
            ("0001234567-24-000123", {"sec_edgar:0001234567-24-000123"}),
            ("US10335464 B2", {"uspto:10335464"}),
            ("dataset 9mfq-cb36", {"cdc:9mfq-cb36"}),
            ("NDA215256", {"openfda:NDA215256"}),
        ]:
            with self.subTest(text=text):
                self.assertEqual(set(map(str, extract_citations(text))), expected)


if __name__ == "__main__":
    unittest.main()
