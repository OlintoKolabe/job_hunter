import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from catalog_engine import extra_pull,run_task

class QuickinPublicApiTests(unittest.TestCase):
    @patch("catalog_engine.read")
    def test_confirmed_empty_public_board_is_not_a_failure(self,read):
        read.return_value=(json.dumps({"docs":[],"total":0,"limit":30,"page":1,"pages":1}).encode(),200)
        result,jobs=run_task("quickin","accountid",allow_js=False)
        self.assertEqual(result["state"],"sem_vagas")
        self.assertEqual(jobs,[])

    @patch("catalog_engine.read")
    def test_botcity_real_contract_id_and_docs_with_all_pages(self,read):
        # Exact public shape verified 27 Oct: Nuxt account_id + docs/total/pages.
        site={"slug":2,"account_id":3}
        html='<script id="__NUXT_DATA__" type="application/json">'+json.dumps([
            None,site,"botcity","67f6b4c5dcf76400135d3538"])+"</script>"
        def fake(url,**kwargs):
            if "/public/botcity/" in url:raise HTTPError(url,400,"Invalid account_id",{},None)
            if "jobs.quickin.io" in url:return html.encode(),200
            if "page=2" in url:return json.dumps({"docs":[{"_id":"2","title":"Business Analyst","publicate":"published"}]}).encode(),200
            return json.dumps({"docs":[{"_id":"1","title":"Product Owner","publicate":"published"}],
                "total":2,"page":1,"limit":1,"pages":2}).encode(),200
        read.side_effect=fake
        jobs,status=extra_pull("quickin","botcity")
        self.assertEqual(status,"ok")
        self.assertEqual([j["title"] for j in jobs],["Product Owner","Business Analyst"])
        self.assertTrue(any("page=2" in call.args[0] for call in read.call_args_list))

    def test_public_api_parses_company_location_and_public_job_url(self):
        payload=[{"_id":"abc123","publicate":"published","title":"Product Owner",
            "career_url":"https://jobs.quickin.io/example/jobs/abc123",
            "company_id":{"name":"Empresa Brasileira"},"city":"Goiânia",
            "region":"GO","country":"BR","created_at":"2026-10-19",
            "description":"Gestão de backlog","requirements":"Scrum"},
            {"_id":"unpublished","publicate":"internal","title":"Analista de Negócios"}]
        with patch("catalog_engine.read",return_value=(json.dumps(payload).encode(),200)) as read:
            jobs,state=extra_pull("quickin","example")
        self.assertEqual(state,"ok")
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]["company"],"Empresa Brasileira")
        self.assertEqual(jobs[0]["location"],"Goiânia, GO, BR")
        self.assertIn("backlog",jobs[0]["description"])
        self.assertEqual(read.call_count,1)

if __name__=="__main__":unittest.main()
