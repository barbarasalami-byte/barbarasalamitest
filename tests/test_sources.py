"""Offline tests: PubMed XML parsing, the registry, and source-agnosticism."""

import re
import unittest

from research_core.sources import Record, SearchOutcome, SourceProvider, registry
from research_core.sources.pubmed import parse_articles

FIXTURE = """<?xml version="1.0"?>
<PubmedArticleSet>
 <PubmedArticle>
  <MedlineCitation>
   <PMID Version="1">37356941</PMID>
   <Article>
    <Journal>
     <ISOAbbreviation>N Engl J Med</ISOAbbreviation>
     <JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue>
    </Journal>
    <ArticleTitle>Semaglutide and <i>cardiovascular</i> outcomes.</ArticleTitle>
    <Abstract>
     <AbstractText Label="BACKGROUND">Obesity raises risk.</AbstractText>
     <AbstractText Label="RESULTS">HR was 0.80.</AbstractText>
    </Abstract>
    <AuthorList>
     <Author><LastName>Lincoff</LastName><Initials>AM</Initials></Author>
     <Author><CollectiveName>SELECT Investigators</CollectiveName></Author>
    </AuthorList>
    <PublicationTypeList>
     <PublicationType>Randomized Controlled Trial</PublicationType>
    </PublicationTypeList>
   </Article>
  </MedlineCitation>
 </PubmedArticle>
 <PubmedArticle>
  <MedlineCitation>
   <PMID Version="1">30122560</PMID>
   <Article>
    <Journal>
     <ISOAbbreviation>Lancet</ISOAbbreviation>
     <JournalIssue><PubDate><MedlineDate>2018 Aug-Sep</MedlineDate></PubDate></JournalIssue>
    </Journal>
    <ArticleTitle>An unstructured abstract study.</ArticleTitle>
    <Abstract><AbstractText>No label here.</AbstractText></Abstract>
   </Article>
  </MedlineCitation>
 </PubmedArticle>
</PubmedArticleSet>
"""


class PubMedParseTests(unittest.TestCase):
    def setUp(self):
        self.records = parse_articles(FIXTURE)

    def test_parses_every_record(self):
        self.assertEqual([r.id for r in self.records], ["37356941", "30122560"])

    def test_inline_markup_in_title_is_flattened(self):
        self.assertEqual(self.records[0].title, "Semaglutide and cardiovascular outcomes.")

    def test_structured_abstract_keeps_labels(self):
        self.assertIn("BACKGROUND: Obesity raises risk.", self.records[0].abstract)
        self.assertIn("RESULTS: HR was 0.80.", self.records[0].abstract)

    def test_unstructured_abstract_has_no_label_prefix(self):
        self.assertEqual(self.records[1].abstract, "No label here.")

    def test_collective_author_is_skipped_not_blank(self):
        self.assertEqual(self.records[0].authors, ["Lincoff AM"])

    def test_medline_date_falls_back_to_year(self):
        self.assertEqual(self.records[1].year, "2018")

    def test_citation_key_is_source_scoped(self):
        self.assertEqual(self.records[0].citation_key(), "pubmed:37356941")


class FakeSource:
    """A minimal third-party source - the whole extension surface."""

    name = "fakedb"
    id_label = "FAKEID"
    id_patterns = [re.compile(r"\bFAKEID[:\s]\s*([A-Z]\d{3})\b")]
    syntax_guide = "### FakeDB\n\nQuery with plain keywords."

    def __init__(self, usable=True):
        self._usable = usable

    def available(self):
        return (True, "") if self._usable else (False, "FAKEDB_KEY not set")

    def search(self, query, max_results=25):
        return SearchOutcome(
            source=self.name,
            query=query,
            total_matches=1,
            records=[Record(source=self.name, id="A001", title="A fake paper")],
        )

    def fetch(self, ids):
        return [Record(source=self.name, id=i, title="A fake paper") for i in ids]

    def exists(self, record_id):
        return record_id == "A001"


class RegistryTests(unittest.TestCase):
    def tearDown(self):
        registry.unregister("fakedb")

    def test_custom_source_satisfies_the_protocol(self):
        self.assertIsInstance(FakeSource(), SourceProvider)

    def test_register_and_discover(self):
        registry.register(FakeSource())
        self.assertIn("fakedb", registry.available_sources())

    def test_duplicate_registration_is_rejected_without_replace(self):
        registry.register(FakeSource())
        with self.assertRaises(ValueError):
            registry.register(FakeSource())
        registry.register(FakeSource(), replace=True)  # explicit replace is fine

    def test_unusable_source_is_registered_but_not_available(self):
        registry.register(FakeSource(usable=False))
        self.assertIn("fakedb", registry.all_sources())
        self.assertNotIn("fakedb", registry.available_sources())
        self.assertIn("FAKEDB_KEY", registry.unavailable_sources()["fakedb"])

    def test_lookup_by_id_label(self):
        self.assertEqual(registry.find_by_id_label("pmid").name, "pubmed")
        self.assertIsNone(registry.find_by_id_label("nope"))


if __name__ == "__main__":
    unittest.main()
