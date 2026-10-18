"""Search filters with conservative inclusion: unknown location/mode/date are not matches."""
from datetime import datetime,timezone,timedelta
import re,unicodedata
from urllib.parse import urlsplit

DEFAULT_ROLES="Product Manager, Product Owner, Project Manager, Gerente de Projetos, Product Marketing, Marketing, Growth, Business Analyst, Analista de Negócios, PMO"
LATAM={"brazil","brasil","argentina","chile","colombia","colômbia","peru","uruguay","uruguai","paraguay","paraguai","bolivia","bolívia","ecuador","equador","mexico","méxico","costa rica","panama","panamá","guatemala","el salvador","honduras","nicaragua","nicarágua","dominican republic","república dominicana","venezuela"}
COUNTRIES=[("LATAM","América Latina"),("BR","Brasil"),("AR","Argentina"),("BO","Bolívia"),("CL","Chile"),("CO","Colômbia"),("CR","Costa Rica"),("EC","Equador"),("GT","Guatemala"),("MX","México"),("PA","Panamá"),("PY","Paraguai"),("PE","Peru"),("DO","República Dominicana"),("UY","Uruguai"),("VE","Venezuela"),("US","Estados Unidos"),("CA","Canadá"),("PT","Portugal"),("ES","Espanha"),("GB","Reino Unido"),("GLOBAL","Global")]
COUNTRY_NAMES=dict(COUNTRIES)
TOKENS={"BR":["brazil","brasil"],"AR":["argentina"],"BO":["bolivia"],"CL":["chile"],"CO":["colombia"],"CR":["costa rica"],"EC":["ecuador"],"GT":["guatemala"],"MX":["mexico"],"PA":["panama"],"PY":["paraguay","paraguai"],"PE":["peru"],"DO":["dominican republic","republica dominicana"],"UY":["uruguay","uruguai"],"VE":["venezuela"],"US":["united states","usa","u.s."],"CA":["canada"],"PT":["portugal"],"ES":["spain","espanha"],"GB":["united kingdom","uk","england"]}
REMOTE=["remote","remoto","remota","home office","home-office","homeoffice","home based","work from home","work-from-home","work remotely","work remotely from","fully remote","remote first","remote-first","100% remote","100% remoto","full remote","teletrabalho","telecommute","telecommuting","remotely","trabalho remoto","trabalho a distancia","trabalho à distância","trabalho em casa","trabalho de casa","any location","work anywhere","work at home","virtual position","distributed team","anywhere"]
HYBRID=["hybrid","hibrido","híbrido","flexible hybrid","modelo hibrido","parcialmente presencial"]
ONSITE=["on-site","onsite","on site","presencial","in-office","in office","office based","office-based","on premises"]
REGIONAL=["latam","latin america","america latina","americas","remote worldwide","worldwide","anywhere in the world","global remote","remote latin america","south america","america do sul","americas remote","latinoamerica","latinoamerica remote"]

def fold(x):
    return unicodedata.normalize("NFKD",str(x or "")).encode("ascii","ignore").decode().lower()

def search_terms(value):
    raw=[x.strip() for x in re.split(r"[,;\n]+",str(value or ""))]
    return [fold(x) for x in raw if x.strip()][:25]

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
    if NON_TARGET_TITLE.search(title):return False
    families=requested_families(terms)
    if any(alias in title for fam in families for alias in ROLE_FAMILIES[fam]):return True
    # Any custom free-text role the user typed still matches literally.
    return any(len(t)>=3 and t in title for t in terms)
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
    for key in ("workplaceType","workArrangement","remoteType","workMode","workplace"):
        value=job.get(key)
        if isinstance(value,str):
            result=detect(normalize(value))
            if result:return result
    # False does not establish onsite: it can also mean hybrid or unspecified.
    if job.get("remote") is True:return "remote"
    result=detect(normalize(job.get("location")))
    if result:return result
    jd=evidence.get("work_evidence") or []
    if "onsite_only" in jd:return "onsite"
    if "remote" in jd:return "remote"
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
    if any(contains_phrase(loc,p) for p in FOREIGN_ONLY_MARKERS) or "foreign_only" in jd_geo:
        if country in ("BR","LATAM"):return "excluded"
    if country=="BR" and any(contains_phrase(loc,p) for p in BRAZIL_EXCLUSIONS):
        return "excluded"
    # A bare "US"/"USA" is an explicit US job location, not unknown Brazil eligibility.
    us_only=any(contains_phrase(loc,p) for p in ("us","usa","united states","u.s.","united states of america"))
    br=any(contains_phrase(loc,p) for p in ("brazil","brasil","br")) or any(contains_phrase(loc,p) for p in BR_CITIES) or "brazil" in jd_geo
    regional=any(contains_phrase(loc,p) for p in LATAM_MARKERS)
    global_eligible=any(contains_phrase(loc,p) for p in GLOBAL_MARKERS)
    codes={code for code,aliases in TOKENS.items() if any(contains_phrase(loc,p) for p in aliases)}
    if br:codes.add("BR")
    if country=="BR":
        if us_only and not (br or regional or global_eligible):return "excluded"
        if br or regional or global_eligible:return "eligible"
        # If the vacancy explicitly names a different country but not BR/LATAM, don't silently confirm Brazil.
        if codes and "BR" not in codes:return "excluded"
        return "unknown"
    if country=="LATAM":
        if us_only and not (regional or global_eligible or bool(codes & LATAM_CODES)):return "excluded"
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
    if NON_TARGET_TITLE.search(title):return "excluded","cargo"
    if not role_match(title,terms) and not evidence["family_evidence"]:return "excluded","cargo"
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
    date_ok=not days or (published is not None and datetime.now(timezone.utc)-timedelta(days=days)<=published<=datetime.now(timezone.utc)+timedelta(days=1))
    if days and published and not date_ok:return "excluded","data"
    unknown=[]
    if not mode_ok:unknown.append("modalidade")
    if not country_ok:unknown.append("pais")
    if days and not published:unknown.append("data")
    if unknown:return "review",",".join(unknown)
    return "confirmed",""

def analyze_filters(jobs,roles=DEFAULT_ROLES,country="BR",mode="remote",days=30,sort="newest"):
    from jd_signals import signals
    from block4_score import score_job
    terms=search_terms(roles)
    if len(roles)>700:raise ValueError("Filtros de cargo excessivamente longos")
    if country not in COUNTRY_NAMES:raise ValueError("País desconhecido")
    if mode not in ("remote","hybrid","onsite","all"):raise ValueError("Regime inválido")
    if days not in (0,1,3,7,15,30,60,90):raise ValueError("Período inválido")
    if sort not in ("score","newest","oldest"):raise ValueError("Ordem inválida")
    confirmed=[];review=[];reasons={}
    for j in jobs:
        bucket,reason=classify(j,terms,country,mode,days)
        reasons[bucket+(":"+reason if reason else "")]=reasons.get(bucket+(":"+reason if reason else ""),0)+1
        if bucket=="confirmed":confirmed.append({**j,"detected_mode":detect_work_mode(j,signals(j,roles)),"jd_evidence":signals(j,roles),"ranking":score_job(j,roles),"description":""})
        elif bucket=="review":review.append({**j,"detected_mode":detect_work_mode(j,signals(j,roles)),"jd_evidence":signals(j,roles),"description":"","needs_verification":reason.split(",")})
    order=lambda j:parse_date(j.get("published")) or datetime.min.replace(tzinfo=timezone.utc)
    if sort=="score":
        key=lambda j:(j["ranking"]["score"],j["ranking"]["confidence"]=="completa",order(j))
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
