"""Gate 9: real-source contract fixtures for early, free metadata enrichment."""
import unittest
from unittest.mock import patch
from datetime import datetime,timezone,timedelta

from eligibility_enrichment import enrich_inhire_before_filter
from collectors import item
from search_filters import classify,search_terms,geo_verdict,role_match


class EligibilityGate9(unittest.TestCase):
    def test_inhire_detail_is_read_before_date_filter(self):
        recent=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        job={"source":"inHire","title":"Product Manager","company":"brq",
             "url":"https://brq.inhire.app/vagas/123/product-manager",
             "location":"Brazil Remote","workplaceType":"remote","published":"","description":""}
        self.assertEqual(classify(job,search_terms("Product Manager"),"BR","remote",7),("review","data"))
        with patch("eligibility_enrichment.fetch_json",return_value={"publishedAt":recent,
                "description":"Required product roadmap, stakeholder management, backlog and Scrum. "*12}) as fetch:
            output,stats=enrich_inhire_before_filter([job],"Product Manager")
        self.assertEqual(stats["complete"],1)
        self.assertEqual(fetch.call_args.args[1],{"X-Tenant":"brq"})
        self.assertEqual(classify(output[0],search_terms("Product Manager"),"BR","remote",7),("confirmed",""))

    def test_no_update_timestamp_as_publication_evidence(self):
        job={"source":"inHire","title":"Product Owner","url":"https://radix.inhire.app/vagas/123/po"}
        with patch("eligibility_enrichment.fetch_json",return_value={"updatedAt":"2026-10-23", "description":"Full JD"}):
            output,_=enrich_inhire_before_filter([job],"Product Owner")
        self.assertFalse(output[0].get("published"))

    def test_public_details_only_for_matching_titles_and_bounded(self):
        records=[{"source":"inHire","title":"Product Manager","url":f"https://brq.inhire.app/vagas/{i}/pm"} for i in range(4)]
        records.append({"source":"inHire","title":"Software Engineer","url":"https://brq.inhire.app/vagas/other/dev"})
        with patch("eligibility_enrichment.fetch_json",return_value={"publishedAt":"2026-10-22"}) as fetch:
            result,stats=enrich_inhire_before_filter(records,"Product Manager",limit=2)
        self.assertEqual(fetch.call_count,2)
        self.assertEqual(stats["deferred"],2)
        self.assertFalse(result[-1].get("published"))

    def test_cross_country_with_explicit_brazil_is_eligible(self):
        self.assertEqual(geo_verdict({"location":"Brazil / Germany"},"BR"),"eligible")
        self.assertEqual(geo_verdict({"location":"Remote - Germany"},"BR"),"excluded")

    def test_explicit_pm_does_not_include_product_analyst(self):
        self.assertFalse(role_match("Product Analyst",search_terms("Product Manager")))
        self.assertTrue(role_match("Gerente de Produto Sênior",search_terms("Product Manager")))

    def test_numeric_date_normalizes_in_collector(self):
        row=item("Acme","Product Manager","https://example.com/pm","Brazil","Lever",1790000000000)
        self.assertTrue(row["published"].startswith("2026-"))


if __name__=="__main__":unittest.main()
