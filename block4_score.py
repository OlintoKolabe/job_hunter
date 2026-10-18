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

# A statement is matched against a documented skill, never against a title alone.
SKILLS={
 "roadmap":(("roadmap","product strategy","estrategia de produto"),"product","Hexagon / Neocoder: roadmaps e estratégia de produto"),
 "backlog":(("backlog","user stor","historias de usuario","product owner"),"product","Hexagon / Dotz: backlog, histórias e PO"),
 "scrum":(("scrum","kanban","agile delivery","metodologias ageis"),"projects","Neocoder: Scrum e Kanban"),
 "project":(("project management","manage projects","gestao de projetos","pmo","project delivery"),"projects","Neocoder: gestão de projetos e PMO"),
 "stakeholders":(("stakeholder management","stakeholders","gestao de stakeholders"),"product","Hexagon e Neocoder: gestão de stakeholders"),
 "growth":(("growth experiment","a/b testing","experimentacao","conversion optimization"),"growth","Kolabe / LiberPay: experimentação e growth"),
 "marketing":(("marketing strategy","marketing campaigns","estrategia de marketing","digital marketing"),"marketing","Lagoa / Grupo Privé: liderança de marketing"),
 "crm":(("crm","lifecycle marketing","retention marketing"),"marketing","Dotz / Lagoa: CRM e fidelização"),
 "analytics":(("google analytics","google ads","kpis","okrs","metricas"),"growth","Kolabe: analytics, KPIs e Google Ads"),
 "process":(("business process","process improvement","process mapping","analise de processos"),"business","Neocoder / Top Saúde: processos e indicadores"),
 "figma":(("figma","prototyping","prototipacao"),"product","Kolabe / Dotz: Figma e prototipação"),
 "jira":(("jira","confluence","azure devops"),"product","Neocoder / Hexagon: Jira, Confluence e Azure DevOps"),
}
# Explicitly non-proven qualifications: absence is UNKNOWN, not a claim of inability.
UNPROVEN={
 "spanish":("fluent spanish","spanish fluency","fluency in spanish","espanhol fluente"),
 "engineering":("write production code","hands-on coding required","must code"),
 "payments":("iso 8583","card acquiring","scheme settlement"),
}
MANDATORY=("required","must have","mandatory","essential","obrigatorio","obrigatoria","necessario","necessaria","requisito")
DESIRABLE=("nice to have","preferred","desirable","plus","desejavel","diferencial")
def requirement_lines(jd):
    # Keep HTML bullet boundaries and distinguish mandatory vs desirable entries.
    raw=re.sub(r"<[^>]+>", "\n",jd or "")
    rows=re.split(r"[\n\r•]+|(?<=[.;])\s+",raw)
    return [fold(x).strip() for x in rows if len(fold(x).strip())>=8][:120]

def score_job(job,roles):
    jd_raw=job.get("description") or job.get("jobDescription") or job.get("content") or ""
    jd=clean_jd(jd_raw)
    title=fold(job.get("title",""))
    requirements=[]
    used=set()
    section=None
    heading_required=("requirements","qualifications","what you bring","what we look for","requisitos","qualificacoes","qualificações","skills and experience")
    heading_optional=("nice to have","preferred qualifications","desejaveis","diferenciais")
    heading_end=("benefits","perks","what we offer","about us","sobre nos","responsibilities","responsabilidades","what you will do","about the role")
    for line in requirement_lines(str(jd_raw)):
        if len(line)<95 and any(line.startswith(h) for h in heading_optional):
            section="desejavel"
            continue
        if len(line)<95 and any(line.startswith(h) for h in heading_required):
            section="obrigatorio"
            continue
        if len(line)<95 and any(line.startswith(h) for h in heading_end):
            section=None
            continue
        is_mandatory=any(x in line for x in MANDATORY) or section=="obrigatorio"
        is_desirable=any(x in line for x in DESIRABLE) or section=="desejavel"
        if not (is_mandatory or is_desirable):continue
        kind="obrigatorio" if is_mandatory else "desejavel"
        before=len(requirements)
        for skill,(phrases,family,proof) in SKILLS.items():
            if skill not in used and any(p in line for p in phrases):
                requirements.append({"name":skill,"type":kind,"status":"comprovado","evidence":proof})
                used.add(skill)
        for skill,phrases in UNPROVEN.items():
            if skill not in used and any(p in line for p in phrases):
                requirements.append({"name":skill,"type":kind,"status":"nao_comprovado","evidence":None})
                used.add(skill)
        if len(requirements)==before and len(line)>12:
            requirements.append({"name":line[:110],"type":kind,"status":"nao_comprovado","evidence":None})
    mandatory=[r for r in requirements if r["type"]=="obrigatorio"]
    desirable=[r for r in requirements if r["type"]=="desejavel"]
    # No requirements extracted means no professional-fit claim can be substantiated.
    available=len(requirements)>0
    # Mandatory requirements dominate; desirables only adjust scored candidates.
    wtotal=3*len(mandatory)+len(desirable)
    wmet=sum((3 if r["type"]=="obrigatorio" else 1) for r in requirements if r["status"]=="comprovado")
    fit=round(100*wmet/wtotal) if wtotal else None
    uncertainty=sum(r["status"]=="nao_comprovado" for r in requirements)
    priority={
        "remote":detect_work_mode(job,signals(job,roles))=="remote",
        "salary_informed":any(bool(job.get(k)) for k in ("salary","salaryRange","compensation")),
        "sector":next((name for name,_,phrases in AXES if any(p in title+" "+jd for p in phrases)),None),
    }
    return {"score":fit,"score_max":100,"confidence":"requisitos_extraidos" if available else "sem_base",
            "fit":fit,"requirements":requirements,"mandatory_count":len(mandatory),
            "desirable_count":len(desirable),"unverified_count":uncertainty,
            "priority":priority,
            "profile_evidence":[{"family":r["name"],"source":[r["evidence"]]} for r in requirements if r["evidence"]],
            "reason":("Percentual sobre requisitos extraídos do JD; não representa cobertura integral se o anúncio for incompleto"
                      if available else "JD sem requisitos identificáveis: sem nota de aderência"),
            "method":"block4-evidencias-v1"}
