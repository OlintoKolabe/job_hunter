import io, json, os, unittest
from unittest.mock import patch, MagicMock
from resume_engine import build_plan, render_docx, audit
import resume_hybrid as h

JD="Product Manager responsável por roadmap, backlog, pesquisa de usuários e stakeholders."
class HybridResumeTests(unittest.TestCase):
    def setUp(self):
        self.plan=build_plan(JD,"Product Manager")
    def test_no_api_when_disabled(self):
        cursor=MagicMock()
        with patch.dict(os.environ,{"JH_CV_AI_ENABLED":"0","OPENAI_API_KEY":"dummy"}):
            plan,usage=h.apply_hybrid(cursor,"example.com/vaga",JD,self.plan)
        self.assertEqual(usage["ai_calls"],0)
        cursor.execute.assert_not_called()
    def test_unverified_specialization_rejected(self):
        self.assertIsNone(h.validate_text({"summary":"Especialista em Oracle, PowerBuilder e arquitetura de software com experiência em gestão de produtos.","source_ids":["1"]},self.plan))
    def test_unsupported_metrics_rejected(self):
        self.assertIsNone(h.validate_text({"summary":"Responsável por um crescimento de 900% em dois meses com lideranças globais e entregas ágeis.","source_ids":["1"]},self.plan))
    def test_summary_must_identify_sources(self):
        self.assertIsNone(h.validate_text({"summary":"Profissional com experiência em produto digital, colaboração com stakeholders e roadmaps.","source_ids":["99999"]},self.plan))
    def test_micro_cost_bound(self):
        self.assertLessEqual(h.price({"prompt_tokens":1700,"completion_tokens":220}),0.002)
    def test_cache_skips_ai(self):
        cursor=MagicMock()
        candidate={"summary":"Profissional com atuação em gestão de produtos e roadmaps digitais, alinhando decisões com stakeholders e equipes técnicas.","source_ids":[str(e["source_index"]) for e in self.plan["experience"] if e["facts"]][:1]}
        cursor.fetchone.return_value=(candidate,)
        with patch.dict(os.environ,{"JH_CV_AI_ENABLED":"1","OPENAI_API_KEY":"dummy"}):
            with patch.object(h,"request_micro_summary",side_effect=AssertionError("should not call")):
                plan,usage=h.apply_hybrid(cursor,"example.com/vaga",JD,self.plan)
        self.assertEqual(usage["mode"],"cached_hybrid")
        self.assertEqual(usage["ai_calls"],0)
    def test_fallback_when_model_claim_invalid(self):
        cursor=MagicMock()
        cursor.fetchone.side_effect=[None,(0.0,0.0),(1001,),("2026-10",0.002)]
        candidate={"summary":"Experiência comprovada como especialista em Oracle e PowerBuilder para engenharia financeira de alto desempenho.","source_ids":["1"]}
        with patch.dict(os.environ,{"JH_CV_AI_ENABLED":"1","OPENAI_API_KEY":"dummy"}):
            with patch.object(h,"request_micro_summary",return_value=(candidate,{"prompt_tokens":350,"completion_tokens":70})):
                plan,usage=h.apply_hybrid(cursor,"example.com/vaga",JD,self.plan)
        self.assertEqual(usage["mode"],"fallback")
        self.assertEqual(usage["ai_calls"],1)
        self.assertEqual(plan["summary"],self.plan["summary"])
    def test_render_unchanged_provenance(self):
        data=render_docx(self.plan)
        self.assertTrue(audit(self.plan,data)["factual_bullets_verified"])

if __name__=="__main__":unittest.main()
