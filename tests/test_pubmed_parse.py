"""Offline tests for the PubMed XML parser and the citation auditor.

These run without network access. The fixture exercises the shapes that break
naive parsers: structured abstracts, inline markup inside ArticleTitle, and a
MedlineDate instead of a plain Year.
"""

import unittest

from research_core.agent import ReviewResult
from research_core.pubmed import Article, _parse_articles
from research_core.verify import audit_citations

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


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.articles = _parse_articles(FIXTURE)

    def test_parses_every_record(self):
        self.assertEqual([a.pmid for a in self.articles], ["37356941", "30122560"])

    def test_inline_markup_in_title_is_flattened(self):
        self.assertEqual(
            self.articles[0].title, "Semaglutide and cardiovascular outcomes."
        )

    def test_structured_abstract_keeps_labels(self):
        abstract = self.articles[0].abstract
        self.assertIn("BACKGROUND: Obesity raises risk.", abstract)
        self.assertIn("RESULTS: HR was 0.80.", abstract)

    def test_unstructured_abstract_has_no_label_prefix(self):
        self.assertEqual(self.articles[1].abstract, "No label here.")

    def test_collective_author_is_skipped_not_blank(self):
        self.assertEqual(self.articles[0].authors, ["Lincoff AM"])

    def test_medline_date_falls_back_to_year(self):
        self.assertEqual(self.articles[1].year, "2018")

    def test_publication_types_and_url(self):
        self.assertEqual(
            self.articles[0].publication_types, ["Randomized Controlled Trial"]
        )
        self.assertEqual(
            self.articles[0].url, "https://pubmed.ncbi.nlm.nih.gov/37356941/"
        )


class CitationAuditTests(unittest.TestCase):
    def _result(self, report, retrieved):
        return ReviewResult(
            report=report,
            search_log=[],
            articles={p: Article(p, "t", "j", "2024", []) for p in retrieved},
        )

    def test_clean_report_passes(self):
        audit = audit_citations(self._result("As shown (PMID: 37356941).", {"37356941"}))
        self.assertTrue(audit.ok)
        self.assertEqual(audit.cited, {"37356941"})

    def test_uncited_retrieval_is_not_an_error(self):
        # Retrieving more than you cite is normal screening, not a failure.
        audit = audit_citations(
            self._result("Only one (PMID 37356941).", {"37356941", "30122560"})
        )
        self.assertTrue(audit.ok)

    def test_fabricated_pmid_is_flagged(self):
        # No network: a PMID absent from `articles` is caught before any lookup.
        result = self._result("Claim (PMID: 12345678).", {"37356941"})

        class NeverExists:
            def exists(self, pmid):
                return False

        audit = audit_citations(result, pubmed=NeverExists())
        self.assertFalse(audit.ok)
        self.assertEqual(audit.unretrieved, {"12345678"})
        self.assertEqual(audit.nonexistent, {"12345678"})
        self.assertIn("possible fabrication", audit.summary())

    def test_pmid_formats_both_parse(self):
        audit = audit_citations(
            self._result("a (PMID: 37356941) b (PMID 30122560)", {"37356941", "30122560"})
        )
        self.assertEqual(audit.cited, {"37356941", "30122560"})


if __name__ == "__main__":
    unittest.main()
