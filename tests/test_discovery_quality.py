"""Gate 9: source discovery and conservative eligibility are separate operations."""
import json
import unittest
from unittest.mock import patch

import app
from search_filters import classify, search_terms
from source_extensions import extra


class DiscoveryQualityTests(unittest.TestCase):
    def test_geekhunter_uses_official_keyword_query(self):
        listing='<script type="application/ld+json">'+json.dumps({
            "@type":"ItemList","itemListElement":[{"url":"https://www.geekhunter.com/pt/confidential/jobs/product-manager-1"}]})+'</script>'
        detail='<script type="application/ld+json">'+json.dumps({
            "@type":"JobPosting","title":"Product Manager","description":"Product planning and roadmap. "*20,
            "hiringOrganization":{"name":"Acme"},"datePosted":"2026-10-22"})+'</script>'
        with patch("source_extensions.public_board_html",side_effect=[listing,detail]) as request:
            jobs,state,count=extra("geekhunter","search:product")
        self.assertEqual((state,count,len(jobs)),("validado",1,1))
        self.assertIn("searchTerm=product",request.call_args_list[0].args[0])

    def test_geekhunter_zero_verified_results_not_failure(self):
        with patch("source_extensions.public_board_html",return_value="<h1>0 vagas disponíveis</h1>"):
            jobs,state,count=extra("geekhunter","search:marketing")
        self.assertEqual((jobs,state,count),([],"sem_vagas",0))

    def test_selected_role_drives_public_search_tasks(self):
        with patch.object(app,"source_tasks",return_value=[("geekhunter","public"),("nerdin","marketing")]),patch.object(app.psycopg,"connect") as connect:
            cur=connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
            cur.fetchall.return_value=[]
            tasks=app.active_source_tasks("Product Owner")
        self.assertIn(("geekhunter","search:product"),tasks)
        self.assertIn(("nerdin","product owner"),tasks)
        self.assertNotIn(("nerdin","marketing"),tasks)

    def test_adjacent_inhire_title_stays_unconfirmed_despite_jd_mentions(self):
        job={"source":"inhire","title":"Operations Manager","location":"Remote Brazil",
             "published":"2026-10-23","description":("Product discovery, roadmap, prioritization, stakeholders and product strategy. "*8)}
        outcome,reason=classify(job,search_terms("Product Manager"),"BR","remote",7)
        self.assertEqual(outcome,"review")
        self.assertIn("cargo_a_confirmar",reason)

    def test_no_date_is_tracked_per_source_not_mistaken_as_recent(self):
        jobs=[{"source":"inhire","title":"Product Manager","location":"Remote Brazil","published":""},
              {"source":"geekhunter","title":"Product Manager","location":"Remote Brazil","published":"2026-10-23"},
              {"source":"inhire","title":"Backend Engineer","location":"Remote Brazil","published":"2026-10-23"}]
        counts=app.source_filter_quality(jobs,"Product Manager","BR","remote",7)
        self.assertEqual(counts["inhire"]["review_date"],1)
        self.assertEqual(counts["inhire"]["excluded_cargo"],1)
        self.assertEqual(counts["geekhunter"]["confirmed"],1)


if __name__=="__main__": unittest.main()
