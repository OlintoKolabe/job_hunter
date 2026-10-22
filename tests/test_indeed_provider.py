import unittest
from unittest.mock import patch
import pandas as pd
import indeed_provider

class IndeedProviderTests(unittest.TestCase):
    def test_available_without_api_key(self):
        with patch.dict("os.environ",{"HASDATA_API_KEY":""}):
            self.assertTrue(indeed_provider.enabled())
    def test_indeed_brazil_remote_normalization(self):
        sample=pd.DataFrame([{"title":"Product Manager","company":"Acme","job_url":"https://br.indeed.com/viewjob?jk=abc",
          "location":"São Paulo, Brasil","is_remote":True,"date_posted":"2026-10-21","description":"Gestão de produto"}])
        with patch("jobspy.scrape_jobs",return_value=sample) as spy:
            rows=indeed_provider.search("product manager")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["source"],"indeed")
        self.assertTrue(rows[0]["remote"])
        self.assertIn("Brasil",rows[0]["location"])
        self.assertEqual(spy.call_args.kwargs["country_indeed"],"Brazil")
        self.assertEqual(spy.call_args.kwargs["results_wanted"],15)
    def test_empty_results_remain_empty(self):
        with patch("jobspy.scrape_jobs",return_value=pd.DataFrame()):
            self.assertEqual(indeed_provider.search("product owner"),[])
if __name__=="__main__":unittest.main()
