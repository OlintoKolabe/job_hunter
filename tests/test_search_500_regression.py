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

    def test_both_existing_search_paths_consult_prefilter_cache(self):
        for route in (app.search_jobs,app.catalog_scan):
            source=inspect.getsource(route)
            self.assertIn('analyze_filters(cached_jds_for_filter(',source)
            self.assertIn('persist_listing_jds(',source)
            self.assertLess(source.index('cached_jds_for_filter('),source.index('persist_listing_jds('))

if __name__=="__main__":unittest.main()
