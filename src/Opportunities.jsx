import React,{useState,useEffect,useRef} from 'react';
const defaultRoles='Product Manager, Product Owner, Project Manager, Gerente de Projetos, Product Marketing, Marketing, Growth, Business Analyst, Analista de Negócios, PMO';
const initialCountries=[{value:'LATAM',label:'América Latina'},{value:'BR',label:'Brasil'}];
const boundedRoles=items=>items.reduce((selected,item)=>{const candidate=[...selected,item].join(', ');return candidate.length<=5000?[...selected,item]:selected},[]).join(', ');
function DecisionActions({job,pending,cvPending,cvError,onDecision,onGenerateCv}){
 const shared={borderRadius:7,padding:'7px 10px',fontWeight:700,cursor:pending?'wait':'pointer',color:'#fff'};
 return <div><div style={{display:'flex',justifyContent:'flex-end',gap:8}}>
  <button type="button" disabled={pending} onClick={()=>onDecision(job,'Candidatado')} style={{...shared,background:'#16803c',border:'1px solid #16803c'}}>Candidatado</button>
  <button type="button" disabled={pending} onClick={()=>onDecision(job,'Descartado')} style={{...shared,background:'#b91c1c',border:'1px solid #b91c1c'}}>Descartado</button>
  {job.jd_available===true&&<button type="button" disabled={cvPending} onClick={()=>onGenerateCv(job)} style={{...shared,background:'#2563eb',border:'1px solid #2563eb'}}>{cvPending?'Gerando DOCX com IA…':'Gerar currículo ATS'}</button>}
 </div>{cvError&&<small role="alert" style={{display:'block',color:'#b91c1c',whiteSpace:'normal',maxWidth:330,marginTop:5}}>{cvError}</small>}</div>;
}
export function OpportunitiesPanel({historyStats=null,onDecisionSaved=()=>{},profile=null}){
 const catalog=profile?.roles||[];
 const decidedUrlsRef=useRef(new Set());
 const visibleUndecided=jobs=>jobs.filter(j=>!decidedUrlsRef.current.has(j.url));
 const [onlyNew,setOnlyNew]=useState(false),[searchedQuery,setSearchedQuery]=useState(''),[source,setSource]=useState('all'),[sources,setSources]=useState([{value:'all',label:'Todas as fontes'},{value:'inhire',label:'inHire'},{value:'quickin',label:'Quickin'},{value:'gupy',label:'Gupy'}]),[roles,setRoles]=useState(profile?boundedRoles(catalog):defaultRoles),[days,setDays]=useState(String(profile?.days??0)),[country,setCountry]=useState(profile?.country||'BR'),[countries,setCountries]=useState(initialCountries),[mode,setMode]=useState(profile?.mode||'remote'),[sort,setSort]=useState('score');
 const [sourceStats,setSourceStats]=useState({}),[reviews,setReviews]=useState([]),[excluded,setExcluded]=useState([]),[filterStats,setFilterStats]=useState({}),[rawScanned,setRawScanned]=useState(0),[busy,setBusy]=useState(false),[results,setResults]=useState([]),[message,setMessage]=useState(''),[error,setError]=useState(''),[cvErrors,setCvErrors]=useState({}),[checked,setChecked]=useState(0),[counts,setCounts]=useState({new:0,total:0}),[completed,setCompleted]=useState(false),[visibleCount,setVisibleCount]=useState(10),[evaluated,setEvaluated]=useState(0),[evaluationTotal,setEvaluationTotal]=useState(0),[scoringNow,setScoringNow]=useState([]),[scoringFailed,setScoringFailed]=useState([]),[scoringAttempted,setScoringAttempted]=useState([]);
 const [flowTrace,setFlowTrace]=useState({raw:0,classified_confirmed:0,classified_review:0,history_excluded:0,display_confirmed:0,display_review:0});
 const [eligibilityTrace,setEligibilityTrace]=useState({eligible_for_detail:0,attempted:0,complete:0,failed:0,absent:0,deferred:0});
 const [sourceFieldStats,setSourceFieldStats]=useState({});
 const [sourceQuality,setSourceQuality]=useState({});
 useEffect(()=>{if(!profile)return;setRoles(boundedRoles(profile.roles||[]));setDays(String(profile.days??0));setCountry(profile.country||'BR');setMode(profile.mode||'remote');setResults([]);setReviews([]);setExcluded([]);setSearchedQuery('');setCompleted(false);},[profile]);
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
  setSourceFieldStats({});setSourceQuality({});
  setFlowTrace({raw:0,classified_confirmed:0,classified_review:0,history_excluded:0,display_confirmed:0,display_review:0});setEligibilityTrace({eligible_for_detail:0,attempted:0,complete:0,failed:0,absent:0,deferred:0});
  setVisibleCount(10);setEvaluated(0);setEvaluationTotal(0);setScoringNow([]);setScoringFailed([]);setScoringAttempted([]);setBusy(true);setSearchedQuery(query());setError('');setResults([]);setReviews([]);setExcluded([]);setSourceStats({});setFilterStats({});setRawScanned(0);setChecked(0);setCompleted(false);setMessage('Consultando '+(sources.find(x=>x.value===source)?.label||source)+'…');
  const qs=query();const all=new Map();const uncertain=new Map();const outOfFilter=new Map();const totals={};const sourceTotals={};let inspected=0;const record=(d)=>{setFlowTrace(old=>Object.fromEntries(Object.keys(old).map(k=>[k,old[k]+(d.flow_stats?.[k]||0)])));setEligibilityTrace(old=>Object.fromEntries(Object.keys(old).map(k=>[k,old[k]+(d.eligibility_fetch?.[k]||0)])));(d.details||[]).forEach(x=>{const src=(x.source||'desconhecida').toLowerCase();const n=sourceTotals[src]||{consultas:0,recebidas:0,erros:0,jdValidos:0,jdAusentes:0};n.consultas++;n.recebidas+=x.received||0;if(x.status==='error'||x.state==='pendente')n.erros++;sourceTotals[src]=n});for(const [src,v] of Object.entries(d.source_jd_stats||{})){const key=src.toLowerCase();const n=sourceTotals[key]||{consultas:0,recebidas:0,erros:0,jdValidos:0,jdAusentes:0};n.jdValidos+=(v.jd_valid||0);n.jdAusentes+=(v.jd_missing||0);sourceTotals[key]=n}setSourceStats({...sourceTotals});(d.review_items||[]).forEach(j=>uncertain.set(j.url,j));(d.excluded_items||[]).forEach(j=>{if(outOfFilter.size<300)outOfFilter.set(j.url,j)});setExcluded(visibleUndecided([...outOfFilter.values()]));for(const [key,n] of Object.entries(d.filter_stats||{})){totals[key]=(totals[key]||0)+n}inspected+=d.raw_count||0;setReviews(visibleUndecided([...uncertain.values()]));setFilterStats({...totals});setRawScanned(inspected)};let count=0;let completedAll=false;
  try{
   const requestJson=async (url,timeoutMs=30000)=>{const r=await fetch(url,{method:'POST',signal:AbortSignal.timeout(timeoutMs)});const ct=r.headers.get('content-type')||'';if(!ct.includes('application/json'))throw Error('Servidor retornou HTML ('+r.status+'); lote não processado');const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:('Erro HTTP '+r.status+' ao consultar vagas'));return d};
   let d;
   try{d=await requestJson('/api/search-jobs?'+qs,source==='all'?30000:90000)}
   catch(err){if(source!=='all'||(err.name!=='TimeoutError'&&err.name!=='AbortError'&&!(err instanceof TypeError)))throw err;
    setMessage('Consulta inicial demorou; continuando a busca nas fontes do catálogo sem repetir a mesma requisição.');
    d={items:[],details:[],total:0,raw_count:0};
   }
   accumulateSourceFields(d);

   (d.items||[]).forEach(j=>all.set(j.url,j));record(d);count+=d.total||0;
   setResults(visibleUndecided([...all.values()]));setCounts({new:all.size,total:count});
   // Select from the entire discovery universe before spending any AI tokens.
   const scoredOrAttempted=new Set();
   let resolved=0;
   async function enrichAvailable(selectedUrls){
     const selected=new Set(selectedUrls);
     const candidates=[...all.values()].filter(j=>selected.has(j.url)&&!scoredOrAttempted.has(j.url) &&
       j.ranking?.score==null);
     const waiting=[...new Map(candidates.map(j=>[j.url,j])).values()];
     if(!waiting.length)return;
     setEvaluationTotal(v=>v+waiting.length);
     for(let start=0;start<waiting.length;start+=2){
       const chunk=waiting.slice(start,start+2);
       chunk.forEach(j=>scoredOrAttempted.add(j.url));
       setScoringNow(chunk.map(j=>j.url));
       try{
         const response=await fetch('/api/jd/enrich',{method:'POST',headers:{'Content-Type':'application/json'},
           signal:AbortSignal.timeout(65000),body:JSON.stringify({jobs:chunk,roles})});
         if(!response.ok)throw Error('Falha HTTP '+response.status);
         const data=await response.json();
         for(const j of data.items||[]){
           if(all.has(j.url))all.set(j.url,{...all.get(j.url),...j});
           if(uncertain.has(j.url))uncertain.set(j.url,{...uncertain.get(j.url),...j});
         }
         setResults(visibleUndecided([...all.values()]));setReviews(visibleUndecided([...uncertain.values()]));
       }catch(err){
         setScoringFailed(prev=>[...prev,...chunk.map(j=>j.url)]);
       }finally{
         setScoringAttempted(prev=>[...prev,...chunk.map(j=>j.url)]);
         setScoringNow([]);
         resolved+=chunk.length;setEvaluated(resolved);
       }
     }
   }
   async function rankEntireCollection(maxNew=10){
     const available=[...all.values()].filter(j=>!scoredOrAttempted.has(j.url)&&j.jd_available===true&&!j.needs_verification?.length);
     if(!available.length||maxNew<=0)return;
     setMessage('Selecionando as melhores candidatas de '+all.size+' vagas antes da avaliação por IA…');
     const response=await fetch('/api/ranking/shortlist',{method:'POST',headers:{'Content-Type':'application/json'},
       signal:AbortSignal.timeout(15000),body:JSON.stringify({jobs:available.map(j=>({url:j.url,title:j.title,description:(j.description||'').slice(0,1500),ranking:j.ranking,needs_verification:j.needs_verification})),roles,limit:maxNew})});
     if(!response.ok)throw Error('Triagem global indisponível (HTTP '+response.status+'); nenhuma avaliação paga foi iniciada.');
     const selection=await response.json();
     if(!Array.isArray(selection.urls))throw Error('Resposta inválida da triagem global');
     setMessage('Triagem de '+all.size+' vagas concluída. Avaliando até '+selection.urls.length+' candidatas prioritárias com IA…');
     await enrichAvailable(selection.urls);
   }
   // Surface an initial, tightly bounded set of real scores while the slower
   // multi-board catalog continues scanning. Leave six slots for the complete
   // collection; never re-evaluate a URL or silently use mock scores.
   const earlyRanking=rankEntireCollection(4).catch(err=>{
     setScoringFailed(prev=>[...prev,'shortlist-initial']);
     setMessage('Triagem inicial indisponível; continuando a busca de vagas. '+err.message);
   });
   // Indeed is an on-demand provider, not a catalog board. A catalog scan
   // with source=indeed always returns 400 and can flood the UI with retries.
   if(['himalayas','remotive','remoteok','indeed'].includes(source)){
     await earlyRanking;
     await rankEntireCollection(Math.max(0,10-scoredOrAttempted.size));
     setCompleted(true);
     setMessage('Consulta à fonte '+source+' concluída; vagas apresentadas após filtros e exclusões do Histórico.');
     return;
   }
   let offset=0;
   let skipped=0;
   let nextIntermediateRanking=12;
   for(let n=0;n<180;n++){
    let batch;
     for(let attempt=0;attempt<2;attempt++){
      try{batch=await requestJson('/api/catalog/scan?offset='+offset+'&limit=4&'+qs);accumulateSourceFields(batch);break}
      catch(err){if(!['TimeoutError','AbortError'].includes(err.name)&&!(err instanceof TypeError))break}
     }
     if(!batch){skipped++;offset+=4;setMessage('Alguns quadros falharam após tentativa de recuperação; continuando os demais. Falhas: '+skipped);continue}
    (batch.items||[]).filter(j=>source==='all'||j.source?.toLowerCase()===source||(source==='greenhouse'&&j.source?.toLowerCase()==='greenhouse_eu')).forEach(j=>{const old=all.get(j.url);all.set(j.url,old&&(old.ranking?.score!=null||scoredOrAttempted.has(j.url))?old:j)});record(batch);
    offset=batch.next_offset;if(!Number.isFinite(offset))throw Error('Paginação inválida');
    count+=batch.found||0;setResults(visibleUndecided([...all.values()]));setChecked(x=>x+(batch.details||[]).length);setCounts({new:all.size,total:count});
    if(n+1>=nextIntermediateRanking && scoredOrAttempted.size<10 && [...all.values()].some(j=>j.jd_available===true && j.ranking?.score==null && !scoredOrAttempted.has(j.url))){
      await earlyRanking;
      try{await rankEntireCollection(Math.min(2,10-scoredOrAttempted.size))}catch(err){setScoringFailed(prev=>[...prev,'shortlist-intermediate'])}
      nextIntermediateRanking=n+13;
    }
    if(batch.complete){completedAll=true;break}
    if(!(batch.details||[]).length)break;
   }
   await earlyRanking;
   await rankEntireCollection(Math.max(0,10-scoredOrAttempted.size));
   setCompleted(completedAll);
   setMessage(completedAll&&!skipped&&!Object.values(sourceTotals).some(v=>v.erros)?'Busca concluída.':('Busca com fontes indisponíveis: '+(skipped+Object.values(sourceTotals).reduce((n,v)=>n+v.erros,0))+' falhas registradas. Zero resultado não significa zero vagas. Confira Fontes.'));
  }catch(e){setError(e.message);setMessage('Busca parcial — os resultados encontrados continuam disponíveis.')}
  finally{setBusy(false)}
 }
 async function evaluateManually(job){
   setScoringNow([job.url]);setScoringFailed(prev=>prev.filter(x=>x!==job.url));
   try{
     const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),30000);
     let response;
     try{response=await fetch('/api/jd/enrich',{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify({jobs:[job],roles,manual:true})})}
     finally{clearTimeout(timeout)}
     if(!response.ok)throw Error('Avaliação indisponível: HTTP '+response.status);
     const data=await response.json();const scored=(data.items||[]).find(x=>x.url===job.url);
     if(!scored)throw Error('A vaga não pôde ser avaliada');
     setReviews(prev=>prev.map(x=>x.url===job.url?{...x,...scored}:x));
     setResults(prev=>prev.map(x=>x.url===job.url?{...x,...scored}:x));
   }catch(e){setScoringFailed(prev=>[...prev,job.url]);setError(e.message)}
   finally{setScoringNow([]);setScoringAttempted(prev=>[...prev,job.url])}
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
 async function generateCv(job){
   // AI-only one-click flow: never silently substitute the old deterministic engine.
   if(cvNow.includes(job.url))return;
   setError('');setCvErrors(v=>({...v,[job.url]:''}));setCvNow(v=>[...v,job.url]);setMessage('IA analisando a vaga e preparando currículo ATS…');
   try{
     const response=await fetch('/api/resume/ai-download',{
       method:'POST',credentials:'same-origin',
       headers:{'Content-Type':'application/json'},
       signal:AbortSignal.timeout(65000),
       body:JSON.stringify({url:job.url,title:job.title,company:job.company||'',description:job.description||'',confirmed:job.confirmed===true,needs_verification:job.needs_verification||[]})});
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
 const scoreStatus=v=>{
   if(v.jd_available===false)return 'no_jd';
   if(v.ranking?.score!==null&&v.ranking?.score!==undefined)return 'scored';
   if(scoringFailed.includes(v.url))return 'failed';
   if(scoringNow.includes(v.url))return 'calculating';
   if(v.confirmed && busy && !scoringAttempted.includes(v.url) && v.ranking?.score==null)return 'waiting';
   return 'inconclusive';
 };
 const scoreDisplay=v=>{
   const state=scoreStatus(v);
   if(state==='scored')return <span style={{display:'grid',gap:3}}><strong>{v.ranking?.method==='local'?'Aderência local estimada':'Aderência'}: {v.ranking.score}/100</strong>{v.ranking?.method==='local'&&<small>Sem custo de IA · baseada apenas nos requisitos interpretados</small>}{v.needs_verification?.length>0&&<small>Elegibilidade a confirmar: {v.needs_verification.join(', ')}</small>}{v.ranking?.application_recommendation?.score!=null&&<strong>Recomendação: {v.ranking.application_recommendation.score}/100</strong>}<small>{({recomendada:'Vale candidatar-se',avaliar:'Avaliar candidatura',nao_prioritaria:'Baixa prioridade',nao_recomendada:'Não recomendar',confirmar:'Confirmar localização'})[v.ranking?.application_recommendation?.decision]||'Recomendação não calculada'}</small></span>;
   if(state==='waiting'||state==='calculating')return <span role="status" style={{display:'inline-flex',alignItems:'center',gap:6}}><span aria-hidden="true" className="jh-score-spinner"/>{state==='calculating'?'Calculando nota…':'Aguardando avaliação'}</span>;
   return <strong>{state==='no_jd'?'JD indisponível':state==='failed'?'Falha na avaliação':'Nota inconclusiva'}</strong>;
 };
 const scoreExplanation=v=>{
   const state=scoreStatus(v);
   if(state==='no_jd')return 'Descrição de vaga ausente ou inválida: sem nota, sem IA paga e sem geração de currículo.';
   if(state==='waiting'||state==='calculating')return 'Analisando os requisitos da vaga. A nota aparecerá quando a avaliação terminar.';
   if(state==='failed')return 'O lote falhou; tente uma nova busca';
   if(state==='scored' && v.ranking?.confidence==='essential_gap')return 'Exigência técnica obrigatória não comprovada no perfil';
   if(state==='scored' && v.ranking?.confidence==='hard_role_mismatch')return 'Incompatibilidade essencial com função técnica — nenhuma chamada de IA foi necessária';
   if(state==='scored')return v.ranking?.confidence==='requisitos_extraidos'?'% dos requisitos extraídos':v.ranking?.confidence==='amostra_limitada'?'Amostra limitada — conferir JD':'Nota calculada';
   if(v.ai_status==='failed')return 'A análise automática falhou. Tente uma nova busca.';
   if(v.ai_status==='cached_failure')return 'A análise automática falhou; o resultado foi guardado para evitar nova cobrança na mesma vaga.';
   if(v.ai_status==='disabled')return 'IA desativada — avaliação apenas por regras';
   if(v.ai_status==='budget_exhausted')return 'Limite mensal de IA atingido';
   if(v.jd_status==='indisponivel')return 'Não foi possível obter a descrição completa da vaga.';
   if(v.jd_status==='pendente')return 'A descrição ainda aguarda avaliação.';
   return (v.ai_status==='interpreted'||v.ai_status==='cache')?'A IA analisou a descrição, mas os requisitos e as evidências identificados ainda não sustentam uma nota confiável.':v.ranking?.confidence==='cobertura_insuficiente'?'JD disponível, mas a extração de requisitos é insuficiente para uma nota confiável.':'JD disponível, mas não há evidências suficientes para uma nota confiável.';
 };
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
 const ordered=[...combined.values()].filter(v=>!hiddenDecisions.includes(v.url)&&(!onlyNew||(v.is_new&&v.ranking?.score==null))).sort((a,b)=>{
   const date=v=>{const x=Date.parse(v.published||'');return Number.isFinite(x)?x:0};
   // Unconfirmed country/mode must not crowd out the confirmed opportunities.
   if(Boolean(a.confirmed)!==Boolean(b.confirmed))return a.confirmed?-1:1;
   // In the score view, an evaluated strong match must reach the first ten
   // even if its eligible remote location says LATAM rather than Brazil.
   if(sort==='score'){
     const scoreDiff=(b.ranking?.score??-1)-(a.ranking?.score??-1);
     if(scoreDiff)return scoreDiff;
   }
   if(country==='BR'||country==='LATAM'){
     const geoDiff=geoPriority(a)-geoPriority(b);
     if(geoDiff)return geoDiff;
   }
   return sort==='recommendation'?((b.ranking?.application_recommendation?.score??-1)-(a.ranking?.application_recommendation?.score??-1)||date(b)-date(a)):sort==='score'?((b.ranking?.score??-1)-(a.ranking?.score??-1)||((b.ranking?.requirements?.length||0)-(a.ranking?.requirements?.length||0))||date(b)-date(a)):(sort==='newest'?date(b)-date(a):date(a)-date(b))
 });
 return <section className="history-pane">
  <div className="infra-title"><div><h3>Encontrar oportunidades</h3><p>Personalize sua busca. Os quadros são verificados automaticamente ao pesquisar.</p></div></div>
  <div className="history-stats" aria-label="Contagem de decisões no Histórico"><span>Candidatado: <b>{historyStats?(historyStats.states.Candidatado||0).toLocaleString("pt-BR"):"—"}</b></span><span>Descartado: <b>{historyStats?(historyStats.states.Descartado||0).toLocaleString("pt-BR"):"—"}</b></span></div>
  <div className="jh-filters">
   {profile?<div className="jh-field jh-roles"><span>Selecione os cargos do seu catálogo (Meu Perfil)</span><div className="role-options">{catalog.map(role=><label key={role}><input type="checkbox" checked={roles.split(',').map(x=>x.trim()).includes(role)} disabled={busy} onChange={e=>setRoles(previous=>{const active=previous.split(',').map(x=>x.trim()).filter(Boolean);const next=(e.target.checked?[...new Set([...active,role])]:active.filter(x=>x!==role)).join(', ');if(next.length>5000){setError('Selecione menos cargos por busca (limite de 5.000 caracteres). Os demais continuam salvos no perfil.');return previous}setError('');return next})}/>{role}</label>)}</div>{!catalog.length&&<p>Cadastre cargos em Meu Perfil para iniciar a busca.</p>}</div>:
   <label className="jh-field jh-roles"><span>Quais vagas você procura? <button type="button" style={{marginLeft:12,fontSize:12}} disabled={busy} onClick={()=>setRoles(defaultRoles)}>Restaurar cargos padrão</button></span><textarea rows="3" value={roles} onChange={e=>setRoles(e.target.value)} maxLength={5000} placeholder="Separe os cargos por vírgula"/></label>}
   <label className="jh-field"><span>Fonte / site</span><select value={source} onChange={e=>changeSource(e.target.value)}>{sources.map(x=><option key={x.value} value={x.value}>{x.label}</option>)}</select></label>
   <label className="jh-field"><span>Publicadas nos últimos</span><select value={days} onChange={e=>setDays(e.target.value)}>{[['1','1 dia'],['3','3 dias'],['7','7 dias'],['15','15 dias'],['30','30 dias'],['60','60 dias'],['90','90 dias'],['0','Qualquer período']].map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
   <label className="jh-field"><span>Ordenar por</span><select value={sort} onChange={e=>setSort(e.target.value)}><option value="score">Maior aderência primeiro</option><option value="recommendation">Mais recomendadas primeiro</option><option value="newest">Mais recentes primeiro</option><option value="oldest">Mais antigas primeiro</option></select></label>
   <label className="jh-field"><span>País / Região</span><select value={country} onChange={e=>setCountry(e.target.value)}>{countries.map(c=><option key={c.value} value={c.value}>{c.label}</option>)}</select></label>
   <label className="jh-field"><span>Modalidade</span><select value={mode} onChange={e=>setMode(e.target.value)}><option value="remote">Remoto / Home office</option><option value="hybrid">Híbrido</option><option value="onsite">Presencial</option><option value="all">Todas as modalidades</option></select></label>
   <label style={{display:"inline-flex",alignItems:"center",gap:8,fontWeight:700,cursor:"pointer",gridColumn:"1 / -1"}}><input type="checkbox" checked={onlyNew} onChange={e=>setOnlyNew(e.target.checked)}/> Somente vagas novas <small style={{fontWeight:400,opacity:.8}}>(primeira descoberta, ainda sem nota)</small></label>
  </div>
  {busy&&<div role="status" className="notice"><p>Busca e avaliação em andamento: {checked} quadros consultados · {evaluated}/{evaluationTotal} JDs adicionais processados</p><progress value={evaluationTotal?evaluated:checked} max={evaluationTotal||Math.max(checked+4,1)} style={{width:"100%"}} /></div>}
  <button className="import-btn" disabled={busy||!roles.trim()} onClick={search}>{busy?'Pesquisando vagas e verificando quadros…':'Buscar oportunidades'}</button>
  {message&&<p className="notice" role="status">{message}{checked>0?' · Quadros verificados agora: '+checked:''}</p>}
  {error&&<p className="notice" role="alert">{error}</p>}
  {!currentMatches&&searchedQuery&&<p className="notice">Os filtros mudaram após a última pesquisa. Clique em Buscar oportunidades para atualizar os resultados.</p>}
  {currentMatches&&(results.length>0||reviews.length>0||completed)&&<><div className="history-stats"><span>{onlyNew?"Vagas novas nesta busca":"Oportunidades para avaliar"}: <b>{ordered.length}</b></span><span>Confirmadas: <b>{results.length}</b></span><span>Precisam de confirmação: <b>{visibleReviews.filter(v=>!results.some(r=>r.url===v.url)).length}</b></span><span>Anúncios analisados: <b>{rawScanned}</b></span><span>Quadros consultados: <b>{checked}</b></span>{mode!=='all'&&<span>Modalidade a confirmar: <b>{unknownModeCount}</b></span>}{country!=='GLOBAL'&&<span>País a confirmar: <b>{unknownCountryCount}</b></span>}</div>
  {ordered.length===0?<p>{onlyNew?"Nenhuma vaga inédita e sem nota nesta pesquisa. Desmarque o filtro para conferir os demais resultados e abra Fontes para verificar os quadros consultados.":"Nenhuma vaga correspondente foi identificada nos quadros consultados. Abra Fontes e Auditoria dos filtros para ver falhas e exclusões."}</p>:
  <><p>Somente vagas confirmadas para o país, modalidade e período selecionados. Vagas sem comprovação ficam separadas em "Vagas não confirmadas pelos filtros", inclusive anúncios sem data verificável.</p>
  <div className="table-wrap"><table><thead><tr><th>Nota / evidências</th><th>Cargo e situação</th><th>Empresa</th><th>Local informado</th><th>Data</th><th>Modalidade detectada</th><th>Fonte</th><th style={{textAlign:'right'}}>Ações</th></tr></thead><tbody>{ordered.slice(0,visibleCount).map(v=><tr key={v.url}><td>{scoreDisplay(v)}<small style={{display:'block'}}>{scoreExplanation(v)}</small><details><summary>Como foi avaliada?</summary><p>{v.ranking?.reason||'Sem análise'}</p>{v.ranking?.application_recommendation&&<p><strong>Recomendação de candidatura:</strong> {v.ranking.application_recommendation.score==null?'A confirmar':v.ranking.application_recommendation.score+'/100'} — {v.ranking.application_recommendation.reason} {v.ranking.application_recommendation.factors?.join(' · ')}</p>}{v.ranking?.match_summary&&<p><strong>Comparação profissional:</strong> {v.ranking.match_summary.direct} diretas · {v.ranking.match_summary.transferable} transferíveis · {v.ranking.match_summary.unproven} sem evidência documentada</p>}<small>Requisitos identificados: {v.ranking?.evaluated_requirements??0} · Obrigatórios: {v.ranking?.mandatory_count??0} · Desejáveis analisados: {v.ranking?.desirable_count??0} · Não comprovados: {v.ranking?.unverified_count??0} · Não interpretados: {v.ranking?.uninterpreted_count??0} · Cobertura: {v.ranking?.coverage_pct??0}%</small>{v.ranking?.requirements?.map((r,i)=><p key={i}><b>{r.type}: {r.name}</b> — {r.match_level==='direta'?'Correspondência direta':r.match_level==='transferivel'?'Experiência transferível':r.status==='nao_interpretado'?'Não interpretado':'Sem evidência comprovada'}{r.evidence?' · Evidência: '+r.evidence:''}{r.explanation?' · '+r.explanation:''}</p>)}<p>Prioridade (fora da nota): {v.ranking?.priority?.remote?'Remoto':'Modalidade não remota/indefinida'} · {v.ranking?.priority?.salary_informed?'Salário informado':'Salário não informado'} · Setor: {v.ranking?.priority?.sector||'não identificado'}</p></details></td><td><a href={v.url} target="_blank" rel="noopener noreferrer">{v.title}</a>{v.is_new&&v.ranking?.score==null&&<span title="Vaga descoberta pela primeira vez pelo Caçador" style={{display:'inline-flex',verticalAlign:'middle',marginLeft:8,background:'#ffedd5',color:'#9a3412',border:'1px solid #fdba74',borderRadius:999,padding:'2px 8px',fontWeight:800,fontSize:11}}>Novo!</span>}<small style={{display:'block',fontWeight:600,marginTop:4}}> {v.confirmed?'Confirmada':'A confirmar: '+(v.needs_verification||[]).join(', ')}</small>{v.jd_evidence?.family_evidence?.length>0&&<small style={{display:'block',opacity:.75}}>JD: {v.jd_evidence.family_evidence.flatMap(e=>e.evidence).slice(0,2).join(' / ')}</small>}</td><td>{v.company||'Não informada'}{v.already_known&&<small style={{display:'block',opacity:.65}}>Já conhecida</small>}</td><td>{v.location||'Não informada'}</td><td>{v.published?String(v.published).slice(0,10):'—'}</td><td>{({remote:'Remoto',hybrid:'Híbrido',onsite:'Presencial'})[v.detected_mode]||'Não identificada'}</td><td>{v.source||'—'}{v.board_slug&&<small style={{display:'block',opacity:.76}}>Quadro: {v.board_slug}</small>}</td><td style={{textAlign:'right',whiteSpace:'nowrap'}}><DecisionActions job={v} pending={decisionNow.includes(v.url)} onDecision={markDecision} onGenerateCv={generateCv} cvPending={cvNow.includes(v.url)} cvError={cvErrors[v.url]}/></td></tr>)}</tbody></table></div>{ordered.length>visibleCount&&<button type="button" className="import-btn" onClick={()=>setVisibleCount(v=>v+10)}>Mostrar mais 10 resultados ({Math.min(visibleCount,ordered.length)} de {ordered.length})</button>}</>}
  {reviewDiagnostics.length>0&&<details className="catalog-diagnostics"><summary>Vagas não confirmadas pelos filtros ({reviewDiagnostics.length})</summary><p>Essas vagas não foram incluídas entre as elegíveis. País, modalidade ou data precisam ser comprovados; a nota não representa elegibilidade.</p><div className="table-wrap"><table><thead><tr><th>Vaga</th><th>Fonte</th><th>Motivo</th><th>Nota</th></tr></thead><tbody>{reviewDiagnostics.map(v=><tr key={v.url}><td><a href={v.url} target="_blank" rel="noopener noreferrer">{v.title}</a></td><td>{v.source||'—'}</td><td>{(v.needs_verification||[]).join(', ')}</td><td>{scoreDisplay(v)} {v.jd_available===true&&<button type="button" disabled={scoringNow.includes(v.url)} onClick={()=>evaluateManually(v)}>Avaliar esta vaga</button>} <DecisionActions job={v} pending={decisionNow.includes(v.url)} onDecision={markDecision} onGenerateCv={generateCv} cvPending={cvNow.includes(v.url)} cvError={cvErrors[v.url]}/></td></tr>)}</tbody></table></div></details>}
  {excluded.length>0&&<details className="catalog-diagnostics"><summary>Fora dos filtros — decidir manualmente ({excluded.length} nesta amostra)</summary><p>Esses anúncios não passaram nos critérios selecionados. Não são considerados elegíveis. Mostramos até 25 por lote e 300 nesta busca, sem repetir vagas já decididas.</p><div className="table-wrap"><table><thead><tr><th>Vaga</th><th>Empresa</th><th>Fonte</th><th>Motivo da exclusão</th><th>Ações</th></tr></thead><tbody>{excluded.filter(v=>!hiddenDecisions.includes(v.url)).sort((a,b)=>geoPriority(a)-geoPriority(b)).map(v=><tr key={v.url}><td><a href={v.url} target="_blank" rel="noopener noreferrer">{v.title}</a></td><td>{v.company||'Não informada'}</td><td>{v.source||'—'}</td><td>{({cargo:'Cargo',pais:'País',modalidade:'Modalidade',data:'Data',espanhol_obrigatorio:'Espanhol obrigatório'})[v.excluded_reason]||v.excluded_reason}</td><td><DecisionActions job={v} pending={decisionNow.includes(v.url)} onDecision={markDecision} onGenerateCv={generateCv} cvPending={cvNow.includes(v.url)} cvError={cvErrors[v.url]}/></td></tr>)}</tbody></table></div></details>}
  <details className="catalog-diagnostics"><summary>Fontes consultadas nesta busca</summary><p>JDs válidos e ausentes: somente vagas elegíveis ou em revisão, antes da análise paga. Não representam todos os anúncios brutos.</p><div className="table-wrap"><table><thead><tr><th>Fonte</th><th>Consultas</th><th>Anúncios brutos</th><th>JDs válidos</th><th>JDs ausentes</th><th>Pendências</th></tr></thead><tbody>{Object.entries(sourceStats).sort((a,b)=>b[1].recebidas-a[1].recebidas).map(([source,v])=><tr key={source}><td>{source}</td><td>{v.consultas}</td><td>{v.recebidas}</td><td>{v.jdValidos||0}</td><td>{v.jdAusentes||0}</td><td>{v.erros}</td></tr>)}</tbody></table></div></details>
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
