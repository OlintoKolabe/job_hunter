import unittest
from unittest.mock import patch

from linkedin_pdf import parse_profile_text, parse_linkedin_pdf, MAX_PDF_BYTES


ENGLISH = """Jane Example
Data Scientist at Analytics Lab
Contact
jane@example.com
linkedin.com/in/jane-example
Summary
Data scientist with experience preparing commercial data.
Experience
Analytics Lab
Data Scientist
January 2022 - Present (4 years)
Developed reproducible data cleaning pipelines in Python.
Created model evaluation reports for the analytics team.
Another Company
Data Analyst
May 2020 - December 2021 (1 year 8 months)
Built automated quality checks on incoming data.
Education
University of Example
Bachelor of Computer Science
Skills
Python
Pandas
Data Science
Languages
English
Portuguese
Certifications
Data Analytics Certificate
"""

PORTUGUESE = """Ana Oliveira
Gerente de Produto
Contato
ana@example.com
Resumo
Profissional de produtos digitais.
Experiência
Startup Verde
Gerente de Produto
março de 2020 – o momento
Organizou o backlog e alinhou entregas com equipes ágeis.
Formação acadêmica
Universidade Exemplo
MBA em Marketing
Competências
Roadmap
Scrum
Idiomas
Português
Inglês
"""


class LinkedInPdfTests(unittest.TestCase):
    def test_wrapped_linkedin_bullets_remain_complete(self):
        source = """Jane Example
Contact
jane@example.com
Summary
Product manager working with AI prototypes.
Experience
Kolabe
Product Manager
May 2018 - January 2023
São Paulo, Brasil
• Created product discovery journeys, user interviews and
prototypes for validation with stakeholders.
• Managed the product roadmap, prioritizing value
and aligning engineering with UX decisions.
Education
University of Example
Bachelor degree
"""
        data = parse_profile_text(source)["profile"]["experience"]
        self.assertEqual(len(data), 1)
        self.assertEqual(len(data[0]["facts"]), 2)
        self.assertIn("user interviews and prototypes", data[0]["facts"][0])
        self.assertIn("prioritizing value and aligning", data[0]["facts"][1])
        self.assertNotIn("São Paulo, Brasil", data[0]["facts"])

    def test_linkedin_sidebar_does_not_pollute_marcus_academic_fields(self):
        source = """Marcus Pablo Rezende Teixeira Manso Pereira
Contact
marcus@example.com
Summary
I turn raw data into strategic decisions — and manual processes
into intelligent automation. &amp; analytics.
Experience
Bluetech Films
Automation Analyst
June 2025 - August 2025
Built Python and SQL pipelines for business analytics.
Education
Pontifícia Universidade Católica de Goiás
Engenharia de Computação
(2022 - 2026)
Asimov Academy
Certificado de conclusão python
Marcus Pablo Rezende Teixeira Manso Pereira
Data Scientist & Data Engineer
Python
SQL
Databricks
Senior Associate @PwC
São Paulo
Brasil
"""
        result = parse_profile_text(source)
        profile = result["profile"]
        self.assertEqual(len(profile["experience"]), 1)
        self.assertEqual(profile["summary"],
                         "I turn raw data into strategic decisions — and manual processes into intelligent automation. & analytics.")
        self.assertIn("Engenharia de Computação", profile["education"])
        for contamination in ("Python", "SQL", "Databricks", "Data Scientist & Data Engineer",
                              "Marcus Pablo Rezende Teixeira Manso Pereira", "Senior Associate @PwC"):
            self.assertNotIn(contamination, profile["education"])
        self.assertTrue(result["warnings"])

    def test_abbreviated_profile_name_marks_end_of_certification_area(self):
        from linkedin_pdf import clean_credentials
        fields, rejected=clean_credentials(
            ["Build Solutions with Power Apps", "Marcus Pablo R. T. Manso",
             "Data Scientist & Data Engineer", "Power", "BI", "São Paulo", "Brasil"],
            "Marcus Pablo Rezende Teixeira Manso Pereira", [])
        self.assertEqual(fields,["Build Solutions with Power Apps"])
        self.assertIn("São Paulo",rejected)

    def test_full_english_profile_is_structured_without_invention(self):
        result = parse_profile_text(ENGLISH)
        p = result["profile"]
        self.assertEqual(p["name"], "Jane Example")
        self.assertEqual(p["linkedin"], "linkedin.com/in/jane-example")
        self.assertEqual(len(p["experience"]), 2)
        self.assertEqual(p["experience"][0]["company"], "Analytics Lab")
        self.assertEqual(p["experience"][0]["role"], "Data Scientist")
        self.assertIn("reproducible data cleaning", " ".join(p["experience"][0]["facts"]))
        self.assertEqual(p["skills"], ["Python", "Pandas", "Data Science"])
        self.assertFalse(any(x["verified"] for x in p["experience"]))
        self.assertEqual(result["email_detected"], "jane@example.com")

    def test_portuguese_linkedin_sections(self):
        p = parse_profile_text(PORTUGUESE)["profile"]
        self.assertEqual(p["name"], "Ana Oliveira")
        self.assertEqual(p["experience"][0]["company"], "Startup Verde")
        self.assertEqual(p["experience"][0]["role"], "Gerente de Produto")
        self.assertEqual(p["languages"], ["Português", "Inglês"])
        self.assertIn("MBA em Marketing", p["education"])

    def test_password_protected_and_non_pdf_rejected(self):
        with self.assertRaisesRegex(ValueError, "PDF válido"):
            parse_linkedin_pdf(b"this is not a PDF")
        with self.assertRaisesRegex(ValueError, "8 MB"):
            parse_linkedin_pdf(b"%PDF-" + b"x" * MAX_PDF_BYTES)

    def test_short_scanned_pdf_does_not_create_qualifications(self):
        with self.assertRaisesRegex(ValueError, "sem texto suficiente"):
            parse_profile_text("Jane Example")

    def test_pdf_reader_not_called_until_bytes_validated(self):
        with patch("linkedin_pdf.PdfReader") as reader:
            with self.assertRaises(ValueError):
                parse_linkedin_pdf(b"not pdf")
            reader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
