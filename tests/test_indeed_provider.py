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
    def test_detail_lookup_never_substitutes_another_indeed_job(self):
        df=pd.DataFrame([
            {"job_url":"https://br.indeed.com/viewjob?jk=1111111111111111","description":"Wrong job "*50},
            {"job_url":"https://br.indeed.com/viewjob?jk=245b508b66b7f110","description":"Verified requirements "*35},
        ])
        with patch("jobspy.scrape_jobs",return_value=df):
            text=indeed_provider.description_for_job("https://br.indeed.com/viewjob?jk=245b508b66b7f110","Project Manager","Acme")
        self.assertTrue(text.startswith("Verified requirements"))
    def test_detail_lookup_fails_closed_when_only_similar_jobs_exist(self):
        df=pd.DataFrame([{"job_url":"https://br.indeed.com/viewjob?jk=1111111111111111","description":"Wrong job "*50}])
        with patch("jobspy.scrape_jobs",return_value=df):
            self.assertIsNone(indeed_provider.description_for_job("https://br.indeed.com/viewjob?jk=245b508b66b7f110","Project Manager"))
if __name__=="__main__":unittest.main()
