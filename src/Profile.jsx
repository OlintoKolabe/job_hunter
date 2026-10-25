import React,{useState} from 'react';
import {UserRound,BriefcaseBusiness,GraduationCap,CheckCircle2,Plus,Trash2,Save,ShieldCheck,FileUp,FileText,AlertCircle} from 'lucide-react';

const emptyExperience=()=>({role:'',company:'',dates:'',facts:[],verified:false});
const parseList=value=>value.split(/\n|,/).map(s=>s.trim()).filter(Boolean);
export function ProfilePanel({profile,onSaved}){
 const [form,setForm]=useState(structuredClone(profile));
 const [listDrafts,setListDrafts]=useState(Object.fromEntries(['roles','skills','education','certifications','languages'].map(k=>[k,(profile[k]||[]).join('\n')])));
 const [factDrafts,setFactDrafts]=useState((profile.experience||[]).map(e=>(e.facts||[]).join('\n')));
 const [notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
 const [importPreview,setImportPreview]=useState(null),[accepted,setAccepted]=useState(false),[importing,setImporting]=useState(false);
 const update=(key,value)=>setForm(p=>({...p,[key]:value}));
 const updateExperience=(index,key,value)=>setForm(p=>({...p,experience:p.experience.map((e,i)=>i===index?{...e,[key]:value}:e)}));
 async function importPdf(event){
  const file=event.target.files?.[0];if(!file)return;
  setNotice('');setImportPreview(null);setAccepted(false);
  if(file.type!=='application/pdf'&&!file.name.toLowerCase().endsWith('.pdf')){setNotice('Escolha o PDF exportado pelo LinkedIn.');return}
  if(file.size>8*1024*1024){setNotice('O arquivo não pode ultrapassar 8 MB.');return}
  setImporting(true);
  try{
   const response=await fetch('/api/profile/import-linkedin',{method:'POST',headers:{'Content-Type':'application/pdf'},body:file});
   const parsed=await response.json();if(!response.ok)throw Error(parsed.detail||'Não foi possível ler o PDF');
   const next={...form};
   for(const [key,value] of Object.entries(parsed.profile)){
    if((Array.isArray(value)&&value.length)||(typeof value==='string'&&value.trim()))next[key]=value;
   }
   setForm(next);
   setListDrafts(v=>({...v,...Object.fromEntries(['roles','skills','education','certifications','languages'].map(k=>[k,(next[k]||[]).join('\n')]))}));
   setFactDrafts((next.experience||[]).map(e=>(e.facts||[]).join('\n')));
   setImportPreview({fileName:file.name,pages:parsed.pages,warnings:parsed.warnings||[],sections:parsed.extracted_sections||[]});
   setNotice('PDF lido. Confira o resultado e confirme o currículo mestre abaixo.');
  }catch(error){setNotice(error.message)}finally{setImporting(false);event.target.value=''}
 }
 async function save(e){
  e.preventDefault();setBusy(true);setNotice('');
  try{
   if(importPreview&&!accepted)throw Error('Confirme que conferiu os dados importados antes de salvar.');
   const dataToSave={...form,...Object.fromEntries(Object.entries(listDrafts).map(([k,v])=>[k,parseList(v)])),
    experience:form.experience.map((e,i)=>({...e,verified:importPreview?accepted:e.verified,facts:parseList(factDrafts[i]||'')}))};
   const response=await fetch('/api/profile',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile:dataToSave})});
   const data=await response.json();if(!response.ok)throw Error(data.detail||'Falha ao salvar');
   setForm(data.profile);setImportPreview(null);setAccepted(false);onSaved(data.profile);setNotice('Currículo mestre salvo. O Caçador já pode utilizar as evidências confirmadas nas análises e nos currículos ATS.');
  }catch(error){setNotice(error.message)}finally{setBusy(false)}
 }
 const fields=[['name','Nome completo'],['location','Cidade / país'],['phone','Telefone'],['linkedin','LinkedIn']];
 const listFields=[['roles','Cargos que deseja buscar (um por linha)'],['skills','Competências'],['education','Formação acadêmica'],['certifications','Certificações'],['languages','Idiomas']];
 return <form className="profile-page" onSubmit={save}>
  <div className="profile-intro"><div><div className="eyebrow">PERFIL PROFISSIONAL PRIVADO</div><h2>Seu currículo mestre</h2><p>Importe o PDF do LinkedIn. O Caçador preenche os dados e você apenas confere antes de confirmar.</p></div><ShieldCheck size={35}/></div>
  <section className="linkedin-upload-card">
   <div className="linkedin-upload-heading"><div className="linkedin-upload-icon"><FileUp size={27}/></div><div><h3>Importar currículo do LinkedIn</h3><p>Abra seu perfil no LinkedIn, escolha <b>Mais → Salvar em PDF</b> e envie o arquivo aqui.</p></div></div>
   <label className="linkedin-upload-button"><FileText size={17}/>{importing?'Lendo PDF…':'Selecionar PDF do LinkedIn'}<input type="file" accept=".pdf,application/pdf" disabled={importing||busy} onChange={importPdf}/></label>
   <span className="linkedin-upload-hint">Até 8 MB · leitura privada no servidor · não envia dados para outra IA</span>
   {importPreview&&<div className="linkedin-import-result"><CheckCircle2 size={20}/><div><b>{importPreview.fileName}</b><p>{importPreview.pages} página(s) lida(s) · {(form.experience||[]).length} experiência(s) identificada(s) · {(form.education||[]).length} item(ns) de formação</p></div></div>}
   {importPreview?.warnings?.length>0&&<div className="linkedin-import-warnings"><AlertCircle size={19}/><div>{importPreview.warnings.map((w,i)=><p key={i}>{w}</p>)}</div></div>}
  </section>
  <details className="profile-manual-details" key={importPreview?'imported':'manual'} open={!!importPreview}>
   <summary>{importPreview?'Conferir e corrigir os dados extraídos':'Ver ou editar os dados do currículo mestre'} <span>{importPreview?'Revise antes de salvar':'Opcional'}</span></summary>
   <div className="profile-manual-content">
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
   </div>
  </details>
  {importPreview&&<label className="linkedin-confirm"><input type="checkbox" checked={accepted} onChange={e=>setAccepted(e.target.checked)}/><span>Conferi as informações extraídas do PDF e confirmo que são verdadeiras e podem ser usadas como evidências profissionais no Caçador.</span></label>}
  <div className="profile-save"><button disabled={busy||importing||(importPreview&&!accepted)} type="submit"><Save size={18}/>{busy?'Salvando…':importPreview?'Confirmar currículo mestre':'Salvar meu perfil'}</button>{notice&&<span role="status">{notice}</span>}</div>
 </form>
}
