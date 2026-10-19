"""Verify newly included Brazil/LATAM-oriented career boards are discoverable."""
import unittest
from unittest.mock import patch
from catalog_engine import source_tasks,scan

NEW_ASHBY=("connectly","dandy","gratia","LeanLayer","moovx",
           "puzzle-consulting-services","rehire","Scale Army Careers",
           "Skydropx","southgeeks","willow-health")

class BrazilSourceExpansionTests(unittest.TestCase):
    def test_ashby_and_greenhouse_in_catalog(self):
        tasks=source_tasks()
        for slug in NEW_ASHBY:
            self.assertIn(("ashby",slug),tasks)
        for slug in ("monks","blip-global","platformscience"):
            self.assertIn(("greenhouse",slug),tasks)

    def test_scan_exposes_exact_board_slug(self):
        def fake_task(source,slug):
            return {"source":source,"slug":slug,"state":"validado","received":1},[{"url":"https://example.org/job/1","source":source}]
        with patch("catalog_engine.run_task",side_effect=fake_task):
            details,jobs=scan([("ashby","Skydropx")],workers=1)
        self.assertEqual(jobs[0]["board_slug"],"Skydropx")
        self.assertEqual(jobs[0]["board_source"],"ashby")
        self.assertEqual(details[0]["slug"],"Skydropx")

    def test_no_duplicate_case_insensitive_boards(self):
        tasks=source_tasks()
        normalized=[(source,slug.lower()) for source,slug in tasks]
        self.assertEqual(len(normalized),len(set(normalized)))

if __name__=="__main__":unittest.main()
