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

ENGINE_VERSION = "block5-deterministic-v3"
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
EDUCATION = ["MBA em Marketing — Universidade de São Paulo (2015–2016)",
             "MBA em Administração e Gestão — Fundação Getulio Vargas (2001–2003)",
             "Graduação em Odontologia — Universidade de São Paulo (1996–1999)",
             "Professional Scrum Product Owner I (PSPO I)"]
STOP={"the","and","with","for","that","from","have","will","are","this","your","our",
      "para","com","que","dos","das","uma","por","como","nos","nas","mais","sobre",
      "experiencia","experience","required","requirements","responsibilities","years"}
def words(value):
    value=html.unescape(re.sub(r"<[^>]+>"," ",value or "")).lower()
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
 "growth":("growth","marketing","tráfego","ads","funil","leads","crm","campanha","retenção","churn","ltv","upsell","cross-sell","vendas","comercial","acquisition"),
 "data":("indicadores","analytics","dados","metrics","métricas","kpi","reports","relatórios","dashboards","análise","analysis"),
 "people":("stakeholders","equipe","times","liderança","facilitar","facilitação","alinhamento","comunicação","customer"),
 "tools":("jira","azure devops","confluence","figma","posthog","trello","miro"),
}
# A concept is credited only if it occurs in the exact documented evidence.
FACT_TOPICS={
 "analysis":("requisitos","histórias de usuários","backlog","stakeholders","pesquisa de mercado","validação","discovery"),
 "agility":("scrum","kanban","sprints","backlog"),
 "project":("projetos","processos","recursos","orçamento","portfólio","delivery","implantação"),
 "product":("produto","product","roadmap","discovery","priorização","usuários","protótipos","figma","jornadas"),
 "growth":("growth","marketing","leads","crm","retenção","churn","fidelização","vendas","google ads","ticket médio"),
 "data":("indicadores","kpis","okrs","métricas","análises","painéis","testes a/b","analytics"),
 "people":("stakeholders","equipes","liderança","alinhamento","colaboração"),
 "tools":("jira","azure devops","confluence","figma","posthog","trello","miro")
}
def contains(text, phrase):
    # Word-aware matching avoids accidental substring hits.
    return bool(re.search(r"(?<!\w)"+re.escape(phrase)+r"(?!\w)",text,re.IGNORECASE))
def categories(text, definitions):
    cleaned=html.unescape(re.sub(r"<[^>]+>"," ",text or "")).casefold()
    return {k for k,phrases in definitions.items() if any(contains(cleaned,p.casefold()) for p in phrases)}
def relevance(fact, required, jd_words):
    matched=categories(fact,FACT_TOPICS)&required
    specificity=min(3,len(words(fact)&jd_words))
    return 4*len(matched)+specificity
def build_plan(jd, title):
    if not jd or not jd.strip():raise ValueError("JD vazio")
    needs=categories(jd,TOPICS)
    tokens=words(jd)
    scored=[]
    for idx,item in sorted(enumerate(EXPERIENCE),key=lambda x:chronology_index(x[1]),reverse=True):
        ordered=sorted(item["facts"],key=lambda f:(-relevance(f,needs,tokens),item["facts"].index(f)))
        strength=sum(max(0,relevance(f,needs,tokens)-1) for f in ordered[:3])
        scored.append((idx,item,ordered,strength))
    prioritized=sorted(scored,key=lambda x:(-x[3],-chronology_index(x[1])[0],-chronology_index(x[1])[1]))
    # Evidence is selected per role, not copied into two different sections.
    major={idx for idx,_,_,score in prioritized[:4] if score>=5}
    experiences=[];older=[]
    for idx,item,facts,score in scored:
        if idx in major:
            cap=3 if score>=8 else 2
            chosen=[f for f in facts if relevance(f,needs,tokens)>0][:cap]
            if not chosen:chosen=facts[:1]
            experiences.append({"role":item["role"],"company":item["company"],"dates":item["dates"],
                                "facts":chosen,"source_index":idx})
        else:
            older.append({"role":item["role"],"company":item["company"],"dates":item["dates"],"source_index":idx})
    if not experiences:
        idx,item,facts,_=scored[0]
        experiences=[{"role":item["role"],"company":item["company"],"dates":item["dates"],"facts":facts[:1],"source_index":idx}]
        older=older[1:]
    label={"analysis":"análise de negócios e levantamento de necessidades","agility":"práticas ágeis e gestão de backlog",
           "project":"gestão de projetos e processos","product":"desenvolvimento de produtos digitais",
           "growth":"marketing, crescimento e relacionamento com clientes",
           "data":"gestão orientada por indicadores","people":"alinhamento com equipes e stakeholders",
           "tools":"ferramentas de colaboração e gestão"}
    top_topics=sorted(needs,key=lambda topic:-sum(relevance(f,{topic},tokens) for _,e,_,_ in scored for f in e["facts"]))[:3]
    if not top_topics:top_topics=["product","project"]
    focus=", ".join(label[t] for t in top_topics)
    summary="Profissional com atuação em tecnologia e negócios, reunindo experiência em "+focus+". Atuação em diferentes setores, com responsabilidades em entregas e colaboração multidisciplinar."
    # Only a profile-level statement here, never repeated verbatim from the roles.
    return {"title":title[:120],"summary":summary,"focus_topics":top_topics,
            "experience":experiences,"additional_experience":older,
            "jd_sha256":hashlib.sha256(jd.encode()).hexdigest(),"engine":ENGINE_VERSION}

def render_docx(plan):
    doc=Document();normal=doc.styles["Normal"];normal.font.name="Calibri";normal.font.size=Pt(10)
    section=doc.sections[0]
    from docx.shared import Inches
    section.top_margin=Inches(.62);section.bottom_margin=Inches(.62)
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
    for degree in EDUCATION:doc.add_paragraph(degree,style="List Bullet")
    doc.add_paragraph("Idiomas: Português (nativo); Inglês (profissional); Italiano (intermediário).")
    out=io.BytesIO();doc.save(out);return out.getvalue()

def audit(plan,data):
    parsed=Document(io.BytesIO(data))
    content=" ".join(p.text for p in parsed.paragraphs)
    assert CONTACT["email"] in content and CONTACT["phone"] in content
    original={f for e in EXPERIENCE for f in e["facts"]}
    selected=[f for e in plan["experience"] for f in e["facts"]]
    assert selected and len(selected)==len(set(selected))
    assert all(f in original for f in selected)
    assert all(content.count(f)==1 for f in selected)
    return {"engine":ENGINE_VERSION,"document_sha256":hashlib.sha256(data).hexdigest(),
            "jd_sha256":plan["jd_sha256"],"factual_bullets_verified":True,
            "cost_usd":0.0,"ai_calls":0,"paragraphs":len(parsed.paragraphs)}
