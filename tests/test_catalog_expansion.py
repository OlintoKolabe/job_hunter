"""Regression checks for evidence-backed zero-cost catalog expansion."""
import unittest
from catalog_engine import source_tasks

NEW_BOARDS = ("Skydropx", "puzzle-consulting-services", "connectly", "moovx",
              "Scale Army Careers", "rehire", "gratia", "willow-health",
              "LeanLayer", "dandy", "southgeeks")

class CatalogExpansionTests(unittest.TestCase):
    def test_new_ashby_boards_in_source_tasks(self):
        tasks=source_tasks()
        for slug in NEW_BOARDS:
            self.assertIn(("ashby",slug),tasks)
    def test_no_duplicate_source_slugs(self):
        tasks=source_tasks()
        self.assertEqual(len(tasks),len(set((s,k.casefold()) for s,k in tasks)))

if __name__=="__main__":
    unittest.main()
