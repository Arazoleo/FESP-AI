#!/usr/bin/env python3
import warnings
import os
import re
import logging
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from collections import OrderedDict
from uuid import uuid4

warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.NotOpenSSLWarning)
except ImportError:
    pass

from pathlib import Path
import json
import asyncio
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from .multi_agent_rag import MultiAgentRAG
from .planner import plan_curriculum, DEFAULT_MAX_CREDITOS
from .context_resolver import context_resolver
from .llm_judge import judge_answer
from langchain_ollama import OllamaLLM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="FESP-AI API", version="0.1.0")

cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://frontend:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag: MultiAgentRAG = None

# ── Ollama helpers ────────────────────────────────────────────────────────────

def ensure_ollama_model(ollama_url: str, model: str):
    """
    Garante que o modelo exista no Ollama.
    Se não existir, tenta fazer pull automaticamente.
    """
    if not model:
        return
    import requests

    try:
        show = requests.post(f"{ollama_url}/api/show", json={"name": model}, timeout=30)
        if show.status_code == 200:
            return
    except Exception:
        # Se show falhar, ainda tentamos pull.
        pass

    print(f"  - Baixando modelo no Ollama: {model}")
    r = requests.post(
        f"{ollama_url}/api/pull",
        json={"name": model, "stream": False},
        timeout=60 * 30,
    )
    r.raise_for_status()


# Configurações de gerenciamento de memória para conversas
MAX_CONVERSATIONS = 1000  # Máximo de conversas simultâneas
CONVERSATION_TTL = timedelta(hours=24)  # Tempo de vida das conversas

# Usar OrderedDict para manter ordem de inserção (LRU)
conversations: OrderedDict[str, List[dict]] = OrderedDict()
conversation_timestamps: Dict[str, datetime] = {}


def cleanup_old_conversations():
    """Remove conversas antigas e limita o número total de conversas."""
    now = datetime.now()
    
    # Remover conversas expiradas
    expired = [
        cid for cid, ts in conversation_timestamps.items()
        if now - ts > CONVERSATION_TTL
    ]
    for cid in expired:
        conversations.pop(cid, None)
        conversation_timestamps.pop(cid, None)
    
    # Limitar número máximo (remover mais antigas - LRU)
    while len(conversations) > MAX_CONVERSATIONS:
        oldest_cid, _ = conversations.popitem(last=False)
        conversation_timestamps.pop(oldest_cid, None)
    
    if expired:
        logger.info(f"[CLEANUP] Removidas {len(expired)} conversas expiradas. Total: {len(conversations)}")


# Limites do histórico injetado nos prompts (continuidade de diálogo).
# Curto de propósito: o histórico serve para tom/referências, não como fonte
# de fatos — respostas longas são truncadas para não inflar o prompt.
HISTORY_PROMPT_MAX_TURNS = 6
HISTORY_PROMPT_MAX_CHARS_PER_MSG = 350


def format_history_for_prompt(messages: List[dict]) -> str:
    """Formata as últimas trocas como "Aluno: ... / Assistente: ..." para o prompt."""
    import re as _re
    linhas = []
    for msg in messages[-HISTORY_PROMPT_MAX_TURNS:]:
        papel = "Aluno" if msg.get("role") == "user" else "Assistente"
        content = _re.sub(r"\s+", " ", str(msg.get("content", ""))).strip()
        if len(content) > HISTORY_PROMPT_MAX_CHARS_PER_MSG:
            content = content[:HISTORY_PROMPT_MAX_CHARS_PER_MSG].rsplit(" ", 1)[0] + "…"
        if content:
            linhas.append(f"{papel}: {content}")
    return "\n".join(linhas)


class Message(BaseModel):
    role: str  # "user" ou "assistant"
    content: str
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    include_history: bool = True
    max_history: int = 10  # Número máximo de mensagens anteriores a incluir


class ChatEvalRequest(BaseModel):
    message: str
    include_history: bool = False
    max_history: int = 0
    include_context: bool = True
    include_sources: bool = True


class ChatEvalResponse(BaseModel):
    response: str
    active_agent: str
    intent: str = "unknown"
    term: str = ""
    confidence: float = 0.0
    context: Optional[str] = None
    sources: Optional[List[str]] = None


class JudgeRequest(BaseModel):
    question: str
    answer: str
    evidence: str = ""
    judge_model: Optional[str] = None


class JudgeResponse(BaseModel):
    groundedness: int
    correctness: int
    completeness: int
    clarity: int
    unsupported_claims: int
    rationale: str


class AgentInfo(BaseModel):
    label: str
    description: str
    color: str
    icon: str


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    timestamp: str
    active_agent: str = "fallback"
    agent_info: Optional[AgentInfo] = None
    # Quando preenchido, o front deve abrir o planejador de grade (canvas ao vivo).
    plan_request: Optional[Dict] = None


class ConversationResponse(BaseModel):
    conversation_id: str
    messages: List[Message]


@app.on_event("startup")
async def startup_event():
    import requests
    import threading
    global rag
    print("Inicializando Multi-Agent RAG...")
    rag = MultiAgentRAG()

    # Antes de indexar/criar embeddings, garantir que os modelos existem.
    try:
        ollama_url = rag.config.OLLAMA_BASE_URL or "http://ollama:11434"
        ensure_ollama_model(ollama_url, rag.config.EMBEDDING_MODEL)
        ensure_ollama_model(ollama_url, rag.config.MODEL_NAME)
    except Exception as e:
        # Se não conseguir baixar, falha com mensagem clara (evita loop de restart sem contexto)
        raise RuntimeError(
            f"Falha ao garantir modelos no Ollama ({rag.config.OLLAMA_BASE_URL}). "
            f"Verifique se o Ollama está acessível e faça pull do modelo. Erro: {e}"
        )

    rag.sync()
    print("Multi-Agent RAG inicializado e pronto!")
    
    def warmup_models():
        import time
        time.sleep(1)
        print("Pre-carregando modelos (warmup)...")
        try:
            ollama_url = rag.config.OLLAMA_BASE_URL or "http://ollama:11434"
            print(f"  - Carregando modelo LLM: {rag.config.MODEL_NAME}")
            requests.post(f"{ollama_url}/api/generate", json={
                "model": rag.config.MODEL_NAME,
                "prompt": "teste",
                "stream": False,
                "keep_alive": "5m"
            }, timeout=60)
            print(f"  - Carregando modelo embeddings: {rag.config.EMBEDDING_MODEL}")
            requests.post(f"{ollama_url}/api/embed", json={
                "model": rag.config.EMBEDDING_MODEL,
                "input": "teste",
                "keep_alive": "5m"
            }, timeout=60)
            print("Modelos pre-carregados! Primeira query sera mais rapida.")
        except Exception as e:
            print(f"Warmup falhou: {e}")
    
    threading.Thread(target=warmup_models, daemon=True).start()

    def warmup_pyreason():
        """Pré-aquece o reasoner Datalog (PyReason) e seu JIT do numba.

        O primeiro `pr.reason()` paga ~20s compilando kernels do numba.
        Roda em background no startup para que a primeira query que
        precise de inferência transitiva não pague essa penalidade.
        Usa `_build_default_engine` para popular o cache global — todas
        as instâncias subsequentes de SymbolicValidator vão reutilizar
        o mesmo engine warmed-up.
        """
        import time
        time.sleep(2)  # esperar o KG terminar de carregar
        try:
            if rag is None or rag.knowledge_graph is None:
                print("PyReason warmup: KG indisponível, pulando.")
                return
            print("PyReason warmup: pré-aquecendo reasoner Datalog...")
            from .neurosymbolic_validator import _build_default_engine
            engine = _build_default_engine(rag.knowledge_graph)
            if hasattr(engine, "_init_reasoner"):
                ok = engine._init_reasoner()
                print(f"PyReason warmup: reasoner pronto (ok={ok}).")
            else:
                print("PyReason warmup: usando engine Python (fallback).")
        except Exception as e:
            print(f"PyReason warmup falhou (não-fatal, fallback Python): {e}")

    threading.Thread(target=warmup_pyreason, daemon=True).start()


@app.get("/")
async def root():
    return {
        "message": "FESP-AI API",
        "status": "running",
        "version": "0.1.0"
    }


@app.get("/telemetry")
async def telemetry():
    """Contadores do loop neurossimbólico (grounding, correções B1, reescritas)."""
    from .telemetry import snapshot
    return snapshot()


@app.get("/health")
async def health():
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG nao inicializado")
    return {
        "status": "healthy",
        "rag_ready": rag.chain is not None,
        "multi_agent": rag._pipeline is not None,
        "model": rag.config.MODEL_NAME,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG nao inicializado")
    
    conversation_id = request.conversation_id or str(uuid4())
    
    # Limpar conversas antigas periodicamente
    cleanup_old_conversations()
    
    if conversation_id not in conversations:
        conversations[conversation_id] = []
        conversation_timestamps[conversation_id] = datetime.now()
    else:
        # Atualizar timestamp (mover para final - LRU)
        conversations.move_to_end(conversation_id)
        conversation_timestamps[conversation_id] = datetime.now()
    
    user_message = {
        "role": "user",
        "content": request.message,
        "timestamp": datetime.now().isoformat()
    }
    conversations[conversation_id].append(user_message)
    
    # Usar o ContextResolver para resolver referências contextuais
    history_text = ""
    if request.include_history and len(conversations[conversation_id]) > 1:
        history = conversations[conversation_id][-request.max_history-1:-1]
        # Histórico formatado para os prompts dos agentes (continuidade de
        # diálogo — evita "Olá!" a cada turno e permite referências ao que
        # já foi dito)
        history_text = format_history_for_prompt(history)
        
        # Atualizar contexto com mensagens do histórico
        for msg in history:
            context_resolver.update_context(conversation_id, msg['content'], msg['role'])
        
        # Resolver referências na pergunta atual (baseado em regras)
        enhanced_question, was_modified = context_resolver.resolve_question(
            request.message, 
            conversation_id, 
            history
        )
        
        # Se não foi modificado mas a pergunta é ambígua, usar LLM
        if not was_modified and context_resolver.is_ambiguous_question(request.message):
            # Usar LLM para reescrever apenas se realmente necessário
            if rag and rag.llm:
                enhanced_question = context_resolver.rewrite_with_llm(
                    request.message,
                    conversation_id,
                    history,
                    rag.llm
                )
                if enhanced_question != request.message:
                    was_modified = True
        
        if was_modified:
            logger.info(f"[CONTEXT] Pergunta resolvida: '{request.message}' → '{enhanced_question}'")
    else:
        enhanced_question = request.message
    
    # Atualizar contexto com a pergunta atual
    context_resolver.update_context(conversation_id, request.message, 'user')

    try:
        result = rag.query_with_metadata(enhanced_question, history=history_text)
        response_text = result["response"]
        active_agent = result.get("active_agent", "fallback")
        agent_metadata = result.get("agent_info") or result.get("agent_metadata", {})
        plan_request = result.get("plan_request")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar pergunta: {str(e)}")
    
    assistant_message = {
        "role": "assistant",
        "content": response_text,
        "timestamp": datetime.now().isoformat()
    }
    conversations[conversation_id].append(assistant_message)
    
    # Atualizar contexto com a resposta (para extrair listas de docentes, etc.)
    context_resolver.update_context(conversation_id, response_text, 'assistant')
    
    logger.info(f"[AGENT] Agente ativo: {active_agent}")
    
    agent_info = None
    if agent_metadata:
        agent_info = AgentInfo(
            label=agent_metadata.get("label", active_agent),
            description=agent_metadata.get("description", ""),
            color=agent_metadata.get("color", "#6b7280"),
            icon=agent_metadata.get("icon", "Bot"),
        )
    
    return ChatResponse(
        response=response_text,
        conversation_id=conversation_id,
        timestamp=assistant_message["timestamp"],
        active_agent=active_agent,
        agent_info=agent_info,
        plan_request=plan_request,
    )


@app.post("/chat_eval", response_model=ChatEvalResponse)
async def chat_eval(request: ChatEvalRequest):
    """
    Endpoint voltado para avaliação offline.
    Retorna (opcionalmente) contexto e fontes para permitir métricas de fidelidade/grounding.
    """
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG nao inicializado")

    enhanced_question = request.message
    try:
        result = rag.query_with_metadata(enhanced_question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar pergunta: {str(e)}")

    return ChatEvalResponse(
        response=(result.get("response") or "").strip(),
        active_agent=result.get("active_agent", "fallback"),
        intent=result.get("intent", "unknown"),
        term=result.get("term", ""),
        confidence=float(result.get("confidence", 0.0) or 0.0),
        context=result.get("context") if request.include_context else None,
        sources=result.get("sources") if request.include_sources else None,
    )


@app.post("/llm_judge", response_model=JudgeResponse)
async def llm_judge(request: JudgeRequest):
    """Executa LLM-as-a-Judge (opcionalmente com um modelo cloud alternativo)."""
    if rag is None or rag.llm is None:
        raise HTTPException(status_code=503, detail="LLM nao inicializado")

    try:
        llm = rag.llm
        if request.judge_model and request.judge_model.strip():
            ollama_url = rag.config.OLLAMA_BASE_URL or "http://ollama:11434"
            # garantir que o modelo do juiz existe (pull se necessário)
            # reusar a função do startup (está no escopo do módulo)
            try:
                ensure_ollama_model(ollama_url, request.judge_model.strip())
            except Exception:
                # não bloquear; se o modelo já existir e show falhou, seguimos
                pass
            llm = OllamaLLM(
                model=request.judge_model.strip(),
                base_url=ollama_url,
                temperature=0.0,
                num_predict=1024,
            )
        res = judge_answer(
            llm=llm,
            question=request.question,
            answer=request.answer,
            evidence=request.evidence,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no judge: {str(e)}")

    d = res.to_dict()
    return JudgeResponse(**d)


class BaselineRequest(BaseModel):
    message: str
    system: str = "b2"  # "b2" = Standard RAG | "b3" = Graph-RAG sem validação


class BaselineResponse(BaseModel):
    response: str
    system: str
    latency_s: float


@app.post("/chat_baseline", response_model=BaselineResponse)
async def chat_baseline(request: BaselineRequest):
    """
    Endpoint para avaliação dos baselines do paper BRACIS.
    
    system="b2" → Standard RAG (só vector store, sem KG, sem validação simbólica)
    system="b3" → Graph-RAG (KG + vector store, sem validação neurossimbólica)
    """
    import time
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    if rag is None:
        raise HTTPException(status_code=503, detail="RAG nao inicializado")
    if request.system not in ("b2", "b3"):
        raise HTTPException(status_code=400, detail="system deve ser 'b2' ou 'b3'")

    PROMPT = (
        "Você é um assistente acadêmico da UNIFESP ICT. Responda APENAS em português "
        "brasileiro usando SOMENTE as informações abaixo. Se não encontrar, diga que "
        "não tem a informação.\n\n"
        "{context}\n\nPergunta: {question}\n\nResposta:"
    )
    prompt = ChatPromptTemplate.from_template(PROMPT)
    chain = prompt | rag.llm | StrOutputParser()

    t0 = time.time()
    try:
        inner = rag._rag  # RAGUnifesp instance (MultiAgentRAG wraps it)
        if request.system == "b2":
            # Só retriever híbrido, sem KG
            docs = inner.retriever.invoke(request.message)
            context = inner._format_docs(docs)
        else:
            # B3: KG + retriever, sem enriquecimento/validação simbólica
            context_parts = []
            if inner.graph_rag:
                use_g, q_type, termo = inner.graph_rag.should_use_graph(request.message)
                if use_g and q_type and termo:
                    kg_resp = inner.graph_rag.query_graph(q_type, termo)
                    if kg_resp:
                        context_parts.append(kg_resp)
            docs = inner.retriever.invoke(request.message)
            context_parts.append(inner._format_docs(docs))
            context = "\n\n".join(context_parts)

        response = chain.invoke({"context": context, "question": request.message})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return BaselineResponse(
        response=response.strip(),
        system=request.system,
        latency_s=round(time.time() - t0, 2),
    )


@app.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str):
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversa nao encontrada")
    
    messages = [
        Message(**msg) for msg in conversations[conversation_id]
    ]
    
    return ConversationResponse(
        conversation_id=conversation_id,
        messages=messages
    )


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversa nao encontrada")
    
    del conversations[conversation_id]
    context_resolver.clear_context(conversation_id)
    return {"message": "Conversa deletada com sucesso"}


@app.post("/conversations")
async def create_conversation():
    conversation_id = str(uuid4())
    conversations[conversation_id] = []
    return {"conversation_id": conversation_id}


@app.get("/status")
async def status():
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG nao inicializado")
    
    counts = rag.list_sources()
    return {
        "rag_ready": rag.chain is not None,
        "sources": counts,
        "active_conversations": len(conversations),
        "total_messages": sum(len(msgs) for msgs in conversations.values())
    }


# ==================== ENDPOINTS DE EXTRAÇÃO DE RELAÇÕES ====================

class ExtractRequest(BaseModel):
    text: str
    min_confidence: float = 0.6


class EnrichRequest(BaseModel):
    text: str
    min_confidence: float = 0.7


@app.post("/extract-relations")
async def extract_relations(request: ExtractRequest):
    """
    Extrai relações de um texto sem adicionar ao grafo.
    Útil para preview antes de enriquecer o Knowledge Graph.
    """
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG não inicializado")
    
    if not rag.relation_extractor:
        raise HTTPException(status_code=503, detail="Extrator de relações não disponível")
    
    try:
        relations = rag.extract_relations(request.text, request.min_confidence)
        return {
            "relations": relations,
            "count": len(relations),
            "text_length": len(request.text)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na extração: {str(e)}")


@app.post("/enrich-graph")
async def enrich_graph(request: EnrichRequest):
    """
    Extrai relações de um texto e adiciona ao Knowledge Graph.
    Requer maior confiança por padrão (0.7).
    """
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG não inicializado")
    
    if not rag.graph_enricher:
        raise HTTPException(status_code=503, detail="Enriquecedor de grafo não disponível")
    
    try:
        stats = rag.enrich_graph_from_text(request.text, request.min_confidence)
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no enriquecimento: {str(e)}")


@app.get("/graph-stats")
async def graph_stats():
    """Retorna estatísticas do Knowledge Graph."""
    if rag is None or not rag.knowledge_graph:
        raise HTTPException(status_code=503, detail="Knowledge Graph não disponível")
    
    stats = rag.knowledge_graph.get_stats()
    
    # Adicionar estatísticas de extração se disponíveis
    if rag.graph_enricher:
        extraction_stats = rag.graph_enricher.get_extraction_stats()
        stats['extracted_relations'] = extraction_stats
    
    return stats


@app.get("/graph")
async def get_graph():
    """Retorna o Knowledge Graph completo para visualização (nodes + edges)."""
    if rag is None or not rag.knowledge_graph:
        raise HTTPException(status_code=503, detail="Knowledge Graph não disponível")
    return rag.knowledge_graph.export_for_visualization()


# ──────────────── Explain endpoint (demo neurosymbolic vs vanilla) ────────────

class ChatExplainRequest(BaseModel):
    message: str
    use_neurosymbolic: bool = True


class ChatExplainResponse(BaseModel):
    response: str
    active_agent: str
    intent: str
    term: str
    use_neurosymbolic: bool
    target_node_id: Optional[str] = None
    base_node_ids: List[str] = []
    inferred_node_ids: List[str] = []
    base_edges: List[Dict] = []
    inferred_edges: List[Dict] = []
    rules_applied: List[str] = []


def _disc_id(kg, nome: str) -> Optional[str]:
    return kg._find_node(nome, "disciplina")


def _compute_highlights(kg, intent: str, term: str) -> Dict:
    """
    Computa nós/arestas que o GraphRAG puro tocaria (base) e os extras
    que o InferenceEngine acrescentaria (inferred), por intent.
    """
    from .neurosymbolic_validator import InferenceEngine, _parse_trajectory_term

    base_nodes: List[str] = []
    inferred_nodes: List[str] = []
    base_edges: List[Dict] = []
    inferred_edges: List[Dict] = []
    rules: List[str] = []
    target_id: Optional[str] = None

    if not term:
        return {
            "target_node_id": None,
            "base_node_ids": [], "inferred_node_ids": [],
            "base_edges": [], "inferred_edges": [], "rules_applied": [],
        }

    engine = InferenceEngine(kg)

    if intent == "prerequisite_chain":
        target_id = _disc_id(kg, term)
        if target_id:
            base_nodes.append(target_id)
            direct = kg.get_prerequisite_chain(term, max_depth=0)
            direct_set = set(direct)
            for d in direct:
                nid = _disc_id(kg, d)
                if nid:
                    base_nodes.append(nid)
                    base_edges.append({"from": nid, "to": target_id, "label": "PREREQUISITO_DE"})

            # Inferred: pré-requisitos transitivos (ancestrais que não são diretos)
            all_anc = kg.get_all_ancestors(term)
            transitive = [a for a in all_anc if a not in direct_set]
            for d in transitive:
                nid = _disc_id(kg, d)
                if nid and nid not in base_nodes:
                    inferred_nodes.append(nid)
                    # adicionar arestas inferidas conectando o transitivo ao seu sucessor
                    for succ_name in kg.get_dependent_disciplines(d):
                        succ_id = _disc_id(kg, succ_name)
                        if succ_id and (succ_id in base_nodes or succ_id in inferred_nodes):
                            inferred_edges.append({
                                "from": nid, "to": succ_id, "label": "PREREQUISITO_DE"
                            })
            if transitive:
                rules.append("prereq_transitivity")

            co = engine.find_co_prerequisites(term)
            for d in co:
                nid = _disc_id(kg, d)
                if nid and nid not in base_nodes and nid not in inferred_nodes:
                    inferred_nodes.append(nid)
            if co:
                rules.append("co_prerequisite")

            critical = dict(engine.critical_disciplines(min_dependents=3))
            for d in direct:
                if d in critical:
                    rules.append("critical_discipline")
                    break

    elif intent == "dependents":
        target_id = _disc_id(kg, term)
        if target_id:
            base_nodes.append(target_id)
            for d in kg.get_dependent_disciplines(term):
                nid = _disc_id(kg, d)
                if nid:
                    base_nodes.append(nid)
                    base_edges.append({"from": target_id, "to": nid, "label": "PREREQUISITO_DE"})

    elif intent == "trajectory_planning":
        # Igual ao graph_rag.py: se o termo inteiro é uma disciplina (mesmo com ":")
        # tratar como target puro; caso contrário parsear "completed:target".
        if _disc_id(kg, term):
            completed, target = [], term
        else:
            completed, target = _parse_trajectory_term(term)
        if target:
            target_id = _disc_id(kg, target)
            if target_id:
                base_nodes.append(target_id)
                # base = pré-requisitos DIRETOS (o que o KG sozinho sabe, 1 hop)
                for d in kg.get_prerequisite_chain(target, max_depth=0):
                    nid = _disc_id(kg, d)
                    if nid:
                        base_nodes.append(nid)
                        base_edges.append({"from": nid, "to": target_id, "label": "PREREQUISITO_DE"})

                # inferred = caminho mínimo completo (todas as fases)
                phases = engine.plan_minimal_path(target, completed) or []
                rules.append("minimal_path")
                for phase in phases:
                    for d in phase:
                        nid = _disc_id(kg, d)
                        if nid and nid not in base_nodes and nid not in inferred_nodes:
                            inferred_nodes.append(nid)
                            # arestas inferidas: do nó até seus dependentes que estão no plano
                            for succ_name in kg.get_dependent_disciplines(d):
                                succ_id = _disc_id(kg, succ_name)
                                if succ_id and (succ_id in base_nodes or succ_id in inferred_nodes):
                                    inferred_edges.append({
                                        "from": nid, "to": succ_id, "label": "PREREQUISITO_DE"
                                    })

                # disciplinas 'completed' também aparecem como base (já cursadas)
                for c in completed:
                    nid = _disc_id(kg, c)
                    if nid and nid not in base_nodes:
                        base_nodes.append(nid)

    elif intent == "discipline_docentes":
        target_id = _disc_id(kg, term)
        if target_id:
            base_nodes.append(target_id)
            for d in kg.get_docentes_of_discipline(term):
                nid = kg._find_node(d, "docente")
                if nid:
                    base_nodes.append(nid)
                    base_edges.append({"from": nid, "to": target_id, "label": "LECIONA"})

    elif intent == "docente_disciplines":
        target_id = kg._find_node(term, "docente")
        if target_id:
            base_nodes.append(target_id)
            for d in kg.get_disciplines_of_docente(term):
                nid = _disc_id(kg, d)
                if nid:
                    base_nodes.append(nid)
                    base_edges.append({"from": target_id, "to": nid, "label": "LECIONA"})

    elif intent == "docente_areas":
        target_id = kg._find_node(term, "docente")
        if target_id:
            base_nodes.append(target_id)
            for a in kg.get_areas_of_docente(term):
                nid = kg._find_node(a, "area")
                if nid:
                    base_nodes.append(nid)
                    base_edges.append({"from": target_id, "to": nid, "label": "ESPECIALISTA_EM"})

    elif intent == "docentes_by_area":
        target_id = kg._find_node(term, "area")
        if target_id:
            base_nodes.append(target_id)
            for d in kg.get_docentes_by_area(term):
                nid = kg._find_node(d, "docente")
                if nid:
                    base_nodes.append(nid)
                    base_edges.append({"from": nid, "to": target_id, "label": "ESPECIALISTA_EM"})

    return {
        "target_node_id": target_id,
        "base_node_ids": list(dict.fromkeys(base_nodes)),
        "inferred_node_ids": list(dict.fromkeys(inferred_nodes)),
        "base_edges": base_edges,
        "inferred_edges": inferred_edges,
        "rules_applied": list(dict.fromkeys(rules)),
    }


@app.post("/chat_explain", response_model=ChatExplainResponse)
async def chat_explain(request: ChatExplainRequest):
    """
    Endpoint de demonstração: roda a query e devolve, além da resposta,
    os nós do KG que o GraphRAG puro tocaria (base) e os extras que o
    reasoner neurossimbólico acrescenta (inferred). Permite visualizar
    no grafo o ganho informacional da camada simbólica.
    """
    if rag is None:
        raise HTTPException(status_code=503, detail="RAG não inicializado")

    try:
        if request.use_neurosymbolic:
            result = rag.query_with_metadata(request.message)
            response_text = result.get("response", "")
            active_agent = result.get("active_agent", "fallback")
            intent = result.get("intent", "unknown")
            term = result.get("term", "")
        else:
            # baseline b3: GraphRAG + retriever, sem enriquecimento/validação simbólica.
            # Reusa a lógica do /chat_baseline mas extrai intent/term via graph_rag.
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import StrOutputParser
            inner = rag._rag
            intent, term = "unknown", ""
            context_parts: List[str] = []
            if inner.graph_rag:
                use_g, q_type, termo = inner.graph_rag.should_use_graph(request.message)
                if use_g and q_type:
                    intent = q_type
                    term = termo or ""
                    if termo:
                        kg_resp = inner.graph_rag.query_graph(q_type, termo)
                        if kg_resp:
                            context_parts.append(kg_resp)
            docs = inner.retriever.invoke(request.message)
            context_parts.append(inner._format_docs(docs))
            context = "\n\n".join(context_parts)
            PROMPT = (
                "Você é um assistente acadêmico da UNIFESP ICT. Responda APENAS em português "
                "brasileiro usando SOMENTE as informações abaixo. Se não encontrar, diga que "
                "não tem a informação.\n\n{context}\n\nPergunta: {question}\n\nResposta:"
            )
            chain = ChatPromptTemplate.from_template(PROMPT) | rag.llm | StrOutputParser()
            response_text = chain.invoke({"context": context, "question": request.message}).strip()
            active_agent = "baseline_b3"
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")

    hl = _compute_highlights(rag.knowledge_graph, intent, term)
    return ChatExplainResponse(
        response=response_text,
        active_agent=active_agent,
        intent=intent,
        term=term,
        use_neurosymbolic=request.use_neurosymbolic,
        **hl,
    )


@app.get("/graph-viewer")
async def graph_viewer_page():
    """Serve a página HTML que visualiza o grafo (mesma origem que /graph, evita CORS)."""
    path = Path(__file__).resolve().parent.parent / "graph_viewer.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="graph_viewer.html não encontrado")
    return FileResponse(path, media_type="text/html")


# ── Planejador de trajetória curricular ───────────────────────────────────────

@app.get("/cursos")
async def listar_cursos():
    """Lista os cursos com matriz curricular (para o seletor do planejador)."""
    if rag is None or rag.knowledge_graph is None:
        raise HTTPException(status_code=503, detail="Knowledge Graph não inicializado")
    cursos = rag.knowledge_graph.get_all_cursos()
    # Apenas o necessário para o front, sem duplicatas por nome.
    vistos = set()
    saida = []
    for c in cursos:
        nome = (c.get("nome") or "").strip()
        if not nome or nome in vistos:
            continue
        vistos.add(nome)
        saida.append({
            "nome": nome,
            "sigla": c.get("sigla", ""),
            "duracao_termos": c.get("duracao_termos", ""),
        })
    return {"cursos": sorted(saida, key=lambda x: x["nome"])}


def _sse(event: str, data: dict) -> str:
    """Formata um evento SSE."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/plan/stream")
async def plan_stream(
    curso: str = Query(..., description="Nome ou sigla do curso"),
    completed: str = Query("", description="Disciplinas já cursadas, separadas por ';'"),
    max_creditos: int = Query(DEFAULT_MAX_CREDITOS, ge=1, le=60),
):
    """
    Transmite (SSE) a montagem da trajetória curricular, evento a evento, para o
    canvas desenhar ao vivo. O plano é calculado pelo módulo simbólico
    `plan_curriculum` (sem LLM, sem alucinação); o streaming apenas dá o ritmo.
    """
    if rag is None or rag.knowledge_graph is None:
        raise HTTPException(status_code=503, detail="Knowledge Graph não inicializado")

    # Aceita ';' (preferido) ou ',' como separador.
    raw = completed.replace(",", ";")
    cursadas = [c.strip() for c in raw.split(";") if c.strip()]

    plan = plan_curriculum(rag.knowledge_graph, curso, cursadas, max_creditos=max_creditos)

    async def gen():
        if plan is None:
            yield _sse("error", {
                "message": f"Não encontrei a matriz curricular de '{curso}'. "
                           "Confira o nome do curso e tente de novo."
            })
            yield _sse("done", {})
            return

        # 1. Metadados gerais.
        yield _sse("meta", {
            "curso": plan["curso"],
            "max_creditos": plan["max_creditos"],
            "total_semestres": plan["total_semestres"],
            "total_disciplinas": plan["total_disciplinas"],
            "total_creditos": plan["total_creditos"],
            "avisos": plan["avisos"],
        })
        await asyncio.sleep(0.3)

        # Mapa de arestas de entrada por disciplina (para desenhar no momento certo).
        incoming = {}
        for e in plan["edges"]:
            incoming.setdefault(e["to"], []).append(e["from"])

        # 2. Disciplinas já cursadas entram primeiro, como base (semestre 0).
        cursadas_nodes = [n for n in plan["nodes"] if n.get("cursada")]
        if cursadas_nodes:
            yield _sse("narration", {
                "text": f"Beleza! Você já tem {len(cursadas_nodes)} disciplina(s) "
                        "no currículo. Vou partir delas. 👇"
            })
            await asyncio.sleep(0.4)
            for n in cursadas_nodes:
                yield _sse("node_added", n)
                await asyncio.sleep(0.08)

        # 3. Semestre a semestre.
        for s in plan["semestres"]:
            nomes = ", ".join(d["nome"] for d in s["disciplinas"])
            yield _sse("narration", {
                "text": f"**Semestre {s['numero']}** ({s['creditos']} créditos): {nomes}."
            })
            await asyncio.sleep(0.5)
            for d in s["disciplinas"]:
                node = {
                    "id": d["nome"],
                    "label": d["nome"],
                    "semestre": s["numero"],
                    "creditos": d["creditos"],
                    "cursada": False,
                }
                yield _sse("node_added", node)
                await asyncio.sleep(0.22)
                for origem in incoming.get(d["nome"], []):
                    yield _sse("edge_added", {"from": origem, "to": d["nome"]})
                    await asyncio.sleep(0.08)
            yield _sse("phase_done", {"semestre": s["numero"], "creditos": s["creditos"]})
            await asyncio.sleep(0.25)

        # 4. Avisos (se houver) e encerramento.
        for aviso in plan["avisos"]:
            yield _sse("narration", {"text": f"⚠️ {aviso}"})
            await asyncio.sleep(0.3)

        yield _sse("narration", {
            "text": f"Pronto! 🎉 Sua trajetória ficou em **{plan['total_semestres']} "
                    f"semestre(s)**, somando {plan['total_disciplinas']} disciplinas "
                    f"e {plan['total_creditos']} créditos."
        })
        yield _sse("done", {
            "total_semestres": plan["total_semestres"],
            "total_disciplinas": plan["total_disciplinas"],
            "total_creditos": plan["total_creditos"],
        })

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.get("/planner")
async def planner_page():
    """Serve a página HTML do planejador de trajetória (canvas ao vivo)."""
    path = Path(__file__).resolve().parent.parent / "planner.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="planner.html não encontrado")
    return FileResponse(path, media_type="text/html")


@app.get("/noticias")
async def noticias(limit: int = Query(8, ge=1, le=20), force: bool = False):
    """Retorna as últimas notícias oficiais da UNIFESP SJC (retrieval ao vivo)."""
    from .news_fetcher import fetch_news, NEWS_URL
    itens = fetch_news(limit=limit, force=force)
    return {"fonte": NEWS_URL, "total": len(itens), "noticias": itens}


@app.post("/crawl-sjc")
async def crawl_sjc_endpoint(max_pages: int = Query(400, ge=10, le=1000)):
    """
    (Re)rastreia o site do campus SJC e atualiza o corpus do agente Web SJC.
    Operação custosa: pode levar alguns minutos. Pensado para rodar sob demanda
    ou via agendamento.
    """
    from .site_crawler import crawl_sjc
    pages = crawl_sjc(max_pages=max_pages)
    # O agente Web SJC recarrega o corpus automaticamente ao detectar o cache novo.
    return {"paginas_rastreadas": len(pages)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

