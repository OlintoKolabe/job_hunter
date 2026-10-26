"""P0 canary: tenant-bound defaults, source priority and eligibility invariants."""
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException

import multiuser as mu
from app import resolved_search_filters, ordered_catalog_tasks, WARM_SOURCE_TASKS
from search_filters import classify, search_terms


class P0SearchRegressionTests(unittest.TestCase):
    def _resolve(self, profile, query=None, supplied="Product Manager", days=30):
        with patch.object(mu, "enabled", True):
            token=mu.current_profile.set(profile)
            try:
                return resolved_search_filters(SimpleNamespace(query_params=query or {}),
                                               supplied, "BR", "remote", days)
            finally:
                mu.current_profile.reset(token)

    def test_missing_parameters_use_active_account_not_fathers_defaults(self):
        marcus={"roles":["Data Scientist","Data Engineer"],"country":"GLOBAL","mode":"remote","days":0}
        self.assertEqual(self._resolve(marcus),("Data Scientist, Data Engineer","GLOBAL","remote",0))

    def test_explicit_subselection_preserves_selected_filters(self):
        profile={"roles":["Product Manager","Product Owner"],"country":"BR","mode":"remote","days":7}
        query={"roles":"Product Owner","country":"BR","mode":"remote","days":"7"}
        self.assertEqual(self._resolve(profile,query,"Product Owner",7),
                         ("Product Owner","BR","remote",7))

    def test_cannot_search_fathers_role_from_unrelated_profile(self):
        profile={"roles":["Data Scientist"],"country":"GLOBAL","days":0}
        with self.assertRaises(HTTPException) as exc:
            self._resolve(profile,{"roles":"Product Manager"},"Product Manager")
        self.assertEqual(exc.exception.status_code,400)

    def test_stable_brazil_starter_boards_are_prioritized_once(self):
        tasks=[("lever","other"),("inhire","brq"),("ashby","belvo"),
               ("greenhouse","rdstation"),("lever","other2")]
        ordered=ordered_catalog_tasks(tasks)
        self.assertEqual(ordered[:3],[("ashby","belvo"),("greenhouse","rdstation"),("inhire","brq")])
        self.assertEqual(len(ordered),len(tasks))
        self.assertIn(("inhire","brq"),WARM_SOURCE_TASKS)

    def test_brazil_remote_is_classified_consistently_across_sources(self):
        now=datetime.now(timezone.utc).isoformat()
        terms=search_terms("Product Manager")
        for source in ("ashby","greenhouse","lever","inhire","quickin","gupy"):
            with self.subTest(source=source):
                job={"source":source,"title":"Product Manager",
                     "location":"Brazil - Remote","published":now}
                self.assertEqual(classify(job,terms,"BR","remote",7)[0],"confirmed")
                job["location"]="United States - Remote"
                self.assertEqual(classify(job,terms,"BR","remote",7)[0],"excluded")
                job["location"]="Brazil - Hybrid"
                self.assertEqual(classify(job,terms,"BR","remote",7)[0],"excluded")
                job["location"]="Brazil - Remote"
                job["published"]=(datetime.now(timezone.utc)-timedelta(days=20)).isoformat()
                self.assertEqual(classify(job,terms,"BR","remote",7)[0],"excluded")

    def test_catalog_strides_cover_every_offset_without_duplicates(self):
        source=Path(__file__).resolve().parent.parent.joinpath("src","Opportunities.jsx").read_text()
        self.assertIn("const scanConcurrency=2",source)
        self.assertIn("offset+=scanBatchSize*scanConcurrency",source)
        self.assertNotIn("nextIntermediateRanking",source)
        first=list(range(0,336,12))
        second=list(range(6,336,12))
        self.assertEqual(sorted(first+second),list(range(0,336,6)))


if __name__=="__main__":
    unittest.main()
