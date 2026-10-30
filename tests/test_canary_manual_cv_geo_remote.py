"""Canary regression contracts: manual CV choice and Brazil/remote recognition."""
import unittest
from pathlib import Path
from search_filters import classify, search_terms, detect_work_mode

TERMS = search_terms("Product Manager")
BASE = {"title": "Product Manager", "published": ""}

def verdict(location="", description="", **fields):
    return classify({**BASE, "location": location, "description": description, **fields}, TERMS, "BR", "remote", 0)[0]

class BrazilRemoteCanaryTests(unittest.TestCase):
    def test_brazil_remote_aliases(self):
        for location in ("Brazil - Remote", "Brasil - Remota", "BR - Home Office", "BRA - Remote", "Caldas Novas - Remote", "Goiânia - Remote"):
            with self.subTest(location=location):
                self.assertEqual(verdict(location), "confirmed")

    def test_remote_workplace_aliases(self):
        for mode in ("WFH", "Work Anywhere", "Remote-first", "Telecommuting", "Trabalho a distância"):
            with self.subTest(mode=mode):
                self.assertEqual(verdict("Brasil", workplaceType=mode), "confirmed")

    def test_explicit_foreign_and_hybrid_stay_out(self):
        self.assertEqual(verdict("United States - Remote"), "excluded")
        self.assertEqual(verdict("Brazil - Hybrid"), "excluded")
        self.assertEqual(verdict("Brasil", description="This is an onsite only role; must work from office."), "excluded")

    def test_unknown_is_still_unconfirmed(self):
        self.assertEqual(verdict("Brasil"), "review")
        self.assertEqual(verdict("Remote"), "review")

    def test_manual_cv_button_and_server_guard(self):
        ui = Path("src/Opportunities.jsx").read_text()
        server = Path("app.py").read_text()
        self.assertIn("manual_outside_filters:true", ui)
        self.assertIn("manual_outside_filters: bool = False", server)
        self.assertIn("and not payload.manual_outside_filters:", server)
        self.assertNotIn("job.jd_available===true&&<button", ui)
        self.assertIn("valid_listing_jd(jd)", server)

if __name__ == "__main__":
    unittest.main()
