"""
Estado compartilhado entre os nós do LangGraph.
"""

from typing import TypedDict, List, Optional, Dict, Any


class AgentState(TypedDict, total=False):
    # Pergunta original do usuário
    question: str
    # Pergunta após o ContextResolver (pode ser reescrita)
    enhanced_question: str
    # Últimas trocas da conversa formatadas ("Aluno: ...\nAssistente: ..."),
    # para continuidade de diálogo nos prompts (sem re-saudação a cada turno)
    history: str
    # Nome do agente ativo ("disciplinas" | "docentes" | "cursos" | "regimentos" | "fallback")
    active_agent: str
    # Intent classificado pelo IntentClassifier
    intent: str
    # Termo extraído da pergunta (ex: "Compiladores", "BCC", "João Silva")
    term: str
    # Confiança da classificação (0.0 a 1.0)
    confidence: float
    # Contexto recuperado pelos agentes
    context: str
    # Resposta final gerada
    response: str
    # Fontes usadas na resposta
    sources: List[str]
    # Contador de tentativas (para evitar loops)
    retry_count: int
    # Segunda chance (retry-on-miss): agente forçado pelo loop externo —
    # o router roteia direto para ele, sem reclassificar
    forced_agent: str
    # Sinal para o front abrir o planejador de grade (canvas ao vivo).
    # Preenchido pelo MontarGradeAgent: {curso: <detectado|None>}.
    plan_request: Optional[Dict[str, Any]]
    # Grafo estruturado de pré-requisitos para renderização no chat
    # ({nodes: [...], edges: [...]}, ver GraphRAGEngine.graph_payload).
    # Preenchido pelo atalho simbólico (prerequisite_chain / dependents /
    # trajectory_planning).
    graph_data: Optional[Dict[str, Any]]
