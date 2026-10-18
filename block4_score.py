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
# Evidence-backed synonyms; only skills documented in the October LinkedIn profile.
SKILLS.update({
 "portfolio":(("portfolio management","project portfolio","gestao de portfolio","gestao de portifolio"),"projects","Neocoder: Head de projetos e processos, gestão de portfólio"),
 "leadership":(("cross-functional teams","cross functional teams","multidisciplinary teams","times multidisciplinares","team leadership","people management"),"projects","Neocoder e Lagoa: liderança de equipes e projetos"),
 "finance":(("budget management","financial planning","p&l","budgeting","gestao orcamentaria","gestao de orcamento"),"business","Top Saúde e Lagoa: gestão financeira e orçamentos"),
 "strategy":(("strategic planning","business development","commercial strategy","business strategy","planejamento estrategico","desenvolvimento de negocios"),"business","Lagoa: desenvolvimento corporativo e estratégia"),
 "experience":(("user experience","ux research","user research","product discovery","prototyping","prototipacao"),"product","Kolabe e Dotz: discovery, UX e protótipos"),
 "delivery":(("agile methodologies","sprint planning","product delivery","cross-functional delivery","agile frameworks"),"projects","Hexagon e Neocoder: entrega ágil, sprints e Scrum/Kanban"),
 "acquisition":(("user acquisition","customer acquisition","retention","churn","activation","growth strategy","conversion optimization"),"growth","Kolabe e LiberPay: aquisição, retenção e crescimento"),
 "launch":(("go-to-market","go to market","product launch","product lifecycle","nps","product-market fit"),"product","Neocoder / Kolabe: ciclo de produto, PMF e lançamentos"),
 "segmentation":(("customer segmentation","loyalty programs","fidelizacao","customer journey"),"marketing","Dotz: CRM, segmentação, fidelização e jornada"),
})
# Domain evidence grounded in the professional history; do not infer technical implementation.
SKILLS.update({
 "healthcare_product":(("healthcare product","healthtech product","clinical workflows","clinical operations platform"),"product","Top Saúde: liderança do produto interno SysTop e processos de operação clínica"),
 "mining_product":(("mining product","mining software product","autonomous mining operations","mining traffic control"),"product","Hexagon Mining: Product Manager do Mission Manager em controle de tráfego autônomo"),
 "crypto_payments":(("crypto payments","cryptocurrency payments","stablecoin payment","web3 payments"),"product","Neocoder/LiberPay: consultoria de produtos e estratégia B2B em pagamentos cripto e stablecoins; não comprova Pix ou adquirência"),
 "loyalty_product":(("loyalty crm","retail loyalty","loyalty products","loyalty platform"),"product","Dotz: Product Owner do Meu Varejo, CRM, fidelização e inteligência comercial"),
})
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

def hard_role_mismatch(job):
    """Unambiguous hands-on engineering/QA job titles lie outside the documented PM/business career."""
    title=fold(str(job.get("title") or ""))
    return any(term in title for term in (
        "software engineer","software developer","frontend developer","front end developer",
        "backend developer","back end developer","fullstack developer","full stack developer",
        "qa engineer","qa analyst","quality assurance engineer","test automation engineer",
        "engenheiro de software","desenvolvedor de software","analista de testes automatizados",
    ))

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
        if len(line)<95 and any(line.strip(" :.-")==h for h in heading_optional):
            section="desejavel"
            continue
        if len(line)<95 and any(line.strip(" :.-")==h for h in heading_required):
            section="obrigatorio"
            continue
        if len(line)<95 and any(line.strip(" :.-")==h for h in heading_end):
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
            requirements.append({"name":line[:110],"type":kind,"status":"nao_interpretado","evidence":None})
    mandatory=[r for r in requirements if r["type"]=="obrigatorio"]
    desirable=[r for r in requirements if r["type"]=="desejavel"]
    # No requirements extracted means no professional-fit claim can be substantiated.
    available=len(requirements)>0
    # Mandatory requirements dominate; desirables only adjust scored candidates.
    interpreted=[r for r in requirements if r["status"]!="nao_interpretado"]
    wtotal=sum(3 if r["type"]=="obrigatorio" else 1 for r in interpreted)
    wmet=sum((3 if r["type"]=="obrigatorio" else 1) for r in requirements if r["status"]=="comprovado")
    fit=round(100*wmet/wtotal) if wtotal else None
    uncertainty=sum(r["status"]=="nao_comprovado" for r in requirements)
    uninterpreted=sum(r["status"]=="nao_interpretado" for r in requirements)
    coverage=round(100*len(interpreted)/len(requirements)) if requirements else 0
    if coverage<60 or len(requirements)<4 or len(str(jd_raw).strip())<300:fit=None
    priority={
        "remote":detect_work_mode(job,signals(job,roles))=="remote",
        "salary_informed":any(bool(job.get(k)) for k in ("salary","salaryRange","compensation")),
        "sector":next((name for name,_,phrases in AXES if any(p in title+" "+jd for p in phrases)),None),
    }
    confidence=("sem_base" if not available else ("cobertura_insuficiente" if coverage<60 else ("amostra_limitada" if len(requirements)<4 else "requisitos_extraidos")))
    return {"score":fit,"score_max":100,"confidence":confidence,"evaluated_requirements":len(requirements),
            "fit":fit,"requirements":requirements,"mandatory_count":len(mandatory),
            "desirable_count":len(desirable),"unverified_count":uncertainty,"uninterpreted_count":uninterpreted,"coverage_pct":coverage,
            "priority":priority,
            "profile_evidence":[{"family":r["name"],"source":[r["evidence"]]} for r in requirements if r["evidence"]],
            "reason":("Percentual sobre requisitos extraídos do JD; não representa cobertura integral se o anúncio for incompleto"
                      if available else "JD sem requisitos identificáveis: sem nota de aderência"),
            "method":"block4-evidencias-cobertura-v2"}

def merge_semantic_requirements(base, extracted):
    """Evidence-first grading; unrelated requirements earn zero, adjacent experience earns partial credit.
    A missing skill_id is UNKNOWN evidence, never proof that the candidate cannot perform a job.
    """
    if not extracted:return base
    rows=[]
    for row in extracted:
        if not isinstance(row,dict):continue
        name=str(row.get("name") or "").strip()
        kind=row.get("type")
        skill=row.get("skill_id")
        if not name or kind not in ("obrigatorio","desejavel"):continue
        name=name[:160]
        proof=SKILLS[skill][2] if isinstance(skill,str) and skill in SKILLS else None
        normalized=fold(name)
        # The documented LiberPay consulting experience is adjacent, not direct
        # payment-product ownership or knowledge of the Pix/card rails.
        payments_context=any(x in normalized for x in ("payment","payments","pagamento","pagamentos","pix","acquiring","adquirencia","settlement"))
        specialized_payments=any(x in normalized for x in ("pix","card acquiring","settlement","iso 8583","brazilian payment rails"))
        technical_core=any(x in normalized for x in ("write code","hands-on coding","programming required","software development required","previous software developer experience","hands-on software development","test automation","qa automation","computer science degree","coding required"))
        # A generic PM capability does not prove specialized Pix/card-rails expertise.
        transferable_domains=(
            (("healthcare domain","clinical operations","healthtech domain"),"Top Saúde: gestão de serviços médicos e processos"),
            (("mining domain","mining operations"),"Hexagon Mining: experiência em produto na mineração"),
            (("loyalty programs","retail loyalty"),"Dotz: experiência em produto e CRM"),
            (("marketing industry","advertising domain"),"Lagoa Parques: direção de marketing"),
        )
        domain_evidence=next((e for terms,e in transferable_domains if any(t in normalized for t in terms)),None)
        relationship=row.get("relationship")
        explicit_skill=bool(proof and any(fold(term) in normalized for term in SKILLS[skill][0]))
        if technical_core or relationship=="nenhuma":
            degree="nao_comprovada"
            evidence=None
            points=0.0
        elif proof and (relationship=="transferivel" or not explicit_skill):
            degree="transferivel"
            evidence=proof+"; habilidade documentada aplicável parcialmente ao contexto da vaga"
            points=0.45
        elif proof and specialized_payments:
            degree="transferivel"
            evidence=proof+"; competência de produto transferível, mas atuação nas regras de pagamento específicas não comprovada"
            points=0.4
        elif proof:
            degree="direta"
            evidence=proof
            points=1.0
        elif payments_context:
            degree="transferivel"
            evidence="Neocoder/LiberPay: consultoria e estratégia em pagamentos com criptoativos e stablecoins; sem evidência de liderança de produto de Pix"
            points=0.25
        elif domain_evidence:
            degree="transferivel"
            evidence=domain_evidence+"; domínio transferível não comprova todas as competências técnicas da vaga"
            points=0.35
        else:
            degree="nao_comprovada"
            evidence=None
            points=0.0
        rows.append({"name":name,"type":kind,"status":"comprovado" if degree=="direta" else "parcial" if degree=="transferivel" else "nao_comprovado",
                     "match_level":degree,"match_points":points,"evidence":evidence,
                     "evidence_id":skill if evidence and proof else "liberpay_payments_context" if evidence and payments_context else None,
                     "explanation":("Experiência diretamente documentada" if degree=="direta" else
                                    "Experiência aplicável parcialmente, sem equivalência plena de função ou tecnologia" if degree=="transferivel" else
                                    "Não há evidência suficiente no perfil documentado; isso não prova incapacidade")})
    if not rows:return base
    weights=[3 if r["type"]=="obrigatorio" else 1 for r in rows]
    total=sum(weights)
    met=sum(w*r["match_points"] for r,w in zip(rows,weights))
    # The model may miss requirements; 1–3 extracted requirements are not
    # enough to claim either 0 or 100 overall fit.
    sufficiently_parsed=len(rows)>=4
    fit=round(100*met/total) if sufficiently_parsed and total else None
    matched=sum(r["match_points"]>0 for r in rows)
    return {**base,"score":fit,"fit":fit,"requirements":rows,
        "evaluated_requirements":len(rows),
        "mandatory_count":sum(r["type"]=="obrigatorio" for r in rows),
        "desirable_count":sum(r["type"]=="desejavel" for r in rows),
        "unverified_count":sum(r["match_level"]=="nao_comprovada" for r in rows),
        "uninterpreted_count":0,"coverage_pct":100,
        "confidence":"semantic_evidence" if fit is not None else "semantic_insufficient",
        "match_summary":{"direct":sum(r["match_level"]=="direta" for r in rows),
                         "transferable":sum(r["match_level"]=="transferivel" for r in rows),
                         "unproven":sum(r["match_level"]=="nao_comprovada" for r in rows),
                         "requirements_found":len(rows),"evidence_count":matched},
        "reason":("Nota ponderada: experiência direta vale integral, transferência documentada vale parcialmente, ausência de evidência vale zero no requisito. Zero não equivale a incapacidade."
                  if fit is not None else
                  "Menos de quatro requisitos interpretados: não há base para classificar a compatibilidade, nem mesmo como zero."),
        "method":"block4.1-transferable-evidence-v1"}
