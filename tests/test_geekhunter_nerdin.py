"""Gate 9: publicly observed JSON-LD shapes from GeekHunter and Nerdin."""
import json
import unittest
from unittest.mock import patch
from source_extensions import extra
from catalog_engine import source_tasks,run_task


GEEK_LIST='<script type="application/ld+json">'+json.dumps({
    "@type":"ItemList","itemListElement":[{"@type":"ListItem","url":
    "https://www.geekhunter.com/pt/confidential/jobs/product-owner-1","name":"Product Owner"}]})+'</script>'
NERDIN_LIST='<div class="vaga-card" data-href="vaga_emprego/vaga-product-manager-10001.php"><h3>Product Manager</h3></div>'

def ld_job(url, title):
    return '<script type="application/ld+json">'+json.dumps({
        "@type":"JobPosting","title":title,"url":url,"datePosted":"2026-10-23",
        "description":"Manage the product roadmap, backlog, discovery, prioritization and delivery. "*9,
        "hiringOrganization":{"name":"Acme"},"jobLocationType":"TELECOMMUTE",
        "applicantLocationRequirements":{"@type":"Country","name":"BRA"},
        "employmentType":["CONTRACTOR"],"baseSalary":{"currency":"BRL",
            "value":{"minValue":12000,"maxValue":16000,"unitText":"MONTH"}}})+'</script>'


class NewPublicSources(unittest.TestCase):
    def test_new_sources_are_catalog_tasks(self):
        tasks=source_tasks()
        self.assertIn(("geekhunter","public"),tasks)
        self.assertIn(("nerdin","product manager"),tasks)

    def test_geekhunter_listing_and_detail_preserve_evidence(self):
        with patch("source_extensions.public_board_html",side_effect=[GEEK_LIST,
                ld_job("https://www.geekhunter.com/pt/confidential/jobs/product-owner-1","Product Owner")]) as fetch:
            jobs,state,count=extra("geekhunter","public")
        self.assertEqual((state,count),("validado",1))
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]["company"],"Acme")
        self.assertEqual(jobs[0]["published"],"2026-10-23")
        self.assertEqual(jobs[0]["workplaceType"],"remote")
        self.assertEqual(jobs[0]["countryCode"],"BR")
        self.assertEqual(jobs[0]["salary"]["min"],12000)
        self.assertGreater(len(jobs[0]["description"]),300)
        self.assertEqual(fetch.call_count,2)

    def test_nerdin_listing_uses_official_jobposting_detail(self):
        with patch("source_extensions.public_board_html",side_effect=[NERDIN_LIST,
                ld_job("https://www.nerdin.com.br/vaga_emprego/vaga-product-manager-10001.php","Product Manager")]):
            jobs,state,count=extra("nerdin","product manager")
        self.assertEqual((state,count),("validado",1))
        self.assertEqual(jobs[0]["source"],"nerdin")
        self.assertEqual(jobs[0]["published"],"2026-10-23")
        self.assertEqual(jobs[0]["countryCode"],"BR")

    def test_incomplete_detail_never_becomes_false_complete_job(self):
        with patch("source_extensions.public_board_html",side_effect=[NERDIN_LIST,"<h1>Unavailable</h1>"]):
            jobs,state,count=extra("nerdin","product manager")
        self.assertEqual((state,count),("pendente",1))
        self.assertEqual(jobs,[])

    def test_unavailable_listing_is_pending_not_zero_jobs(self):
        with patch("source_extensions.public_board_html",side_effect=TimeoutError("source unavailable")):
            result,jobs=run_task("geekhunter","public")
        self.assertEqual(result["state"],"pendente")
        self.assertEqual(jobs,[])


if __name__ == "__main__":unittest.main()
