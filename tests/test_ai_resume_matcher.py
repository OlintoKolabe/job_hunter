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

if __name__=="__main__":unittest.main()
