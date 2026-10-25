"""Conservative, local-only extraction of LinkedIn-exported PDF resumes.

The returned fields are suggestions for review, never verified evidence.
No uploaded PDF or extracted text is sent to another service or saved here.
"""
from io import BytesIO
import html
import re
import unicodedata

from pypdf import PdfReader

MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_PAGES = 15

SECTION_NAMES = {
    "contact": ("contact", "contato", "contact information", "informacoes de contato"),
    "summary": ("summary", "resumo", "sobre", "about", "perfil", "professional summary"),
    "experience": ("experience", "experiencia", "experiencia profissional", "professional experience", "work experience"),
    "education": ("education", "formacao academica", "formacao", "academic background"),
    "skills": ("skills", "competencias", "aptidoes", "principais competencias", "top skills"),
    "certifications": ("licenses & certifications", "licenses and certifications", "licencas e certificados", "certifications", "certificacoes", "certificados"),
    "languages": ("languages", "idiomas"),
}
HEADINGS = {name: key for key, names in SECTION_NAMES.items() for name in names}
MONTH = r"(?:jan(?:uary|eiro)?|feb(?:ruary|vereiro)?|mar(?:ch|co)?|apr(?:il)?|abr(?:il)?|may|mai(?:o)?|jun(?:e|ho)?|jul(?:y|ho)?|aug(?:ust)?|ago(?:sto)?|sep(?:tember|tembro)?|oct(?:ober)?|out(?:ubro)?|nov(?:ember|embro)?|dec(?:ember|embro)?|dez(?:embro)?)"
DATE_RANGE = re.compile(rf"(?i)\b(?:(?:{MONTH})\s+(?:de\s+)?\d{{4}}|\d{{4}})\s*[-–—]\s*(?:present|atual|o momento|current|hoje|(?:{MONTH})\s+(?:de\s+)?\d{{4}}|\d{{4}})\b")
ROLE_CUES = re.compile(r"(?i)\b(manager|owner|director|head|lead|analyst|engineer|scientist|designer|developer|intern|specialist|consultant|coordinator|founder|executive|gerente|diretor|analista|engenheir[oa]|cientista|desenvolvedor|estagiari[oa]|coordenador|consultor|especialista|fundador|product|produto|marketing)\b")
EMAIL = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.I)
PHONE = re.compile(r"(?:\+\d{1,3}[\s-]?)?(?:\(?\d{2,3}\)?[\s-]?)?\d[\d\s().-]{7,}\d")
LINKEDIN = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w%\-]+/?", re.I)


def normal(value):
    text = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split()).strip(":")


def lines_from_text(text):
    result = []
    for line in html.unescape(text).replace("\x00", "").replace("\u200b", "").splitlines():
        cleaned = " ".join(line.split()).strip("• \t")
        if cleaned and not re.fullmatch(r"(?:Page|Página)\s+\d+(?:\s+(?:of|de)\s+\d+)?", cleaned, re.I):
            result.append(cleaned[:1200])
    return result


def sections_from_lines(lines):
    sections = {key: [] for key in SECTION_NAMES}
    before = []
    active = None
    for line in lines:
        key = HEADINGS.get(normal(line))
        if key:
            active = key
        elif active:
            sections[active].append(line)
        else:
            before.append(line)
    return before, sections


def unique(lines, limit=60):
    result = []
    seen = set()
    for line in lines:
        line = line.strip("• \t")
        key = normal(line)
        if line and key not in seen:
            result.append(line[:200])
            seen.add(key)
        if len(result) >= limit:
            break
    return result


def simple_list(lines, limit=60):
    result = []
    for line in lines:
        if normal(line).startswith(("page ", "pagina ")):
            continue
        if len(line) < 150 and re.search(r"\s[•·]\s|\s[|]\s", line):
            result.extend(re.split(r"\s[•·|]\s", line))
        else:
            result.append(line)
    return unique(result, limit)


def clean_summary(lines):
    return " ".join(html.unescape(" ".join(lines)).replace("\\", " ").split())[:1500]


def clean_credentials(lines, name, skills):
    """Reject LinkedIn sidebar spillover, never infer an academic credential."""
    name_key = normal(name)
    name_words = [x for x in re.findall(r"\w+", name_key) if len(x)>1]
    skill_keys = {normal(x) for x in skills}
    sidebar_technologies = {"python", "sql", "databricks", "power bi", "pyspark",
                            "spark", "streamlit", "n8n", "generative ai & process automation"}
    result, rejected = [], []
    footer_started = False
    for entry in simple_list(lines):
        key = normal(entry)
        words = [x for x in re.findall(r"\w+", key) if len(x)>1]
        repeated_name = (len(name_words)>=2 and len(words)>=2 and
                         words[:2]==name_words[:2] and
                         sum(w in name_words for w in words)>=min(3,len(words)) and
                         sum(w in name_words for w in words)/len(words)>=.75)
        if repeated_name:
            footer_started = True
        is_sidebar = (footer_started or key in skill_keys or key in sidebar_technologies or
                      EMAIL.search(entry) or LINKEDIN.search(entry) or
                      "@" in entry or re.search(r"(?i)data scientist\s*&\s*data engineer",entry))
        if len(entry.strip()) < 4 or is_sidebar:
            rejected.append(entry)
        else:
            result.append(entry)
    return result, rejected


def experience_from_lines(lines):
    records = []
    warnings = []
    dates = [i for i, line in enumerate(lines) if DATE_RANGE.search(line)]
    for n, index in enumerate(dates):
        # LinkedIn PDF export convention: company and role immediately precede
        # a date range, followed by location and description.
        first = lines[index - 2] if index >= 2 else ""
        second = lines[index - 1] if index >= 1 else ""
        if not first or not second or DATE_RANGE.search(first) or DATE_RANGE.search(second):
            warnings.append("Há uma experiência cujo cargo ou empresa precisa ser conferido.")
            continue
        if ROLE_CUES.search(first) and not ROLE_CUES.search(second):
            role, company = first, second
        else:
            company, role = first, second
        next_start = (dates[n + 1] - 2) if n + 1 < len(dates) else len(lines)
        description = lines[index + 1:max(index + 1, next_start)]
        facts = []
        for line in description:
            if len(line) >= 18 and not DATE_RANGE.search(line) and not LINKEDIN.search(line):
                # Never synthesize achievements or expand abbreviations.
                facts.append(line[:500])
        if not ROLE_CUES.search(role):
            warnings.append("Confira cargo e empresa de uma experiência importada.")
        records.append({"role": role[:200], "company": company[:200],
                        "dates": lines[index][:200], "facts": unique(facts, 25),
                        "verified": False})
    if lines and not records:
        warnings.append("A seção de experiências não pôde ser estruturada; confira o PDF e complete apenas o que faltar.")
    return records[:40], warnings


def parse_profile_text(text):
    lines = lines_from_text(text)
    if len(" ".join(lines)) < 100:
        raise ValueError("PDF sem texto suficiente. Exporte o currículo diretamente do LinkedIn, sem digitalizá-lo.")
    preamble, groups = sections_from_lines(lines)
    email = EMAIL.search(text)
    linked = LINKEDIN.search(text)
    phones = [match.group().strip() for match in PHONE.finditer("\n".join(groups["contact"]))]
    name = next((line for line in preamble[:5] if 2 <= len(line.split()) <= 6
                 and len(line) < 100 and not EMAIL.search(line) and not LINKEDIN.search(line)), "")
    experience, warnings = experience_from_lines(groups["experience"])
    result = {
        "name": name,
        "phone": phones[0] if phones else "",
        "linkedin": linked.group().rstrip("/") if linked else "",
        "summary": clean_summary(groups["summary"]),
        "experience": experience,
        "education": [],
        "skills": simple_list(groups["skills"]),
        "certifications": simple_list(groups["certifications"]),
        "languages": simple_list(groups["languages"]),
    }
    result["education"], rejected = clean_credentials(groups["education"], name, result["skills"])
    result["certifications"], rejected_certs = clean_credentials(groups["certifications"], name, result["skills"])
    if rejected or rejected_certs:
        warnings.append("Fragmentos do cabeçalho ou competências foram excluídos das credenciais; confira a formação antes de confirmar.")
    employers = {normal(row["company"]) for row in experience}
    for fragment in [*rejected, *rejected_certs]:
        headline = re.search(r"\b@([\w][\w .&-]{1,50})", fragment)
        if headline and normal(headline.group(1)) not in employers:
            warnings.append("Há uma empresa mencionada no cabeçalho sem experiência estruturada; confira se alguma atuação ficou de fora.")
            break
    if not groups["experience"]:
        warnings.append("Não foi encontrada uma seção de experiências reconhecível.")
    if experience and not any(row["facts"] for row in experience):
        warnings.append("O PDF não trouxe realizações detalhadas; essas evidências poderão ser complementadas posteriormente.")
    return {"profile": result, "email_detected": email.group() if email else None,
            "warnings": unique(warnings), "extracted_sections":
                [key for key, value in groups.items() if value]}


def parse_linkedin_pdf(data):
    if not isinstance(data, bytes) or not data.startswith(b"%PDF-"):
        raise ValueError("Envie um PDF válido exportado do LinkedIn.")
    if len(data) > MAX_PDF_BYTES:
        raise ValueError("O PDF deve ter no máximo 8 MB.")
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ValueError("O PDF está protegido por senha; exporte uma cópia desbloqueada do LinkedIn.")
        if not 1 <= len(reader.pages) <= MAX_PAGES:
            raise ValueError("O PDF deve ter de 1 a 15 páginas.")
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Não foi possível ler este PDF. Faça uma nova exportação no LinkedIn.") from exc
    return {**parse_profile_text(text), "pages": len(reader.pages)}
