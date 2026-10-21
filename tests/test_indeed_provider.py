import unittest
from unittest.mock import patch,MagicMock
import indeed_provider
from search_filters import classify, search_terms, DEFAULT_ROLES

class IndeedIntegrationTests(unittest.TestCase):
    def test_disabled_without_key(self):
        with patch.dict("os.environ",{"HASDATA_API_KEY":""}):
            self.assertFalse(indeed_provider.enabled())
            with self.assertRaises(RuntimeError):indeed_provider.search("product manager")
    def test_parses_brazil_remote_results(self):
        import json
        payload={"jobs":[{"title":"Product Manager","company":"Exemplo","url":"https://br.indeed.com/viewjob?jk=abc","location":"Brasil - remoto","isoDate":"2026-10-20T12:00:00Z","description":"Gestão de produto digital"}]}
        reply=MagicMock();reply.read.return_value=json.dumps(payload).encode()
        ctx=MagicMock();ctx.__enter__.return_value=reply
        with patch.dict("os.environ",{"HASDATA_API_KEY":"test-key"}),patch("indeed_provider.urllib.request.urlopen",return_value=ctx) as urlopen:
            jobs=indeed_provider.search("product manager")
        self.assertEqual(len(jobs),1)
        self.assertEqual(jobs[0]["source"],"indeed")
        self.assertEqual(classify(jobs[0],search_terms(DEFAULT_ROLES),"BR","remote",0)[0],"confirmed")
        self.assertIn("br.indeed.com",urlopen.call_args.args[0].full_url)
    def test_no_jobs_is_not_fake_data(self):
        import json
        reply=MagicMock();reply.read.return_value=json.dumps({"jobs":[]}).encode()
        ctx=MagicMock();ctx.__enter__.return_value=reply
        with patch.dict("os.environ",{"HASDATA_API_KEY":"test-key"}),patch("indeed_provider.urllib.request.urlopen",return_value=ctx):
            self.assertEqual(indeed_provider.search("product manager"),[])
if __name__=="__main__":unittest.main()
