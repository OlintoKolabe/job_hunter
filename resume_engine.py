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
import multiuser as mu

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


# LinkedIn profile audit (October 2026): append verified evidence; never change old IDs.
EXPERIENCE[0]["facts"].extend([
    "Concepção de plataforma DTx com treinamento cognitivo gamificado baseado em neurociência e terapia cognitivo-comportamental.",
])
EXPERIENCE[3]["facts"].extend([
    "Estruturação de processos administrativos, comerciais e de marketing com equipe multidisciplinar.",
])
EXPERIENCE[6]["facts"].extend([
    "Definição de cronogramas de tecnologia e negócios e negociação de prioridades com stakeholders.",
    "Startup financiada pelo programa Centelha, classificada entre as 15 melhores de mil propostas.",
])
EXPERIENCE[7]["facts"].extend([
    "Criação de jornadas, interfaces e protótipos no Figma para validação e desenvolvimento de soluções.",
])
EXPERIENCE[8]["facts"].extend([
    "Reestruturação de operações para eficiência e maximização de receitas.",
])
EXPERIENCE[11]["facts"].extend([
    "Criação da marca Privé Diversão, unificando a estratégia de branding de três parques aquáticos.",
    "Participação no comitê executivo operacional de hospitalidade e entretenimento.",
])
EXPERIENCE[12]["facts"].extend([
    "Criação e execução de eventos corporativos com o departamento de eventos.",
    "Campanhas e eventos de lançamento de produtos de hospitalidade e entretenimento.",
])
EXPERIENCE.append({"role":"Professor de MBA","company":"Estácio",
    "dates":"jun 2016 – out 2016",
    "facts":["Atuação como professor de MBA em pós-graduação de Recursos Humanos."]})

EDUCATION = ["Graduação — Universidade de São Paulo (USP)",
             "MBA em Marketing — Universidade de São Paulo (2015–2016)",
             "MBA em Administração e Gestão — Fundação Getulio Vargas (2001–2003)",
             "Professional Scrum Product Owner I (PSPO I)"]
# Imports in AI matcher retain these dynamic proxies and resolve the facts for
# the authenticated request; legacy deployments still use the original facts.
EXPERIENCE = mu.ProfileSequence(EXPERIENCE, mu.factual_experience)
EDUCATION = mu.ProfileSequence(EDUCATION, mu.profile_education)
CONTACT = mu.ProfileContact(CONTACT)
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
    if mu.enabled:
        dates=str(item.get("dates") or "")
        match=re.search(r"(?i)(?:jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)[a-z]*\s+(20\d\d|19\d\d)",dates)
        months={"jan":1,"fev":2,"mar":3,"abr":4,"mai":5,"jun":6,
                "jul":7,"ago":8,"set":9,"out":10,"nov":11,"dez":12}
        if match:
            return (int(match.group(1)),months.get(match.group(0)[:3].lower(),1))
        year=re.search(r"\b(19\d{2}|20\d{2})\b",dates)
        return (int(year.group(1)),1) if year else (0,0)
    starts={
      "Centauro.life":(2026,4),"Neocoder / LiberPay":(2025,5),"Neocoder":(2025,2),
      "Hexagon Mining":(2023,8),"Stefanini Brasil / Hexagon Mining":(2023,5),
      "Dotz Inc. / Meu Varejo":(2022,8),"Top Saúde Clínicas Médicas":(2020,2),
      "Kolabe":(2018,5),"Estácio":(2016,6),"Lagoa Parques e Hotéis":(2015,1),
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
def build_plan(jd, title):
    if not jd or not jd.strip():raise ValueError("JD vazio")
    if mu.enabled and not mu.factual_experience():
        raise ValueError("Cadastre e valide experiências antes de gerar um currículo")
    # Job title is high-signal; descriptions often mention unrelated tools and domains.
    needs=categories(relevant_jd_text(jd)+" "+title,TOPICS)
    title_needs=categories(title,TOPICS)
    # Portuguese role titles may not contain the literal word "marketing".
    # Treat performance-media roles as growth, not as generic product roles.
    if re.search(r"(?i)\b(m[ií]dia|performance|tr[aá]fego|aquisi[cç][aã]o)\b", title):
        title_needs.add("growth")
        needs.add("growth")
    tokens=words(relevant_jd_text(jd))
    scored=[]
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
    if mu.enabled:
        profile=mu.current_profile.get() or {}
        summary=html.unescape(str(profile.get("summary") or "")).replace("\\", " ")
        summary=" ".join(summary.split()).strip()
        # LinkedIn PDF often appends a direct-contact invitation to About.
        # Contact information already lives in the document header.
        summary=re.split(r"(?i)\s*\[\s*[^\]]*(?:@|direct message)[^\]]*\]",summary,maxsplit=1)[0].strip()
        if len(summary)>520:
            end=max(summary.rfind(x,280,521) for x in ".!?")
            summary=(summary[:end+1] if end>=280
                     else summary[:520].rsplit(" ",1)[0].rstrip(" ,;:")+".")
        if not summary:
            summary="Profissional com experiência documentada em "+", ".join(
                sorted(set(e["role"] for e in EXPERIENCE))[:3])+"."
    tailored_education=[degree for degree in EDUCATION if "odontolog" not in degree.casefold()]
    return {"title":title[:120],"summary":summary,"focus_topics":top_topics,
            "education":tailored_education,
            "experience":experiences,"additional_experience":older,
            "jd_sha256":hashlib.sha256(jd.encode()).hexdigest(),"engine":ENGINE_VERSION}

def render_docx(plan):
    from docx.shared import Inches, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    doc=Document();normal=doc.styles["Normal"];normal.font.name="Calibri";normal.font.size=Pt(10.5)
    normal.font.color.rgb=RGBColor(0,0,0)
    section=doc.sections[0]
    section.top_margin=Inches(.72);section.bottom_margin=Inches(.68)
    section.left_margin=Inches(.82);section.right_margin=Inches(.82)
    normal.paragraph_format.space_after=Pt(4)
    normal.paragraph_format.line_spacing=1.08
    title_style=doc.styles["Title"]
    title_style.font.name="Calibri";title_style.font.size=Pt(18)
    title_style.font.bold=True;title_style.font.color.rgb=RGBColor(0,0,0)
    title_style.paragraph_format.space_before=Pt(0)
    title_style.paragraph_format.space_after=Pt(5)
    title_style.paragraph_format.keep_with_next=True
    # Neutralize Word's default blue underline/border below the Title style.
    pPr=title_style.element.get_or_add_pPr()
    border=pPr.find(qn("w:pBdr"))
    if border is not None:pPr.remove(border)
    border=OxmlElement("w:pBdr")
    bottom=OxmlElement("w:bottom");bottom.set(qn("w:val"),"nil")
    border.append(bottom);pPr.append(border)
    for name,size,before,after in (("Heading 1",11.5,10,4),("Heading 2",10.5,6,1)):
        style=doc.styles[name]
        style.font.name="Calibri";style.font.size=Pt(size)
        style.font.bold=True;style.font.color.rgb=RGBColor(0,0,0)
        style.paragraph_format.space_before=Pt(before)
        style.paragraph_format.space_after=Pt(after)
        style.paragraph_format.keep_with_next=True
    bullet=doc.styles["List Bullet"]
    bullet.font.name="Calibri";bullet.font.size=Pt(10.5)
    bullet.font.color.rgb=RGBColor(0,0,0)
    bullet.paragraph_format.left_indent=Inches(.22)
    bullet.paragraph_format.first_line_indent=Inches(-.14)
    bullet.paragraph_format.space_before=Pt(0)
    bullet.paragraph_format.space_after=Pt(3)
    bullet.paragraph_format.line_spacing=1.08
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
    contact=doc.add_paragraph(" | ".join(v for v in
        [CONTACT["location"],CONTACT["phone"],CONTACT["email"],CONTACT["linkedin"]] if v))
    contact.style=normal
    for run in contact.runs:run.font.size=Pt(9)
    contact.paragraph_format.space_after=Pt(5)
    english=plan.get("language")=="en"
    localized=plan.get("localized") or {}
    translated_rows={e["source_index"]:row for e,row in zip(plan["experience"]+plan["additional_experience"],localized.get("entries",[]))}
    doc.add_heading("Professional Summary" if english else "Resumo profissional",1)
    doc.add_paragraph(localized.get("summary",plan["summary"]))
    doc.add_heading("Professional Experience" if english else "Experiência profissional",1)
    detailed={e["source_index"]:e for e in plan["experience"]}
    compact={e["source_index"]:e for e in plan["additional_experience"]}
    chronology=sorted(set(detailed)|set(compact),key=lambda i:chronology_index(EXPERIENCE[i]),reverse=True)
    for idx in chronology:
        e=detailed.get(idx) or compact[idx]
        translated=translated_rows.get(idx) or {}
        role=translated.get("role",e["role"])
        dates_text=translated.get("dates",e["dates"])
        displayed_facts=translated.get("facts") or (e["facts"] if idx in detailed else [e.get("fact") or EXPERIENCE[idx]["facts"][0]])
        if idx not in detailed:
            heading=doc.add_heading(role+" — "+e["company"],2)
            heading.paragraph_format.keep_with_next=True
            dates=doc.add_paragraph(dates_text)
            dates.paragraph_format.keep_with_next=True
            for run in dates.runs:run.font.size=Pt(9)
            # Compact experience must still have a factual description.
            doc.add_paragraph(displayed_facts[0],style="List Bullet")
            continue
        heading=doc.add_heading(role+" — "+e["company"],2)
        heading.paragraph_format.keep_with_next=True
        dates=doc.add_paragraph(dates_text);dates.paragraph_format.keep_with_next=True
        for run in dates.runs:run.font.size=Pt(9)
        for fact in displayed_facts:doc.add_paragraph(fact,style="List Bullet")
    doc.add_heading("Education and Certifications" if english else "Formação e certificações",1)
    for degree in localized.get("education",plan.get("education",EDUCATION)):
        if "odontolog" not in degree.casefold():doc.add_paragraph(degree,style="List Bullet")
    if mu.enabled:
        languages=(mu.current_profile.get() or {}).get("languages") or []
        if languages:doc.add_paragraph(("Languages: " if english else "Idiomas: ")+ "; ".join(localized.get("languages",languages))+".")
    else:
        doc.add_paragraph("Languages: Portuguese (native); English (professional); Italian (intermediate)." if english else "Idiomas: Português (nativo); Inglês (profissional); Italiano (intermediário).")
    out=io.BytesIO();doc.save(out);return out.getvalue()

def professional_bullets(document):
    """Read only the experience section, never education/certification bullets."""
    inside=False
    bullets=[]
    for paragraph in document.paragraphs:
        if paragraph.text in ("Experiência profissional","Professional Experience"):
            inside=True
        elif paragraph.text in ("Formação e certificações","Education and Certifications"):
            inside=False
        elif inside and paragraph.style.name=="List Bullet":
            bullets.append(paragraph.text)
    return bullets


def audit(plan,data):
    parsed=Document(io.BytesIO(data))
    content=" ".join(p.text for p in parsed.paragraphs)
    assert CONTACT["email"] in content and CONTACT["phone"] in content, "contact_missing"
    original={f for e in EXPERIENCE for f in e["facts"]}
    selected=[f for e in plan["experience"] for f in e["facts"]]
    provenance=plan.get("bullet_provenance") or {}
    assert selected and len(selected)==len(set(selected)), "missing_or_duplicate_facts"
    assert all(f in original or provenance.get(f) in original for f in selected), "unproven_fact"
    # The evidence must occur once as a professional bullet, not once across
    # the whole document: cities, credentials and skills can recur elsewhere.
    bullets=professional_bullets(parsed)
    rows=plan["experience"]+plan.get("additional_experience",[])
    translations=(plan.get("localized") or {}).get("entries",[])
    expected=[f for i,e in enumerate(rows[:len(plan["experience"])]) for f in (translations[i]["facts"] if i<len(translations) else e["facts"])]
    assert all(bullets.count(f)==1 for f in expected), "fact_bullet_missing_or_repeated"
    assert not any(f in plan["summary"] for f in selected), "summary_repeats_fact"
    assert all(source in original for source in provenance.values()), "invalid_provenance"
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
    bullet_lines=professional_bullets(doc)
    translations=(plan.get("localized") or {}).get("entries",[])
    expected=[f for i,e in enumerate(plan["experience"]) for f in (translations[i]["facts"] if i<len(translations) else e["facts"])]
    bullet_present=all(bullet_lines.count(f)==1 for f in expected)
    all_roles=sorted(range(len(EXPERIENCE)),key=lambda i:chronology_index(EXPERIENCE[i]),reverse=True)
    localized_rows={e["source_index"]:row for e,row in zip(plan["experience"]+plan.get("additional_experience",[]),(plan.get("localized") or {}).get("entries",[]))}
    offsets=[displayed.find(localized_rows.get(i,{}).get("role",EXPERIENCE[i]["role"])+" — "+EXPERIENCE[i]["company"]) for i in all_roles]
    chronologically_sorted=all(p>=0 for p in offsets) and offsets==sorted(offsets)
    factual_ok=factual==len(facts) and bullet_present and unique
    english=plan.get("language")=="en"
    heading_ok=(("Professional Summary" in displayed and "Professional Experience" in displayed) if english else ("Resumo profissional" in displayed and "Experiência profissional" in displayed))
    scores={
        "factual_traceability":2.0 if factual_ok else 0.0,
        "role_relevance":2.0*len(covered&title_requirements)/max(1,len(title_requirements)),
        "jd_topic_coverage":2.0*len(covered)/max(1,len(requirements)),
        "document_integrity":2.0 if heading_ok and chronologically_sorted else 0.0,
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
