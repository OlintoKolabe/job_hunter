"""Block 4.1 unit regressions; run without API keys or external requests."""
import unittest
import re
from unittest.mock import patch
from jd_retrieval import safe_public_url
from ai_interpreter import interpret
from block4_score import score_job,merge_semantic_requirements
from scripts.check_scope import validate

class Block41Tests(unittest.TestCase):
    def test_paid_matchmaking_endpoint_is_retired(self):
        from unittest.mock import Mock
        from app import jd_enrich,JDRequest
        from fastapi import HTTPException
        row={"url":"https://example.com/jobs/123","title":"Product Manager","company":"Acme","source":"greenhouse"}
        with patch("app.require_auth"),patch("app.psycopg.connect"),patch("app.hydrate_jobs",return_value=([row],{})) as hydrate:
            with self.assertRaises(HTTPException) as raised:
                jd_enrich(Mock(),JDRequest(jobs=[row],roles="Product Manager"))
        self.assertEqual(raised.exception.status_code,410)
        hydrate.assert_not_called()
    def test_cached_score_does_not_call_ai_again(self):
        from datetime import datetime,timezone
        from unittest.mock import Mock
        from jd_enrichment import hydrate_jobs
        url="https://example.com/jobs/123"
        jd="Required product roadmap management. "*20
        cur=Mock()
        cur.fetchall.return_value=[(url,jd,datetime.now(timezone.utc))]
        stored={"score":82,"confidence":"semantic_evidence","requirements":[]}
        with patch("jd_enrichment.get_cached",return_value=stored),patch("jd_enrichment.evaluate_ai") as interpret_ai,patch("jd_enrichment.score_job") as compute:
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
        rows=[{"name":n,"type":"obrigatorio","skill_id":None} for n in ("Python coding","QA automation","Algorithms","Degree in computer science")]
        x=merge_semantic_requirements({"score":None},rows)
        self.assertEqual(x["score"],0)

    def test_two_matches_do_not_fake_perfect_score(self):
        rows=[{"name":"Roadmap","type":"obrigatorio","skill_id":"roadmap"},{"name":"Backlog","type":"obrigatorio","skill_id":"backlog"}]
        self.assertIsNone(merge_semantic_requirements({"score":None},rows)["score"])

    def test_old_semantic_cache_is_not_misrepresented_as_new_ai_fit(self):
        from datetime import datetime, timezone
        from unittest.mock import Mock
        from jd_enrichment import hydrate_jobs
        url="https://example.com/jobs/transfer"
        jd="Required payments roadmap experience. "*20
        cur=Mock()
        cur.fetchall.return_value=[(url,jd,datetime.now(timezone.utc))]
        with patch.dict("os.environ",{"JH_AI_ENABLED":"0","OPENAI_API_KEY":""}),patch("jd_enrichment.get_cached",return_value=None),patch("jd_enrichment.evaluate_ai") as ai,patch("jd_enrichment.save") as saved:
            jobs,_=hydrate_jobs(cur,[{"url":url,"title":"Payments PM"}],"Product Manager",lambda v:v)
        self.assertIsNone(jobs[0]["ranking"]["score"])
        self.assertEqual(jobs[0]["ai_status"],"disabled")
        ai.assert_not_called()
        saved.assert_not_called()

    def test_pm_collaboration_is_not_hands_on_coding(self):
        rows=[{"name":n,"type":"obrigatorio","skill_id":k} for n,k in
              [("Stakeholder management with software engineers","stakeholders"),
               ("Backlog","backlog"),("Roadmap","roadmap"),("Scrum","scrum")]]
        x=merge_semantic_requirements({"score":None},rows)
        self.assertGreater(x["score"],70)
        self.assertEqual(x["requirements"][0]["match_level"],"direta")

    def test_unrelated_skill_cannot_award_perfect_score(self):
        rows=[{"name":"Machine learning infrastructure","type":"obrigatorio","skill_id":"roadmap"},
              {"name":"Backlog","type":"obrigatorio","skill_id":"backlog"},
              {"name":"Roadmap","type":"obrigatorio","skill_id":"roadmap"},
              {"name":"CRM","type":"desejavel","skill_id":"crm"}]
        x=merge_semantic_requirements({"score":None},rows)
        self.assertLess(x["score"],100)

    def test_hard_technical_role_excludes_without_paid_ai(self):
        from block4_score import hard_role_mismatch
        self.assertTrue(hard_role_mismatch({"title":"Senior Software Engineer"}))
        self.assertTrue(hard_role_mismatch({"title":"QA Engineer"}))
        self.assertFalse(hard_role_mismatch({"title":"Technical Product Manager - Developer Experience"}))
        self.assertFalse(hard_role_mismatch({"title":"Product Manager working with software engineers"}))
    def test_hard_role_zero_is_returned_without_model_call(self):
        from datetime import datetime,timezone
        from unittest.mock import Mock
        from jd_enrichment import hydrate_jobs
        url="https://example.com/jobs/engineer"
        jd="Senior Software Engineer: write production code with Python and maintain CI. "*10
        cur=Mock()
        cur.fetchall.return_value=[(url,jd,datetime.now(timezone.utc))]
        with patch("jd_enrichment.get_cached",return_value=None),patch("jd_enrichment.evaluate_ai") as interpret_ai,patch("jd_enrichment.reserve") as reserve_ai,patch("jd_enrichment.save") as save:
            jobs,_=hydrate_jobs(cur,[{"url":url,"title":"Senior Software Engineer"}],"Product Manager",lambda v:v)
        self.assertEqual(jobs[0]["ranking"]["score"],0)
        self.assertEqual(jobs[0]["ai_status"],"not_needed")
        interpret_ai.assert_not_called()
        reserve_ai.assert_not_called()
        save.assert_called_once()

    def test_required_cs_degree_rejects_without_evidence(self):
        rows=[{"name":"Degree in computer science","type":"obrigatorio","skill_id":None},
              {"name":"Roadmap","type":"obrigatorio","skill_id":"roadmap"},
              {"name":"Backlog","type":"obrigatorio","skill_id":"backlog"},
              {"name":"Scrum","type":"desejavel","skill_id":"scrum"}]
        self.assertEqual(merge_semantic_requirements({"score":None},rows)["score"],0)

    def test_or_equivalent_experience_not_automatic_rejection(self):
        rows=[{"name":"Degree in computer science or equivalent experience","type":"obrigatorio","skill_id":None},
              {"name":"Roadmap","type":"obrigatorio","skill_id":"roadmap"},
              {"name":"Backlog","type":"obrigatorio","skill_id":"backlog"},
              {"name":"Scrum","type":"desejavel","skill_id":"scrum"}]
        self.assertGreater(merge_semantic_requirements({"score":None},rows)["score"],0)

    def test_business_product_role_with_engineering_words_stays_eligible(self):
        from block4_score import hard_role_mismatch
        self.assertFalse(hard_role_mismatch({"title":"Senior Product Manager - Software Engineering Platform"}))
        self.assertFalse(hard_role_mismatch({"title":"Product Owner / QA Automation Platform"}))
        self.assertTrue(hard_role_mismatch({"title":"Senior Software Engineer"}))

    def test_pm_core_competencies_are_not_discounted(self):
        rows=[{"name":n,"type":"obrigatorio","skill_id":None} for n in
              ("Product discovery and user research","Backlog prioritization",
               "Product metrics and KPIs","Roadmap planning")]
        result=merge_semantic_requirements({"score":None},rows)
        self.assertGreaterEqual(result["score"],90)
        self.assertEqual(result["match_summary"]["direct"],4)

    def test_desirable_sector_expertise_does_not_overrule_pm_core(self):
        rows=[{"name":n,"type":"obrigatorio","skill_id":None} for n in
              ("Product discovery","Backlog prioritization","Roadmap planning","Product analytics")]
        rows.extend([{"name":"Pix","type":"desejavel","skill_id":None},
                     {"name":"Open Finance domain knowledge","type":"desejavel","skill_id":None}])
        result=merge_semantic_requirements({"score":None},rows)
        self.assertGreaterEqual(result["score"],90)

    def test_advanced_spanish_mandatory_is_essential_gap(self):
        rows=[{"name":"Advanced Spanish required","type":"obrigatorio","skill_id":None},
              {"name":"Product discovery","type":"obrigatorio","skill_id":None},
              {"name":"Backlog","type":"obrigatorio","skill_id":"backlog"},
              {"name":"Roadmap","type":"obrigatorio","skill_id":"roadmap"}]
        result=merge_semantic_requirements({"score":None},rows)
        self.assertEqual(result["score"],0)
        self.assertEqual(result["confidence"],"essential_gap")

    def test_application_recommendation_is_distinct_from_professional_fit(self):
        from block4_score import recommend_application
        ranking={"score":67,"confidence":"semantic_evidence","requirements":[
            {"type":"obrigatorio","match_points":1,"match_level":"direta"},
            {"type":"obrigatorio","match_points":0.45,"match_level":"transferivel"},
            {"type":"obrigatorio","match_points":1,"match_level":"direta"},
            {"type":"desejavel","match_points":0,"match_level":"nao_comprovada"}]}
        result=recommend_application({"detected_mode":"remote","location":"Brazil Remote"},ranking)
        self.assertEqual(result["decision"],"recomendada")
        self.assertNotEqual(result["score"],ranking["score"])
    def test_application_recommendation_geo_knockout(self):
        from block4_score import recommend_application
        ranking={"score":90,"requirements":[{"type":"obrigatorio","match_points":1}]}
        result=recommend_application({"detected_mode":"hybrid","location":"São Paulo, Brazil"},ranking)
        self.assertEqual(result["score"],0)
        self.assertEqual(result["decision"],"nao_recomendada")
    def test_application_recommendation_core_knockout(self):
        from block4_score import recommend_application
        ranking={"score":0,"confidence":"essential_gap","requirements":[{"type":"obrigatorio","match_points":0}]}
        self.assertEqual(recommend_application({},ranking)["decision"],"nao_recomendada")
    def test_recommendation_unknown_fit_stays_unknown(self):
        from block4_score import recommend_application
        x=recommend_application({},{"score":None,"requirements":[]})
        self.assertIsNone(x["score"])
        self.assertEqual(x["decision"],"avaliar")
    def test_optional_gap_does_not_knock_out_recommendation(self):
        from block4_score import recommend_application
        rows=[{"type":"obrigatorio","match_points":1,"match_level":"direta"} for _ in range(5)]
        rows.append({"type":"desejavel","match_points":0,"match_level":"nao_comprovada"})
        result=recommend_application({"detected_mode":"remote"}, {"score":97,"requirements":rows})
        self.assertEqual(result["decision"],"recomendada")
    def test_recommendation_is_persisted_without_ai_on_cached_score(self):
        from datetime import datetime,timezone
        from unittest.mock import Mock
        from jd_enrichment import hydrate_jobs
        url="https://example.com/jobs/business-analyst"
        jd="Manage product roadmap and product discovery with stakeholders. "*20
        cur=Mock()
        cur.fetchall.return_value=[(url,jd,datetime.now(timezone.utc))]
        cached={"score":72,"confidence":"semantic_evidence","requirements":[
            {"name":"Product roadmap","type":"obrigatorio","match_points":1,"match_level":"direta"}]}
        with patch("jd_enrichment.get_cached",return_value=cached),patch("jd_enrichment.evaluate_ai") as ai:
            first,_=hydrate_jobs(cur,[{"url":url,"title":"Product Manager","detected_mode":"remote"}],"Product Manager",lambda v:v)
        self.assertIsNotNone(first[0]["ranking"]["application_recommendation"]["score"])
        self.assertTrue(any("jsonb_set" in str(call) for call in cur.execute.call_args_list))
        ai.assert_not_called()

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
            {"name":"SAP ABAP ERP programming","type":"obrigatorio","skill_id":None},
            {"name":"crm","type":"desejavel","skill_id":"crm"}
        ]
        score=merge_semantic_requirements({"score":None},rows)
        self.assertGreaterEqual(score["score"],65)
        self.assertLessEqual(score["score"],80)
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
    def test_legacy_ai_interpreter_never_calls_provider(self):
        with patch.dict("os.environ",{"JH_AI_ENABLED":"1","OPENAI_API_KEY":"test-only"}):
            with patch("urllib.request.urlopen",side_effect=AssertionError("OpenAI evaluation forbidden")) as provider:
                self.assertIsNone(interpret("Required roadmap expertise and backlog planning."))
                self.assertIsNone(interpret("<h3>Requirements</h3><li>Manage product roadmap</li>"))
        provider.assert_not_called()
    def test_failed_interpretation_is_persistently_cached(self):
        from datetime import datetime,timezone,timedelta
        from unittest.mock import Mock
        from score_repository import get_cached
        cur=Mock()
        cur.fetchone.return_value=({"score":None,"_ai_failed":True},"ai_error",datetime.now(timezone.utc))
        with patch.dict("os.environ",{"JH_AI_ENABLED":"1","OPENAI_API_KEY":"test-only"}):
            result=get_cached(cur,"https://example.com/job","hash","Product Manager")
        self.assertTrue(result["_ai_failed"])
        cur.fetchone.return_value=({"score":None,"_ai_failed":True},"ai_error",datetime.now(timezone.utc)-timedelta(hours=2))
        with patch.dict("os.environ",{"JH_AI_ENABLED":"1","OPENAI_API_KEY":"test-only"}):
            self.assertTrue(get_cached(cur,"https://example.com/job","hash","Product Manager")["_ai_failed"])
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
