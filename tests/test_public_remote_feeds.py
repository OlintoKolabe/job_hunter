import unittest
from unittest.mock import patch
from public_remote_feeds import fetch

class PublicFeedTests(unittest.TestCase):
    def test_himalayas_requires_attributed_apply_url(self):
        payload={"jobs":[{"companyName":"Acme","title":"Product Manager","applicationLink":"https://himalayas.app/companies/acme/jobs/pm","locationRestrictions":[{"alpha2":"BR","name":"Brazil"}],"pubDate":1780000000000}]}
        with patch("public_remote_feeds.fetch_json",return_value=payload) as get:
            jobs=fetch("himalayas","Product Manager","BR")
        self.assertEqual(jobs[0]["source"],"himalayas")
        self.assertEqual(jobs[0]["location"],"Brazil")
        self.assertIn("country=BR",get.call_args.args[0])
    def test_remotive_attribution(self):
        with patch("public_remote_feeds.fetch_json",return_value={"jobs":[{"company_name":"Acme","title":"Project Manager","url":"https://remotive.com/remote-jobs/pm","candidate_required_location":"Brazil"}]}):
            jobs=fetch("remotive")
        self.assertEqual(jobs[0]["url"],"https://remotive.com/remote-jobs/pm")
    def test_remoteok_ignores_terms_and_external_url(self):
        rows=[{"legal":"Terms"},{"company":"A","position":"Product Owner","url":"https://remoteok.com/remote-jobs/pm-1"},{"company":"B","position":"Project Manager","url":"https://external.example/job"}]
        with patch("public_remote_feeds.fetch_json",return_value=rows):
            jobs=fetch("remoteok")
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]["source"],"remoteok")

if __name__=="__main__":unittest.main()
