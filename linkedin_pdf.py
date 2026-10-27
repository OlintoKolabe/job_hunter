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
    # LinkedIn exports append unrelated sections after certifications. They
    # are not credentials and must not spill into the final CV's education.
    "other": ("honors & awards", "honors-awards", "honors and awards",
              "honras e premios", "honrarias e premios", "publications",
              "publicacoes", "projects", "projetos", "volunteer experience",
              "trabalho voluntario", "organizations", "organizacoes"),
}
HEADINGS = {name: key for key, names in SECTION_NAMES.items() for name in names}
MONTH = r"(?:jan(?:uary|eiro)?|feb(?:ruary)?|fev(?:ereiro)?|mar(?:ch|co|ço)?|apr(?:il)?|abr(?:il)?|may|mai(?:o)?|jun(?:e|ho)?|jul(?:y|ho)?|aug(?:ust)?|ago(?:sto)?|sep(?:tember)?|set(?:embro)?|oct(?:ober)?|out(?:ubro)?|nov(?:ember|embro)?|dec(?:ember)?|dez(?:embro)?)"
DATE_RANGE = re.compile(rf"(?i)^(?:(?:{MONTH})\s+(?:de\s+)?\d{{4}}|\d{{4}})\s*[-–—]\s*(?:present|atual|o momento|current|hoje|(?:{MONTH})\s+(?:de\s+)?\d{{4}}|\d{{4}})(?:\s*\([^)]*\))?$")
ROLE_CUES = re.compile(r"(?i)\b(manager|owner|director|head|lead|analyst|engineer|scientist|designer|developer|intern|specialist|consultant|coordinator|founder|executive|ceo|cto|cmo|professor|gestor|gerente|diretor|analista|engenheir[oa]|cientista|desenvolvedor|estagiari[oa]|coordenador|consultor|especialista|fundador|product|produto|marketing)\b")
EMAIL = re.compile(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", re.I)
PHONE = re.compile(r"(?:\+\d{1,3}[\s-]?)?(?:\(?\d{2,3}\)?[\s-]?)?\d[\d\s().-]{7,}\d")
LINKEDIN = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w%\-]+/?", re.I)


def normal(value):
    text = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split()).strip(":")


def lines_from_text(text):
    result = []
    for line in html.unescape(text).replace("\x00", "").replace("\u200b", "").splitlines():
        cleaned = " ".join(line.split()).strip()
        if cleaned.startswith(("•", "●")):
            cleaned = "• " + cleaned[1:].strip()
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


def unique(lines, limit=60, max_chars=200):
    result = []
    seen = set()
    for line in lines:
        line = line.strip("• \t")
        key = normal(line)
        if line and key not in seen:
            result.append(line[:max_chars])
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


def education_blocks(lines):
    """Keep a LinkedIn institution, qualification and period together.

    A dated academic item ends at the printed (YYYY - YYYY), not at a PDF
    line break. Undated/unrecognized fragments stay separate for user review.
    """
    result, pending = [], []
    end_date = re.compile(r"(?:\s*[·•]\s*)?\(\d{4}\s*[-–]\s*(?:\d{4}|Present|Atual)\)\s*$",re.I)
    for line in lines:
        pending.append(line)
        if end_date.search(line):
            if len(pending)>=2 and len(pending)<=4:
                institution=pending[0]
                credential=" ".join(pending[1:]).replace(" · "," ")
                result.append(institution+" — "+credential)
            else:
                result.extend(pending)
            pending=[]
        elif len(pending)>=4:
            # A malformed block must not swallow the next institution.
            result.extend(pending)
            pending=[]
    result.extend(pending)
    return result


def certification_blocks(lines):
    """Join visually wrapped certification names with parenthesized acronyms."""
    result=[]
    for line in lines:
        if (result and len(result[-1])<=55 and "(" not in result[-1]
            and re.search(r"\([A-Za-z0-9 .+\-/]{2,25}\)\s*$",line)
            and not re.search(r"\b(?:university|universidade|institute|instituto)\b",result[-1],re.I)):
            result[-1] += " " + line
        else:
            result.append(line)
    return result


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
    """Parse roles using heading boundaries, not the two lines before a date.

    LinkedIn writes a company once above several roles; descriptions frequently
    end in a technology stack, and company-level tenure is a separate line.
    None of those lines can safely be used as the next employer.
    """
    def is_duration(line):
        return bool(re.fullmatch(
            r"(?i)\d+\s+(?:anos?|years?|m[eê]s(?:es)?|months?)(?:(?:\s+e)?\s+\d+\s+(?:m[eê]s(?:es)?|months?))?", line))

    def is_title(line):
        return (len(line) <= 110 and bool(ROLE_CUES.search(line))
                and not DATE_RANGE.fullmatch(line) and not line.endswith((".",":",";"))
                and not normal(line).startswith(("stacks:", "skills:", "competencias:")))

    def is_company(line):
        key = normal(line)
        return (2 <= len(line) <= 100 and not is_duration(line)
                and not re.match(r"(?i)^(?:product manager|product owner|project manager|senior manager|head de|head of|diretor de|director of|gerente de|analista de|consultor de|consultant|estagi[aá]rio de|data scientist|software engineer|ceo$|cto$|cmo$)",line)
                and not DATE_RANGE.fullmatch(line)
                and not line.endswith((":",";"))
                and (not line.endswith(".") or re.search(r"(?i)\b(?:inc|ltd|corp|s\.a)\.$",line))
                and not re.search(r"(?i)^(stacks?|ferramentas?|technologies|tecnologias)\s*:",line)
                and not re.search(r"(?i)\b(?:roadmaps?|scrum|kanban|posthog|codex|lovable|figma|jira|confluence|trello)\b",line)
                and not re.search(r"(?i)\b(?:desenvolvi|lider|implemente|gest[aã]o|planej|alinh|cria[cç][aã]o|otimiz|maximiz|processos|atividades)\b",line)
                and not re.search(r"[,;:]",line) and len(line.split()) <= 7 and key not in {"experiencia"})

    dates = [i for i, line in enumerate(lines) if DATE_RANGE.fullmatch(line)]
    headers = []
    previous_company = None
    previous_date = -1
    for index in dates:
        role_index = index - 1
        role = lines[role_index] if role_index >= 0 else ""
        if not is_title(role):
            # Never guess the employer or silently certify a malformed role.
            headers.append((index,index,None,None))
            previous_date=index
            continue
        company = None
        company_start = role_index
        # A new employer heading is immediately above the role, possibly
        # separated by a company-level tenure line.
        j=role_index-1
        while j>previous_date and is_duration(lines[j]):
            j-=1
        if j>previous_date and is_company(lines[j]):
            company=lines[j]
            company_start=j
        elif previous_company:
            company=previous_company
        headers.append((index,company_start,role,company))
        if company:previous_company=company
        previous_date=index

    records, warnings = [], []
    for n,(index,header_start,role,company) in enumerate(headers):
        if not role or not company:
            warnings.append("Cargo ou empresa não identificados com segurança; revise o PDF.")
            continue
        next_start=headers[n+1][1] if n+1<len(headers) else len(lines)
        description = lines[index+1:max(index+1,next_start)]
        # LinkedIn often prints the location before the first achievement.
        if description and ("," in description[0] and
            re.search(r"(?i)(?:brasil|brazil|distrito federal|s[aã]o paulo|goi[aá]s|minas gerais)",description[0])):
            description=description[1:]
        elif (description and len(description[0].split())<=2 and
              not description[0].endswith((".",":",";"))):
            description=description[1:]
        # LinkedIn places location immediately after the date. It is not a
        # professional accomplishment when followed by a marked bullet.
        if (len(description)>1 and not description[0].startswith("• ")
            and description[1].startswith("• ")):
            description=description[1:]
        facts = []
        current = ""
        for line in description:
            if DATE_RANGE.search(line) or LINKEDIN.search(line):
                continue
            marked = line.startswith("• ")
            clean = line[2:].strip() if marked else line.strip()
            if not clean:
                continue
            # The PDF exporter wraps a single factual bullet across multiple
            # physical lines. Keep its exact words and punctuation together.
            if marked and current:
                facts.append(current)
                current = ""
            if current and not marked and (not re.search(r"[.!?]$", current) or
                                           clean[:1].islower()):
                current += " " + clean
            else:
                if current:
                    facts.append(current)
                current = clean
        if current:
            facts.append(current)
        facts = [fact for fact in facts if len(fact) >= 18]
        records.append({"role": role[:200], "company": company[:200],
                        "dates": lines[index][:200], "facts": unique(facts, 25, 500),
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
    result["education"], rejected = clean_credentials(education_blocks(groups["education"]), name, result["skills"])
    result["certifications"], rejected_certs = clean_credentials(certification_blocks(groups["certifications"]), name, result["skills"])
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
