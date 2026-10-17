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

    def test_mcp_not_claimed_integrated(self):
        self.assertIn("Render",CONNECTORS["Indeed MCP"])
        self.assertIn("Render",CONNECTORS["Firecrawl"])

if __name__=="__main__":
    unittest.main()
