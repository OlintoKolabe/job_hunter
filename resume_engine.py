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

ENGINE_VERSION = "block5-evidence-v1"
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
def build_plan(jd, title):
    if not jd.strip(): raise ValueError("JD vazio")
    important=words(jd)
    scored=[]
    for idx,item in enumerate(EXPERIENCE):
        facts=sorted(item["facts"], key=lambda f:(-len(words(f)&important),item["facts"].index(f)))
        overlap=sum(min(3,len(words(f)&important)) for f in facts[:4])
        scored.append((idx,item,facts,overlap))
    relevant=sorted(scored,key=lambda v:(-v[3],v[0]))
    focus=relevant[:4]
    summary=("Profissional de produto, projetos e estratégia de negócios, com atuação em empresas "
             "de tecnologia, saúde, mineração e marketing. Experiência em gestão de stakeholders, "
             "priorização de demandas e desenvolvimento de soluções digitais.")
    return {"title":title[:120],"summary":summary,
            "highlighted":[{"company":x[1]["company"],"source_index":x[0],
                            "facts":x[2][:3]} for x in focus],
            "experience":[{"role":e["role"],"company":e["company"],"dates":e["dates"],
                           "facts":facts[:3],"source_index":idx}
                          for idx,e,facts,_ in scored],
            "jd_sha256":hashlib.sha256(jd.encode()).hexdigest(),
            "engine":ENGINE_VERSION}
def render_docx(plan):
    doc=Document();normal=doc.styles["Normal"];normal.font.name="Calibri";normal.font.size=Pt(10)
    doc.add_heading(CONTACT["name"],0)
    doc.add_paragraph(" | ".join([CONTACT["location"],CONTACT["phone"],CONTACT["email"],CONTACT["linkedin"]]))
    doc.add_heading("Resumo profissional",1);doc.add_paragraph(plan["summary"])
    doc.add_heading("Competências e experiências relevantes para a vaga",1)
    seen=set()
    for row in plan["highlighted"]:
        for fact in row["facts"]:
            if fact not in seen:
                doc.add_paragraph(fact,style="List Bullet");seen.add(fact)
    doc.add_heading("Experiência profissional",1)
    for e in plan["experience"]:
        doc.add_heading(e["role"]+" — "+e["company"],2);doc.add_paragraph(e["dates"])
        for fact in e["facts"]:doc.add_paragraph(fact,style="List Bullet")
    doc.add_heading("Formação e certificações",1)
    for degree in EDUCATION:doc.add_paragraph(degree,style="List Bullet")
    out=io.BytesIO();doc.save(out);return out.getvalue()
def audit(plan, data):
    parsed=Document(io.BytesIO(data))
    text=" ".join(p.text for p in parsed.paragraphs)
    assert CONTACT["email"] in text and CONTACT["phone"] in text
    original={f for item in EXPERIENCE for f in item["facts"]}
    for e in plan["experience"]:
        assert all(f in original for f in e["facts"])
    for e in plan["highlighted"]:
        assert all(f in original for f in e["facts"])
    return {"engine":ENGINE_VERSION,"document_sha256":hashlib.sha256(data).hexdigest(),
            "jd_sha256":plan["jd_sha256"],"factual_bullets_verified":True,
            "cost_usd":0.0,"ai_calls":0,"paragraphs":len(parsed.paragraphs)}
