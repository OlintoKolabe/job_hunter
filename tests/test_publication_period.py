import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from search_filters import classify

class PublicationPeriodTests(unittest.TestCase):
    def check(self, published, days):
        job={"title":"Product Manager","company":"Example","url":"https://example.com/jobs/1",
             "location":"Brasil remoto","published":published}
        with patch("jd_signals.signals",return_value={"spanish_required":False,"family_evidence":[]}), \
             patch("search_filters.role_match",return_value=True), \
             patch("search_filters.detect_work_mode",return_value="remote"), \
             patch("search_filters.geo_verdict",return_value="eligible"):
            return classify(job,["product manager"],"BR","remote",days)

    def test_missing_date_is_visible_for_verification_not_confirmed(self):
        for days in (1,3,7,15,30,60,90):
            self.assertEqual(self.check("",days),("review","data"))
        self.assertEqual(self.check("",0),("confirmed",""))

    def test_old_date_excluded_and_recent_accepted(self):
        old=(datetime.now(timezone.utc)-timedelta(days=40)).isoformat()
        recent=(datetime.now(timezone.utc)-timedelta(hours=6)).isoformat()
        self.assertEqual(self.check(old,30),("excluded","data"))
        self.assertEqual(self.check(recent,1),("confirmed",""))

    def test_future_date_is_not_published(self):
        future=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
        self.assertEqual(self.check(future,30),("excluded","data"))

    def test_invalid_date_excluded_only_when_period_selected(self):
        self.assertEqual(self.check("unknown",7),("review","data"))
        self.assertEqual(self.check("unknown",0),("confirmed",""))

if __name__=="__main__":unittest.main()
