"""Block 4.1 unit regressions; run without API keys or external requests."""
import unittest
import re
from unittest.mock import patch
from jd_retrieval import safe_public_url
from ai_interpreter import interpret
from block4_score import score_job,merge_semantic_requirements
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
    def test_one_matching_requirement_does_not_mean_100_percent(self):
        jd="Requirements: must have experience with product roadmap. "+("Business context and team details. "*15)
        out=score_job({"title":"Product Manager","description":jd},"Product Manager")
        self.assertIsNone(out["score"])
    def test_short_jd_does_not_generate_a_score(self):
        jd="Requirements: must have product roadmap. Must have backlog. Must have Scrum. Must have CRM."
        out=score_job({"title":"Product Manager","description":jd},"Product Manager")
        self.assertIsNone(out["score"])
    def test_semantic_scoring_uses_only_documented_skills(self):
        rows=[
            {"name":"roadmap","type":"obrigatorio","skill_id":"roadmap"},
            {"name":"backlog","type":"obrigatorio","skill_id":"backlog"},
            {"name":"project planning","type":"obrigatorio","skill_id":None},
            {"name":"crm","type":"desejavel","skill_id":"crm"}
        ]
        score=merge_semantic_requirements({"score":None},rows)
        self.assertEqual(score["score"],70)
        self.assertEqual(score["unverified_count"],1)
    def test_semantic_evidence_id_matches_documented_skill(self):
        rows=[{"name":"roadmap","type":"obrigatorio","skill_id":"roadmap"},
              {"name":"unproven expertise","type":"obrigatorio","skill_id":None},
              {"name":"backlog","type":"obrigatorio","skill_id":"backlog"},
              {"name":"crm","type":"desejavel","skill_id":"crm"}]
        out=merge_semantic_requirements({"score":None},rows)
        self.assertEqual(out["requirements"][0]["evidence_id"],"roadmap")
        self.assertIsNone(out["requirements"][1]["evidence_id"])
        self.assertLess(out["score"],100)
    def test_ai_discards_requirements_not_in_jd(self):
        import json
        from io import BytesIO
        jd="Must have roadmap and backlog experience, plus CRM skills."
        response={"choices":[{"message":{"content":json.dumps({"requirements":[
            {"name":"roadmap","type":"obrigatorio","skill_id":"roadmap"},
            {"name":"invented SQL requirement","type":"obrigatorio","skill_id":None}
        ]})}}],"usage":{"prompt_tokens":30,"completion_tokens":20}}
        with patch.dict("os.environ",{"JH_AI_ENABLED":"1","OPENAI_API_KEY":"test-only"}):
            with patch("urllib.request.urlopen",return_value=BytesIO(json.dumps(response).encode())):
                result=interpret(jd)
        self.assertEqual([item["name"] for item in result["requirements"]],["roadmap"])
    def test_unknown_semantic_skills_are_not_awarded_points(self):
        rows=[{"name":str(i),"type":"obrigatorio","skill_id":"imaginary_skill"} for i in range(4)]
        self.assertIsNone(merge_semantic_requirements({"score":None},rows)["score"])
    def test_jsonld_script_pattern(self):
        html='<script type="application/ld+json">{"@type":"JobPosting"}</script>'
        pattern=r"""<script[^>]*\btype\s*=\s*(?:"application/ld\+json"|'application/ld\+json'|application/ld\+json)(?=[\s>])[^>]*>(.*?)</script>"""
        self.assertEqual(len(re.findall(pattern,html,re.I|re.S)),1)
    def test_html_whitespace_normalization(self):
        self.assertEqual(re.sub(r"\s+"," ","A  B\nC"),"A B C")
    def test_gate_does_not_allow_new_file(self):
        contract={"allowed_files":["app.py"],"forbidden_paths":[],"base_ref":"sha","feature_ref":"branch"}
        self.assertEqual(validate(["src/Unauthorized.jsx"],contract),["src/Unauthorized.jsx"])

if __name__=="__main__":
    unittest.main()
