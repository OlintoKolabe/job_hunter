"""Regression checks for job discovery coverage without external requests."""
import unittest
from unittest.mock import patch
import app

class CoverageTests(unittest.TestCase):
    def test_distinct_urls_same_company_and_title_survive(self):
        jobs=[
            {"url":"https://example.com/jobs/123","company":"Acme","title":"Product Manager"},
            {"url":"https://example.com/jobs/456","company":"Acme","title":"Product Manager"},
            {"url":"https://example.com/jobs/123","company":"Acme","title":"Product Manager"},
        ]
        self.assertEqual(len(app.unique_jobs_by_url(jobs)),2)

    def test_linkedin_discovery_covers_default_families(self):
        with patch.object(app,"source_tasks",return_value=[]),patch.object(app.psycopg,"connect") as connect:
            conn=connect.return_value.__enter__.return_value
            conn.cursor.return_value.__enter__.return_value.fetchall.return_value=[]
            tasks=app.active_source_tasks()
        linkedin={term for src,term in tasks if src=="linkedin_guest"}
        for term in ("product manager","product owner","project manager","marketing",
                     "growth","business analyst","pmo","gerente de projetos"):
            self.assertIn(term,linkedin)
        self.assertFalse(any(src=="gupy" for src,_ in tasks))

if __name__=="__main__":unittest.main()
