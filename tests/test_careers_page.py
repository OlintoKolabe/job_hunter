import unittest
from unittest.mock import patch

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
    def test_source_is_available(self):
        self.assertIn(("careers_page", "customertimes"), source_tasks())

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

    def test_rejects_untrusted_slug(self):
        with self.assertRaises(ValueError):
            collect_board("../evil", lambda *args, **kwargs:(b"", 200))


if __name__ == "__main__":
    unittest.main()
