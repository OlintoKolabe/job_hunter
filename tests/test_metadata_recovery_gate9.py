"""Gate 9: public-detail fields may confirm eligibility; unknown stays unknown."""
import unittest
from unittest.mock import patch
from pathlib import Path

from eligibility_enrichment import enrich_inhire_before_filter,eligibility_audit
from search_filters import classify,search_terms


ROLE="Product Manager"
URL="https://example.inhire.app/vagas/12345678-aabb-ccdd-eeff-001122334455/product-manager"


def listing(**changes):
    return {"source":"inHire","title":"Product Manager","company":"Example",
            "url":URL,"location":"","published":"","description":"",**changes}


class MetadataRecoveryGate9(unittest.TestCase):
    def test_public_details_recover_country_mode_date_and_jd(self):
        raw=[listing()]
        details={"lastPublishedAt":"2026-10-22T12:00:00Z",
                 "description":"Responsible for the product roadmap and backlog. "*30,
                 "workplaceType":"Remote","location":"Brasil"}
        with patch("eligibility_enrichment.fetch_json",return_value=details) as fetch:
            enriched,metrics=enrich_inhire_before_filter(raw,ROLE)
        fetch.assert_called_once()
        self.assertEqual(metrics["complete"],1)
        self.assertEqual(enriched[0]["location"],"Brasil")
        self.assertEqual(enriched[0]["workplaceType"],"Remote")
        self.assertEqual(classify(raw[0],search_terms(ROLE),"BR","remote",7)[0],"review")
        self.assertEqual(classify(enriched[0],search_terms(ROLE),"BR","remote",7)[0],"confirmed")
        quality=eligibility_audit(raw,enriched,ROLE,"BR","remote",7)
        self.assertEqual(quality["recovered_confirmed"],1)
        self.assertEqual(quality["lost_confirmed"],0)

    def test_foreign_only_location_cannot_become_brazil_eligible(self):
        raw=[listing()]
        with patch("eligibility_enrichment.fetch_json",return_value={
            "publishedAt":"2026-10-22T00:00:00Z","workplaceType":"Remote",
            "location":"United States","description":"Product roadmap"}):
            enriched,_=enrich_inhire_before_filter(raw,ROLE)
        self.assertEqual(classify(enriched[0],search_terms(ROLE),"BR","remote",7)[0],"excluded")
        quality=eligibility_audit(raw,enriched,ROLE,"BR","remote",7)
        self.assertEqual(quality["recovered_confirmed"],0)

    def test_invalid_or_missing_date_never_passes_recent_window(self):
        with patch("eligibility_enrichment.fetch_json",return_value={
            "updatedAt":"2026-10-22T00:00:00Z","workplaceType":"Remote",
            "location":"Brasil","description":"Product roadmap"}):
            enriched,_=enrich_inhire_before_filter([listing()],ROLE)
        self.assertFalse(enriched[0].get("published"))
        self.assertEqual(classify(enriched[0],search_terms(ROLE),"BR","remote",7)[0],"review")

    def test_fetch_is_bounded_and_fails_closed(self):
        raw=[listing(url=URL.replace("12345678",str(i).zfill(8))) for i in range(20)]
        with patch("eligibility_enrichment.fetch_json",side_effect=TimeoutError):
            enriched,metrics=enrich_inhire_before_filter(raw,ROLE,limit=3)
        self.assertEqual(metrics["attempted"],3)
        self.assertEqual(metrics["failed"],3)
        self.assertEqual(metrics["deferred"],17)
        self.assertEqual(enriched,raw)

    def test_elapsed_request_defers_details_without_inventing_eligibility(self):
        raw=[listing()]
        with patch("eligibility_enrichment.fetch_json") as fetch:
            enriched,metrics=enrich_inhire_before_filter(raw,ROLE,remaining_budget_s=2)
        fetch.assert_not_called()
        self.assertEqual(metrics["deferred"],1)
        self.assertEqual(enriched,raw)

    def test_moderate_time_budget_limits_detail_calls_to_one_wave(self):
        raw=[listing(url=URL.replace("12345678",str(i).zfill(8))) for i in range(20)]
        with patch("eligibility_enrichment.fetch_json",return_value={"description":"Actual public detail"}) as fetch:
            _,metrics=enrich_inhire_before_filter(raw,ROLE,remaining_budget_s=12)
        self.assertEqual(fetch.call_count,8)
        self.assertEqual(metrics["deferred"],12)

    def test_other_sources_never_trigger_inhire_detail_calls(self):
        raw=[listing(source="Greenhouse")]
        with patch("eligibility_enrichment.fetch_json") as fetch:
            enriched,metrics=enrich_inhire_before_filter(raw,ROLE)
        fetch.assert_not_called()
        self.assertEqual(metrics["attempted"],0)
        self.assertEqual(enriched,raw)

    def test_new_localization_fields_can_be_objects_without_inference(self):
        raw=[listing()]
        with patch("eligibility_enrichment.fetch_json",return_value={
            "publishedAt":"2026-10-22T00:00:00Z","workplaceType":"Remote",
            "location":{"country":"Brazil","city":"São Paulo"}}):
            enriched,_=enrich_inhire_before_filter(raw,ROLE)
        self.assertEqual(enriched[0]["country"],"Brazil")
        self.assertEqual(enriched[0]["city"],"São Paulo")
        self.assertEqual(classify(enriched[0],search_terms(ROLE),"BR","remote",7)[0],"confirmed")

    def test_both_search_routes_expose_the_same_metadata_audit(self):
        source=Path("app.py").read_text()
        self.assertEqual(source.count('"eligibility_quality":eligibility_quality'),2)
        self.assertEqual(source.count('eligibility_audit(original_items,'),2)

    def test_ui_exposes_before_after_and_source_breakdown(self):
        source=Path("src/Opportunities.jsx").read_text()
        self.assertIn("Qualidade dos metadados — antes e depois da recuperação",source)
        self.assertIn("qualityTrace.recovered_confirmed",source)
        self.assertIn("qualityTrace.unknown_country_after",source)
        self.assertIn("Object.entries(qualityTrace.by_source)",source)


if __name__=="__main__":unittest.main()
