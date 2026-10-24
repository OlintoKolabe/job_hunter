"""Gate 9: source fields must not disappear between provider and filter."""
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from collectors import item, preserve_eligibility_fields
from eligibility_enrichment import enrich_inhire_before_filter
from search_filters import classify, search_terms


class SourceFidelityTests(unittest.TestCase):
    def test_provided_metadata_survives_normalization(self):
        raw = {"workplaceType": "remote", "countryCode": "BR", "salary": {"min": 9000, "max": 14000, "currency": "BRL"},
               "seniority": "Senior", "department": "Product", "employmentType": "Full-time", "id": "requisition-101"}
        job = preserve_eligibility_fields(item("A", "Product Manager", "https://example.org/job", "Brazil", "Ashby"), raw)
        for field in ("workplaceType", "countryCode", "salary", "seniority", "department", "employmentType", "source_job_id"):
            self.assertIn(field, job)
        self.assertEqual(job["salary"]["min"], 9000)

    def test_all_role_relevant_inhire_details_are_checked_in_bounded_batches(self):
        date = (datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        jobs = [{"source":"inHire", "title":"Product Manager", "company":"brq",
                 "url":f"https://brq.inhire.app/vagas/{i}/product-manager",
                 "location":"Brazil Remote", "published":"", "description":""} for i in range(19)]
        with patch("eligibility_enrichment.fetch_json", return_value={"jobPage":{
            "publishedAt":date,"description":"Own the product roadmap and backlog. "*20}}) as fetch:
            enriched, metrics = enrich_inhire_before_filter(jobs, "Product Manager")
        self.assertEqual(fetch.call_count, 19)
        self.assertEqual(metrics["complete"],19)
        self.assertEqual(metrics["deferred"],0)
        self.assertTrue(all(classify(j,search_terms("Product Manager"),"BR","remote",7)[0]=="confirmed" for j in enriched))

    def test_provider_error_is_distinguished_from_not_yet_fetched(self):
        jobs = [{"source":"inHire", "title":"Product Manager", "url":f"https://brq.inhire.app/vagas/{i}/product-manager",
                 "description":"", "published":""} for i in range(3)]
        with patch("eligibility_enrichment.fetch_json", side_effect=TimeoutError):
            result,metrics=enrich_inhire_before_filter(jobs,"Product Manager",limit=2)
        self.assertEqual(metrics["failed"],2)
        self.assertEqual(metrics["deferred"],1)
        self.assertEqual([j["source_detail_status"] for j in result],["error","error","pending"])

    def test_inhire_detail_preserves_real_salary_and_never_uses_created_at_as_publication(self):
        job={"source":"inHire","title":"Product Manager","url":"https://brq.inhire.app/vagas/77/product-manager",
             "published":"","description":""}
        with patch("eligibility_enrichment.fetch_json",return_value={"jobPage":{
                "createdAt":"2026-10-24", "description":"Product roadmap "*30,
                "salary":{"min":10000,"max":15000,"currency":"BRL"},
                "workplaceType":"remote","countryCode":"BR"}}):
            result,metrics=enrich_inhire_before_filter([job],"Product Manager")
        self.assertEqual(metrics["complete"],1)
        self.assertFalse(result[0].get("published"))
        self.assertEqual(result[0]["salary"]["min"],10000)
        self.assertEqual(result[0]["workplaceType"],"remote")

    def test_successful_empty_detail_is_not_called_extraction_error(self):
        job={"source":"inHire","title":"Product Manager","url":"https://brq.inhire.app/vagas/77/product-manager",
             "published":"","description":""}
        with patch("eligibility_enrichment.fetch_json",return_value={"jobPage":{}}):
            result,metrics=enrich_inhire_before_filter([job],"Product Manager")
        self.assertEqual(metrics["absent"],1)
        self.assertEqual(metrics["failed"],0)
        self.assertEqual(result[0]["source_detail_status"],"source_absent")


if __name__ == "__main__": unittest.main()
