import unittest
from unittest.mock import patch
from job_detail_evidence import extract,enrich,recover

HTML='''<script type="application/ld+json">{"@type":"JobPosting", "datePosted":"2026-11-04", "jobLocationType":"TELECOMMUTE", "applicantLocationRequirements":{"@type":"Country", "name":"Brazil"}, "description":"Remote role in Brazil"}</script>'''

class JobDetailEvidenceTests(unittest.TestCase):
    def test_extracts_only_declared_job_posting_fields(self):
        result=extract(HTML)
        self.assertEqual(result["published"],"2026-11-04")
        self.assertTrue(result["remote"])
        self.assertEqual(result["location"],"Brazil")
    def test_no_guess_without_job_posting(self):
        self.assertEqual(extract('<script type="application/ld+json">{"@type":"Article","datePosted":"2026-11-04"}</script>'),{})
    def test_untrusted_hosts_are_never_fetched(self):
        job={"source":"jobgether","url":"https://example.com/jobs/123","title":"Product Manager"}
        with patch("job_detail_evidence.urllib.request.urlopen") as fetch:
            self.assertEqual(recover(job),job)
        fetch.assert_not_called()
    def test_bounded_parallel_fetch_only_selected_sources(self):
        jobs=[{"source":"jobgether","url":f"https://jobgether.com/{i}","title":"PM"} for i in range(7)]
        with patch("job_detail_evidence.recover",side_effect=lambda job:{**job,"source_detail_status":"recovered"}) as fn:
            result=enrich(jobs,limit=3)
        self.assertEqual(fn.call_count,3)
        self.assertEqual(sum(j.get("source_detail_status")=="recovered" for j in result),3)
    def test_detail_budget_prioritizes_requested_titles(self):
        jobs=[{"source":"jobgether","url":f"https://jobgether.com/{i}",
               "title":"Sales Representative" if i<4 else "Product Manager"} for i in range(6)]
        with patch("job_detail_evidence.recover",side_effect=lambda job:{**job,"source_detail_status":"recovered"}) as fn:
            result=enrich(jobs,limit=2,roles="Product Manager")
        self.assertEqual(fn.call_count,2)
        self.assertEqual([j["title"] for j in result if j.get("source_detail_status")=="recovered"],
                         ["Product Manager","Product Manager"])

if __name__=="__main__":unittest.main()
