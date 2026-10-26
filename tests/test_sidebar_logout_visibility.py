"""Regression: account controls remain accessible for long search results."""
from pathlib import Path
import unittest


class LogoutVisibilityTests(unittest.TestCase):
    def test_sticky_sidebar_and_mobile_logout(self):
        root = Path(__file__).resolve().parents[1] / "src"
        css = (root / "style.css").read_text()
        jsx = (root / "main.jsx").read_text()
        self.assertIn("position:sticky;top:0;height:100vh", css)
        self.assertIn(".shell>aside .sidebar-bottom{display:flex", css)
        self.assertIn('className="logout" aria-label="Sair"', jsx)
        self.assertIn("onClick={logout}", jsx)


if __name__ == "__main__":
    unittest.main()
