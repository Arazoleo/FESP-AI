"""
Auditoria de integralização e pré-verificação de matrícula.

- auditar_progresso: cruza as disciplinas cursadas com a matriz do curso no KG
  e devolve obrigatórias faltantes, disponíveis agora, bloqueadas (com o
  pré-requisito que falta) e o mínimo de semestres restantes pelo caminho
  crítico do DAG de pré-requisitos.
- verificar_matricula: aplica os motivos de indeferimento verificáveis
  (pré-requisito não cumprido, UC já cursada) e explica a prioridade do
  art. 112 da Prograd.

Entradas em linguagem natural são aterradas no KG; o que não resolve é
reportado ao aluno, nunca inventado.
"""

import re
import unicodedata
from typing import Dict, List, Optional, Tuple


def _norm(text: str) -> str:
    t = "".join(
        c for c in unicodedata.normalize("NFD", str(text or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", t).strip()


def _matriz_do_curso(kg, curso: str) -> Optional[Dict[str, Dict]]:
    termos = kg.get_todos_termos_do_curso(curso)
    if not termos:
        return None
    info = {}
    for termo_num, discs in termos.items():
        for d in discs:
            nome = d.get("nome")
            if not nome:
                continue
            key = kg._normalize_text(nome)
            try:
                t = int(re.match(r"(\d+)", str(termo_num)).group(1))
            except (AttributeError, ValueError):
                t = 99
            if key not in info or t < info[key]["termo"]:
                info[key] = {"nome": nome, "termo": t}
    return info


def auditar_progresso(kg, curso: str, cursadas: List[str]) -> Optional[Dict]:
    info = _matriz_do_curso(kg, curso)
    if not info:
        return None
    norm = kg._normalize_text

    cursadas_norm = set()
    desconhecidas = []
    for c in cursadas:
        if not c or not c.strip():
            continue
        k = norm(c)
        if k in info:
            cursadas_norm.add(k)
            continue
        node = kg._find_node(c, "disciplina")
        if node:
            k2 = norm(kg.graph.nodes[node].get("nome", c))
            if k2 in info:
                cursadas_norm.add(k2)
                continue
        desconhecidas.append(c)

    pendentes = {k: v for k, v in info.items() if k not in cursadas_norm}

    prereqs = {}
    for k, v in pendentes.items():
        directs = kg.get_direct_prerequisites(v["nome"]) or []
        prereqs[k] = {norm(p) for p in directs if p and norm(p) in info}

    disponiveis, bloqueadas = [], []
    for k, v in sorted(pendentes.items(), key=lambda kv: (kv[1]["termo"], kv[1]["nome"])):
        faltando = [
            info[p]["nome"] for p in prereqs[k]
            if p not in cursadas_norm
        ]
        if faltando:
            bloqueadas.append({**v, "faltando": sorted(faltando)})
        else:
            base_pendente = []
            try:
                for b in kg.get_base_recomendada(v["nome"]):
                    if norm(b["nome"]) not in cursadas_norm:
                        base_pendente.append(b["nome"])
            except Exception:
                pass
            disponiveis.append({**v, "base_pendente": base_pendente[:2]})

    interdisciplinares_cursadas = []
    for c in cursadas:
        node = kg._find_node(c, "disciplina")
        if node and kg.graph.nodes[node].get("interdisciplinar"):
            nome_i = kg.graph.nodes[node].get("nome", c)
            if nome_i not in interdisciplinares_cursadas:
                interdisciplinares_cursadas.append(nome_i)

    nivel: Dict[str, int] = {}

    def _nivel(k: str, trilha=frozenset()) -> int:
        if k in nivel:
            return nivel[k]
        if k in trilha:
            return 1
        pend_prereqs = [p for p in prereqs.get(k, set()) if p in pendentes]
        n = 1 + max((_nivel(p, trilha | {k}) for p in pend_prereqs), default=0)
        nivel[k] = n
        return n

    semestres_min = max((_nivel(k) for k in pendentes), default=0)

    return {
        "curso": curso,
        "total_matriz": len(info),
        "cursadas": sorted(info[k]["nome"] for k in cursadas_norm),
        "desconhecidas": desconhecidas,
        "pendentes": len(pendentes),
        "disponiveis": disponiveis,
        "bloqueadas": bloqueadas,
        "semestres_minimos": semestres_min,
        "interdisciplinares_cursadas": interdisciplinares_cursadas,
    }


def formatar_progresso(r: Dict) -> str:
    linhas = [
        f"**Auditoria de progresso no {r['curso'].upper()}**",
        "",
        f"- Obrigatórias da matriz: **{r['total_matriz']}**",
        f"- Reconhecidas como cursadas: **{len(r['cursadas'])}**",
        f"- Ainda pendentes: **{r['pendentes']}**",
        f"- Mínimo de semestres restantes (pelo caminho crítico de pré-requisitos): **{r['semestres_minimos']}**",
    ]
    if r["disponiveis"]:
        linhas.append("")
        linhas.append("**Você já pode cursar** (pré-requisitos cumpridos):")
        for d in r["disponiveis"][:12]:
            extra = ""
            if d.get("base_pendente"):
                extra = f" - base recomendada pendente: {', '.join(d['base_pendente'])}"
            linhas.append(f"- {d['nome']} (termo {d['termo']}){extra}")
        if len(r["disponiveis"]) > 12:
            linhas.append(f"- ... e mais {len(r['disponiveis']) - 12}")
    if r["bloqueadas"]:
        linhas.append("")
        linhas.append("**Bloqueadas por pré-requisito:**")
        for d in r["bloqueadas"][:10]:
            linhas.append(
                f"- {d['nome']} (termo {d['termo']}) ← falta {', '.join(d['faltando'])}"
            )
        if len(r["bloqueadas"]) > 10:
            linhas.append(f"- ... e mais {len(r['bloqueadas']) - 10}")
    if r["desconhecidas"]:
        linhas.append("")
        linhas.append(
            "Não reconheci na matriz (confira o nome): "
            + ", ".join(r["desconhecidas"])
        )
    linhas.append("")
    inter = r.get("interdisciplinares_cursadas") or []
    curso_norm = _norm(r["curso"])
    if "bct" in curso_norm or "ciencia e tecnologia" in curso_norm:
        status_inter = (
            f"**{len(inter)} de 4** UCs Eletivas Interdisciplinares cursadas"
            + (f" ({', '.join(inter)})" if inter else "")
        )
        linhas.append(f"- Interdisciplinares (requisito do PPC 2023): {status_inter}")
        linhas.append("")
    linhas.append(
        "Além das obrigatórias, a integralização exige as eletivas e horas de "
        "extensão da matriz, as 312h de Atividades Complementares e, no BCT, "
        "4 UCs Eletivas Interdisciplinares."
    )
    linhas.append("")
    linhas.append(
        "*Regras aplicadas: `prereq_transitivity` e `unlock_condition` sobre o "
        "Knowledge Graph; o mínimo de semestres é o caminho crítico do DAG de "
        "pré-requisitos. Confirme sempre com o Histórico Escolar oficial.*"
    )
    return "\n".join(linhas)


def verificar_matricula(kg, desejadas: List[str], cursadas: List[str]) -> Dict:
    norm = kg._normalize_text
    cursadas_norm = set()
    for c in cursadas:
        node = kg._find_node(c, "disciplina")
        if node:
            cursadas_norm.add(norm(kg.graph.nodes[node].get("nome", c)))
        else:
            cursadas_norm.add(norm(c))

    pareceres = []
    for d in desejadas:
        node = kg._find_node(d, "disciplina")
        if not node:
            pareceres.append({
                "disciplina": d,
                "status": "desconhecida",
                "motivos": ["não encontrei essa UC no sistema"],
                "base_pendente": [],
            })
            continue
        nome = kg.graph.nodes[node].get("nome", d)
        motivos = []
        if norm(nome) in cursadas_norm:
            motivos.append("UC já cursada (motivo de indeferimento)")
        faltando = [
            p for p in (kg.get_direct_prerequisites(nome) or [])
            if norm(p) not in cursadas_norm
        ]
        if faltando:
            motivos.append(
                "falta pré-requisito: " + ", ".join(sorted(faltando))
                + " (motivo de indeferimento)"
            )
        base_pendente = []
        try:
            for b in kg.get_base_recomendada(nome):
                if norm(b["nome"]) not in cursadas_norm:
                    base_pendente.append(
                        f"{b['nome']} ({', '.join(b['conceitos'])})"
                    )
        except Exception:
            pass
        pareceres.append({
            "disciplina": nome,
            "status": "risco" if motivos else "ok",
            "motivos": motivos,
            "base_pendente": base_pendente[:3],
        })
    return {"pareceres": pareceres}


def formatar_matricula(r: Dict) -> str:
    linhas = ["**Pré-verificação da sua inscrição em UCs**", ""]
    for p in r["pareceres"]:
        if p["status"] == "ok":
            linhas.append(
                f"- **{p['disciplina']}**: ✓ sem impedimento nos critérios que "
                "consigo verificar (pré-requisitos e UC repetida)"
            )
        else:
            linhas.append(f"- **{p['disciplina']}**: ⚠ {'; '.join(p['motivos'])}")
        if p.get("base_pendente"):
            linhas.append(
                f"  - base recomendada que você ainda não cursou: "
                f"{'; '.join(p['base_pendente'])} - não impede o deferimento, "
                "mas a disciplina pressupõe esses conceitos (regra `base_recomendada`)"
            )
    linhas.append("")
    linhas.append(
        "O que não consigo verificar por aqui: falta de vagas, choque de "
        "horário (duas UCs no mesmo dia e horário) e matrícula em "
        "curso/termo/turno diferente do seu."
    )
    linhas.append("")
    linhas.append(
        "Se houver disputa por vagas, o art. 112 do Regimento da Prograd "
        "prioriza nesta ordem: seguir o currículo padrão; estar mais próximo "
        "de integralizar; não ter reprovação por frequência na UC; maior CR; "
        "cursos do mesmo campus; cursos de outros campi. Rematrícula concedida "
        "fora do prazo perde prioridade."
    )
    linhas.append("")
    linhas.append(
        "*Regras aplicadas: `unlock_condition` (pré-requisitos no Knowledge "
        "Graph) e os motivos de indeferimento do Regimento Interno da Prograd "
        "(2014).*"
    )
    return "\n".join(linhas)


_CURSADAS_RE = re.compile(
    r"(?:cursei|conclui|concluí|terminei|fiz|ja\s+cursei|ja\s+fiz|tendo\s+cursado|ja\s+tenho)\s*:?\s+(.+?)(?=\.\s|\?|$)",
    re.IGNORECASE,
)
_DESEJADAS_RE = re.compile(
    r"(?:matricular(?:-me)?\s+em|me\s+inscrever\s+em|inscricao\s+em|vagas?\s+em|pegar|pedir|cursar)\s*:?\s+(.+?)(?=\s+(?:tendo|ja\b|se\s+eu|sendo)|[.?]\s|\?$|\.$|$)",
    re.IGNORECASE,
)


def _split_lista(trecho: str) -> List[str]:
    partes = re.split(r",| e |;", trecho or "")
    return [p.strip(" .?!") for p in partes if p and p.strip(" .?!")]


def extrair_cursadas(texto: str) -> List[str]:
    m = _CURSADAS_RE.search(_strip_question(texto))
    return _split_lista(m.group(1)) if m else []


def extrair_desejadas(texto: str) -> List[str]:
    m = _DESEJADAS_RE.search(_strip_question(texto))
    return _split_lista(m.group(1)) if m else []


def _strip_question(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


_PROGRESSO_CUES_RES = [re.compile(p) for p in (
    r"\bquanto\s+(?:ainda\s+)?falta\b.*\b(?:formar|integralizar|concluir|terminar)",
    r"\b(?:o\s+que|oq)\s+(?:ainda\s+)?falta\s+(?:cursar|fazer)\b",
    r"\b(?:o\s+que|oq|quanto)\s+falta\s+(?:pra|para|p)\s+(?:eu\s+)?(?:me\s+)?(?:formar|concluir|terminar)",
    r"\bfalta\s+(?:pra|para|p)\s+(?:eu\s+)?(?:me\s+)?(?:formar|concluir|terminar)",
    r"\baudit\w*\b.*\b(?:situacao|progresso|curso)\b",
    r"\bmeu\s+progresso\b",
    r"\bconsigo\s+me\s+formar\b",
    r"\b(?:devendo|pendencias?|pendente)\b.*\b(?:diploma|formar|formatura|me\s+formar)\b",
    r"\bpegar\s+(?:o\s+|meu\s+)?diploma\b",
)]


def is_progresso_request(texto: str) -> bool:
    q = _norm(texto)
    return any(p.search(q) for p in _PROGRESSO_CUES_RES)


_MATRICULA_CUES_RES = [re.compile(p) for p in (
    r"\b(?:posso|consigo)\s+(?:me\s+)?(?:matricular|inscrever|pegar|cursar|pedir)\b",
    r"\b(?:vao|vai|sera|serao)\s+(?:deferir|deferida?s?|aceitar|indeferir)\b",
    r"\bminha\s+inscricao\s+(?:vai|sera)\b",
    r"\bvai\s+aceitar\b.*\b(?:pedido|inscricao|matricula|vagas?)\b",
)]


def is_matricula_request(texto: str) -> bool:
    q = _norm(texto)
    if not any(p.search(q) for p in _MATRICULA_CUES_RES):
        return False
    return bool(extrair_desejadas(texto))
