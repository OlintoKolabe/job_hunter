"""Search filters with conservative inclusion: unknown location/mode/date are not matches."""
from datetime import datetime,timezone,timedelta
import hashlib
import re,unicodedata
from urllib.parse import urlsplit

DEFAULT_ROLES="Product Manager, Product Owner, Project Manager, Gerente de Projetos, Product Marketing, Marketing, Growth, Business Analyst, Analista de Negócios, PMO"
LATAM={"brazil","brasil","argentina","chile","colombia","colômbia","peru","uruguay","uruguai","paraguay","paraguai","bolivia","bolívia","ecuador","equador","mexico","méxico","costa rica","panama","panamá","guatemala","el salvador","honduras","nicaragua","nicarágua","dominican republic","república dominicana","venezuela"}
COUNTRIES=[("LATAM","América Latina"),("BR","Brasil"),("AR","Argentina"),("BO","Bolívia"),("CL","Chile"),("CO","Colômbia"),("CR","Costa Rica"),("EC","Equador"),("GT","Guatemala"),("MX","México"),("PA","Panamá"),("PY","Paraguai"),("PE","Peru"),("DO","República Dominicana"),("UY","Uruguai"),("VE","Venezuela"),("US","Estados Unidos"),("CA","Canadá"),("PT","Portugal"),("ES","Espanha"),("GB","Reino Unido"),("GLOBAL","Global")]
COUNTRY_NAMES=dict(COUNTRIES)
TOKENS={"BR":["brazil","brasil"],"AR":["argentina"],"BO":["bolivia"],"CL":["chile"],"CO":["colombia"],"CR":["costa rica"],"EC":["ecuador"],"GT":["guatemala"],"MX":["mexico"],"PA":["panama"],"PY":["paraguay","paraguai"],"PE":["peru"],"DO":["dominican republic","republica dominicana"],"UY":["uruguay","uruguai"],"VE":["venezuela"],"US":["united states","usa","u.s."],"CA":["canada"],"PT":["portugal"],"ES":["spain","espanha"],"GB":["united kingdom","uk","england"]}
# The UI country selector covers only a subset of world countries. A concrete
# foreign location must not be classified as geographically unknown merely
# because its country is absent from TOKENS.
OTHER_FOREIGN_COUNTRIES=(
    "germany","deutschland","france","italy","netherlands","belgium","switzerland",
    "austria","sweden","norway","denmark","finland","poland","ireland",
    "czech republic","czechia","romania","hungary","greece","ukraine",
    "india","pakistan","bangladesh","singapore","japan","china","taiwan",
    "south korea","philippines","indonesia","malaysia","thailand","vietnam",
    "australia","new zealand","south africa","nigeria","kenya","israel",
    "united arab emirates","uae","saudi arabia","egypt","turkey",
)
# High-confidence foreign city-only locations seen in collector records.
# Unrecognized cities remain 'unknown', never silently confirmed.
FOREIGN_CITY_ONLY=("boston","new york","san francisco","los angeles","seattle",
                   "chicago","austin","london","berlin","munich","paris","amsterdam")
REMOTE=["remote","remoto","remota","home office","home-office","homeoffice","home based","work from home","work-from-home","work remotely","work remotely from","fully remote","remote first","remote-first","100% remote","100% remoto","full remote","teletrabalho","telecommute","telecommuting","remotely","trabalho remoto","trabalho a distancia","trabalho à distância","trabalho em casa","trabalho de casa","any location","work anywhere","work at home","virtual position","distributed team","anywhere"]
HYBRID=["hybrid","hibrido","híbrido","flexible hybrid","modelo hibrido","parcialmente presencial"]
ONSITE=["on-site","onsite","on site","presencial","in-office","in office","office based","office-based","on premises"]
REGIONAL=["latam","latin america","america latina","americas","remote worldwide","worldwide","anywhere in the world","global remote","remote latin america","south america","america do sul","americas remote","latinoamerica","latinoamerica remote"]

def fold(x):
    return unicodedata.normalize("NFKD",str(x or "")).encode("ascii","ignore").decode().lower()

def search_terms(value):
    raw=[x.strip() for x in re.split(r"[,;\n]+",str(value or ""))]
    return [fold(x) for x in raw if x.strip()][:250]

def parse_date(value):
    if not value:return None
    try:
        if isinstance(value,(int,float)) or (isinstance(value,str) and value.isdigit()):
            v=float(value)
            if v>1e11:v/=1000
            return datetime.fromtimestamp(v,timezone.utc)
        return datetime.fromisoformat(str(value).replace("Z","+00:00")).replace(tzinfo=timezone.utc) if datetime.fromisoformat(str(value).replace("Z","+00:00")).tzinfo is None else datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(timezone.utc)
    except (ValueError,OverflowError,OSError):return None

TITLE_ALIASES={
 "product manager":["product manager","gerente de produto","gestor de produto","product lead","product management","product analyst","analista de produto","analista de produtos","especialista de produto","especialista de produtos","lider de produto","lider de produtos","estrategista de produto","gerencia de produtos"],
 "product owner":["product owner","dono de produto","product ownership","po senior","po pleno"],
 "project manager":["project manager","gerente de projetos","gestor de projetos","gestao de projetos","gerenciamento de projetos","coordenador de projetos","coordenadora de projetos","lider de projetos","project lead","project coordinator","program manager","delivery manager","implementation project"],
 "gerente de projetos":["gerente de projetos","project manager","gestor de projetos"],
 "product marketing":["product marketing","marketing de produto","product marketer","marketing de produtos","product marketing specialist"],
 "business analyst":["business analyst","analista de negocios","analista de negocio"],
 "analista de negocios":["analista de negocios","business analyst","analista de negocio"],
 "pmo":["pmo","project management office"],
 "growth":["growth manager","growth lead","head of growth","head de growth","growth marketing","gerente de growth","coordenador de growth","growth specialist","especialista de growth","growth strategist","growth marketer","growth operations","acquisition manager","lifecycle marketing"],
 "marketing":["marketing manager","marketing lead","head of marketing","head de marketing","gerente de marketing","diretor de marketing","marketing director","product marketing","marketing specialist","especialista de marketing","coordenador de marketing","coordenadora de marketing","analista de marketing","marketing operations","marketing ops","demand generation","field marketing","lifecycle marketing","acquisition marketing"],
}
# Broader role discovery, without treating unrelated engineering/science jobs as matches.
NON_TARGET_TITLE=re.compile(r"\b(developer|engineer|scientist|researcher|designer|intern|estagiario|estagiaria|recruiter|sales|account executive|sdr|devops|software|backend|frontend)\b")
RELATED_TITLE=re.compile(r"(product|produto|project|projetos|marketing|growth|pmo|negocios|business analy)")
# Families are semantic OR-groups. Selection of multiple families is also OR.
ROLE_FAMILIES={
 "product":("product manager","product owner","product lead","head of product","head de produto","product management","product operations","product ops","product analyst","product specialist","product strategist","gerente de produto","gerente de produtos","gestor de produto","gestao de produto","lider de produto","lider de produtos","coordenador de produto","coordenadora de produto","especialista de produto","especialista de produtos","analista de produto","analista de produtos","estrategista de produto","consultor de produto","consultora de produto","product growth","gerente de plataforma de produto"),
 "projects":("project manager","program manager","programme manager","project lead","project coordinator","project management","project specialist","project analyst","delivery manager","delivery lead","implementation manager","implementation project","transformation manager","digital transformation lead","gerente de projeto","gerente de projetos","gestor de projetos","gestora de projetos","gestao de projetos","gerenciamento de projetos","coordenador de projeto","coordenador de projetos","coordenadora de projetos","lider de projetos","analista de projetos","especialista de projetos","escritorio de projetos","pmo"),
 "marketing":("marketing","market intelligence","inteligencia de mercado","demand generation","demand gen","performance marketing","lifecycle","crm manager","gerente de crm","acquisition","aquisicao","retention marketing","retencao","field marketing","brand manager","gestor de marca","gestao de marca","product marketing","marketing de produto","marketing de produtos","go to market","go-to-market","gtm manager"),
 "growth":("growth manager","growth lead","growth marketer","head of growth","growth marketing","growth specialist","growth operations","growth strategist","gerente de growth","coordenador de growth","especialista de growth","gerente de crescimento","gestor de crescimento","acquisition manager","lifecycle marketing","revenue growth","growth product","growth ops"),
 "business":("business analyst","business analysis","business operations","business ops","business process","business transformation","analista de negocios","analista de negocio","consultor de negocios","consultora de negocios","gestor de negocios","gestao de negocios","analista de processos","consultor de processos"),
}
ROLE_KEYS={
 "product":("product manager","product owner","produto","product","po"),
 "projects":("project manager","projeto","project","program manager","pmo","delivery manager"),
 "marketing":("marketing","mercadologia","market intelligence","crm"),
 "growth":("growth","crescimento","acquisition"),
 "business":("business analyst","analista de negocios","analista de negocio","business operations"),
}
NON_TARGET_TITLE=re.compile(r"\b(developers?|engineers?|engineering|scientists?|researchers?|designers?|interns?|estagiarios?|estagiarias?|recruiters?|account executive|sdr|devops|backend|frontend)\b")
def requested_families(terms):
    families=set()
    for term in terms:
        matched=False
        for family,aliases in ROLE_KEYS.items():
            if any(alias in term for alias in aliases):
                families.add(family);matched=True
        if not matched:
            for family,aliases in ROLE_FAMILIES.items():
                if any(term==alias for alias in aliases):families.add(family)
    return families
def role_match(title,terms):
    title=fold(title)
    terms=[fold(t) for t in terms]
    if not terms:return True
    # An explicitly selected title must not silently mean its entire family.
    # E.g. Product Manager is not Product Analyst or Head of Product.
    for term in terms:
        aliases=TITLE_ALIASES.get(term,(term,))
        if term=="product manager":
            aliases=("product manager","gerente de produto","gestor de produto")
        elif term=="product owner":
            aliases=("product owner","dono de produto","product ownership")
        if any(contains_phrase(title,alias) for alias in aliases):return True
    if NON_TARGET_TITLE.search(title):return False
    return any(len(t)>=3 and contains_phrase(title,t) for t in terms)
# Small bilingual discovery set per selected family, not the entire synonym lexicon.
DISCOVERY={
 "product":("product manager","product owner","gerente de produto","especialista de produtos"),
 "projects":("project manager","gerente de projetos","pmo"),
 "marketing":("marketing manager","gerente de marketing","marketing ops"),
 "growth":("growth manager","growth marketing","gerente de growth"),
 "business":("business analyst","analista de negocios","business operations"),
}
def discovery_queries(roles,limit=12):
    terms=search_terms(roles)
    families=[f for f in ("product","projects","marketing","growth","business") if f in requested_families(terms)]
    queues={f:list(DISCOVERY[f]) for f in families}
    out=[]
    while len(out)<limit and any(queues.values()):
        for family in families:
            if queues[family]:
                candidate=queues[family].pop(0)
                if candidate not in out:out.append(candidate)
                if len(out)>=limit:break
    for term in terms:
        if len(out)>=limit:break
        if term not in out:out.append(term)
    return out


def detect_work_mode(job,evidence=None):
    """Infer a single work mode, or leave it unknown."""
    evidence=evidence or {"work_evidence":[]}
    def normalize(value):
        return re.sub(r"\s+"," ",fold(value).replace("_"," ").replace("-"," ")).strip()
    remote=("remote","remoto","remota","home office","homeoffice","work from home","teletrabalho","telecommute","100% remoto","100% remote")
    hybrid=("hybrid","hibrido","hibrida","hibrid","partial remote","parcialmente remoto","semipresencial")
    onsite=("on site","onsite","presencial","in office","office based","no escritorio")
    def found(text,patterns):
        return any(re.search(r"(?<![a-z])"+re.escape(p)+r"(?![a-z])",text) for p in patterns)
    def detect(text):
        h,r,o=found(text,hybrid),found(text,remote),found(text,onsite)
        if h or (r and o):return "hybrid"
        if o:return "onsite"
        if r:return "remote"
        return None
    # Explicitly conflicting signals are not proof of remote eligibility.
    jd=evidence.get("work_evidence") or []
    if "onsite_only" in jd:return "onsite"
    structured=[]
    for key in ("workplaceType","workArrangement","remoteType","workMode","workplace"):
        value=job.get(key)
        if isinstance(value,str):
            detected=detect(normalize(value))
            if detected:structured.append(detected)
    if len(set(structured))>1:return None
    # A strict onsite statement overrides a generic remote flag.
    if structured and "remote" in structured and "onsite_only" in jd:return "onsite"
    if structured:
        if job.get("remote") is True and structured[0]!="remote":return None
        return structured[0]
    result=detect(normalize(job.get("location")))
    if result:
        if job.get("remote") is True and result!="remote":return None
        return result
    # False does not establish onsite: it can also mean hybrid or unspecified.
    if job.get("remote") is True:return "remote"
    if "remote" in jd:return "remote"
    # These endpoints are documented remote-only job feeds. The adapter has
    # already selected a remote opportunity, although its generic listing
    # lacks a separate work-mode field. Do not infer this for arbitrary ATS.
    if fold(job.get("source", "")) in ("himalayas", "remotive", "remoteok"):
        return "remote"
    return None


BR_CITIES=("sao paulo","rio de janeiro","belo horizonte","curitiba","porto alegre","brasilia","goiania","recife","fortaleza","salvador","campinas","florianopolis","uberlandia","belem","manaus","vitoria","ribeirao preto")
LATAM_MARKERS=("latam","latin america","america latina","latinoamerica","south america","america do sul")
GLOBAL_MARKERS=("worldwide","anywhere in the world","global remote","remote worldwide")
FOREIGN_ONLY_MARKERS=("remote us","remote usa","remote - us","remote - usa","us remote","usa remote","remote, us","us-based","us based","usa based","united states only","us only","usa only","u.s. only","europe only","canada only","must be based in the us","must reside in the us")
BRAZIL_EXCLUSIONS=("except brazil","excluding brazil","not available in brazil","excluindo brasil","exceto brasil","fora do brasil")
LATAM_CODES={"BR","AR","BO","CL","CO","CR","EC","GT","MX","PA","PY","PE","DO","UY","VE"}

def contains_phrase(text,phrase):
    return re.search(r"(?<![a-z])"+re.escape(fold(phrase))+r"(?![a-z])",text) is not None

def geo_verdict(job,country,evidence=None):
    """Return eligible, unknown or excluded, without treating regional tags as global."""
    evidence=evidence or {"geography_evidence":[]}
    if country=="GLOBAL":return "eligible"
    parts=[]
    for key in ("location","country","countryCode","countryName","city","state","region","eligibleLocations","remoteRegions"):
        value=job.get(key)
        if isinstance(value,str):parts.append(value)
        elif isinstance(value,list):parts.extend(str(v) for v in value if isinstance(v,str))
    loc=fold(" ".join(parts))
    jd_geo=evidence.get("geography_evidence") or []
    # Job descriptions may narrow a multi-country/location heading.
    from jd_signals import clean_jd
    jd_text=clean_jd(job.get("description") or job.get("jobDescription") or job.get("content"))
    restricted=any(contains_phrase(jd_text,p) for p in FOREIGN_ONLY_MARKERS)
    restricted=restricted or bool(re.search(
        r"\b(?:must|required to|need to)\s+(?:be\s+)?(?:located|based|reside|live)\s+in\s+"
        r"(?:the\s+)?(?:united states|usa|u\.s\.|canada|europe|uk|united kingdom)\b",jd_text))
    # A global/empty API location never overrides an explicit EMEA-only JD.
    restricted=restricted or bool(re.search(
        r"\b(?:remote\s*[(\-:]?\s*emea|emea\s*(?:only|remote)|"
        r"(?:based|located|reside|live)\s+in\s+emea)\b",jd_text))
    if any(contains_phrase(loc,p) for p in FOREIGN_ONLY_MARKERS) or "foreign_only" in jd_geo or restricted:
        if country in ("BR","LATAM"):return "excluded"
    if country=="BR" and any(contains_phrase(loc+" "+jd_text,p) for p in BRAZIL_EXCLUSIONS):
        return "excluded"
    has_br_location=any(contains_phrase(loc,p) for p in ("brazil","brasil","br")) or any(contains_phrase(loc,p) for p in BR_CITIES)
    has_latam_location=any(contains_phrase(loc,p) for p in LATAM_MARKERS)
    if country in ("BR","LATAM") and not any(contains_phrase(loc,p) for p in GLOBAL_MARKERS):
        if not (has_br_location or has_latam_location) and any(contains_phrase(loc,p) for p in OTHER_FOREIGN_COUNTRIES+FOREIGN_CITY_ONLY):
            return "excluded"
    # A bare "US"/"USA" is an explicit US job location, not unknown Brazil eligibility.
    us_only=any(contains_phrase(loc,p) for p in ("us","usa","united states","u.s.","united states of america"))
    br=any(contains_phrase(loc,p) for p in ("brazil","brasil","br")) or any(contains_phrase(loc,p) for p in BR_CITIES) or "brazil" in jd_geo
    regional=any(contains_phrase(loc,p) for p in LATAM_MARKERS)
    global_eligible=any(contains_phrase(loc,p) for p in GLOBAL_MARKERS)
    # Himalayas uses exactly "Worldwide" when locationRestrictions is empty.
    # Only this feed-specific, explicit API convention proves BR eligibility.
    if fold(job.get("source", "")) == "himalayas" and loc.strip() == "worldwide":
        global_eligible=True
    codes={code for code,aliases in TOKENS.items() if any(contains_phrase(loc,p) for p in aliases)}
    if br:codes.add("BR")
    if country=="BR":
        if us_only and not (br or regional or global_eligible):return "excluded"
        if br or regional or global_eligible:return "eligible"
        if any(contains_phrase(loc,p) for p in OTHER_FOREIGN_COUNTRIES+FOREIGN_CITY_ONLY):return "excluded"
        # If the vacancy explicitly names a different country but not BR/LATAM, don't silently confirm Brazil.
        if codes and "BR" not in codes:return "excluded"
        return "unknown"
    if country=="LATAM":
        if us_only and not (regional or global_eligible or bool(codes & LATAM_CODES)):return "excluded"
        if not (regional or global_eligible or bool(codes & LATAM_CODES)) and any(contains_phrase(loc,p) for p in OTHER_FOREIGN_COUNTRIES+FOREIGN_CITY_ONLY):return "excluded"
        return "eligible" if regional or global_eligible or bool(codes & LATAM_CODES) else "unknown"
    if any(contains_phrase(loc,p) for p in TOKENS.get(country,())) or global_eligible:
        return "eligible"
    if codes and country not in codes:return "excluded"
    return "unknown"

def classify(job,terms,country,mode,days):
    title=fold(job.get("title",""))
    from jd_signals import signals
    evidence=signals(job,", ".join(terms))
    if evidence["spanish_required"]:return "excluded","espanhol_obrigatorio"
    if re.search(r"\b(?:internship|intern|estagio|estagiari[oa])\b",title) and not any(
        re.search(r"\b(?:internship|intern|estagio|estagiari[oa])\b",term) for term in terms):
        return "excluded","cargo"
    # Generic family aliases such as "marketing"/"acquisition" must not
    # admit engineering roles or HR recruitment into an executive search.
    # Protect explicitly named PM/PO/BA/project/marketing management roles,
    # including e.g. "Technical Product Manager - Engineering".
    explicit_target=any(phrase in title for phrase in (
        "product manager", "product owner", "project manager", "program manager",
        "business analyst", "marketing manager", "growth manager", "product marketing manager",
        "gerente de produto", "gerente de projetos", "analista de negocios",
        "gerente de marketing"))
    if NON_TARGET_TITLE.search(title) and not explicit_target:return "excluded","cargo"
    if "talent acquisition" in title and not any("talent acquisition" in term for term in terms):
        return "excluded","cargo"
    # Match the requested role before applying generic negative title tokens.
    # E.g. "Product Manager, Engineering" is a product leadership vacancy.
    title_matches=role_match(title,terms)
    # Reject explicit technical titles; incidental project words in their JD
    # are insufficient evidence of a matching business role.
    if NON_TARGET_TITLE.search(title) and not title_matches:return "excluded","cargo"
    # Missing JDs on adjacent management roles deserve a review queue, not
    # silent exclusion. They are never confirmed automatically.
    adjacent=bool(re.search(r"\b(?:operations|operacoes|strategy|estrategia|transformation|transformacao|program|delivery|commercial|comercial)\b",title)) and bool(re.search(r"\b(?:lead|manager|head|director|gerente|coordenador|coordenadora|especialista)\b",title))
    # JD vocabulary describes collaboration as well as the role itself.
    # A technical lead or designer may mention product roadmaps many times;
    # JD keywords alone must not turn such a title into a PM opening.
    # Preserve established discovery of genuinely adjacent management roles
    # when the JD supplies >=2 specific signals for the requested family.
    # A title alone remains a review item; unrelated technical titles above
    # cannot be rescued by incidental JD vocabulary.
    # The existing project-discovery contract intentionally recognizes
    # transformation/operations leads backed by specific project-delivery JD
    # evidence. Preserve it; product vocabulary in a generic operations role
    # alone does not prove that the role is Product Manager.
    project_jd_match=adjacent and "projects" in requested_families(terms) and bool(evidence.get("family_evidence"))
    uncertain_role=not title_matches and adjacent and not project_jd_match
    if not title_matches and not adjacent:return "excluded","cargo"
    loc=fold(job.get("location",""))
    structured_geo=fold(" ".join(str(job.get(k) or "") for k in ("country","countryCode","countryName","city","state","region","eligibleLocations","remoteRegions")))
    loc=(loc+" "+structured_geo).strip()
    detected=detect_work_mode(job,evidence)
    if mode!="all" and detected not in (None,mode):
        return "excluded","modalidade"
    mode_ok=(mode=="all" or detected==mode)
    geo=geo_verdict(job,country,evidence)
    if geo=="excluded":return "excluded","pais"
    country_ok=geo=="eligible"
    published=parse_date(job.get("published"))
    # A requested publication window requires an actual, verifiable date.
    # Undated listings are available only under "Qualquer período".
    now=datetime.now(timezone.utc)
    if days and published is not None and not now-timedelta(days=days)<=published<=now:
        return "excluded","data"
    unknown=[]
    if uncertain_role:unknown.append("cargo_a_confirmar")
    if not mode_ok:unknown.append("modalidade")
    if not country_ok:unknown.append("pais")
    if days and published is None:unknown.append("data")
    if unknown:return "review",",".join(unknown)
    return "confirmed",""

def analyze_filters(jobs,roles=DEFAULT_ROLES,country="BR",mode="remote",days=30,sort="newest"):
    from jd_signals import signals
    from block4_score import score_job
    from jd_enrichment import valid_listing_jd
    terms=search_terms(roles)
    if len(roles)>5000:raise ValueError("Seleção de cargos acima de 5.000 caracteres; divida a busca em grupos")
    if country not in COUNTRY_NAMES:raise ValueError("País desconhecido")
    if mode not in ("remote","hybrid","onsite","all"):raise ValueError("Regime inválido")
    if days not in (0,1,3,7,15,30,60,90):raise ValueError("Período inválido")
    if sort not in ("score","recommendation","newest","oldest"):raise ValueError("Ordem inválida")
    confirmed=[];review=[];reasons={}
    for j in jobs:
        bucket,reason=classify(j,terms,country,mode,days)
        reasons[bucket+(":"+reason if reason else "")]=reasons.get(bucket+(":"+reason if reason else ""),0)+1
        if bucket in ("confirmed","review"):
            description=str(j.get("description") or "")
            valid=valid_listing_jd(description)
            evidence=signals(j,roles)
            result={**j,"detected_mode":detect_work_mode(j,evidence),"jd_evidence":evidence,
                    "jd_available":valid,"ranking":score_job(j,roles) if valid else {"score":None,"confidence":"jd_indisponivel"},
                    "_listing_jd_hash":hashlib.sha256(description.encode()).hexdigest() if valid else None,
                    "description":""}
            if bucket=="confirmed":confirmed.append(result)
            else:
                result["needs_verification"]=reason.split(",")
                if valid and result["ranking"]:result["ranking"]={**result["ranking"],"method":"local","cost_usd":0}
                review.append(result)
    order=lambda j:parse_date(j.get("published")) or datetime.min.replace(tzinfo=timezone.utc)
    if sort in ("score","recommendation"):
        key=lambda j:((j.get("ranking") or {}).get("score") is not None,(j.get("ranking") or {}).get("score") if (j.get("ranking") or {}).get("score") is not None else -1,-(j.get("ranking") or {}).get("unverified_count",0),order(j))
        confirmed.sort(key=key,reverse=True)
        review.sort(key=key,reverse=True)
    else:
        confirmed.sort(key=order,reverse=sort=="newest")
        review.sort(key=order,reverse=sort=="newest")
    return confirmed,review,reasons

def matches(job,terms,country,mode,days):
    return classify(job,terms,country,mode,days)[0]=="confirmed"

def apply_filters(jobs,roles=DEFAULT_ROLES,country="BR",mode="remote",days=30,sort="newest"):
    return analyze_filters(jobs,roles,country,mode,days,sort)[0]
