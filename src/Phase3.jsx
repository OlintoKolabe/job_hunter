import React,{useState} from 'react';
export function OpportunitiesPanel(){
 const [busy,setBusy]=useState(false),[result,setResult]=useState(null),[error,setError]=useState('');
 async function search(){
  setBusy(true);setError('');
  try{
   const r=await fetch('/api/search-jobs',{method:'POST'});
   const d=await r.json();
   if(!r.ok)throw Error(d.detail||'Falha ao consultar as vagas');
   setResult(d);
  }catch(e){setError(e.message)}finally{setBusy(false)}
 }
 return <section className="history-pane"><div className="infra-title"><div><h3>Busca de oportunidades</h3><p>Jobgether · cinco termos · ordenação por data · Brasil</p></div><button className="import-btn" onClick={search} disabled={busy}>{busy?'Consultando…':'Buscar vagas'}</button></div>
 <p>Apenas coleta e deduplicação nesta entrega. O sistema ainda <strong>não valida o anúncio completo nem confirma elegibilidade remota</strong>.</p>
 {error&&<p role="alert" className="notice">{error}</p>}
 {result&&<><div className="history-stats"><span>Coletadas: <b>{result.total}</b></span><span>Inéditas: <b>{result.new}</b></span><span>Já conhecidas: <b>{result.duplicates}</b></span></div><p className="notice">{result.notice}</p>
 <div className="table-wrap"><table><thead><tr><th>Empresa</th><th>Vaga</th><th>Local informado</th><th>Origem</th></tr></thead><tbody>{result.items.map((v,i)=><tr key={v.url+i}><td>{v.company||'Não informada'}</td><td><a target="_blank" rel="noopener noreferrer" href={v.url}>{v.title}</a></td><td>{v.location||'Não informado'}</td><td>{v.source}</td></tr>)}</tbody></table></div>
 <h3 style={{marginTop:24}}>Diagnóstico de coleta</h3><div className="history-stats">{result.details.map(v=><span key={v.term}>{v.term}: <b>{v.status==='ok'?v.received+' registros':'Erro'}</b></span>)}</div>
 {result.details.filter(x=>x.status==='error').map(x=><p key={x.term} className="notice" role="alert">{x.term}: {x.detail}</p>)}
 </>}
 </section>
}
