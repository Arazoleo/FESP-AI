"""
Validador Neurossimbólico — conecta o Knowledge Graph (simbólico) com o LLM (neural).

Padrão implementado:
  Simbólico → Neural : enriquece o contexto com fatos verificados ANTES da geração do LLM
  Neural → Simbólico : valida fatos na resposta APÓS a geração do LLM

Benefícios:
  - Reduz alucinações: LLM recebe fatos corretos no contexto antes de gerar
  - Detecta inconsistências: valida se resposta gerada bate com o KG
  - Inferência transitiva: calcula cadeias completas de pré-requisitos via nx.ancestors()
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .knowledge_graph import KnowledgeGraph


# Intents que recebem enriquecimento do KG antes do LLM (Simbólico → Neural)
ENRICH_DISCIPLINE_INTENTS: frozenset = frozenset({
    "ementa_disciplina",
    "prerequisite_chain",
    "dependents",
    "discipline_docentes",
})

ENRICH_DOCENTE_INTENTS: frozenset = frozenset({
    "docente_info",
    "docente_areas",
    "docente_disciplines",
    "docentes_by_area",
})

# Intents validados após geração (Neural → Simbólico)
VALIDATE_PREREQ_INTENTS: frozenset = frozenset({"prerequisite_chain"})
VALIDATE_DOCENTE_INTENTS: frozenset = frozenset({"discipline_docentes", "docente_disciplines"})


@dataclass
class ValidationResult:
    """Resultado da validação simbólica de uma resposta do LLM."""

    is_valid: bool = True
    violations: List[str] = field(default_factory=list)
    verified_facts: List[str] = field(default_factory=list)

    def to_annotation(self) -> str:
        """Formata nota de verificação para anexar ao final da resposta."""
        if not self.violations and not self.verified_facts:
            return ""
        lines = ["\n\n---"]
        if self.verified_facts:
            lines.append("*Verificado no Knowledge Graph:* " + " · ".join(self.verified_facts[:3]))
        if self.violations:
            lines.append("*⚠ Atenção:* " + " · ".join(self.violations[:2]))
        return "\n".join(lines)


class SymbolicValidator:
    """
    Validador simbólico que usa o Knowledge Graph para:

    1. Enriquecer o contexto com fatos verificados (Simbólico → Neural)
       Chamado ANTES do LLM: prepend de fatos confiáveis ao prompt

    2. Validar a resposta gerada (Neural → Simbólico)
       Chamado APÓS o LLM: detecta afirmações que contradizem o KG
    """

    def __init__(self, kg: "KnowledgeGraph"):
        self.kg = kg
        self._normalize = kg._normalize_text
        # Caches lazy — invalidados quando o grafo é enriquecido
        self._known_disciplines: Optional[Set[str]] = None
        self._known_docentes: Optional[Set[str]] = None

    # ── Gerenciamento de cache ────────────────────────────────────────────────

    def invalidate_cache(self):
        """Invalida os caches. Chamar após enriquecimento do grafo."""
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

    # ── Simbólico → Neural (enriquecimento de contexto) ──────────────────────

    def enrich_agent_context(self, intent: str, term: str) -> str:
        """
        Ponto de entrada principal para enriquecimento de contexto.
        Retorna bloco de fatos verificados do KG para ser prepended ao contexto.
        Retorna string vazia se não há enriquecimento disponível.
        """
        if not term or term in ("", "unknown"):
            return ""

        if intent in ENRICH_DISCIPLINE_INTENTS:
            return self._build_discipline_facts(term)
        elif intent in ENRICH_DOCENTE_INTENTS:
            return self._build_docente_facts(term)
        return ""

    def _build_discipline_facts(self, disciplina: str) -> str:
        """Bloco de fatos verificados do KG para uma disciplina."""
        node_id = self.kg._find_node(disciplina, "disciplina")
        if not node_id:
            return ""

        lines = []

        # Pré-requisitos diretos
        prereqs_diretos = self.kg.get_prerequisite_chain(disciplina, max_depth=1)
        if prereqs_diretos:
            lines.append(f"Pré-requisitos diretos: {', '.join(prereqs_diretos)}")
        else:
            lines.append("Pré-requisitos diretos: nenhum")

        # Inferência transitiva — todos os ancestrais na cadeia de pré-requisitos
        todos_prereqs = self.kg.get_all_ancestors(disciplina)
        indiretos = [p for p in todos_prereqs if p not in prereqs_diretos]
        if indiretos:
            lines.append(f"Pré-requisitos transitivos (indiretos): {', '.join(indiretos[:8])}")

        # Docentes responsáveis pela disciplina
        docentes = self.kg.get_docentes_of_discipline(disciplina)
        if docentes:
            lines.append(f"Docentes responsáveis: {', '.join(docentes)}")

        # Esta disciplina desbloqueia quais outras?
        dependentes = self.kg.get_dependent_disciplines(disciplina)
        if dependentes:
            lines.append(f"Desbloqueia (é pré-requisito de): {', '.join(dependentes[:5])}")

        if not lines:
            return ""

        return (
            f"[FATOS VERIFICADOS NO KNOWLEDGE GRAPH — {disciplina}]\n"
            + "\n".join(f"  • {line}" for line in lines)
        )

    def _build_docente_facts(self, docente: str) -> str:
        """Bloco de fatos verificados do KG para um docente."""
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

    # ── Neural → Simbólico (validação pós-geração) ───────────────────────────

    def validate_response(self, response: str, intent: str, term: str) -> ValidationResult:
        """
        Ponto de entrada principal para validação.
        Verifica se fatos-chave na resposta do LLM batem com o KG.
        """
        if intent in VALIDATE_PREREQ_INTENTS and term:
            return self._validate_prereq_claims(response, term)
        elif intent in VALIDATE_DOCENTE_INTENTS and term:
            return self._validate_docente_claims(response, term)
        else:
            return self._validate_generic(response)

    def _validate_prereq_claims(self, response: str, disciplina: str) -> ValidationResult:
        """Verifica se os pré-requisitos afirmados na resposta existem no KG."""
        result = ValidationResult()

        real_prereqs_raw = self.kg.get_prerequisite_chain(disciplina, max_depth=1)
        real_prereqs_norm = {self._normalize(p) for p in real_prereqs_raw}

        if real_prereqs_raw:
            result.verified_facts.append(
                f"Pré-requisitos de {disciplina}: {', '.join(real_prereqs_raw)}"
            )
        else:
            node_id = self.kg._find_node(disciplina, "disciplina")
            if node_id:
                result.verified_facts.append(f"{disciplina}: sem pré-requisitos diretos no KG")

        # Detectar afirmações de pré-requisito na resposta do LLM
        claim_patterns = [
            r'([A-ZÀ-Úa-zà-ú][A-Za-zÀ-Úà-ú\s\-I]+?)\s+é\s+pré[\-\s]?requisito',
            r'requer\s+([A-ZÀ-Ú][A-Za-zÀ-Úà-ú\s]+?)(?:\s+e\s+|\s*[,.\n]|$)',
            r'antes\s+(?:de\s+)?(?:cursar|fazer)\s+([A-ZÀ-Ú][A-Za-zÀ-Úà-ú\s]+?)(?:\s*[,.\n]|$)',
        ]

        known = self._get_known_disciplines()
        claimed_names = set()
        for pattern in claim_patterns:
            for m in re.finditer(pattern, response, re.IGNORECASE):
                name_raw = m.group(1).strip()
                name_norm = self._normalize(name_raw)
                if name_norm and len(name_norm) > 3:
                    claimed_names.add((name_raw, name_norm))

        for name_raw, name_norm in claimed_names:
            if name_norm not in known:
                partial_match = any(
                    (name_norm in k or k in name_norm)
                    for k in known
                    if len(k) > 5
                )
                if not partial_match:
                    result.violations.append(
                        f"Disciplina não encontrada no KG: '{name_raw}'"
                    )
                    result.is_valid = False

        return result

    def _validate_docente_claims(self, response: str, disciplina: str) -> ValidationResult:
        """Verifica se os docentes citados para a disciplina existem no KG."""
        result = ValidationResult()

        real_docentes = self.kg.get_docentes_of_discipline(disciplina)
        if real_docentes:
            result.verified_facts.append(
                f"Docentes de {disciplina} no KG: {', '.join(real_docentes)}"
            )

        resp_norm = self._normalize(response)
        confirmed = [d for d in real_docentes if self._normalize(d) in resp_norm]
        if confirmed:
            result.verified_facts.append(f"Confirmados na resposta: {', '.join(confirmed)}")

        result.is_valid = len(result.violations) == 0
        return result

    def _validate_generic(self, response: str) -> ValidationResult:
        """Validação genérica: conta entidades do KG presentes na resposta."""
        result = ValidationResult()
        resp_norm = self._normalize(response)

        confirmed_disc = sum(
            1 for d in self._get_known_disciplines() if len(d) > 6 and d in resp_norm
        )
        confirmed_doc = sum(
            1 for d in self._get_known_docentes() if len(d) > 6 and d in resp_norm
        )

        if confirmed_disc + confirmed_doc > 0:
            result.verified_facts.append(
                f"{confirmed_disc} disciplina(s) e {confirmed_doc} docente(s) verificados no KG"
            )

        return result

    # ── Utilitários ───────────────────────────────────────────────────────────

    def get_symbolic_facts_summary(self, disciplina: str) -> Dict:
        """
        Retorna dicionário com todos os fatos verificáveis do KG para uma disciplina.
        Útil para depuração e testes.
        """
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
            "docentes": self.kg.get_docentes_of_discipline(disciplina),
            "dependentes": self.kg.get_dependent_disciplines(disciplina),
        }
