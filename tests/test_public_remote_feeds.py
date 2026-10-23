import unittest
from unittest.mock import patch
from public_remote_feeds import fetch,_CACHE

class PublicFeedTests(unittest.TestCase):
    def setUp(self):
        _CACHE.clear()
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
    def test_himalayas_string_restrictions_and_multiple_roles(self):
        def payload(url):
            job="Product Owner" if "Product+Owner" in url else "Product Manager"
            return {"jobs":[{"companyName":"Acme","title":job,
                "applicationLink":"https://himalayas.app/jobs/"+job.replace(" ","-"),
                "locationRestrictions":["Brazil","Germany"],"pubDate":1780000000000}]}
        with patch("public_remote_feeds.fetch_json",side_effect=payload) as remote:
            jobs=fetch("himalayas","Product Manager, Product Owner","BR")
        self.assertEqual(len(jobs),2)
        self.assertEqual(remote.call_count,2)
        self.assertTrue(all(j["location"]=="Brazil, Germany" for j in jobs))
    def test_himalayas_malformed_location_is_not_worldwide(self):
        with patch("public_remote_feeds.fetch_json",return_value={"jobs":[{
                "companyName":"Acme","title":"Product Manager","applicationLink":"https://himalayas.app/jobs/unknown",
                "locationRestrictions":[{"alpha2":"XX"}]}]}):
            jobs=fetch("himalayas","Product Manager","BR")
        self.assertEqual(jobs[0]["location"],"")
    def test_remoteok_ignores_terms_and_external_url(self):
        rows=[{"legal":"Terms"},{"company":"A","position":"Product Owner","url":"https://remoteok.com/remote-jobs/pm-1"},{"company":"B","position":"Project Manager","url":"https://external.example/job"}]
        with patch("public_remote_feeds.fetch_json",return_value=rows):
            jobs=fetch("remoteok")
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]["source"],"remoteok")

if __name__=="__main__":unittest.main()
