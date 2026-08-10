"""
Estado compartilhado entre os nós do LangGraph.
"""

from typing import TypedDict, List, Optional, Dict, Any


class AgentState(TypedDict, total=False):
    question: str
    enhanced_question: str
    history: str
    active_agent: str
    intent: str
    term: str
    confidence: float
    context: str
    response: str
    sources: List[str]
    retry_count: int
    forced_agent: str
    plan_request: Optional[Dict[str, Any]]
    graph_data: Optional[Dict[str, Any]]
