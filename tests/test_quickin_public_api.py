import json
import unittest
from unittest.mock import patch
from catalog_engine import extra_pull

class QuickinPublicApiTests(unittest.TestCase):
    def test_public_api_parses_company_location_and_public_job_url(self):
        payload=[{"_id":"abc123","publicate":"published","title":"Product Owner",
            "career_url":"https://jobs.quickin.io/example/jobs/abc123",
            "company_id":{"name":"Empresa Brasileira"},"city":"Goiânia",
            "region":"GO","country":"BR","created_at":"2026-10-19",
            "description":"Gestão de backlog","requirements":"Scrum"},
            {"_id":"unpublished","publicate":"internal","title":"Analista de Negócios"}]
        with patch("catalog_engine.read",return_value=(json.dumps(payload).encode(),200)) as read:
            jobs,state=extra_pull("quickin","example")
        self.assertEqual(state,"ok")
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]["company"],"Empresa Brasileira")
        self.assertEqual(jobs[0]["location"],"Goiânia, GO, BR")
        self.assertIn("backlog",jobs[0]["description"])
        self.assertEqual(read.call_count,1)

if __name__=="__main__":unittest.main()
