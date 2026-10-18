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
    def test_reopened_docx_technical_grading(self):
        from resume_engine import evaluate_rendered_resume
        plan=build_plan(JD,"Senior Business Analyst")
        data=render_docx(plan)
        result=evaluate_rendered_resume(plan,data,JD)
        self.assertTrue(result["factual_ok"])
        self.assertIn("factual_traceability",result["dimensions"])
        self.assertEqual(result["jd_sha256"],plan["jd_sha256"])
        self.assertGreater(result["technical_score"],0)

    def test_complete_linkedin_history_adds_marketing_evidence(self):
        from resume_engine import EXPERIENCE
        self.assertTrue(any("R$ 7 milhões" in fact for fact in EXPERIENCE[12]["facts"]))
        self.assertTrue(any("triplicada" in fact for fact in EXPERIENCE[9]["facts"]))
        self.assertTrue(any("Hotjar" in fact for fact in EXPERIENCE[1]["facts"]))

    def test_program_manager_gets_governance_evidence(self):
        from resume_engine import EXPERIENCE
        jd="Program Manager governance portfolio cross-functional teams risk project delivery budget"
        p=build_plan(jd,"Program Manager")
        detail={e["source_index"]:e["facts"] for e in p["experience"]}
        self.assertIn(2,detail)
        self.assertIn(8,detail)
        self.assertTrue(any("Governança corporativa" in f for f in detail[8]))
        self.assertTrue(audit(p,render_docx(p))["factual_bullets_verified"])
    def test_performance_media_docx_surfaces_marketing_career(self):
        jd=("Lead digital performance campaigns, paid media, media budgets, "
            "Google Analytics, CRM, growth, audience targeting and A/B testing.")
        plan=build_plan(jd,"Coordenador de Mídia De Performance Digital")
        detailed={e["source_index"] for e in plan["experience"]}
        self.assertIn(9,detailed)
        self.assertIn("liderança de marketing",plan["summary"])
        data=render_docx(plan)
        self.assertTrue(audit(plan,data)["factual_bullets_verified"])
        paragraphs=[p.text for p in Document(io.BytesIO(data)).paragraphs]
        self.assertTrue(any("Gestão de marketing, campanhas omnichannel, CRM" in p for p in paragraphs))

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

    def test_internal_docx_homologation_matrix(self):
        """Run the actual engine and reopen DOCX for each distinct JD category."""
        from resume_engine import categories, TOPICS, FACT_TOPICS
        from docx import Document
        matrix = [
            ("Business Analyst", "Business Analyst: map stakeholder needs, document user stories, prioritize backlog, support Scrum and Azure DevOps.", "analysis"),
            ("Product Owner", "Product Owner: own roadmap, discovery, backlog, user research and alignment with stakeholders.", "product"),
            ("Growth Manager", "Growth Manager: CRM, retention, acquisition, marketing campaigns, churn, leads, Google Ads.", "growth"),
            ("Project Manager", "Project Manager: portfolio governance, delivery, resources, budget, and processes.", "project"),
            ("Marketing Manager", "Marketing Manager: coordinate marketing strategy, branding, paid campaigns, CRM and sales.", "growth"),
            ("Data Product Manager", "Data Product Manager: roadmap, KPIs, indicators, analytics and product discovery.", "data"),
        ]
        seen=set()
        for title,jd,required in matrix:
            with self.subTest(title=title):
                plan=build_plan(jd,title)
                content=render_docx(plan)
                report=audit(plan,content)
                doc=Document(io.BytesIO(content))
                body=" ".join(p.text for p in doc.paragraphs)
                facts=[f for e in plan["experience"] for f in e["facts"]]
                covered=set().union(*(categories(f,FACT_TOPICS) for f in facts))
                self.assertTrue(report["factual_bullets_verified"])
                self.assertIn(required,covered, f"No supported evidence of {required}: {title}")
                self.assertIn("Resumo profissional",body)
                self.assertIn("Experiência profissional",body)
                self.assertGreaterEqual(len(facts),3)
                self.assertNotIn(report["jd_sha256"],seen)
                seen.add(report["jd_sha256"])

    def test_product_output_is_scored_from_reopened_docx(self):
        """Inspect the actual DOCX paragraphs, not the selection plan alone."""
        import re
        from resume_engine import TOPICS, FACT_TOPICS, categories
        cases=[
            ("Business Analyst", "Translate product strategy and roadmap priorities into acceptance journeys and test cases; gather stakeholder requirements; optimize business processes; support UAT, release outcomes and acceptance criteria.",
             {"analysis","product","project"}),
            ("Product Owner", "Prioritize roadmap, product discovery, user research, backlog and stakeholder alignment; own outcomes and sprint planning.",
             {"product","agility"}),
            ("Marketing Manager", "Lead CRM campaigns, brand strategy, customer retention, acquisition, marketing budget and commercial teams.",
             {"growth","people"}),
            ("Project Manager", "Manage project portfolio, governance, resources, budgets, delivery and multi-disciplinary teams.",
             {"project","people"}),
        ]
        for title,jd,expected in cases:
            with self.subTest(title=title):
                plan=build_plan(jd,title)
                output=render_docx(plan)
                self.assertTrue(audit(plan,output)["factual_bullets_verified"])
                doc=Document(io.BytesIO(output))
                rendered=[p.text.strip() for p in doc.paragraphs if p.text.strip()]
                content=" ".join(rendered)
                self.assertEqual(content.count("Resumo profissional"),1)
                self.assertEqual(content.count("Experiência profissional"),1)
                facts=[p.text for p in doc.paragraphs if p.style.name=="List Bullet"]
                cv_evidence=[x for x in facts if x in {f for e in EXPERIENCE for f in e["facts"]}]
                self.assertEqual(len(cv_evidence),len(set(cv_evidence)))
                self.assertGreaterEqual(len(cv_evidence),3)
                topics=set().union(*(categories(f,FACT_TOPICS) for f in cv_evidence))
                coverage=len(topics & expected)/len(expected)
                self.assertGreaterEqual(coverage,0.5,
                    f"Rendered CV coverage too low: {title}, {coverage:.0%}")
                # Explicitly disallow industry/technology claims found in the JD
                # if the underlying career evidence does not contain them.
                for unsupported in ("Oracle programming","PowerBuilder","life insurance claims","UAT"):
                    if unsupported.casefold() not in " ".join(f for e in EXPERIENCE for f in e["facts"]).casefold():
                        self.assertNotIn(unsupported.casefold(),content.casefold())

    def test_empty_jd_rejected(self):
        with self.assertRaises(ValueError):build_plan("  ","A")
if __name__=="__main__":unittest.main()
