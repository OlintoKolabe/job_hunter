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
    def test_selected_evidence_only_known_facts(self):
        sample=h.evidence_for_prompt(self.plan)
        chosen=[sample[0]["id"],sample[1]["id"],sample[6]["id"],sample[8]["id"],sample[12]["id"]]
        candidate={"evidence_ids":chosen}
        selected=h.selected_evidence(candidate,self.plan)
        self.assertIsNotNone(selected)
        for e in selected:
            from resume_engine import EXPERIENCE
            self.assertTrue(all(f in EXPERIENCE[e["source_index"]]["facts"] for f in e["facts"]))
        self.assertIsNone(h.selected_evidence({"evidence_ids":chosen[:-1]+["999:10"]},self.plan))
    def test_no_repeated_factual_bullets_after_reselection(self):
        ids=["1:0","1:1","2:0","4:0","6:0"]
        selected=h.selected_evidence({"evidence_ids":ids},self.plan)
        self.assertIsNotNone(selected)
        new_plan={**self.plan,"experience":selected}
        self.assertTrue(audit(new_plan,render_docx(new_plan))["factual_bullets_verified"])
    def test_cache_skips_ai(self):
        cursor=MagicMock()
        candidate={"summary":"Profissional com atuação em gestão de produtos e roadmaps digitais, alinhando decisões com stakeholders e equipes técnicas.","source_ids":[str(e["source_index"]) for e in self.plan["experience"] if e["facts"]][:1],"evidence_ids":["1:0","1:1","2:0","4:0","6:0"]}
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
    def test_partial_ai_result_applies_verified_evidence(self):
        cursor=MagicMock()
        cursor.fetchone.side_effect=[None,(0.0,0.0),(1234,),("2026-10",0.002)]
        candidate={"summary":"Especialista certificado em Oracle e PowerBuilder com experiência de longa duração.","source_ids":["1"],"evidence_ids":["1:0","2:0","4:0"]}
        with patch.dict(os.environ,{"JH_CV_AI_ENABLED":"1","OPENAI_API_KEY":"dummy"}):
            with patch.object(h,"request_micro_summary",return_value=(candidate,{"prompt_tokens":1600,"completion_tokens":200})):
                plan,usage=h.apply_hybrid(cursor,"example.com/new",JD,self.plan)
        self.assertEqual(usage["mode"],"hybrid")
        self.assertEqual(plan["summary"],self.plan["summary"])
        self.assertTrue(any(e["facts"] for e in plan["experience"] if e["source_index"]==2))
        self.assertTrue(audit(plan,render_docx(plan))["factual_bullets_verified"])
    def test_promotes_older_marketing_role_with_grounded_evidence(self):
        from resume_engine import EXPERIENCE
        picked=h.selected_evidence({"evidence_ids":["9:0","9:1","13:0"]},self.plan)
        self.assertIsNotNone(picked)
        baseline={f for e in self.plan["experience"] for f in e["facts"]}
        result={f for e in picked for f in e["facts"]}
        self.assertTrue(baseline.issubset(result))
        self.assertIn(EXPERIENCE[9]["facts"][0],result)
        self.assertIn(EXPERIENCE[13]["facts"][0],result)
        report=audit({**self.plan,"experience":picked},
                     render_docx({**self.plan,"experience":picked}))
        self.assertTrue(report["factual_bullets_verified"])
    def test_single_header_when_compact_role_promoted(self):
        from docx import Document
        picked=h.selected_evidence({"evidence_ids":["9:0","13:0"]},self.plan)
        data=render_docx({**self.plan,"experience":picked})
        txt="\\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
        self.assertEqual(txt.count("Diretor de marketing — Lagoa Parques e Hotéis"),1)
    def test_does_not_erase_baseline_on_sparse_ai_selection(self):
        picked=h.selected_evidence({"evidence_ids":["1:0"]},self.plan)
        self.assertIsNotNone(picked)
        original={f for e in self.plan["experience"] for f in e["facts"]}
        self.assertTrue(original.issubset({f for e in picked for f in e["facts"]}))
    def test_render_unchanged_provenance(self):
        data=render_docx(self.plan)
        self.assertTrue(audit(self.plan,data)["factual_bullets_verified"])

if __name__=="__main__":unittest.main()
