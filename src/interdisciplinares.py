"""
UCs Eletivas Interdisciplinares (Integradoras de Conhecimento) do PPC 2023.

Responde a lista completa (com chips clicáveis) e a verificação pontual
("X é interdisciplinar?"), sempre a partir da flag aterrada no Knowledge Graph.
"""

import re
import unicodedata
from typing import Dict, List, Optional


def _norm(text: str) -> str:
    t = "".join(
        c for c in unicodedata.normalize("NFD", str(text or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", t).strip()


_LISTA_RES = [re.compile(p) for p in (
    r"\b(?:quais|que|lista\s+de|liste\s+as?)\b.*\binterdisciplinar",
    r"\binterdisciplinares\s+(?:do\s+bct|disponiveis|que\s+(?:tem|existem))\b",
    r"\bintegradoras\s+de\s+conhecimento\b",
    r"\bquantas\s+(?:ucs?\s+)?interdisciplinares\b",
)]


def is_lista_interdisciplinares(texto: str) -> bool:
    q = _norm(texto)
    return any(p.search(q) for p in _LISTA_RES)


_CHECK_RE = re.compile(
    r"(.+?)\s+(?:e|eh|seria|conta\s+como|vale\s+como)\s+"
    r"(?:uma\s+)?(?:uc\s+|eletiva\s+|disciplina\s+)?interdisciplinar"
)


def extrair_disciplina_check(texto: str) -> Optional[str]:
    m = _CHECK_RE.search(_norm(texto))
    if not m:
        return None
    alvo = m.group(1)
    alvo = re.sub(
        r"^.*?\b(?:a\s+disciplina|a\s+uc|a\s+materia|sera\s+que|sabe\s+se|se)\s+",
        "", alvo,
    ).strip(" ?.!,")
    return alvo or None


def responder_lista(kg) -> Optional[Dict]:
    ucs = kg.get_interdisciplinares()
    if not ucs:
        return None
    regra = getattr(kg, "_interdisciplinares_regra", {}) or {}
    qtd = regra.get("quantidade_obrigatoria", 4)
    linhas = [
        f"**UCs Eletivas Interdisciplinares do BCT** ({len(ucs)} opções)",
        "",
        f"Para concluir o BCT você precisa cursar, com aproveitamento, "
        f"**{qtd} UCs Eletivas Interdisciplinares** (Integradoras de "
        "Conhecimento), independentemente da carga horária.",
        "",
    ]
    for u in ucs:
        cod = f" (código {u['codigo']})" if u.get("codigo") else ""
        linhas.append(f"- {u['nome']}{cod}")
    linhas.append("")
    linhas.append(
        f"*Fonte: {regra.get('fonte', 'PPC 2023 do BCT')}. Clique numa "
        "disciplina para ver ementa, pré-requisitos e docentes.*"
    )
    chips = {
        "type": "discipline_list",
        "title": f"Eletivas interdisciplinares ({len(ucs)})",
        "items": [{"nome": u["nome"], "hint": u.get("codigo")} for u in ucs],
    }
    return {"texto": "\n".join(linhas), "chips": chips}


def responder_check(kg, disciplina: str) -> Optional[str]:
    flag = kg.is_interdisciplinar(disciplina)
    if flag is None:
        return None
    node = kg._find_node(disciplina, "disciplina")
    nome = kg.graph.nodes[node].get("nome", disciplina)
    regra = getattr(kg, "_interdisciplinares_regra", {}) or {}
    qtd = regra.get("quantidade_obrigatoria", 4)
    if flag:
        return (
            f"Sim! **{nome}** está na lista de UCs Eletivas Interdisciplinares "
            f"(Integradoras de Conhecimento) do PPC 2023 e conta para as "
            f"**{qtd} UCs interdisciplinares** exigidas na conclusão do BCT.\n\n"
            "*Verificado na lista oficial do PPC 2023 aterrada no Knowledge Graph.*"
        )
    return (
        f"Não. **{nome}** não está na lista de UCs Eletivas Interdisciplinares "
        f"do PPC 2023, então não conta para as {qtd} UCs interdisciplinares "
        "exigidas na conclusão do BCT. Se quiser, pergunte \"quais são as "
        "eletivas interdisciplinares?\" para ver a lista completa.\n\n"
        "*Verificado na lista oficial do PPC 2023 aterrada no Knowledge Graph.*"
    )
