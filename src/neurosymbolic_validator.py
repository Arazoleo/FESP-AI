import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .knowledge_graph import KnowledgeGraph


ENRICH_DISCIPLINE_INTENTS: frozenset = frozenset({
    "ementa_disciplina",
    "prerequisite_chain",
    "dependents",
    "discipline_docentes",
    "unlocked_disciplines",
})

ENRICH_DOCENTE_INTENTS: frozenset = frozenset({
    "docente_info",
    "docente_areas",
    "docente_disciplines",
    "docentes_by_area",
})

VALIDATE_PREREQ_INTENTS: frozenset = frozenset({"prerequisite_chain"})
VALIDATE_DOCENTE_INTENTS: frozenset = frozenset({"discipline_docentes", "docente_disciplines"})


@dataclass
class ValidationResult:
    is_valid: bool = True
    violations: List[str] = field(default_factory=list)
    verified_facts: List[str] = field(default_factory=list)
    confidence_scores: Dict[str, float] = field(default_factory=dict)

    def to_annotation(self) -> str:
        if not self.violations and not self.verified_facts:
            return ""
        lines = ["\n\n---"]
        if self.verified_facts:
            lines.append("*Verificado no Knowledge Graph:* " + " · ".join(self.verified_facts[:3]))
        low_conf = {k: v for k, v in self.confidence_scores.items() if v < 1.0}
        if low_conf:
            conf_strs = [f"{k}: {v:.0%}" for k, v in list(low_conf.items())[:3]]
            lines.append("*Confiança parcial:* " + " · ".join(conf_strs))
        if self.violations:
            lines.append("*Atenção:* " + " · ".join(self.violations[:2]))
        return "\n".join(lines)


class SymbolicValidator:
    def __init__(self, kg: "KnowledgeGraph", llm=None):
        self.kg = kg
        self.llm = llm
        self._normalize = kg._normalize_text
        self._known_disciplines: Optional[Set[str]] = None
        self._known_docentes: Optional[Set[str]] = None

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

    def enrich_agent_context(self, intent: str, term: str) -> str:
        if not term or term in ("", "unknown"):
            return ""

        if intent == "unlocked_disciplines":
            return self._build_unlocked_facts(term)
        if intent in ENRICH_DISCIPLINE_INTENTS:
            return self._build_discipline_facts(term)
        if intent in ENRICH_DOCENTE_INTENTS:
            return self._build_docente_facts(term)
        return ""

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
                prereq_strs.append(f"{p} ({conf:.0%})" if conf < 1.0 else p)
            lines.append(f"Pré-requisitos diretos: {', '.join(prereq_strs)}")
        else:
            lines.append("Pré-requisitos diretos: nenhum")

        todos_prereqs = self.kg.get_all_ancestors(disciplina)
        indiretos = [p for p in todos_prereqs if p not in prereqs_diretos]
        if indiretos:
            lines.append(f"Pré-requisitos transitivos (indiretos): {', '.join(indiretos[:8])}")

        docentes = self.kg.get_docentes_of_discipline(disciplina)
        if docentes:
            lines.append(f"Docentes responsáveis: {', '.join(docentes)}")

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
        completed = [d.strip() for d in term.split(',') if d.strip()]
        if not completed:
            return ""

        unlocked = self.kg.get_unlocked_disciplines(completed)

        header = f"[FATOS VERIFICADOS NO KNOWLEDGE GRAPH — Disciplinas Desbloqueadas]\n"
        header += f"  • Cursadas: {', '.join(completed)}\n"
        if unlocked:
            header += f"  • Desbloqueadas agora: {', '.join(unlocked[:10])}"
        else:
            header += "  • Nenhuma disciplina totalmente desbloqueada com estas cursadas"
        return header

    def validate_response(self, response: str, intent: str, term: str) -> ValidationResult:
        if intent in VALIDATE_PREREQ_INTENTS and term:
            result = self._validate_prereq_claims(response, term)
        elif intent in VALIDATE_DOCENTE_INTENTS and term:
            result = self._validate_docente_claims(response, term)
        else:
            result = self._validate_generic(response)

        # Estágio 3: sinalizar ausência de cobertura no KG
        if term and not result.verified_facts and not result.violations:
            node_id = (self.kg._find_node(term, "disciplina") or
                       self.kg._find_docente_id(term))
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
                result.verified_facts.append(f"{disciplina}: sem pré-requisitos diretos no KG")

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
            if name_norm in known:
                continue

            # Estágio 1: partial match no KG
            partial_match = any(
                (name_norm in k or k in name_norm)
                for k in known
                if len(k) > 5
            )

            # Estágio 2: confirmação via LLM quando parcial match falha
            if not partial_match and self.llm:
                try:
                    from langchain_core.messages import HumanMessage
                    prompt = (
                        f"A disciplina '{name_raw}' existe na grade curricular da UNIFESP ICT? "
                        "Responda apenas 'sim' ou 'não'."
                    )
                    answer = self.llm.invoke([HumanMessage(content=prompt)])
                    answer_text = (
                        answer.content if hasattr(answer, "content") else str(answer)
                    ).lower()
                    if "sim" in answer_text:
                        partial_match = True
                except Exception:
                    pass

            if not partial_match:
                result.violations.append(
                    f"Disciplina não encontrada no KG: '{name_raw}'"
                )
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
        if confirmed:
            result.verified_facts.append(f"Confirmados na resposta: {', '.join(confirmed)}")

        result.is_valid = len(result.violations) == 0
        return result

    def _validate_generic(self, response: str) -> ValidationResult:
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

    def get_symbolic_facts_summary(self, disciplina: str) -> Dict:
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
        }
