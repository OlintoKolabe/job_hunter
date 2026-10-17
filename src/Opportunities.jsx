import React,{useState,useEffect} from 'react';
const defaultRoles='Product Manager, Product Owner, Project Manager, Gerente de Projetos, Product Marketing, Marketing, Growth, Business Analyst, Analista de Negócios, PMO';
const initialCountries=[{value:'LATAM',label:'América Latina'},{value:'BR',label:'Brasil'}];
export function OpportunitiesPanel(){
 const [roles,setRoles]=useState(defaultRoles),[days,setDays]=useState('30'),[country,setCountry]=useState('BR'),[countries,setCountries]=useState(initialCountries),[mode,setMode]=useState('remote'),[sort,setSort]=useState('newest');
 const [busy,setBusy]=useState(false),[results,setResults]=useState([]),[message,setMessage]=useState(''),[error,setError]=useState(''),[checked,setChecked]=useState(0),[counts,setCounts]=useState({new:0,total:0}),[completed,setCompleted]=useState(false);
 useEffect(()=>{fetch('/api/search-filters').then(r=>r.ok?r.json():null).then(d=>{if(d?.countries)setCountries(d.countries)}).catch(()=>{})},[]);
 const query=()=>new URLSearchParams({roles,country,mode,days,sort}).toString();
 async function search(){
  setBusy(true);setError('');setResults([]);setChecked(0);setCompleted(false);setMessage('Consultando fontes e quadros…');
  const qs=query();const all=new Map();let count=0;let completedAll=false;
  try{
   const r=await fetch('/api/search-jobs?'+qs,{method:'POST'});const d=await r.json();
   if(!r.ok)throw Error(d.detail||'Falha nas fontes gerais');
   (d.items||[]).forEach(j=>all.set(j.url,j));count+=d.total||0;
   setResults([...all.values()]);setCounts({new:all.size,total:count});
   for(let n=0;n<45;n++){
    const v=await fetch('/api/catalog/scan?offset=0&limit=12&due_only=true&'+qs,{method:'POST'});
    const batch=await v.json();if(!v.ok)throw Error(batch.detail||'Falha na consulta aos quadros');
    (batch.items||[]).forEach(j=>all.set(j.url,j));
    count+=batch.found||0;setResults([...all.values()]);setChecked(x=>x+(batch.details||[]).length);setCounts({new:all.size,total:count});
    if(batch.complete){completedAll=true;break}
    if(!(batch.details||[]).length)break;
   }
   setCompleted(completedAll);
   setMessage(completedAll?'Busca concluída. Mostradas apenas vagas com evidência suficiente para os filtros selecionados.':'Busca parcial. Consulte Fontes para verificar quadros pendentes.');
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
   <label className="jh-field"><span>Publicadas nos últimos</span><select value={days} onChange={e=>setDays(e.target.value)}>{[['1','1 dia'],['3','3 dias'],['7','7 dias'],['15','15 dias'],['30','30 dias'],['60','60 dias'],['90','90 dias'],['0','Qualquer período']].map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
   <label className="jh-field"><span>Ordenar por</span><select value={sort} onChange={e=>setSort(e.target.value)}><option value="newest">Mais recentes primeiro</option><option value="oldest">Mais antigas primeiro</option></select></label>
   <label className="jh-field"><span>País / Região</span><select value={country} onChange={e=>setCountry(e.target.value)}>{countries.map(c=><option key={c.value} value={c.value}>{c.label}</option>)}</select></label>
   <label className="jh-field"><span>Modalidade</span><select value={mode} onChange={e=>setMode(e.target.value)}><option value="remote">Remoto / Home office</option><option value="hybrid">Híbrido</option><option value="onsite">Presencial</option><option value="all">Todas as modalidades</option></select></label>
  </div>
  <button className="import-btn" disabled={busy||!roles.trim()} onClick={search}>{busy?'Pesquisando vagas e verificando quadros…':'Buscar oportunidades'}</button>
  {message&&<p className="notice" role="status">{message}{checked>0?' · Quadros verificados agora: '+checked:''}</p>}
  {error&&<p className="notice" role="alert">{error}</p>}
  {(results.length>0||completed)&&<><div className="history-stats"><span>Oportunidades exibidas: <b>{ordered.length}</b></span><span>Consultas de quadros nesta busca: <b>{checked}</b></span></div>
  {ordered.length===0?<p>Nenhuma vaga com país, modalidade e data confirmados corresponde a estes filtros. Ajuste-os para ampliar a busca.</p>:
  <div className="table-wrap"><table><thead><tr><th>Cargo</th><th>Empresa</th><th>Local informado</th><th>Publicação</th><th>Fonte</th></tr></thead><tbody>{ordered.map(v=><tr key={v.url}><td><a href={v.url} target="_blank" rel="noopener noreferrer">{v.title}</a></td><td>{v.company||'Não informada'}</td><td>{v.location||'Não informada'}</td><td>{v.published?String(v.published).slice(0,10):'—'}</td><td>{v.source}</td></tr>)}</tbody></table></div>}
  </>}
 </section>
}
