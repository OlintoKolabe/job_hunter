"""Ensure review jobs remain visible and all decision buttons share a component."""
import unittest
from pathlib import Path

class OpportunityUIContracts(unittest.TestCase):
    def test_reviews_only_in_collapsed_diagnostics(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertNotIn("visibleReviews.forEach(v=>{if(!combined.has(v.url))combined.set(v.url,{...v,confirmed:false})})",s)
        self.assertIn('Vagas não confirmadas pelos filtros',s)
        self.assertIn('const reviewDiagnostics=visibleReviews.filter(v=>v.needs_verification?.length)',s)
        self.assertIn('const combined=new Map();(currentMatches?results:[]).filter(v=>!v.needs_verification?.length)',s)
    def test_shared_action_buttons_in_all_three_sections(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertEqual(s.count("<DecisionActions job={v} pending={decisionNow.includes(v.url)} onDecision={markDecision} onGenerateCv={generateCv} cvPending={cvNow.includes(v.url)} cvError={cvErrors[v.url]}/>"),2)
        self.assertEqual(s.count("<DecisionActions job={v} pending={decisionNow.includes(v.url)} onDecision={markDecision} onGenerateCv={generateCv} cvPending={cvNow.includes(v.url)} cvError={cvErrors[v.url]} manualOutsideFilters={true}/>"),1)
        self.assertIn('role="alert"',s)
        self.assertIn("onClick={()=>onGenerateCv(job,manualOutsideFilters)}",s)
        self.assertIn("background:'#2563eb'",s)
        self.assertEqual(s.count("onClick={()=>markDecision(v,'Candidatado')}"),0)
        self.assertEqual(s.count("onClick={()=>markDecision(v,'Descartado')}"),0)

    def test_cv_is_existing_button_only_and_downloads_using_ai(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertIn("'Gerar currículo ATS'",s)
        self.assertEqual(s.count("onClick={()=>generateCv(v)}"),0)
        self.assertNotIn("v.ranking?.score!=null&&<button",s)
        self.assertIn("AI-only one-click flow",s)
        self.assertIn("fetch('/api/resume/ai-download'",s)
        self.assertIn("anchor.download=filename",s)
        self.assertNotIn("window.open('https://chatgpt.com",s)
        self.assertNotIn("/api/resume/generate",s)
        self.assertNotIn("/api/resume/gpt-start",s)

    def test_docx_download_fallback_uses_signed_in_profile_not_previous_owner(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertIn("const accountName=String(profile?.name||'').trim()",s)
        self.assertIn("const filename=found?decodeURIComponent(found[1]):(accountName+",s)
        self.assertNotIn("'Olinto Manso Pereira - '+(job.title",s)
        self.assertNotIn("Preparar com ChatGPT</button>",s)

    def test_confirmed_and_geographically_relevant_jobs_precede_uncertain_results(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertIn("const geoPriority=v=>",s)
        self.assertIn("if(geoDiff)return geoDiff;",s)
        self.assertLess(s.index("if(Boolean(a.confirmed)!==Boolean(b.confirmed))"),s.index("if(geoDiff)return geoDiff;"))
        self.assertNotIn("const scoreDiff=",s)
        self.assertIn("if(explicitBrazil)return 0;",s)
        self.assertIn("if(latam)return 1;",s)
        self.assertIn("if(v.needs_verification?.includes('pais'))return 3;",s)
        self.assertIn(".sort((a,b)=>geoPriority(a)-geoPriority(b)).map(v=>",s)

    def test_indeed_on_demand_search_does_not_scan_catalog(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertIn("['himalayas','remotive','remoteok','indeed'].includes(source)",s)

    def test_catalog_scan_does_not_start_paid_matchmaking(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertIn("const scanWorker=async()=>",s)
        self.assertNotIn("/api/jd/enrich",s)
        self.assertNotIn("rankEntireCollection",s)

    def test_missing_jd_hides_cv_and_all_score_controls_are_removed(self):
        s=Path('src/Opportunities.jsx').read_text()
        self.assertIn("(job.jd_available===true||manualOutsideFilters)&&<button",s)
        self.assertNotIn('Avaliar esta vaga',s)
        self.assertNotIn('Nota / evidências',s)
        self.assertNotIn('scoreDisplay',s)
        self.assertIn('Gerar currículo ATS',s)

    def test_out_of_filters_cv_uses_explicit_manual_action_only(self):
        s=Path('src/Opportunities.jsx').read_text()
        self.assertIn('manualOutsideFilters={true}',s)
        self.assertEqual(s.count('manualOutsideFilters={true}'),1)
        self.assertIn('onGenerateCv(job,manualOutsideFilters)',s)
        self.assertIn('manual_outside_filters:manualOutsideFilters',s)
        self.assertIn('ainda exige uma descrição válida da vaga',s)

    def test_catalog_scanning_remains_active_without_scoring(self):
        s=Path('src/Opportunities.jsx').read_text()
        self.assertIn('const scanWorker=async()=>',s)
        self.assertIn('await scanWorker();',s)
        self.assertIn('fetch(\'/api/resume/ai-download\'',s)
        self.assertNotIn('await earlyRanking;',s)

if __name__=="__main__":unittest.main()
