import unittest
from unittest.mock import patch

from search_filters import analyze_filters, classify, search_terms


class ChildOnlySearchRegression(unittest.TestCase):
    def test_escaped_commas_produce_identical_selected_roles(self):
        roles=["Estágio em Desenvolvimento de Software","Estagiário de TI","Software Engineer Intern"]
        plain=", ".join(roles)
        escaped=plain.replace(", ", r"\, ")
        self.assertEqual(search_terms(plain),search_terms(escaped))

    def test_explicit_internships_are_not_discarded(self):
        roles="Estágio em Desenvolvimento de Software, Estagiário em Desenvolvimento de Sistemas, Estagiário de TI, Software Engineer Intern"
        for title in ("Software Engineer Intern","Estagiário em Desenvolvimento de Sistemas","Estagiário de TI"):
            with self.subTest(title=title):
                verdict,reason=classify({"title":title,"location":"Brasil","description":"","remote":True},
                                        search_terms(roles),"BR","all",0)
                self.assertEqual(verdict,"confirmed")

    def test_existing_father_and_marcus_selections_do_not_gain_unrelated_internships(self):
        groups=(
            "Product Manager, Product Owner, Project Manager, Marketing, Growth, Business Analyst",
            "Data Scientist, Data Analyst, Data Engineer, Machine Learning Engineer, AI Engineer",
        )
        for roles in groups:
            for title in ("Software Engineer Intern","Estagiário de TI"):
                with self.subTest(roles=roles,title=title):
                    self.assertEqual(classify({"title":title,"location":"Brasil","description":""},
                                              search_terms(roles),"BR","all",0),
                                     ("excluded","cargo"))

    def test_child_awaits_own_evidence_without_using_fathers_fixed_score(self):
        import multiuser as mu
        job={"title":"Software Engineer Intern","location":"Brasil","description":"Python required and full stack development.",
             "url":"https://example.org/intern","company":"Example","remote":True}
        with patch.object(mu,"enabled",True), \
             patch("jd_enrichment.valid_listing_jd",return_value=True), \
             patch("block4_score.score_job",side_effect=AssertionError("owner score leaked")):
            items,_,_=analyze_filters([job],"Software Engineer Intern","BR","all",0)
            self.assertEqual(len(items),1)
            self.assertIsNone(items[0]["ranking"]["score"])

if __name__=="__main__":
    unittest.main()
