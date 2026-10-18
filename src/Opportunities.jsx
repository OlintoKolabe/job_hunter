import React,{useState,useEffect} from 'react';
const defaultRoles='Product Manager, Product Owner, Project Manager, Gerente de Projetos, Product Marketing, Marketing, Growth, Business Analyst, Analista de Negócios, PMO';
const initialCountries=[{value:'LATAM',label:'América Latina'},{value:'BR',label:'Brasil'}];
export function OpportunitiesPanel(){
 const [searchedQuery,setSearchedQuery]=useState(''),[source,setSource]=useState('all'),[sources,setSources]=useState([{value:'all',label:'Todas as fontes'},{value:'inhire',label:'inHire'},{value:'quickin',label:'Quickin'},{value:'gupy',label:'Gupy'}]),[roles,setRoles]=useState(defaultRoles),[days,setDays]=useState('0'),[country,setCountry]=useState('BR'),[countries,setCountries]=useState(initialCountries),[mode,setMode]=useState('remote'),[sort,setSort]=useState('score');
 const [sourceStats,setSourceStats]=useState({}),[reviews,setReviews]=useState([]),[filterStats,setFilterStats]=useState({}),[rawScanned,setRawScanned]=useState(0),[busy,setBusy]=useState(false),[results,setResults]=useState([]),[message,setMessage]=useState(''),[error,setError]=useState(''),[checked,setChecked]=useState(0),[counts,setCounts]=useState({new:0,total:0}),[completed,setCompleted]=useState(false),[visibleCount,setVisibleCount]=useState(10),[evaluated,setEvaluated]=useState(0),[evaluationTotal,setEvaluationTotal]=useState(0),[scoringNow,setScoringNow]=useState([]),[scoringFailed,setScoringFailed]=useState([]),[scoringAttempted,setScoringAttempted]=useState([]);
 useEffect(()=>{fetch('/api/search-filters').then(r=>r.ok?r.json():null).then(d=>{if(d?.countries)setCountries(d.countries);if(d?.sources)setSources(d.sources)}).catch(()=>{})},[]);
 const query=()=>new URLSearchParams({roles,country,mode,days,sort,source}).toString();
 const changeSource=value=>{setSource(value);setResults([]);setReviews([]);setChecked(0);setCompleted(false);setMessage("Fonte alterada. Clique em Buscar oportunidades para executar a nova seleção.");setError("");};
 async function search(){
  setVisibleCount(10);setEvaluated(0);setEvaluationTotal(0);setScoringNow([]);setScoringFailed([]);setScoringAttempted([]);setBusy(true);setSearchedQuery(query());setError('');setResults([]);setReviews([]);setSourceStats({});setFilterStats({});setRawScanned(0);setChecked(0);setCompleted(false);setMessage('Consultando '+(sources.find(x=>x.value===source)?.label||source)+'…');
  const qs=query();const all=new Map();const uncertain=new Map();const totals={};const sourceTotals={};let inspected=0;const record=(d)=>{(d.details||[]).forEach(x=>{const source=x.source||'desconhecida';const n=sourceTotals[source]||{consultas:0,recebidas:0,erros:0};n.consultas++;n.recebidas+=x.received||0;if(x.status==='error'||x.state==='pendente')n.erros++;sourceTotals[source]=n});setSourceStats({...sourceTotals});(d.review_items||[]).forEach(j=>uncertain.set(j.url,j));for(const [key,n] of Object.entries(d.filter_stats||{})){totals[key]=(totals[key]||0)+n}inspected+=d.raw_count||0;setReviews([...uncertain.values()]);setFilterStats({...totals});setRawScanned(inspected)};let count=0;let completedAll=false;
  try{
   const requestJson=async url=>{let problem;for(let retry=0;retry<2;retry++){try{const r=await fetch(url,{method:'POST'});const ct=r.headers.get('content-type')||'';if(!ct.includes('application/json'))throw Error('Servidor retornou HTML ('+r.status+'); lote não processado');const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:('Erro HTTP '+r.status+' ao consultar vagas'));return d}catch(err){problem=err}}throw problem};
   const d=await requestJson('/api/search-jobs?'+qs);

   (d.items||[]).forEach(j=>all.set(j.url,j));record(d);count+=d.total||0;
   setResults([...all.values()]);setCounts({new:all.size,total:count});
   // Score incomplete JDs as each batch arrives rather than waiting for the entire catalog.
   const scoredOrAttempted=new Set();
   let resolved=0;
   async function enrichAvailable(){
     const candidates=[...all.values()].filter(j=>!scoredOrAttempted.has(j.url) &&
       (j.jd_status==='pendente' || (j.ranking?.score==null &&
       ['greenhouse','inhire'].some(src=>j.source?.toLowerCase().includes(src)))));
     const waiting=[...new Map(candidates.map(j=>[j.url,j])).values()];
     if(!waiting.length)return;
     setEvaluationTotal(v=>v+waiting.length);
     for(let start=0;start<waiting.length;start+=10){
       const chunk=waiting.slice(start,start+10);
       chunk.forEach(j=>scoredOrAttempted.add(j.url));
       setScoringNow(chunk.map(j=>j.url));
       try{
         const response=await fetch('/api/jd/enrich',{method:'POST',headers:{'Content-Type':'application/json'},
           signal:AbortSignal.timeout(30000),body:JSON.stringify({jobs:chunk,roles})});
         if(!response.ok)throw Error('Falha HTTP '+response.status);
         const data=await response.json();
         for(const j of data.items||[]){
           if(all.has(j.url))all.set(j.url,{...all.get(j.url),...j});
           if(uncertain.has(j.url))uncertain.set(j.url,{...uncertain.get(j.url),...j});
         }
         setResults([...all.values()]);setReviews([...uncertain.values()]);
       }catch(err){
         setScoringFailed(prev=>[...prev,...chunk.map(j=>j.url)]);
       }finally{
         setScoringAttempted(prev=>[...prev,...chunk.map(j=>j.url)]);
         setScoringNow([]);
         resolved+=chunk.length;setEvaluated(resolved);
       }
     }
   }
   await enrichAvailable();
   let offset=0;
   let skipped=0;
   for(let n=0;n<180;n++){
    let batch;try{batch=await requestJson('/api/catalog/scan?offset='+offset+'&limit=4&'+qs)}catch(err){skipped++;offset+=4;setMessage('Alguns quadros falharam; continuando os demais. Falhas: '+skipped);continue}
    (batch.items||[]).filter(j=>source==='all'||j.source?.toLowerCase()===source||(source==='greenhouse'&&j.source?.toLowerCase()==='greenhouse_eu')).forEach(j=>{const old=all.get(j.url);all.set(j.url,old?.ranking?.score!=null&&!j.ranking?.score?old:j)});record(batch);
    offset=batch.next_offset;if(!Number.isFinite(offset))throw Error('Paginação inválida');
    count+=batch.found||0;setResults([...all.values()]);await enrichAvailable();setChecked(x=>x+(batch.details||[]).length);setCounts({new:all.size,total:count});
    if(batch.complete){completedAll=true;break}
    if(!(batch.details||[]).length)break;
   }
   await enrichAvailable();
   setCompleted(completedAll);
   setMessage(completedAll&&!skipped?'Busca concluída.':'Busca parcialmente concluída: '+skipped+' lotes falharam. Confira Fontes.');
  }catch(e){setError(e.message);setMessage('Busca parcial — os resultados encontrados continuam disponíveis.')}
  finally{setBusy(false)}
 }
 const currentMatches=searchedQuery!==''&&searchedQuery===query();
 const sourceKey=v=>String(v||'').toLowerCase().replace(/[^a-z0-9]/g,'');
 const visibleReviews=(currentMatches?reviews:[]).filter(v=>(source==='all'||sourceKey(v.source)===sourceKey(source)||source==='greenhouse'&&sourceKey(v.source)==='greenhouseeu')&&(mode==='all'||!(v.needs_verification||[]).includes('modalidade'))&&(country==='GLOBAL'||!(v.needs_verification||[]).includes('pais')));
 const unknownModeCount=reviews.filter(v=>(v.needs_verification||[]).includes('modalidade')).length;
 const unknownCountryCount=reviews.filter(v=>(v.needs_verification||[]).includes('pais')).length;
 const combined=new Map();(currentMatches?results:[]).forEach(v=>combined.set(v.url,{...v,confirmed:true}));visibleReviews.forEach(v=>{if(!combined.has(v.url))combined.set(v.url,{...v,confirmed:false})});
 const scoreStatus=v=>{
   if(v.ranking?.score!==null&&v.ranking?.score!==undefined)return 'scored';
   if(scoringFailed.includes(v.url))return 'failed';
   if(scoringNow.includes(v.url))return 'calculating';
   if(busy && !scoringAttempted.includes(v.url) && (v.jd_status==='pendente' || (v.ranking?.score==null && ['greenhouse','inhire'].some(src=>v.source?.toLowerCase().includes(src)))))return 'waiting';
   return 'unscored';
 };
 const scoreDisplay=v=>{
   const state=scoreStatus(v);
   if(state==='scored')return <strong>{v.ranking.score}/100</strong>;
   if(state==='waiting'||state==='calculating')return <span role="status" style={{display:'inline-flex',alignItems:'center',gap:6}}><span aria-hidden="true" className="jh-score-spinner"/>{state==='calculating'?'Calculando nota…':'Aguardando avaliação'}</span>;
   return <strong>{state==='failed'?'Falha na avaliação':'Sem nota'}</strong>;
 };
 const scoreExplanation=v=>{
   const state=scoreStatus(v);
   if(state==='waiting'||state==='calculating')return 'Nota pendente — a busca ainda está em andamento';
   if(state==='failed')return 'O lote falhou; tente uma nova busca';
   if(state==='scored')return v.ranking?.confidence==='requisitos_extraidos'?'% dos requisitos extraídos':v.ranking?.confidence==='amostra_limitada'?'Amostra limitada — conferir JD':'Nota calculada';
   return v.ranking?.confidence==='cobertura_insuficiente'?'Cobertura insuficiente — avaliação concluída':'JD ou requisitos insuficientes — avaliação concluída';
 };
 const ordered=[...combined.values()].sort((a,b)=>{
   const date=v=>{const x=Date.parse(v.published||'');return Number.isFinite(x)?x:0};
   return sort==='score'?((b.ranking?.score??-1)-(a.ranking?.score??-1)||((b.ranking?.requirements?.length||0)-(a.ranking?.requirements?.length||0))||date(b)-date(a)):(sort==='newest'?date(b)-date(a):date(a)-date(b))
 });
 return <section className="history-pane">
  <div className="infra-title"><div><h3>Encontrar oportunidades</h3><p>Personalize sua busca. Os quadros são verificados automaticamente ao pesquisar.</p></div></div>
  <div className="jh-filters">
   <label className="jh-field jh-roles"><span>Quais vagas você procura?</span><textarea rows="3" value={roles} onChange={e=>setRoles(e.target.value)} maxLength={700} placeholder="Separe os cargos por vírgula"/></label>
   <label className="jh-field"><span>Fonte / site</span><select value={source} onChange={e=>changeSource(e.target.value)}>{sources.map(x=><option key={x.value} value={x.value}>{x.label}</option>)}</select></label>
   <label className="jh-field"><span>Publicadas nos últimos</span><select value={days} onChange={e=>setDays(e.target.value)}>{[['1','1 dia'],['3','3 dias'],['7','7 dias'],['15','15 dias'],['30','30 dias'],['60','60 dias'],['90','90 dias'],['0','Qualquer período']].map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
   <label className="jh-field"><span>Ordenar por</span><select value={sort} onChange={e=>setSort(e.target.value)}><option value="score">Maior nota primeiro</option><option value="newest">Mais recentes primeiro</option><option value="oldest">Mais antigas primeiro</option></select></label>
   <label className="jh-field"><span>País / Região</span><select value={country} onChange={e=>setCountry(e.target.value)}>{countries.map(c=><option key={c.value} value={c.value}>{c.label}</option>)}</select></label>
   <label className="jh-field"><span>Modalidade</span><select value={mode} onChange={e=>setMode(e.target.value)}><option value="remote">Remoto / Home office</option><option value="hybrid">Híbrido</option><option value="onsite">Presencial</option><option value="all">Todas as modalidades</option></select></label>
  </div>
  {busy&&<div role="status" className="notice"><p>Busca e avaliação em andamento: {checked} quadros consultados · {evaluated}/{evaluationTotal} JDs adicionais processados</p><progress value={evaluationTotal?evaluated:checked} max={evaluationTotal||Math.max(checked+4,1)} style={{width:"100%"}} /></div>}
  <button className="import-btn" disabled={busy||!roles.trim()} onClick={search}>{busy?'Pesquisando vagas e verificando quadros…':'Buscar oportunidades'}</button>
  {message&&<p className="notice" role="status">{message}{checked>0?' · Quadros verificados agora: '+checked:''}</p>}
  {error&&<p className="notice" role="alert">{error}</p>}
  {!currentMatches&&searchedQuery&&<p className="notice">Os filtros mudaram após a última pesquisa. Clique em Buscar oportunidades para atualizar os resultados.</p>}
  {currentMatches&&(results.length>0||reviews.length>0||completed)&&<><div className="history-stats"><span>Oportunidades identificadas: <b>{ordered.length}</b></span><span>Confirmadas: <b>{results.length}</b></span><span>Precisam de confirmação: <b>{visibleReviews.filter(v=>!results.some(r=>r.url===v.url)).length}</b></span><span>Anúncios analisados: <b>{rawScanned}</b></span><span>Quadros consultados: <b>{checked}</b></span>{mode!=='all'&&<span>Modalidade não comprovada (fora da lista): <b>{unknownModeCount}</b></span>}{country!=='GLOBAL'&&<span>País não comprovado (fora da lista): <b>{unknownCountryCount}</b></span>}</div>
  {ordered.length===0?<p>Nenhuma vaga correspondente foi identificada nos quadros consultados. Abra Fontes e Auditoria dos filtros para ver falhas e exclusões.</p>:
  <><p>Panorama de vagas relacionadas aos cargos selecionados. A marcação "A confirmar" significa que faltam provas de modalidade, país ou data — não é uma confirmação de elegibilidade.</p>
  <div className="table-wrap"><table><thead><tr><th>Nota / evidências</th><th>Cargo e situação</th><th>Empresa</th><th>Local informado</th><th>Data</th><th>Modalidade detectada</th><th>Fonte</th></tr></thead><tbody>{ordered.slice(0,visibleCount).map(v=><tr key={v.url}><td>{scoreDisplay(v)}<small style={{display:'block'}}>{scoreExplanation(v)}</small><details><summary>Como foi avaliada?</summary><p>{v.ranking?.reason||'Sem análise'}</p><small>Requisitos identificados: {v.ranking?.evaluated_requirements??0} · Obrigatórios: {v.ranking?.mandatory_count??0} · Desejáveis analisados: {v.ranking?.desirable_count??0} · Não comprovados: {v.ranking?.unverified_count??0} · Não interpretados: {v.ranking?.uninterpreted_count??0} · Cobertura: {v.ranking?.coverage_pct??0}%</small>{v.ranking?.requirements?.map((r,i)=><p key={i}><b>{r.type}: {r.name}</b> — {r.status==='comprovado'?'Comprovado':r.status==='nao_interpretado'?'Não interpretado':'Não comprovado'}{r.evidence?' · '+r.evidence:''}</p>)}<p>Prioridade (fora da nota): {v.ranking?.priority?.remote?'Remoto':'Modalidade não remota/indefinida'} · {v.ranking?.priority?.salary_informed?'Salário informado':'Salário não informado'} · Setor: {v.ranking?.priority?.sector||'não identificado'}</p></details></td><td><a href={v.url} target="_blank" rel="noopener noreferrer">{v.title}</a><small style={{display:'block',fontWeight:600,marginTop:4}}>{v.confirmed?'Confirmada':'A confirmar: '+(v.needs_verification||[]).join(', ')}</small>{v.jd_evidence?.family_evidence?.length>0&&<small style={{display:'block',opacity:.75}}>JD: {v.jd_evidence.family_evidence.flatMap(e=>e.evidence).slice(0,2).join(' / ')}</small>}</td><td>{v.company||'Não informada'}{v.already_known&&<small style={{display:'block',opacity:.65}}>Já conhecida</small>}</td><td>{v.location||'Não informada'}</td><td>{v.published?String(v.published).slice(0,10):'—'}</td><td>{({remote:'Remoto',hybrid:'Híbrido',onsite:'Presencial'})[v.detected_mode]||'Não identificada'}</td><td>{v.source||'—'}</td></tr>)}</tbody></table></div>{ordered.length>visibleCount&&<button type="button" className="import-btn" onClick={()=>setVisibleCount(v=>v+10)}>Mostrar mais 10 resultados ({Math.min(visibleCount,ordered.length)} de {ordered.length})</button>}</>}
  {(unknownModeCount>0||unknownCountryCount>0)&&<details className="catalog-diagnostics"><summary>Vagas não confirmadas pelos filtros ({reviews.filter(v=>(v.needs_verification||[]).includes('pais')||(v.needs_verification||[]).includes('modalidade')).length})</summary><p>Essas vagas não foram incluídas entre as elegíveis. País ou modalidade precisam ser comprovados.</p><div className="table-wrap"><table><thead><tr><th>Vaga</th><th>Fonte</th><th>Motivo</th><th>Nota</th></tr></thead><tbody>{reviews.filter(v=>(v.needs_verification||[]).includes('pais')||(v.needs_verification||[]).includes('modalidade')).map(v=><tr key={v.url}><td><a href={v.url} target="_blank" rel="noopener noreferrer">{v.title}</a></td><td>{v.source||'—'}</td><td>{(v.needs_verification||[]).join(', ')}</td><td>{scoreDisplay(v)}</td></tr>)}</tbody></table></div></details>}
  <details className="catalog-diagnostics"><summary>Fontes consultadas nesta busca</summary><div className="table-wrap"><table><thead><tr><th>Fonte</th><th>Consultas</th><th>Anúncios brutos</th><th>Pendências</th></tr></thead><tbody>{Object.entries(sourceStats).sort((a,b)=>b[1].recebidas-a[1].recebidas).map(([source,v])=><tr key={source}><td>{source}</td><td>{v.consultas}</td><td>{v.recebidas}</td><td>{v.erros}</td></tr>)}</tbody></table></div></details>
  <details className="catalog-diagnostics"><summary>Auditoria dos filtros</summary><p>Total bruto analisado: {rawScanned}. As exclusões são contadas por motivo, antes da deduplicação com o histórico.</p>{Object.entries(filterStats).map(([reason,n])=><p key={reason}>{reason}: <b>{n}</b></p>)}</details>
  </>}
 </section>
}
