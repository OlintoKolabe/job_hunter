"""Mocked contract tests: no real API calls or billing."""
import io
import json
import os
import unittest
from unittest.mock import patch
from docx import Document
from ai_resume_matcher import evaluate, tailored_plan, to_ranking, AIUnavailable
from resume_engine import audit, render_docx, EXPERIENCE

JD=("Senior Product Manager required to lead discovery, product roadmaps, stakeholders, "
    "backlog prioritization and Scrum delivery in a regulated business. "
    "Must have proven product ownership and leadership experience. "
    "Preferred: programming in Python and extensive Power BI dashboards.")

class AIResumeMatcherTests(unittest.TestCase):
    def test_no_key_no_paid_call(self):
        with patch.dict(os.environ,{"JH_AI_ENABLED":"0","OPENAI_API_KEY":""}):
            with self.assertRaises(AIUnavailable):
                evaluate(JD,"Senior Product Manager")

    def test_matcher_rejects_unproven_evidence_and_score_inflation(self):
        answer={"score":100,"reasoning":"Relevant PM experience, but gaps remain.",
                "requirements":[{"name":"product roadmaps","mandatory":True,"match":"direct","evidence_ids":["1:0"]},
                 {"name":"Python programming","mandatory":True,"match":"direct","evidence_ids":["999:9"]},
                 {"name":"Power BI dashboards","mandatory":False,"match":"unproven","evidence_ids":[]}]}
        with patch("ai_resume_matcher._ask",return_value=answer):
            result=evaluate(JD,"Senior Product Manager")
        self.assertEqual(result["requirements"][1]["match"],"unproven")
        self.assertLess(result["score"],80)
        ranking=to_ranking({"title":"Senior Product Manager","description":JD},"Product Manager",result)
        self.assertEqual(ranking["unverified_count"],2)
        self.assertEqual(ranking["mandatory_count"],2)

    def test_cv_is_ai_selected_and_does_not_invent_bullets(self):
        answer={"selected_fact_ids":["1:0","1:1","1:2","4:1","4:2"],
                "summary":"Profissional de produto com experiência em gestão de roadmaps e backlog."}
        with patch("ai_resume_matcher._ask",return_value=answer):
            plan=tailored_plan(JD,"Senior Product Manager","Empresa de testes")
        self.assertEqual(plan["cv_mode"],"ai_resume_matcher_evidence_v1")
        doc=render_docx(plan)
        self.assertTrue(audit(plan,doc)["factual_bullets_verified"])
        text=" ".join(x.text for x in Document(io.BytesIO(doc)).paragraphs)
        self.assertNotIn("Power BI dashboards",text)
        self.assertIn("Graduação",text)

    def test_cv_rejects_sparse_or_unknown_selection(self):
        with patch("ai_resume_matcher._ask",return_value={"selected_fact_ids":["999:9","1:0"]}):
            with self.assertRaises(ValueError):
                tailored_plan(JD,"Senior Product Manager")

    def test_ai_bullet_rewrites_require_original_fact_provenance(self):
        base={"selected_fact_ids":["1:0","1:1","1:2","4:1","4:2"],
              "summary":"Gestão de produtos, projetos e stakeholders.",
              "rewrites":[{"id":"1:0","text":"Gestão e criação de roadmaps de produto, priorizando impacto e valor percebido."},
                          {"id":"1:1","text":"Implementou SQL e Power BI para gerar ROI de 900% no departamento."}]}
        with patch("ai_resume_matcher._ask",return_value=base):
            plan=tailored_plan(JD,"Product Manager")
        facts=[f for entry in plan["experience"] for f in entry["facts"]]
        self.assertIn("Gestão e criação de roadmaps de produto, priorizando impacto e valor percebido.",facts)
        self.assertIn(EXPERIENCE[1]["facts"][1],facts)
        self.assertTrue(audit(plan,render_docx(plan))["factual_bullets_verified"])

    def test_post_filter_hydration_uses_ai_fit_and_existing_budget(self):
        from datetime import datetime,timezone
        from unittest.mock import Mock
        from jd_enrichment import hydrate_jobs
        url="https://example.com/job/1"
        cursor=Mock()
        cursor.fetchall.return_value=[(url,JD,datetime.now(timezone.utc))]
        ai={"score":68,"requirements":[{"name":"product roadmaps","mandatory":True,
             "match":"direct","evidence_ids":["1:0"]}],
             "reasoning":"Documented roadmaps","usage":{"prompt_tokens":100,"completion_tokens":80}}
        with patch.dict(os.environ,{"JH_AI_ENABLED":"1","OPENAI_API_KEY":"test-only","DATABASE_URL":"fake"}), \
             patch("jd_enrichment.get_cached",return_value=None), \
             patch("jd_enrichment.evaluate_ai",return_value=ai) as called, \
             patch("jd_enrichment.reserve",return_value=9), \
             patch("jd_enrichment.settle") as settled, \
             patch("jd_enrichment.save") as saved, \
             patch("jd_enrichment.psycopg.connect") as conn:
            result,_=hydrate_jobs(cursor,[{"url":url,"title":"Senior Product Manager",
                                           "description":JD}],"Product Manager",lambda x:x)
        self.assertEqual(result[0]["ranking"]["score"],68)
        self.assertEqual(result[0]["ranking"]["ai_evidence_source"],"resume_matcher_methodology")
        called.assert_called_once()
        settled.assert_called_once()
        saved.assert_called_once()
        self.assertEqual(result[0]["ai_status"],"interpreted")

    def test_authenticated_route_returns_actual_docx_not_chatgpt_url(self):
        import asyncio
        from unittest.mock import Mock
        import app as service
        result={"selected_fact_ids":["1:0","1:1","1:2","4:1","4:2"],
                "summary":"Experiência comprovada em produtos, roadmaps e gestão de equipes."}
        async def drain(response):
            return b"".join([part async for part in response.body_iterator])
        with patch.dict(os.environ,{"JH_AI_ENABLED":"1","OPENAI_API_KEY":"test-only"}), \
             patch("app.require_auth"), patch("app._cv_source",return_value=("example.com/job/1",JD)), \
             patch("score_repository.reserve",return_value=23), \
             patch("score_repository.settle"),patch("app.psycopg.connect"), \
             patch("ai_resume_matcher._ask",return_value=result):
            payload=service.ResumeAIRequest(url="https://example.com/job/1",title="Senior Product Manager",company="Example")
            response=service.ai_resume_download(payload,Mock())
            document=asyncio.run(drain(response))
        self.assertEqual(response.status_code,200)
        self.assertEqual(document[:2],b"PK")
        self.assertIn("wordprocessingml",response.media_type)
        self.assertIn("AI=ai_resume_matcher_evidence_v1",
                      Document(io.BytesIO(document)).core_properties.keywords)

    def test_failed_cv_without_provider_response_releases_full_reservation(self):
        from unittest.mock import Mock
        import app as service
        with patch.dict(os.environ,{"JH_AI_ENABLED":"1","OPENAI_API_KEY":"test-only"}), \
             patch("app.require_auth"), patch("app._cv_source",return_value=("example.com/job/1",JD)), \
             patch("score_repository.reserve",return_value=24), \
             patch("score_repository.settle") as settled, \
             patch("app.psycopg.connect"), \
             patch("ai_resume_matcher._ask",side_effect=ValueError("invalid response")):
            with self.assertRaises(service.HTTPException) as raised:
                service.ai_resume_download(service.ResumeAIRequest(
                    url="https://example.com/job/1",title="Senior Product Manager"),Mock())
        self.assertEqual(raised.exception.status_code,422)
        settled.assert_called_once_with(unittest.mock.ANY,24,0.0,False)

    def test_failed_cv_after_provider_response_charges_only_actual_tokens(self):
        from unittest.mock import Mock
        import app as service
        from ai_resume_matcher import _last_billable_usage, estimate_cost
        usage={"prompt_tokens":4000,"completion_tokens":800}
        def incomplete_response(*_args):
            _last_billable_usage.set(usage)
            return {"selected_fact_ids":["999:9"]}
        with patch.dict(os.environ,{"JH_AI_ENABLED":"1","OPENAI_API_KEY":"test-only"}), \
             patch("app.require_auth"), patch("app._cv_source",return_value=("example.com/job/1",JD)), \
             patch("score_repository.reserve",return_value=25), \
             patch("score_repository.settle") as settled, \
             patch("app.psycopg.connect"), \
             patch("ai_resume_matcher._ask",side_effect=incomplete_response):
            with self.assertRaises(service.HTTPException):
                service.ai_resume_download(service.ResumeAIRequest(
                    url="https://example.com/job/1",title="Senior Product Manager"),Mock())
        settled.assert_called_once_with(unittest.mock.ANY,25,estimate_cost(usage),False)

if __name__=="__main__":unittest.main()
