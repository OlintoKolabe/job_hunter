import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from collectors import pull
from catalog_engine import run_task, source_tasks
from source_extensions import CONNECTORS

class Phase3ContractTests(unittest.TestCase):
    def test_catalog_has_expected_sources(self):
        sources={s for s,_ in source_tasks()}
        for source in ("greenhouse","ashby","inhire","lever","quickin","bamboohr","zoho"):
            self.assertIn(source,sources)

    def test_blocked_employer_not_in_seed(self):
        self.assertFalse(any(slug.casefold() in ("kraken","kraken.com","payward") for _,slug in source_tasks()))

    def test_lever_false_http_200_is_error(self):
        with patch("collectors.fetch_json",return_value={"ok":False}):
            with self.assertRaisesRegex(ValueError,"Slug Lever rejeitado"):
                pull("Lever","invalid")

    def test_unknown_ats_is_pending(self):
        state,jobs=run_task("not-implemented","any")
        self.assertEqual(state["state"],"pendente")
        self.assertEqual(jobs,[])

    def test_quickin_spa_empty_not_claimed_zero_jobs(self):
        with patch("catalog_engine.extra_pull",return_value=([],"ok")):
            state,_=run_task("quickin","sample")
        self.assertEqual(state["state"],"pendente")

    def test_inhire_unparsed_is_pending(self):
        with patch("collectors.fetch_json",return_value={"data":{"items":[]}}):
            state,_=run_task("inhire","dummy")
        self.assertEqual(state["state"],"pendente")

    def test_scrapling_guarded_without_enable_flag(self):
        from scrapling_fallback import js_fallback
        with patch.dict("os.environ",{"JH_SCRAPLING_JS":"0"}):
            with self.assertRaisesRegex(RuntimeError,"desativado"):
                js_fallback("quickin","test")

    def test_block4_extracts_unlabeled_qualification_bullets(self):
        from block4_score import score_job
        jd="<h3>Requirements</h3><ul><li>Product roadmap planning</li><li>Experience in Jira</li><li>Python expertise</li></ul>"
        r=score_job({"title":"Product Manager","location":"Brazil Remote","description":jd},"Product Manager")
        self.assertEqual(r["mandatory_count"],3)
        self.assertEqual(r["uninterpreted_count"],1)
        self.assertEqual(r["score"],100)
        self.assertEqual(r["confidence"],"amostra_limitada")

    def test_greenhouse_collects_full_job_descriptions(self):
        from collectors import pull
        seen=[]
        def response(url,headers=None):
            seen.append(url)
            return {"jobs":[{"title":"Product Manager","absolute_url":"https://jobs.example/a",
                            "location":{"name":"Brazil Remote"},
                            "content":"<h3>Requirements</h3><li>Product roadmap</li>"}]}
        with patch("collectors.fetch_json",side_effect=response):
            _,jobs=pull("Greenhouse","example")
        self.assertIn("content=true",seen[0])
        self.assertTrue(jobs[0]["description"])

    def test_inhire_detail_uses_tenant_and_public_api(self):
        from jd_enrichment import inhire_detail
        job={"source":"inHire","url":"https://amcom.inhire.app/vagas/abc123/product-manager"}
        self.assertEqual(inhire_detail(job),
            ("https://api.inhire.app/job-posts/public/pages/abc123",{"X-Tenant":"amcom"}))
        self.assertIsNone(inhire_detail({**job,"url":"https://evil.example/vagas/abc123"}))

    def test_inhire_hydration_fetches_and_scores(self):
        from jd_enrichment import hydrate_jobs
        from app import url_key
        from unittest.mock import Mock
        cur=Mock();cur.fetchall.return_value=[]
        row={"source":"inHire","company":"AMCOM","title":"Product Manager","location":"Brazil Remote",
             "url":"https://amcom.inhire.app/vagas/abc123/product-manager"}
        with patch("jd_enrichment.fetch_json",return_value={"description":"<h3>Requirements</h3><li>Product roadmap</li>"}) as request:
            results,coverage=hydrate_jobs(cur,[row],"Product Manager",url_key)
        self.assertEqual(coverage["fetched"],1)
        self.assertEqual(results[0]["ranking"]["score"],100)
        self.assertEqual(request.call_args.args[1],{"X-Tenant":"amcom"})

    def test_block4_greenhouse_detail_link_parses_real_job_id(self):
        from jd_enrichment import greenhouse_detail_url
        job={"company":"acme","source":"Greenhouse","url":"https://boards.greenhouse.io/acme/jobs/456789"}
        self.assertEqual(greenhouse_detail_url(job),"https://boards-api.greenhouse.io/v1/boards/acme/jobs/456789")
        self.assertIsNone(greenhouse_detail_url({**job,"source":"LinkedIn guest"}))

    def test_block4_cache_and_hydration_keep_unavailable_jobs_unscored(self):
        from jd_enrichment import hydrate_jobs
        from app import url_key
        from unittest.mock import Mock
        cur=Mock()
        cur.fetchall.return_value=[]
        jobs=[{"title":"Product Manager","company":"acme","source":"Greenhouse",
               "url":"https://boards.greenhouse.io/acme/jobs/456789","location":"Brazil Remote"}]
        with patch("jd_enrichment.fetch_json",return_value={"content":"<h3>Requirements</h3><li>Product roadmap management</li>"}):
            scored,coverage=hydrate_jobs(cur,jobs,"Product Manager",url_key,limit=10)
        self.assertEqual(coverage["fetched"],1)
        self.assertEqual(scored[0]["ranking"]["score"],100)
        self.assertEqual(scored[0]["jd_status"],"fetched")
        self.assertTrue(any("INSERT INTO jh_jd_cache" in str(x) for x in cur.execute.call_args_list))

    def test_block4_bounded_remote_hydration(self):
        from jd_enrichment import hydrate_jobs
        from app import url_key
        from unittest.mock import Mock
        cur=Mock();cur.fetchall.return_value=[]
        jobs=[{"title":"Product Manager","company":"acme","source":"Greenhouse",
            "url":"https://boards.greenhouse.io/acme/jobs/"+str(12000+i)} for i in range(15)]
        with patch("jd_enrichment.fetch_json",return_value={"content":"<h3>Requirements</h3><li>Product roadmap</li>"}) as fetch:
            scored,coverage=hydrate_jobs(cur,jobs,"Product Manager",url_key,limit=10)
        self.assertEqual(fetch.call_count,10)
        self.assertEqual(coverage["not_attempted"],5)
        self.assertEqual(sum(j["jd_status"]=="pendente" for j in scored),5)

    def test_block4_uninterpreted_does_not_mean_unqualified(self):
        from block4_score import score_job
        row={"title":"Product Manager","description":"Requirements\\nProduct roadmap\\nExpertise in obscure proprietary platform\\nExperience with unspecified internal process"}
        r=score_job(row,"Product Manager")
        self.assertEqual(r["uninterpreted_count"],2)
        self.assertEqual(r["coverage_pct"],33)
        self.assertIsNone(r["score"])
        self.assertEqual(r["confidence"],"cobertura_insuficiente")

    def test_block4_verifiable_leadership_and_budget(self):
        from block4_score import score_job
        row={"title":"Project Manager","description":"Requirements\\nTeam leadership\\nBudget management\\nProject portfolio management"}
        r=score_job(row,"Project Manager")
        self.assertEqual(r["coverage_pct"],100)
        self.assertEqual(r["score"],100)
        self.assertEqual(r["mandatory_count"],3)

    def test_block4_fit_is_about_requirements_not_preferences(self):
        from block4_score import score_job
        jd="Required: product roadmap and backlog management. Required: fluent Spanish."
        row={"title":"Product Manager","location":"Brazil - Remote","description":jd}
        result=score_job(row,"Product Manager")
        self.assertEqual(result["score"],67)
        self.assertEqual(result["mandatory_count"],3)
        self.assertEqual(result["unverified_count"],1)
        self.assertEqual(result["confidence"],"amostra_limitada")
        changed={**row,"location":"Brazil - Onsite","salary":"R$ 50000"}
        self.assertEqual(score_job(changed,"Product Manager")["score"],result["score"])
        self.assertNotEqual(score_job(changed,"Product Manager")["priority"],result["priority"])

    def test_block4_review_jobs_also_have_ranking_for_score_sort(self):
        from search_filters import analyze_filters
        rows=[
            {"title":"Product Owner","location":"Remote","workplaceType":"remote",
             "description":"Required: product roadmap. Required: backlog."},
            {"title":"Product Manager","location":"Brazil Remote",
             "description":"Required: product roadmap. Preferred: Figma."},
        ]
        confirmed,pending,_=analyze_filters(rows,"Product Manager, Product Owner","BR","remote",0,"score")
        self.assertEqual(len(confirmed),1)
        self.assertEqual(len(pending),1)
        self.assertIn("ranking",pending[0])
        self.assertIsInstance(pending[0]["ranking"]["score"],int)

    def test_block4_unknown_jd_has_no_fit(self):
        from block4_score import score_job
        score=score_job({"title":"Product Owner","location":"Brazil Remote"},"Product Owner")
        self.assertEqual(score["confidence"],"sem_base")
        self.assertIsNone(score["score"])

    def test_block4_sorted_by_fit_with_unscored_last(self):
        from search_filters import analyze_filters
        rows=[
            {"title":"Product Analyst","location":"Brazil Remote","description":"","published":"2026-10-16"},
            {"title":"Senior Product Manager","location":"Brazil Remote","description":"Required: roadmap. Required: backlog. Preferred: Figma.","published":"2026-10-12"}
        ]
        found,_,_=analyze_filters(rows,"Product Manager","BR","remote",0,"score")
        self.assertEqual(len(found),2)
        self.assertEqual(found[0]["title"],"Senior Product Manager")
        self.assertIsNone(found[1]["ranking"]["score"])

    def test_discovery_budget_covers_every_selected_family(self):
        from search_filters import discovery_queries,DEFAULT_ROLES
        queries=discovery_queries(DEFAULT_ROLES,12)
        self.assertEqual(len(queries),12)
        self.assertTrue(any("business" in q or "negocios" in q for q in queries))
        self.assertTrue(any("product" in q for q in queries))
        self.assertTrue(any("project" in q for q in queries))
        self.assertTrue(any("marketing" in q for q in queries))
        self.assertTrue(any("growth" in q for q in queries))

    def test_unrelated_technical_role_not_rescued_by_incidental_jd(self):
        from search_filters import analyze_filters
        jd="Coordinate project delivery and project milestones for engineering."
        rows=[{"title":"Manager, Software Engineering","location":"Brazil - Remote","description":jd}]
        good,review,why=analyze_filters(rows,"Project Manager","BR","remote",0)
        self.assertEqual(good,[])
        self.assertEqual(review,[])
        self.assertEqual(why.get("excluded:cargo"),1)

    def test_novel_role_can_be_discovered_via_jd_evidence(self):
        from search_filters import analyze_filters
        jd="Lead project planning and project delivery for cross-functional teams."
        rows=[{"title":"Business Transformation Lead","location":"Brazil - Remote","description":jd}]
        good,review,_=analyze_filters(rows,"Project Manager","BR","remote",0)
        self.assertEqual(len(good),1)

    def test_search_filters_require_actual_location_and_mode(self):
        from search_filters import apply_filters
        rows=[{"title":"Product Manager","location":"Brazil - Remote","published":"2026-10-17","url":"https://x/a"},
              {"title":"Product Manager","location":"São Paulo - Hybrid","published":"2026-10-17","url":"https://x/b"},
              {"title":"Product Manager","location":"","published":"2026-10-17","url":"https://x/c"}]
        matched=apply_filters(rows,"Product Manager","BR","remote",30,"newest")
        self.assertEqual([j["url"] for j in matched],["https://x/a"])

    def test_latam_and_reverse_chronology(self):
        from search_filters import apply_filters
        rows=[{"title":"Product Owner","location":"LATAM Remote","published":"2026-10-16"},
              {"title":"Product Owner","location":"Brazil Remote","published":"2026-10-15"}]
        matched=apply_filters(rows,"Product Owner","LATAM","remote",30,"oldest")
        self.assertEqual([j["published"] for j in matched],["2026-10-15","2026-10-16"])

    def test_unknown_metadata_not_silently_lost(self):
        from search_filters import analyze_filters
        confirmed,review,counts=analyze_filters([{"title":"Gerente de Produto","url":"https://example.com/job","location":"Brasil","published":""}],"Product Manager","BR","remote",30)
        self.assertEqual(len(confirmed),0)
        self.assertEqual(len(review),1)
        self.assertEqual(review[0]["needs_verification"],["modalidade","data"])

    def test_known_wrong_mode_excluded(self):
        from search_filters import analyze_filters
        confirmed,review,counts=analyze_filters([{"title":"Product Manager","location":"São Paulo presencial","published":"2026-10-17"}],"Product Manager","BR","remote",30)
        self.assertEqual(confirmed,[])
        self.assertEqual(review,[])

    def test_inhire_public_jobs_page_parsing(self):
        from collectors import pull
        payload={"tenantName":"Empresa Exemplo","jobsPage":[{"displayName":"Product Owner","jobId":"abc123","location":"Brasil","workplaceType":"Remote"}]}
        with patch("collectors.fetch_json",return_value=payload):
            summary,jobs=pull("inHire","exemplo")
        self.assertEqual(summary["received"],1)
        self.assertEqual(jobs[0]["title"],"Product Owner")
        self.assertIn("/vagas/abc123/product-owner",jobs[0]["url"])
        self.assertIn("Remote",jobs[0]["location"])

    def test_gupy_public_api_yields_remote_brazil_listing(self):
        from source_extensions import extra
        payload={"data":[{"name":"Gerente de Produto","careerPageName":"Empresa Brasileira","jobUrl":"https://empresa.gupy.io/job/123","workplaceType":"remote","state":"Goiás","createdAt":"2026-10-17"}]}
        with patch("source_extensions.fetch_json",return_value=payload):
            jobs,state,total=extra("gupy","gerente de produto")
        self.assertEqual(total,1)
        self.assertEqual(state,"validado")
        self.assertEqual(jobs[0]["company"],"Empresa Brasileira")
        self.assertIn("Brasil",jobs[0]["location"])

    def test_generic_growth_engineer_is_not_default_role(self):
        from search_filters import analyze_filters
        entries=[{"title":"Staff Data Scientist, Growth","location":"Brazil Remote","published":"2026-10-17"},
                 {"title":"Growth Manager","location":"Brazil Remote","published":"2026-10-17"},
                 {"title":"Shopify Growth Developer","location":"Brazil Remote","published":"2026-10-17"}]
        confirmed,review,reasons=analyze_filters(entries,"Growth","BR","remote",30)
        self.assertEqual([x["title"] for x in confirmed],["Growth Manager"])

    def test_relevant_marketing_roles_not_lost(self):
        from search_filters import role_match, search_terms
        self.assertTrue(role_match("analista de marketing",search_terms("Marketing")))
        self.assertTrue(role_match("coordenador de growth",search_terms("Growth")))
        self.assertFalse(role_match("staff data scientist, growth",search_terms("Growth")))
        self.assertFalse(role_match("shopify growth developer",search_terms("Growth")))

    def test_source_scoped_before_network(self):
        from collectors import collect
        with patch("collectors.pull") as p:
            p.return_value=({"source":"inHire","term":"amcom","status":"ok","received":0},[])
            _,details=collect(["product owner"],"BR","inhire")
        self.assertTrue(details)
        self.assertTrue(all(d["source"]=="inHire" for d in details))
        self.assertTrue(all(call.args[0]=="inHire" for call in p.call_args_list))

    def test_history_excludes_confirmed_and_review(self):
        from app import exclude_history_matches
        old={"title":"Product Manager","company":"Acme","url":"https://x.example/old"}
        same_pair={"title":"Product Manager","company":"Acme","url":"https://x.example/new"}
        new={"title":"Product Owner","company":"Another","url":"https://x.example/fresh"}
        pending_old={"title":"Project Manager","company":"Old Co","url":"https://x.example/pending"}
        confirmed,review,count=exclude_history_matches(
            [old,same_pair,new],[pending_old,new],
            {"x.example/old","x.example/pending"},{"acme|product manager"})
        self.assertEqual([j["url"] for j in confirmed],["https://x.example/fresh"])
        self.assertEqual([j["url"] for j in review],["https://x.example/fresh"])
        self.assertEqual(count,3)

    def test_search_jobs_route_points_to_search_handler(self):
        from app import app,search_jobs,exclude_history_matches
        routes=[r for r in app.routes if getattr(r,"path",None)=="/api/search-jobs"]
        self.assertEqual(len(routes),1)
        self.assertIs(routes[0].endpoint,search_jobs)
        self.assertIsNot(routes[0].endpoint,exclude_history_matches)

    def test_history_checked_for_both_result_types(self):
        from pathlib import Path
        code=Path("app.py").read_text()
        self.assertIn('items+review',code)
        self.assertIn('"review_items":pending[:150]',code)
        self.assertIn('"review_items":pending[:150]',code)
        self.assertNotIn('"already_known":url_key',code)

    def test_brazilian_city_and_remote_synonyms(self):
        from search_filters import analyze_filters
        rows=[
         {"title":"Líder de Produtos","location":"São Paulo - Homeoffice","published":""},
         {"title":"Marketing Ops Manager","location":"Belo Horizonte - 100% remoto","published":""},
         {"title":"Product Manager","location":"Brazil - Remote-first","published":""},
         {"title":"Growth Developer","location":"Brasil Remoto","published":""}
        ]
        confirmed,review,why=analyze_filters(rows,country="BR",mode="remote",days=0)
        self.assertEqual([x["title"] for x in confirmed],["Líder de Produtos","Marketing Ops Manager","Product Manager"])
        self.assertEqual(review,[])

    def test_any_period_does_not_require_publication(self):
        from search_filters import analyze_filters
        rows=[{"title":"Product Owner","location":"Brasil | Teletrabalho","published":""}]
        confirmed,review,_=analyze_filters(rows,country="BR",mode="remote",days=0)
        self.assertEqual(len(confirmed),1)
        recent,review,_=analyze_filters(rows,country="BR",mode="remote",days=30)
        self.assertFalse(recent)
        self.assertEqual(len(review),1)

    def test_collectors_preserve_titles_before_relevance(self):
        from collectors import pull
        with patch("collectors.fetch_json",return_value={"jobs":[{"title":"Líder de Produtos","absolute_url":"https://example.com/1","location":{"name":"São Paulo"}}]}):
            detail,jobs=pull("Greenhouse","board")
        self.assertEqual(len(jobs),1)

    def test_equivalence_families_in_three_languages(self):
        from search_filters import role_match,search_terms
        self.assertTrue(role_match("especialista de produtos",search_terms("Product Manager")))
        self.assertTrue(role_match("coordenadora de projetos",search_terms("Project Manager")))
        self.assertTrue(role_match("Marketing Ops Manager",search_terms("Marketing")))
        self.assertTrue(role_match("Growth Marketer",search_terms("Growth")))
        self.assertTrue(role_match("Analista de Negócios",search_terms("Business Analyst")))
        self.assertFalse(role_match("Growth Data Scientist",search_terms("Growth")))
        self.assertFalse(role_match("Frontend Developer - Product",search_terms("Product Manager")))

    def test_bilingual_discovery_queries(self):
        from search_filters import discovery_queries
        q=discovery_queries("Product Manager, Project Manager, Marketing, Growth")
        self.assertIn("gerente de produto",q)
        self.assertIn("gerente de projetos",q)
        self.assertIn("marketing manager",q)
        self.assertIn("growth manager",q)
        self.assertLessEqual(len(q),12)

    def test_geo_workplace_equivalents(self):
        from search_filters import analyze_filters
        rows=[
         {"title":"Product Lead","location":"","country":"Brasil","workplaceType":"Work from home","published":""},
         {"title":"Gerente de Projetos","location":"Goiânia","workplaceType":"Teletrabalho","published":""},
         {"title":"Marketing Ops Manager","location":"USA only","workplaceType":"Remoto","published":""}
        ]
        confirmed,review,_=analyze_filters(rows,country="BR",mode="remote",days=0)
        self.assertEqual(len(confirmed),2)
        self.assertFalse(review)

    def test_jd_recovers_relevant_unusual_role(self):
        from search_filters import analyze_filters
        row={"title":"Operations Enablement Lead","location":"Brasil - Remoto","published":"","description":"Lead project delivery, project planning, project governance and project stakeholders."}
        good,review,stats=analyze_filters([row],roles="Project Manager",country="BR",mode="remote",days=0)
        self.assertEqual(len(good),1)
        self.assertTrue(good[0]["jd_evidence"]["family_evidence"])
        self.assertEqual(good[0]["description"],"")

    def test_jd_does_not_make_generic_role_relevant(self):
        from search_filters import analyze_filters
        row={"title":"Chef de cozinha","location":"Brasil Remoto","published":"","description":"We value collaboration with product teams and other stakeholders."}
        good,review,stats=analyze_filters([row],roles="Product Manager",country="BR",mode="remote",days=0)
        self.assertFalse(good+review)

    def test_jd_geo_remote_and_spanish_evidence(self):
        from search_filters import analyze_filters
        base={"title":"Product Manager","location":"","published":"","description":"Fully remote role, work from Brazil. Lead product strategy and product discovery."}
        good,review,_=analyze_filters([base],roles="Product Manager",country="BR",mode="remote",days=0)
        self.assertEqual(len(good),1)
        blocked={**base,"description":base["description"]+" Fluent Spanish required."}
        good,review,stats=analyze_filters([blocked],roles="Product Manager",country="BR",mode="remote",days=0)
        self.assertEqual(len(good)+len(review),0)
        optional={**base,"description":base["description"]+" Spanish preferred."}
        good,review,stats=analyze_filters([optional],roles="Product Manager",country="BR",mode="remote",days=0)
        self.assertEqual(len(good),1)

    def test_jd_unavailable_remains_unverified(self):
        from search_filters import analyze_filters
        row={"title":"Product Owner","location":"","published":"","description":""}
        good,review,_=analyze_filters([row],roles="Product Owner",country="BR",mode="remote",days=0)
        self.assertEqual(len(good),0)
        self.assertEqual(len(review),1)

    def test_work_modes_are_mutually_exclusive(self):
        from search_filters import analyze_filters
        rows=[
          {"title":"Product Owner","location":"Brasil","workplaceType":"remote","published":""},
          {"title":"Product Owner","location":"Brasil","workplaceType":"hybrid","published":""},
          {"title":"Product Owner","location":"Brasil","workplaceType":"on-site","published":""},
          {"title":"Product Owner","location":"Brasil","published":""},
          {"title":"Product Owner","location":"Brasil - Híbrido / remoto parcial","published":""},
        ]
        for selection,expected in (("remote","remote"),("hybrid","hybrid"),("onsite","on-site")):
            good,review,stats=analyze_filters(rows,"Product Owner","BR",selection,0)
            self.assertEqual([j.get("workplaceType","location-hybrid") for j in good],([expected,"location-hybrid"] if selection=="hybrid" else [expected]))
            self.assertEqual(len(review),1)
            self.assertIn("modalidade",review[0]["needs_verification"])

    def test_jd_fills_missing_mode_but_does_not_override_hybrid(self):
        from search_filters import analyze_filters
        rows=[{"title":"Product Manager","location":"Brasil","description":"This is a fully remote role. Lead product strategy and product discovery."},
              {"title":"Product Manager","location":"Brasil","workplaceType":"hybrid","description":"Our company is remote first and our teams work from home."}]
        good,review,_=analyze_filters(rows,"Product Manager","BR","remote",0)
        self.assertEqual(len(good),1)
        self.assertEqual(good[0]["workplaceType"] if "workplaceType" in good[0] else "", "")
        self.assertFalse(review)

    def test_work_mode_source_of_truth(self):
        from search_filters import detect_work_mode,analyze_filters
        self.assertEqual(detect_work_mode({"workplaceType":"hybrid","location":"Brazil remote"}),"hybrid")
        self.assertEqual(detect_work_mode({"workplaceType":"On-site","location":"Brazil"}),"onsite")
        self.assertEqual(detect_work_mode({"workplaceType":"Remote","location":"Brazil"}),"remote")
        self.assertEqual(detect_work_mode({"location":"Brasil - Híbrido / remoto parcial"}),"hybrid")
        self.assertEqual(detect_work_mode({"remote":False,"location":"Brasil"}),None)
        rows=[{"title":"Product Owner","location":"Brasil","workplaceType":x,"published":""} for x in ("hybrid","remote","onsite")]
        for mode in ("hybrid","remote","onsite"):
            confirmed,review,reasons=analyze_filters(rows,"Product Owner","BR",mode,0)
            self.assertEqual(len(confirmed),1)
            self.assertEqual(confirmed[0]["detected_mode"],mode)
            self.assertEqual(len(review),0)

    def test_brazil_latam_region_decisions(self):
        from search_filters import geo_verdict
        checks=[
            ({"location":"São Paulo, SP"},"BR","eligible"),
            ({"location":"Brazil - remote"},"BR","eligible"),
            ({"countryCode":"BR"},"BR","eligible"),
            ({"location":"LATAM Remote"},"BR","eligible"),
            ({"location":"Latin America"},"BR","eligible"),
            ({"location":"Global Remote"},"BR","eligible"),
            ({"location":"Argentina - remoto"},"BR","excluded"),
            ({"location":"Chile"},"BR","excluded"),
            ({"location":"Americas"},"BR","unknown"),
            ({"location":"LATAM excluding Brazil"},"BR","excluded"),
            ({"location":""},"BR","unknown"),
            ({"location":"Argentina"},"LATAM","eligible"),
            ({"location":"Colombia"},"LATAM","eligible"),
            ({"location":"Brasil"},"LATAM","eligible"),
            ({"location":"México"},"LATAM","eligible"),
            ({"location":"Latin America"},"LATAM","eligible"),
            ({"location":"Europe only"},"LATAM","excluded"),
            ({"location":""},"LATAM","unknown"),
        ]
        for job,region,expected in checks:
            with self.subTest(job=job,region=region):
                self.assertEqual(geo_verdict(job,region),expected)

    def test_geo_filter_does_not_modify_modes(self):
        from search_filters import analyze_filters
        rows=[
           {"title":"Product Owner","location":"Argentina","workplaceType":"remote"},
           {"title":"Product Owner","location":"Brasil","workplaceType":"remote"},
           {"title":"Product Owner","location":"LATAM","workplaceType":"hybrid"}
        ]
        confirmed,review,_=analyze_filters(rows,"Product Owner","BR","remote",0)
        self.assertEqual([j["location"] for j in confirmed],["Brasil"])
        confirmed,review,_=analyze_filters(rows,"Product Owner","LATAM","remote",0)
        self.assertEqual([j["location"] for j in confirmed],["Argentina","Brasil"])
        confirmed,review,_=analyze_filters(rows,"Product Owner","BR","hybrid",0)
        self.assertEqual([j["location"] for j in confirmed],["LATAM"])

    def test_us_remote_is_not_brazil_or_latam(self):
        from search_filters import analyze_filters,geo_verdict
        for location in ("Remote US","Remote - US","US Remote","Remote, USA","United States - Remote"):
            for country in ("BR","LATAM"):
                with self.subTest(location=location,country=country):
                    self.assertEqual(geo_verdict({"location":location},country),"excluded")
                    good,review,why=analyze_filters(
                        [{"title":"Product Manager","location":location,"workplaceType":"remote","published":""}],
                        "Product Manager",country,"remote",0)
                    self.assertEqual(good,[])
                    self.assertEqual(review,[])
        self.assertEqual(geo_verdict({"location":"LATAM / Remote US"},"BR"),"excluded")
        self.assertEqual(geo_verdict({"location":"LATAM Remote"},"BR"),"eligible")
        self.assertEqual(geo_verdict({"location":"Brasil Remote"},"BR"),"eligible")

    def test_unknown_geo_is_review_not_confirmation(self):
        from search_filters import analyze_filters
        good,review,_=analyze_filters(
            [{"title":"Product Owner","location":"Remote","workplaceType":"remote"}],
            "Product Owner","BR","remote",0)
        self.assertEqual(good,[])
        self.assertEqual(review[0]["needs_verification"],["pais"])

    def test_mcp_not_claimed_integrated(self):
        self.assertIn("Render",CONNECTORS["Indeed MCP"])
        self.assertIn("Render",CONNECTORS["Firecrawl"])

if __name__=="__main__":
    unittest.main()
