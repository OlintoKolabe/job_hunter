import unittest
from unittest.mock import patch

import multiuser as mu
from app import require_profile_roles
from fastapi import HTTPException
from search_filters import classify, search_terms


class MultiuserRoleSearchTests(unittest.TestCase):
    def test_authenticated_profile_accepts_only_own_selected_roles(self):
        with patch.object(mu, "enabled", True):
            token = mu.current_profile.set({
                "roles": ["Data Scientist", "Machine Learning Engineer", "Estágio em Engenharia de Software"]
            })
            try:
                require_profile_roles("Data Scientist, Estágio em Engenharia de Software")
                for wrong in ("Product Manager", "Data Scientist, Product Manager", ""):
                    with self.assertRaises(HTTPException) as denied:
                        require_profile_roles(wrong)
                    self.assertEqual(denied.exception.status_code, 400)
            finally:
                mu.current_profile.reset(token)

    def test_switching_tenants_changes_authorized_roles(self):
        with patch.object(mu, "enabled", True):
            token = mu.current_profile.set({"roles": ["Product Manager"]})
            try:
                require_profile_roles("Product Manager")
                mu.current_profile.set({"roles": ["Data Engineer"]})
                require_profile_roles("Data Engineer")
                with self.assertRaises(HTTPException):
                    require_profile_roles("Product Manager")
            finally:
                mu.current_profile.reset(token)

    def test_explicit_technical_and_intern_titles_are_not_excluded_as_cargo(self):
        for title in (
            "Data Scientist",
            "Machine Learning Engineer",
            "Estágio em Engenharia de Software",
            "Junior Software Engineer",
        ):
            with self.subTest(title=title):
                job = {"title": title, "location": "Brasil", "description": "", "remote": True}
                verdict, reason = classify(job, search_terms(title), "BR", "remote", 0)
                self.assertNotEqual(reason, "cargo")

    def test_technical_role_is_still_excluded_for_product_only_profile(self):
        job = {"title": "Software Engineer", "location": "Brasil", "description": ""}
        self.assertEqual(classify(job, search_terms("Product Manager"), "BR", "remote", 0),
                         ("excluded", "cargo"))


if __name__ == "__main__":
    unittest.main()
