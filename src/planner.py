"""
Planejador de trajetória curricular do FESP-AI.

Dado um curso, as disciplinas já cursadas e um teto de créditos por semestre,
monta uma grade semestre a semestre que respeita o DAG de pré-requisitos.

100% simbólico/determinístico: o caminho é derivado do Knowledge Graph, não
gerado por LLM - portanto não há alucinação. O agente conversacional apenas
conduz a coleta de dados e narra o resultado; o plano em si vem daqui.

Algoritmo: layering topológico do DAG de pré-requisitos + bin-packing guloso
das disciplinas prontas em cada semestre, respeitando o teto de créditos.
"""

from datetime import date
from typing import Any, Dict, List, Optional

from .oferta import proximo_semestre, rotulo, paridade_do_semestre
from .progresso import _PLACEHOLDERS_MATRIZ, _norm as _norm_texto


DEFAULT_MAX_CREDITOS = 24
_DEFAULT_CREDITOS = 4
_MAX_SEMESTRES = 20


def _to_int(value: Any, default: int) -> int:
    """Converte créditos (string/None) em int, com fallback seguro."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def plan_curriculum(
    kg,
    curso: str,
    completed: Optional[List[str]] = None,
    max_creditos: int = DEFAULT_MAX_CREDITOS,
    respeitar_oferta: bool = True,
    data: Optional[date] = None,
) -> Optional[Dict[str, Any]]:
    """
    Monta a grade restante do `curso`, respeitando pré-requisitos e o teto de
    créditos por semestre.

    Args:
        kg: instância de KnowledgeGraph.
        curso: nome ou sigla do curso (ex.: "Ciência da Computação", "BCC").
        completed: disciplinas já cursadas (nomes).
        max_creditos: teto de créditos por semestre.

    Returns:
        dict com a grade planejada, nós e arestas para visualização e avisos;
        ou None se o curso não for encontrado no grafo.
    """
    completed = completed or []
    max_creditos = max(1, int(max_creditos or DEFAULT_MAX_CREDITOS))

    termos = kg.get_todos_termos_do_curso(curso)
    if not termos:
        return None

    norm = kg._normalize_text

    info_by_key: Dict[str, Dict[str, Any]] = {}
    for termo_num, discs in termos.items():
        for d in discs:
            nome = d.get("nome")
            if not nome:
                continue
            if _norm_texto(nome) in _PLACEHOLDERS_MATRIZ:
                continue
            key = norm(nome)
            creditos = _to_int(d.get("creditos"), _DEFAULT_CREDITOS)
            t = _to_int(termo_num, 99)
            if key not in info_by_key or t < info_by_key[key]["termo_sugerido"]:
                paridade = None
                if t not in (99, None):
                    paridade = "par" if t % 2 == 0 else "impar"
                info_by_key[key] = {
                    "nome": nome,
                    "creditos": creditos,
                    "termo_sugerido": t,
                    "paridade": paridade,
                }

    completed_norm = {norm(c) for c in completed if c and c.strip()}

    find_node = getattr(kg, "_find_node", None)
    eletivas_cursadas = []
    completed_desconhecidas = []
    for c in completed:
        if not c or not c.strip() or norm(c) in info_by_key:
            continue
        if find_node and find_node(c, "disciplina"):
            eletivas_cursadas.append(c)
        else:
            completed_desconhecidas.append(c)

    pending = {k: v for k, v in info_by_key.items() if k not in completed_norm}

    prereqs: Dict[str, set] = {}
    for key, info in pending.items():
        directs = kg.get_direct_prerequisites(info["nome"])
        prereqs[key] = {norm(p) for p in directs if p}

    resolved = set(completed_norm)
    semestres: List[Dict[str, Any]] = []
    remaining = dict(pending)

    def is_ready(key: str) -> bool:
        for p in prereqs[key]:
            if p in resolved:
                continue
            if p in remaining:
                return False
        return True

    sem_atual = proximo_semestre(data)
    numero = 0
    rodadas_vazias = 0
    for _ in range(_MAX_SEMESTRES):
        if not remaining:
            break

        ready = [k for k in remaining if is_ready(k)]
        if not ready:
            break

        paridade_sem = paridade_do_semestre(sem_atual)
        if respeitar_oferta:
            ofertadas = [
                k for k in ready
                if remaining[k]["paridade"] in (None, paridade_sem)
            ]
        else:
            ofertadas = ready

        if not ofertadas:
            rodadas_vazias += 1
            if rodadas_vazias > 2:
                break
            ano, s = sem_atual
            sem_atual = (ano, 2) if s == 1 else (ano + 1, 1)
            continue
        rodadas_vazias = 0

        ofertadas.sort(key=lambda k: (
            remaining[k]["termo_sugerido"],
            -remaining[k]["creditos"],
            remaining[k]["nome"],
        ))

        chosen: List[str] = []
        creditos_sem = 0
        for key in ofertadas:
            c = remaining[key]["creditos"]
            if creditos_sem + c <= max_creditos or not chosen:
                chosen.append(key)
                creditos_sem += c

        numero += 1
        disciplinas_sem = []
        for key in chosen:
            info = remaining[key]
            disciplinas_sem.append({
                "nome": info["nome"],
                "creditos": info["creditos"],
                "termo_sugerido": info["termo_sugerido"],
                "paridade": info["paridade"],
                "prereqs": [
                    info_by_key[p]["nome"]
                    for p in prereqs[key]
                    if p in info_by_key
                ],
            })

        semestres.append({
            "numero": numero,
            "rotulo": rotulo(sem_atual),
            "paridade": paridade_sem,
            "disciplinas": disciplinas_sem,
            "creditos": creditos_sem,
        })

        for key in chosen:
            resolved.add(key)
            del remaining[key]

        ano, s = sem_atual
        sem_atual = (ano, 2) if s == 1 else (ano + 1, 1)

    avisos: List[str] = []
    if completed_desconhecidas:
        avisos.append(
            "Não reconheci no currículo de "
            f"{curso}: {', '.join(completed_desconhecidas)}. "
            "Verifique o nome ou o curso."
        )
    if remaining:
        nao_planejadas = sorted(remaining[k]["nome"] for k in remaining)
        avisos.append(
            "Não consegui encaixar (possível pré-requisito faltando ou ciclo no grafo): "
            + ", ".join(nao_planejadas)
        )

    nodes, edges = _build_graph_elements(info_by_key, completed_norm, semestres, prereqs)

    return {
        "curso": curso,
        "max_creditos": max_creditos,
        "completed": [info_by_key[c]["nome"] for c in completed_norm if c in info_by_key],
        "eletivas_cursadas": len(eletivas_cursadas),
        "obrigatorias_completas": not pending,
        "semestres": semestres,
        "total_semestres": len(semestres),
        "total_disciplinas": sum(len(s["disciplinas"]) for s in semestres),
        "total_creditos": sum(s["creditos"] for s in semestres),
        "avisos": avisos,
        "nodes": nodes,
        "edges": edges,
    }


def _build_graph_elements(info_by_key, completed_norm, semestres, prereqs):
    """Gera nós (com grupo/coluna por semestre) e arestas de pré-requisito."""
    sem_of_key: Dict[str, int] = {c: 0 for c in completed_norm if c in info_by_key}
    for s in semestres:
        for d in s["disciplinas"]:
            sem_of_key[_norm_key(d["nome"], info_by_key)] = s["numero"]

    nodes = []
    for key, sem in sem_of_key.items():
        info = info_by_key[key]
        nodes.append({
            "id": info["nome"],
            "label": info["nome"],
            "semestre": sem,
            "creditos": info["creditos"],
            "cursada": sem == 0,
        })

    present = set(sem_of_key.keys())
    edges = []
    seen = set()
    for key in present:
        for p in prereqs.get(key, ()):
            if p in present:
                pair = (info_by_key[p]["nome"], info_by_key[key]["nome"])
                if pair not in seen:
                    seen.add(pair)
                    edges.append({"from": pair[0], "to": pair[1]})
    return nodes, edges


def _norm_key(nome: str, info_by_key: Dict[str, Any]) -> str:
    """Recupera a chave normalizada de um nome já presente em info_by_key."""
    for key, info in info_by_key.items():
        if info["nome"] == nome:
            return key
    return nome
