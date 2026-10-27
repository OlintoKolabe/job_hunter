"""Evidence-based inHire empty-board versus malformed API responses."""
import unittest
from unittest.mock import patch

from collectors import pull


class InHireCollectorContractTests(unittest.TestCase):
    @patch("collectors.fetch_json")
    def test_published_tenant_with_no_jobs_is_not_an_error(self,fetch_json):
        # Real public API contracts observed for grupotaking and mtrix.
        fetch_json.return_value={"tenantName":"Grupo Taking","jobsPage":[]}
        result,jobs=pull("inHire","grupotaking")
        self.assertEqual(result["received"],0)
        self.assertEqual(jobs,[])

    @patch("collectors.fetch_json")
    def test_malformed_tenant_stays_error(self,fetch_json):
        fetch_json.return_value={"tenantName":"Broken","jobsPage":"broken"}
        with self.assertRaises(ValueError):pull("inHire","broken")

    @patch("collectors.fetch_json")
    def test_complete_valid_job_list_kept_without_role_prefilter(self,fetch_json):
        fetch_json.return_value={"tenantName":"BRQ","jobsPage":[
            {"jobId":"a1","displayName":"Product Owner","location":"Brazil"},
            {"jobId":"a2","displayName":"Backend Engineer","location":"Brazil"}]}
        result,jobs=pull("inHire","brq")
        self.assertEqual(result["received"],2)
        self.assertEqual(len(jobs),2)


if __name__=="__main__":unittest.main()
