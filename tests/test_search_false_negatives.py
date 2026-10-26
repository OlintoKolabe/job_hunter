"""Regression contracts: search exclusions and eligibility across ATS sources."""
import unittest
from unittest.mock import patch
from search_filters import classify,search_terms
from app import exclude_history_matches

TERMS=search_terms("Product Manager, Product Owner, Project Manager, Marketing, Growth, Business Analyst, PMO")

def job(title,location="",description="",source="Greenhouse"):
    return {"url":"https://example.org/jobs/123","company":"Example","title":title,"location":location,"description":description,"source":source,"published":""}

class SearchFalseNegativeTests(unittest.TestCase):
    def test_product_engineering_manager_title(self):
        for source in ("Greenhouse","quickin"):
            with self.subTest(source=source):
                status,_=classify(job("Product Manager, Engineering","Brazil - Remote",source=source),TERMS,"BR","remote",0)
                self.assertEqual(status,"confirmed")

    def test_unrelated_engineering_title_remains_out(self):
        status,_=classify(job("Backend Engineer","Brazil - Remote"),TERMS,"BR","remote",0)
        self.assertEqual(status,"excluded")

    def test_full_jd_proves_brazil_remote(self):
        for source in ("Greenhouse","quickin"):
            with self.subTest(source=source):
                status,_=classify(job("Product Owner","",
                    "This position is remote within Brazil. Product roadmap and product discovery.",source),TERMS,"BR","remote",0)
                self.assertEqual(status,"confirmed")

    def test_foreign_only_remains_excluded(self):
        status,_=classify(job("Product Manager","US - Remote","Must be based in the US."),TERMS,"BR","remote",0)
        self.assertEqual(status,"excluded")

    def test_unknown_geo_and_mode_stays_unconfirmed(self):
        status,_=classify(job("Product Manager",""),TERMS,"BR","remote",0)
        self.assertEqual(status,"review")

    def test_explicit_data_science_roles_are_not_blocked_as_non_target(self):
        roles=search_terms("Data Scientist, Machine Learning Engineer, AI Engineer")
        for title in ("Data Scientist","Machine Learning Engineer","AI Engineer"):
            with self.subTest(title=title):
                status,_=classify(job(title,"Brazil - Remote"),roles,"BR","remote",0)
                self.assertEqual(status,"confirmed")

    def test_explicit_junior_and_intern_roles_are_not_blocked(self):
        roles=search_terms("Software Engineer Intern, Desenvolvedor Júnior, Estagiário de TI")
        for title in ("Software Engineer Intern","Desenvolvedor Júnior","Estagiário de TI"):
            with self.subTest(title=title):
                status,_=classify(job(title,"Brazil - Remote"),roles,"BR","remote",0)
                self.assertEqual(status,"confirmed")

    def test_product_profile_still_rejects_unrequested_engineering(self):
        for title in ("Data Scientist","AI Engineer","Software Engineer Intern"):
            with self.subTest(title=title):
                status,reason=classify(job(title,"Brazil - Remote"),TERMS,"BR","remote",0)
                self.assertEqual((status,reason),("excluded","cargo"))

    def test_history_sets_control_exclusion(self):
        j=job("Product Manager","Brazil - Remote")
        confirmed,review,count=exclude_history_matches([j],[],set(),set())
        self.assertEqual(len(confirmed),1)
        self.assertEqual(count,0)

if __name__=="__main__":unittest.main()
