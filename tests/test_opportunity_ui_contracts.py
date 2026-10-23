"""Ensure review jobs remain visible and all decision buttons share a component."""
import unittest
from pathlib import Path

class OpportunityUIContracts(unittest.TestCase):
    def test_reviews_in_main_result_map(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertIn("visibleReviews.forEach(v=>{if(!combined.has(v.url))combined.set(v.url,{...v,confirmed:false})})",s)
    def test_shared_action_buttons_in_all_three_sections(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertEqual(s.count("<DecisionActions job={v} pending={decisionNow.includes(v.url)} onDecision={markDecision} onGenerateCv={generateCv} cvPending={cvNow.includes(v.url)} cvError={cvErrors[v.url]}/>"),3)
        self.assertIn('role="alert"',s)
        self.assertIn("onClick={()=>onGenerateCv(job)}",s)
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
        self.assertNotIn("Preparar com ChatGPT</button>",s)

    def test_confirmed_and_scored_jobs_precede_uncertain_results(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertIn("const geoPriority=v=>",s)
        self.assertIn("if(geoDiff)return geoDiff;",s)
        self.assertLess(s.index("if(Boolean(a.confirmed)!==Boolean(b.confirmed))"),s.index("if(geoDiff)return geoDiff;"))
        self.assertLess(s.index("const scoreDiff=(b.ranking?.score??-1)"),s.index("if(geoDiff)return geoDiff;"))
        self.assertIn("if(explicitBrazil)return 0;",s)
        self.assertIn("if(latam)return 1;",s)
        self.assertIn("if(v.needs_verification?.includes('pais'))return 3;",s)
        self.assertIn(".sort((a,b)=>geoPriority(a)-geoPriority(b)).map(v=>",s)

    def test_indeed_on_demand_search_does_not_scan_catalog(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertIn("['himalayas','remotive','remoteok','indeed'].includes(source)",s)

    def test_initial_scoring_starts_before_full_catalog_scan_with_ten_job_cap(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertLess(s.index("const earlyRanking=rankEntireCollection(4)"),s.index("for(let n=0;n<180;n++)"))
        self.assertIn("rankEntireCollection(Math.max(0,10-scoredOrAttempted.size))",s)
        self.assertIn("filter(j=>!scoredOrAttempted.has(j.url)&&j.jd_available===true",s)

    def test_missing_jd_hides_cv_and_manual_scoring_and_has_clear_state(self):
        s=Path('src/Opportunities.jsx').read_text()
        self.assertIn("job.jd_available===true&&<button",s)
        self.assertIn("v.jd_available===true&&<button",s)
        self.assertIn("if(v.jd_available===false)return 'no_jd'",s)
        self.assertIn("'JD indisponível'",s)
        self.assertIn('Aderência local estimada',s)

    def test_intermediate_batches_can_score_without_waiting_180(self):
        s=Path('src/Opportunities.jsx').read_text()
        self.assertIn('let nextIntermediateRanking=12',s)
        self.assertLess(s.index('nextIntermediateRanking=12'),s.index('for(let n=0;n<180;n++)'))
        self.assertIn('await rankEntireCollection(Math.min(2,10-scoredOrAttempted.size))',s)

if __name__=="__main__":unittest.main()
