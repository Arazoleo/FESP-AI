"""
Validação neuro-simbólica para o FESP-AI.

Implementa o loop Neural ↔ Simbólico em três camadas:

1. InferenceEngine (Simbólico puro)
   Regras formais de primeira ordem sobre o Knowledge Graph:
   - prereq_transitivity:  ∀x,y,z: prereq(x,y) ∧ prereq(y,z) → prereq_trans(x,z)
   - unlock_condition:     ∀x,C:  (∀p∈prereqs(x): p∈C) → desbloqueado(x,C)
   - critical_discipline:  ∀x:   |dependentes(x)| ≥ θ → crítica(x)
   - co_prerequisite:      ∀x,y,z: prereq(x,z) ∧ prereq(y,z) → co_prereq(x,y)
   - minimal_path:         caminho mínimo no DAG de pré-requisitos (BFS topológico)

   `PyReasonEngine` (em src/pyreason_engine.py) estende `InferenceEngine`
   substituindo `prereq_transitivity` por um reasoner Datalog anotado
   (PyReason, Aditya et al., AAAI 2023) que propaga bounds [l, u] ⊆ [0,1]
   das arestas para as conclusões inferidas. Demais regras seguem em Python.

   A seleção do motor é controlada pela env var FESPAI_REASONER:
   - "pyreason" (padrão) → tenta PyReason, fallback silencioso para Python
   - "python"            → força InferenceEngine clássico

2. SymbolicValidator (Simbólico ↔ Neural)
   - Enriquecimento: fatos verificados + fatos inferidos → contexto do LLM
   - Validação:     claims do LLM verificados contra o KG
   - Correção:      reescrita da resposta quando violações são detectadas

3. ValidationResult
   Rastreia fatos verificados, violações, correções aplicadas, regras de inferência
   usadas e propagação de incerteza de arestas de baixa confiança.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .knowledge_graph import KnowledgeGraph


# ── Conjuntos de intents por comportamento ────────────────────────────────────

ENRICH_DISCIPLINE_INTENTS: frozenset = frozenset({
    "ementa_disciplina",
    "prerequisite_chain",
    "dependents",
    "discipline_docentes",
    "unlocked_disciplines",
    "trajectory_planning",
})

ENRICH_DOCENTE_INTENTS: frozenset = frozenset({
    "docente_info",
    "docente_areas",
    "docente_disciplines",
    "docentes_by_area",
})

VALIDATE_PREREQ_INTENTS: frozenset = frozenset({"prerequisite_chain"})
VALIDATE_DOCENTE_INTENTS: frozenset = frozenset({"discipline_docentes", "docente_disciplines"})

# Limiar de confiança: abaixo disso a resposta usa linguagem de incerteza
CONF_HIGH = 1.0
CONF_MEDIUM = 0.8
CONF_LOW = 0.6


# ── ValidationResult ──────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    is_valid: bool = True
    violations: List[str] = field(default_factory=list)
    verified_facts: List[str] = field(default_factory=list)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    # B1 — Reescrita corretiva
    was_corrected: bool = False
    correction_details: List[str] = field(default_factory=list)
    # B4 — Rastreamento de regras de inferência aplicadas
    inference_rules_applied: List[str] = field(default_factory=list)

    def to_annotation(self) -> str:
        """Gera anotação de rodapé para a resposta do LLM."""
        if not self.violations and not self.verified_facts and not self.was_corrected:
            return ""
        lines = ["\n\n---"]
        if self.was_corrected:
            lines.append(
                "*⚠️ Resposta corrigida pelo Knowledge Graph* "
                + ("· Regras: " + ", ".join(self.inference_rules_applied)
                   if self.inference_rules_applied else "")
            )
        elif self.verified_facts:
            lines.append("*Verificado no Knowledge Graph:* " + " · ".join(self.verified_facts[:3]))
        # B2 — Propagação de incerteza
        low_conf = {k: v for k, v in self.confidence_scores.items() if v < CONF_HIGH}
        if low_conf:
            conf_strs = [
                f"{k}: {v:.0%}" + (" *(provável)*" if v >= CONF_MEDIUM else " *(incerto)*")
                for k, v in sorted(low_conf.items(), key=lambda x: x[1])[:3]
            ]
            lines.append("*Confiança parcial:* " + " · ".join(conf_strs))
        if self.violations:
            lines.append("*Atenção:* " + " · ".join(self.violations[:2]))
        return "\n".join(lines)


# ── InferenceEngine (B4) ──────────────────────────────────────────────────────

class InferenceEngine:
    """
    Motor de inferência simbólica com regras formais sobre o Knowledge Graph.

    Cada método implementa uma ou mais regras de lógica de primeira ordem.
    As regras são aplicadas tanto no enriquecimento de contexto (antes do LLM)
    quanto na geração de explicações corretivas (após o LLM).
    """

    RULES: Dict[str, str] = {
        "prereq_transitivity": (
            "∀x,y,z: prereq(x,y) ∧ prereq(y,z) → prereq_trans(x,z)"
        ),
        "unlock_condition": (
            "∀x,C: (∀p ∈ prereqs_diretos(x): p ∈ C) → desbloqueado(x,C)"
        ),
        "critical_discipline": (
            "∀x: |dependentes(x)| ≥ θ → crítica(x)   [θ=3]"
        ),
        "co_prerequisite": (
            "∀x,y,z: prereq(x,z) ∧ prereq(y,z) ∧ x≠y → co_prereq(x,y)"
        ),
        "minimal_path": (
            "∀target,C: min{|path|: cursando(path) → desbloqueado(target, C∪path)}"
        ),
        # Recomendação semântico-simbólica: conteúdo sobreposto (embeddings de
        # NOME+EMENTA), fora da cadeia do DAG, respeitando a ordem do currículo
        # (termo da matriz ou, na falta, profundidade no DAG). θ calibrado
        # empiricamente (KGCompletion.REC_BEFORE_THRESHOLD).
        "recommended_before": (
            "∀a,b: sim_ementa(a,b) ≥ θ ∧ ¬ancestral(a,b) ∧ ¬ancestral(b,a) "
            "∧ ordem(a) < ordem(b) → recommended_before(a,b)"
        ),
    }

    def __init__(self, kg: "KnowledgeGraph"):
        self.kg = kg

    # ── Regra: unlock_condition ───────────────────────────────────────────────

    def can_take(self, discipline: str, completed: List[str]) -> bool:
        """Verifica se todos os pré-requisitos diretos de `discipline` estão em `completed`."""
        prereqs = self.kg.get_prerequisite_chain(discipline, max_depth=1)
        if not prereqs:
            return True
        completed_norm = {self.kg._normalize_text(c) for c in completed}
        return all(self.kg._normalize_text(p) in completed_norm for p in prereqs)

    def derive_unlocked(self, completed: List[str]) -> List[str]:
        """Aplica unlock_condition a todas as disciplinas do KG."""
        return self.kg.get_unlocked_disciplines(completed)

    # ── Regra: minimal_path ───────────────────────────────────────────────────

    def plan_minimal_path(
        self,
        target: str,
        completed: List[str],
    ) -> Optional[List[List[str]]]:
        """
        Retorna o caminho mínimo de disciplinas a cursar para atingir `target`.

        Algoritmo: BFS topológico no DAG de pré-requisitos.
        Cada fase contém disciplinas que podem ser cursadas em paralelo.

        Returns None se o alvo não existe no KG ou há inconsistência no grafo.
        """
        target_id = self.kg._find_node(target, "disciplina")
        if not target_id:
            return None

        if self.can_take(target, completed):
            return [[target]]

        # Todos os ancestrais de target não ainda cursados
        all_ancestors = set(self.kg.get_all_ancestors(target))
        completed_norm = {self.kg._normalize_text(c) for c in completed}
        missing = {
            a for a in all_ancestors
            if self.kg._normalize_text(a) not in completed_norm
        }
        missing.add(target)

        # BFS topológico: a cada iteração, pegar disciplinas prontas para cursar
        resolved_norm = set(completed_norm)
        remaining = set(missing)
        phases: List[List[str]] = []

        for _ in range(30):  # limite de segurança
            if not remaining:
                break
            ready = [
                disc for disc in sorted(remaining)
                if all(
                    self.kg._normalize_text(p) in resolved_norm
                    for p in self.kg.get_prerequisite_chain(disc, max_depth=1)
                )
            ]
            if not ready:
                break  # ciclo ou inconsistência
            phases.append(ready)
            for disc in ready:
                resolved_norm.add(self.kg._normalize_text(disc))
                remaining.discard(disc)

        return phases if phases else None

    def path_confidence(
        self, phases: List[List[str]]
    ) -> Tuple[Dict[str, float], float]:
        """
        B2 — Propagação de incerteza no caminho mínimo.

        Para cada disciplina do caminho, o menor `confidence` das arestas de
        pré-requisito que a habilitam; e o bound inferior do caminho inteiro
        (mínimo global — semântica de bounds [low, 1.0] do PyReason).

        Returns:
            (confianca_por_disciplina, bound_inferior_do_caminho)
            Disciplinas com todas as arestas em confiança 1.0 ficam fora do dict.
        """
        per_disc: Dict[str, float] = {}
        overall = 1.0
        for phase in phases or []:
            for disc in phase:
                worst = 1.0
                for p in self.kg.get_prerequisite_chain(disc, max_depth=1):
                    conf = self.kg.get_prerequisite_confidence(p, disc)
                    if 0.0 < conf < worst:
                        worst = conf
                if worst < 1.0:
                    per_disc[disc] = worst
                    overall = min(overall, worst)
        return per_disc, overall

    # ── Regra: critical_discipline ────────────────────────────────────────────

    def critical_disciplines(
        self, min_dependents: int = 3
    ) -> List[Tuple[str, int]]:
        """
        Disciplinas críticas: são pré-requisito de pelo menos `min_dependents` outras.
        Útil para recomendar priorização no planejamento de curso.
        """
        result = []
        for _, data in self.kg.graph.nodes(data=True):
            if data.get("tipo") != "disciplina":
                continue
            nome = data.get("nome", "")
            if not nome:
                continue
            n_dependentes = len(self.kg.get_dependent_disciplines(nome))
            if n_dependentes >= min_dependents:
                result.append((nome, n_dependentes))
        return sorted(result, key=lambda x: -x[1])

    # ── Regra: recommended_before ─────────────────────────────────────────────

    def get_recommended_before(self, discipline: str, n: int = 3) -> List[Tuple[str, float]]:
        """
        Disciplinas recomendadas ANTES de `discipline` (regra recommended_before):
        NÃO são pré-requisitos nem estão na mesma cadeia do DAG, mas o conteúdo
        (ementa) se sobrepõe e elas vêm antes na ordem do currículo.

        Implementação no KGCompletion (que detém os embeddings); sem embeddings
        injetados retorna [] (graceful).
        """
        try:
            return self.kg.kgc.get_recommended_before(discipline, n=n)
        except Exception:
            return []

    # ── Regra: co_prerequisite ────────────────────────────────────────────────

    def find_co_prerequisites(self, discipline: str) -> List[str]:
        """
        Retorna disciplinas que são co-pré-requisitos de `discipline`:
        outras disciplinas exigidas pelos mesmos dependentes de `discipline`.
        """
        dependents = self.kg.get_dependent_disciplines(discipline)
        co_prereqs: Set[str] = set()
        disc_norm = self.kg._normalize_text(discipline)
        for dep in dependents:
            for p in self.kg.get_prerequisite_chain(dep, max_depth=1):
                if self.kg._normalize_text(p) != disc_norm:
                    co_prereqs.add(p)
        return sorted(co_prereqs)

    # ── Derivação de fatos para contexto do LLM ───────────────────────────────

    def derive_facts_for_context(self, intent: str, term: str) -> str:
        """
        Aplica as regras relevantes e retorna um bloco de fatos inferidos
        para enriquecer o contexto enviado ao LLM.
        """
        if not term or term in ("", "unknown"):
            return ""
        if intent == "prerequisite_chain":
            return self._infer_prereq_context(term)
        if intent == "unlocked_disciplines":
            return self._infer_unlock_context(term)
        if intent == "trajectory_planning":
            return self._infer_trajectory_context(term)
        return ""

    def _infer_prereq_context(self, disciplina: str) -> str:
        lines: List[str] = []
        critical = dict(self.critical_disciplines(min_dependents=3))
        prereqs = self.kg.get_prerequisite_chain(disciplina, max_depth=1)

        # Pré-requisitos críticos (têm muitos dependentes)
        critical_prereqs = [(p, critical[p]) for p in prereqs if p in critical]
        if critical_prereqs:
            strs = [f"{p} ({n} dependentes)" for p, n in critical_prereqs]
            lines.append(
                f"[Regra critical_discipline] Pré-requisitos críticos: {', '.join(strs)}"
            )

        # Co-pré-requisitos
        co = self.find_co_prerequisites(disciplina)
        if co:
            lines.append(
                f"[Regra co_prerequisite] Disciplinas frequentemente cursadas junto: "
                f"{', '.join(co[:4])}"
            )

        if not lines:
            return ""
        return "[FATOS INFERIDOS — InferenceEngine]\n" + "\n".join(f"  • {l}" for l in lines)

    def _infer_unlock_context(self, term: str) -> str:
        completed = [d.strip() for d in term.split(",") if d.strip()]
        if not completed:
            return ""
        unlocked = self.derive_unlocked(completed)
        if not unlocked:
            return ""
        return (
            f"[Regra unlock_condition] Com {len(completed)} disciplina(s) cursada(s), "
            f"{len(unlocked)} disciplina(s) estão totalmente desbloqueadas."
        )

    def _infer_trajectory_context(self, term: str) -> str:
        """Para trajectory_planning: term pode ser 'target' ou 'c1,c2:target'."""
        completed, target = _parse_trajectory_term(term)
        if not target:
            return ""
        phases = self.plan_minimal_path(target, completed)
        if not phases:
            return ""
        total = sum(len(p) for p in phases)
        linha = (
            f"[Regra minimal_path] Caminho mínimo para {target}: "
            f"{len(phases)} fase(s), {total} disciplina(s)."
        )
        # B2: propagar incerteza dos elos do caminho
        _, bound = self.path_confidence(phases)
        if bound < CONF_HIGH:
            linha += (
                f"\n[Regra minimal_path — incerteza] Bound inferior de confiança "
                f"do caminho: {bound:.0%} (há elos de pré-requisito com confiança parcial)."
            )
        return linha


# ── SymbolicValidator ─────────────────────────────────────────────────────────

class SymbolicValidator:
    def __init__(self, kg: "KnowledgeGraph", llm=None, engine: Optional[InferenceEngine] = None):
        self.kg = kg
        self.llm = llm
        self._normalize = kg._normalize_text
        self._known_disciplines: Optional[Set[str]] = None
        self._known_docentes: Optional[Set[str]] = None
        # B4: motor de inferência. Default = PyReason quando disponível
        # (FESPAI_REASONER=python força fallback).
        self.engine = engine if engine is not None else _build_default_engine(kg)

    def invalidate_cache(self):
        self._known_disciplines = None
        self._known_docentes = None

    def _get_known_disciplines(self) -> Set[str]:
        if self._known_disciplines is None:
            self._known_disciplines = {
                self._normalize(data.get("nome", ""))
                for _, data in self.kg.graph.nodes(data=True)
                if data.get("tipo") == "disciplina" and data.get("nome")
            }
        return self._known_disciplines

    def _get_known_docentes(self) -> Set[str]:
        if self._known_docentes is None:
            self._known_docentes = {
                self._normalize(data.get("nome", ""))
                for _, data in self.kg.graph.nodes(data=True)
                if data.get("tipo") == "docente" and data.get("nome")
            }
        return self._known_docentes

    # ── Enriquecimento de contexto (Simbólico → Neural) ───────────────────────

    def enrich_agent_context(self, intent: str, term: str) -> str:
        """
        Combina fatos verificados do KG com fatos derivados pelo InferenceEngine.
        O bloco resultante é prefixado ao contexto enviado ao LLM.
        """
        if not term or term in ("", "unknown"):
            return ""

        # Fatos verificados (explícitos no KG)
        if intent == "unlocked_disciplines":
            kg_facts = self._build_unlocked_facts(term)
        elif intent in ENRICH_DISCIPLINE_INTENTS:
            kg_facts = self._build_discipline_facts(term)
        elif intent in ENRICH_DOCENTE_INTENTS:
            kg_facts = self._build_docente_facts(term)
        else:
            kg_facts = ""

        # B4: fatos inferidos pelas regras de inferência
        inferred_facts = self.engine.derive_facts_for_context(intent, term)

        parts = [p for p in [kg_facts, inferred_facts] if p]
        return "\n\n".join(parts)

    def _build_discipline_facts(self, disciplina: str) -> str:
        node_id = self.kg._find_node(disciplina, "disciplina")
        if not node_id:
            return ""

        lines = []

        prereqs_diretos = self.kg.get_prerequisite_chain(disciplina, max_depth=1)
        if prereqs_diretos:
            prereq_strs = []
            for p in prereqs_diretos:
                conf = self.kg.get_prerequisite_confidence(p, disciplina)
                # B2: só exibir confiança quando o atributo está presente (0 < conf < 1)
                if 0.0 < conf < CONF_HIGH:
                    prereq_strs.append(f"{p} (confiança {conf:.0%})")
                else:
                    prereq_strs.append(p)
            lines.append(f"Pré-requisitos diretos: {', '.join(prereq_strs)}")
        else:
            lines.append("Pré-requisitos diretos: nenhum")

        todos_prereqs = self.kg.get_all_ancestors(disciplina)
        indiretos = [p for p in todos_prereqs if p not in prereqs_diretos]
        if indiretos:
            lines.append(
                f"Pré-requisitos transitivos (indiretos): {', '.join(indiretos[:8])}"
            )

        docentes = self.kg.get_docentes_of_discipline(disciplina)
        if docentes:
            lines.append(f"Docentes responsáveis: {', '.join(docentes)}")

        dependentes = self.kg.get_dependent_disciplines(disciplina)
        if dependentes:
            lines.append(
                f"Desbloqueia (é pré-requisito de): {', '.join(dependentes[:5])}"
            )

        if not lines:
            return ""

        facts_block = (
            f"[FATOS VERIFICADOS NO KNOWLEDGE GRAPH — {disciplina}]\n"
            + "\n".join(f"  • {line}" for line in lines)
        )

        # KGC: enriquecimento estrutural
        try:
            kgc_block = self.kg.kgc.get_enrichment_block(disciplina, max_similar=3)
            if kgc_block:
                facts_block += "\n\n" + kgc_block
        except Exception:
            pass

        return facts_block

    def _build_docente_facts(self, docente: str) -> str:
        lines = []

        info = self.kg.get_docente_info(docente)
        if info:
            if info.get("email"):
                lines.append(f"Email: {info['email']}")
            if info.get("sala"):
                lines.append(f"Sala: {info['sala']}")

        disciplinas = self.kg.get_disciplines_of_docente(docente)
        if disciplinas:
            lines.append(f"Disciplinas lecionadas: {', '.join(disciplinas)}")

        areas = self.kg.get_areas_of_docente(docente)
        if areas:
            lines.append(f"Áreas de pesquisa: {', '.join(areas[:6])}")

        if not lines:
            return ""

        return (
            f"[FATOS VERIFICADOS NO KNOWLEDGE GRAPH — {docente}]\n"
            + "\n".join(f"  • {line}" for line in lines)
        )

    def _build_unlocked_facts(self, term: str) -> str:
        completed = [d.strip() for d in term.split(",") if d.strip()]
        if not completed:
            return ""

        unlocked = self.kg.get_unlocked_disciplines(completed)
        header = "[FATOS VERIFICADOS NO KNOWLEDGE GRAPH — Disciplinas Desbloqueadas]\n"
        header += f"  • Cursadas: {', '.join(completed)}\n"
        if unlocked:
            header += f"  • Desbloqueadas agora: {', '.join(unlocked[:10])}"
        else:
            header += "  • Nenhuma disciplina totalmente desbloqueada com estas cursadas"
        return header

    # ── Validação + Correção (Neural → Simbólico → Neural) ───────────────────

    def validate_and_correct(
        self,
        response: str,
        intent: str,
        term: str,
    ) -> Tuple[str, ValidationResult]:
        """
        B1 — Reescrita corretiva:
        Valida a resposta do LLM e, quando há violações verificáveis,
        gera uma resposta substituta baseada exclusivamente em fatos do KG.

        Returns:
            (resposta_final, validation_result)
        """
        validation = self.validate_response(response, intent, term)

        if not validation.violations:
            # Sem violações: anotar fatos verificados e propagação de incerteza
            annotation = validation.to_annotation()
            return (response + annotation if annotation else response), validation

        # Há violações: tentar reescrita corretiva
        corrected: Optional[str] = None

        if intent in VALIDATE_PREREQ_INTENTS and term:
            corrected = self._correct_prereq_response(term, validation)
        elif intent in VALIDATE_DOCENTE_INTENTS and term:
            corrected = self._correct_docente_response(term, validation)

        # B1 genérico: para os demais intents, reescrever via LLM ancorado
        # nos fatos verificados do KG (em vez de apenas anotar a violação)
        if corrected is None:
            corrected = self._correct_generic_response(response, intent, term, validation)

        if corrected:
            from .telemetry import incr
            incr(
                "b1_correcao_generica"
                if "generic_kg_rewrite" in validation.inference_rules_applied
                else "b1_correcao_dedicada"
            )
            validation.was_corrected = True
            validation.correction_details.append(
                f"intent={intent}, term={term}, violações={len(validation.violations)}"
            )
            annotation = validation.to_annotation()
            return (corrected + annotation if annotation else corrected), validation

        # Não foi possível corrigir: retornar com anotação de violação
        annotation = validation.to_annotation()
        return (response + annotation if annotation else response), validation

    def _correct_prereq_response(
        self, disciplina: str, validation: ValidationResult
    ) -> str:
        """Gera resposta corrigida para claims de pré-requisitos com violações."""
        node_id = self.kg._find_node(disciplina, "disciplina")
        if not node_id:
            return f"Não encontrei **{disciplina}** na base de dados da UNIFESP ICT."

        prereqs_diretos = self.kg.get_prerequisite_chain(disciplina, max_depth=1)
        todos_prereqs = self.kg.get_all_ancestors(disciplina)

        parts = [f"**Pré-requisitos de {disciplina}**"]

        if not prereqs_diretos:
            parts.append(
                "**Diretos:** nenhum — pode ser cursada sem pré-requisitos prévios."
            )
        else:
            diretos_strs = []
            for p in prereqs_diretos:
                conf = self.kg.get_prerequisite_confidence(p, disciplina)
                # B2: só propagar incerteza quando o atributo existe (0 < conf < 1)
                if 0.0 < conf < CONF_LOW:
                    validation.confidence_scores[p] = conf
                    diretos_strs.append(f"{p} *(possivelmente — {conf:.0%})*")
                elif 0.0 < conf < CONF_MEDIUM:
                    validation.confidence_scores[p] = conf
                    diretos_strs.append(f"{p} *(provavelmente — {conf:.0%})*")
                else:
                    diretos_strs.append(p)
            parts.append("**Diretos:** " + ", ".join(diretos_strs))

        indiretos = [p for p in todos_prereqs if p not in prereqs_diretos]
        if indiretos:
            parts.append("**Transitivos:** " + ", ".join(indiretos[:8]))

        validation.inference_rules_applied += ["prereq_transitivity", "unlock_condition"]
        return "\n\n".join(parts)

    _GENERIC_CORRECTION_PROMPT = (
        "Voce e o corretor simbolico do assistente da UNIFESP ICT.\n"
        "A resposta abaixo contem afirmacoes que CONTRADIZEM o Knowledge Graph oficial.\n\n"
        "FATOS VERIFICADOS NO KNOWLEDGE GRAPH (unica fonte de verdade):\n{facts}\n\n"
        "VIOLACOES DETECTADAS:\n{violations}\n\n"
        "RESPOSTA ORIGINAL:\n{response}\n\n"
        "Reescreva a resposta em portugues brasileiro corrigindo APENAS os trechos que "
        "violam os fatos verificados: remova ou substitua as afirmacoes erradas usando "
        "exclusivamente os fatos acima. Mantenha o restante do conteudo e o tom original. "
        "Nao adicione informacao nova, nao mencione esta correcao nem o Knowledge Graph.\n\n"
        "Resposta corrigida:"
    )

    def _correct_generic_response(
        self,
        response: str,
        intent: str,
        term: str,
        validation: ValidationResult,
    ) -> Optional[str]:
        """
        B1 genérico — reescrita corretiva para intents sem corretor dedicado.

        Usa o LLM para reescrever a resposta, ancorado exclusivamente nos fatos
        verificados do KG. Sem LLM ou sem fatos disponíveis, retorna None
        (a violação fica apenas anotada, comportamento anterior).
        """
        if not self.llm or not term:
            return None

        facts = self.enrich_agent_context(intent, term)
        if not facts and self.kg._find_node(term, "disciplina"):
            facts = self._build_discipline_facts(term)
        if not facts:
            return None

        prompt = self._GENERIC_CORRECTION_PROMPT.format(
            facts=facts,
            violations="\n".join(f"- {v}" for v in validation.violations),
            response=response,
        )
        try:
            from langchain_core.messages import HumanMessage
            ans = self.llm.invoke([HumanMessage(content=prompt)])
            text = (ans.content if hasattr(ans, "content") else str(ans)).strip()
            if text:
                validation.inference_rules_applied.append("generic_kg_rewrite")
                return text
        except Exception:
            pass
        return None

    def _correct_docente_response(
        self, disciplina: str, validation: ValidationResult
    ) -> Optional[str]:
        """Gera resposta corrigida para claims de docentes com violações."""
        docentes = self.kg.get_docentes_of_discipline(disciplina)
        if not docentes:
            return None  # Sem dados para corrigir

        lines = [f"**Docentes de {disciplina}** (verificados no Knowledge Graph):"]
        for d in docentes:
            lines.append(f"- {d}")

        validation.inference_rules_applied.append("docente_verification")
        return "\n".join(lines)

    # ── NSAI-1: validação de claims via LLM (LLM propõe, KG julga) ───────────

    _CLAIM_EXTRACT_PROMPT = (
        "Extraia da resposta abaixo os fatos verificaveis sobre disciplinas da "
        "UNIFESP ICT, como JSON. Tipos aceitos:\n"
        '- "codigo": {{"tipo": "codigo", "entidade": "<disciplina>", "valor": "<codigo>"}}\n'
        '- "docente": {{"tipo": "docente", "entidade": "<disciplina>", "valor": "<nome do docente>"}}\n'
        '- "prereq": {{"tipo": "prereq", "entidade": "<disciplina>", "valor": "<pre-requisito>"}}\n'
        'Formato de saida: {{"claims": [...]}}. Liste APENAS o que esta afirmado '
        "explicitamente na resposta. Sem explicacoes, apenas o JSON.\n\n"
        "RESPOSTA:\n{response}\n\nJSON:"
    )

    def validate_claims_llm(self, response: str, result: ValidationResult) -> None:
        """
        Extração de claims via LLM + verificação simbólica no KG.

        Cobre o que os validadores dedicados não veem (códigos, docentes e
        pré-requisitos citados em qualquer intent). Gate barato: só roda quando
        a resposta contém dígitos (material verificável) e há LLM disponível.
        """
        if not self.llm or not re.search(r"\d", response):
            return
        import json as _json
        try:
            from langchain_core.messages import HumanMessage
            ans = self.llm.invoke([HumanMessage(
                content=self._CLAIM_EXTRACT_PROMPT.format(response=response[:3000])
            )])
            text = ans.content if hasattr(ans, "content") else str(ans)
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                return
            claims = _json.loads(m.group()).get("claims", [])[:12]
        except Exception:
            return
        if not claims:
            return
        from .telemetry import incr
        incr("claims_extraidos", len(claims))
        for c in claims:
            try:
                viol = self._check_claim(
                    str(c.get("tipo", "")), str(c.get("entidade", "")), str(c.get("valor", ""))
                )
            except Exception:
                viol = None
            if viol:
                result.violations.append(viol)
                result.is_valid = False
                incr("claims_violacoes")
        result.inference_rules_applied.append("llm_claim_verification")

    def _check_claim(self, tipo: str, entidade: str, valor: str) -> Optional[str]:
        """Verifica um claim contra o KG. Retorna a violação ou None (ok/não verificável)."""
        if not entidade or not valor:
            return None
        if tipo == "codigo":
            node = self.kg._find_node(entidade, "disciplina")
            if node:
                real = str(self.kg.graph.nodes[node].get("codigo", "")).strip()
                dito = re.sub(r"\D", "", valor)
                if real and dito and dito != re.sub(r"\D", "", real):
                    return (
                        f"Código de {entidade} incorreto: resposta diz '{valor}', "
                        f"KG registra '{real}'"
                    )
        elif tipo == "docente":
            docentes = {self._normalize(d) for d in self.kg.get_docentes_of_discipline(entidade)}
            v = self._normalize(valor)
            if docentes and v and not any(v in d or d in v for d in docentes):
                return f"Docente '{valor}' não consta em {entidade} no KG"
        elif tipo == "prereq":
            prereqs = {self._normalize(p) for p in self.kg.get_all_ancestors(entidade)}
            v = self._normalize(valor)
            if prereqs and v and not any(v in p or p in v for p in prereqs):
                return f"'{valor}' não é pré-requisito (nem transitivo) de {entidade} no KG"
        return None

    # ── Validação pura (backward compat) ─────────────────────────────────────

    def validate_response(self, response: str, intent: str, term: str) -> ValidationResult:
        if intent in VALIDATE_PREREQ_INTENTS and term:
            result = self._validate_prereq_claims(response, term)
        elif intent in VALIDATE_DOCENTE_INTENTS and term:
            result = self._validate_docente_claims(response, term)
        else:
            result = self._validate_generic(response)
            # NSAI-1: verificação de claims no nível de fatos (desligável via env)
            if os.environ.get("FESPAI_CLAIM_CHECK", "1") != "0":
                self.validate_claims_llm(response, result)

        if term and not result.verified_facts and not result.violations:
            node_id = (
                self.kg._find_node(term, "disciplina")
                or self.kg._find_docente_id(term)
            )
            if not node_id:
                result.verified_facts.append(
                    f"'{term}' não encontrado no KG — resposta sem verificação simbólica"
                )

        return result

    def _validate_prereq_claims(self, response: str, disciplina: str) -> ValidationResult:
        result = ValidationResult()

        real_prereqs_raw = self.kg.get_prerequisite_chain(disciplina, max_depth=1)
        real_prereqs_norm = {self._normalize(p) for p in real_prereqs_raw}

        if real_prereqs_raw:
            for p in real_prereqs_raw:
                conf = self.kg.get_prerequisite_confidence(p, disciplina)
                result.confidence_scores[p] = conf
            result.verified_facts.append(
                f"Pré-requisitos de {disciplina}: {', '.join(real_prereqs_raw)}"
            )
        else:
            node_id = self.kg._find_node(disciplina, "disciplina")
            if node_id:
                result.verified_facts.append(
                    f"{disciplina}: sem pré-requisitos diretos no KG"
                )

        claim_patterns = [
            r"([A-ZÀ-Úa-zà-ú][A-Za-zÀ-Úà-ú\s\-I]+?)\s+é\s+pré[\-\s]?requisito",
            r"requer\s+([A-ZÀ-Ú][A-Za-zÀ-Úà-ú\s]+?)(?:\s+e\s+|\s*[,.\n]|$)",
            r"antes\s+(?:de\s+)?(?:cursar|fazer)\s+([A-ZÀ-Ú][A-Za-zÀ-Úà-ú\s]+?)(?:\s*[,.\n]|$)",
        ]

        known = self._get_known_disciplines()
        claimed_names: Set[Tuple[str, str]] = set()
        for pattern in claim_patterns:
            for m in re.finditer(pattern, response, re.IGNORECASE):
                name_raw = m.group(1).strip()
                name_norm = self._normalize(name_raw)
                if name_norm and len(name_norm) > 3:
                    claimed_names.add((name_raw, name_norm))

        for name_raw, name_norm in claimed_names:
            if name_norm in known:
                continue
            partial_match = any(
                (name_norm in k or k in name_norm) for k in known if len(k) > 5
            )
            if not partial_match and self.llm:
                try:
                    from langchain_core.messages import HumanMessage
                    prompt = (
                        f"A disciplina '{name_raw}' existe na grade curricular da UNIFESP ICT? "
                        "Responda apenas 'sim' ou 'não'."
                    )
                    ans = self.llm.invoke([HumanMessage(content=prompt)])
                    ans_text = (
                        ans.content if hasattr(ans, "content") else str(ans)
                    ).lower()
                    if "sim" in ans_text:
                        partial_match = True
                except Exception:
                    pass
            if not partial_match:
                result.violations.append(f"Disciplina não encontrada no KG: '{name_raw}'")
                result.is_valid = False

        return result

    def _validate_docente_claims(self, response: str, disciplina: str) -> ValidationResult:
        result = ValidationResult()

        real_docentes = self.kg.get_docentes_of_discipline(disciplina)
        if real_docentes:
            result.verified_facts.append(
                f"Docentes de {disciplina} no KG: {', '.join(real_docentes)}"
            )

        resp_norm = self._normalize(response)
        confirmed = [d for d in real_docentes if self._normalize(d) in resp_norm]
        unconfirmed = [d for d in real_docentes if self._normalize(d) not in resp_norm]

        if confirmed:
            result.verified_facts.append(f"Confirmados na resposta: {', '.join(confirmed)}")
        if unconfirmed:
            result.violations.append(
                f"Docente(s) do KG ausentes na resposta: {', '.join(unconfirmed[:3])}"
            )
            result.is_valid = False

        return result

    # Padrões conservadores de menção explícita a disciplina.
    # Exigem nome próprio (inicial maiúscula) após "disciplina/matéria" para
    # não gerar falsos positivos com frases genéricas ("disciplina de graduação").
    _DISC_MENTION_PATTERNS = [
        r"disciplina\s+(?:de\s+)?[\"“']?([A-ZÀ-Ú][A-Za-zÀ-Úà-ú0-9\s\-]{3,50}?)[\"”']?(?=\s*[,.;:\n(]|$)",
        r"mat[ée]ria\s+(?:de\s+)?[\"“']?([A-ZÀ-Ú][A-Za-zÀ-Úà-ú0-9\s\-]{3,50}?)[\"”']?(?=\s*[,.;:\n(]|$)",
    ]

    def _validate_generic(self, response: str) -> ValidationResult:
        result = ValidationResult()
        resp_norm = self._normalize(response)
        known = self._get_known_disciplines()

        confirmed_disc = sum(
            1 for d in known if len(d) > 6 and d in resp_norm
        )
        confirmed_doc = sum(
            1 for d in self._get_known_docentes() if len(d) > 6 and d in resp_norm
        )

        if confirmed_disc + confirmed_doc > 0:
            result.verified_facts.append(
                f"{confirmed_disc} disciplina(s) e {confirmed_doc} docente(s) verificados no KG"
            )

        # B1: disciplinas citadas explicitamente que não existem no KG → violação
        # (habilita a reescrita corretiva genérica em validate_and_correct)
        for pattern in self._DISC_MENTION_PATTERNS:
            for m in re.finditer(pattern, response):
                name_raw = m.group(1).strip()
                name_norm = self._normalize(name_raw)
                if not name_norm or len(name_norm) <= 3:
                    continue
                if name_norm in known:
                    continue
                if any((name_norm in k or k in name_norm) for k in known if len(k) > 5):
                    continue
                result.violations.append(
                    f"Disciplina não encontrada no KG: '{name_raw}'"
                )
                result.is_valid = False

        return result

    def get_symbolic_facts_summary(self, disciplina: str) -> Dict:
        """Retorna um dicionário com todos os fatos simbólicos sobre uma disciplina."""
        node_id = self.kg._find_node(disciplina, "disciplina")
        if not node_id:
            return {"found": False, "disciplina": disciplina}

        node_data = self.kg.graph.nodes[node_id]
        prereqs_diretos = self.kg.get_prerequisite_chain(disciplina, max_depth=1)
        todos_prereqs = self.kg.get_all_ancestors(disciplina)

        return {
            "found": True,
            "nome": node_data.get("nome", disciplina),
            "codigo": node_data.get("codigo", ""),
            "sigla": node_data.get("sigla", ""),
            "prerequisitos_diretos": prereqs_diretos,
            "prerequisitos_transitivos": todos_prereqs,
            "prerequisitos_confidence": {
                p: self.kg.get_prerequisite_confidence(p, disciplina)
                for p in prereqs_diretos
            },
            "docentes": self.kg.get_docentes_of_discipline(disciplina),
            "dependentes": self.kg.get_dependent_disciplines(disciplina),
            "co_prerequisitos": self.engine.find_co_prerequisites(disciplina),
            "caminho_minimo_exemplo": self.engine.plan_minimal_path(disciplina, []),
        }


# ── Seleção de engine ─────────────────────────────────────────────────────────

# Cache de engines por KG. O PyReason mantém state global (pr.reset/load_graph),
# então múltiplas instâncias para o mesmo KG se atropelariam. Além disso, o
# JIT do numba paga ~20s na primeira inferência — não queremos pagar isso N
# vezes (uma por agente). O cache garante one-engine-per-KG.
_engine_cache: Dict[int, "InferenceEngine"] = {}


def _build_default_engine(kg: "KnowledgeGraph") -> "InferenceEngine":
    """Escolhe o motor de inferência conforme FESPAI_REASONER.

    - `pyreason` (padrão): usa PyReason quando disponível; fallback silencioso
      para o motor Python se a importação falhar.
    - `python`: força o motor Python original (`InferenceEngine`).

    Engines são cacheados por identidade do KG (um engine por instância de
    KnowledgeGraph) para evitar reinicialização redundante do reasoner.
    """
    key = id(kg)
    cached = _engine_cache.get(key)
    if cached is not None:
        return cached

    choice = os.environ.get("FESPAI_REASONER", "pyreason").lower()
    if choice == "python":
        engine: "InferenceEngine" = InferenceEngine(kg)
    else:
        try:
            from .pyreason_engine import PyReasonEngine
            engine = PyReasonEngine(kg)
        except Exception:
            engine = InferenceEngine(kg)

    _engine_cache[key] = engine
    return engine


def clear_engine_cache() -> None:
    """Limpa o cache de engines. Chamar após reconstruir o KG."""
    _engine_cache.clear()


# ── Utilitários ───────────────────────────────────────────────────────────────

def _parse_trajectory_term(term: str) -> Tuple[List[str], str]:
    """
    Parseia o termo de trajectory_planning.
    Formato: 'c1,c2,...:target'  ou apenas 'target'.
    """
    if ":" in term:
        completed_str, target = term.rsplit(":", 1)
        completed = [c.strip() for c in completed_str.split(",") if c.strip()]
        return completed, target.strip()
    return [], term.strip()
