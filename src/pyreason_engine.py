"""
Motor neurossimbólico baseado em PyReason (Aditya et al., AAAI 2023).

Estende `InferenceEngine` substituindo a derivação **dedutiva** por um reasoner
de lógica anotada (Datalog com bounds [l, u] ⊆ [0, 1]). As regras dedutivas:

    prereq_transitivity:  prereq(x, z) <- prereq(x, y), prereq(y, z)
    co_prerequisite:      co_prereq(x, y) <- prereq(x, z), prereq(y, z)

são executadas pelo PyReason sobre um sub-grafo limpo de disciplinas, com
propagação automática de bounds de confiança das arestas `PREREQUISITO_DE`.

Operações **não-dedutivas** (planejamento de trajetória, contagem de
dependentes, queries dinâmicas dependentes de C) permanecem em Python via
herança de `InferenceEngine` - PyReason não traz ganho ali e o overhead de
re-inicialização do reasoner global tornaria queries dinâmicas inviáveis.
"""

from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import networkx as nx

from .neurosymbolic_validator import InferenceEngine

if TYPE_CHECKING:
    from .knowledge_graph import KnowledgeGraph


class PyReasonEngine(InferenceEngine):
    RULES_DATALOG: Dict[str, str] = {
        "prereq_transitivity_base": "prereq_trans(x, z) <-1 prereq(x, y), prereq(y, z)",
        "prereq_transitivity_step": "prereq_trans(x, z) <-1 prereq(x, y), prereq_trans(y, z)",
    }

    def __init__(self, kg: "KnowledgeGraph"):
        super().__init__(kg)
        self._inferred: bool = False
        self._id_to_name: Dict[str, str] = {}
        self._name_to_id: Dict[str, str] = {}
        self._transitive_prereqs_bounds: Dict[str, List[Tuple[str, List[float]]]] = {}


    def _build_subgraph(self) -> nx.DiGraph:
        """Sub-grafo limpo: só disciplinas e arestas PREREQUISITO_DE.

        IDs originais (`DISC:Cálculo I`) contêm `:`, espaços e acentos que
        quebram o parser de regras do PyReason. Mapeamos para `d0, d1, ...`
        e mantemos `_id_to_name` para retornar nomes legíveis.
        """
        sg: nx.DiGraph = nx.DiGraph()
        node_map: Dict[str, str] = {}

        for idx, (node_id, data) in enumerate(self.kg.graph.nodes(data=True)):
            if data.get("tipo") != "disciplina":
                continue
            clean = f"d{len(node_map)}"
            node_map[node_id] = clean
            nome = data.get("nome", node_id)
            self._id_to_name[clean] = nome
            norm = self.kg._normalize_text(nome)
            if norm:
                self._name_to_id[norm] = clean
            sg.add_node(clean)

        for u, v, data in self.kg.graph.edges(data=True):
            if data.get("relacao") != "PREREQUISITO_DE":
                continue
            cu, cv = node_map.get(u), node_map.get(v)
            if not cu or not cv:
                continue
            sg.add_edge(cu, cv, prereq=1)

        return sg

    def _max_chain_depth(self, sg: nx.DiGraph) -> int:
        """Profundidade da DAG = número de timesteps necessários para o
        fecho transitivo convergir. A regra `step` propaga um nível por
        timestep; em uma chain de comprimento N, precisamos de ~N steps.
        Damos uma margem 2x para garantir convergência mesmo em casos
        com ramificações que requerem mais iterações.
        """
        try:
            longest = nx.dag_longest_path_length(sg)
        except Exception:
            longest = 10
        return max(2, 2 * longest)

    def _init_reasoner(self) -> bool:
        """Inicializa o PyReason e executa o fecho dedutivo uma única vez.

        Returns True se o reasoner rodou com sucesso, False caso contrário
        (fallback para a implementação Python de `InferenceEngine`).
        """
        if self._inferred:
            return True

        try:
            import pyreason as pr
        except ImportError:
            return False

        sg = self._build_subgraph()
        if sg.number_of_edges() == 0:
            self._inferred = True
            return True

        try:
            pr.reset()
            pr.reset_rules()
            pr.reset_settings()
            pr.settings.verbose = False
            pr.settings.atom_trace = False
            pr.settings.memory_profile = False

            pr.load_graph(sg)
            for name, rule_str in self.RULES_DATALOG.items():
                pr.add_rule(pr.Rule(rule_str, name, infer_edges=True))

            timesteps = self._max_chain_depth(sg) + 1
            interp = pr.reason(timesteps=timesteps)
            self._extract_results(interp, sg)
            self._inferred = True
            return True
        except Exception:
            self._inferred = False
            return False

    def _extract_results(self, interpretation, sg: nx.DiGraph) -> None:
        """Extrai o fecho transitivo do reasoner e calcula bounds por path.

        Estratégia:
          (1) PyReason fornece o conjunto de pares (ancestor → descendant)
              que estão na cadeia transitiva - Boolean, sem bounds.
          (2) Para cada par derivado, calculamos o bound como o `min` das
              confidences ao longo de algum caminho A → ... → D no KG
              original (semântica de "elo mais fraco"). Como há múltiplos
              caminhos possíveis, escolhemos o de maior `min` (caminho de
              maior confiança), que é a interpretação otimista padrão.
          (3) Prereqs diretos (1 salto) ficam com bound `[confidence, 1.0]`.
        """
        import pyreason as pr

        seen: Dict[str, set] = {}

        for u, v, _data in sg.edges(data=True):
            src_name = self._id_to_name.get(u)
            dst_name = self._id_to_name.get(v)
            if not src_name or not dst_name:
                continue
            conf = self.kg.get_prerequisite_confidence(src_name, dst_name)
            if conf <= 0.0:
                conf = 1.0
            self._transitive_prereqs_bounds.setdefault(dst_name, []).append(
                (src_name, [conf, 1.0])
            )
            seen.setdefault(dst_name, set()).add(src_name)

        trans_dfs = pr.filter_and_sort_edges(interpretation, ["prereq_trans"])
        if not trans_dfs:
            return
        last_df = trans_dfs[-1]
        for _, row in last_df.iterrows():
            comp = row["component"]
            src_name = self._id_to_name.get(comp[0])
            dst_name = self._id_to_name.get(comp[1])
            if not src_name or not dst_name:
                continue
            if src_name in seen.get(dst_name, set()):
                continue
            low = self._min_confidence_best_path(src_name, dst_name)
            self._transitive_prereqs_bounds.setdefault(dst_name, []).append(
                (src_name, [low, 1.0])
            )
            seen.setdefault(dst_name, set()).add(src_name)


    def _min_confidence_best_path(self, src_name: str, dst_name: str) -> float:
        """Bound do par transitivo = max sobre caminhos do (min sobre arestas).

        Semântica: "qual a maior confiança alcançável em algum caminho de
        src até dst" - interpretação otimista, padrão para bottleneck path.
        """
        src_id = self.kg._find_node(src_name, "disciplina")
        dst_id = self.kg._find_node(dst_name, "disciplina")
        if not src_id or not dst_id:
            return 1.0

        prereq_g: nx.DiGraph = nx.DiGraph()
        for u, v, data in self.kg.graph.edges(data=True):
            if data.get("relacao") != "PREREQUISITO_DE":
                continue
            conf = float(data.get("confidence", 1.0))
            prereq_g.add_edge(u, v, conf=conf)

        if src_id not in prereq_g or dst_id not in prereq_g:
            return 1.0
        try:
            paths = list(nx.all_simple_paths(prereq_g, src_id, dst_id, cutoff=10))
        except Exception:
            return 1.0
        if not paths:
            return 1.0
        best = 0.0
        for path in paths:
            mins = 1.0
            for u, v in zip(path[:-1], path[1:]):
                mins = min(mins, prereq_g[u][v].get("conf", 1.0))
            best = max(best, mins)
        return best if best > 0 else 1.0


    def _find_by_name(self, disciplina: str, table: Dict) -> Optional[str]:
        norm_target = self.kg._normalize_text(disciplina)
        for key in table:
            if self.kg._normalize_text(key) == norm_target:
                return key
        return None


    def get_transitive_prereqs_with_bounds(
        self, disciplina: str
    ) -> List[Tuple[str, List[float]]]:
        """Retorna pré-requisitos transitivos com bounds de confiança propagados."""
        if not self._init_reasoner():
            return [(p, [1.0, 1.0]) for p in self.kg.get_all_ancestors(disciplina)]
        key = self._find_by_name(disciplina, self._transitive_prereqs_bounds)
        return self._transitive_prereqs_bounds.get(key, []) if key else []


    def _infer_prereq_context(self, disciplina: str) -> str:
        if not self._init_reasoner():
            return super()._infer_prereq_context(disciplina)

        lines: List[str] = []
        critical = dict(self.critical_disciplines(min_dependents=3))
        prereqs = self.kg.get_prerequisite_chain(disciplina, max_depth=1)

        critical_prereqs = [(p, critical[p]) for p in prereqs if p in critical]
        if critical_prereqs:
            strs = [f"{p} ({n} dependentes)" for p, n in critical_prereqs]
            lines.append(
                f"[Regra critical_discipline | Python] Pré-requisitos críticos: "
                f"{', '.join(strs)}"
            )

        trans = self.get_transitive_prereqs_with_bounds(disciplina)
        if trans:
            partes = []
            for nome, bound in trans[:6]:
                low, high = bound[0], bound[1]
                if low < 1.0:
                    partes.append(f"{nome} [{low:.0%}, {high:.0%}]")
                else:
                    partes.append(nome)
            lines.append(
                f"[Regra prereq_transitivity | PyReason] Pré-requisitos transitivos: "
                f"{', '.join(partes)}"
            )

        co = self.find_co_prerequisites(disciplina)
        if co:
            lines.append(
                f"[Regra co_prerequisite | Python] Disciplinas frequentemente cursadas junto: "
                f"{', '.join(co[:4])}"
            )

        if not lines:
            return ""
        return "[FATOS INFERIDOS - PyReasonEngine]\n" + "\n".join(f"  • {l}" for l in lines)
