"""Block 4.1 unit regressions; run without API keys or external requests."""
import unittest
import re
from unittest.mock import patch
from jd_retrieval import safe_public_url
from ai_interpreter import interpret
from block4_score import score_job,merge_semantic_requirements
from scripts.check_scope import validate

class Block41Tests(unittest.TestCase):
    def test_historical_job_is_passed_to_cache_lookup(self):
        from unittest.mock import Mock
        from app import jd_enrich,JDRequest
        row={"url":"https://example.com/jobs/123","title":"Product Manager","company":"Acme","source":"greenhouse"}
        with patch("app.require_auth"),patch("app.psycopg.connect"),patch("app.hydrate_jobs",return_value=([row],{})) as hydrate:
            response=jd_enrich(Mock(),JDRequest(jobs=[row],roles="Product Manager"))
        self.assertEqual(len(response["items"]),1)
        self.assertEqual(hydrate.call_args.args[1][0]["url"],row["url"])
    def test_cached_score_does_not_call_ai_again(self):
        from datetime import datetime,timezone
        from unittest.mock import Mock
        from jd_enrichment import hydrate_jobs
        url="https://example.com/jobs/123"
        jd="Required product roadmap management. "*20
        cur=Mock()
        cur.fetchall.return_value=[(url,jd,datetime.now(timezone.utc))]
        stored={"score":82,"confidence":"semantic_evidence","requirements":[]}
        with patch("jd_enrichment.get_cached",return_value=stored),patch("jd_enrichment.interpret") as interpret_ai,patch("jd_enrichment.score_job") as compute:
            jobs,coverage=hydrate_jobs(cur,[{"url":url,"title":"Product Manager","source":"greenhouse"}],"Product Manager",lambda v:v)
        self.assertEqual(jobs[0]["ranking"]["score"],82)
        self.assertEqual(coverage["cached"],1)
        interpret_ai.assert_not_called()
        compute.assert_not_called()
    def test_transferable_payment_context(self):
        rows=[{"name":n,"type":"obrigatorio","skill_id":sid} for n,sid in [("Pix payments",None),("Roadmap", "roadmap"),("Card settlement",None),("Fraud tooling",None)]]
        x=merge_semantic_requirements({"score":None},rows)
        self.assertGreater(x["score"],0)
        self.assertLess(x["score"],70)
        self.assertEqual(x["requirements"][0]["match_level"],"transferivel")

    def test_zero_when_four_requirements_have_no_evidence(self):
        rows=[{"name":n,"type":"obrigatorio","skill_id":None} for n in ("Python coding","QA automation","Algorithms","Computer science diploma")]
        x=merge_semantic_requirements({"score":None},rows)
        self.assertEqual(x["score"],0)

    def test_two_matches_do_not_fake_perfect_score(self):
        rows=[{"name":"Roadmap","type":"obrigatorio","skill_id":"roadmap"},{"name":"Backlog","type":"obrigatorio","skill_id":"backlog"}]
        self.assertIsNone(merge_semantic_requirements({"score":None},rows)["score"])

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
    def test_ai_unexpected_skill_id_type_is_safe(self):
        import json
        from io import BytesIO
        jd="Required roadmap expertise and backlog planning."
        payload={"choices":[{"message":{"content":json.dumps({"requirements":[
            {"name":"roadmap","type":"obrigatorio","skill_id":["roadmap"]},
            {"name":"backlog","type":"obrigatorio","skill_id":"backlog"}]})}}],"usage":{}}
        with patch.dict("os.environ",{"JH_AI_ENABLED":"1","OPENAI_API_KEY":"test-only"}):
            with patch("urllib.request.urlopen",return_value=BytesIO(json.dumps(payload).encode())):
                result=interpret(jd)
        self.assertIsNone(result["requirements"][0]["skill_id"])
        self.assertEqual(result["requirements"][1]["skill_id"],"backlog")
    def test_ai_normalizes_html_whitespace_before_literal_match(self):
        import json
        from io import BytesIO
        jd="<h3>Requirements</h3><li>Manage product&nbsp; roadmap</li>"
        payload={"choices":[{"message":{"content":json.dumps({"requirements":[
            {"name":"Manage product roadmap","type":"obrigatorio","skill_id":"roadmap"}
        ]})}}],"usage":{}}
        with patch.dict("os.environ",{"JH_AI_ENABLED":"1","OPENAI_API_KEY":"test-only"}):
            with patch("urllib.request.urlopen",return_value=BytesIO(json.dumps(payload).encode())):
                result=interpret(jd)
        self.assertEqual(len(result["requirements"]),1)
    def test_failed_interpretation_is_cooled_down(self):
        from datetime import datetime,timezone,timedelta
        from unittest.mock import Mock
        from score_repository import get_cached
        cur=Mock()
        cur.fetchone.return_value=({"score":None,"_ai_retry_later":True},"ai_error",datetime.now(timezone.utc))
        with patch.dict("os.environ",{"JH_AI_ENABLED":"1","OPENAI_API_KEY":"test-only"}):
            result=get_cached(cur,"https://example.com/job","hash","Product Manager")
        self.assertTrue(result["_ai_retry_later"])
        cur.fetchone.return_value=({"score":None,"_ai_retry_later":True},"ai_error",datetime.now(timezone.utc)-timedelta(hours=2))
        with patch.dict("os.environ",{"JH_AI_ENABLED":"1","OPENAI_API_KEY":"test-only"}):
            self.assertIsNone(get_cached(cur,"https://example.com/job","hash","Product Manager"))
    def test_ai_empty_output_fails_explicitly(self):
        import json
        from io import BytesIO
        payload={"choices":[{"message":{"content":""}}]}
        with patch.dict("os.environ",{"JH_AI_ENABLED":"1","OPENAI_API_KEY":"test-only"}):
            with patch("urllib.request.urlopen",return_value=BytesIO(json.dumps(payload).encode())):
                with self.assertRaises(ValueError):
                    interpret("Required roadmap")
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
