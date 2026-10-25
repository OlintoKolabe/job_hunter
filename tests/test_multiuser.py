import unittest
from unittest.mock import patch
import multiuser as mu


class AcademicSidebarTests(unittest.TestCase):
 def test_academic_sidebar_is_not_promoted_to_credentials(self):
    profile = {"name": "Marcus Pablo Rezende Teixeira Manso Pereira",
               "skills": ["Python", "SQL"],
               "education": ["Pontifícia Universidade Católica de Goiás", "Engenharia de Computação",
                             "Marcus Pablo Rezende Teixeira Manso Pereira", "Python", "SQL",
                             "Data Scientist & Data Engineer", "Senior Associate @PwC"],
               "certifications": ["Power BI", "Asimov Academy"]}
    token = mu.current_profile.set(profile)
    try:
        credentials = mu.profile_education()
        assert "Engenharia de Computação" in credentials
        assert "Asimov Academy" in credentials
        assert "Python" not in credentials
        assert "Data Scientist & Data Engineer" not in credentials
        assert "Senior Associate @PwC" not in credentials
        assert profile["education"][2] not in credentials
    finally:
        mu.current_profile.reset(token)
from docx import Document
from io import BytesIO
import resume_engine
import ai_resume_matcher


class Cursor:
    def __init__(self):
        self.sql=[]
    def execute(self,sql,*params):
        self.sql.append(sql)


class TenantTests(unittest.TestCase):
    def test_independent_schemas_and_shared_catalog(self):
        a,b=Cursor(),Cursor()
        mu.provision_schema(a,11)
        mu.provision_schema(b,22)
        self.assertTrue(all("jh_user_11" in q for q in a.sql))
        self.assertTrue(all("jh_user_22" in q for q in b.sql))
        self.assertNotIn("jh_jd_cache"," ".join(a.sql))
        self.assertNotIn("jh_catalog_source"," ".join(a.sql))
        self.assertEqual(sum("CREATE TABLE" in q for q in a.sql),5)
        self.assertTrue(any("jh_history" in q for q in a.sql))
        self.assertTrue(any("jh_score_cache" in q for q in a.sql))

    def test_no_cross_user_evidence(self):
        profile_a={"experience":[{"role":"Product Manager","company":"Alpha",
            "dates":"2020-2024","facts":["Liderou o backlog do produto Alpha."],"verified":True}]}
        profile_b={"experience":[{"role":"Data Scientist","company":"Beta",
            "dates":"2022-2025","facts":["Treinou modelos de classificação em Python."],"verified":True}]}
        with patch.object(mu,"enabled",True):
            token=mu.current_profile.set(profile_a)
            self.assertEqual(mu.factual_experience()[0]["company"],"Alpha")
            mu.current_profile.set(profile_b)
            self.assertEqual(mu.factual_experience()[0]["company"],"Beta")
            self.assertNotIn("Alpha",str(mu.factual_experience()))
            mu.current_profile.reset(token)

    def test_unverified_facts_not_exposed(self):
        with patch.object(mu,"enabled",True):
            token=mu.current_profile.set({"experience":[
                {"role":"Engineer","company":"Example","facts":["Unverified Java"],"verified":False}]})
            self.assertEqual(mu.factual_experience(),[])
            mu.current_profile.reset(token)

    def test_short_geographic_fragments_are_not_professional_evidence(self):
        profile={"experience":[{"role":"Analista de automação","company":"Exemplo",
            "dates":"2024-2026","verified":True,
            "facts":["Goiás","Brasil","Goiânia","Automation",
                     "Led automation projects to improve business processes."]}]}
        with patch.object(mu,"enabled",True):
            token=mu.current_profile.set(profile)
            try:
                self.assertEqual(mu.factual_experience()[0]["facts"],
                    ["Led automation projects to improve business processes."])
            finally:
                mu.current_profile.reset(token)

    def test_connection_schema_is_derived_from_numeric_uid(self):
        with patch.object(mu,"enabled",True),patch.object(mu.psycopg,"connect") as connect:
            token=mu.current_uid.set(42)
            mu.connect("postgresql://placeholder",connect_timeout=4)
            self.assertNotIn("options", connect.call_args.kwargs)
            connect.return_value.execute.assert_called_once_with(
                'SET search_path TO "jh_user_42", public')
            mu.current_uid.reset(token)

    def test_private_connection_fails_closed_without_account(self):
        with patch.object(mu,"enabled",True),patch.object(mu.psycopg,"connect") as connect:
            token=mu.current_uid.set(None)
            try:
                with self.assertRaises(PermissionError):
                    mu.connect("postgresql://placeholder")
                connect.assert_not_called()
            finally:
                mu.current_uid.reset(token)

    def test_independent_evidence_proxy(self):
        legacy=[{"role":"Legacy"}]
        dynamic=mu.ProfileSequence(legacy,mu.factual_experience)
        with patch.object(mu,"enabled",True):
            token=mu.current_profile.set({"experience":[{"role":"Intern","company":"Tech",
                "facts":["Criou testes unitários"],"verified":True}]})
            self.assertEqual(dynamic[0]["role"],"Intern")
            self.assertNotIn("Legacy",repr(list(dynamic)))
            mu.current_profile.reset(token)

    def test_three_profiles_docx_and_evidence_are_isolated(self):
        profiles=[
            ("Olinto Teste","Product Manager","Produto Exemplo","Geriu backlog e priorizou entregas do produto."),
            ("Estagiário Teste","Estagiário de Tecnologia","Empresa de Tecnologia","Criou testes unitários em Python sob supervisão."),
            ("Cientista Teste","Cientista de Dados","Laboratório de Dados","Treinou modelos de classificação usando Python e avaliou precisão.")
        ]
        with patch.object(mu,"enabled",True):
            for name,role,company,fact in profiles:
                profile={"name":name,"email":"test@example.test","phone":"","location":"Brasil",
                    "linkedin":"","summary":"Experiência em "+role.lower()+".",
                    "education":["Formação declarada de teste"],"certifications":[],
                    "languages":["Português"],"experience":[{"role":role,"company":company,
                    "dates":"jan 2024 – set 2026","facts":[fact],"verified":True}]}
                token=mu.current_profile.set(profile)
                try:
                    catalog=ai_resume_matcher.evidence_catalog()
                    self.assertEqual([x["fact"] for x in catalog],[fact])
                    plan=resume_engine.build_plan("Requisitos: "+role+"; experiência profissional comprovada e responsabilidades em equipe.",role)
                    data=resume_engine.render_docx(plan)
                    resume_engine.audit(plan,data)
                    doc=Document(BytesIO(data))
                    rendered="\n".join(p.text for p in doc.paragraphs)
                    self.assertIn(name,rendered)
                    self.assertIn(fact,rendered)
                    for other,_,_,other_fact in profiles:
                        if other!=name:
                            self.assertNotIn(other,rendered)
                            self.assertNotIn(other_fact,rendered)
                finally:
                    mu.current_profile.reset(token)

    def test_non_owner_cv_survives_fragmented_import_and_repeated_education_term(self):
        substantive="Designed and automated business processes with reliable data pipelines."
        profile={"name":"Marcos Exemplo","email":"marcos@example.test","phone":"62999999999",
                 "location":"Goiânia, Goiás","linkedin":"","summary":"Experiência em automação.",
                 "education":["Formação em Goiás", "Designed and automated business processes with reliable data pipelines."],
                 "certifications":["Automation Brasil"],"languages":[],
                 "experience":[{"role":"Analista de automação","company":"Empresa B",
                                "dates":"2023-2026","verified":True,
                                "facts":["Goiás","Brasil","Goiânia","Automation",substantive]}]}
        with patch.object(mu,"enabled",True):
            token=mu.current_profile.set(profile)
            try:
                self.assertEqual([row["fact"] for row in ai_resume_matcher.evidence_catalog()],
                                 [substantive])
                with patch("ai_resume_matcher._ask",return_value={
                    "selected_fact_ids":["0:0"],"summary":"Experiência em automação."}):
                    plan=ai_resume_matcher.tailored_plan(
                        "Automação de processos de negócios e gestão de dados com experiências demonstradas.",
                        "Analista de automação")
                document=resume_engine.render_docx(plan)
                resume_engine.audit(plan,document)
                rendered="\n".join(p.text for p in Document(BytesIO(document)).paragraphs)
                self.assertIn(substantive,rendered)
                self.assertIn("Marcos Exemplo",rendered)
                self.assertNotIn("Olinto Manso Pereira",rendered)
                self.assertNotIn("Digital Design",rendered)
            finally:
                mu.current_profile.reset(token)

    def test_hallucinated_fact_still_fails_audit(self):
        profile={"name":"Usuário Exemplo","email":"exemplo@example.test","phone":"62999999999",
                 "location":"","linkedin":"","summary":"Profissional de tecnologia.",
                 "education":[],"certifications":[],"experience":[{
                     "role":"Developer","company":"Exemplo","dates":"2023-2026",
                     "facts":["Maintained and improved test automation for existing workflows."],
                     "verified":True}]}
        with patch.object(mu,"enabled",True):
            token=mu.current_profile.set(profile)
            try:
                plan=resume_engine.build_plan("Software engineering testing requirements", "Developer")
                plan["experience"][0]["facts"]=["Invented leadership of an entire department."]
                with self.assertRaisesRegex(AssertionError,"unproven_fact"):
                    resume_engine.audit(plan,resume_engine.render_docx(plan))
            finally:
                mu.current_profile.reset(token)


if __name__=="__main__":
    unittest.main()
