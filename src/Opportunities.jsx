import React,{useState,useEffect} from 'react';
const defaultRoles='Product Manager, Product Owner, Project Manager, Gerente de Projetos, Product Marketing, Marketing, Growth, Business Analyst, Analista de Negócios, PMO';
const initialCountries=[{value:'LATAM',label:'América Latina'},{value:'BR',label:'Brasil'}];
export function OpportunitiesPanel(){
 const [source,setSource]=useState('all'),[sources,setSources]=useState([{value:'all',label:'Todas as fontes'},{value:'inhire',label:'inHire'},{value:'quickin',label:'Quickin'},{value:'gupy',label:'Gupy'}]),[roles,setRoles]=useState(defaultRoles),[days,setDays]=useState('30'),[country,setCountry]=useState('BR'),[countries,setCountries]=useState(initialCountries),[mode,setMode]=useState('remote'),[sort,setSort]=useState('newest');
 const [sourceStats,setSourceStats]=useState({}),[reviews,setReviews]=useState([]),[filterStats,setFilterStats]=useState({}),[rawScanned,setRawScanned]=useState(0),[busy,setBusy]=useState(false),[results,setResults]=useState([]),[message,setMessage]=useState(''),[error,setError]=useState(''),[checked,setChecked]=useState(0),[counts,setCounts]=useState({new:0,total:0}),[completed,setCompleted]=useState(false);
 useEffect(()=>{fetch('/api/search-filters').then(r=>r.ok?r.json():null).then(d=>{if(d?.countries)setCountries(d.countries);if(d?.sources)setSources(d.sources)}).catch(()=>{})},[]);
 const query=()=>new URLSearchParams({roles,country,mode,days,sort,source}).toString();
 const changeSource=value=>{setSource(value);setResults([]);setReviews([]);setChecked(0);setCompleted(false);setMessage("Fonte alterada. Clique em Buscar oportunidades para executar a nova seleção.");setError("");};
 async function search(){
  setBusy(true);setError('');setResults([]);setReviews([]);setSourceStats({});setFilterStats({});setRawScanned(0);setChecked(0);setCompleted(false);setMessage('Consultando '+(sources.find(x=>x.value===source)?.label||source)+'…');
  const qs=query();const all=new Map();const uncertain=new Map();const totals={};const sourceTotals={};let inspected=0;const record=(d)=>{(d.details||[]).forEach(x=>{const source=x.source||'desconhecida';const n=sourceTotals[source]||{consultas:0,recebidas:0,erros:0};n.consultas++;n.recebidas+=x.received||0;if(x.status==='error'||x.state==='pendente')n.erros++;sourceTotals[source]=n});setSourceStats({...sourceTotals});(d.review_items||[]).forEach(j=>uncertain.set(j.url,j));for(const [key,n] of Object.entries(d.filter_stats||{})){totals[key]=(totals[key]||0)+n}inspected+=d.raw_count||0;setReviews([...uncertain.values()]);setFilterStats({...totals});setRawScanned(inspected)};let count=0;let completedAll=false;
  try{
   const requestJson=async url=>{let problem;for(let retry=0;retry<2;retry++){try{const r=await fetch(url,{method:'POST'});const ct=r.headers.get('content-type')||'';if(!ct.includes('application/json'))throw Error('Servidor retornou HTML ('+r.status+'); lote não processado');const d=await r.json();if(!r.ok)throw Error(d.detail||'HTTP '+r.status);return d}catch(err){problem=err}}throw problem};
   const d=await requestJson('/api/search-jobs?'+qs);

   (d.items||[]).forEach(j=>all.set(j.url,j));record(d);count+=d.total||0;
   setResults([...all.values()]);setCounts({new:all.size,total:count});
   let offset=0;
   let skipped=0;
   for(let n=0;n<180;n++){
    let batch;try{batch=await requestJson('/api/catalog/scan?offset='+offset+'&limit=4&'+qs)}catch(err){skipped++;offset+=4;setMessage('Alguns quadros falharam; continuando os demais. Falhas: '+skipped);continue}
    (batch.items||[]).filter(j=>source==='all'||j.source?.toLowerCase()===source||(source==='greenhouse'&&j.source?.toLowerCase()==='greenhouse_eu')).forEach(j=>all.set(j.url,j));record(batch);
    offset=batch.next_offset;if(!Number.isFinite(offset))throw Error('Paginação inválida');
    count+=batch.found||0;setResults([...all.values()]);setChecked(x=>x+(batch.details||[]).length);setCounts({new:all.size,total:count});
    if(batch.complete){completedAll=true;break}
    if(!(batch.details||[]).length)break;
   }
   setCompleted(completedAll);
   setMessage(completedAll&&!skipped?'Busca concluída.':'Busca concluída parcialmente: '+skipped+' lotes falharam. Confira Fontes.');
  }catch(e){setError(e.message);setMessage('Busca parcial — os resultados encontrados continuam disponíveis.')}
  finally{setBusy(false)}
 }
 const ordered=[...results].sort((a,b)=>{
   const date=v=>{const x=Date.parse(v.published||'');return Number.isFinite(x)?x:0};
   return sort==='newest'?date(b)-date(a):date(a)-date(b)
 });
 return <section className="history-pane">
  <div className="infra-title"><div><h3>Encontrar oportunidades</h3><p>Personalize sua busca. Os quadros são verificados automaticamente ao pesquisar.</p></div></div>
  <div className="jh-filters">
   <label className="jh-field jh-roles"><span>Quais vagas você procura?</span><textarea rows="3" value={roles} onChange={e=>setRoles(e.target.value)} maxLength={700} placeholder="Separe os cargos por vírgula"/></label>
   <label className="jh-field"><span>Fonte / site</span><select value={source} onChange={e=>changeSource(e.target.value)}>{sources.map(x=><option key={x.value} value={x.value}>{x.label}</option>)}</select></label>
   <label className="jh-field"><span>Publicadas nos últimos</span><select value={days} onChange={e=>setDays(e.target.value)}>{[['1','1 dia'],['3','3 dias'],['7','7 dias'],['15','15 dias'],['30','30 dias'],['60','60 dias'],['90','90 dias'],['0','Qualquer período']].map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
   <label className="jh-field"><span>Ordenar por</span><select value={sort} onChange={e=>setSort(e.target.value)}><option value="newest">Mais recentes primeiro</option><option value="oldest">Mais antigas primeiro</option></select></label>
   <label className="jh-field"><span>País / Região</span><select value={country} onChange={e=>setCountry(e.target.value)}>{countries.map(c=><option key={c.value} value={c.value}>{c.label}</option>)}</select></label>
   <label className="jh-field"><span>Modalidade</span><select value={mode} onChange={e=>setMode(e.target.value)}><option value="remote">Remoto / Home office</option><option value="hybrid">Híbrido</option><option value="onsite">Presencial</option><option value="all">Todas as modalidades</option></select></label>
  </div>
  <button className="import-btn" disabled={busy||!roles.trim()} onClick={search}>{busy?'Pesquisando vagas e verificando quadros…':'Buscar oportunidades'}</button>
  {message&&<p className="notice" role="status">{message}{checked>0?' · Quadros verificados agora: '+checked:''}</p>}
  {error&&<p className="notice" role="alert">{error}</p>}
  {(results.length>0||reviews.length>0||completed)&&<><div className="history-stats"><span>Correspondências confirmadas: <b>{ordered.length}</b></span><span>Para conferir: <b>{reviews.length}</b></span><span>Anúncios analisados: <b>{rawScanned}</b></span><span>Consultas de quadros nesta busca: <b>{checked}</b></span></div>
  {ordered.length===0?<p>Nenhuma vaga com país, modalidade e data confirmados corresponde a estes filtros. Ajuste-os para ampliar a busca.</p>:
  <div className="table-wrap"><table><thead><tr><th>Cargo</th><th>Empresa</th><th>Local informado</th><th>Publicação</th><th>Fonte</th></tr></thead><tbody>{ordered.map(v=><tr key={v.url}><td><a href={v.url} target="_blank" rel="noopener noreferrer">{v.title}</a></td><td>{v.company||'Não informada'}{v.already_known&&<small style={{display:'block',opacity:.65}}>Já conhecida</small>}</td><td>{v.location||'Não informada'}</td><td>{v.published?String(v.published).slice(0,10):'—'}</td><td>{v.source}</td></tr>)}</tbody></table></div>}
  {reviews.length>0&&<details open className="catalog-diagnostics"><summary>{reviews.length} vagas potencialmente relevantes — precisam de confirmação</summary><p>Estas vagas passaram pelo filtro de cargos, mas o ATS não trouxe evidência suficiente de país, modalidade ou data. Confira cada anúncio; elas não são confirmadas.</p><div className="table-wrap"><table><thead><tr><th>Vaga</th><th>Empresa</th><th>Local informado</th><th>Falta verificar</th></tr></thead><tbody>{reviews.map(v=><tr key={v.url}><td><a href={v.url} target="_blank" rel="noopener noreferrer">{v.title}</a></td><td>{v.company||'—'}</td><td>{v.location||'—'}</td><td>{(v.needs_verification||[]).join(', ')}</td></tr>)}</tbody></table></div></details>}
  <details className="catalog-diagnostics"><summary>Fontes consultadas nesta busca</summary><div className="table-wrap"><table><thead><tr><th>Fonte</th><th>Consultas</th><th>Anúncios brutos</th><th>Pendências</th></tr></thead><tbody>{Object.entries(sourceStats).sort((a,b)=>b[1].recebidas-a[1].recebidas).map(([source,v])=><tr key={source}><td>{source}</td><td>{v.consultas}</td><td>{v.recebidas}</td><td>{v.erros}</td></tr>)}</tbody></table></div></details>
  <details className="catalog-diagnostics"><summary>Auditoria dos filtros</summary><p>Total bruto analisado: {rawScanned}. As exclusões são contadas por motivo, antes da deduplicação com o histórico.</p>{Object.entries(filterStats).map(([reason,n])=><p key={reason}>{reason}: <b>{n}</b></p>)}</details>
  </>}
 </section>
}
