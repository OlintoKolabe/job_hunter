"""Gate 9 regression checks for the observed 30-second browser timeout.

Structural contracts complement public-source benchmarks and authenticated
canary tests; they cannot replace real end-to-end latency evidence.
"""
import inspect
import unittest
from pathlib import Path

import app
from eligibility_enrichment import enrich_inhire_before_filter


class SearchTimeoutGate9(unittest.TestCase):
    def test_independent_public_feeds_are_concurrent_in_all_source_search(self):
        source=inspect.getsource(app.search_jobs)
        self.assertIn("ThreadPoolExecutor(max_workers=5)",source)
        self.assertIn('for provider in ("workable","jobgether")',source)
        self.assertNotIn('pool.submit(collect,discovery_queries(roles),country,"all")',source)
        self.assertIn("pool.submit(fetch_public_remote,feed,roles,country)",source)
        self.assertIn("for future in as_completed(futures)",source)

    def test_search_budget_is_based_on_real_elapsed_time(self):
        for route in (app.search_jobs,app.catalog_scan):
            source=inspect.getsource(route)
            self.assertIn("started=time.monotonic()",source)
            self.assertIn("remaining_budget_s=18-(time.monotonic()-started)",source)

    def test_no_source_failure_blocks_other_catalog_batches(self):
        source=Path("src/Opportunities.jsx").read_text()
        self.assertLess(source.index("const initialPromise=requestJson("),source.index("for(let n=0;n<180;n++)"))
        self.assertIn("failedOffsets.push({offset,error:",source)
        self.assertIn("for(const failed of failedOffsets.slice(0,8))",source)
        self.assertIn("all.set(j.url",source)  # deduplicated by URL
        self.assertIn("Os resultados recebidos permanecem disponíveis",source)

    def test_ui_reports_actual_request_latency(self):
        source=Path("src/Opportunities.jsx").read_text()
        self.assertIn("AbortSignal.timeout(70000)",source)
        self.assertIn("_request_ms:Math.round(performance.now()-started)",source)
        self.assertIn("requestPerf.max_ms",source)
        self.assertIn("requestPerf.completed",source)

    def test_latency_is_reported_on_server(self):
        source=Path("app.py").read_text()
        self.assertIn("JH_SEARCH_REQUEST path=%s elapsed_ms=%d status=%d",source)
        self.assertIn('response.headers["Server-Timing"]',source)

    def test_budget_exhaustion_does_not_relabel_unknown_jobs(self):
        raw=[{"source":"inHire","title":"Product Manager","url":
              "https://radix.inhire.app/vagas/12345678-aaaa-bbbb-cccc-111111111111/product-manager",
              "published":"","location":"","description":""}]
        after,metrics=enrich_inhire_before_filter(raw,"Product Manager",remaining_budget_s=-1)
        self.assertEqual(raw,after)
        self.assertEqual(metrics["attempted"],0)
        self.assertEqual(metrics["deferred"],1)


if __name__=="__main__":
    unittest.main()
