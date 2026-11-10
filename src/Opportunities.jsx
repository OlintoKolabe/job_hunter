import React,{useState,useEffect,useRef} from 'react';
const defaultRoles='Product Manager, Product Owner, Project Manager, Gerente de Projetos, Product Marketing, Marketing, Growth, Business Analyst, Analista de Negócios, PMO';
const initialCountries=[{value:'LATAM',label:'América Latina'},{value:'BR',label:'Brasil'}];
const boundedRoles=items=>items.reduce((selected,item)=>{const candidate=[...selected,item].join(', ');return candidate.length<=5000?[...selected,item]:selected},[]).join(', ');
function DecisionActions({job,pending,cvPending,cvDraft,cvError,onDecision,onGenerateCv,onCancelCv,manualOutsideFilters=false}){
 const shared={borderRadius:7,padding:'7px 10px',fontWeight:700,cursor:pending?'wait':'pointer',color:'#fff'};
 return <div><div style={{display:'flex',justifyContent:'flex-end',gap:8}}>
  <button type="button" disabled={pending} onClick={()=>onDecision(job,'Candidatado')} style={{...shared,background:'#16803c',border:'1px solid #16803c'}}>Candidatado</button>
  <button type="button" disabled={pending} onClick={()=>onDecision(job,'Descartado')} style={{...shared,background:'#b91c1c',border:'1px solid #b91c1c'}}>Descartado</button>
  <button type="button" disabled={cvPending||!!cvDraft} onClick={()=>onGenerateCv(job,manualOutsideFilters)} style={{...shared,background:'#2563eb',border:'1px solid #2563eb'}}>{cvPending?'Adicionando…':cvDraft?'Preparando…':'Gerar currículo ATS'}</button>
 </div>{cvDraft&&<div style={{display:'flex',alignItems:'center',gap:8,marginTop:6}}>
  <progress aria-label="Tempo para cancelar currículo" value={cvDraft.progress} max="100" style={{width:150}}/>
  <small>{Math.max(0,Math.ceil((100-cvDraft.progress)/20))} s para enviar</small>
  <button type="button" className="cv-action cv-action-danger" onClick={()=>onCancelCv(job.url)}>Cancelar</button>
 </div>}{cvError&&<small role="alert" style={{display:'block',color:'#b91c1c',whiteSpace:'normal',maxWidth:330,marginTop:5}}>{cvError}</small>}</div>;
}
export function OpportunitiesPanel({historyStats=null,onDecisionSaved=()=>{},profile=null}){
 const catalog=profile?.roles||[];
 const decidedUrlsRef=useRef(new Set());
 const activeSearchRef=useRef(null);
 const profileIdentity=JSON.stringify([profile?.id||profile?.user_id||profile?.email||profile?.name||'',profile?.roles||[],profile?.country||'BR',profile?.mode||'remote',profile?.days??0]);
 const cancelActiveSearch=()=>{const running=activeSearchRef.current;if(running){running.abort();activeSearchRef.current=null;setBusy(false);}};
 const visibleUndecided=jobs=>jobs.filter(j=>!decidedUrlsRef.current.has(j.url));
 const [onlyNew,setOnlyNew]=useState(false),[searchedQuery,setSearchedQuery]=useState(''),[source,setSource]=useState('all'),[sources,setSources]=useState([{value:'all',label:'Todas as fontes'},{value:'inhire',label:'inHire'},{value:'quickin',label:'Quickin'},{value:'gupy',label:'Gupy'}]),[roles,setRoles]=useState(profile?boundedRoles(catalog):defaultRoles),[days,setDays]=useState(String(profile?.days??0)),[country,setCountry]=useState(profile?.country||'BR'),[countries,setCountries]=useState(initialCountries),[mode,setMode]=useState(profile?.mode||'remote'),[sort,setSort]=useState('newest'),[totalBoards,setTotalBoards]=useState(null);
 const [sourceStats,setSourceStats]=useState({}),[reviews,setReviews]=useState([]),[excluded,setExcluded]=useState([]),[filterStats,setFilterStats]=useState({}),[rawScanned,setRawScanned]=useState(0),[busy,setBusy]=useState(false),[results,setResults]=useState([]),[message,setMessage]=useState(''),[error,setError]=useState(''),[cvErrors,setCvErrors]=useState({}),[checked,setChecked]=useState(0),[counts,setCounts]=useState({new:0,total:0}),[completed,setCompleted]=useState(false),[visibleCount,setVisibleCount]=useState(10);
 const [flowTrace,setFlowTrace]=useState({raw:0,classified_confirmed:0,classified_review:0,history_excluded:0,display_confirmed:0,display_review:0});
 const [eligibilityTrace,setEligibilityTrace]=useState({eligible_for_detail:0,attempted:0,complete:0,failed:0,absent:0,deferred:0});
 const [sourceFieldStats,setSourceFieldStats]=useState({});
 const [sourceQuality,setSourceQuality]=useState({});
 useEffect(()=>{cancelActiveSearch();if(!profile)return;setRoles(boundedRoles(profile.roles||[]));setDays(String(profile.days??0));setCountry(profile.country||'BR');setMode(profile.mode||'remote');setResults([]);setReviews([]);setExcluded([]);setSearchedQuery('');setCompleted(false);},[profileIdentity]);
 useEffect(()=>{if(activeSearchRef.current)cancelActiveSearch();},[roles,country,mode,days,source,sort]);
 useEffect(()=>()=>{activeSearchRef.current?.abort();activeSearchRef.current=null;},[]);
  useEffect(()=>{fetch('/api/search-filters',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(d=>{if(d?.countries)setCountries(d.countries);if(!Array.isArray(d?.sources)||d.sources.length<4)throw Error('Lista de fontes incompleta');setSources(d.sources);}).catch(()=>setError('Não foi possível carregar a lista completa de fontes. Atualize a página; se persistir, consulte o serviço.'))},[]);
 const query=()=>new URLSearchParams({roles,country,mode,days,sort,source}).toString();
 const accumulateSourceFields=payload=>{
  if(payload?.source_filter_quality){
   setSourceQuality(previous=>{
    const next={...previous};
    Object.entries(payload.source_filter_quality).forEach(([source,counts])=>{
     const old=next[source]||{};
     next[source]=Object.fromEntries(Object.entries(counts).map(([key,n])=>[key,(old[key]||0)+n]));
    });
    return next;
   });
  }
  if(!payload?.source_field_stats)return;
  setSourceFieldStats(previous=>{
   const next={...previous};
   Object.entries(payload.source_field_stats).forEach(([name,fields])=>{
    const current=next[name]||{};
    next[name]=Object.fromEntries(Object.entries(fields).map(([field,count])=>[field,(current[field]||0)+count]));
   });
   return next;
  });
 };
 const changeSource=value=>{setSource(value);setResults([]);setReviews([]);setExcluded([]);setChecked(0);setCompleted(false);setMessage("Fonte alterada. Clique em Buscar oportunidades para executar a nova seleção.");setError("");};
 async function search(){
  cancelActiveSearch();
  const controller=new AbortController();
  activeSearchRef.current=controller;
  const isCurrent=()=>activeSearchRef.current===controller&&!controller.signal.aborted;
  const searchSignal=ms=>AbortSignal.any([controller.signal,AbortSignal.timeout(ms)]);
  setSourceFieldStats({});setSourceQuality({});
  setFlowTrace({raw:0,classified_confirmed:0,classified_review:0,history_excluded:0,display_confirmed:0,display_review:0});setEligibilityTrace({eligible_for_detail:0,attempted:0,complete:0,failed:0,absent:0,deferred:0});
  setVisibleCount(10);setBusy(true);setSearchedQuery(query());setError('');setResults([]);setReviews([]);setExcluded([]);setSourceStats({});setFilterStats({});setRawScanned(0);setChecked(0);setTotalBoards(null);setCompleted(false);setMessage('Consultando '+(sources.find(x=>x.value===source)?.label||source)+'…');
  const qs=query();const all=new Map();const uncertain=new Map();const outOfFilter=new Map();const totals={};const sourceTotals={};let inspected=0;const record=(d)=>{if(!isCurrent())return;setFlowTrace(old=>Object.fromEntries(Object.keys(old).map(k=>[k,old[k]+(d.flow_stats?.[k]||0)])));setEligibilityTrace(old=>Object.fromEntries(Object.keys(old).map(k=>[k,old[k]+(d.eligibility_fetch?.[k]||0)])));(d.details||[]).forEach(x=>{const src=(x.source||'desconhecida').toLowerCase();const n=sourceTotals[src]||{consultas:0,recebidas:0,erros:0,jdValidos:0,jdAusentes:0};n.consultas++;n.recebidas+=x.received||0;if(x.status==='error'||x.state==='pendente')n.erros++;sourceTotals[src]=n});for(const [src,v] of Object.entries(d.source_jd_stats||{})){const key=src.toLowerCase();const n=sourceTotals[key]||{consultas:0,recebidas:0,erros:0,jdValidos:0,jdAusentes:0};n.jdValidos+=(v.jd_valid||0);n.jdAusentes+=(v.jd_missing||0);sourceTotals[key]=n}setSourceStats({...sourceTotals});(d.review_items||[]).forEach(j=>uncertain.set(j.url,j));(d.excluded_items||[]).forEach(j=>{if(outOfFilter.size<300)outOfFilter.set(j.url,j)});setExcluded(visibleUndecided([...outOfFilter.values()]));for(const [key,n] of Object.entries(d.filter_stats||{})){totals[key]=(totals[key]||0)+n}inspected+=d.raw_count||0;setReviews(visibleUndecided([...uncertain.values()]));setFilterStats({...totals});setRawScanned(inspected)};let count=0;let completedAll=false;
  try{
   const requestJson=async (url,timeoutMs=30000)=>{
    const r=await fetch(url,{method:'POST',signal:searchSignal(timeoutMs)});
    const ct=r.headers.get('content-type')||'';
    if(!ct.includes('application/json')){const err=Error('Servidor retornou HTML ('+r.status+'); lote não processado');err.status=r.status;throw err;}
    const d=await r.json();
    if(!r.ok){const err=Error(typeof d.detail==='string'?d.detail:('Erro HTTP '+r.status+' ao consultar vagas'));err.status=r.status;throw err;}
    if(!isCurrent())throw Error('Busca cancelada por troca de perfil ou filtros');
    return d;
   };
   let d;let initialSucceeded=true;
   // All-source searches start with the highest-yield catalog tasks and stream
   // confirmed results after each small batch. The former blocking 8+ role
   // fan-out could consume the gateway timeout before the first result.
   if(source==='all'){
    initialSucceeded=false;
    d={items:[],details:[],total:0,raw_count:0};
    setMessage('Priorizando vagas compatíveis; verificando fontes em lotes menores…');
   }else d=await requestJson('/api/search-jobs?'+qs,90000);
   if(!isCurrent())return;
   accumulateSourceFields(d);

   (d.items||[]).forEach(j=>all.set(j.url,j));record(d);count+=d.total||0;
   setResults(visibleUndecided([...all.values()]));setCounts({new:all.size,total:count});
   // Indeed is an on-demand provider, not a catalog board. A catalog scan
   // with source=indeed always returns 400 and can flood the UI with retries.
   if(['himalayas','remotive','indeed','leveljobs','remotejobs_org','tavily'].includes(source)){
     if(!isCurrent())return;
     setCompleted(true);
     setMessage('Consulta à fonte '+source+' concluída; vagas apresentadas após filtros e exclusões do Histórico.');
     return;
   }
   const scanBatchSize=source==='all'?8:12;
   // Each request is bounded, but the catalog cursor has no total time limit.
   // Long searches keep streaming verified results until every board is visited
   // or the user explicitly cancels the search.
   // Exclude only starter boards with successful initial responses.
   const starters=initialSucceeded?(d.details||[]).filter(x=>x.status==='ok'&&x.source&&x.term)
     .map(x=>String(x.source).toLowerCase()+':'+String(x.term).toLowerCase()).join(','):'';
   const starterQuery=starters?'&skip_starter='+encodeURIComponent(starters):'';
   let skipped=0;
   let reachedEnd=false;
   let scannedBoards=0;
   let expectedBoardCount=null;
   const scanWorker=async()=>{
    let offset=0;
    let expectedTotal=null;
    const failedOffsets=[];
    let consecutiveFailedBatches=0;
    while(isCurrent()){
     let batch;
     for(let attempt=0;attempt<2&&isCurrent();attempt++){
      try{
       batch=await requestJson('/api/catalog/scan?offset='+offset+'&limit='+scanBatchSize+'&'+qs+starterQuery,90000);
       accumulateSourceFields(batch);
       break;
      }catch(err){
       if(!isCurrent())throw err;
       if([400,401,403].includes(err.status))throw err;
       // Render's gateway can return HTML for a temporary 502/503/504.
       // Such responses must use the same bounded retry as a network timeout.
       if(!['TimeoutError','AbortError'].includes(err.name)&&!(err instanceof TypeError)&&![429,502,503,504].includes(err.status))throw err;
      }
     }
     if(!isCurrent())return;
     if(!batch){
      skipped++;
      failedOffsets.push(offset);
      consecutiveFailedBatches++;
      setMessage('Falha transitória no lote '+(offset+1)+'; continuando com os demais quadros sem encerrar a busca.');
      offset+=scanBatchSize;
      if(expectedTotal!==null&&offset>=expectedTotal){reachedEnd=true;break}
      if(consecutiveFailedBatches>=5)throw Error('Cinco lotes consecutivos indisponíveis; resultados preservados. Verifique a disponibilidade do servidor.');
      continue;
     }
     consecutiveFailedBatches=0;
     if(!Number.isFinite(batch.total_sources)||!Number.isFinite(batch.next_offset)||batch.next_offset<=offset)
      throw Error('Paginação inválida no catálogo; resultados parciais preservados.');
     if(expectedTotal!==null&&expectedTotal!==batch.total_sources)
      throw Error('Catálogo mudou durante a busca; execute nova consulta.');
     expectedTotal=batch.total_sources;
     expectedBoardCount=expectedTotal;
     setTotalBoards(expectedTotal);
     (batch.items||[]).filter(j=>source==='all'||j.source?.toLowerCase()===source||(source==='greenhouse'&&j.source?.toLowerCase()==='greenhouse_eu')).forEach(j=>all.set(j.url,j));
     record(batch);
     scannedBoards+=(batch.details||[]).length;
     count+=batch.found||0;setResults(visibleUndecided([...all.values()]));setChecked(x=>x+(batch.details||[]).length);setCounts({new:all.size,total:count});
     setMessage('Busca em andamento — '+scannedBoards+' de '+expectedTotal+' quadros verificados; resultados disponíveis conforme chegam.');
     offset=batch.next_offset;
     if(batch.complete||offset>=expectedTotal){reachedEnd=true;break}
     if(!(batch.details||[]).length)throw Error('Lote vazio antes do fim do catálogo; busca parcial preservada.');
    }
    // Revisit transient failures once after the forward pass. Do not let one
    // unavailable source prevent all other boards from being inspected.
    for(const retryOffset of failedOffsets){
     if(!isCurrent())return;
     try{
      const retry=await requestJson('/api/catalog/scan?offset='+retryOffset+'&limit='+scanBatchSize+'&'+qs+starterQuery,90000);
      if(retry.total_sources!==expectedTotal)continue;
      accumulateSourceFields(retry);
      (retry.items||[]).filter(j=>source==='all'||j.source?.toLowerCase()===source||(source==='greenhouse'&&j.source?.toLowerCase()==='greenhouse_eu')).forEach(j=>all.set(j.url,j));
      record(retry);
      scannedBoards+=(retry.details||[]).length;
      count+=retry.found||0;setResults(visibleUndecided([...all.values()]));setChecked(x=>x+(retry.details||[]).length);setCounts({new:all.size,total:count});
      skipped--;
     }catch(err){
      if(!isCurrent())return;
     }
    }
   };
   // One sequential cursor avoids overlap and limits Render CPU/memory pressure.
   await scanWorker();
   if(!isCurrent())return;
   completedAll=reachedEnd&&skipped===0;
   const failedSources=Object.values(sourceTotals).reduce((n,v)=>n+v.erros,0);
   const fullyComplete=completedAll&&failedSources===0;
   setCompleted(fullyComplete);
   const catalogCoverage=scannedBoards+' de '+(expectedBoardCount??'total indisponível')+' quadros do catálogo';
   setMessage(fullyComplete?'Busca concluída — '+catalogCoverage+'.':('Busca parcial — '+catalogCoverage+', '+skipped+' lotes e '+failedSources+' quadros com falha ou dados pendentes. Zero resultado não significa zero vagas. Confira Fontes.'));
  }catch(e){if(isCurrent()){setError(e.message);setMessage('Busca parcial — os resultados encontrados continuam disponíveis. '+e.message);}}
  finally{if(activeSearchRef.current===controller){activeSearchRef.current=null;setBusy(false)}}
 }
 const [cvNow,setCvNow]=useState([]);
 const [cvDrafts,setCvDrafts]=useState({});
 const cvDraftTimersRef=useRef(new Map());
 useEffect(()=>()=>{cvDraftTimersRef.current.forEach(timer=>clearInterval(timer));cvDraftTimersRef.current.clear()},[]);
 useEffect(()=>{
   cvDraftTimersRef.current.forEach(timer=>clearInterval(timer));
   cvDraftTimersRef.current.clear();
   setCvDrafts({});
 },[profileIdentity]);

 const [decisionNow,setDecisionNow]=useState([]),[hiddenDecisions,setHiddenDecisions]=useState([]);
 async function markDecision(job,state){
   if(decisionNow.includes(job.url))return;
   setDecisionNow(prev=>[...prev,job.url]);setError('');
   try{
     const response=await fetch('/api/jobs/disposition',{method:'POST',headers:{'Content-Type':'application/json'},
       signal:AbortSignal.timeout(15000),
       body:JSON.stringify({url:job.url,title:job.title,company:job.company||'',state,source:job.source||'Caçador'})});
     const data=await response.json().catch(()=>({}));
     if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:('Não foi possível salvar a decisão (HTTP '+response.status+').'));
     if(data.saved!==true||data.state!==state)throw Error('O servidor não confirmou a decisão. A vaga permaneceu na lista.');
     decidedUrlsRef.current.add(job.url);
     onDecisionSaved();
     setHiddenDecisions(prev=>[...new Set([...prev,job.url])]);
     setResults(prev=>prev.filter(x=>x.url!==job.url));
     setReviews(prev=>prev.filter(x=>x.url!==job.url));
     setExcluded(prev=>prev.filter(x=>x.url!==job.url));
     setMessage('Vaga marcada como '+state+'. Salva no Histórico e excluída das próximas buscas.');
   }catch(e){setError('Não foi possível marcar “'+job.title+'” como '+state+': '+(e.name==='TimeoutError'?'servidor demorou a responder; confira o Histórico antes de tentar novamente.':e.message))}
   finally{setDecisionNow(prev=>prev.filter(x=>x!==job.url))}
 }
 const [queueJobs,setQueueJobs]=useState([]);
 const queueAge=(timestamp)=>{const elapsed=Math.max(0,Math.floor((Date.now()-Date.parse(timestamp||''))/1000));return Number.isFinite(elapsed)?(elapsed>=60?Math.floor(elapsed/60)+'min '+elapsed%60+'s':elapsed+'s'):''};
 const enqueuedHereRef=useRef(new Set());
 const autoAttemptedRef=useRef(new Set());
 useEffect(()=>{
   queueJobs.forEach(job=>{
     if(job.status==='ready'&&enqueuedHereRef.current.has(job.id)&&!autoAttemptedRef.current.has(job.id)){
       autoAttemptedRef.current.add(job.id);
       void downloadQueuedCv(job);
     }
   });
 },[queueJobs]);
 useEffect(()=>{
   let active=true;
   const refresh=async()=>{
     try{
       const response=await fetch('/api/resume/queue',{credentials:'same-origin',cache:'no-store'});
       if(!response.ok)return;
       const data=await response.json();
       if(active)setQueueJobs(data.jobs||[]);
     }catch(_){}
   };
   refresh();
   const timer=setInterval(refresh,4000);
   return ()=>{active=false;clearInterval(timer)};
 },[]);
 async function refreshQueue(){
   try{
     const response=await fetch('/api/resume/queue',{credentials:'same-origin',cache:'no-store'});
     if(response.ok){const data=await response.json();setQueueJobs(data.jobs||[])}
   }catch(_){}
 }
 async function downloadQueuedCv(job){
   setCvErrors(v=>({...v,[job.id]:''}));
   try{
     const response=await fetch('/api/resume/queue/'+encodeURIComponent(job.id)+'/download',{credentials:'same-origin'});
     if(!response.ok){const detail=await response.json().catch(()=>({}));throw Error(detail.detail||('HTTP '+response.status))}
     const blob=await response.blob();
     const url=URL.createObjectURL(blob);
     const a=document.createElement('a');
     a.href=url;a.download=job.filename||'curriculo.docx';
     document.body.appendChild(a);a.click();a.remove();
     setTimeout(()=>URL.revokeObjectURL(url),30000);
   }catch(e){setCvErrors(v=>({...v,[job.id]:'Download indisponível: '+e.message}))}
 }
 const [deletingCvIds,setDeletingCvIds]=useState([]);
 const [selectedCvIds,setSelectedCvIds]=useState([]);
 const [bulkDeleting,setBulkDeleting]=useState(false);
 const [confirmClearAll,setConfirmClearAll]=useState(false);
 const [cvDeleteNotice,setCvDeleteNotice]=useState('');
 useEffect(()=>{setSelectedCvIds(ids=>ids.filter(id=>queueJobs.some(job=>job.id===id&&job.status!=='running')))},[queueJobs]);
 async function deleteQueuedCv(job){
   setDeletingCvIds(v=>[...v,job.id]);
   try{
     const response=await fetch('/api/resume/queue/'+encodeURIComponent(job.id),{method:'DELETE',credentials:'same-origin'});
     if(!response.ok){const data=await response.json().catch(()=>({}));throw Error(data.detail||('HTTP '+response.status))}
     setQueueJobs(v=>v.filter(j=>j.id!==job.id));
     setSelectedCvIds(v=>v.filter(id=>id!==job.id));
     enqueuedHereRef.current.delete(job.id);autoAttemptedRef.current.delete(job.id);
     setCvDeleteNotice('Currículo apagado do banco.');
   }catch(e){setCvErrors(v=>({...v,[job.id]:'Não foi possível apagar: '+e.message}))}
   finally{setDeletingCvIds(v=>v.filter(id=>id!==job.id))}
 }
 async function bulkDeleteCvs(all=false){
   const ids=selectedCvIds.filter(id=>queueJobs.some(j=>j.id===id&&j.status!=='running'));
   if(!all&&!ids.length)return;
   setBulkDeleting(true);setCvDeleteNotice('');
   try{
     const response=await fetch('/api/resume/queue/delete',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(all?{all:true}:{ids})});
     const data=await response.json().catch(()=>({}));
     if(!response.ok)throw Error(data.detail||('HTTP '+response.status));
     const deleted=new Set(data.deleted_ids||[]);
     deleted.forEach(id=>{enqueuedHereRef.current.delete(id);autoAttemptedRef.current.delete(id)});
     setQueueJobs(v=>v.filter(j=>!deleted.has(j.id)));
     setSelectedCvIds(v=>v.filter(id=>!deleted.has(id)));
     setCvDeleteNotice(`${data.deleted} currículo(s) apagado(s).${data.running?' '+data.running+' em geração permaneceram no banco.':''}`);
     setConfirmClearAll(false);
     await refreshQueue();
   }catch(e){setCvDeleteNotice('Não foi possível excluir: '+e.message)}
   finally{setBulkDeleting(false)}
 }
 function cancelCvDraft(url){
   const timer=cvDraftTimersRef.current.get(url);
   if(timer!==undefined){
     clearInterval(timer);cvDraftTimersRef.current.delete(url);
     setCvDrafts(v=>{const next={...v};delete next[url];return next});
   }
 }
 function generateCv(job,manualOutsideFilters=false){
   if(cvNow.includes(job.url)||cvDraftTimersRef.current.has(job.url))return;
   const started=Date.now(),duration=5000;
   setCvDrafts(v=>({...v,[job.url]:{progress:0}}));
   const timer=setInterval(()=>{
     if(!cvDraftTimersRef.current.has(job.url))return;
     const progress=Math.min(100,Math.floor((Date.now()-started)*100/duration));
     if(progress>=100){
       clearInterval(timer);cvDraftTimersRef.current.delete(job.url);
       setCvDrafts(v=>{const next={...v};delete next[job.url];return next});
       void submitCv(job,manualOutsideFilters);
     }else setCvDrafts(v=>({...v,[job.url]:{progress}}));
   },100);
   cvDraftTimersRef.current.set(job.url,timer);
 }
 async function submitCv(job,manualOutsideFilters=false){
   if(cvNow.includes(job.url))return;
   setError('');setCvNow(v=>[...v,job.url]);
   try{
     const response=await fetch('/api/resume/queue',{
       method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},
       body:JSON.stringify({url:job.url,title:job.title,company:job.company||'',
         description:job.description||'',confirmed:job.confirmed===true,
         needs_verification:job.needs_verification||[],manual_outside_filters:manualOutsideFilters})
     });
     const data=await response.json().catch(()=>({}));
     if(!response.ok)throw Error(data.detail||('HTTP '+response.status));
     if(data.id)enqueuedHereRef.current.add(data.id);
     setMessage('Currículo adicionado à fila. Pode solicitar outros enquanto este é preparado.');
     await refreshQueue();
   }catch(e){
     setCvErrors(v=>({...v,[job.url]:'Não foi possível adicionar à fila: '+e.message}));
   }finally{setCvNow(v=>v.filter(x=>x!==job.url))}
 }

 const currentMatches=searchedQuery!==''&&searchedQuery===query();
 const sourceKey=v=>String(v||'').toLowerCase().replace(/[^a-z0-9]/g,'');
 const visibleReviews=(currentMatches?reviews:[]).filter(v=>(source==='all'||sourceKey(v.source)===sourceKey(source)||source==='greenhouse'&&sourceKey(v.source)==='greenhouseeu'));
 const reviewDiagnostics=visibleReviews.filter(v=>v.needs_verification?.length);
 const unknownModeCount=visibleReviews.filter(v=>(v.needs_verification||[]).includes('modalidade')).length;
 const unknownCountryCount=visibleReviews.filter(v=>(v.needs_verification||[]).includes('pais')).length;
 // The main list is a strict result set: uncertainty about the selected
 // country/mode belongs only in the separate collapsed diagnostics section.
 const combined=new Map();(currentMatches?results:[]).filter(v=>!v.needs_verification?.length).forEach(v=>combined.set(v.url,{...v,confirmed:true}));
 const geoPriority=v=>{
   const raw=String(v.location||'').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
   const explicitBrazil=/(^|[^a-z])(brazil|brasil|brazilian|sao paulo|rio de janeiro|belo horizonte|brasilia|curitiba|goiania|porto alegre|recife|campinas|florianopolis)([^a-z]|$)/.test(raw)||/(^|[\s,(/])br([\s,)/]|$)/.test(raw);
   const latam=/(latam|latin america|america latina|south america|america do sul)/.test(raw);
   const global=/(worldwide|anywhere|global|work from anywhere)/.test(raw);
   // Country-restricted or non-Brazil postings must never jump ahead of Brazil.
   if(explicitBrazil)return 0;
   if(latam)return 1;
   if(global)return 2;
   if(!v.needs_verification?.includes('pais') && v.confirmed)return 2;
   if(v.needs_verification?.includes('pais'))return 3;
   return 4;
 };
 const ordered=[...combined.values()].filter(v=>!hiddenDecisions.includes(v.url)&&(!onlyNew||v.is_new)).sort((a,b)=>{
   const date=v=>{const x=Date.parse(v.published||'');return Number.isFinite(x)?x:0};
   // Unconfirmed country/mode must not crowd out the confirmed opportunities.
   if(Boolean(a.confirmed)!==Boolean(b.confirmed))return a.confirmed?-1:1;
   if(country==='BR'||country==='LATAM'){
     const geoDiff=geoPriority(a)-geoPriority(b);
     if(geoDiff)return geoDiff;
   }
   return sort==='newest'?date(b)-date(a):date(a)-date(b)
 });
 return <section className="history-pane">
  <div className="infra-title"><div><h3>Encontrar oportunidades</h3><p>Personalize sua busca. Os quadros são verificados automaticamente ao pesquisar.</p></div></div>
  <div className="history-stats" aria-label="Contagem de decisões no Histórico"><span>Candidatado: <b>{historyStats?(historyStats.states.Candidatado||0).toLocaleString("pt-BR"):"—"}</b></span><span>Descartado: <b>{historyStats?(historyStats.states.Descartado||0).toLocaleString("pt-BR"):"—"}</b></span></div>
  <div className="jh-filters">
   {profile?<div className="jh-field jh-roles"><span>Selecione os cargos do seu catálogo (Meu Perfil)</span><div className="role-options">{catalog.map(role=><label key={role}><input type="checkbox" checked={roles.split(',').map(x=>x.trim()).includes(role)} disabled={busy} onChange={e=>setRoles(previous=>{const active=previous.split(',').map(x=>x.trim()).filter(Boolean);const next=(e.target.checked?[...new Set([...active,role])]:active.filter(x=>x!==role)).join(', ');if(next.length>5000){setError('Selecione menos cargos por busca (limite de 5.000 caracteres). Os demais continuam salvos no perfil.');return previous}setError('');return next})}/>{role}</label>)}</div>{!catalog.length&&<p>Cadastre cargos em Meu Perfil para iniciar a busca.</p>}</div>:
   <label className="jh-field jh-roles"><span>Quais vagas você procura? <button type="button" style={{marginLeft:12,fontSize:12}} disabled={busy} onClick={()=>setRoles(defaultRoles)}>Restaurar cargos padrão</button></span><textarea rows="3" value={roles} onChange={e=>setRoles(e.target.value)} maxLength={5000} placeholder="Separe os cargos por vírgula"/></label>}
   <label className="jh-field"><span>Fonte / site</span><select value={source} onChange={e=>changeSource(e.target.value)}>{sources.map(x=><option key={x.value} value={x.value}>{x.label}</option>)}</select></label>
   <label className="jh-field"><span>Publicadas nos últimos</span><select value={days} onChange={e=>setDays(e.target.value)}>{[['1','1 dia'],['3','3 dias'],['7','7 dias'],['15','15 dias'],['30','30 dias'],['60','60 dias'],['90','90 dias'],['0','Qualquer período']].map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
   <label className="jh-field"><span>Ordenar por</span><select value={sort} onChange={e=>setSort(e.target.value)}><option value="newest">Mais recentes primeiro</option><option value="oldest">Mais antigas primeiro</option></select></label>
   <label className="jh-field"><span>País / Região</span><select value={country} onChange={e=>setCountry(e.target.value)}>{countries.map(c=><option key={c.value} value={c.value}>{c.label}</option>)}</select></label>
   <label className="jh-field"><span>Modalidade</span><select value={mode} onChange={e=>setMode(e.target.value)}><option value="remote">Remoto / Home office</option><option value="hybrid">Híbrido</option><option value="onsite">Presencial</option><option value="all">Todas as modalidades</option></select></label>
   <label style={{display:"inline-flex",alignItems:"center",gap:8,fontWeight:700,cursor:"pointer",gridColumn:"1 / -1"}}><input type="checkbox" checked={onlyNew} onChange={e=>setOnlyNew(e.target.checked)}/> Somente vagas novas <small style={{fontWeight:400,opacity:.8}}>(primeira descoberta)</small></label>
  </div>

  <details className="catalog-diagnostics"><summary>Fontes consultadas nesta busca · Fila ATS ({queueJobs.filter(j=>j.status==='queued'||j.status==='running').length} pendentes)</summary><section aria-label="Fila de currículos ATS" style={{marginBottom:16}}><h3>Fila de currículos ATS</h3>
    <p>Os currículos prontos ficam disponíveis aqui. A exclusão remove definitivamente o DOCX e o registro desta conta. Currículos em geração não podem ser apagados até terminarem.</p>
    <div className="cv-bulk-actions">
      <label><input type="checkbox" checked={queueJobs.some(j=>j.status!=='running')&&queueJobs.filter(j=>j.status!=='running').every(j=>selectedCvIds.includes(j.id))} onChange={e=>setSelectedCvIds(e.target.checked?queueJobs.filter(j=>j.status!=='running').map(j=>j.id):[])} disabled={bulkDeleting||!queueJobs.some(j=>j.status!=='running')}/> Selecionar todos os exibidos</label>
      <span>{selectedCvIds.length} selecionado(s)</span>
      <button type="button" className="cv-action cv-action-danger" disabled={bulkDeleting||!selectedCvIds.length} onClick={()=>bulkDeleteCvs(false)}>{bulkDeleting?'Excluindo…':'Apagar selecionados'}</button>
      <button type="button" className="cv-action cv-action-danger" disabled={bulkDeleting||!queueJobs.some(j=>j.status!=='running')} onClick={()=>setConfirmClearAll(true)}>Limpar todos os currículos</button>
    </div>
    {confirmClearAll&&<div className="cv-delete-confirm" role="group" aria-label="Confirmação para limpar todos os currículos"><strong>Apagar todos os currículos desta conta?</strong><span>Isso inclui registros que não estão nesta lista de 100 itens e não pode ser desfeito. Currículos em geração serão preservados.</span><div className="cv-bulk-actions"><button type="button" className="cv-action cv-action-danger" disabled={bulkDeleting} onClick={()=>bulkDeleteCvs(true)}>Sim, apagar todos</button><button type="button" className="cv-action cv-action-primary" disabled={bulkDeleting} onClick={()=>setConfirmClearAll(false)}>Voltar</button></div></div>}
    {cvDeleteNotice&&<p role="status" className="notice">{cvDeleteNotice}</p>}
    <div className="cv-card-list">
      {queueJobs.length===0&&<p>Nenhum currículo registrado.</p>}
      {queueJobs.map(j=><div key={j.id} className="cv-job-card">
        <input className="cv-job-select" type="checkbox" aria-label={'Selecionar currículo '+(j.title||'Vaga')} disabled={j.status==='running'||bulkDeleting||deletingCvIds.includes(j.id)} checked={selectedCvIds.includes(j.id)} onChange={e=>setSelectedCvIds(ids=>e.target.checked?[...ids,j.id]:ids.filter(id=>id!==j.id))}/>
        <div className="cv-job-info">
          <strong>{j.title||'Vaga'}</strong>
          <span>{j.company||'Empresa'}</span>
          <small>{({queued:'Na fila',running:'Gerando…',ready:'Pronto',failed:'Falhou'})[j.status]||j.status}{j.status==='queued'&&j.created_at?' · aguardando '+queueAge(j.created_at):''}{j.status==='running'&&j.started_at?' · processando há '+queueAge(j.started_at):''}</small>
          {j.status==='failed'&&<small role="alert">{j.error}</small>}
          {cvErrors[j.id]&&<small role="alert">{cvErrors[j.id]}</small>}
        </div>
        <div className="cv-job-actions">
          {j.status==='ready'&&<button type="button" className="cv-action cv-action-success" onClick={()=>downloadQueuedCv(j)}>Baixar DOCX</button>}
          {j.status!=='running'&&<button type="button" className="cv-action cv-action-danger" disabled={bulkDeleting||deletingCvIds.includes(j.id)} onClick={()=>deleteQueuedCv(j)}>{deletingCvIds.includes(j.id)?'Apagando…':'Apagar do banco'}</button>}
        </div>
      </div>)}
    </div>
  </section><p>JDs válidos e ausentes: somente vagas elegíveis ou em revisão, Não representam todos os anúncios brutos.</p><div className="table-wrap"><table><thead><tr><th>Fonte</th><th>Consultas</th><th>Anúncios brutos</th><th>JDs válidos</th><th>JDs ausentes</th><th>Pendências</th></tr></thead><tbody>{Object.entries(sourceStats).sort((a,b)=>b[1].recebidas-a[1].recebidas).map(([source,v])=><tr key={source}><td>{source}</td><td>{v.consultas}</td><td>{v.recebidas}</td><td>{v.jdValidos||0}</td><td>{v.jdAusentes||0}</td><td>{v.erros}</td></tr>)}</tbody></table></div></details>
  {busy&&<div role="status" className="notice"><p>Busca em andamento: {checked}{totalBoards!==null?' de '+totalBoards:''} quadros consultados</p><progress value={checked} max={Math.max(totalBoards??(checked+4),1)} style={{width:"100%"}} /></div>}
  <div className="search-actions">
    <button className="import-btn" disabled={busy||!roles.trim()} onClick={search}>{busy?'Pesquisando vagas e verificando quadros…':'Buscar oportunidades'}</button>
    {busy&&<button type="button" className="import-btn search-cancel-btn" onClick={()=>{cancelActiveSearch();setMessage('Busca cancelada por você. Os resultados já encontrados foram preservados.')}}>Cancelar busca</button>}
  </div>
  {message&&<p className="notice" role="status">{message}{checked>0?' · Quadros verificados agora: '+checked:''}</p>}
  {error&&<p className="notice" role="alert">{error}</p>}


  {!currentMatches&&searchedQuery&&<p className="notice">Os filtros mudaram após a última pesquisa. Clique em Buscar oportunidades para atualizar os resultados.</p>}
  {currentMatches&&(results.length>0||reviews.length>0||completed)&&<><div className="history-stats"><span>{onlyNew?"Vagas novas nesta busca":"Oportunidades encontradas"}: <b>{ordered.length}</b></span><span>Confirmadas: <b>{results.length}</b></span><span>Precisam de confirmação: <b>{visibleReviews.filter(v=>!results.some(r=>r.url===v.url)).length}</b></span><span>Anúncios analisados: <b>{rawScanned}</b></span><span>Quadros consultados: <b>{checked}</b></span>{mode!=='all'&&<span>Modalidade a confirmar: <b>{unknownModeCount}</b></span>}{country!=='GLOBAL'&&<span>País a confirmar: <b>{unknownCountryCount}</b></span>}</div>
  {ordered.length===0?<p>{onlyNew?"Nenhuma vaga inédita nesta pesquisa. Desmarque o filtro para conferir os demais resultados e abra Fontes para verificar os quadros consultados.":"Nenhuma vaga correspondente foi identificada nos quadros consultados. Abra Fontes e Auditoria dos filtros para ver falhas e exclusões."}</p>:
  <><p>Somente vagas confirmadas para o país, modalidade e período selecionados. Vagas sem comprovação ficam separadas em "Vagas não confirmadas pelos filtros", inclusive anúncios sem data verificável.</p>
  <div className="table-wrap"><table><thead><tr><th>Cargo e situação</th><th>Empresa</th><th>Local informado</th><th>Data</th><th>Modalidade detectada</th><th>Fonte</th><th style={{textAlign:'right'}}>Ações</th></tr></thead><tbody>{ordered.slice(0,visibleCount).map(v=><tr key={v.url}><td><a href={v.url} target="_blank" rel="noopener noreferrer">{v.title}</a>{v.is_new&&<span title="Vaga descoberta pela primeira vez pelo Caçador" style={{display:'inline-flex',verticalAlign:'middle',marginLeft:8,background:'#ffedd5',color:'#9a3412',border:'1px solid #fdba74',borderRadius:999,padding:'2px 8px',fontWeight:800,fontSize:11}}>Novo!</span>}<small style={{display:'block',fontWeight:600,marginTop:4}}> {v.confirmed?'Confirmada':'A confirmar: '+(v.needs_verification||[]).join(', ')}</small>{v.jd_evidence?.family_evidence?.length>0&&<small style={{display:'block',opacity:.75}}>JD: {v.jd_evidence.family_evidence.flatMap(e=>e.evidence).slice(0,2).join(' / ')}</small>}</td><td>{v.company||'Não informada'}{v.already_known&&<small style={{display:'block',opacity:.65}}>Já conhecida</small>}</td><td>{v.location||'Não informada'}</td><td>{v.published?String(v.published).slice(0,10):'—'}</td><td>{({remote:'Remoto',hybrid:'Híbrido',onsite:'Presencial'})[v.detected_mode]||'Não identificada'}</td><td>{v.source||'—'}{v.board_slug&&<small style={{display:'block',opacity:.76}}>Quadro: {v.board_slug}</small>}</td><td style={{textAlign:'right',whiteSpace:'nowrap'}}><DecisionActions job={v} pending={decisionNow.includes(v.url)} onDecision={markDecision} onGenerateCv={generateCv} cvPending={cvNow.includes(v.url)} cvDraft={cvDrafts[v.url]} onCancelCv={cancelCvDraft} cvError={cvErrors[v.url]}/></td></tr>)}</tbody></table></div>{ordered.length>visibleCount&&<button type="button" className="import-btn" onClick={()=>setVisibleCount(v=>v+10)}>Mostrar mais 10 resultados ({Math.min(visibleCount,ordered.length)} de {ordered.length})</button>}</>}
  {reviewDiagnostics.length>0&&<details className="catalog-diagnostics"><summary>Vagas não confirmadas pelos filtros ({reviewDiagnostics.length})</summary><p>Essas vagas não foram incluídas entre as elegíveis. País, modalidade ou data precisam ser comprovados.</p><div className="table-wrap"><table><thead><tr><th>Vaga</th><th>Fonte</th><th>Motivo</th><th>Ações</th></tr></thead><tbody>{reviewDiagnostics.map(v=><tr key={v.url}><td><a href={v.url} target="_blank" rel="noopener noreferrer">{v.title}</a></td><td>{v.source||'—'}</td><td>{(v.needs_verification||[]).join(', ')}</td><td><DecisionActions job={v} pending={decisionNow.includes(v.url)} onDecision={markDecision} onGenerateCv={generateCv} cvPending={cvNow.includes(v.url)} cvDraft={cvDrafts[v.url]} onCancelCv={cancelCvDraft} cvError={cvErrors[v.url]}/></td></tr>)}</tbody></table></div></details>}
  {excluded.length>0&&<details className="catalog-diagnostics"><summary>Fora dos filtros — decidir manualmente ({excluded.length} nesta amostra)</summary><p>Esses anúncios não passaram nos critérios selecionados. Não são considerados elegíveis. Você pode solicitar um currículo ATS manualmente; a geração ainda exige uma descrição válida da vaga. Mostramos até 25 por lote e 300 nesta busca, sem repetir vagas já decididas.</p><div className="table-wrap"><table><thead><tr><th>Vaga</th><th>Empresa</th><th>Fonte</th><th>Motivo da exclusão</th><th>Ações</th></tr></thead><tbody>{excluded.filter(v=>!hiddenDecisions.includes(v.url)).sort((a,b)=>geoPriority(a)-geoPriority(b)).map(v=><tr key={v.url}><td><a href={v.url} target="_blank" rel="noopener noreferrer">{v.title}</a></td><td>{v.company||'Não informada'}</td><td>{v.source||'—'}</td><td>{({cargo:'Cargo',pais:'País',modalidade:'Modalidade',data:'Data',espanhol_obrigatorio:'Espanhol obrigatório'})[v.excluded_reason]||v.excluded_reason}</td><td><DecisionActions job={v} pending={decisionNow.includes(v.url)} onDecision={markDecision} onGenerateCv={generateCv} cvPending={cvNow.includes(v.url)} cvDraft={cvDrafts[v.url]} onCancelCv={cancelCvDraft} cvError={cvErrors[v.url]} manualOutsideFilters={true}/></td></tr>)}</tbody></table></div></details>}

  <details className="catalog-diagnostics"><summary>Auditoria dos filtros</summary><p>Total bruto analisado: {rawScanned}. As exclusões são contadas por motivo, antes da deduplicação com o histórico.</p>{Object.entries(filterStats).map(([reason,n])=><p key={reason}>{reason}: <b>{n}</b></p>)}</details>
  <details className="catalog-diagnostics"><summary>Integridade dos dados por fonte</summary>
   <p>Campos efetivamente recebidos nos anúncios brutos, após a recuperação de detalhes disponível. Ausência não prova que o site original não possua a informação.</p>
   <div className="table-wrap"><table><thead><tr><th>Fonte</th><th>Vagas</th><th>Com data</th><th>Com descrição</th><th>Com localização</th><th>Modalidade explícita</th><th>Salário informado</th><th>Detalhes recuperados</th><th>Pendentes</th><th>Sem dados no detalhe</th><th>Falhas</th></tr></thead><tbody>
   {Object.entries(sourceFieldStats).sort((a,b)=>b[1].total-a[1].total).map(([name,s])=><tr key={name}><td>{name}</td><td>{s.total}</td><td>{s.dated}</td><td>{s.described}</td><td>{s.located}</td><td>{s.mode_explicit}</td><td>{s.salary_informed}</td><td>{s.details_recovered}</td><td>{s.details_pending}</td><td>{s.details_absent}</td><td>{s.details_failed}</td></tr>)}
   </tbody></table></div>
  </details>
  <details className="catalog-diagnostics"><summary>Qualidade da descoberta e dos filtros por fonte</summary>
   <p>Separação dos anúncios recebidos conforme os cargos, país, modalidade e período que você selecionou. "A confirmar" significa falta de prova, não elegibilidade aprovada. Uma vaga pode precisar confirmar mais de um campo. A ausência de data não é tratada como publicação recente.</p>
   <div className="table-wrap"><table><thead><tr><th>Fonte</th><th>Recebidas</th><th>Confirmadas</th><th>A confirmar</th><th>Fora dos filtros</th><th>Fora do cargo</th><th>Data ausente</th><th>País incerto</th><th>Modalidade incerta</th><th>Cargo adjacente</th></tr></thead><tbody>
    {Object.entries(sourceQuality).sort((a,b)=>b[1].raw-a[1].raw).map(([name,s])=><tr key={name}><td>{name}</td><td>{s.raw}</td><td>{s.confirmed}</td><td>{s.review}</td><td>{s.excluded}</td><td>{s.excluded_cargo}</td><td>{s.review_date}</td><td>{s.review_country}</td><td>{s.review_mode}</td><td>{s.review_role}</td></tr>)}
   </tbody></table></div>
  </details>
  <details className="catalog-diagnostics"><summary>Rastreamento da busca — Gate 9</summary>
   <p>Contagens por lote, antes e depois dos filtros. Registros podem repetir-se entre fontes e lotes; os totais da lista usam URLs únicas.</p>
   <p>Recebidos: <b>{flowTrace.raw}</b> · Confirmados pelos filtros: <b>{flowTrace.classified_confirmed}</b> · A confirmar: <b>{flowTrace.classified_review}</b> · Excluídos pelo histórico: <b>{flowTrace.history_excluded}</b> · Confirmados após histórico: <b>{flowTrace.display_confirmed}</b> · A confirmar após histórico: <b>{flowTrace.display_review}</b>.</p>
   <p>inHire — vagas pertinentes para consultar detalhes: <b>{eligibilityTrace.eligible_for_detail}</b> · Consultas tentadas: <b>{eligibilityTrace.attempted}</b> · Com dados recuperados: <b>{eligibilityTrace.complete}</b> · Sem metadados no endpoint: <b>{eligibilityTrace.absent}</b> · Falhas de extração: <b>{eligibilityTrace.failed}</b> · Adiadas pelo limite: <b>{eligibilityTrace.deferred}</b>.</p>
   <p>Uma data desconhecida nunca prova publicação recente. Essas vagas não são confirmadas nem recebem avaliação paga.</p>
  </details>
  </>}
 </section>
}
