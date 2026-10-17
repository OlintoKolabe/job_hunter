import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from collectors import pull
from catalog_engine import run_task, source_tasks
from source_extensions import CONNECTORS

class Phase3ContractTests(unittest.TestCase):
    def test_catalog_has_expected_sources(self):
        sources={s for s,_ in source_tasks()}
        for source in ("greenhouse","ashby","inhire","lever","quickin","bamboohr","zoho"):
            self.assertIn(source,sources)

    def test_blocked_employer_not_in_seed(self):
        self.assertFalse(any(slug.casefold() in ("kraken","kraken.com","payward") for _,slug in source_tasks()))

    def test_lever_false_http_200_is_error(self):
        with patch("collectors.fetch_json",return_value={"ok":False}):
            with self.assertRaisesRegex(ValueError,"Slug Lever rejeitado"):
                pull("Lever","invalid")

    def test_unknown_ats_is_pending(self):
        state,jobs=run_task("not-implemented","any")
        self.assertEqual(state["state"],"pendente")
        self.assertEqual(jobs,[])

    def test_quickin_spa_empty_not_claimed_zero_jobs(self):
        with patch("catalog_engine.extra_pull",return_value=([],"ok")):
            state,_=run_task("quickin","sample")
        self.assertEqual(state["state"],"pendente")

    def test_inhire_unparsed_is_pending(self):
        with patch("collectors.fetch_json",return_value={"data":{"items":[]}}):
            state,_=run_task("inhire","dummy")
        self.assertEqual(state["state"],"pendente")

    def test_scrapling_guarded_without_enable_flag(self):
        from scrapling_fallback import js_fallback
        with patch.dict("os.environ",{"JH_SCRAPLING_JS":"0"}):
            with self.assertRaisesRegex(RuntimeError,"desativado"):
                js_fallback("quickin","test")

    def test_search_filters_require_actual_location_and_mode(self):
        from search_filters import apply_filters
        rows=[{"title":"Product Manager","location":"Brazil - Remote","published":"2026-10-17","url":"https://x/a"},
              {"title":"Product Manager","location":"São Paulo - Hybrid","published":"2026-10-17","url":"https://x/b"},
              {"title":"Product Manager","location":"","published":"2026-10-17","url":"https://x/c"}]
        matched=apply_filters(rows,"Product Manager","BR","remote",30,"newest")
        self.assertEqual([j["url"] for j in matched],["https://x/a"])

    def test_latam_and_reverse_chronology(self):
        from search_filters import apply_filters
        rows=[{"title":"Product Owner","location":"LATAM Remote","published":"2026-10-16"},
              {"title":"Product Owner","location":"Brazil Remote","published":"2026-10-15"}]
        matched=apply_filters(rows,"Product Owner","LATAM","remote",30,"oldest")
        self.assertEqual([j["published"] for j in matched],["2026-10-15","2026-10-16"])

    def test_unknown_metadata_not_silently_lost(self):
        from search_filters import analyze_filters
        confirmed,review,counts=analyze_filters([{"title":"Gerente de Produto","url":"https://example.com/job","location":"Brasil","published":""}],"Product Manager","BR","remote",30)
        self.assertEqual(len(confirmed),0)
        self.assertEqual(len(review),1)
        self.assertEqual(review[0]["needs_verification"],["modalidade","data"])

    def test_known_wrong_mode_excluded(self):
        from search_filters import analyze_filters
        confirmed,review,counts=analyze_filters([{"title":"Product Manager","location":"São Paulo presencial","published":"2026-10-17"}],"Product Manager","BR","remote",30)
        self.assertEqual(confirmed,[])
        self.assertEqual(review,[])

    def test_inhire_public_jobs_page_parsing(self):
        from collectors import pull
        payload={"tenantName":"Empresa Exemplo","jobsPage":[{"displayName":"Product Owner","jobId":"abc123","location":"Brasil","workplaceType":"Remote"}]}
        with patch("collectors.fetch_json",return_value=payload):
            summary,jobs=pull("inHire","exemplo")
        self.assertEqual(summary["received"],1)
        self.assertEqual(jobs[0]["title"],"Product Owner")
        self.assertIn("/vagas/abc123/product-owner",jobs[0]["url"])
        self.assertIn("Remote",jobs[0]["location"])

    def test_gupy_public_api_yields_remote_brazil_listing(self):
        from source_extensions import extra
        payload={"data":[{"name":"Gerente de Produto","careerPageName":"Empresa Brasileira","jobUrl":"https://empresa.gupy.io/job/123","workplaceType":"remote","state":"Goiás","createdAt":"2026-10-17"}]}
        with patch("source_extensions.fetch_json",return_value=payload):
            jobs,state,total=extra("gupy","gerente de produto")
        self.assertEqual(total,1)
        self.assertEqual(state,"validado")
        self.assertEqual(jobs[0]["company"],"Empresa Brasileira")
        self.assertIn("Brasil",jobs[0]["location"])

    def test_mcp_not_claimed_integrated(self):
        self.assertIn("Render",CONNECTORS["Indeed MCP"])
        self.assertIn("Render",CONNECTORS["Firecrawl"])

if __name__=="__main__":
    unittest.main()
