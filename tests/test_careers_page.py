import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from careers_page import collect_board
from catalog_engine import run_task, source_tasks


BOARD = b'''<h2>2 Open Positions</h2>
<a href="/jobs/abc123">Learn more</a>
<a href="/jobs/abc123/apply">Apply now</a>
<a href="https://elsewhere.com/jobs/bad">Outside</a>
<a href="/jobs/def456">Learn more</a>'''
DETAIL = b'''<meta property="og:title" content="Product Manager | Test Employer">
<h4>Product Manager</h4><div>Brazil Remote Full-Time</div>
<h5>Job Description</h5><p>Own product roadmap and discovery.</p>'''


class CareersPageTests(unittest.TestCase):
    def test_429_is_failure_not_zero_and_stops_requests(self):
        calls=[]
        def read(url, size=0):
            calls.append(url)
            raise HTTPError(url,429,"Too Many Requests",{},None)
        jobs,state=collect_board("customertimes",read)
        self.assertEqual((jobs,state),([],"rate_limited"))
        self.assertEqual(len(calls),1)

    def test_no_matching_titles_is_valid_empty(self):
        calls=[]
        def read(url,size=0):
            calls.append(url)
            return b'<h2>1 Open Positions</h2><a href="/jobs/abc" data-job-title="Accountant">Accountant</a>',200
        jobs,state=collect_board("latynlabs",read)
        self.assertEqual((jobs,state),([],"ok"))
        self.assertEqual(len(calls),1)

    def test_429_after_index_preserves_partial_success_status(self):
        def read(url,size=0):
            if "?page=" in url:
                raise HTTPError(url,429,"Too Many Requests",{},None)
            return b'<h2>20 Open Positions</h2><a href="/jobs/pm" data-job-title="Product Manager">Role</a><a href="?page=2">Next</a>',200
        jobs,state=collect_board("customertimes",read)
        self.assertEqual(state,"rate_limited")
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]["title"],"Product Manager")
        self.assertFalse(jobs[0]["published"])
        self.assertFalse(jobs[0]["location"])

    def test_relevant_jobs_on_later_pages_are_not_starved(self):
        calls=[]
        def read(url, size=0):
            calls.append(url)
            if "?page=" in url:
                return (b'<a href="/jobs/target" data-job-title="Product Manager">Role</a>',200)
            if url.endswith("/"):
                return (b'<h2>30 Open Positions</h2><a href="/jobs/irrelevant" data-job-title="Accountant">Other</a><a href="?page=2">Next</a>',200)
            return DETAIL,200
        jobs,state=collect_board("customertimes",read,max_pages=2,max_details=1)
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]["url"],"https://customertimes.careers-page.com/jobs/target")
        self.assertFalse(any("/jobs/irrelevant" in url for url in calls))
    def test_source_is_available(self):
        self.assertIn(("careers_page", "customertimes"), source_tasks())
        self.assertIn(("careers_page", "nearshore-business-solutions"), source_tasks())
        self.assertIn(("careers_page", "yoailabs"), source_tasks())
        self.assertIn(("careers_page", "latamforce-llc"), source_tasks())

    def test_extracts_details_without_application_or_cross_host(self):
        calls = []
        def read(url, size=0):
            calls.append(url)
            return (BOARD if url.endswith("/") else DETAIL), 200
        jobs, state = collect_board("customertimes", read)
        self.assertEqual(state, "ok")
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]["title"], "Product Manager")
        self.assertEqual(jobs[0]["source"], "careers_page")
        self.assertIn("roadmap", jobs[0]["description"])
        self.assertEqual(len(calls), 3)
        self.assertFalse(any("/apply" in url for url in calls))

    def test_legitimate_empty_board_is_zero(self):
        jobs, state = collect_board("customertimes", lambda *args, **kwargs:(b"<p>0 Open Positions</p>", 200))
        self.assertEqual((jobs, state), ([], "ok"))

    def test_unrecognized_board_is_not_zero_success(self):
        with self.assertRaisesRegex(ValueError, "unrecognized"):
            collect_board("customertimes", lambda *args, **kwargs:(b"<p>Access denied</p>", 200))

    def test_errors_are_isolated_by_source(self):
        with patch("catalog_engine.collect_board", side_effect=TimeoutError("timeout")):
            status, jobs = run_task("careers_page", "customertimes")
        self.assertEqual(status["state"], "pendente")
        self.assertEqual(jobs, [])

    def test_empty_board_status_is_not_pending(self):
        with patch("catalog_engine.collect_board",return_value=([],"ok")):
            status,jobs=run_task("careers_page","latynlabs")
        self.assertEqual(status["state"],"sem_vagas")
        self.assertEqual(jobs,[])

    def test_rate_limited_board_remains_pending(self):
        with patch("catalog_engine.collect_board",return_value=([],"rate_limited")):
            status,jobs=run_task("careers_page","customertimes")
        self.assertEqual(status["state"],"pendente")
        self.assertEqual(status["error"],"429")
        self.assertEqual(jobs,[])

    def test_rejects_untrusted_slug(self):
        with self.assertRaises(ValueError):
            collect_board("../evil", lambda *args, **kwargs:(b"", 200))


if __name__ == "__main__":
    unittest.main()
