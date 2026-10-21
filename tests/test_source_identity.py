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

if __name__=="__main__":unittest.main()
