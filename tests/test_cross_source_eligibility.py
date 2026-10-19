"""Cross-source regression: the same eligibility rules apply regardless of ATS."""
import unittest
from search_filters import classify, search_terms

TERMS=search_terms("Product Manager")
BASE={"title":"Product Manager","published":""}

def check(source,location,description="",**fields):
    return classify({**BASE,"source":source,"location":location,
                     "description":description,**fields},TERMS,"BR","remote",0)[0]

class CrossSourceEligibility(unittest.TestCase):
    def test_all_sources_confirm_brazil_remote(self):
        for source in ("Ashby","Greenhouse","Lever","inHire","Gupy","Quickin"):
            with self.subTest(source=source):
                self.assertEqual(check(source,"Brazil - Remote"),"confirmed")

    def test_all_sources_reject_foreign_only(self):
        for source in ("Ashby","Greenhouse","Lever","inHire","Gupy","Quickin"):
            with self.subTest(source=source):
                self.assertEqual(check(source,"United States - Remote"),"excluded")

    def test_regional_heading_does_not_override_foreign_restriction(self):
        for source in ("Ashby","Greenhouse","Lever","inHire","Gupy","Quickin"):
            with self.subTest(source=source):
                self.assertEqual(check(source,"LATAM - Remote",
                    "Must be based in the United States."),"excluded")

    def test_remote_heading_does_not_override_onsite_only(self):
        self.assertNotEqual(check("Greenhouse","Brazil - Remote",
            "This is an onsite only role; must work from office."),"confirmed")

    def test_unknown_stays_pending(self):
        self.assertEqual(check("Ashby","Brazil"),"review")

    def test_ashby_structured_remote(self):
        self.assertEqual(check("Ashby","Brazil",remote=True),"confirmed")

    def test_explicit_brazil_exclusion_in_description(self):
        self.assertEqual(check("Lever","Worldwide - Remote",
            "Candidates from anywhere except Brazil."),"excluded")

if __name__=="__main__":unittest.main()
