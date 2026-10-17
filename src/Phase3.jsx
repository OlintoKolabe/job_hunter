import React,{useState} from 'react';
export function OpportunitiesPanel(){
 const [runAll,setRunAll]=useState(false),[coverage,setCoverage]=useState(null),[scanning,setScanning]=useState(false),[cursor,setCursor]=useState(0),[reports,setReports]=useState([]),[catalogJobs,setCatalogJobs]=useState([]),[busy,setBusy]=useState(false),[result,setResult]=useState(null),[error,setError]=useState('');
 async function uploadCatalog(e){const file=e.target.files?.[0];if(!file)return;setError('');try{const r=await fetch('/api/catalog/import',{method:'POST',headers:{'Content-Type':'application/json'},body:await file.arrayBuffer()});const d=await r.json();if(!r.ok)throw Error(d.detail||'Falha de importação');await loadCatalog();setError('Catálogo importado: '+d.imported+' identificadores reconhecidos.');}catch(err){setError(err.message)}e.target.value='';}
 async function loadCatalog(){try{const r=await fetch('/api/catalog');if(r.ok)setCoverage(await r.json())}catch(e){setError(String(e))}}
 React.useEffect(()=>{loadCatalog()},[]);
 async function scanAll(){
  if(scanning||runAll)return;
  setRunAll(true);setScanning(true);setError('');
  let offset=0,details=[],jobs=[],total=coverage?.total||0;
  try{
    while(offset<total){
      const r=await fetch('/api/catalog/scan?offset='+offset+'&limit=12',{method:'POST'});
      const d=await r.json();
      if(!r.ok)throw Error(d.detail||'Falha no lote '+offset);
      if(d.next_offset<=offset)throw Error('Varredura sem avanço');
      offset=d.next_offset;details=[...details,...d.details];jobs=[...jobs,...d.items];
      setCursor(offset);setReports(details);setCatalogJobs(jobs);
      if(d.complete)break;
    }
  }catch(err){setError(err.message+' — Pode retomar pelo próximo lote.')}
  finally{setScanning(false);setRunAll(false);}
 }
 async function scanCatalog(reset=false){setScanning(true);setError('');try{let offset=reset?0:cursor;let details=reset?[]:reports;let jobs=reset?[]:catalogJobs;const t=await fetch('/api/catalog/scan?offset='+offset+'&limit=12',{method:'POST'});const d=await t.json();if(!t.ok)throw Error(d.detail||'Erro na coleta');setCursor(d.next_offset);setReports([...details,...d.details]);setCatalogJobs([...jobs,...d.items]);}catch(e){setError(e.message)}finally{setScanning(false)}}
 async function search(){
  setBusy(true);setError('');
  try{
   const r=await fetch('/api/search-jobs',{method:'POST'});
   const d=await r.json();
   if(!r.ok)throw Error(d.detail||'Falha ao consultar as vagas');
   setResult(d);
  }catch(e){setError(e.message)}finally{setBusy(false)}
 }
 return <section className="history-pane"><div className="infra-title"><div><h3>Busca de oportunidades</h3><p>APIs públicas e catálogo ATS · coleta por lotes</p></div><button className="import-btn" onClick={search} disabled={busy}>{busy?'Consultando…':'Buscar vagas'}</button></div>
 <div className="infra-title" style={{marginTop:25}}><div><h3>Catálogo de empresas</h3><p>{coverage?coverage.total+' quadros catalogados · '+coverage.due+' para revisar':'Carregando inventário...'}</p></div><button className="import-btn" onClick={scanAll} disabled={scanning||!coverage}>Varrer todos os quadros</button><button className="import-btn" onClick={()=>scanCatalog(cursor===0)} disabled={scanning}>{scanning?'Consultando…':cursor===0?'Iniciar varredura':'Consultar próximo lote'}</button></div>
 <label className="import-btn" style={{marginBottom:12}}>Importar cadastro_empresas.json<input type="file" hidden accept=".json,application/json" onChange={uploadCatalog}/></label>
 <p>O catálogo original fica no Neon, não no repositório público. A importação acrescenta slugs e não elimina os conhecidos.</p><p>A coleta percorre lotes de até 12 quadros, registrando sucesso, ausência de vagas e falhas. Você pode iniciar a varredura de todos os quadros ou avançar lote a lote. A execução ocorre enquanto a aba permanece aberta.</p>
 {coverage&&<><div className="history-stats">{Object.entries(coverage.by_source).map(([source,count])=><span key={source}>{source}: <b>{count}</b></span>)}</div><p>Cadência: 3 dias (inHire, Quickin, Dynamite) · semanal (Ashby, Greenhouse, Lever, Gupy, LinkedIn) · quinzenal (Teamtailor) · mensal (demais). A verificação fica registrada no Neon.</p><details><summary>Estado de todos os quadros</summary><div className="table-wrap"><table><thead><tr><th>ATS</th><th>Slug</th><th>Estado real</th><th>Próxima revisão</th></tr></thead><tbody>{coverage.sources.map(x=><tr key={x.source+x.slug}><td>{x.source}</td><td>{x.slug}</td><td>{x.state}</td><td>{x.next_check?new Date(x.next_check).toLocaleDateString('pt-BR'):'Pendente'}</td></tr>)}</tbody></table></div></details><details><summary>Conectores MCP externos</summary>{Object.entries(coverage.mcp_status||{}).map(([name,status])=><p key={name}><b>{name}:</b> {status}</p>)}</details></>}
 {reports.length>0&&<><p className="notice">Verificados {cursor} de {coverage?.total||'?'} quadros · {catalogJobs.length} candidatas coletadas nos lotes (antes da triagem).</p>
 <div className="table-wrap"><table><thead><tr><th>ATS</th><th>Slug</th><th>Estado</th><th>Vagas coletadas</th></tr></thead><tbody>{reports.map((r,i)=><tr key={i}><td>{r.source}</td><td>{r.slug}</td><td>{r.state}</td><td>{r.received}{r.error?' — '+r.error:''}</td></tr>)}</tbody></table></div>
 <h3 style={{marginTop:24}}>Vagas encontradas pelo catálogo</h3><div className="table-wrap"><table><thead><tr><th>Empresa</th><th>Cargo</th><th>Origem</th></tr></thead><tbody>{catalogJobs.map((v,i)=><tr key={i}><td>{v.company}</td><td><a href={v.url} target="_blank" rel="noopener noreferrer">{v.title}</a></td><td>{v.source}</td></tr>)}</tbody></table></div></>}
 <p>Apenas coleta e deduplicação nesta entrega. O sistema ainda <strong>não valida o anúncio completo nem confirma elegibilidade remota</strong>.</p>
 {error&&<p role="alert" className="notice">{error}</p>}
 {result&&<><div className="history-stats"><span>Coletadas: <b>{result.total}</b></span><span>Inéditas: <b>{result.new}</b></span><span>Já conhecidas: <b>{result.duplicates}</b></span></div><p className="notice">{result.notice}</p>
 <div className="table-wrap"><table><thead><tr><th>Empresa</th><th>Vaga</th><th>Local informado</th><th>Origem</th></tr></thead><tbody>{result.items.map((v,i)=><tr key={v.url+i}><td>{v.company||'Não informada'}</td><td><a target="_blank" rel="noopener noreferrer" href={v.url}>{v.title}</a></td><td>{v.location||'Não informado'}</td><td>{v.source}</td></tr>)}</tbody></table></div>
 <h3 style={{marginTop:24}}>Diagnóstico de coleta</h3><div className="history-stats">{result.details.map(v=><span key={v.source+v.term}>{v.source} / {v.term}: <b>{v.status==='ok'?v.received+' registros':'Erro'}</b></span>)}</div>
 {result.details.filter(x=>x.status==='error').map(x=><p key={x.source+x.term} className="notice" role="alert">{x.source} / {x.term}: {x.detail}</p>)}
 </>}
 </section>
}
