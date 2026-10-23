"""Cross-source regression: the same eligibility rules apply regardless of ATS."""
import unittest
from search_filters import classify, search_terms, analyze_filters
from collectors import preserve_eligibility_fields

TERMS=search_terms("Product Manager")
BASE={"title":"Product Manager","published":""}

def check(source,location,description="",**fields):
    return classify({**BASE,"source":source,"location":location,
                     "description":description,**fields},TERMS,"BR","remote",0)[0]

class CrossSourceEligibility(unittest.TestCase):
    def test_collector_keeps_explicit_metadata_without_guessing(self):
        job={'title':'Product Manager','location':'São Paulo'}
        preserve_eligibility_fields(job,{'workplaceType':'Remote','countryCode':'BR','isRemote':True})
        self.assertEqual(job['workplaceType'],'Remote')
        self.assertEqual(job['countryCode'],'BR')
        self.assertTrue(job['remote'])
        self.assertNotIn('region',job)

    def test_unconfirmed_valid_jd_gets_free_local_ranking_and_invalid_jd_no_score(self):
        real=('We are looking for a Product Manager to own product roadmaps and lead '
              'stakeholder management, backlog prioritization, customer discovery and '
              'cross-functional delivery. The role coordinates agile product initiatives '
              'and uses customer feedback to prioritize product releases. ')*5
        candidates=[{**BASE,'source':'Greenhouse','location':'São Paulo','description':real},
                    {**BASE,'source':'Lever','location':'São Paulo','description':'Job unavailable'}]
        confirmed,review,_=analyze_filters(candidates,'Product Manager','BR','remote',0)
        self.assertFalse(confirmed)
        self.assertEqual(len(review),2)
        good=next(j for j in review if j['jd_available'])
        bad=next(j for j in review if not j['jd_available'])
        self.assertEqual(good['ranking']['method'],'local')
        self.assertEqual(good['ranking']['cost_usd'],0)
        self.assertIsNone(bad['ranking']['score'])
        self.assertEqual(good['description'],'')
    def test_all_sources_confirm_brazil_remote(self):
        for source in ("Ashby","Greenhouse","Lever","inHire","Gupy","Quickin"):
            with self.subTest(source=source):
                self.assertEqual(check(source,"Brazil - Remote"),"confirmed")

    def test_all_sources_reject_foreign_only(self):
        for source in ("Ashby","Greenhouse","Lever","inHire","Gupy","Quickin"):
            with self.subTest(source=source):
                self.assertEqual(check(source,"United States - Remote"),"excluded")

    def test_regional_heading_does_not_override_foreign_restriction(self):
        for source in ("Ashby","Greenhouse","Lever","inHire","Gupy","Quickin"):
            with self.subTest(source=source):
                self.assertEqual(check(source,"LATAM - Remote",
                    "Must be based in the United States."),"excluded")

    def test_remote_heading_does_not_override_onsite_only(self):
        self.assertNotEqual(check("Greenhouse","Brazil - Remote",
            "This is an onsite only role; must work from office."),"confirmed")

    def test_unknown_stays_pending(self):
        self.assertEqual(check("Ashby","Brazil"),"review")

    def test_ashby_structured_remote(self):
        self.assertEqual(check("Ashby","Brazil",remote=True),"confirmed")

    def test_explicit_brazil_exclusion_in_description(self):
        self.assertEqual(check("Lever","Worldwide - Remote",
            "Candidates from anywhere except Brazil."),"excluded")

if __name__=="__main__":unittest.main()
