import io
import unittest
from docx import Document
from resume_engine import build_plan,render_docx,audit,EXPERIENCE,CONTACT

JD="We need a business analyst who manages stakeholder needs, roadmaps and backlog in Azure DevOps, works with product owners and defines user stories. Previous hands-on Oracle programming experience is a plus."

class ResumeEngineTests(unittest.TestCase):
    def test_document_provenance_survives_download_and_fallback(self):
        from resume_engine import CV_DOCUMENT_VERSION
        for mode in ("hybrid","cached_hybrid","fallback","cached_fallback","deterministic"):
            plan=build_plan(JD,"Senior Business Analyst")
            plan["cv_mode"]=mode
            plan["cv_build"]="abcdef123456"
            doc=Document(io.BytesIO(render_docx(plan)))
            tag=doc.core_properties.keywords
            self.assertIn("JobHunterCV="+CV_DOCUMENT_VERSION,tag)
            self.assertIn("AI="+mode,tag)
            self.assertIn("Build=abcdef123456",tag)
            self.assertIn("JD="+plan["jd_sha256"][:16],tag)
            self.assertTrue(audit(plan,render_docx(plan))["factual_bullets_verified"])
    def test_program_manager_gets_governance_evidence(self):
        from resume_engine import EXPERIENCE
        jd="Program Manager governance portfolio cross-functional teams risk project delivery budget"
        p=build_plan(jd,"Program Manager")
        detail={e["source_index"]:e["facts"] for e in p["experience"]}
        self.assertIn(2,detail)
        self.assertIn(8,detail)
        self.assertTrue(any("Governança corporativa" in f for f in detail[8]))
        self.assertTrue(audit(p,render_docx(p))["factual_bullets_verified"])
    def test_marketing_manager_highlights_earlier_marketing_leadership(self):
        p=build_plan("Marketing strategy CRM campaigns branding and marketing budget","Marketing Manager")
        detailed={e["source_index"] for e in p["experience"]}
        self.assertIn(9,detailed)
        self.assertTrue({9,11,12,13}&detailed)
    def test_generates_document_without_ai(self):
        p=build_plan(JD,"Senior Business Analyst")
        b=render_docx(p)
        a=audit(p,b)
        self.assertEqual(a["cost_usd"],0)
        self.assertEqual(a["ai_calls"],0)
        self.assertTrue(a["factual_bullets_verified"])
    def test_contact_and_chronology(self):
        p=build_plan(JD,"Senior Business Analyst")
        self.assertEqual([x["company"] for x in p["experience"]+p["additional_experience"]].__len__(),len(EXPERIENCE))
        from resume_engine import chronology_index
        self.assertEqual([chronology_index(EXPERIENCE[e["source_index"]]) for e in p["experience"]], sorted([chronology_index(EXPERIENCE[e["source_index"]]) for e in p["experience"]],reverse=True))
        doc=Document(io.BytesIO(render_docx(p)))
        content="\n".join(x.text for x in doc.paragraphs)
        for c in CONTACT.values():self.assertIn(c,content)
    def test_no_unverified_technical_claim(self):
        p=build_plan(JD,"Senior Business Analyst")
        b=render_docx(p)
        content="\n".join(x.text for x in Document(io.BytesIO(b)).paragraphs)
        self.assertNotIn("Oracle programming",content)
        self.assertNotIn("PowerBuilder",content)
    def test_reproducible_bytes_and_hash(self):
        p=build_plan(JD,"Senior Business Analyst")
        a=audit(p,render_docx(p))
        b=audit(p,render_docx(p))
        self.assertEqual(a["jd_sha256"],b["jd_sha256"])
    def test_no_duplicate_bullets_or_highlight_section(self):
        p=build_plan(JD,"Senior Business Analyst")
        doc=Document(io.BytesIO(render_docx(p)))
        text="\n".join(x.text for x in doc.paragraphs)
        self.assertNotIn("Competências e experiências relevantes para a vaga",text)
        bullets=[f for e in p["experience"] for f in e["facts"]]
        self.assertEqual(len(bullets),len(set(bullets)))
        self.assertTrue(all(text.count(f)==1 for f in bullets))
    def test_distinct_jds_select_distinct_relevant_evidence(self):
        a=build_plan("Business analyst backlog requirements user stories stakeholders Azure DevOps","Analyst")
        b=build_plan("Marketing digital paid ads CRM churn vendas growth leads aquisição","Growth")
        fa=[f for e in a["experience"] for f in e["facts"]]
        fb=[f for e in b["experience"] for f in e["facts"]]
        self.assertNotEqual(fa,fb)
        self.assertNotEqual(a["summary"],b["summary"])
    def test_document_maintains_earlier_roles_compact(self):
        p=build_plan(JD,"Senior Business Analyst")
        self.assertTrue(p["additional_experience"])
        self.assertTrue(all("facts" not in e for e in p["additional_experience"]))
    def test_single_chronological_career_timeline(self):
        from resume_engine import chronology_index
        p=build_plan(JD,"Business Analyst")
        parsed=Document(io.BytesIO(render_docx(p)))
        text="\\n".join(x.text for x in parsed.paragraphs)
        self.assertNotIn("Outras experiências",text)
        order=sorted(EXPERIENCE,key=chronology_index,reverse=True)
        positions=[text.find(e["role"]+" — "+e["company"]) for e in order]
        self.assertTrue(all(position>=0 for position in positions))
        self.assertEqual(positions,sorted(positions))
    def test_empty_jd_rejected(self):
        with self.assertRaises(ValueError):build_plan("  ","A")
if __name__=="__main__":unittest.main()
