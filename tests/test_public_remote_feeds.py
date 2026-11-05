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
    def test_leveljobs_role_query_and_canonical_url(self):
        response={"data":[{"slug":"pm-acme","title":"Product Manager","company":"Acme","location":"Remote","posted_at":"2026-11-04T12:00:00Z"}]}
        with patch("public_remote_feeds.fetch_json",return_value=response) as get:
            jobs=fetch("leveljobs","Product Manager","BR")
        self.assertEqual(jobs[0]["url"],"https://jobsbylevel.com/jobs/pm-acme")
        self.assertIn("posted_within_hours=168",get.call_args.args[0])
    def test_remotejobs_org_verified_remote_field(self):
        response={"data":[{"title":"Business Analyst","company":{"name":"Acme"},"url":"https://remotejobs.org/remote-jobs/ba", "location":"Brazil", "posted_at":"2026-11-04T12:00:00Z","location_normalization":{"work_arrangement":"remote"}}]}
        with patch("public_remote_feeds.fetch_json",return_value=response):
            jobs=fetch("remotejobs_org","Business Analyst","BR")
        self.assertTrue(jobs[0]["remote"])
        self.assertEqual(jobs[0]["source"],"remotejobs_org")
    def test_public_source_one_query_failure_does_not_block_others(self):
        def response(url):
            if "Product+Owner" in url:raise TimeoutError("upstream")
            return {"data":[{"title":"Product Manager","url":"https://remotejobs.org/remote-jobs/product-manager"}]}
        with patch("public_remote_feeds.fetch_json",side_effect=response):
            jobs=fetch("remotejobs_org","Product Owner,Product Manager")
        self.assertEqual(len(jobs),1)
    def test_tavily_without_key_is_disabled_and_uses_no_credits(self):
        with patch.dict("os.environ",{"TAVILY_API_KEY":""}),patch("public_remote_feeds._tavily_search") as api:
            with self.assertRaisesRegex(ValueError,"não configurado"):
                fetch("tavily","Product Manager")
        api.assert_not_called()
    def test_tavily_results_do_not_invent_freshness_or_remote(self):
        with patch.dict("os.environ",{"TAVILY_API_KEY":"present"}),patch("public_remote_feeds._tavily_search",return_value={"results":[{"title":"Product Manager - Acme","url":"https://jobs.lever.co/acme/123","content":"Remote Brazil role"}]}):
            jobs=fetch("tavily","Product Manager")
        self.assertEqual(jobs[0]["published"],"")
        self.assertEqual(jobs[0]["location"],"")
    def test_catalog_adapter_returns_independent_source_attribution(self):
        from catalog_engine import run_task
        with patch("catalog_engine.fetch_public_remote",return_value=[{"url":"https://remotejobs.org/remote-jobs/example","source":"remotejobs_org"}]):
            status,jobs=run_task("remotejobs_org","Product Manager",allow_js=False)
        self.assertEqual(status["state"],"validado")
        self.assertEqual(jobs[0]["source"],"remotejobs_org")

if __name__=="__main__":unittest.main()
