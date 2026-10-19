import React,{useState,useEffect} from 'react';
export function HistoryPanel(){
 const today=()=>{const d=new Date();return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-')};
 const [data,setData]=useState({total:0,items:[]}),[stats,setStats]=useState({total:0,states:{}}),[daily,setDaily]=useState({days:[],candidatado:0,descartado:0});
 const [q,setQ]=useState(''),[state,setState]=useState(''),[page,setPage]=useState(0),[notice,setNotice]=useState('');
 const [period,setPeriod]=useState('all'),[start,setStart]=useState(today()),[end,setEnd]=useState(today()),[oneDay,setOneDay]=useState(today()),[candidateDay,setCandidateDay]=useState(today()),[chosen,setChosen]=useState([]);
 function dateParams(){
  const p=new URLSearchParams();
  if(period==='single'){p.set('from_date',oneDay);p.set('to_date',oneDay)}
  if(period==='range'){p.set('from_date',start);p.set('to_date',end)}
  if(period==='multiple'&&chosen.length)p.set('dates',[...chosen].sort().join(','));
  return p;
 }
 async function reload(){
  try{
   const periodQuery=dateParams();const p=new URLSearchParams(periodQuery);
   p.set('q',q);p.set('state',state);p.set('limit','50');p.set('offset',String(page*50));
   const [records,summary,globalStats]=await Promise.all([
    fetch('/api/history?'+p,{cache:'no-store'}),
    fetch('/api/history-daily?'+periodQuery,{cache:'no-store'}),
    fetch('/api/history-stats',{cache:'no-store'})]);
   if(!records.ok||!summary.ok||!globalStats.ok)throw Error('Não foi possível consultar o Histórico');
   const [r,s,t]=await Promise.all([records.json(),summary.json(),globalStats.json()]);
   setData(r);setDaily(s);setStats(t);setNotice('');
  }catch(e){setNotice(e.message||'Erro de conexão')}
 }
 useEffect(()=>{reload()},[q,state,page,period,start,end,oneDay,chosen.join(',')]);
 async function upload(e){let f=e.target.files?.[0];if(!f)return;setNotice('Importando...');try{let r=await fetch('/api/history-import',{method:'POST',headers:{'Content-Type':'text/csv'},body:await f.arrayBuffer()});let d=await r.json();if(!r.ok)throw Error(d.detail||'Erro na importação');setNotice('Importadas: '+d.inserted+' · Duplicadas: '+d.duplicates+' · Inválidas: '+d.invalid);await reload()}catch(e){setNotice(e.message)}e.target.value=''}
 const displayDay=d=>d?d.split('-').reverse().join('/'):'—';
 const choosePeriod=p=>{setPage(0);setPeriod(p)};
 return <section className="history-pane">
  <div className="infra-title"><h3>Seu histórico · {stats.total.toLocaleString('pt-BR')} vagas</h3><label className="import-btn">Importar CSV<input type="file" hidden accept=".csv,text/csv" onChange={upload}/></label></div>
  <p>Veja candidaturas e descartes por dia ou período. Registros antigos e atuais são contados juntos, sem alterar o banco.</p>
  <div className="history-stats"><span>Total histórico: <b>{stats.total}</b></span><span>Candidatado: <b>{(stats.states.Candidatado||0)+(stats.states.candidatado||0)}</b></span><span>Descartado: <b>{(stats.states.Descartado||0)+(stats.states.descartada||0)+(stats.states.descartado||0)}</b></span></div>
  <div className="filters">
   <label>Período <select value={period} onChange={e=>choosePeriod(e.target.value)}><option value="all">Todos os dias</option><option value="single">Um dia</option><option value="range">Faixa de dias</option><option value="multiple">Dias selecionados</option></select></label>
   {period==='single'&&<label>Dia <input type="date" value={oneDay} onChange={e=>{setPage(0);setOneDay(e.target.value)}}/></label>}
   {period==='range'&&<><label>De <input type="date" value={start} onChange={e=>{setPage(0);setStart(e.target.value)}}/></label><label>Até <input type="date" value={end} min={start} onChange={e=>{setPage(0);setEnd(e.target.value)}}/></label></>}
   {period==='multiple'&&<div><label>Adicionar dia <input type="date" value={candidateDay} onChange={e=>setCandidateDay(e.target.value)}/></label><button type="button" onClick={()=>{if(candidateDay){setChosen(v=>[...new Set([...v,candidateDay])]);setPage(0)}}}>Adicionar</button><div>{chosen.slice().sort().map(d=><button type="button" key={d} title="Remover dia" onClick={()=>{setChosen(v=>v.filter(x=>x!==d));setPage(0)}}>{displayDay(d)} ×</button>)}</div></div>}
  </div>
  {period==='multiple'&&!chosen.length&&<p className="notice">Adicione pelo menos um dia para consultar um conjunto específico. Sem dias selecionados, a visão permanece geral.</p>}
  {notice&&<p role="status" className="notice">{notice}</p>}
  <h4>Resumo do período</h4>
  <div className="history-stats"><span>Candidatado: <b>{daily.candidatado}</b></span><span>Descartado: <b>{daily.descartado}</b></span><span>Total de decisões: <b>{daily.candidatado+daily.descartado}</b></span></div>
  <div className="table-wrap"><table><thead><tr><th>Dia</th><th>Candidatado</th><th>Descartado</th><th>Total</th><th>Ver vagas</th></tr></thead><tbody>{daily.days.map(d=><tr key={d.day}><td>{displayDay(d.day)}</td><td>{d.candidatado}</td><td>{d.descartado}</td><td>{d.candidatado+d.descartado}</td><td><button type="button" onClick={()=>{setOneDay(d.day);setPage(0);setPeriod('single');setState('')}}>Ver dia</button></td></tr>)}{!daily.days.length&&<tr><td colSpan="5">Nenhuma decisão encontrada neste período.</td></tr>}</tbody></table></div>
  <h4>Vagas do período</h4>
  <div className="filters"><input placeholder="Pesquisar empresa ou cargo" value={q} onChange={e=>{setPage(0);setQ(e.target.value)}}/><select value={state} onChange={e=>{setPage(0);setState(e.target.value)}}><option value="">Todos os estados</option><option value="Candidatado">Candidatado</option><option value="Descartado">Descartado</option><option value="triada">Triada</option><option value="encerrada">Encerrada</option></select></div>
  <div className="table-wrap"><table><thead><tr><th>Data</th><th>Empresa</th><th>Cargo</th><th>Estado</th><th>Vaga</th></tr></thead><tbody>{data.items.map(v=><tr key={v.id}><td>{/^\\d{4}-/.test(v.data)?displayDay(v.data):v.data||'—'}</td><td>{v.empresa}</td><td>{v.cargo}</td><td>{v.estado}</td><td>{/^https?:\\/\\//i.test(v.url)?<a href={v.url} target="_blank" rel="noopener noreferrer">Abrir</a>:'—'}</td></tr>)}</tbody></table></div>
  <div className="pager"><span>{data.total} resultados</span><button disabled={page===0} onClick={()=>setPage(page-1)}>Anterior</button><button disabled={(page+1)*50>=data.total} onClick={()=>setPage(page+1)}>Próxima</button></div>
 </section>
}
export function SecurityPanel(){
 const [current,setCurrent]=useState(''),[next,setNext]=useState(''),[confirm,setConfirm]=useState(''),[message,setMessage]=useState('');
 async function submit(e){e.preventDefault();if(next!==confirm){setMessage('As novas senhas não conferem');return}try{let r=await fetch('/api/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_password:current,new_password:next})});let d=await r.json();if(!r.ok)throw Error(d.detail||'Erro ao alterar');setMessage('Senha alterada com sucesso. Sessões anteriores invalidadas.');setCurrent('');setNext('');setConfirm('')}catch(e){setMessage(e.message)}}
 return <section className="history-pane"><h3>Alterar senha</h3><p>A nova senha deve ter entre 12 e 128 caracteres. Ela é salva como hash no banco Neon.</p><form className="password-form" onSubmit={submit}><label>Senha atual<input type="password" required autoComplete="current-password" value={current} onChange={e=>setCurrent(e.target.value)}/></label><label>Nova senha<input type="password" required autoComplete="new-password" minLength="12" value={next} onChange={e=>setNext(e.target.value)}/></label><label>Confirmar nova senha<input type="password" required autoComplete="new-password" minLength="12" value={confirm} onChange={e=>setConfirm(e.target.value)}/></label><button>Salvar nova senha</button></form>{message&&<p role="status" className="notice">{message}</p>}</section>
}
