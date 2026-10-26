"""Evidence-led regression tests for the isolated October 26 follow-up."""
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from search_filters import classify, search_terms
from app import ordered_catalog_tasks
from catalog_engine import run_task, scan


def example(title, source="workable", location="Brazil - Remote"):
    return {
        "title": title, "source": source, "location": location,
        "published": datetime.now(timezone.utc).isoformat(),
        "description": "Remote work collaborating with distributed product teams.",
    }


class SelectedRoleAndSourceRegressionTests(unittest.TestCase):
    def test_unselected_marketing_does_not_ride_on_growth(self):
        selected = search_terms("Product Manager, Product Owner, Project Manager, Gerente de Projetos, Growth, PMO")
        for title in ("General Manager - Marketing and Ecommerce Growth", "VR Growth & Live Games", "Growth Marketing Manager", "Marketing Operations Manager"):
            with self.subTest(title=title):
                self.assertEqual(classify(example(title), selected, "BR", "remote", 0)[0], "excluded")

    def test_growth_manager_and_existing_profiles_remain_eligible(self):
        roles = search_terms("Product Manager, Product Owner, Project Manager, Growth")
        for title in ("Growth Manager", "Product Manager", "Product Owner", "Project Manager"):
            with self.subTest(title=title):
                self.assertEqual(classify(example(title), roles, "BR", "remote", 0)[0], "confirmed")
        self.assertEqual(classify(example("Marketing Manager"), search_terms("Marketing"), "BR", "remote", 0)[0], "confirmed")
        self.assertEqual(classify(example("Data Scientist"), search_terms("Data Scientist"), "BR", "remote", 0)[0], "confirmed")
        self.assertEqual(classify(example("Junior Software Developer"), search_terms("Desenvolvedor Júnior"), "BR", "remote", 0)[0], "confirmed")

    def test_only_himalayas_exact_worldwide_is_brazil_eligible(self):
        roles=search_terms("Product Manager")
        self.assertEqual(classify(example("Product Manager", "himalayas", "Worldwide"), roles,"BR","remote",0)[0], "confirmed")
        self.assertEqual(classify(example("Product Manager", "himalayas", "Worldwide - Remote"), roles,"BR","remote",0)[0], "review")
        self.assertEqual(classify(example("Product Manager", "remotive", "Worldwide"), roles,"BR","remote",0)[0], "review")

    def test_browser_js_is_deferred_only_for_all_source_catalog(self):
        with patch("catalog_engine.extra_pull", return_value=([],"ok")), patch("catalog_engine.js_fallback") as js:
            details, jobs = scan([("quickin","board")],workers=1,allow_js=False)
            self.assertEqual(jobs, [])
            self.assertEqual(details[0]["state"], "pendente")
            js.assert_not_called()
        with patch("catalog_engine.extra_pull",return_value=([],"ok")), patch("catalog_engine.js_fallback",return_value=[example("Product Manager","quickin")]) as js:
            detail, jobs=run_task("quickin","board",allow_js=True)
            self.assertEqual(len(jobs),1)
            js.assert_called_once()

    def test_js_only_catalog_sources_do_not_block_fast_sources(self):
        tasks=[("quickin", "q0"),("kaszek","k0"),("ashby","nonwarm"),("lever","nonwarm"),("inhire","nonwarm")]
        ordered=ordered_catalog_tasks(tasks)
        self.assertEqual(set(ordered),set(tasks))
        self.assertEqual(set(ordered[:3]),{("ashby","nonwarm"),("lever","nonwarm"),("inhire","nonwarm")})
        self.assertEqual({source for source,_ in ordered[-2:]},{"kaszek","quickin"})

    def test_general_ui_scan_is_bounded_and_reports_partial_results(self):
        source=Path(__file__).resolve().parent.parent.joinpath("src","Opportunities.jsx").read_text()
        self.assertIn("const scanDeadline=Date.now()+120000",source)
        self.assertIn("if(Date.now()>scanDeadline)",source)
        self.assertIn("busca interrompida por limite de tempo",source)


if __name__=="__main__":
    unittest.main()
