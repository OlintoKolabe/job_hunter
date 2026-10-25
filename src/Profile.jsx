import React,{useState} from 'react';
import {UserRound,BriefcaseBusiness,GraduationCap,CheckCircle2,Plus,Trash2,Save,ShieldCheck} from 'lucide-react';

const emptyExperience=()=>({role:'',company:'',dates:'',facts:[],verified:false});
const parseList=value=>value.split(/\n|,/).map(s=>s.trim()).filter(Boolean);
export function ProfilePanel({profile,onSaved}){
 const [form,setForm]=useState(structuredClone(profile));
 const [listDrafts,setListDrafts]=useState(Object.fromEntries(['roles','skills','education','certifications','languages'].map(k=>[k,(profile[k]||[]).join('\n')])));
 const [factDrafts,setFactDrafts]=useState((profile.experience||[]).map(e=>(e.facts||[]).join('\n')));
 const [notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
 const update=(key,value)=>setForm(p=>({...p,[key]:value}));
 const updateExperience=(index,key,value)=>setForm(p=>({...p,experience:p.experience.map((e,i)=>i===index?{...e,[key]:value}:e)}));
 async function save(e){
  e.preventDefault();setBusy(true);setNotice('');
  try{
   const dataToSave={...form,...Object.fromEntries(Object.entries(listDrafts).map(([k,v])=>[k,parseList(v)])),
    experience:form.experience.map((e,i)=>({...e,facts:parseList(factDrafts[i]||'')}))};
   const response=await fetch('/api/profile',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile:dataToSave})});
   const data=await response.json();if(!response.ok)throw Error(data.detail||'Falha ao salvar');
   setForm(data.profile);onSaved(data.profile);setNotice('Perfil salvo. A próxima busca utilizará suas preferências e evidências verificadas.');
  }catch(error){setNotice(error.message)}finally{setBusy(false)}
 }
 const fields=[['name','Nome completo'],['location','Cidade / país'],['phone','Telefone'],['linkedin','LinkedIn']];
 const listFields=[['roles','Cargos que deseja buscar (um por linha)'],['skills','Competências'],['education','Formação acadêmica'],['certifications','Certificações'],['languages','Idiomas']];
 return <form className="profile-page" onSubmit={save}>
  <div className="profile-intro"><div><div className="eyebrow">PERFIL PROFISSIONAL PRIVADO</div><h2>Seu currículo mestre</h2><p>Cadastre apenas informações verdadeiras. Experiências assinaladas como verificadas serão as únicas usadas na avaliação por IA e nos currículos ATS.</p></div><ShieldCheck size={35}/></div>
  <section className="profile-card"><h3><UserRound/> Informações pessoais</h3><div className="profile-grid">
    {fields.map(([key,label])=><label key={key}>{label}<input value={form[key]||''} onChange={e=>update(key,e.target.value)}/></label>)}
    <label className="profile-wide">Resumo profissional<textarea rows="4" value={form.summary||''} onChange={e=>update('summary',e.target.value)} placeholder="Síntese factual de sua atuação profissional"/></label>
  </div></section>
  <section className="profile-card"><h3><BriefcaseBusiness/> Experiências e realizações</h3><p>Escreva cada realização em uma linha. Marque como verificada apenas quando você puder sustentá-la por currículo, portfólio ou documentação profissional.</p>
    {(form.experience||[]).map((item,i)=><div className="experience-edit" key={i}>
      <div className="experience-head"><b>Experiência {i+1}</b><button type="button" title="Remover experiência" onClick={()=>{setForm(p=>({...p,experience:p.experience.filter((_,j)=>i!==j)}));setFactDrafts(v=>v.filter((_,j)=>i!==j))}}><Trash2 size={16}/></button></div>
      <div className="profile-grid">
        <label>Cargo<input value={item.role} onChange={e=>updateExperience(i,'role',e.target.value)}/></label>
        <label>Empresa<input value={item.company} onChange={e=>updateExperience(i,'company',e.target.value)}/></label>
        <label className="profile-wide">Período<input value={item.dates} placeholder="jan 2023 – dez 2025" onChange={e=>updateExperience(i,'dates',e.target.value)}/></label>
        <label className="profile-wide">Responsabilidades e realizações comprováveis<textarea rows="4" value={factDrafts[i]||''} onChange={e=>setFactDrafts(v=>v.map((x,j)=>i===j?e.target.value:x))}/></label>
      </div>
      <label className="verified-check"><input type="checkbox" checked={item.verified===true} onChange={e=>updateExperience(i,'verified',e.target.checked)}/><CheckCircle2 size={17}/> Declaro que estas informações são verdadeiras e verificáveis</label>
    </div>)}
    <button className="profile-secondary" type="button" onClick={()=>{setForm(p=>({...p,experience:[...(p.experience||[]),emptyExperience()]}));setFactDrafts(v=>[...v,''])}}><Plus size={16}/> Adicionar experiência</button>
  </section>
  <section className="profile-card"><h3><GraduationCap/> Formação, competências e cargos</h3><div className="profile-grid">
   {listFields.map(([key,label])=><label key={key}>{label}<textarea rows="4" value={listDrafts[key]||''} onChange={e=>setListDrafts(v=>({...v,[key]:e.target.value}))} placeholder="Um item por linha"/></label>)}
  </div></section>
  <section className="profile-card"><h3>Preferências da busca</h3><div className="profile-grid">
   <label>País ou região<select value={form.country||'BR'} onChange={e=>update('country',e.target.value)}><option value="BR">Brasil</option><option value="LATAM">América Latina</option><option value="GLOBAL">Global</option></select></label>
   <label>Modalidade<select value={form.mode||'remote'} onChange={e=>update('mode',e.target.value)}><option value="remote">Remoto</option><option value="hybrid">Híbrido</option><option value="onsite">Presencial</option><option value="all">Todas</option></select></label>
   <label>Senioridade<input value={form.seniority||''} onChange={e=>update('seniority',e.target.value)} placeholder="Estágio, Júnior, Pleno, Sênior…"/></label>
   <label>Período<select value={String(form.days??7)} onChange={e=>update('days',Number(e.target.value))}>{[1,3,7,15,30,60,90,0].map(v=><option key={v} value={v}>{v?v+' dias':'Qualquer período'}</option>)}</select></label>
  </div></section>
  <div className="profile-save"><button disabled={busy} type="submit"><Save size={18}/>{busy?'Salvando…':'Salvar meu perfil'}</button>{notice&&<span role="status">{notice}</span>}</div>
 </form>
}
