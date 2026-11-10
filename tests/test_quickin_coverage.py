"""Quickin coverage and normalization regression tests."""
import unittest
from unittest.mock import patch
from catalog_engine import SEED, extra_pull
from search_filters import classify, search_terms

class QuickinCoverageTests(unittest.TestCase):
    @patch("catalog_engine.read")
    def test_publication_date_alias_is_preserved(self, read):
        import json
        read.return_value=(json.dumps({"jobs":[{
            "_id":"123", "title":"Product Manager", "publicate":"published",
            "publishedAt":"2026-11-09T10:00:00Z"}]}).encode(),200)
        jobs,state=extra_pull("quickin","iterative")
        self.assertEqual(state,"ok")
        self.assertEqual(jobs[0]["published"],"2026-11-09T10:00:00Z")

    @patch("catalog_engine.read")
    def test_six_html_pages_are_not_reported_complete(self, read):
        from catalog_engine import run_task
        from urllib.error import HTTPError
        def response(url, **kwargs):
            if "api.quickin.io" in url:
                raise HTTPError(url,400,"invalid",{},None)
            page=int(url.rsplit("page=",1)[-1])
            return (f'<a href="/iterative/jobs/{page}">Product Manager {page}</a>'.encode(),200)
        read.side_effect=response
        details,jobs=run_task("quickin","iterative",allow_js=False)
        self.assertEqual(len(jobs),6)
        self.assertEqual(details["state"],"pendente")

    def test_verified_remote_boards_present(self):
        self.assertIn("iterative", SEED["quickin"])
        self.assertIn("attractfy", SEED["quickin"])

    @patch("catalog_engine.read")
    def test_official_api_retains_remote_metadata(self, read):
        import json
        jobs=[{"title":"Product Owner Sênior","_id":"123","city":"São Paulo",
               "country":"Brasil","workplaceType":"Remote",
               "description":"Product discovery e gestão de backlog",
               "requirements":"Product roadmap","publicate":"published"}]
        read.return_value=(json.dumps({"jobs":jobs}).encode(),200)
        found,state=extra_pull("quickin","iterative")
        self.assertEqual(state,"ok")
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]["workplaceType"],"Remote")
        self.assertIn("Product roadmap",found[0]["description"])
        status,_=classify(found[0],search_terms("Product Owner"),"BR","remote",0)
        self.assertEqual(status,"confirmed")

    @patch("catalog_engine.read")
    def test_missing_mode_not_mislabeled_remote(self,read):
        import json
        read.return_value=(json.dumps({"jobs":[{"title":"Product Owner","_id":"12",
                         "city":"São Paulo","country":"Brasil","publicate":"published"}]}).encode(),200)
        jobs,_=extra_pull("quickin","iterative")
        status,reason=classify(jobs[0],search_terms("Product Owner"),"BR","remote",0)
        self.assertEqual(status,"review")
        self.assertIn("modalidade",reason)

if __name__=="__main__":
    unittest.main()
