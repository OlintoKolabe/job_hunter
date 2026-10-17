"""Deterministic JD evidence extraction. No AI calls or made-up eligibility."""
import html,re
from search_filters import fold,requested_families,search_terms,ROLE_FAMILIES

JD_PATTERNS={
 "product":("product roadmap","product discovery","product strategy","product lifecycle","product backlog","product requirements","stakeholder management","user research","gestao de produto","estrategia de produto","visao do produto","priorizacao do backlog","gestao de backlog"),
 "projects":("project delivery","project planning","project management","manage projects","manage cross functional projects","project stakeholders","project governance","project milestones","scrum master","agile delivery","gestao de projetos","gerenciamento de projetos","cronograma de projetos","governanca de projetos","gestao de stakeholders"),
 "marketing":("marketing strategy","marketing campaigns","campaign management","marketing operations","demand generation","go to market","growth marketing","performance marketing","crm campaigns","lead generation","estrategia de marketing","campanhas de marketing","geracao de demanda","marketing digital"),
 "growth":("growth experiments","growth strategy","growth initiatives","growth funnel","conversion optimization","customer acquisition","retention strategy","lifecycle marketing","funnel optimization","a/b testing","growth loops","experimentos de crescimento","aquisicao de clientes","otimizacao de conversao"),
 "business":("business requirements","business analysis","process mapping","business process","stakeholder requirements","process improvement","analise de negocios","analise de processos","levantamento de requisitos","mapeamento de processos"),
}
REMOTE_EVIDENCE=("fully remote","100% remote","100% remoto","work from home","home office","trabalho remoto","remote position","remote role","remote working","teletrabalho")
ONSITE_EVIDENCE=("on site only","onsite only","must work from office","presencial obrigatorio","exclusivamente presencial")
FOREIGN_ONLY=("us only","usa only","united states only","must reside in the us","must be based in the us","europe only","canada only")
BRAZIL_EVIDENCE=("based in brazil","located in brazil","reside in brazil","work from brazil","brazilian residents","candidatos do brasil","residir no brasil","atuar do brasil","brazil or latam")
SPANISH_REQ=("fluent spanish required","fluent in spanish","spanish fluency required","fluency in spanish","espanhol fluente obrigatorio","fluencia em espanhol obrigatoria")
SPANISH_OPTIONAL=("spanish is a plus","spanish preferred","espanhol desejavel","espanhol sera um diferencial")
def clean_jd(raw):
    if not raw:return ""
    if isinstance(raw,(list,dict)):return ""
    value=html.unescape(re.sub(r"<[^>]+>"," ",str(raw)))
    value=fold(re.sub(r"\s+"," ",value)).strip()
    return value[:18000]

def signals(job,roles):
    jd=clean_jd(job.get("description") or job.get("jobDescription") or job.get("content"))
    if not jd:return {"jd_available":False,"family_evidence":[],"work_evidence":[],"geography_evidence":[],"spanish_required":False}
    requested=requested_families(search_terms(roles))
    matched=[]
    for family in requested:
        hits=[phrase for phrase in JD_PATTERNS.get(family,()) if phrase in jd]
        if len(hits)>=2:matched.append({"family":family,"evidence":hits[:3]})
    work=[]
    if any(x in jd for x in REMOTE_EVIDENCE):work.append("remote")
    if any(x in jd for x in ONSITE_EVIDENCE):work.append("onsite_only")
    geo=[]
    if any(x in jd for x in BRAZIL_EVIDENCE):geo.append("brazil")
    if any(x in jd for x in FOREIGN_ONLY):geo.append("foreign_only")
    spanish=any(x in jd for x in SPANISH_REQ) and not any(x in jd for x in SPANISH_OPTIONAL)
    return {"jd_available":True,"family_evidence":matched,"work_evidence":work,"geography_evidence":geo,"spanish_required":spanish}
