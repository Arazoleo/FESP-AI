"""
Auditor de Atividades Complementares: aplica as regras do regulamento ao caso
concreto do aluno.

Capacidades:
- classificar uma atividade descrita em linguagem natural no eixo correto
  (casamento determinístico contra as atividades aceitas do regulamento);
- auditar uma lista de atividades com horas, simulando a acreditação com as
  regras como código (teto de 104h no eixo I, mínimo de 1h por eixo, 312h
  totais, máximo de 2 certificados por instituição exceto UNIFESP);
- gerar o checklist de peticionamento do SEI a partir do manual da DAE.

O parser de entrada é regex-first e o aterramento é obrigatório: nada que não
casar com o regulamento vira decisão.
"""

import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_REGULAMENTO_PATH = (
    Path(__file__).resolve().parent.parent
    / "jsons_regimentos"
    / "regulamento_atividades_complementares_bct_2023.json"
)

TOTAL_HORAS = 312
TETO_EIXO_1 = 104
MIN_POR_EIXO = 1
MAX_CERT_POR_INSTITUICAO = 2

_EIXO_NOMES = {
    1: "Eixo I - Formação Cidadã, Cultural ou Artística",
    2: "Eixo II - Orientação Acadêmica ou Monitoria",
    3: "Eixo III - Formação Pessoal, Científica ou Profissional",
}

_SINONIMOS = {
    1: [
        ("doação de sangue", ["doacao de sangue", "doei sangue", "doar sangue", "medula", "redome", "hemocentro"]),
        ("atividades artísticas", ["teatro", "danca", "canto", "coral", "banda", "musica", "instrumental", "circo", "performatic", "artistic"]),
        ("concursos culturais ou exposições", ["concurso cultural", "exposicao", "mostra cultural"]),
        ("serviços sociais e voluntariado", ["voluntari", "ong", "servico social", "acao social", "trabalho comunitario", "igreja", "pastoral"]),
        ("organização de eventos externos", ["organizacao de evento", "organizei evento", "organizar evento"]),
        ("centro acadêmico ou atlética", ["centro academico", "caak", "atletica", "aaaja", "bateria universitaria"]),
    ],
    2: [
        ("monitoria, tutoria ou orientação", ["monitoria", "monitor", "tutor", "tutoria", "orientador academico"]),
        ("recepção de estudantes estrangeiros", ["mobilidade internacional", "estudantes estrangeiros", "intercambistas"]),
        ("atividades da DAE", ["dae"]),
        ("atividades do NAE ou NAI", ["nae", "nai", "assistencia estudantil", "acessibilidade e inclusao"]),
        ("orientação sobre os cursos para ensino médio", ["ensino medio", "divulgacao dos cursos", "feira de profissoes"]),
        ("recepção de calouros e matrículas", ["recepcao de calouros", "acolhimento de calouros", "semana de recepcao", "matricula de ingressantes"]),
    ],
    3: [
        ("iniciação científica", ["iniciacao cientifica", "ic ", " ic,", " ic.", "pibic", "pibiti", "bolsista de pesquisa"]),
        ("eventos científicos como ouvinte", ["congresso", "palestra", "ouvinte", "workshop", "semana academica", "evento cientifico", "seminario"]),
        ("apresentação de trabalhos", ["apresentacao de trabalho", "apresentei trabalho", "poster", "artigo em congresso"]),
        ("competições científicas e tecnológicas", ["competicao", "maratona de programacao", "hackathon", "olimpiada", "torneio de robotica"]),
        ("estágio não obrigatório", ["estagio"]),
        ("atividade profissional em C&T", ["atividade profissional", "clt", "carteira assinada", "emprego", "trabalho em empresa", "jovem aprendiz"]),
        ("cursos de línguas estrangeiras", ["ingles", "espanhol", "frances", "alemao", "idioma", "lingua estrangeira", "curso de lingua"]),
        ("UC optativa", ["optativa", "unidade curricular optativa"]),
        ("cursos e capacitações", ["curso online", "curso de", "certificacao", "capacitacao", "treinamento", "bootcamp", "alura", "coursera", "udemy"]),
    ],
}

_UNIFESP_RE = re.compile(r"\bunifesp\b|\bict\b")


def _norm(text: str) -> str:
    t = "".join(
        c for c in unicodedata.normalize("NFD", str(text or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", t).strip()


def classificar_eixo(descricao: str) -> Optional[Dict]:
    """
    Classifica uma atividade no eixo pelo casamento com as atividades aceitas
    do regulamento. Retorna {eixo, eixo_nome, atividade} ou None se nada casa.
    """
    d = f" {_norm(descricao)} "
    melhor = None
    melhor_tam = 0
    for eixo, entradas in _SINONIMOS.items():
        for atividade, chaves in entradas:
            for chave in chaves:
                alvo = chave if chave.startswith(" ") or chave.endswith(" ") else f"{chave}"
                if alvo in d and len(chave) > melhor_tam:
                    melhor = {
                        "eixo": eixo,
                        "eixo_nome": _EIXO_NOMES[eixo],
                        "atividade": atividade,
                    }
                    melhor_tam = len(chave)
    return melhor


_ITEM_SPLIT_RE = re.compile(r"[;\n]+|,\s+(?=\d)|\.\s+(?=\d)")
_HORAS_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*h(?:oras?|rs?)?\b")
_INSTITUICAO_RE = re.compile(
    r"\b(?:na|no|pela|pelo|da|do)\s+([A-ZÀ-Ú][\w.&-]*(?:\s+[A-ZÀ-Ú][\w.&-]*)*)"
)


def parsear_atividades(texto: str) -> List[Dict]:
    """
    Extrai itens {descricao, horas, instituicao} de uma lista em linguagem
    natural. Determinístico: segmentos sem horas explícitas são descartados
    (e reportados ao aluno para correção).
    """
    itens = []
    for bruto in _ITEM_SPLIT_RE.split(texto or ""):
        seg = bruto.strip(" .,-")
        if not seg:
            continue
        m = _HORAS_RE.search(seg)
        if not m:
            continue
        horas = float(m.group(1).replace(",", "."))
        if horas <= 0:
            continue
        instituicao = None
        mi = _INSTITUICAO_RE.search(seg)
        if mi:
            instituicao = mi.group(1).strip()
        itens.append({
            "descricao": seg,
            "horas": horas,
            "instituicao": instituicao,
        })
    return itens


def auditar_atividades(itens: List[Dict]) -> Dict:
    """
    Simula a acreditação: classifica cada item, aplica os tetos e mínimos do
    regulamento e devolve o balanço por eixo com pendências e avisos.
    """
    classificados, nao_classificados = [], []
    for item in itens:
        c = classificar_eixo(item.get("descricao", ""))
        registro = {**item, **(c or {})}
        if c:
            classificados.append(registro)
        else:
            nao_classificados.append(registro)

    brutas = {1: 0.0, 2: 0.0, 3: 0.0}
    for r in classificados:
        brutas[r["eixo"]] += float(r["horas"])

    validas = dict(brutas)
    excedente_eixo1 = 0.0
    if validas[1] > TETO_EIXO_1:
        excedente_eixo1 = validas[1] - TETO_EIXO_1
        validas[1] = TETO_EIXO_1

    total_valido = min(sum(validas.values()), TOTAL_HORAS + 0)
    faltam = max(0.0, TOTAL_HORAS - sum(validas.values()))

    pendencias = []
    for eixo in (1, 2, 3):
        if brutas[eixo] < MIN_POR_EIXO:
            pendencias.append(
                f"nenhuma hora no {_EIXO_NOMES[eixo]} (mínimo de {MIN_POR_EIXO}h)"
            )

    avisos = []
    if excedente_eixo1:
        avisos.append(
            f"{excedente_eixo1:.0f}h do Eixo I excedem o teto de {TETO_EIXO_1}h e não contam"
        )
    contagem_inst: Dict[str, int] = {}
    for r in classificados:
        inst = _norm(r.get("instituicao") or "")
        if inst and not _UNIFESP_RE.search(inst):
            contagem_inst[inst] = contagem_inst.get(inst, 0) + 1
    for inst, qtd in contagem_inst.items():
        if qtd > MAX_CERT_POR_INSTITUICAO:
            avisos.append(
                f"{qtd} certificados de '{inst}': só {MAX_CERT_POR_INSTITUICAO} "
                "de uma mesma instituição são aceitos (exceto UNIFESP)"
            )

    return {
        "itens": classificados,
        "nao_classificados": nao_classificados,
        "horas_brutas": brutas,
        "horas_validas": validas,
        "total_valido": sum(validas.values()),
        "faltam": faltam,
        "pendencias": pendencias,
        "avisos": avisos,
        "apto": faltam == 0 and not pendencias,
    }


def formatar_auditoria(resultado: Dict) -> str:
    linhas = ["**Simulação de acreditação das suas Atividades Complementares**", ""]
    for eixo in (1, 2, 3):
        validas = resultado["horas_validas"][eixo]
        brutas = resultado["horas_brutas"][eixo]
        extra = f" (de {brutas:.0f}h informadas)" if brutas != validas else ""
        status = "✓" if brutas >= MIN_POR_EIXO else "✗"
        linhas.append(f"- {_EIXO_NOMES[eixo]}: **{validas:.0f}h**{extra} {status}")
    linhas.append("")
    linhas.append(
        f"**Total válido: {resultado['total_valido']:.0f}h de {TOTAL_HORAS}h**"
        + (
            " - você já pode solicitar a validação!"
            if resultado["apto"]
            else f" - faltam **{resultado['faltam']:.0f}h**"
        )
    )

    if resultado["itens"]:
        linhas.append("")
        linhas.append("Como classifiquei cada atividade:")
        for r in resultado["itens"]:
            linhas.append(
                f"- {r['descricao']} → eixo {r['eixo']} ({r['atividade']})"
            )
    if resultado["nao_classificados"]:
        linhas.append("")
        linhas.append(
            "Não consegui classificar (verifique com a coordenação em "
            "coordenacao.bct@unifesp.br):"
        )
        for r in resultado["nao_classificados"]:
            linhas.append(f"- {r['descricao']}")
    if resultado["pendencias"]:
        linhas.append("")
        linhas.append("**Pendências obrigatórias:**")
        for p in resultado["pendencias"]:
            linhas.append(f"- {p}")
    if resultado["avisos"]:
        linhas.append("")
        linhas.append("**Avisos:**")
        for a in resultado["avisos"]:
            linhas.append(f"- {a}")

    linhas.append("")
    linhas.append(
        "*Regras aplicadas: teto de 104h no Eixo I, mínimo de 1h por eixo, "
        "312h totais e máximo de 2 certificados por instituição (exceto "
        "UNIFESP), conforme o Regulamento de AC do BCT (2023) e o Manual da "
        "DAE (2025). Simulação orientativa: a decisão final é da comissão da "
        "Coordenação do BCT.*"
    )
    return "\n".join(linhas)


_AUDIT_CUES_RES = [re.compile(p) for p in (
    r"\b(?:audita|auditar|simul|confere|conferir|verifica|verificar|calcul|contabiliz|soma|somar)\w*\b.*\b(?:ac|acs|atividades? complementar)",
    r"\b(?:quanta?s?\s+horas?\s+(?:eu\s+)?(?:ja\s+)?tenho)\b",
    r"\bquanto\s+(?:ja\s+)?tenho\s+de\s+acs?\b",
    r"\bja\s+(?:posso|consigo)\s+(?:validar|enviar|peticionar)\b",
)]


def is_audit_request(question: str) -> bool:
    q = _norm(question)
    tem_horas = len(_HORAS_RE.findall(q)) >= 1
    tem_ac = bool(re.search(r"\bacs?\b|\batividades?\s+complementar", q))
    if tem_horas and tem_ac:
        return True
    return any(p.search(q) for p in _AUDIT_CUES_RES) and tem_ac


def responder_auditoria(question: str) -> str:
    itens = parsear_atividades(question)
    if not itens:
        return (
            "Posso simular a acreditação das suas Atividades Complementares! "
            "Me liste as atividades com as horas de cada uma, por exemplo:\n\n"
            "*40h de monitoria; 80h de curso de inglês na Cultura Inglesa; "
            "120h de iniciação científica; doação de sangue 4h*\n\n"
            "Eu classifico cada uma no eixo correto e aplico as regras do "
            "regulamento (teto de 104h no Eixo I, mínimo por eixo e as 312h totais)."
        )
    return formatar_auditoria(auditar_atividades(itens))


_CHECKLIST_CUES_RES = [re.compile(p) for p in (
    r"\bchecklist\b",
    r"\b(?:pronto|preparado)\s+para\s+(?:enviar|peticionar)\b",
    r"\b(?:o\s+que|que)\s+(?:preciso|falta)\s+(?:para|antes\s+de)\s+(?:enviar|peticionar|abrir\s+o\s+processo)\b",
    r"\bantes\s+de\s+peticionar\b",
)]


def is_checklist_request(question: str) -> bool:
    q = _norm(question)
    tem_ac = bool(re.search(r"\bacs?\b|\batividades?\s+complementar|\bsei\b", q))
    return tem_ac and any(p.search(q) for p in _CHECKLIST_CUES_RES)


def responder_checklist() -> str:
    return "\n".join([
        "**Checklist antes de peticionar suas Atividades Complementares no SEI**",
        "",
        "**Horas e eixos:**",
        "- [ ] Somou 312h em atividades comprovadas?",
        "- [ ] Tem pelo menos 1h em cada um dos três eixos?",
        "- [ ] O Eixo I não passa de 104h? (o excedente não conta)",
        "",
        "**Comprovantes:**",
        "- [ ] Certificados com emissor identificado, assinatura do responsável e instituição promotora?",
        "- [ ] Cada um com descrição da atividade, período e carga horária total (máximo 16h/dia)?",
        "- [ ] Certificados com verificação de autenticidade online?",
        "- [ ] No máximo 2 certificados por instituição (exceto UNIFESP)?",
        "- [ ] Declarações de estágio com dados, período, carga horária e assinatura eletrônica?",
        "- [ ] Comprovantes organizados em pastas por eixo?",
        "",
        "**Documentos do processo:**",
        "- [ ] Histórico Escolar solicitado com a finalidade \"Atividades Complementares (SEM assinatura da direção)\"? (o histórico on-line não serve)",
        "- [ ] Formulário de AC preenchido (baixe em .docx na página da secretaria)?",
        "- [ ] Cadastro de usuário externo no SEI liberado? (e-mail à secretaria com nome, RA, curso, CPF e período)",
        "",
        "**No peticionamento:**",
        "- [ ] Tipo: ABERTURA DE PROCESSO ACADÊMICO - GRADUAÇÃO (SP, São José dos Campos)",
        "- [ ] Especificação: \"Atividades Complementares\"",
        "- [ ] Formulário SA02 preenchido (documento principal, obrigatório)",
        "- [ ] Anexos: formulário de AC + Histórico Escolar + comprovantes, cada um com tipo e formato (nato-digital ou digitalizado)",
        "",
        "Envio preferencialmente no último semestre letivo, em uma única submissão, "
        "e todo o trâmite em um único processo SEI.",
        "",
        "*Fonte: Manual de Atividades Complementares da DAE (2025). Quer que eu "
        "simule suas horas? Me liste as atividades com as horas de cada uma.*",
    ])
