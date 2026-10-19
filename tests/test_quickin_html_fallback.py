"""Regression: Quickin HTML fallback must not discard visible remote/Brazil evidence."""
import unittest
from unittest.mock import patch
from urllib.error import URLError
from catalog_engine import extra_pull
from search_filters import classify,search_terms

BOARD=b'<a href="/iterative/jobs/123">Growth Product Manager</a>'
DETAIL='''<html><body><h1>Growth Product Manager</h1>
<h5>PJ, São Paulo Remote</h5>
<p>Growth Product Manager. Product strategy, product roadmap and growth strategy.</p>
<p>Trabalho 100% remoto.</p></body></html>'''.encode()

class QuickinFallbackTests(unittest.TestCase):
    @patch("catalog_engine.read")
    def test_remote_role_in_brazil_confirmed_after_api_failure(self,mock_read):
        def response(url,**kw):
            if "api.quickin.io" in url:raise URLError("unavailable")
            if url.endswith("/jobs?page=1"):return BOARD,200
            if url.endswith("/jobs?page=2"):return b"",200
            if url.endswith("/jobs/123"):return DETAIL,200
            raise AssertionError(url)
        mock_read.side_effect=response
        jobs,state=extra_pull("quickin","iterative")
        self.assertEqual(state,"ok")
        self.assertEqual(len(jobs),1)
        self.assertIn("São Paulo",jobs[0]["location"])
        self.assertIn("remoto",jobs[0]["description"])
        self.assertEqual(classify(jobs[0],search_terms("Growth, Product Manager"),"BR","remote",0)[0],"confirmed")

    @patch("catalog_engine.read")
    def test_unreadable_job_stays_unconfirmed(self,mock_read):
        def response(url,**kw):
            if "api.quickin.io" in url or url.endswith("/jobs/123"):raise URLError("unavailable")
            if url.endswith("/jobs?page=1"):return BOARD,200
            return b"",200
        mock_read.side_effect=response
        jobs,_=extra_pull("quickin","iterative")
        self.assertEqual(len(jobs),1)
        self.assertEqual(classify(jobs[0],search_terms("Growth, Product Manager"),"BR","remote",0)[0],"review")

if __name__=="__main__":unittest.main()
