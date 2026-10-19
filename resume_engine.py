"""Job Hunter Block 5: evidence-grounded, ATS-readable draft generator.

No AI API calls. This is a baseline for independent audit, NOT an ATS-rank guarantee.
Do not infer unlisted skills or accomplishments.
"""
from __future__ import annotations
import hashlib
import html
import io
import re
from datetime import datetime, timezone
from docx import Document
from docx.shared import Pt

ENGINE_VERSION = "block5-traceable-rewrite-v5"
CV_DOCUMENT_VERSION = "job-hunter-cv-provenance-v1"
CONTACT = {"name":"Olinto Manso Pereira","email":"olinto_manso@hotmail.com",
           "phone":"+55 64 98116-4936","location":"Caldas Novas, GO, Brasil",
           "linkedin":"https://www.linkedin.com/in/olintomanso"}
# Exact factual paraphrases anchored in the LinkedIn document (Profile 11.pdf).
EXPERIENCE = [
    {"role":"Fundador","company":"Centauro.life","dates":"abr 2026 – atual",
     "facts":["Fundação de plataforma de terapêutica digital e treinamento cognitivo gamificado."]},
    {"role":"Consultor de produtos","company":"Neocoder / LiberPay","dates":"mai 2025 – set 2026",
     "facts":["Criação e gestão de roadmaps de produto, priorizando impacto e valor percebido.",
              "Implementação de Scrum e Kanban e alinhamento entre tecnologia, design e negócios.",
              "Definição de hipóteses e indicadores para experimentos de growth, retenção e ativação.",
              "Interface com stakeholders para traduzir objetivos de negócio em entregas de produto.",
              "Consultoria estratégica para produto B2B de pagamentos com criptoativos e stablecoins.",
              "Ferramentas documentadas: Jira, Confluence, Azure DevOps, Trello, Miro, Figma e PostHog."]},
    {"role":"Head de projetos e processos","company":"Neocoder","dates":"fev 2025 – ago 2026",
     "facts":["Padronização de processos e frameworks de gestão de projetos e portfólio.",
              "Implementação de Scrum e Kanban para melhorar fluxos de trabalho.",
              "Definição de métricas de acompanhamento e gestão de recursos.",
              "Liderança e orientação de equipes multidisciplinares e stakeholders."]},
    {"role":"CEO","company":"Top Saúde Clínicas Médicas","dates":"fev 2020 – fev 2025",
     "facts":["Estruturação do negócio, dos processos administrativos, comerciais e de marketing.",
              "Planejamento e implementação de laboratório de análises clínicas com parceiros.",
              "Liderança do desenvolvimento do SysTop, produto interno de inteligência de negócios.",
              "Gestão de marketing digital, geração de leads e análises de viabilidade de negócios."]},
    {"role":"Product Manager","company":"Hexagon Mining","dates":"ago 2023 – out 2024",
     "facts":["Gestão do Mission Manager, produto para tráfego de veículos autônomos em mineração.",
              "Priorização de backlog e definição de histórias de usuários em colaboração com stakeholders.",
              "Participação no planejamento de sprints e acompanhamento do desenvolvimento técnico.",
              "Melhorias orientadas por testes de confiabilidade e usabilidade."]},
    {"role":"Product Manager","company":"Stefanini Brasil / Hexagon Mining","dates":"mai 2023 – ago 2023",
     "facts":["Atuação em produto na solução Mission Manager da Hexagon Mining."]},
    {"role":"Fundador / Product Manager","company":"Kolabe","dates":"mai 2018 – jan 2023",
     "facts":["Product discovery, pesquisa de mercado e validação de proposta de valor com usuários.",
              "Definição de roadmaps para aplicações web e mobile e gestão de delivery e orçamento.",
              "Uso de KPIs, OKRs, testes A/B e análises de Google Ads e Analytics.",
              "Priorização de backlog com feedback de usuários e NPS.",
              "Criação de jornadas, protótipos e interfaces no Figma."]},
    {"role":"Product Owner","company":"Dotz Inc. / Meu Varejo","dates":"ago 2022 – dez 2022",
     "facts":["Product Owner de plataforma de campanhas segmentadas de CRM e inteligência de varejo.",
              "Foco em recorrência, frequência, ticket médio e fidelização.",
              "Desenvolvimento de painéis analíticos e jornadas de produto."]},
    {"role":"Diretor de desenvolvimento corporativo e de negócios","company":"Lagoa Parques e Hotéis","dates":"jan 2015 – jan 2020",
     "facts":["Governança corporativa, viabilidade econômica e projetos estratégicos.",
              "Reestruturação de processos e gestão de equipes multidisciplinares."]},
    {"role":"Diretor de marketing","company":"Lagoa Parques e Hotéis","dates":"jan 2015 – jan 2018",
     "facts":["Gestão de marketing, campanhas omnichannel, CRM e funil comercial.",
              "Pesquisas de mercado, lançamentos e estratégias de expansão."]},
    {"role":"Diretor de comunicação de marketing","company":"Companhia de Negócios","dates":"jun 2014 – dez 2014",
     "facts":["Planejamento estratégico de marketing, orçamento e suporte às equipes comerciais."]},
    {"role":"Gerente Corporativo de Marketing","company":"Grupo Privé","dates":"jun 2012 – mai 2014",
     "facts":["Gestão de marketing para hospitalidade, entretenimento e construção civil."]},
    {"role":"Gestor de Marketing regional","company":"Aviva","dates":"nov 2011 – mai 2012",
     "facts":["Gestão de campanhas, branding, pesquisa de mercado e orçamento de marketing."]},
    {"role":"CEO","company":"Digital Design Comunicação","dates":"jan 2000 – out 2011",
     "facts":["Gestão de agência de comunicação, branding, campanhas e projetos para clientes corporativos."]}
]
# Additional career facts verified against the complete 10-page LinkedIn profile.
# Append, never renumber existing fact IDs: cached/source trace references depend on them.
EXPERIENCE[1]["facts"].extend([
    "Apoio ao posicionamento de produto Web3, com foco em UX e integrações B2B.",
    "Acompanhamento de churn, margem e resultados financeiros para priorização do produto.",
    "Ferramentas documentadas: Aha!, Hotjar, Codex, Claude Code e Lovable.",
])
EXPERIENCE[2]["facts"].extend([
    "Gestão de recursos e priorização de portfólio de projetos de marketing para Web3.",
    "Atuação em conformidade, qualidade, gestão de mudanças e mitigação de riscos.",
])
EXPERIENCE[3]["facts"].extend([
    "Planejamento de viabilidade econômica e estruturação do plano de negócios da clínica.",
    "Estratégias de geração de leads com Google Ads e campanhas de conteúdo.",
    "Desenvolvimento do SysTop com informação operacional e inteligência de negócios.",
])
EXPERIENCE[4]["facts"].extend([
    "Testes e melhorias de usabilidade e confiabilidade com equipes em Morton e Perth.",
])
EXPERIENCE[6]["facts"].extend([
    "Growth Hacking, Google Analytics, Google Ads, Social Media Ads e SEO para produtos digitais.",
    "Gestão de comunidades e redes sociais, com foco em engajamento.",
    "Evolução de design systems e padrões de interação web e mobile.",
    "Gestão do delivery e orçamento de aplicações web e mobile ao longo do ciclo do produto.",
    "Validação de modelo de negócio e pesquisa de mercado em startup selecionada no programa Centelha.",
])
EXPERIENCE[7]["facts"].extend([
    "Painéis de dados com comportamentos de clientes, SKUs, marcas e categorias do varejo.",
])
EXPERIENCE[8]["facts"].extend([
    "Modelo de governança corporativa com marca, sustentabilidade e relatórios de compliance.",
    "Supervisão de projeto de praia artificial com retorno financeiro de R$ 5 milhões na primeira temporada.",
])
EXPERIENCE[9]["facts"].extend([
    "Estratégias de campanhas de marketing digital e tradicional para hotéis e parques.",
    "Gestão de funil de vendas, CRM e campanhas omnichannel para fidelização de clientes.",
    "Reestruturação comercial com receita triplicada em três anos e redução de rotatividade em 45%.",
])
EXPERIENCE[10]["facts"].extend([
    "Planejamento de negócios imobiliários e viabilidade econômica para novos empreendimentos.",
    "Direção de orçamento de marketing, campanhas digitais e suporte comercial.",
])
EXPERIENCE[11]["facts"].extend([
    "Lançamento de produtos de hotelaria e entretenimento, com integração de branding e trade marketing.",
    "Lançamento do Privé Riviera Park Hotel, com reservas 58% acima do orçamento no primeiro mês.",
    "Gestão de equipe interna de criação e campanhas de marketing promocional e de guerrilha.",
])
EXPERIENCE[12]["facts"].extend([
    "Gestão regional de marketing em Goiás, Minas Gerais e Distrito Federal, com orçamento superior a R$ 7 milhões.",
    "Supervisão de criação e equipe interna responsável por cerca de 2.000 demandas de design ao ano.",
    "Branding, campanhas digitais e tradicionais, parcerias comerciais e ações de crossbranding.",
])
EXPERIENCE[13]["facts"].extend([
    "Planejamento de branding, mídia, orçamento e campanhas para clientes corporativos.",
    "Estratégias de marketing e merchandising em pontos de venda.",
    "Publicidade em rádio, televisão, mídia impressa, mídia externa e campanhas promocionais.",
])

EDUCATION = ["MBA em Marketing — Universidade de São Paulo (2015–2016)",
             "MBA em Administração e Gestão — Fundação Getulio Vargas (2001–2003)",
             "Graduação em Odontologia — Universidade de São Paulo (1996–1999)",
             "Professional Scrum Product Owner I (PSPO I)"]
STOP={"the","and","with","for","that","from","have","will","are","this","your","our",
      "para","com","que","dos","das","uma","por","como","nos","nas","mais","sobre",
      "experiencia","experience","required","requirements","responsibilities","years"}
def relevant_jd_text(value):
    """Normalize nested HTML and focus on actual responsibilities/requirements.

    The raw JD remains hashed and cached unchanged. Marketing/benefit boilerplate
    must not outweigh the requirements in ranking and model prompts.
    """
    text=str(value or "")
    for _ in range(3):
        decoded=html.unescape(text)
        if decoded==text:break
        text=decoded
    text=re.sub(r"<\s*(?:br|/p|/li|/div|/h[1-6]|/section)\b[^>]*>","\n",text,flags=re.I)
    text=re.sub(r"<[^>]+>"," ",text)
    text=re.sub(r"[ \t]+"," ",text)
    text=re.sub(r"\n\s+","\n",text)
    anchors=[r"\brole expectations\s*:",r"\bresponsibilities\s*:",
             r"\bwe are looking for\b",r"\bcomo\s+.{0,95}\s+voc[eê]\s+vai\s*:"]
    for pattern in anchors:
        found=re.search(pattern,text,re.I)
        if found:
            text=text[found.start():]
            break
    endings=[r"\bwhy apply through\b",r"\bhow jobgether works\b",r"\bwhy work for us\b",
             r"\bbenef[ií]cios\s*:",r"\bour benefits\s*:",
             r"\bequal opportunity employer\b",r"\ba radix est[aá] sempre\b"]
    tail=[m.start() for pattern in endings for m in re.finditer(pattern,text,re.I)]
    if tail and min(tail)>60:text=text[:min(tail)]
    return text.strip()

def words(value):
    value=relevant_jd_text(value).lower()
    return {w for w in re.findall(r"[a-záàâãéêíóôõúüç0-9]{3,}",value) if w not in STOP}
def chronology_index(item):
    """Actual start dates, including overlapping employment."""
    starts={
      "Centauro.life":(2026,4),"Neocoder / LiberPay":(2025,5),"Neocoder":(2025,2),
      "Hexagon Mining":(2023,8),"Stefanini Brasil / Hexagon Mining":(2023,5),
      "Dotz Inc. / Meu Varejo":(2022,8),"Top Saúde Clínicas Médicas":(2020,2),
      "Kolabe":(2018,5),"Lagoa Parques e Hotéis":(2015,1),
      "Companhia de Negócios":(2014,6),"Grupo Privé":(2012,6),
      "Aviva":(2011,11),"Digital Design Comunicação":(2000,1)}
    return starts[item["company"]]

# Domain concepts derived from documented claims, not inferred credentials.
# The same rule set applies to every vacancy; role-family terms only guide selection.
TOPICS={
 "analysis":("business analyst","business analysis","analista de negócios","levantamento de requisitos","requisitos","requirements","user stories","histórias de usuários","casos de uso","use cases","functional","funcionais","product analyst"),
 "agility":("scrum","kanban","scrum master","backlog","sprint","planning","agile","ágil","agilidade","cerimônias","saFe"),
 "project":("projetos","project","pmo","cronograma","prazo","prazos","delivery","implantação","implementação","recursos","portfolio","portfólio","risk","riscos","escopo"),
 "product":("product","produto","roadmap","discovery","priorização","priorizar","prototip","usuários","user research","design"),
 "growth":("growth","marketing","tráfego","ads","funil","leads","crm","campanha","campaign","paid media","performance","advertising","mídia","media budget","retenção","retention","churn","ltv","upsell","cross-sell","vendas","comercial","acquisition"),
 "data":("indicadores","analytics","dados","metrics","métricas","kpi","reports","relatórios","dashboards","análise","analysis","business intelligence","data-driven","data analysis"),
 "people":("stakeholders","equipe","times","liderança","facilitar","facilitação","alinhamento","comunicação","customer"),
 "tools":("jira","azure devops","confluence","figma","posthog","trello","miro"),
 "ai":("codex","claude code","lovable"),
 "ai":("ai-driven","ai tools","genai","artificial intelligence","inteligência artificial","codex","claude code","lovable"),
}
# A concept is credited only if it occurs in the exact documented evidence.
FACT_TOPICS={
 "analysis":("requisitos","histórias de usuários","backlog","stakeholders","validação","discovery"),
 "agility":("scrum","kanban","sprints","backlog"),
 "project":("projetos","processos","recursos","orçamento","portfólio","delivery","implantação"),
 "product":("produto","product","roadmap","discovery","priorização","usuários","protótipos","figma","jornadas"),
 "growth":("growth","marketing","leads","crm","retenção","churn","fidelização","vendas","comercial","receita","google ads","ticket médio"),
 "data":("indicadores","kpis","okrs","métricas","análises","painéis","testes a/b","analytics"),
 "people":("stakeholders","equipes","liderança","alinhamento","colaboração"),
 "tools":("jira","azure devops","confluence","figma","posthog","trello","miro"),
 "ai":("codex","claude code","lovable")
}
def contains(text, phrase):
    # Word-aware matching avoids accidental substring hits.
    return bool(re.search(r"(?<!\w)"+re.escape(phrase)+r"(?!\w)",text,re.IGNORECASE))
def categories(text, definitions):
    cleaned=relevant_jd_text(text).casefold()
    return {k for k,phrases in definitions.items() if any(contains(cleaned,p.casefold()) for p in phrases)}
def relevance(fact, required, jd_words):
    matched=categories(fact,FACT_TOPICS)&required
    specificity=min(3,len(words(fact)&jd_words))
    return 4*len(matched)+specificity
def jd_requirement_signals(jd):
    """Extract concrete vacancy phrases, ignoring generic employer marketing text."""
    text=relevant_jd_text(jd)
    lines=[re.sub(r"\\s+"," ",line).strip(" •-:") for line in text.splitlines()]
    lines=[line for line in lines if 22<=len(line)<=440]
    markers=("require","responsib","accountabil","experien","skills","requisit","obrigat","desej","must","what you","you will","você vai","competên","atuação","fluente","proficiên")
    head=" ".join(lines[:4]).lower()
    focused=[line for line in lines if any(k in line.lower() for k in markers)]
    if len(focused)<3:focused=lines
    return focused[:60]

def jd_specific_relevance(fact,jd_signals,title_topics,needed):
    """Reward shared concrete terms and professional evidence, not broad category alone."""
    tokens=words(fact)
    if not tokens:return 0
    concrete={"crm","google","ads","analytics","azure","devops","jira","confluence","scrum",
              "kanban","roadmap","backlog","growth","clientes","customer","marketing",
              "projetos","processos","portfolio","portfólio","orçamento","receita",
              "retencao","retenção","hotels","hotelaria","vendas","financeiro","stakeholders",
              "product","produto","painéis","kpi","okrs","figma","codex","lovable","mineração"}
    jd_tokens=set().union(*(words(line) for line in jd_signals[:25]))
    overlap=min(14,len(tokens&jd_tokens&concrete))
    title_bonus=4*len(categories(fact,FACT_TOPICS)&title_topics)
    return 3*overlap+title_bonus+relevance(fact,needed,jd_tokens)

def build_plan(jd, title):
    if not jd or not jd.strip():raise ValueError("JD vazio")
    # Job title is high-signal; descriptions often mention unrelated tools and domains.
    needs=categories(relevant_jd_text(jd)+" "+title,TOPICS)
    title_needs=categories(title,TOPICS)
    # Portuguese role titles may not contain the literal word "marketing".
    # Treat performance-media roles as growth, not as generic product roles.
    if re.search(r"(?i)\b(m[ií]dia|performance|tr[aá]fego|aquisi[cç][aã]o)\b", title):
        title_needs.add("growth")
        needs.add("growth")
    tokens=words(relevant_jd_text(jd))
    jd_signals=jd_requirement_signals(jd)
    scored=[]
    jd_evidence_cache={}
    def specific(f):
        if f not in jd_evidence_cache:
            jd_evidence_cache[f]=jd_specific_relevance(f,jd_signals,title_needs,needs)
        return jd_evidence_cache[f]
    for idx,item in sorted(enumerate(EXPERIENCE),key=lambda x:chronology_index(x[1]),reverse=True):
        def evidence_priority(f):
            directly_relevant=bool(categories(f,FACT_TOPICS)&title_needs)
            quantified=bool(re.search(r"(?:R\\$\\s*\\d|\\d[.,]\\d+%|\\d+%|triplicad)",f,re.I))
            return 7*len(categories(f,FACT_TOPICS)&title_needs)+relevance(f,needs,tokens)+(3 if directly_relevant and quantified else 0)
        ordered=sorted(item["facts"],key=lambda f:(-evidence_priority(f),item["facts"].index(f)))
        strength=sum(max(0,relevance(f,needs,tokens)-1) for f in ordered[:3]) + sum(5 for f in ordered[:3] if categories(f,FACT_TOPICS)&title_needs)
        scored.append((idx,item,ordered,strength))
    prioritized=sorted(scored,key=lambda x:(-x[3],-chronology_index(x[1])[0],-chronology_index(x[1])[1]))
    # Evidence is selected per role, not copied into two different sections.
    title_aligned=[idx for idx,_,ordered,score in prioritized
           if score>=5 and (not title_needs or any(categories(f,FACT_TOPICS)&title_needs for f in ordered[:3]))]
    major=set(title_aligned[:6])
    # Reserve one evidence slot for a directly matching prior career specialty.
    # A performance-media candidate must not bury all of their documented
    # marketing leadership while six recent generalist roles occupy the page.
    if "growth" in title_needs:
        specialist=next((idx for idx,item,_,score in prioritized
                         if "marketing" in (item["role"]+" "+item["company"]).casefold()
                         and score>=5),None)
        if specialist is not None and specialist not in major:
            if len(major)>=6:
                weakest=next((idx for idx,_,_,_ in reversed(prioritized) if idx in major),None)
                if weakest is not None:major.remove(weakest)
            major.add(specialist)
    experiences=[];older=[]
    for idx,item,facts,score in scored:
        if idx in major:
            cap=3 if score>=8 else 2
            chosen=[f for f in facts if relevance(f,needs,tokens)>0][:cap]
            if not chosen:chosen=facts[:1]
            if "growth" in title_needs and "marketing" in item["role"].casefold():
                quantified=[f for f in facts if re.search(r"(?:R\\$\\s*\\d|\\d[.,]\\d+%|\\d+%|triplicad)",f,re.I) and categories(f,FACT_TOPICS)&title_needs]
                if quantified and not any(f in chosen for f in quantified):
                    chosen=chosen[:-1]+[quantified[0]] if len(chosen)>=cap else chosen+[quantified[0]]
            experiences.append({"role":item["role"],"company":item["company"],"dates":item["dates"],
                                "facts":chosen,"source_index":idx})
        else:
            older.append({"role":item["role"],"company":item["company"],"dates":item["dates"],"source_index":idx})
    if not experiences:
        idx,item,facts,_=scored[0]
        experiences=[{"role":item["role"],"company":item["company"],"dates":item["dates"],"facts":facts[:1],"source_index":idx}]
        older=older[1:]
    # Repair genuine topic gaps using only facts from displayed roles.
    # Every bounded swap increases verified JD coverage without deleting other concepts.
    for _ in range(len(needs)):
        selected=[f for entry in experiences for f in entry["facts"]]
        covered=set().union(*(categories(f,FACT_TOPICS) for f in selected)) if selected else set()
        gaps=needs-covered
        if not gaps:break
        improvements=[]
        for topic in gaps:
            for entry in experiences:
                source=EXPERIENCE[entry["source_index"]]
                for fact in source["facts"]:
                    if fact in selected or topic not in categories(fact,FACT_TOPICS):continue
                    options=[None] if len(entry["facts"])<3 else list(entry["facts"])
                    for replace in options:
                        trial=[f for f in selected if f!=replace]+[fact]
                        future=set().union(*(categories(f,FACT_TOPICS) for f in trial))
                        gain=len(future&needs)-len(covered&needs)
                        if gain>0:
                            strength=relevance(fact,needs,tokens)
                            improvements.append((gain,strength,entry["source_index"],fact,replace))
        if not improvements:break
        gain,strength,role_idx,new_fact,replace=max(improvements,key=lambda it:(it[0],it[1],-it[2]))
        row=next(e for e in experiences if e["source_index"]==role_idx)
        if replace is not None:row["facts"].remove(replace)
        row["facts"].append(new_fact)

    # Conservative requirement-specific evidence swaps inside selected roles.
    for entry in experiences:
        source=EXPERIENCE[entry["source_index"]]
        for _ in range(2):
            selected=[f for role in experiences for f in role["facts"]]
            baseline_topics=set().union(*(categories(f,FACT_TOPICS) for f in selected))
            candidates=[]
            for replacement in source["facts"]:
                if replacement in selected:continue
                for incumbent in entry["facts"]:
                    if re.search(r"(?:R\\$\\s*\\d|\\d[.,]\\d+%|\\d+%|triplicad)",incumbent,re.I):
                        continue
                    if "product" in title_needs and ("roadmap" in incumbent.casefold() or "produto b2b" in incumbent.casefold()):
                        continue
                    gain=specific(replacement)-specific(incumbent)
                    trial=[f for f in selected if f!=incumbent]+[replacement]
                    topics=set().union(*(categories(f,FACT_TOPICS) for f in trial))
                    if gain>=5 and (baseline_topics&needs)<=(topics&needs):
                        candidates.append((gain,replacement,incumbent))
            if not candidates:break
            gain,replacement,incumbent=max(candidates,key=lambda x:x[0])
            entry["facts"][entry["facts"].index(incumbent)]=replacement

    # Preserve the baseline's selected evidence, but show its most JD-specific
    # accomplishments first within each employer, without changing chronology.
    for entry in experiences:
        entry["facts"].sort(key=lambda f:-specific(f))

    label={"analysis":"análise de negócios e levantamento de necessidades","agility":"práticas ágeis e gestão de backlog",
           "project":"gestão de projetos e processos","product":"desenvolvimento de produtos digitais",
           "growth":"marketing, crescimento e relacionamento com clientes",
           "data":"gestão orientada por indicadores","people":"alinhamento com equipes e stakeholders",
           "tools":"ferramentas de colaboração e gestão","ai":"ferramentas de IA aplicadas a fluxos de trabalho"}
    top_topics=sorted(needs,key=lambda topic:-sum(relevance(f,{topic},tokens) for _,e,_,_ in scored for f in e["facts"]))[:3]
    if not top_topics:top_topics=["product","project"]
    focus=", ".join(label[t] for t in top_topics)
    # Position the documented career according to the role family, never invent credentials.
    if "growth" in title_needs:
        summary=("Executivo de marketing e growth com trajetória em agência de publicidade, "
                 "grupos de hotelaria e saúde. Experiência em campanhas digitais e omnichannel, "
                 "Google Ads e Analytics, CRM, funil comercial, testes A/B e leitura de KPIs. "
                 "Histórico de liderança de marketing, equipes de criação, planejamento de mídia e orçamento.")
    elif "analysis" in title_needs:
        summary=("Profissional de produtos digitais com atuação na priorização de backlog, "
                 "escrita de histórias de usuários e tradução de necessidades de stakeholders "
                 "em entregas de produto. Experiência em solução industrial de mineração "
                 "com veículos autônomos e uso de Jira, Azure DevOps, Trello e Figma. "
                 "Vivência complementar em discovery, prototipação e melhoria de processos.")
    elif "product" in title_needs and "project" in needs:
        summary=("Product Manager com experiência em produtos digitais B2B e plataformas "
                 "operacionais para mineração, pagamentos e serviços. Atuação em definição de "
                 "roadmaps, discovery, validação de hipóteses e priorização de backlog, "
                 "integrando stakeholders e equipes multidisciplinares. "
                 "Histórico adicional em gestão de projetos, Scrum, Kanban e orçamento de delivery.")
    elif "project" in title_needs:
        summary=("Líder de projetos, portfólio e processos, com experiência em PMO, "
                 "gestão de recursos, indicadores e orçamento. Implantação de Scrum e Kanban "
                 "com equipes multidisciplinares em empresas de tecnologia e negócios. "
                 "Experiência em governança, melhoria de processos e coordenação de entregas digitais.")
    elif "product" in title_needs:
        summary=("Product Manager e Product Owner com experiência em produtos digitais "
                 "B2B, plataformas de mineração, CRM e soluções de pagamentos. "
                 "Atuação em product discovery, roadmaps, backlog, pesquisa de usuários, "
                 "priorização por valor, métricas e colaboração com stakeholders. "
                 "Histórico na gestão de delivery de aplicações web e mobile.")
    else:
        summary=("Experiência profissional em "+focus+
                 ", com atuação documentada em tecnologia e negócios. "
                 "Histórico de atividades em equipes e projetos de diferentes setores.")
    # Only a profile-level statement here, never repeated verbatim from the roles.
    tailored_education=[degree for degree in EDUCATION
                        if "Odontologia" not in degree or not title_needs]
    return {"title":title[:120],"summary":summary,"focus_topics":top_topics,
            "education":tailored_education,
            "experience":experiences,"additional_experience":older,
            "jd_sha256":hashlib.sha256(jd.encode()).hexdigest(),"engine":ENGINE_VERSION}

def render_docx(plan):
    doc=Document();normal=doc.styles["Normal"];normal.font.name="Calibri";normal.font.size=Pt(10)
    section=doc.sections[0]
    from docx.shared import Inches
    section.top_margin=Inches(.62);section.bottom_margin=Inches(.62)
    # Provenance is embedded in DOCX metadata, invisible to recruiters/ATS.
    provenance = (
        f"JobHunterCV={CV_DOCUMENT_VERSION};"
        f"Engine={ENGINE_VERSION};"
        f"AI={plan.get('cv_mode', 'deterministic')};"
        f"JD={plan['jd_sha256'][:16]};"
        f"Build={plan.get('cv_build', 'unknown')}"
    )
    doc.core_properties.keywords = provenance
    doc.core_properties.comments = "Job Hunter CV provenance: " + provenance
    doc.add_heading(CONTACT["name"],0)
    doc.add_paragraph(" | ".join([CONTACT["location"],CONTACT["phone"],CONTACT["email"],CONTACT["linkedin"]]))
    doc.add_heading("Resumo profissional",1);doc.add_paragraph(plan["summary"])
    doc.add_heading("Experiência profissional",1)
    detailed={e["source_index"]:e for e in plan["experience"]}
    compact={e["source_index"]:e for e in plan["additional_experience"]}
    chronology=sorted(set(detailed)|set(compact),key=lambda i:chronology_index(EXPERIENCE[i]),reverse=True)
    for idx in chronology:
        e=detailed.get(idx) or compact[idx]
        if idx not in detailed:
            doc.add_paragraph(e["role"]+" — "+e["company"]+" | "+e["dates"])
            continue
        heading=doc.add_heading(e["role"]+" — "+e["company"],2)
        heading.paragraph_format.keep_with_next=True
        dates=doc.add_paragraph(e["dates"]);dates.paragraph_format.keep_with_next=True
        for fact in e["facts"]:doc.add_paragraph(fact,style="List Bullet")
    doc.add_heading("Formação e certificações",1)
    for degree in plan.get("education",EDUCATION):doc.add_paragraph(degree,style="List Bullet")
    doc.add_paragraph("Idiomas: Português (nativo); Inglês (profissional); Italiano (intermediário).")
    out=io.BytesIO();doc.save(out);return out.getvalue()

def audit(plan,data):
    parsed=Document(io.BytesIO(data))
    content=" ".join(p.text for p in parsed.paragraphs)
    assert CONTACT["email"] in content and CONTACT["phone"] in content
    original={f for e in EXPERIENCE for f in e["facts"]}
    selected=[f for e in plan["experience"] for f in e["facts"]]
    provenance=plan.get("bullet_provenance") or {}
    assert selected and len(selected)==len(set(selected))
    assert all(f in original or provenance.get(f) in original for f in selected)
    assert all(content.count(f)==1 for f in selected)
    assert all(source in original for source in provenance.values())
    return {"engine":ENGINE_VERSION,"document_sha256":hashlib.sha256(data).hexdigest(),
            "jd_sha256":plan["jd_sha256"],"factual_bullets_verified":True,
            "cost_usd":0.0,"ai_calls":0,"paragraphs":len(parsed.paragraphs)}

def evaluate_rendered_resume(plan, data, jd):
    """Explainable technical audit of the reopened document; not a recruiter fit score."""
    doc=Document(io.BytesIO(data))
    lines=[p.text.strip() for p in doc.paragraphs if p.text.strip()]
    displayed="\\n".join(lines)
    facts=[f for e in plan["experience"] for f in e["facts"]]
    requirements=categories(jd+" "+plan["title"],TOPICS)
    title_requirements=categories(plan["title"],TOPICS)
    if re.search(r"(?i)\b(m[ií]dia|performance|tr[aá]fego|aquisi[cç][aã]o)\b",plan["title"]):
        title_requirements.add("growth")
    fact_topics=set().union(*(categories(f,FACT_TOPICS) for f in facts)) if facts else set()
    covered=requirements&fact_topics
    fact_source=plan.get("bullet_provenance") or {}
    factual=sum(1 for f in facts if
                f in {x for item in EXPERIENCE for x in item["facts"]}
                or fact_source.get(f) in {x for item in EXPERIENCE for x in item["facts"]})
    unique=len(facts)==len(set(facts))
    bullet_present=all(displayed.count(f)==1 for f in facts)
    all_roles=sorted(EXPERIENCE,key=chronology_index,reverse=True)
    offsets=[displayed.find(e["role"]+" — "+e["company"]) for e in all_roles]
    chronologically_sorted=all(p>=0 for p in offsets) and offsets==sorted(offsets)
    factual_ok=factual==len(facts) and bullet_present and unique
    scores={
        "factual_traceability":2.0 if factual_ok else 0.0,
        "role_relevance":2.0*len(covered&title_requirements)/max(1,len(title_requirements)),
        "jd_topic_coverage":2.0*len(covered)/max(1,len(requirements)),
        "document_integrity":2.0 if "Resumo profissional" in displayed and
            "Experiência profissional" in displayed and chronologically_sorted else 0.0,
        "evidence_density":2.0*min(1.0,len(facts)/9.0),
    }
    # Mechanical quality is distinct from real candidate eligibility and writing quality.
    return {"technical_score":round(sum(scores.values()),2),
            "dimensions":{k:round(v,2) for k,v in scores.items()},
            "covered_topics":sorted(covered),"uncovered_topics":sorted(requirements-covered),
            "fact_count":len(facts),"factual_ok":factual_ok,
            "document_sha256":hashlib.sha256(data).hexdigest(),
            "jd_sha256":plan["jd_sha256"],
            "limitations":"This is a mechanical technical audit, not an independent human or AI editorial review."}
