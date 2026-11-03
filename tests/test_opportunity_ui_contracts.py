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
        self.assertEqual(s.count("<DecisionActions job={v} pending={decisionNow.includes(v.url)} onDecision={markDecision} onGenerateCv={generateCv} cvPending={cvNow.includes(v.url)} cvDraft={cvDrafts[v.url]} onCancelCv={cancelCvDraft} cvError={cvErrors[v.url]}/>"),2)
        self.assertEqual(s.count("<DecisionActions job={v} pending={decisionNow.includes(v.url)} onDecision={markDecision} onGenerateCv={generateCv} cvPending={cvNow.includes(v.url)} cvDraft={cvDrafts[v.url]} onCancelCv={cancelCvDraft} cvError={cvErrors[v.url]} manualOutsideFilters={true}/>"),1)
        self.assertIn('role="alert"',s)
        self.assertIn("onClick={()=>onGenerateCv(job,manualOutsideFilters)}",s)
        self.assertIn("background:'#2563eb'",s)
        self.assertEqual(s.count("onClick={()=>markDecision(v,'Candidatado')}"),0)
        self.assertEqual(s.count("onClick={()=>markDecision(v,'Descartado')}"),0)

    def test_cv_has_cancellable_prequeue_delay_and_source_queue(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertIn("const started=Date.now(),duration=5000;",s)
        self.assertIn("clearInterval(timer);cvDraftTimersRef.current.delete(url)",s)
        self.assertIn("void submitCv(job,manualOutsideFilters)",s)
        self.assertIn('onClick={()=>onCancelCv(job.url)}',s)
        self.assertIn("Fontes consultadas nesta busca · Fila ATS",s)
        self.assertIn('<section aria-label="Fila de currículos ATS"',s)
        self.assertNotIn('aria-label="Fontes e fila de currículos ATS"',s)
        self.assertIn("Apagar do banco",s)
        self.assertIn("window.confirm(",s)

    def test_cv_uses_existing_button_and_persistent_queue(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertIn("'Gerar currículo ATS'",s)
        self.assertEqual(s.count("onClick={()=>generateCv(v)}"),0)
        self.assertNotIn("v.ranking?.score!=null&&<button",s)
        self.assertIn("fetch('/api/resume/queue'",s)
        self.assertIn("downloadQueuedCv(job)",s)
        self.assertIn("a.download=job.filename||'curriculo.docx'",s)
        self.assertNotIn("window.open('https://chatgpt.com",s)
        self.assertNotIn("/api/resume/generate",s)
        self.assertNotIn("/api/resume/gpt-start",s)

    def test_docx_name_stays_owned_by_authenticated_server_profile(self):
        s=Path("app.py").read_text()
        self.assertIn('profile=(mu.current_profile.get() or {}) if mu.enabled else {}',s)
        self.assertIn('name=cv_download_filename(title,company)',s)
        self.assertIn('def resume_queue_download(job_id: str, request: Request)',s)
        self.assertIn('authenticated_uid=require_auth(request)',s)
        self.assertNotIn("Preparar com ChatGPT</button>",Path("src/Opportunities.jsx").read_text())

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
        self.assertIn("['himalayas','remotive','indeed'].includes(source)",s)

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
        self.assertIn('fetch(\'/api/resume/queue\'',s)
        self.assertNotIn('await earlyRanking;',s)

if __name__=="__main__":unittest.main()
