"""
Histórico Acadêmico da UNIFESP: parser determinístico + CR.

O aluno envia o PDF do histórico ("histórico sujo") e ele vira contexto da
SESSÃO (por conversation_id, sem conta de usuário): as capacidades agênticas
passam a usar as disciplinas reais cursadas, e o CR (média ponderada de
conceito por créditos) é calculado e simulável deterministicamente.

O parser valida a si mesmo: o CR recalculado é comparado ao CR geral impresso
no documento.
"""

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

_UC_RE = re.compile(r"^(\d{3,4}) - (.+?)\s*$")
_DADOS_RE = re.compile(
    r"Docente:.*?\s(\d{3})\s+(DF|DE|E|O|AE)\s+(\d+)\s+(\S+)\s+(\d+)\s+(\d+)\s+"
    r"([\d,.]+)\s+([A-ZÃÕÇ ]+?)\s*$"
)
_SEM_RE = re.compile(
    r"ANO/SEM\s*\|\s*(\d{4})/(\d)\s*Coeficiente de Rendimento \(CR\):\s*([\d.,]+)"
)
_CR_GERAL_RE = re.compile(
    r"Coeficiente de Rendimento \(CR\) Geral:\s*([\d.,]+)"
)
_CURSO_RE = re.compile(r"Curso:\s*(.+?)\s*$", re.MULTILINE)

GRUPO_FIXA = "121"
GRUPO_ELETIVA = "102"
GRUPO_INTERDISCIPLINAR = "182"


def _num(s: str) -> Optional[float]:
    try:
        return float(str(s).replace(",", "."))
    except (TypeError, ValueError):
        return None


def extrair_texto_pdf(conteudo: bytes) -> str:
    from io import BytesIO
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(conteudo))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parsear_historico(texto: str) -> Optional[Dict]:
    linhas = (texto or "").splitlines()
    curso = ""
    m = _CURSO_RE.search(texto or "")
    if m:
        curso = m.group(1).strip()
    cr_geral = None
    m = _CR_GERAL_RE.search(texto or "")
    if m:
        cr_geral = _num(m.group(1))

    disciplinas: List[Dict] = []
    semestres: List[Dict] = []
    ano_sem_atual = ""
    uc_pendente: Optional[Tuple[str, str]] = None

    for linha in linhas:
        linha = linha.strip()
        msem = _SEM_RE.search(linha)
        if msem:
            ano_sem_atual = f"{msem.group(1)}/{msem.group(2)}"
            semestres.append({
                "ano_sem": ano_sem_atual,
                "cr": _num(msem.group(3)),
            })
            continue
        muc = _UC_RE.match(linha)
        if muc:
            uc_pendente = (muc.group(1), muc.group(2).strip())
            continue
        if uc_pendente and linha.startswith("Docente:"):
            mdados = _DADOS_RE.search(linha)
            if mdados:
                codigo, nome = uc_pendente
                situacao = mdados.group(8).strip()
                disciplinas.append({
                    "codigo": codigo,
                    "nome": nome.title(),
                    "grupo": mdados.group(1),
                    "tipo": mdados.group(2),
                    "ch": int(mdados.group(3)),
                    "chext": _num(mdados.group(4)) or 0,
                    "creditos": int(mdados.group(5)),
                    "freq": int(mdados.group(6)),
                    "nota": _num(mdados.group(7)),
                    "situacao": situacao,
                    "ano_sem": ano_sem_atual,
                })
            uc_pendente = None

    if not disciplinas:
        return None

    dados = {
        "curso": curso,
        "cr_geral": cr_geral,
        "semestres": semestres,
        "disciplinas": disciplinas,
    }
    dados["cr_calculado"] = calcular_cr(disciplinas)
    dados["cr_confere"] = (
        cr_geral is not None
        and dados["cr_calculado"] is not None
        and abs(dados["cr_calculado"] - cr_geral) <= 0.05
    )
    return dados


def calcular_cr(disciplinas: List[Dict]) -> Optional[float]:
    soma, creditos = 0.0, 0
    for d in disciplinas:
        if d.get("nota") is None or not d.get("creditos"):
            continue
        soma += d["nota"] * d["creditos"]
        creditos += d["creditos"]
    if not creditos:
        return None
    return round(soma / creditos, 3)


def simular_cr(disciplinas: List[Dict], novas: List[Tuple[float, int]]) -> Optional[float]:
    soma, creditos = 0.0, 0
    for d in disciplinas:
        if d.get("nota") is None or not d.get("creditos"):
            continue
        soma += d["nota"] * d["creditos"]
        creditos += d["creditos"]
    for nota, cred in novas:
        soma += nota * cred
        creditos += cred
    if not creditos:
        return None
    return round(soma / creditos, 3)


def curso_sigla(curso_texto: str) -> str:
    t = _norm(curso_texto)
    if "ciencia e tecnologia" in t or "interdisciplinar" in t:
        return "BCT"
    if "ciencia da computacao" in t:
        return "BCC"
    if "engenharia de computacao" in t:
        return "EC"
    if "engenharia biomedica" in t:
        return "EB"
    if "engenharia de materiais" in t:
        return "EM"
    if "matematica computacional" in t:
        return "BMC"
    if "biotecnologia" in t:
        return "BBT"
    return ""


def aprovadas(dados: Dict) -> List[str]:
    return [
        d["nome"] for d in dados.get("disciplinas", [])
        if d.get("situacao") == "APROVADO"
    ]


def interdisciplinares_cursadas(dados: Dict) -> List[str]:
    return sorted({
        d["nome"] for d in dados.get("disciplinas", [])
        if d.get("grupo") == GRUPO_INTERDISCIPLINAR and d.get("situacao") == "APROVADO"
    })


def reprovacoes(dados: Dict) -> List[Dict]:
    return [
        d for d in dados.get("disciplinas", [])
        if d.get("situacao") == "REPROVADO"
    ]


def resumo_historico(dados: Dict) -> str:
    discs = dados.get("disciplinas", [])
    aprov = aprovadas(dados)
    reprov = reprovacoes(dados)
    inter = interdisciplinares_cursadas(dados)
    cr = dados.get("cr_geral") or dados.get("cr_calculado")
    linhas = [
        "**Histórico carregado nesta conversa!** Agora posso responder com os seus dados.",
        "",
        f"- Curso: **{dados.get('curso') or 'não identificado'}**",
        f"- CR geral: **{cr}**" + (
            " (recalculei pela média ponderada nota × créditos e confere ✓)"
            if dados.get("cr_confere") else ""
        ),
        f"- Disciplinas no histórico: **{len(discs)}** ({len(aprov)} aprovações, {len(reprov)} reprovações)",
        f"- UCs Eletivas Interdisciplinares: **{len(inter)} de 4** ({', '.join(inter) if inter else 'nenhuma ainda'})",
    ]
    if reprov:
        nomes = ", ".join(f"{d['nome']} ({d['ano_sem']})" for d in reprov)
        linhas.append(f"- Reprovações: {nomes}")
    linhas.append("")
    linhas.append(
        "Pergunte por exemplo: *qual meu CR?* · *quanto falta para me formar?* · "
        "*posso me matricular em X?* · *se eu tirar 9 em uma disciplina de 4 "
        "créditos, meu CR vai a quanto?*"
    )
    linhas.append("")
    linhas.append(
        "*Os dados ficam apenas nesta conversa (sessão) e são descartados depois.*"
    )
    return "\n".join(linhas)


def _norm(text: str) -> str:
    t = "".join(
        c for c in unicodedata.normalize("NFD", str(text or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", t).strip()


_CR_CUES_RES = [re.compile(p) for p in (
    r"\bmeu\s+(?:cr|coeficiente)\b",
    r"\b(?:qual|quanto)\s+(?:e|eh|esta|ta)\s+(?:o\s+)?(?:meu\s+)?cr\b",
    r"\bcoeficiente\s+de\s+rendimento\b.*\bmeu\b",
    r"\bcalcul\w+\s+(?:o\s+)?(?:meu\s+)?cr\b",
    r"\bsimul\w+\s+(?:o\s+)?(?:meu\s+)?cr\b",
)]


def is_cr_request(texto: str) -> bool:
    q = _norm(texto)
    return any(p.search(q) for p in _CR_CUES_RES)


_SIM_RE = re.compile(
    r"tirar\s+(\d+[.,]?\d*)\s+em\s+(?:uma\s+)?(.+?)(?:\s+de\s+(\d+)\s+cr[eé]ditos?)?(?:[.?,]|$)"
)


def extrair_simulacao(texto: str) -> List[Tuple[float, Optional[str], Optional[int]]]:
    sims = []
    for m in _SIM_RE.finditer(_norm(texto)):
        nota = _num(m.group(1))
        alvo = (m.group(2) or "").strip()
        creditos = int(m.group(3)) if m.group(3) else None
        if nota is not None:
            sims.append((nota, alvo or None, creditos))
    return sims


def responder_cr(dados: Optional[Dict], texto: str, kg=None) -> str:
    if not dados:
        return (
            "Para eu calcular ou simular o seu CR, envie o seu Histórico "
            "Acadêmico (PDF) pelo botão **Histórico** no topo do chat. Ele fica "
            "só nesta conversa e é descartado depois. O CR da UNIFESP é a média "
            "ponderada dos conceitos pelas unidades de crédito de cada UC."
        )
    cr = dados.get("cr_geral") or dados.get("cr_calculado")
    linhas = [f"Seu CR geral é **{cr}**."]
    if dados.get("cr_confere"):
        linhas.append(
            "Recalculei pela média ponderada (Σ nota × créditos / Σ créditos) "
            "sobre as UCs do seu histórico e o valor confere ✓."
        )
    sims = extrair_simulacao(texto)
    if sims:
        novas = []
        detalhes = []
        for nota, alvo, creditos in sims:
            cred = creditos
            nome_alvo = alvo
            if cred is None and alvo and kg is not None:
                node = kg._find_node(alvo, "disciplina")
                if node:
                    nome_alvo = kg.graph.nodes[node].get("nome", alvo)
                    ch = kg.graph.nodes[node].get("carga_horaria")
                    for mz in kg._matrizes_de(node):
                        t = kg.graph.get_edge_data(mz, node) or {}
                        for e in t.values():
                            c = e.get("creditos")
                            if c:
                                try:
                                    cred = int(c)
                                except (TypeError, ValueError):
                                    pass
                            if cred:
                                break
                        if cred:
                            break
            if cred is None:
                cred = 4
            novas.append((nota, cred))
            detalhes.append(f"{nota} em {nome_alvo or 'uma UC'} ({cred} créditos)")
        novo_cr = simular_cr(dados.get("disciplinas", []), novas)
        if novo_cr is not None:
            linhas.append(
                f"**Simulação**: tirando {', '.join(detalhes)}, seu CR iria de "
                f"{cr} para **{novo_cr}**."
            )
    ultimos = dados.get("semestres", [])[-3:]
    if ultimos:
        trilha = " → ".join(f"{s['ano_sem']}: {s['cr']}" for s in ultimos if s.get("cr"))
        if trilha:
            linhas.append(f"Evolução recente por semestre: {trilha}.")
    linhas.append(
        "\n*Cálculo determinístico sobre o seu histórico (média ponderada "
        "nota × créditos). O CR vale prioridade de vaga pelo art. 112 da Prograd.*"
    )
    return "\n".join(linhas)
