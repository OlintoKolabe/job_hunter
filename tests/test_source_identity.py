"""Source boundary regression checks without external network access."""
import unittest
from unittest.mock import patch
from source_extensions import extra

class SourceIdentityTests(unittest.TestCase):
    def test_linkedin_query_uses_jobspy_and_selected_work_mode(self):
        from source_extensions import extra
        for mode in ("remote","onsite","hybrid","all"):
            with self.subTest(mode=mode), patch("linkedin_jobspy.search",return_value=[]) as fetch:
                extra("linkedin_guest","product manager",mode=mode)
                fetch.assert_called_once_with("product manager",mode=mode)

    def test_linkedin_provider_filter_alone_does_not_confirm_mode(self):
        from source_extensions import linkedin_cards
        from search_filters import classify
        from unittest.mock import MagicMock
        markup=b'''<li class="base-card"><a href="/jobs/view/123"><h3>Product Manager</h3></a>
          <h4>Acme</h4><span class="job-search-card__location">Brazil</span>
          <time datetime="2026-11-09"></time></li>'''
        for provider,expected in (("1","onsite"),("2","remote"),("3","hybrid")):
            response=MagicMock();response.read.return_value=markup
            response.url="https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            response.__enter__.return_value=response
            with patch("source_extensions.urllib.request.urlopen",return_value=response):
                job=linkedin_cards("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?f_WT="+provider)[0]
            self.assertEqual(job["providerSearchMode"],expected)
            self.assertNotIn("workplaceType",job)
            self.assertNotIn("remote",job)
            for selected in ("remote","onsite","hybrid"):
                self.assertEqual(classify(job,["product manager"],"BR",selected,0)[0],"review")

    def test_linkedin_job_description_overrides_provider_mode(self):
        from search_filters import classify
        base={"source":"linkedin_guest","company":"Acme","title":"Product Manager",
              "location":"Brazil","published":"2026-11-09","providerSearchMode":"remote"}
        for description,actual in (("Our hybrid work model requires office days.","hybrid"),
                                   ("This is an onsite position in our office.","onsite"),
                                   ("This is a fully remote position in Brazil.","remote")):
            job={**base,"description":description}
            with self.subTest(description=description):
                self.assertEqual(classify(job,["product manager"],"BR",actual,0)[0],"confirmed")
                if actual!="remote":
                    self.assertEqual(classify(job,["product manager"],"BR","remote",0)[0],"excluded")

    def test_catalog_scan_forwards_work_mode_only_to_linkedin(self):
        from catalog_engine import scan
        with patch("catalog_engine.run_task",return_value=({"source":"linkedin_guest","state":"validado"},[])) as task:
            scan([("linkedin_guest","product manager")],workers=1,allow_js=False,mode="hybrid")
            self.assertEqual(task.call_args.args,("linkedin_guest","product manager",False,"hybrid"))


    def test_linkedin_remote_search_preserves_provider_mode_evidence(self):
        from source_extensions import linkedin_cards
        markup=b'''<li class="base-card"><a href="/jobs/view/123"><h3>Product Manager</h3></a>
          <h4>Acme</h4><span class="job-search-card__location">Brazil</span>
          <time datetime="2026-11-09"></time></li>'''
        from unittest.mock import MagicMock
        response=MagicMock();response.read.return_value=markup
        response.url="https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        response.__enter__.return_value=response
        with patch("source_extensions.urllib.request.urlopen",return_value=response):
            jobs=linkedin_cards("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?f_WT=2")
        self.assertEqual(len(jobs),1)
        self.assertNotIn("remote",jobs[0])
        self.assertEqual(jobs[0]["providerSearchMode"],"remote")

    def test_linkedin_hybrid_card_is_not_forced_remote(self):
        from source_extensions import linkedin_cards
        from unittest.mock import MagicMock
        response=MagicMock();response.read.return_value=b'''<li class="base-card">
        <a href="/jobs/view/123"><h3>Product Owner</h3></a>
        <span class="job-search-card__location">Sao Paulo (Hybrid)</span></li>'''
        response.url="https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        response.__enter__.return_value=response
        with patch("source_extensions.urllib.request.urlopen",return_value=response):
            jobs=linkedin_cards("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?f_WT=2")
        self.assertNotIn("remote",jobs[0])

    def test_linkedin_public_detail_recovers_description(self):
        from job_detail_evidence import recover
        from unittest.mock import MagicMock
        response=MagicMock()
        response.read.return_value=b'''<div class="show-more-less-html__markup"><p>
        Product discovery, roadmap, backlog prioritization and stakeholder management.
        </p></div>'''
        response.headers={"Content-Type":"text/html; charset=utf-8"}
        response.__enter__.return_value=response
        job={"source":"linkedin_guest","title":"Product Manager",
             "url":"https://www.linkedin.com/jobs/view/123"}
        with patch("job_detail_evidence.urllib.request.urlopen",return_value=response) as fetch:
            result=recover(job)
        self.assertIn("roadmap",result["description"])
        self.assertIn("/jobPosting/123",fetch.call_args.args[0].full_url)

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
