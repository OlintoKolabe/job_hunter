"""Source boundary regression checks without external network access."""
import unittest
from unittest.mock import patch
from source_extensions import extra

class SourceIdentityTests(unittest.TestCase):
    def test_linkedin_card_fields_feed_country_filter(self):
        from source_extensions import LinkedInCards
        from search_filters import classify,search_terms,DEFAULT_ROLES
        html='''<ul><li class="base-card"><div><img src="/a.png">
          <a href="https://www.linkedin.com/jobs/view/123">
          <h3 class="base-search-card__title">Product Manager</h3></a>
          <h4 class="base-search-card__subtitle">Acme</h4>
          <span class="job-search-card__location">São Paulo, Brasil (Remoto)</span>
          <time datetime="2026-10-20">20/10</time></div></li></ul>'''
        p=LinkedInCards();p.feed(html)
        self.assertEqual(len(p.cards),1)
        card=p.cards[0]
        self.assertEqual(card["location"].strip(),"São Paulo, Brasil (Remoto)")
        self.assertEqual(card["company"].strip(),"Acme")
        job={"title":card["title"],"location":card["location"],"published":card["published"]}
        verdict,_=classify(job,search_terms(DEFAULT_ROLES),"BR","remote",0)
        self.assertEqual(verdict,"confirmed")

    def test_linkedin_card_without_location_not_assumed_brazil(self):
        from source_extensions import LinkedInCards
        p=LinkedInCards()
        p.feed('<li class="base-card"><a href="/jobs/view/789"><h3>Product Owner</h3></a></li>')
        self.assertEqual(p.cards[0]["location"],"")


    def test_linkedin_nested_card_matches_current_guest_markup(self):
        from source_extensions import LinkedInCards
        html='''<ul><li><div class="base-card relative w-full">
          <a href="/jobs/view/123"><h3 class="base-search-card__title">Product Manager</h3></a>
          <h4 class="base-search-card__subtitle">Example</h4>
          <span class="job-search-card__location">Brazil</span>
          <time datetime="2026-10-27"></time>
        </div></li></ul>'''
        p=LinkedInCards();p.feed(html)
        self.assertEqual(len(p.cards),1)
        self.assertEqual(p.cards[0]["title"].strip(),"Product Manager")
        self.assertEqual(p.cards[0]["company"].strip(),"Example")
        self.assertEqual(p.cards[0]["location"].strip(),"Brazil")

    def test_bamboohr_keeps_raw_jobs_until_user_filter(self):
        import json
        from catalog_engine import extra_pull
        payload={"result":[{"id":"7","jobOpeningName":"People Operations Coordinator","location":"Remote"},{"id":"8","jobOpeningName":"Senior Data Engineer","location":"Brazil"}]}
        with patch("catalog_engine.read",return_value=(json.dumps(payload).encode(),200)):
            jobs,state=extra_pull("bamboohr","example")
        self.assertEqual(state,"ok")
        self.assertEqual(len(jobs),2)
        self.assertEqual([j["title"] for j in jobs],["People Operations Coordinator","Senior Data Engineer"])

if __name__=="__main__":unittest.main()
