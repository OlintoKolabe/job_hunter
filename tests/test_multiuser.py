import unittest
from unittest.mock import patch
import multiuser as mu
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

    def test_connection_schema_is_derived_from_numeric_uid(self):
        with patch.object(mu,"enabled",True),patch.object(mu.psycopg,"connect") as connect:
            token=mu.current_uid.set(42)
            mu.connect("postgresql://placeholder",connect_timeout=4)
            self.assertEqual(connect.call_args.kwargs["options"],"-csearch_path=jh_user_42,public")
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


if __name__=="__main__":
    unittest.main()
