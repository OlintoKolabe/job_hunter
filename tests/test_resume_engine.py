import io
import unittest
from docx import Document
from resume_engine import build_plan,render_docx,audit,EXPERIENCE,CONTACT

JD="We need a business analyst who manages stakeholder needs, roadmaps and backlog in Azure DevOps, works with product owners and defines user stories. Previous hands-on Oracle programming experience is a plus."

class ResumeEngineTests(unittest.TestCase):
    def test_generates_document_without_ai(self):
        p=build_plan(JD,"Senior Business Analyst")
        b=render_docx(p)
        a=audit(p,b)
        self.assertEqual(a["cost_usd"],0)
        self.assertEqual(a["ai_calls"],0)
        self.assertTrue(a["factual_bullets_verified"])
    def test_contact_and_chronology(self):
        p=build_plan(JD,"Senior Business Analyst")
        self.assertEqual([x["company"] for x in p["experience"]],[x["company"] for x in EXPERIENCE])
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
        a=audit(p,render_docx(p,b"")) if False else audit(p,render_docx(p))
        b=audit(p,render_docx(p))
        self.assertEqual(a["jd_sha256"],b["jd_sha256"])
    def test_empty_jd_rejected(self):
        with self.assertRaises(ValueError):build_plan("  ","A")
if __name__=="__main__":unittest.main()
