"""Search-only regression tests for Brazil and remote aliases (no CV/UI changes)."""
import unittest
from search_filters import classify, search_terms

TERMS = search_terms("Product Manager")
BASE = {"title": "Product Manager", "published": ""}

def verdict(location="", description="", **fields):
    job = {**BASE, "location": location, "description": description, **fields}
    return classify(job, TERMS, "BR", "remote", 0)

class SearchAliasRegressions(unittest.TestCase):
    def test_positive_brazil_remote(self):
        for location in ("Brazil - Remote", "Brasil - Remota", "BR - Home Office",
                         "BRA - Remote", "Caldas Novas - Remote", "Goiânia - Remote"):
            with self.subTest(location=location):
                self.assertEqual(verdict(location)[0], "confirmed")

    def test_structured_remote_alias(self):
        for mode in ("WFH", "Work Anywhere", "Remote-first", "Telecommuting",
                     "Trabalho a distância"):
            with self.subTest(mode=mode):
                self.assertEqual(verdict("Brasil", workplaceType=mode)[0], "confirmed")

    def test_restrictions_not_overridden(self):
        self.assertEqual(verdict("United States - Remote"), ("excluded", "pais"))
        self.assertEqual(verdict("Brazil - Hybrid"), ("excluded", "modalidade"))
        self.assertEqual(verdict("Brazil - Remote", description="This is an onsite only role; must work from office.")[0], "excluded")

    def test_missing_proof_stays_review(self):
        self.assertEqual(verdict("Brasil"), ("review", "modalidade"))
        self.assertEqual(verdict("Remote"), ("review", "pais"))

    def test_role_filter_stays_strict(self):
        job = {**BASE, "title": "Registered Nurse", "location": "Brazil - Remote"}
        self.assertEqual(classify(job, TERMS, "BR", "remote", 0), ("excluded", "cargo"))

if __name__ == "__main__":
    unittest.main()
