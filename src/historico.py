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
_HORAS_FIXAS_RE = re.compile(r"^FIXAS\s+(\d+)\s*$", re.MULTILINE)
_HORAS_ELETIVAS_RE = re.compile(r"^ELETIVAS\s+(\d+)\s*$", re.MULTILINE)
_HORAS_TOTAL_RE = re.compile(
    r"Total de horas cumpridas pelo estudante[^\d]*(\d+)"
)
_HORAS_EXT_RE = re.compile(
    r"Carga hor[áa]ria extensionista:\s*(\d+)\s*horas"
)

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

    horas = {}
    for chave, pat in (
        ("fixas", _HORAS_FIXAS_RE),
        ("eletivas", _HORAS_ELETIVAS_RE),
        ("total", _HORAS_TOTAL_RE),
        ("extensao", _HORAS_EXT_RE),
    ):
        m = pat.search(texto or "")
        if m:
            horas[chave] = int(m.group(1))

    dados = {
        "curso": curso,
        "cr_geral": cr_geral,
        "semestres": semestres,
        "disciplinas": disciplinas,
        "horas": horas,
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
    horas = dados.get("horas") or {}
    cr = dados.get("cr_geral") or dados.get("cr_calculado")
    curso = dados.get("curso") or "curso não identificado"
    sigla = curso_sigla(curso)

    linhas = ["**Prontinho, li o seu histórico!**", ""]
    frase_cr = f"Você está no **{sigla or curso}** com CR geral **{cr}**"
    if dados.get("cr_confere"):
        frase_cr += " - recalculei nota por nota e o valor bate com o documento ✓"
    linhas.append(frase_cr + ".")
    linhas.append("")
    linhas.append("O que encontrei:")
    frase_discs = (
        f"- **{len(discs)} UCs** cursadas: {len(aprov)} aprovações"
    )
    if reprov:
        nomes = ", ".join(f"{d['nome']} em {d['ano_sem']}" for d in reprov)
        frase_discs += f" e {len(reprov)} reprovação(ões) ({nomes})"
    linhas.append(frase_discs)
    if horas.get("total"):
        detalhe = []
        if horas.get("fixas"):
            detalhe.append(f"{horas['fixas']}h em fixas")
        if horas.get("eletivas"):
            detalhe.append(f"{horas['eletivas']}h em eletivas")
        frase_h = f"- **{horas['total']}h cumpridas**"
        if detalhe:
            frase_h += f" ({' + '.join(detalhe)})"
        if horas.get("extensao"):
            frase_h += f", sendo **{horas['extensao']}h de extensão**"
        linhas.append(frase_h)
    if inter:
        frase_i = f"- **{len(inter)} UCs Eletivas Interdisciplinares**"
        if sigla == "BCT":
            frase_i += " - o PPC pede 4" + (
                ", requisito batido ✓" if len(inter) >= 4 else ""
            )
        linhas.append(frase_i)
    elif sigla == "BCT":
        linhas.append(
            "- Nenhuma UC Eletiva Interdisciplinar ainda (o PPC pede 4)"
        )
    linhas.append("")
    linhas.append(
        "Agora é só perguntar: *quanto falta para me formar?* · *qual meu CR?* · "
        "*posso me matricular em X?* · *se eu passar com 8 em todas, quanto "
        "fica meu CR?*"
    )
    linhas.append("")
    linhas.append(
        "*Seus dados ficam só nesta conversa e são descartados depois - nada é "
        "salvo em conta ou servidor.*"
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
    r"\bquanto\s+(?:vai\s+)?fica\w*\b.*\bcr\b",
    r"\bcr\b.*\bquanto\s+(?:vai\s+)?fica\w*\b",
    r"\bquanto\s+preciso\s+tirar\b",
    r"\bprevisao\s+d[eo]\s+cr\b",
)]


def is_cr_request(texto: str) -> bool:
    q = _norm(texto)
    return any(p.search(q) for p in _CR_CUES_RES)


_SIM_RE = re.compile(
    r"tirar\s+(\d+[.,]?\d*)\s+em\s+(?:uma\s+)?(.+?)(?:\s+de\s+(\d+)\s+cr[eé]ditos?)?(?:[.?,]|$)"
)
_CURSANDO_RE = re.compile(
    r"(?:estou|esto|to|tou)\s+(?:fazendo|cursando)\s+(?:essas?\s+disciplinas?\s*:?\s+)?(.+?)"
    r"(?:\s+(?:esse|este|neste|nesse|no)\s+semestre)?\s*(?:[.?!;]|$)"
)
_NOTA_UNIFORME_RE = re.compile(
    r"(?:passar|tirar|fechar)\s+(?:com\s+|de\s+)?(?:nota\s+)?(\d+[.,]?\d*)\s+em\s+(?:todas|tudo|cada)"
)
_ALVO_CR_RE = re.compile(
    r"(?:cr|coeficiente)\s*(?:geral\s*)?(?:chegar|ficar|ir|subir|bater)\s+"
    r"(?:a|em|para|pra|ate)\s+(\d+[.,]?\d*)"
    r"|(?:chegar|ficar|ir|subir|bater)\s+(?:a|em|para|pra|ate)\s+(?:cr\s+)?(\d+[.,]\d+)"
)


def extrair_cursando(texto: str) -> List[str]:
    m = _CURSANDO_RE.search(_norm(texto))
    if not m:
        return []
    trecho = m.group(1)
    trecho = re.sub(r"\b(?:e\s+)?(?:se\s+eu|quanto|qual)\b.*$", "", trecho).strip(" ,;")
    partes = re.split(r",| e |;", trecho)
    return [p.strip(" .?!") for p in partes if p and len(p.strip(" .?!")) >= 3]


def is_cursando_decl(texto: str) -> bool:
    return bool(extrair_cursando(texto))


def extrair_nota_uniforme(texto: str) -> Optional[float]:
    m = _NOTA_UNIFORME_RE.search(_norm(texto))
    return _num(m.group(1)) if m else None


def extrair_alvo_cr(texto: str) -> Optional[float]:
    q = _norm(texto)
    if not re.search(r"\b(?:preciso|necessari|quanto\s+tenho\s+que\s+tirar)\b", q) \
            and not re.search(r"\bcr\b.*\b(?:chegar|ficar|subir|bater)\b", q):
        return None
    m = _ALVO_CR_RE.search(q)
    if not m:
        return None
    return _num(m.group(1) or m.group(2))


def nota_necessaria(disciplinas: List[Dict], creditos_novos: List[int],
                    alvo: float) -> Optional[float]:
    soma, creditos = 0.0, 0
    for d in disciplinas:
        if d.get("nota") is None or not d.get("creditos"):
            continue
        soma += d["nota"] * d["creditos"]
        creditos += d["creditos"]
    c_novos = sum(creditos_novos)
    if not c_novos:
        return None
    return round((alvo * (creditos + c_novos) - soma) / c_novos, 2)


def extrair_simulacao(texto: str) -> List[Tuple[float, Optional[str], Optional[int]]]:
    sims = []
    for m in _SIM_RE.finditer(_norm(texto)):
        nota = _num(m.group(1))
        alvo = (m.group(2) or "").strip()
        creditos = int(m.group(3)) if m.group(3) else None
        if nota is not None:
            sims.append((nota, alvo or None, creditos))
    return sims


def _resolver_disciplina_kg(kg, nome: str) -> Tuple[Optional[str], Optional[int]]:
    if kg is None or not nome:
        return None, None
    node = kg._find_node(nome, "disciplina")
    if not node:
        return None, None
    nome_kg = kg.graph.nodes[node].get("nome", nome)
    cred = None
    try:
        for mz in kg._matrizes_de(node):
            edge_data = kg.graph.get_edge_data(mz, node) or {}
            for e in edge_data.values():
                c = e.get("creditos")
                if c:
                    try:
                        cred = int(c)
                        break
                    except (TypeError, ValueError):
                        pass
            if cred:
                break
    except Exception:
        cred = None
    return nome_kg, cred


def registrar_cursando(dados: Dict, nomes: List[str], kg=None) -> List[Dict]:
    itens = []
    for nome in nomes:
        nome_kg, cred = _resolver_disciplina_kg(kg, nome)
        itens.append({
            "nome": nome_kg or nome.title(),
            "creditos": cred or 4,
            "no_kg": nome_kg is not None,
        })
    dados["cursando"] = itens
    return itens


def responder_cursando(dados: Dict, texto: str, kg=None) -> str:
    itens = registrar_cursando(dados, extrair_cursando(texto), kg)
    linhas = ["**Anotei o seu semestre atual nesta conversa:**", ""]
    for i in itens:
        marca = "" if i["no_kg"] else " (não achei no sistema; assumi 4 créditos)"
        linhas.append(f"- {i['nome']} ({i['creditos']} créditos){marca}")
    linhas.append("")
    if dados.get("disciplinas"):
        linhas.append(
            "Agora posso prever seu CR: pergunte *\"se eu passar com 8 em "
            "todas, quanto fica meu CR?\"*, *\"e se eu tirar 9 em "
            f"{itens[0]['nome']}?\"* ou *\"quanto preciso tirar para meu CR "
            "chegar a 8.5?\"*"
        )
    else:
        linhas.append(
            "Para eu prever o CR com precisão, envie também o seu Histórico "
            "Acadêmico (PDF) pelo botão **Histórico** no topo do chat."
        )
    return "\n".join(linhas)


def responder_cr(dados: Optional[Dict], texto: str, kg=None) -> str:
    if not dados or not dados.get("disciplinas"):
        return (
            "Para eu calcular ou simular o seu CR, envie o seu Histórico "
            "Acadêmico (PDF) pelo botão **Histórico** no topo do chat. Ele fica "
            "só nesta conversa e é descartado depois. O CR da UNIFESP é a média "
            "ponderada dos conceitos pelas unidades de crédito de cada UC."
        )
    if extrair_cursando(texto):
        registrar_cursando(dados, extrair_cursando(texto), kg)

    cr = dados.get("cr_geral") or dados.get("cr_calculado")
    disciplinas = dados.get("disciplinas", [])
    cursando = dados.get("cursando") or []
    linhas = [f"Seu CR geral é **{cr}**."]
    if dados.get("cr_confere"):
        linhas.append(
            "Recalculei pela média ponderada (Σ nota × créditos / Σ créditos) "
            "sobre as UCs do seu histórico e o valor confere ✓."
        )

    alvo = extrair_alvo_cr(texto)
    nota_todas = extrair_nota_uniforme(texto)
    sims = extrair_simulacao(texto)

    if alvo is not None and cursando:
        creditos_novos = [c["creditos"] for c in cursando]
        necessaria = nota_necessaria(disciplinas, creditos_novos, alvo)
        if necessaria is not None:
            nomes = ", ".join(c["nome"] for c in cursando)
            if necessaria > 10:
                linhas.append(
                    f"**Meta {alvo}**: mesmo com 10 em {nomes} "
                    f"({sum(creditos_novos)} créditos), o CR não chega a {alvo} "
                    f"neste semestre - seria preciso média {necessaria}. A meta "
                    "fica para mais semestres."
                )
            elif necessaria <= 0:
                linhas.append(
                    f"**Meta {alvo}**: qualquer nota de aprovação em {nomes} já "
                    f"leva seu CR além de {alvo}."
                )
            else:
                linhas.append(
                    f"**Meta {alvo}**: você precisa de média **{necessaria}** "
                    f"nas UCs deste semestre ({nomes}, {sum(creditos_novos)} "
                    "créditos) para o CR chegar lá."
                )
    elif alvo is not None and not cursando:
        linhas.append(
            f"Para calcular o que você precisa tirar para chegar a {alvo}, me "
            "diga primeiro o que está cursando: *\"estou fazendo X, Y e Z esse "
            "semestre\"*."
        )

    if nota_todas is not None and cursando:
        novas = [(nota_todas, c["creditos"]) for c in cursando]
        novo_cr = simular_cr(disciplinas, novas)
        if novo_cr is not None:
            nomes = ", ".join(c["nome"] for c in cursando)
            linhas.append(
                f"**Cenário**: passando com {nota_todas} em todas ({nomes}), "
                f"seu CR iria de {cr} para **{novo_cr}**."
            )
    elif nota_todas is not None and not cursando:
        linhas.append(
            "Me diga o que está cursando (*\"estou fazendo X, Y e Z esse "
            "semestre\"*) que eu simulo o CR com essa nota em todas."
        )

    if sims:
        novas = []
        detalhes = []
        for nota, alvo_nome, creditos in sims:
            nome_kg, cred_kg = _resolver_disciplina_kg(kg, alvo_nome or "")
            cred = creditos or cred_kg or 4
            novas.append((nota, cred))
            detalhes.append(
                f"{nota} em {nome_kg or alvo_nome or 'uma UC'} ({cred} créditos)"
            )
        novo_cr = simular_cr(disciplinas, novas)
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
