"""
Previsão de oferta por paridade do termo.

Heurística institucional: disciplinas de termo ímpar são normalmente ofertadas
no 1º semestre do ano (X/1) e as de termo par no 2º (X/2). É previsão, não
garantia: a oferta real é definida pela coordenação a cada semestre, e as
respostas sempre dizem "vale confirmar".
"""

import re
import unicodedata
from datetime import date
from typing import Optional, Tuple


def semestre_de(data: Optional[date] = None) -> Tuple[int, int]:
    d = data or date.today()
    return (d.year, 1 if d.month <= 6 else 2)


def proximo_semestre(data: Optional[date] = None) -> Tuple[int, int]:
    ano, sem = semestre_de(data)
    return (ano, 2) if sem == 1 else (ano + 1, 1)


def rotulo(sem: Tuple[int, int]) -> str:
    return f"{sem[0]}/{sem[1]}"


def paridade_do_semestre(sem: Tuple[int, int]) -> str:
    return "impar" if sem[1] == 1 else "par"


def ofertada_em(paridade_disciplina: Optional[str], sem: Tuple[int, int]) -> Optional[bool]:
    if paridade_disciplina not in ("impar", "par"):
        return None
    return paridade_disciplina == paridade_do_semestre(sem)


def proxima_oferta(paridade_disciplina: Optional[str],
                   data: Optional[date] = None) -> Optional[Tuple[int, int]]:
    if paridade_disciplina not in ("impar", "par"):
        return None
    sem = proximo_semestre(data)
    if ofertada_em(paridade_disciplina, sem):
        return sem
    ano, s = sem
    return (ano, 2) if s == 1 else (ano + 1, 1)


def nota_oferta(paridade_disciplina: Optional[str],
                data: Optional[date] = None) -> Optional[str]:
    if paridade_disciplina not in ("impar", "par"):
        return None
    prox = proximo_semestre(data)
    nome_par = "ímpares" if paridade_disciplina == "impar" else "pares"
    if ofertada_em(paridade_disciplina, prox):
        return (
            f"oferta esperada no próximo semestre ({rotulo(prox)}), pois é de "
            f"termo {'ímpar' if paridade_disciplina == 'impar' else 'par'}"
        )
    prox_oferta = proxima_oferta(paridade_disciplina, data)
    return (
        f"termo {'ímpar' if paridade_disciplina == 'impar' else 'par'}: oferta "
        f"esperada apenas em semestres {nome_par} - próxima em "
        f"{rotulo(prox_oferta)}, não no próximo semestre"
    )


def _norm(text: str) -> str:
    t = "".join(
        c for c in unicodedata.normalize("NFD", str(text or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", t).strip()


_QUANDO = r"(?:no\s+)?(?:proximo\s+semestre|semestre\s+que\s+vem|esse\s+semestre|este\s+semestre|neste\s+semestre)"

_OFERTA_RES = [
    re.compile(rf"\b(?:vai\s+ter|tera|vai\s+abrir|vai\s+rolar|vao\s+ofertar|vai\s+ser\s+ofertad[ao])\s+(?:a\s+|o\s+|uc\s+de\s+|disciplina\s+de\s+)?(.+?)\s+{_QUANDO}"),
    re.compile(rf"\b(.+?)\s+(?:vai\s+ter|tera|abre|e\s+ofertad[ao]|sera\s+ofertad[ao]|vai\s+ser\s+ofertad[ao]|vai\s+abrir|tem\s+oferta)\s+{_QUANDO}"),
    re.compile(r"\b(?:em\s+)?(?:qual|que)\s+semestre\s+(?:e\s+ofertad[ao]|tem|abre|oferecem|vai\s+ter|da\s+pra\s+fazer)\s+(?:a\s+|o\s+|uc\s+de\s+|disciplina\s+de\s+)?(.+)"),
    re.compile(r"\bquando\s+(?:e\s+ofertad[ao]|sera\s+ofertad[ao]|tem\s+oferta\s+de|abre|oferecem|vai\s+ter)\s+(?:a\s+|o\s+|uc\s+de\s+|disciplina\s+de\s+)?(.+)"),
    re.compile(r"\b(.+?)\s+(?:e\s+ofertad[ao]|abre|tem\s+oferta|oferecem)\s+em\s+(?:qual|que)\s+semestre"),
    re.compile(r"\b(.+?)\s+(?:e\s+de\s+)?semestre\s+(?:par|impar)\s*\?"),
]


def extrair_disciplina_oferta(texto: str) -> Optional[str]:
    q = _norm(texto)
    if not re.search(r"\bsemestre", q):
        return None
    for pat in _OFERTA_RES:
        m = pat.search(q)
        if m:
            alvo = m.group(1).strip(" ?.!,")
            alvo = re.sub(r"^(?:sera\s+que|sabe\s+se|voce\s+sabe\s+se|se)\s+", "", alvo)
            alvo = re.sub(r"^(?:a|o|as|os)\s+", "", alvo).strip(" ?.!,")
            if alvo and len(alvo) >= 3:
                return alvo
    return None


def is_oferta_request(texto: str) -> bool:
    return extrair_disciplina_oferta(texto) is not None


def responder_oferta(kg, disciplina: str, data: Optional[date] = None) -> Optional[str]:
    node = kg._find_node(disciplina, "disciplina")
    if not node:
        return None
    nome = kg.graph.nodes[node].get("nome", disciplina)
    paridade = kg.paridade_oferta(nome)
    prox = proximo_semestre(data)
    atual = semestre_de(data)

    linhas = [f"**Oferta de {nome}:**", ""]
    if paridade not in ("impar", "par"):
        termo = kg._termo_num(kg.graph.nodes[node])
        if paridade == "ambos":
            linhas.append(
                f"- {nome} aparece em termos de paridades diferentes conforme a "
                "matriz do curso, então a previsão pela paridade não se aplica - "
                "confirme a oferta diretamente com a coordenação."
            )
        elif termo is None:
            linhas.append(
                f"- {nome} não tem termo fixo na matriz (eletiva), então a "
                "oferta varia semestre a semestre - confirme com a coordenação "
                "ou no sistema de matrícula."
            )
        else:
            return None
        return "\n".join(linhas)

    nome_par = "ímpares" if paridade == "impar" else "pares"
    linhas.append(
        f"- {nome} é de termo {'ímpar' if paridade == 'impar' else 'par'}, "
        f"então a oferta esperada é em **semestres {nome_par}** (X/"
        f"{'1' if paridade == 'impar' else '2'})."
    )
    if ofertada_em(paridade, atual):
        linhas.append(f"- No semestre atual ({rotulo(atual)}) ela deve estar em oferta.")
    if ofertada_em(paridade, prox):
        linhas.append(
            f"- **Próximo semestre ({rotulo(prox)}): deve ter oferta** ✓"
        )
    else:
        linhas.append(
            f"- **Próximo semestre ({rotulo(prox)}): não era para ter** - a "
            f"próxima oferta esperada é em **{rotulo(proxima_oferta(paridade, data))}**."
        )
    linhas.append("")
    linhas.append(
        "*Previsão pela paridade do termo na matriz curricular. A oferta real é "
        "definida pela coordenação a cada semestre - vale confirmar.*"
    )
    return "\n".join(linhas)
