import React,{useState,useEffect,useRef} from 'react';
const defaultRoles='Product Manager, Product Owner, Project Manager, Gerente de Projetos, Product Marketing, Marketing, Growth, Business Analyst, Analista de Negócios, PMO';
const initialCountries=[{value:'LATAM',label:'América Latina'},{value:'BR',label:'Brasil'}];
const boundedRoles=items=>items.reduce((selected,item)=>{const candidate=[...selected,item].join(', ');return candidate.length<=5000?[...selected,item]:selected},[]).join(', ');
function DecisionActions({job,pending,cvPending,cvError,onDecision,onGenerateCv,manualOutsideFilters=false}){
 const shared={borderRadius:7,padding:'7px 10px',fontWeight:700,cursor:pending?'wait':'pointer',color:'#fff'};
 return <div><div style={{display:'flex',justifyContent:'flex-end',gap:8}}>
  <button type="button" disabled={pending} onClick={()=>onDecision(job,'Candidatado')} style={{...shared,background:'#16803c',border:'1px solid #16803c'}}>Candidatado</button>
  <button type="button" disabled={pending} onClick={()=>onDecision(job,'Descartado')} style={{...shared,background:'#b91c1c',border:'1px solid #b91c1c'}}>Descartado</button>
  {(job.jd_available===true||manualOutsideFilters)&&<button type="button" disabled={cvPending} onClick={()=>onGenerateCv(job,manualOutsideFilters)} style={{...shared,background:'#2563eb',border:'1px solid #2563eb'}}>{cvPending?'Gerando DOCX com IA…':'Gerar currículo ATS'}</button>}
 </div>{cvError&&<small role="alert" style={{display:'block',color:'#b91c1c',whiteSpace:'normal',maxWidth:330,marginTop:5}}>{cvError}</small>}</div>;
}
export function OpportunitiesPanel({historyStats=null,onDecisionSaved=()=>{},profile=null}){
 const catalog=profile?.roles||[];
 const decidedUrlsRef=useRef(new Set());
 const activeSearchRef=useRef(null);
 const profileIdentity=JSON.stringify([profile?.id||profile?.user_id||profile?.email||profile?.name||'',profile?.roles||[],profile?.country||'BR',profile?.mode||'remote',profile?.days??0]);
 const cancelActiveSearch=()=>{const running=activeSearchRef.current;if(running){running.abort();activeSearchRef.current=null;setBusy(false);}};
 const visibleUndecided=jobs=>jobs.filter(j=>!decidedUrlsRef.current.has(j.url));
 const [onlyNew,setOnlyNew]=useState(false),[searchedQuery,setSearchedQuery]=useState(''),[source,setSource]=useState('all'),[sources,setSources]=useState([{value:'all',label:'Todas as fontes'},{value:'inhire',label:'inHire'},{value:'quickin',label:'Quickin'},{value:'gupy',label:'Gupy'}]),[roles,setRoles]=useState(profile?boundedRoles(catalog):defaultRoles),[days,setDays]=useState(String(profile?.days??0)),[country,setCountry]=useState(profile?.country||'BR'),[countries,setCountries]=useState(initialCountries),[mode,setMode]=useState(profile?.mode||'remote'),[sort,setSort]=useState('newest');
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
  setVisibleCount(10);setBusy(true);setSearchedQuery(query());setError('');setResults([]);setReviews([]);setExcluded([]);setSourceStats({});setFilterStats({});setRawScanned(0);setChecked(0);setCompleted(false);setMessage('Consultando '+(sources.find(x=>x.value===source)?.label||source)+'…');
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
   try{d=await requestJson('/api/search-jobs?'+qs,source==='all'?45000:90000)}
   catch(err){if(!isCurrent()||source!=='all'||(err.name!=='TimeoutError'&&!(err instanceof TypeError)))throw err;
    initialSucceeded=false;
    setMessage('Consulta inicial demorou; continuando no catálogo, inclusive nas fontes iniciais ainda não confirmadas.');
    d={items:[],details:[],total:0,raw_count:0};
   }
   if(!isCurrent())return;
   accumulateSourceFields(d);

   (d.items||[]).forEach(j=>all.set(j.url,j));record(d);count+=d.total||0;
   setResults(visibleUndecided([...all.values()]));setCounts({new:all.size,total:count});
   // Indeed is an on-demand provider, not a catalog board. A catalog scan
   // with source=indeed always returns 400 and can flood the UI with retries.
   if(['himalayas','remotive','remoteok','indeed'].includes(source)){
     if(!isCurrent())return;
     setCompleted(true);
     setMessage('Consulta à fonte '+source+' concluída; vagas apresentadas após filtros e exclusões do Histórico.');
     return;
   }
   const scanBatchSize=12;
   // The free Render service must not promise an endless full catalog crawl.
   // Keep verified matches and name unfinished coverage explicitly.
   const scanDeadline=Date.now()+120000;
   let truncatedByTime=false;
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
    for(let n=0;n<125&&isCurrent();n++){
     if(Date.now()>scanDeadline){truncatedByTime=true;break}
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
      if(skipped>2)throw Error('Três lotes de catálogo indisponíveis; resultados parciais preservados.');
      setMessage('Falha transitória em lote; prosseguindo com as demais fontes.');
      offset+=scanBatchSize;
      continue;
     }
     if(!Number.isFinite(batch.total_sources)||!Number.isFinite(batch.next_offset)||batch.next_offset<=offset)
      throw Error('Paginação inválida no catálogo; resultados parciais preservados.');
     if(expectedTotal!==null&&expectedTotal!==batch.total_sources)
      throw Error('Catálogo mudou durante a busca; execute nova consulta.');
     expectedTotal=batch.total_sources;
     expectedBoardCount=expectedTotal;
     (batch.items||[]).filter(j=>source==='all'||j.source?.toLowerCase()===source||(source==='greenhouse'&&j.source?.toLowerCase()==='greenhouse_eu')).forEach(j=>all.set(j.url,j));
     record(batch);
     scannedBoards+=(batch.details||[]).length;
     count+=batch.found||0;setResults(visibleUndecided([...all.values()]));setChecked(x=>x+(batch.details||[]).length);setCounts({new:all.size,total:count});
     offset=batch.next_offset;
     if(batch.complete||offset>=expectedTotal){reachedEnd=true;break}
     if(!(batch.details||[]).length)throw Error('Lote vazio antes do fim do catálogo; busca parcial preservada.');
    }
   };
   // Single bounded cursor avoids overlap and limits canary CPU/memory pressure.
   await scanWorker();
   if(!isCurrent())return;
   completedAll=reachedEnd&&skipped===0;
   const failedSources=Object.values(sourceTotals).reduce((n,v)=>n+v.erros,0);
   const fullyComplete=completedAll&&failedSources===0;
   setCompleted(fullyComplete);
   const catalogCoverage=scannedBoards+' de '+(expectedBoardCount??'total indisponível')+' quadros do catálogo';
   setMessage(fullyComplete?'Busca concluída — '+catalogCoverage+'.':('Busca parcial — '+catalogCoverage+', '+skipped+' lotes e '+failedSources+' quadros com falha ou dados pendentes'+(truncatedByTime?', busca interrompida por limite de tempo':'')+'. Zero resultado não significa zero vagas. Confira Fontes.'));
  }catch(e){if(isCurrent()){setError(e.message);setMessage('Busca parcial — os resultados encontrados continuam disponíveis. '+e.message);}}
  finally{if(activeSearchRef.current===controller){activeSearchRef.current=null;setBusy(false)}}
 }
 const [cvNow,setCvNow]=useState([]);
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
 async function generateCv(job,manualOutsideFilters=false){
   // AI-only one-click flow: never silently substitute the old deterministic engine.
   if(cvNow.includes(job.url))return;
   setError('');setCvErrors(v=>({...v,[job.url]:''}));setCvNow(v=>[...v,job.url]);setMessage('IA analisando a vaga e preparando currículo ATS…');
   try{
     const response=await fetch('/api/resume/ai-download',{
       method:'POST',credentials:'same-origin',
       headers:{'Content-Type':'application/json'},
       signal:AbortSignal.timeout(65000),
       body:JSON.stringify({url:job.url,title:job.title,company:job.company||'',description:job.description||'',confirmed:job.confirmed===true,needs_verification:job.needs_verification||[],manual_outside_filters:manualOutsideFilters})});
     if(!response.ok){
       const error=await response.json().catch(()=>({}));
       throw Error(error.detail||('Erro HTTP '+response.status));
     }
     if(!(response.headers.get('content-type')||'').includes('wordprocessingml')){
       throw Error('O servidor não devolveu um DOCX');
     }
     const content=await response.blob();
     const disposition=response.headers.get('Content-Disposition')||'';
     const found=disposition.match(/filename\\*=UTF-8''([^;]+)/i);
     const accountName=String(profile?.name||'').trim();
     if(!found&&!accountName)throw Error('Não foi possível identificar o nome da conta para o currículo');
     const filename=found?decodeURIComponent(found[1]):(accountName+' - '+(job.title||'Vaga')+'.docx');
     const blobUrl=URL.createObjectURL(content);
     const anchor=document.createElement('a');
     anchor.href=blobUrl;anchor.download=filename;document.body.appendChild(anchor);
     anchor.click();anchor.remove();
     setTimeout(()=>URL.revokeObjectURL(blobUrl),30000);
     setMessage('Currículo personalizado por IA, auditado e disponível para download.');
   }catch(e){
     setMessage('');
     setError('Currículo não gerado: '+e.message);
     setCvErrors(v=>({...v,[job.url]:'Currículo não gerado: '+e.message}));
   }finally{setCvNow(v=>v.filter(x=>x!==job.url));}
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
  {busy&&<div role="status" className="notice"><p>Busca em andamento: {checked} quadros consultados</p><progress value={checked} max={Math.max(checked+4,1)} style={{width:"100%"}} /></div>}
  <button className="import-btn" disabled={busy||!roles.trim()} onClick={search}>{busy?'Pesquisando vagas e verificando quadros…':'Buscar oportunidades'}</button>
  {message&&<p className="notice" role="status">{message}{checked>0?' · Quadros verificados agora: '+checked:''}</p>}
  {error&&<p className="notice" role="alert">{error}</p>}
  {!currentMatches&&searchedQuery&&<p className="notice">Os filtros mudaram após a última pesquisa. Clique em Buscar oportunidades para atualizar os resultados.</p>}
  {currentMatches&&(results.length>0||reviews.length>0||completed)&&<><div className="history-stats"><span>{onlyNew?"Vagas novas nesta busca":"Oportunidades encontradas"}: <b>{ordered.length}</b></span><span>Confirmadas: <b>{results.length}</b></span><span>Precisam de confirmação: <b>{visibleReviews.filter(v=>!results.some(r=>r.url===v.url)).length}</b></span><span>Anúncios analisados: <b>{rawScanned}</b></span><span>Quadros consultados: <b>{checked}</b></span>{mode!=='all'&&<span>Modalidade a confirmar: <b>{unknownModeCount}</b></span>}{country!=='GLOBAL'&&<span>País a confirmar: <b>{unknownCountryCount}</b></span>}</div>
  {ordered.length===0?<p>{onlyNew?"Nenhuma vaga inédita nesta pesquisa. Desmarque o filtro para conferir os demais resultados e abra Fontes para verificar os quadros consultados.":"Nenhuma vaga correspondente foi identificada nos quadros consultados. Abra Fontes e Auditoria dos filtros para ver falhas e exclusões."}</p>:
  <><p>Somente vagas confirmadas para o país, modalidade e período selecionados. Vagas sem comprovação ficam separadas em "Vagas não confirmadas pelos filtros", inclusive anúncios sem data verificável.</p>
  <div className="table-wrap"><table><thead><tr><th>Cargo e situação</th><th>Empresa</th><th>Local informado</th><th>Data</th><th>Modalidade detectada</th><th>Fonte</th><th style={{textAlign:'right'}}>Ações</th></tr></thead><tbody>{ordered.slice(0,visibleCount).map(v=><tr key={v.url}><td><a href={v.url} target="_blank" rel="noopener noreferrer">{v.title}</a>{v.is_new&&<span title="Vaga descoberta pela primeira vez pelo Caçador" style={{display:'inline-flex',verticalAlign:'middle',marginLeft:8,background:'#ffedd5',color:'#9a3412',border:'1px solid #fdba74',borderRadius:999,padding:'2px 8px',fontWeight:800,fontSize:11}}>Novo!</span>}<small style={{display:'block',fontWeight:600,marginTop:4}}> {v.confirmed?'Confirmada':'A confirmar: '+(v.needs_verification||[]).join(', ')}</small>{v.jd_evidence?.family_evidence?.length>0&&<small style={{display:'block',opacity:.75}}>JD: {v.jd_evidence.family_evidence.flatMap(e=>e.evidence).slice(0,2).join(' / ')}</small>}</td><td>{v.company||'Não informada'}{v.already_known&&<small style={{display:'block',opacity:.65}}>Já conhecida</small>}</td><td>{v.location||'Não informada'}</td><td>{v.published?String(v.published).slice(0,10):'—'}</td><td>{({remote:'Remoto',hybrid:'Híbrido',onsite:'Presencial'})[v.detected_mode]||'Não identificada'}</td><td>{v.source||'—'}{v.board_slug&&<small style={{display:'block',opacity:.76}}>Quadro: {v.board_slug}</small>}</td><td style={{textAlign:'right',whiteSpace:'nowrap'}}><DecisionActions job={v} pending={decisionNow.includes(v.url)} onDecision={markDecision} onGenerateCv={generateCv} cvPending={cvNow.includes(v.url)} cvError={cvErrors[v.url]}/></td></tr>)}</tbody></table></div>{ordered.length>visibleCount&&<button type="button" className="import-btn" onClick={()=>setVisibleCount(v=>v+10)}>Mostrar mais 10 resultados ({Math.min(visibleCount,ordered.length)} de {ordered.length})</button>}</>}
  {reviewDiagnostics.length>0&&<details className="catalog-diagnostics"><summary>Vagas não confirmadas pelos filtros ({reviewDiagnostics.length})</summary><p>Essas vagas não foram incluídas entre as elegíveis. País, modalidade ou data precisam ser comprovados.</p><div className="table-wrap"><table><thead><tr><th>Vaga</th><th>Fonte</th><th>Motivo</th><th>Ações</th></tr></thead><tbody>{reviewDiagnostics.map(v=><tr key={v.url}><td><a href={v.url} target="_blank" rel="noopener noreferrer">{v.title}</a></td><td>{v.source||'—'}</td><td>{(v.needs_verification||[]).join(', ')}</td><td><DecisionActions job={v} pending={decisionNow.includes(v.url)} onDecision={markDecision} onGenerateCv={generateCv} cvPending={cvNow.includes(v.url)} cvError={cvErrors[v.url]}/></td></tr>)}</tbody></table></div></details>}
  {excluded.length>0&&<details className="catalog-diagnostics"><summary>Fora dos filtros — decidir manualmente ({excluded.length} nesta amostra)</summary><p>Esses anúncios não passaram nos critérios selecionados. Não são considerados elegíveis. Você pode solicitar um currículo ATS manualmente; a geração ainda exige uma descrição válida da vaga. Mostramos até 25 por lote e 300 nesta busca, sem repetir vagas já decididas.</p><div className="table-wrap"><table><thead><tr><th>Vaga</th><th>Empresa</th><th>Fonte</th><th>Motivo da exclusão</th><th>Ações</th></tr></thead><tbody>{excluded.filter(v=>!hiddenDecisions.includes(v.url)).sort((a,b)=>geoPriority(a)-geoPriority(b)).map(v=><tr key={v.url}><td><a href={v.url} target="_blank" rel="noopener noreferrer">{v.title}</a></td><td>{v.company||'Não informada'}</td><td>{v.source||'—'}</td><td>{({cargo:'Cargo',pais:'País',modalidade:'Modalidade',data:'Data',espanhol_obrigatorio:'Espanhol obrigatório'})[v.excluded_reason]||v.excluded_reason}</td><td><DecisionActions job={v} pending={decisionNow.includes(v.url)} onDecision={markDecision} onGenerateCv={generateCv} cvPending={cvNow.includes(v.url)} cvError={cvErrors[v.url]} manualOutsideFilters={true}/></td></tr>)}</tbody></table></div></details>}
  <details className="catalog-diagnostics"><summary>Fontes consultadas nesta busca</summary><p>JDs válidos e ausentes: somente vagas elegíveis ou em revisão, Não representam todos os anúncios brutos.</p><div className="table-wrap"><table><thead><tr><th>Fonte</th><th>Consultas</th><th>Anúncios brutos</th><th>JDs válidos</th><th>JDs ausentes</th><th>Pendências</th></tr></thead><tbody>{Object.entries(sourceStats).sort((a,b)=>b[1].recebidas-a[1].recebidas).map(([source,v])=><tr key={source}><td>{source}</td><td>{v.consultas}</td><td>{v.recebidas}</td><td>{v.jdValidos||0}</td><td>{v.jdAusentes||0}</td><td>{v.erros}</td></tr>)}</tbody></table></div></details>
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
