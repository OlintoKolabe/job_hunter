import unittest
from unittest.mock import patch

import pandas as pd

from linkedin_jobspy import search
from search_filters import classify


class LinkedInJobSpyTests(unittest.TestCase):
    def test_remote_filter_and_explicit_mode(self):
        results = pd.DataFrame([
            {"title":"Product Manager", "company":"Acme", "job_url":"https://www.linkedin.com/jobs/view/123",
             "location":{"city":"São Paulo","country":"Brazil"}, "date_posted":"2026-11-10",
             "is_remote":True, "description":"Fully remote in Brazil."},
            {"title":"Product Owner", "company":"Beta", "job_url":"https://www.linkedin.com/jobs/view/456",
             "location":{"country":"Brazil"}, "date_posted":"2026-11-10",
             "is_remote":False, "description":"Hybrid role with three days in office."},
        ])
        with patch("jobspy.scrape_jobs", return_value=results) as spy:
            jobs = search("product manager", mode="remote")
        self.assertEqual(spy.call_args.kwargs["site_name"], "linkedin")
        self.assertTrue(spy.call_args.kwargs["is_remote"])
        self.assertTrue(spy.call_args.kwargs["fetch_description"])
        self.assertNotIn("hours_old", spy.call_args.kwargs)
        self.assertEqual(jobs[0]["location"], "São Paulo, Brazil")
        self.assertTrue(jobs[0]["remote"])
        self.assertNotIn("remote", jobs[1])
        self.assertEqual(classify(jobs[0],["product manager"],"BR","remote",0)[0],"confirmed")
        self.assertEqual(classify(jobs[1],["product owner"],"BR","remote",0)[0],"excluded")

    def test_unverified_mode_remains_review(self):
        results=pd.DataFrame([{"title":"Product Manager","company":"Acme",
                "job_url":"https://www.linkedin.com/jobs/view/777",
                "location":{"country":"Brazil"},"is_remote":False}])
        with patch("jobspy.scrape_jobs",return_value=results):
            job=search("product manager")[0]
        self.assertEqual(classify(job,["product manager"],"BR","remote",0)[0],"review")

    def test_board_failure_is_not_reported_as_empty(self):
        results=pd.DataFrame()
        results.attrs["errors"]={"linkedin":"response status code 429"}
        with patch("jobspy.scrape_jobs",return_value=results):
            with self.assertRaisesRegex(RuntimeError,"429"):
                search("product manager")


if __name__ == "__main__":
    unittest.main()
