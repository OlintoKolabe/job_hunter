"""Regression: catalog-only rejected jobs must not leak into initial search."""
import ast, inspect, unittest
import app

class SearchIsolationTests(unittest.TestCase):
    def test_initial_search_has_no_undefined_rejected(self):
        tree=ast.parse(inspect.getsource(app.search_jobs))
        names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
        self.assertNotIn("rejected",names)
    def test_catalog_scan_still_has_out_of_filter_results(self):
        source=inspect.getsource(app.catalog_scan)
        self.assertIn('"excluded_items":rejected',source)
        self.assertIn("exclude_history_matches([],rejected",source)

if __name__=="__main__":unittest.main()
