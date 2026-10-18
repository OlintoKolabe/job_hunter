"""Block 4: deterministic, evidence-led ranking. No external model/API calls.
Priority score follows Caçador v2 (fit 40, management 15, remote 20,
salary bonus 10, strongest domain bonus 16), bounded to 97.
A priority score is NOT confirmed professional eligibility.
"""
import re
from search_filters import fold,detect_work_mode,requested_families,search_terms
from jd_signals import signals,clean_jd

# Documented professional evidence from Profile (11).pdf (Oct 2026).
# No unverified qualifications may be inferred from this table.
PROFILE={
 "product":("Hexagon Mining — Mission Manager product/backlog/roadmap",
            "Dotz — Meu Varejo product ownership and CRM",
            "Neocoder/LiberPay — product strategy, roadmaps, retention"),
 "projects":("Neocoder — Head de projetos e processos, PMO, Scrum/Kanban",
             "Kolabe — product delivery, technology project budgets"),
 "marketing":("Lagoa Parques — diretor de marketing, receita triplicada",
              "Grupo Privé — gerente corporativo de marketing",
              "Digital Design — CEO, branding e campanhas"),
 "growth":("Kolabe — Growth Hacking, métricas, Google Ads, SEO",
           "Neocoder/LiberPay — experimentos growth, ativação e retenção"),
 "business":("Lagoa — desenvolvimento corporativo, estratégia e processos",
             "Top Saúde — CEO, plano de negócios, operações e indicadores"),
}
AXES=(
 ("saude",12,("healthcare","health care","clinical","clinica","hospital","saude","healthtech")),
 ("mineracao",12,("mining","mineracao","mineração","autonomous mining")),
 ("loyalty",11,("loyalty","fidelidade","retail","varejo","crm")),
 ("marketing",11,("marketing","advertising","branding","growth")),
 ("pagamentos",8,("payments","pagamentos","fintech","payment processing")),
 ("web3",6,("web3","blockchain","crypto")),
)
FAMILY_TERMS={
 "product":("product","produto","backlog","roadmap","discovery","product owner"),
 "projects":("project","projeto","program management","delivery","pmo","transformation"),
 "marketing":("marketing","branding","demand generation","go to market","crm"),
 "growth":("growth","acquisition","retention","conversion","experimentation"),
 "business":("business analysis","business analyst","business operations","process improvement","negocios","processos"),
}
LEADERSHIP=("manager","head","director","diretor","gerente","lead","lider","coordinator","coordenador","owner","founder")
SENIORITY=("senior","sr.","lead","principal","head","director","gerente","diretor")
REQUIRED_MARKERS=("required","must have","must be","mandatory","obrigatorio","obrigatoria","necessario","necessaria","essential")
SPECIALIZED_GAPS={
 "spanish":("fluent spanish","fluent in spanish","spanish fluency","espanhol fluente"),
 "software_engineering":("write production code","hands-on coding required","coding is required","must code"),
 "card_acquiring":("iso 8583","card acquiring","scheme settlement"),
}

def score_job(job,roles):
    title=fold(job.get("title",""))
    jd=clean_jd(job.get("description") or job.get("jobDescription") or job.get("content"))
    joined=title+" "+jd
    requested=requested_families(search_terms(roles))
    evidence=signals(job,roles)
    family_hits=[]
    for family in requested:
        matched_title=any(p in title for p in FAMILY_TERMS[family])
        matched_jd=any(e["family"]==family for e in evidence["family_evidence"])
        if matched_title or matched_jd:
            family_hits.append(family)
    proof=[{"family":f,"source":list(PROFILE[f])[:2]} for f in family_hits]
    # A title alone establishes relevance, not a full 40-point professional fit.
    fit=min(40,(30 if family_hits else 0)+(10 if jd and evidence["family_evidence"] else 0))
    manage=15 if any(re.search(r"(?<![a-z])"+re.escape(t)+r"(?![a-z])",title) for t in LEADERSHIP) else 0
    remote=20 if detect_work_mode(job,evidence)=="remote" else 0
    salary=10 if any(k in job and bool(job[k]) for k in ("salary","salaryRange","compensation")) else 0
    matching_axes=[(name,weight) for name,weight,terms in AXES if any(term in joined for term in terms)]
    axis,axis_points=max(matching_axes,key=lambda x:x[1]) if matching_axes else ("generalista",10)
    # An irrelevant domain mention in the JD does not produce professional proof.
    if not family_hits:axis_points=0
    gaps=[]
    for label,phrases in SPECIALIZED_GAPS.items():
        if any(p in jd for p in phrases):
            gaps.append(label)
    score=max(0,min(97,fit+manage+remote+salary+axis_points))
    confidence="completa" if jd and len(jd)>=150 else "provisoria"
    return {"score":score,"score_max":97,"confidence":confidence,
            "fit":fit,"management":manage,"remote":remote,"salary_bonus":salary,
            "axis":axis,"axis_bonus":axis_points,"profile_evidence":proof,
            "review_requirements":gaps,
            "reason":("Exige verificação: "+", ".join(gaps)) if gaps else
                      ("JD parcial ou ausente; nota provisória" if confidence=="provisoria"
                       else "Prioridade baseada no cargo, JD e evidências do perfil"),
            "method":"cacador-v2-prioridade"}
