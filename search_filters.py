"""Search filters with conservative inclusion: unknown location/mode/date are not matches."""
from datetime import datetime,timezone,timedelta
import re,unicodedata
from urllib.parse import urlsplit

DEFAULT_ROLES="Product Manager, Product Owner, Project Manager, Gerente de Projetos, Product Marketing, Marketing, Growth, Business Analyst, Analista de Negócios, PMO"
LATAM={"brazil","brasil","argentina","chile","colombia","colômbia","peru","uruguay","uruguai","paraguay","paraguai","bolivia","bolívia","ecuador","equador","mexico","méxico","costa rica","panama","panamá","guatemala","el salvador","honduras","nicaragua","nicarágua","dominican republic","república dominicana","venezuela"}
COUNTRIES=[("LATAM","América Latina"),("BR","Brasil"),("AR","Argentina"),("BO","Bolívia"),("CL","Chile"),("CO","Colômbia"),("CR","Costa Rica"),("EC","Equador"),("GT","Guatemala"),("MX","México"),("PA","Panamá"),("PY","Paraguai"),("PE","Peru"),("DO","República Dominicana"),("UY","Uruguai"),("VE","Venezuela"),("US","Estados Unidos"),("CA","Canadá"),("PT","Portugal"),("ES","Espanha"),("GB","Reino Unido"),("GLOBAL","Global")]
COUNTRY_NAMES=dict(COUNTRIES)
TOKENS={"BR":["brazil","brasil"],"AR":["argentina"],"BO":["bolivia"],"CL":["chile"],"CO":["colombia"],"CR":["costa rica"],"EC":["ecuador"],"GT":["guatemala"],"MX":["mexico"],"PA":["panama"],"PY":["paraguay","paraguai"],"PE":["peru"],"DO":["dominican republic","republica dominicana"],"UY":["uruguay","uruguai"],"VE":["venezuela"],"US":["united states","usa","u.s."],"CA":["canada"],"PT":["portugal"],"ES":["spain","espanha"],"GB":["united kingdom","uk","england"]}
REMOTE=["remote","remoto","remota","home office","home-office","work from home","work-from-home","anywhere","teletrabalho"]
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

def matches(job,terms,country,mode,days):
    title=fold(job.get("title",""))
    if terms and not any(t in title for t in terms):return False
    loc=fold(job.get("location",""))
    if not loc:return False
    # Require actual evidence for the selected work arrangement.
    if mode=="remote" and not any(x in loc for x in REMOTE):return False
    if mode=="hybrid" and not any(x in loc for x in HYBRID):return False
    if mode=="onsite" and not any(x in loc for x in ONSITE):return False
    if mode not in ("remote","hybrid","onsite","all"):return False
    if country=="GLOBAL":pass
    elif country=="LATAM":
        if not(any(fold(x) in loc for x in LATAM) or any(x in loc for x in REGIONAL)):return False
    else:
        if country not in TOKENS:return False
        if not(any(x in loc for x in TOKENS[country]) or any(x in loc for x in REGIONAL)):return False
    if days:
        published=parse_date(job.get("published"))
        if not published:return False
        if published<datetime.now(timezone.utc)-timedelta(days=days):return False
        if published>datetime.now(timezone.utc)+timedelta(days=1):return False
    return True

def apply_filters(jobs,roles=DEFAULT_ROLES,country="BR",mode="remote",days=30,sort="newest"):
    terms=search_terms(roles)
    if len(roles)>700:raise ValueError("Filtros de cargo excessivamente longos")
    if country not in COUNTRY_NAMES:raise ValueError("País desconhecido")
    if mode not in ("remote","hybrid","onsite","all"):raise ValueError("Regime inválido")
    if days not in (0,1,3,7,15,30,60,90):raise ValueError("Período inválido")
    if sort not in ("newest","oldest"):raise ValueError("Ordem inválida")
    found=[j for j in jobs if matches(j,terms,country,mode,days)]
    found.sort(key=lambda j:parse_date(j.get("published")) or datetime.min.replace(tzinfo=timezone.utc),reverse=sort=="newest")
    return found
