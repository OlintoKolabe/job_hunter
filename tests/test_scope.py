import unittest
from scripts.check_scope import validate

CONTRACT = {
    "allowed_files": ["app.py", "scope/active.json", "scripts/check_scope.py"],
    "forbidden_paths": [".github/workflows/"],
    "base_ref": "abc123",
    "feature_ref": "feat/block4-1-ai-scoring",
}

class ScopeGateTest(unittest.TestCase):
    def test_allowed(self):
        self.assertEqual(validate(["app.py"], CONTRACT), [])
    def test_unknown_path_blocked(self):
        self.assertEqual(validate(["collectors.py"], CONTRACT), ["collectors.py"])
    def test_workflow_blocked(self):
        self.assertEqual(validate([".github/workflows/new.yml"], CONTRACT), [".github/workflows/new.yml"])
    def test_missing_identity_blocked(self):
        c = {**CONTRACT, "base_ref": ""}
        self.assertTrue(validate([], c))

if __name__ == "__main__":
    unittest.main()
