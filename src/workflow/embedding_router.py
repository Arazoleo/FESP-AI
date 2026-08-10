"""
Roteamento por similaridade semântica (embeddings).

Em vez de listas de frases, usamos exemplos por agente: a pergunta do usuário
é comparada aos exemplos e o agente com maior similaridade (acima de um limiar)
é escolhido. Novas formas de falar semanticamente próximas dos exemplos
roteiam corretamente sem adicionar padrões.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

AGENT_EXAMPLES: Dict[str, List[str]] = {
    "disciplinas": [
        "o que é Geometria Analítica",
        "o que é Cálculo Numérico",
        "descreva a disciplina Algoritmos",
        "o que se estuda em Compiladores",
        "me fale mais sobre matemática discreta",
        "me fale sobre Matemática Discreta",
        "me fale sobre Compiladores",
        "me fale sobre a disciplina de redes",
        "fale mais sobre a disciplina de compiladores",
        "a disciplina de matemática discreta, me fale mais",
        "qual a ementa de Matemática discreta",
        "qual a ementa de Banco de Dados",
        "conte mais sobre a disciplina de redes",
        "o que aprendo em Álgebra Linear",
        "do que trata Inteligência Artificial",
        "quais são os pré-requisitos de banco de dados",
        "pré-requisitos para cursar algoritmos 2",
        "o que preciso fazer antes de inteligência artificial",
        "disciplinas necessárias para fazer cálculo 2",
        "antes de cursar redes preciso de o que",
        "cadeia de pré-requisitos de estrutura de dados",
        "quais disciplinas dependem de cálculo 1",
        "o que posso cursar depois de algoritmos",
    ],
    "docentes": [
        "quem leciona banco de dados",
        "quais docentes dão Compiladores",
        "quais professores lecionam Cálculo Numérico",
        "quem ensina Algoritmos e Estruturas de Dados",
        "professores de Fenômenos Mecânicos",
        "qual o email do professor Rodrigo",
        "sala do professor Álvaro",
        "como entro em contato com a professora Maria",
        "me fale sobre a professora Lilian Berton",
        "quem é o professor Didier Vega",
        "quais disciplinas o professor João leciona",
        "disciplinas que o Rodrigo Colnago leciona",
        "quais matérias a Daniela dá",
        "qual a área de pesquisa do professor",
        "áreas de atuação do professor Tiago",
        "em que o Álvaro é especialista",
        "professores que trabalham com inteligência artificial",
        "quem pesquisa machine learning",
    ],
    "cursos": [
        "disciplinas do termo 5 de BCC",
        "quais disciplinas tem no termo 3 de engenharia",
        "grade curricular de ciência da computação",
        "matérias do primeiro semestre de computação",
        "grade completa de BCC",
        "eletivas de computação",
        "quais cursos a unifesp oferece",
        "informações sobre o curso de computação",
        "quem é o coordenador de BCC",
    ],
    "regimentos": [
        "o que o regimento diz sobre trancamento",
        "normas sobre aprovação",
        "atividades complementares como funciona",
        "dúvidas frequentes sobre matrícula",
        "FAQ sobre estágio",
        "regras de aprovação",
    ],
}


class EmbeddingAgentRouter:
    """
    Roteia a pergunta para um agente por similaridade semântica aos exemplos.
    """

    def __init__(
        self,
        embeddings_model: Any,
        confidence_threshold: float = 0.58,
    ):
        self.embeddings_model = embeddings_model
        self.confidence_threshold = confidence_threshold
        self._centroids: Dict[str, np.ndarray] = {}
        self._initialized = False

    def initialize(self) -> None:
        """Pré-computa os centróides dos exemplos por agente."""
        if self._initialized or not self.embeddings_model:
            return
        try:
            for agent, examples in AGENT_EXAMPLES.items():
                if not examples:
                    continue
                vecs = self.embeddings_model.embed_documents(examples)
                self._centroids[agent] = np.mean(vecs, axis=0).astype(np.float32)
            self._initialized = True
            logger.info(
                "[EmbeddingAgentRouter] %d agentes com centróides prontos",
                len(self._centroids),
            )
        except Exception as e:
            logger.warning("[EmbeddingAgentRouter] Falha ao inicializar: %s", e)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        n = np.linalg.norm(a) * np.linalg.norm(b)
        if n == 0:
            return 0.0
        return float(np.dot(a, b) / n)

    def route(self, question: str) -> Tuple[str, float]:
        """
        Retorna (agente, confiança) com base na similaridade ao centróide de cada agente.
        Se confiança < threshold, retorna ("", 0.0) para o caller usar fallback.
        """
        if not self._initialized or not self._centroids:
            return "", 0.0
        try:
            q_embed = np.array(
                self.embeddings_model.embed_query(question), dtype=np.float32
            )
            best_agent = ""
            best_score = -1.0
            for agent, centroid in self._centroids.items():
                sim = self._cosine_similarity(q_embed, centroid)
                if sim > best_score:
                    best_score = sim
                    best_agent = agent
            if best_score >= self.confidence_threshold:
                return best_agent, float(best_score)
            return "", float(best_score)
        except Exception as e:
            logger.debug("[EmbeddingAgentRouter] Erro ao rotear: %s", e)
            return "", 0.0
