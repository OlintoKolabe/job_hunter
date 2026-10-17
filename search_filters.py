"""Search filters with conservative inclusion: unknown location/mode/date are not matches."""
from datetime import datetime,timezone,timedelta
import re,unicodedata
from urllib.parse import urlsplit

DEFAULT_ROLES="Product Manager, Product Owner, Project Manager, Gerente de Projetos, Product Marketing, Marketing, Growth, Business Analyst, Analista de Negócios, PMO"
LATAM={"brazil","brasil","argentina","chile","colombia","colômbia","peru","uruguay","uruguai","paraguay","paraguai","bolivia","bolívia","ecuador","equador","mexico","méxico","costa rica","panama","panamá","guatemala","el salvador","honduras","nicaragua","nicarágua","dominican republic","república dominicana","venezuela"}
COUNTRIES=[("LATAM","América Latina"),("BR","Brasil"),("AR","Argentina"),("BO","Bolívia"),("CL","Chile"),("CO","Colômbia"),("CR","Costa Rica"),("EC","Equador"),("GT","Guatemala"),("MX","México"),("PA","Panamá"),("PY","Paraguai"),("PE","Peru"),("DO","República Dominicana"),("UY","Uruguai"),("VE","Venezuela"),("US","Estados Unidos"),("CA","Canadá"),("PT","Portugal"),("ES","Espanha"),("GB","Reino Unido"),("GLOBAL","Global")]
COUNTRY_NAMES=dict(COUNTRIES)
TOKENS={"BR":["brazil","brasil"],"AR":["argentina"],"BO":["bolivia"],"CL":["chile"],"CO":["colombia"],"CR":["costa rica"],"EC":["ecuador"],"GT":["guatemala"],"MX":["mexico"],"PA":["panama"],"PY":["paraguay","paraguai"],"PE":["peru"],"DO":["dominican republic","republica dominicana"],"UY":["uruguay","uruguai"],"VE":["venezuela"],"US":["united states","usa","u.s."],"CA":["canada"],"PT":["portugal"],"ES":["spain","espanha"],"GB":["united kingdom","uk","england"]}
REMOTE=["remote","remoto","remota","home office","home-office","homeoffice","home based","work from home","work-from-home","work remotely","work remotely from","fully remote","remote first","remote-first","100% remote","100% remoto","full remote","teletrabalho","telecommute","telecommuting","virtual position","distributed team","anywhere"]
HYBRID=["hybrid","hibrido","híbrido"]
ONSITE=["on-site","onsite","on site","presencial","in-office","in office"]
REGIONAL=["latam","latin america","america latina","americas","remote worldwide","worldwide","anywhere in the world","global remote"]

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
def role_match(title,terms):
    if not terms:return True
    if NON_TARGET_TITLE.search(title):return False
    if any(any(alias in title for alias in TITLE_ALIASES.get(t,[t])) for t in terms):return True
    requested=" ".join(terms)
    areas=[]
    if "product" in requested or "produto" in requested:areas+=["product","produto"]
    if "project" in requested or "projeto" in requested or "pmo" in requested:areas+=["project","projeto","pmo"]
    if "marketing" in requested:areas+=["marketing"]
    if "growth" in requested:areas+=["growth"]
    if "business analyst" in requested or "negocio" in requested:areas+=["business analy","negocio"]
    return any(x in title for x in areas)

def classify(job,terms,country,mode,days):
    title=fold(job.get("title",""))
    if not role_match(title,terms):return "excluded","cargo"
    loc=fold(job.get("location",""))
    # Structured remote/location flags are distinct from a country label.
    remote_flag=job.get("remote")
    workplace=fold(job.get("workplaceType") or job.get("workplace") or job.get("employmentType") or "")
    mode_text=loc+" "+workplace
    if mode=="remote":
        if remote_flag is False or (any(x in mode_text for x in ONSITE) and not any(x in mode_text for x in REMOTE)) or (any(x in workplace for x in HYBRID) and not any(x in mode_text for x in REMOTE)):return "excluded","modalidade"
        mode_ok=remote_flag is True or any(x in mode_text for x in REMOTE)
    elif mode=="hybrid":
        mode_ok=any(x in mode_text for x in HYBRID)
    elif mode=="onsite":
        mode_ok=any(x in mode_text for x in ONSITE)
    else:mode_ok=True
    # Brazilian job boards often use city/state alone, without a country field.
    br_places=("sao paulo","rio de janeiro","belo horizonte","curitiba","porto alegre","brasilia","goiania","recife","fortaleza","salvador","campinas","florianopolis","uberlandia","belem","manaus","vitoria","ribeirao preto")
    brazil_evidence=any(place in loc for place in br_places) or bool(re.search(r"\\b(br|brazil|brasil)\\b",loc))
    if country=="GLOBAL":country_ok=True
    elif country=="LATAM":
        country_ok=any(fold(x) in loc for x in LATAM) or any(x in loc for x in REGIONAL) or brazil_evidence
    else:
        country_ok=(brazil_evidence if country=="BR" else any(x in loc for x in TOKENS.get(country,[]))) or any(x in loc for x in REGIONAL)
    # Known foreign-only locations must not be rebranded as Brazil-eligible.
    if country in ("BR","LATAM") and loc and not country_ok and any(x in loc for x in ("united states only","us only","europe only","canada only")):
        return "excluded","pais"
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
    terms=search_terms(roles)
    if len(roles)>700:raise ValueError("Filtros de cargo excessivamente longos")
    if country not in COUNTRY_NAMES:raise ValueError("País desconhecido")
    if mode not in ("remote","hybrid","onsite","all"):raise ValueError("Regime inválido")
    if days not in (0,1,3,7,15,30,60,90):raise ValueError("Período inválido")
    if sort not in ("newest","oldest"):raise ValueError("Ordem inválida")
    confirmed=[];review=[];reasons={}
    for j in jobs:
        bucket,reason=classify(j,terms,country,mode,days)
        reasons[bucket+(":"+reason if reason else "")]=reasons.get(bucket+(":"+reason if reason else ""),0)+1
        if bucket=="confirmed":confirmed.append(j)
        elif bucket=="review":review.append({**j,"needs_verification":reason.split(",")})
    order=lambda j:parse_date(j.get("published")) or datetime.min.replace(tzinfo=timezone.utc)
    confirmed.sort(key=order,reverse=sort=="newest")
    review.sort(key=order,reverse=sort=="newest")
    return confirmed,review,reasons

def matches(job,terms,country,mode,days):
    return classify(job,terms,country,mode,days)[0]=="confirmed"

def apply_filters(jobs,roles=DEFAULT_ROLES,country="BR",mode="remote",days=30,sort="newest"):
    return analyze_filters(jobs,roles,country,mode,days,sort)[0]
