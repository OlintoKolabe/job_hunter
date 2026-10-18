"""Block 4.1 unit regressions; run without API keys or external requests."""
import unittest
from unittest.mock import patch
from jd_retrieval import safe_public_url
from ai_interpreter import interpret
from block4_score import score_job
from scripts.check_scope import validate

class Block41Tests(unittest.TestCase):
    def test_secret_unset_means_no_ai(self):
        with patch.dict("os.environ",{"JH_AI_ENABLED":"0","OPENAI_API_KEY":"dummy"}):
            self.assertIsNone(interpret("required project management"))
    def test_local_addresses_blocked(self):
        for url in ["http://example.com/jobs/1","https://localhost/","https://127.0.0.1/","https://10.0.0.1/"]:
            self.assertFalse(safe_public_url(url),url)
    def test_no_jd_does_not_create_perfect_fit(self):
        out=score_job({"title":"Product Manager","description":""},"Product Manager")
        self.assertIsNone(out["score"])
    def test_gate_does_not_allow_new_file(self):
        contract={"allowed_files":["app.py"],"forbidden_paths":[],"base_ref":"sha","feature_ref":"branch"}
        self.assertEqual(validate(["src/Unauthorized.jsx"],contract),["src/Unauthorized.jsx"])

if __name__=="__main__":
    unittest.main()
