"""
Checagem de cobertura da resposta (Perceive/Evaluate do MetaKGRAG, KDD 2026).

O retry-on-miss (second_chance) só enxerga falha CONFESSA ("não encontrei").
Resposta INCOMPLETA passa calada: a pergunta cita duas entidades e a resposta
só trata de uma. Aqui a falha é detectada pela estrutura, não pelo texto:

- Perceive: entidades do KG citadas na PERGUNTA (grounding, sem regex de nome).
- Evaluate: cada uma está coberta na RESPOSTA? As que não estão formam a
  deficiência de completude, já dizendo QUAL entidade faltou.

Fase 1 = só observação (telemetria + log de interação); a resposta não muda.
O Adjust (completar a entidade faltante) fica para quando houver medida.

Sem dependências além do KG recebido, para rodar offline nos testes.
"""

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

# Agentes cuja saída não tem obrigação de citar as entidades da pergunta.
AGENTES_ISENTOS = frozenset({"clarify", "conversa", "meta"})

_ROMANOS = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5"}
_VAZIAS = frozenset({"a", "as", "o", "os", "de", "da", "do", "das", "dos", "e",
                     "em", "na", "no", "nas", "nos", "para", "com"})


def _tokens(texto: str) -> List[str]:
    """minúsculas, sem acento, sem pontuação, numeral romano → arábico."""
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return [_ROMANOS.get(w, w) for w in t.split()]


def _conteudo(nome: str) -> List[str]:
    return [w for w in _tokens(nome) if w not in _VAZIAS]


def entidades_da_pergunta(kg, pergunta: str) -> List[Tuple[str, str]]:
    """(tipo, nome) das entidades do KG citadas na pergunta."""
    if kg is None or not (pergunta or "").strip():
        return []
    out: List[Tuple[str, str]] = []
    try:
        for nome in kg.disciplinas_mencionadas(pergunta):
            out.append(("disciplina", nome))
        docentes = kg.docentes_mencionados(pergunta)
        if not docentes:
            unico = kg.docente_mencionado(pergunta)
            docentes = [unico] if unico else []
        for nome in docentes:
            out.append(("docente", nome))
    except Exception:
        return []
    return out


# Frase que cita a entidade só para dizer que não tem o dado dela ("Não
# possuo informações sobre Álgebra Linear") não a cobre: é a negação parcial
# que o retry-on-miss não vê, porque o resto da resposta está certo.
_AUSENCIA = re.compile(
    r"\bnao\s+(?:tenho|possuo|ha|encontrei|disponho)\b.{0,40}?\binformac"
    r"|\bnao\s+(?:mencionam|menciona|informam|constam?|tenho\s+esse\s+dado)\b"
    r"|\bsem\s+informac"
)


def _frases(texto: str) -> List[str]:
    return [f for f in re.split(r"(?<=[.!?;\n])\s+", texto or "") if f.strip()]


def _cita(tipo: str, nome: str, tokens: set, outros: set) -> bool:
    if tipo == "docente":
        # sobrenome comum a outra entidade da pergunta ("de Oliveira") não
        # distingue quem foi citado
        return any(len(w) >= 4 and w in tokens and w not in outros
                   for w in _tokens(nome))
    conteudo = _conteudo(nome)
    return bool(conteudo) and all(w in tokens for w in conteudo)


def entidade_coberta(tipo: str, nome: str, resposta: str,
                     outros_nomes: Optional[List[str]] = None) -> bool:
    """A resposta trata da entidade? Disciplina: todos os tokens de conteúdo do
    nome aparecem ("Introdução à/às", "Cálculo I/1" casam). Docente: um token
    do nome com 4+ letras ("Profa. Lilian", "Berton") que não seja de outra
    entidade da mesma pergunta. Precisa aparecer numa frase que não seja só a
    confissão de que falta o dado."""
    outros = {w for n in (outros_nomes or []) for w in _tokens(n)}
    for frase in _frases(resposta):
        tokens = _tokens(frase)
        if _cita(tipo, nome, set(tokens), outros) and not _AUSENCIA.search(" ".join(tokens)):
            return True
    return False


def avaliar_cobertura(kg, pergunta: str, resposta: str,
                      agente: str = "") -> Optional[Dict]:
    """Diagnóstico de completude da resposta, ou None quando não se aplica
    (agente isento, resposta vazia ou pergunta sem entidade do KG)."""
    if agente in AGENTES_ISENTOS or not (resposta or "").strip():
        return None
    entidades = entidades_da_pergunta(kg, pergunta)
    if not entidades:
        return None
    nomes = [nome for _, nome in entidades]
    faltantes = [nome for tipo, nome in entidades
                 if not entidade_coberta(tipo, nome, resposta,
                                         [n for n in nomes if n != nome])]
    # Nenhuma entidade coberta e a resposta confessa falta: é miss inteiro com
    # outra redação ("não tenho a informação sobre a sala de X"), não resposta
    # incompleta. Vai para a fila de miss, não para a de cobertura.
    if len(faltantes) == len(entidades) and any(
            _AUSENCIA.search(" ".join(_tokens(f))) for f in _frases(resposta)):
        return {"entidades": nomes, "faltantes": [], "cobertura": 0.0,
                "ausencia_confessa": True}
    return {
        "entidades": nomes,
        "faltantes": faltantes,
        "cobertura": round(1 - len(faltantes) / len(entidades), 3),
    }


def combinar_coberturas(coberturas: List[Optional[Dict]]) -> Optional[Dict]:
    """Une os diagnósticos das subperguntas de uma pergunta composta."""
    validas = [c for c in coberturas if c]
    if not validas:
        return None
    entidades, faltantes = [], []
    for c in validas:
        entidades += [e for e in c["entidades"] if e not in entidades]
        faltantes += [f for f in c["faltantes"] if f not in faltantes]
    return {
        "entidades": entidades,
        "faltantes": faltantes,
        "cobertura": round(1 - len(faltantes) / len(entidades), 3),
    }
