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

    def test_large_role_catalog_preserves_terms_after_first_25(self):
        from search_filters import search_terms,role_match,analyze_filters
        titles=["Specialist "+str(i) for i in range(75)]+["Data Engineer"]
        roles=", ".join(titles)
        self.assertLess(len(roles),5000)
        terms=search_terms(roles)
        self.assertEqual(len(terms),76)
        self.assertTrue(role_match("Senior Data Engineer",terms))
        confirmed,review,_=analyze_filters([],roles,"BR","remote",7,"newest")
        self.assertEqual((confirmed,review),([],[]))
        with self.assertRaisesRegex(ValueError,"5.000 caracteres"):
            analyze_filters([],roles*8,"BR","remote",7,"newest")

    def test_both_existing_search_paths_consult_prefilter_cache(self):
        for route in (app.search_jobs,app.catalog_scan):
            source=inspect.getsource(route)
            self.assertIn('analyze_filters(cached_jds_for_filter(',source)
            self.assertIn('persist_listing_jds(',source)
            self.assertLess(source.index('cached_jds_for_filter('),source.index('persist_listing_jds('))

if __name__=="__main__":unittest.main()
