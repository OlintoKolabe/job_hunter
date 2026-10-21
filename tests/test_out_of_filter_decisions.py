"""Out-of-filter results must respect final disposition history."""
import unittest
import app
from search_filters import classify,search_terms,DEFAULT_ROLES
class OutOfFilterDecisionTests(unittest.TestCase):
    def test_excluded_vacancy_does_not_become_confirmed(self):
        job={"title":"Registered Nurse","company":"Example","url":"https://example.com/jobs/99","location":"Brazil - Remote"}
        state,reason=classify(job,search_terms(DEFAULT_ROLES),"BR","remote",0)
        self.assertEqual((state,reason),("excluded","cargo"))
    def test_history_suppresses_excluded_vacancy(self):
        job={"title":"Registered Nurse","company":"Example","url":"https://example.com/jobs/99"}
        _,visible,_=app.exclude_history_matches([], [job], {app.terminal_url_key(job["url"])},set())
        self.assertEqual(visible,[])
    def test_history_preserves_undecided_excluded_vacancy(self):
        job={"title":"Registered Nurse","company":"Example","url":"https://example.com/jobs/99"}
        _,visible,_=app.exclude_history_matches([], [job],set(),set())
        self.assertEqual(visible,[job])
if __name__=="__main__":unittest.main()
