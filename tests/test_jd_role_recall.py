"""JD evidence may rescue ambiguous roles, never clear incompatibilities."""
import unittest
from search_filters import classify,search_terms,DEFAULT_ROLES
TERMS=search_terms(DEFAULT_ROLES)
def job(title,description,location="Brazil - Remote"):
    return {"title":title,"description":description,"location":location,"published":""}
class RecallTests(unittest.TestCase):
    def test_technical_title_with_repeated_product_evidence_requires_review(self):
        result,reason=classify(job("Engineering Lead","Lead product roadmap, product discovery and product strategy across teams."),TERMS,"BR","remote",0)
        self.assertEqual(result,"review")
        self.assertIn("cargo_a_confirmar",reason)
    def test_unrelated_engineer_still_excluded(self):
        result,reason=classify(job("Backend Engineer","Python systems backend microservices."),TERMS,"BR","remote",0)
        self.assertEqual((result,reason),("excluded","cargo"))
    def test_clear_product_manager_still_confirmed(self):
        result,_=classify(job("Product Manager",""),TERMS,"BR","remote",0)
        self.assertEqual(result,"confirmed")
    def test_foreign_only_still_excluded(self):
        result,_=classify(job("Engineering Lead","Product roadmap, product discovery, product strategy. Must be based in the US."),TERMS,"BR","remote",0)
        self.assertEqual(result,"excluded")
if __name__=="__main__":unittest.main()
