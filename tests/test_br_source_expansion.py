"""Verify newly included Brazil/LATAM-oriented career boards are discoverable."""
import unittest
from catalog_engine import source_tasks

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

    def test_no_duplicate_case_insensitive_boards(self):
        tasks=source_tasks()
        normalized=[(source,slug.lower()) for source,slug in tasks]
        self.assertEqual(len(normalized),len(set(normalized)))

if __name__=="__main__":unittest.main()
