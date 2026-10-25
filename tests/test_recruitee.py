"""Regression contract for public Recruitee boards, with no network or paid calls."""
import unittest
from unittest.mock import patch

from catalog_engine import source_tasks, run_task, scan
from source_extensions import extra
from search_filters import analyze_filters
import app


class RecruiteeTests(unittest.TestCase):
    def test_catalog_and_existing_selector(self):
        tasks=source_tasks()
        for slug in ("asksuite", "curotec", "make", "tether", "ueni", "wizdaa"):
            self.assertIn(("recruitee",slug),tasks)
        self.assertEqual(len(tasks),len(set(tasks)))
        with patch.object(app,"require_auth"):
            sources=app.available_filters(None)["sources"]
        self.assertIn({"value":"recruitee","label":"Recruitee"},sources)

    def test_official_offer_metadata_survives_shared_collector(self):
        payload={"offers":[{
            "id":123,"title":"Product Manager", "careers_url":"https://asksuite.recruitee.com/o/product-manager",
            "published_at":"2026-10-24T10:00:00Z",
            "locations":[{"city":"Florianópolis","country":"Brazil"}],
            "description":"Own roadmap, discovery and delivery. "*12,
            "requirements":"Lead cross-functional product teams.",
            "workplaceType":"remote"
        }]}
        with patch("source_extensions.fetch_json",return_value=payload) as fetch:
            details,jobs=run_task("recruitee","asksuite")
        self.assertEqual(fetch.call_args.args[0],"https://asksuite.recruitee.com/api/offers/")
        self.assertEqual(details["state"],"validado")
        self.assertEqual(details["received"],1)
        self.assertEqual(jobs[0]["location"],"Florianópolis, Brazil")
        self.assertIn("cross-functional",jobs[0]["description"])
        self.assertEqual(jobs[0]["published"],"2026-10-24T10:00:00Z")
        self.assertEqual(jobs[0]["source_job_id"],"123")

    def test_unconfirmed_geography_or_date_is_not_invented(self):
        offer={"title":"Product Owner","careers_url":"https://ueni.recruitee.com/o/product-owner"}
        with patch("source_extensions.fetch_json",return_value={"offers":[offer]}):
            jobs,state,count=extra("recruitee","ueni")
        self.assertEqual((state,count),("validado",1))
        self.assertEqual(jobs[0]["published"],"")
        self.assertEqual(jobs[0]["location"],"")
        confirmed,review,_=analyze_filters(jobs,roles="Product Owner",country="BR",mode="remote",days=7)
        self.assertEqual(confirmed,[])
        self.assertEqual(len(review),1)

    def test_empty_or_invalid_response_is_honest(self):
        with patch("source_extensions.fetch_json",return_value={"offers":[]}):
            self.assertEqual(extra("recruitee","make"),( [],"sem_vagas",0))
        with patch("source_extensions.fetch_json",return_value={"offers":{}}):
            details,jobs=run_task("recruitee","make")
        self.assertEqual(details["state"],"pendente")
        self.assertEqual(jobs,[])

    def test_catalog_scan_reuses_existing_engine(self):
        with patch("source_extensions.fetch_json",return_value={"offers":[{
            "title":"Product Marketing Manager","careers_url":"https://tether.recruitee.com/o/product-marketing-manager"
        }]}):
            details,jobs=scan([("recruitee","tether")],workers=1)
        self.assertEqual(details[0]["source"],"recruitee")
        self.assertEqual(jobs[0]["board_source"],"recruitee")
        self.assertEqual(jobs[0]["board_slug"],"tether")


if __name__=="__main__":unittest.main()
