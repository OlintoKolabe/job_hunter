"""Source boundary regression checks without external network access."""
import unittest
from unittest.mock import patch
from source_extensions import extra

class SourceIdentityTests(unittest.TestCase):
    def test_linkedin_results_use_ui_source_identifier(self):
        jobs=[{"title":"Product Manager","company":"Acme","location":"","url":"https://linkedin.com/jobs/view/123","source":""}]
        with patch("source_extensions.html_links",return_value=jobs):
            items,state,count=extra("linkedin_guest","product manager")
        self.assertEqual(count,1)
        self.assertEqual(state,"validado")
        self.assertEqual(items[0]["source"],"linkedin_guest")

if __name__=="__main__":unittest.main()
