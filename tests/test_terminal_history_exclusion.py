"""Protect terminal candidature/discard decisions from reappearing in searches."""
import unittest
from app import terminal_url_key,terminal_url_bases,exclude_history_matches,pair_key

class TerminalDecisionTests(unittest.TestCase):
    def test_tracking_params_do_not_make_old_candidate_new(self):
        saved="boards.greenhouse.io/acme/jobs/123?gh_jid=123&utm_source=mail"
        returned="https://boards.greenhouse.io/acme/jobs/123?utm_campaign=ads&gh_jid=123"
        self.assertEqual(terminal_url_key(saved),terminal_url_key(returned))
        job={"url":returned,"company":"Acme","title":"Product Manager"}
        visible,pending,n=exclude_history_matches([job],[],{terminal_url_key(saved)},set())
        self.assertEqual((len(visible),len(pending),n),(0,0,1))
    def test_distinct_job_id_remains_distinct(self):
        a="https://boards.greenhouse.io/acme/jobs/123?gh_jid=123"
        b="https://boards.greenhouse.io/acme/jobs/123?gh_jid=456"
        self.assertNotEqual(terminal_url_key(a),terminal_url_key(b))
    def test_review_vacancy_also_hidden(self):
        job={"url":"https://jobs.quickin.io/acme/jobs/abc?utm_source=feed","company":"Acme","title":"Product Owner"}
        visible,pending,n=exclude_history_matches([],[job],{terminal_url_key(job["url"])},set())
        self.assertEqual((len(visible),len(pending),n),(0,0,1))
    def test_same_company_role_different_url_must_remain_visible(self):
        job={"url":"https://jobs.quickin.io/acme/jobs/new-requisition","company":"Acme","title":"Product Owner"}
        visible,pending,n=exclude_history_matches([job],[],set(),{pair_key("Acme","Product Owner")})
        self.assertEqual((len(visible),len(pending),n),(1,0,0))

    def test_exact_url_still_blocked_even_if_pair_matches(self):
        job={"url":"https://jobs.quickin.io/acme/jobs/old-requisition","company":"Acme","title":"Product Owner"}
        visible,pending,n=exclude_history_matches([job],[],{terminal_url_key(job["url"])},{pair_key("Acme","Product Owner")})
        self.assertEqual((len(visible),len(pending),n),(0,0,1))

    def test_url_bases(self):
        jobs=[{"url":"https://example.org/job/1?utm_source=x"},{"url":"https://example.org/job/1?utm_source=y"}]
        self.assertEqual(terminal_url_bases(jobs),["example.org/job/1"])

if __name__=="__main__":unittest.main()
