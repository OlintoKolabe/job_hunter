"""P0 canary: tenant-bound defaults, source priority and eligibility invariants."""
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException

import multiuser as mu
from app import resolved_search_filters, ordered_catalog_tasks, WARM_SOURCE_TASKS, search_jobs, catalog_scan
from search_filters import classify, search_terms, discovery_queries
import inspect


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

    def test_catalog_round_robin_covers_sources_before_late_quickin_burst(self):
        tasks=[("quickin",f"q{i}") for i in range(15)]
        tasks += [("ashby",f"a{i}") for i in range(15)]
        tasks += [("greenhouse",f"g{i}") for i in range(15)]
        tasks += [("lever",f"l{i}") for i in range(15)]
        ordered=ordered_catalog_tasks(tasks)
        self.assertEqual(set(ordered),set(tasks))
        self.assertEqual(len(ordered),len(tasks))
        self.assertGreaterEqual(len(set(s for s,_ in ordered[:12])),4)
        self.assertLessEqual(sum(s=="quickin" for s,_ in ordered[:12]),3)

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

    def test_search_stops_old_runs_and_invalid_or_unauthorized_pages(self):
        source=Path(__file__).resolve().parent.parent.joinpath("src","Opportunities.jsx").read_text()
        self.assertIn("const activeSearchRef=useRef(null)",source)
        self.assertIn("activeSearchRef.current=null",source)
        self.assertIn("signal:searchSignal(65000)",source)
        self.assertIn("const scanWorker=async()=>",source)
        self.assertIn("if([400,401,403].includes(err.status))throw err",source)
        self.assertIn("offset=batch.next_offset",source)
        self.assertIn("await scanWorker();",source)
        self.assertNotIn("const scanConcurrency=2",source)
        self.assertNotIn("offset+=scanBatchSize*scanConcurrency",source)

    def test_only_successful_initial_starter_boards_are_skipped(self):
        first=inspect.getsource(search_jobs)
        later=inspect.getsource(catalog_scan)
        self.assertIn('pool.submit(collect,discovery_queries(roles),country,"all")',first)
        self.assertIn('skip_starter:str=""',later)
        self.assertIn('fetched &= WARM_SOURCE_TASKS',later)
        self.assertIn('tasks=[(src,slug) for src,slug in tasks if',later)
        frontend=Path(__file__).resolve().parent.parent.joinpath("src","Opportunities.jsx").read_text()
        self.assertIn("x.status==='ok'&&x.source&&x.term",frontend)
        self.assertIn("&skip_starter=",frontend)

    def test_junior_and_intern_roles_do_not_admit_unrelated_management(self):
        now=datetime.now(timezone.utc).isoformat()
        roles=search_terms("Estagiário de TI, Desenvolvedor Júnior, Desenvolvedor Front End Júnior")
        for title in ("IT Intern","Junior Software Developer","Junior Frontend Developer"):
            with self.subTest(title=title):
                job={"source":"ashby","title":title,"location":"Brazil - Remote","published":now}
                self.assertEqual(classify(job,roles,"BR","remote",7)[0],"confirmed")
        unrelated={"source":"ashby","title":"Commercial Operations Manager",
                   "location":"Brazil - Remote","published":now}
        self.assertEqual(classify(unrelated,roles,"BR","remote",7)[0],"excluded")
        self.assertIn("software engineer intern",discovery_queries("Estagiário de TI, Desenvolvedor Júnior"))
        # Existing Product Manager vocabulary must not admit junior developers.
        self.assertEqual(classify({"source":"ashby","title":"Junior Developer",
            "location":"Brazil - Remote","published":now},search_terms("Product Manager"),"BR","remote",7)[0],"excluded")

    def test_worldwide_himalayas_needs_explicit_brazil_proof(self):
        now=datetime.now(timezone.utc).isoformat()
        job={"source":"himalayas","title":"Product Manager","location":"Worldwide - Remote","published":now}
        self.assertEqual(classify(job,search_terms("Product Manager"),"BR","remote",7)[0],"review")
        job["location"]="Brazil - Remote"
        self.assertEqual(classify(job,search_terms("Product Manager"),"BR","remote",7)[0],"confirmed")


if __name__=="__main__":
    unittest.main()
