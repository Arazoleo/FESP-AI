"""
Consulta determinística da OFERTA REAL do semestre (sala, dia, horário e
professor de cada turma), a partir do JSON produzido por gerar_oferta_agenda.py
(extraído da agenda de salas do campus). Substitui a heurística de paridade do
oferta.py quando a disciplina está na oferta corrente.

Fonte carimbada na resposta (agenda de salas do campus + data de coleta).
"""

import json
import re
import unicodedata
from pathlib import Path
from typing import Optional, Tuple

_JSON = Path(__file__).resolve().parent.parent / "jsons_regimentos" / "oferta_semestre.json"

DIAS_EXT = {"Seg": "segunda", "Ter": "terça", "Qua": "quarta", "Qui": "quinta",
            "Sex": "sexta", "Sáb": "sábado", "Dom": "domingo"}
_ORDEM = {d: i for i, d in enumerate(["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"])}

_STOP = {"introducao", "a", "as", "o", "os", "de", "da", "do", "das", "dos",
         "e", "em", "para", "com", "the"}
_GATILHOS = ("sala", "salas", "onde", "local", "dia", "dias", "horario",
             "que horas", "quando", "hora", "professor", "prof", "quem",
             "ministra", "leciona", "oferta", "ofertad", "grade", "aula",
             "aulas", "acontece")

_cache = {"mtime": None, "dados": None}


def _carregar() -> Optional[dict]:
    try:
        mt = _JSON.stat().st_mtime
    except OSError:
        return None
    if _cache["mtime"] != mt:
        try:
            _cache["dados"] = json.loads(_JSON.read_text(encoding="utf-8"))
            _cache["mtime"] = mt
        except Exception:
            return None
    return _cache["dados"]


_ROMANOS = [(" viii", " 8"), (" vii", " 7"), (" vi", " 6"), (" iv", " 4"),
            (" ix", " 9"), (" iii", " 3"), (" ii", " 2"), (" v", " 5"),
            (" i", " 1"), (" x", " 10")]


def _norm(s: str) -> str:
    n = unicodedata.normalize("NFD", (s or "").lower())
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    n = " " + re.sub(r"[^a-z0-9]+", " ", n).strip() + " "
    for rom, ar in _ROMANOS:
        n = n.replace(rom + " ", ar + " ")
    return re.sub(r"\s+", " ", n).strip()


def _match_disciplina(pergunta: str):
    """Acha a disciplina da oferta mencionada na pergunta (nome, turmas) ou None.

    Casa por (a) nome completo na pergunta, (b) 2+ palavras significativas da
    disciplina presentes, ou (c) uma única palavra distintiva (>=6 letras).
    Vence quem tiver mais/maiores palavras em comum (ex.: "análise real" ganha
    de "...análise de regressão" quando a pergunta traz "real").
    """
    dados = _carregar()
    if not dados:
        return None
    qn = " " + _norm(pergunta) + " "
    qtoks = {t for t in qn.split() if len(t) > 3 and t not in _STOP}
    melhor, melhor_score = None, 0
    for nome, turmas in dados["disciplinas"].items():
        dn = _norm(nome)
        if f" {dn} " in qn:
            score = 100 + len(dn)
        else:
            dtoks = [t for t in dn.split() if len(t) > 3 and t not in _STOP]
            comuns = [t for t in dtoks if t in qtoks]
            # distintividade: >=2 palavras em comum OU uma palavra longa (>=6)
            if not comuns or not (len(comuns) >= 2 or max(map(len, comuns)) >= 6):
                continue
            score = sum(len(t) for t in comuns)
        if score > melhor_score:
            melhor, melhor_score = (nome, turmas), score
    return melhor


def detectar(pergunta: str) -> Optional[str]:
    """Retorna o nome da disciplina se a pergunta é de oferta/sala/dia/prof."""
    qn = _norm(pergunta)
    if not any(g in qn for g in _GATILHOS):
        return None
    m = _match_disciplina(pergunta)
    return m[0] if m else None


def _fmt_encontros(encontros):
    """Agrupa encontros com mesmo horário/sala: 'segunda e quarta 13:30–15:30 (sala 302)'."""
    porslot = {}
    for e in encontros:
        chave = (e["inicio"], e["fim"], e["sala"])
        porslot.setdefault(chave, []).append(e["dia"])
    partes = []
    for (ini, fim, sala), dias in porslot.items():
        dias = sorted(set(dias), key=lambda d: _ORDEM.get(d, 9))
        nomes = [DIAS_EXT.get(d, d) for d in dias]
        quando = " e ".join(nomes) if len(nomes) <= 2 else ", ".join(nomes[:-1]) + " e " + nomes[-1]
        partes.append(f"{quando} das {ini} às {fim}, na {sala}")
    return "; ".join(partes)


def responder(pergunta: str, disciplina: Optional[str] = None) -> Optional[str]:
    """Resposta determinística sobre a oferta da disciplina, ou None."""
    dados = _carregar()
    if not dados:
        return None
    if disciplina and disciplina in dados["disciplinas"]:
        nome, turmas = disciplina, dados["disciplinas"][disciplina]
    else:
        m = _match_disciplina(pergunta)
        if not m:
            return None
        nome, turmas = m
    linhas = [f"Na oferta de {dados['semestre']}, **{nome}** está assim:"]
    for t in turmas:
        prof = t.get("professor") or "professor não informado na agenda"
        quando = _fmt_encontros(t.get("encontros", []))
        linhas.append(f"- **Turma {t['turma']}** — Prof. {prof} — {quando}.")
    linhas.append(
        f"\n_Fonte: agenda de salas do campus SJC (coletado em "
        f"{dados['coletado_em']}). Vale confirmar mudanças pontuais com a "
        f"coordenação._")
    return "\n".join(linhas)


def esta_ofertada(disciplina: str) -> Optional[Tuple[str, str]]:
    """Se a disciplina consta na oferta corrente, retorna (nome, semestre)."""
    dados = _carregar()
    if not dados:
        return None
    m = _match_disciplina(disciplina)
    return (m[0], dados["semestre"]) if m else None
