"""Gate 9 regressions for the Oct 26 canary search incident."""
import unittest
from datetime import datetime, timezone
from pathlib import Path

from ai_resume_matcher import shortlist_jobs
from collectors import TITLE_RE
from search_filters import classify, search_terms


def job(title, suffix):
    return {
        "url": "https://example.com/jobs/" + suffix,
        "title": title,
        "company": "Public company",
        "location": "Brazil - Remote",
        "published": datetime.now(timezone.utc).isoformat(),
        "description": "Public job description with development, software, testing, agile delivery and product collaboration. " * 5,
        "jd_available": True,
    }


class SearchSourceFallbackRegressions(unittest.TestCase):
    def test_son_shortlist_does_not_raise_unknown_engineering_family(self):
        roles = "Estagiário de TI, Desenvolvedor Júnior, Software Engineer Intern"
        found = shortlist_jobs(
            [job("Junior Software Developer", "junior"), job("IT Intern", "intern")],
            roles,
            limit=2,
        )
        self.assertEqual(len(found), 2)
        self.assertIn("https://example.com/jobs/intern", found)
        self.assertIn("https://example.com/jobs/junior", found)

    def test_legacy_html_prefilter_includes_technical_junior_data_and_intern_titles(self):
        for title in (
            "Estagiário em Desenvolvimento de Software",
            "Junior Backend Developer",
            "Software Engineer Intern",
            "IT Intern",
            "Analista de Dados Júnior",
            "Data Scientist",
            "Machine Learning Engineer",
        ):
            with self.subTest(title=title):
                self.assertIsNotNone(TITLE_RE.search(title))

    def test_junior_source_discovery_does_not_admit_it_into_fathers_filter(self):
        item = job("Junior Backend Developer", "developer")
        terms = search_terms("Product Manager, Product Owner")
        self.assertEqual(classify(item, terms, "BR", "remote", 7)[0], "excluded")

    def test_marcus_ranking_remains_available(self):
        found = shortlist_jobs(
            [job("Data Scientist", "ds"), job("Data Analyst", "da")],
            "Data Scientist, Data Analyst",
            limit=2,
        )
        self.assertEqual(len(found), 2)

    def test_transient_gateway_statuses_retry_without_silent_success(self):
        src = Path("src/Opportunities.jsx").read_text()
        self.assertIn("![429,502,503,504].includes(err.status)", src)
        self.assertIn("skipped++;", src)
        self.assertIn("completedAll=reachedEnd&&skipped===0", src)
        self.assertIn("Busca parcial", src)


if __name__ == "__main__":
    unittest.main()
