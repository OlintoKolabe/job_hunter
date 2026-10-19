import os
import unittest
from unittest.mock import patch
import jsearch_provider

class JSearchProviderTests(unittest.TestCase):
    def test_no_key_means_no_external_call(self):
        with patch.dict(os.environ,{"JH_JSEARCH_RAPIDAPI_KEY":""}):
            with patch.object(jsearch_provider,"fetch_json") as fetch:
                jobs,meta=jsearch_provider.search("Product Manager","BR")
                self.assertEqual(jobs,[])
                self.assertEqual(meta["state"],"not_configured")
                fetch.assert_not_called()

    def test_one_bounded_request_and_normalization(self):
        payload={"data":[{"job_title":"Senior Product Manager","employer_name":"Example",
          "job_apply_link":"https://example.org/apply/1","job_city":"São Paulo",
          "job_country":"Brazil","job_is_remote":True,
          "job_posted_at_datetime_utc":"2026-10-19T00:00:00Z",
          "job_description":"Remote PM opportunity"}]}
        with patch.dict(os.environ,{"JH_JSEARCH_RAPIDAPI_KEY":"test-not-real"}):
            with patch.object(jsearch_provider,"fetch_json",return_value=payload) as fetch:
                jobs,meta=jsearch_provider.search("Product Manager, Product Owner","BR")
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]["source"],"jsearch")
        self.assertEqual(jobs[0]["company"],"Example")
        self.assertTrue(jobs[0]["location"].startswith("Remote"))
        self.assertEqual(meta["received"],1)
        self.assertEqual(fetch.call_count,1)
        self.assertEqual(fetch.call_args.kwargs["headers"]["X-RapidAPI-Host"],"jsearch.p.rapidapi.com")

    def test_unsupported_country_fails_without_cost(self):
        with patch.dict(os.environ,{"JH_JSEARCH_RAPIDAPI_KEY":"test-not-real"}):
            with patch.object(jsearch_provider,"fetch_json") as fetch:
                jobs,meta=jsearch_provider.search("PM","CA")
        self.assertFalse(jobs)
        self.assertEqual(meta["state"],"unsupported_country")
        fetch.assert_not_called()

if __name__=="__main__":
    unittest.main()
