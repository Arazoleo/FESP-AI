"""
LangGraph pipeline para o sistema multi-agente FESP-AI.

Fluxo:
  router_node → [disciplinas | docentes | cursos | regimentos | fallback] → END
"""

import os
import re
import unicodedata


def _refere_proprias_ucs(texto: str) -> bool:
    return bool(re.search(
        r"\b(?:que\s+)?estou\s+(?:cursando|fazendo)\b"
        r"|\bminhas\s+disciplinas\b|\bdas\s+disciplinas\s+que\b",
        _fold_router(texto),
    ))


def _fold_router(texto: str) -> str:
    baixo = (texto or "").lower()
    return "".join(
        c for c in unicodedata.normalize("NFD", baixo)
        if unicodedata.category(c) != "Mn"
    )
from collections import Counter
from typing import Any
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .state import AgentState
from .router import (
    route_intent,
    phrase_override,
    llm_route,
    term_from_llm_route,
    get_meta_capability_response,
    is_conversational,
    is_montar_grade,
    is_noticias,
    is_web_sjc,
    is_course_overview,
    is_regimento_domain,
    SYMBOLIC_DIRECT_INTENTS,
    AGENTIC_INTENTS,
)
from ..telemetry import incr as telemetry_incr

_TERM_OPTIONAL_INTENTS: frozenset = frozenset({"listar_cursos", "critical_disciplines"})
from .embedding_router import EmbeddingAgentRouter
from ..agents.disciplinas_agent import DisciplinasAgent
from ..agents.docentes_agent import DocentesAgent
from ..agents.cursos_agent import CursosAgent
from ..agents.regimentos_agent import RegimentosAgent
from ..agents.conversa_agent import ConversaAgent
from ..agents.montar_grade_agent import MontarGradeAgent
from ..agents.noticias_agent import NoticiasAgent
from ..agents.web_sjc_agent import WebSjcAgent


_KG_HUMANIZER_TEMPLATE = """Voce e o assistente virtual da UNIFESP ICT, simpatico e acolhedor. Abaixo esta uma RESPOSTA JA VERIFICADA, extraida diretamente da base de dados oficial. Ela esta correta e completa.

Pergunta do aluno: {question}

Resposta verificada:
{kg_response}

Sua tarefa: reescrever essa resposta num tom mais conversacional, caloroso e natural, como um chatbot amigavel conversando com um aluno.

REGRAS INVIOLAVEIS:
- NAO altere, remova, adicione ou invente NENHUM fato: nomes, codigos, numeros, disciplinas, professores, artigos e listas devem permanecer IDENTICOS em conteudo.
- Mantenha TODOS os itens de qualquer lista, na mesma ordem.
- Voce so pode mudar a FORMA: uma abertura amigavel, conectar as frases de modo natural e, se fizer sentido, uma frase final se colocando a disposicao.
- Responda em PORTUGUES BRASILEIRO, de forma breve. NAO use emojis.
- Nao comente estas instrucoes nem mencione "base de dados" ou "Knowledge Graph".

Resposta conversacional:"""


def _kg_facts_preserved(original: str, humanized: str) -> bool:
    """
    Guard barato de pós-verificação do humanizer: True se a saída preservou os
    fatos da resposta original do KG. O LLM ocasionalmente mutila a resposta
    (ex.: "O cursoisciplinas obrigatórias" - perda de um trecho no decoding).

    Critérios (perda > 10% → descarta):
      - dígitos: >= 90% dos tokens numéricos da original (multiset) presentes;
      - listas: com 3+ itens na original, >= 90% dos itens com o CONTEÚDO
        presente na saída (o humanizer pode converter bullets em prosa - o que
        conta é o conteúdo do item, não o marcador).
    """
    if not humanized or not humanized.strip():
        return False
    orig_nums = re.findall(r"\d+", original)
    if orig_nums:
        hum_counts = Counter(re.findall(r"\d+", humanized))
        kept = sum(
            min(count, hum_counts.get(num, 0))
            for num, count in Counter(orig_nums).items()
        )
        if kept < 0.9 * len(orig_nums):
            return False
    orig_items = re.findall(r"^\s*(?:[-•*]|\d+[.)])\s+(.+)$", original, re.MULTILINE)
    if len(orig_items) >= 3:
        hum_lower = humanized.lower()
        items_ok = 0
        for item in orig_items:
            tokens = re.findall(r"[^\W\d_]{4,}", item, re.UNICODE)
            if not tokens:
                items_ok += 1
                continue
            present = sum(1 for t in tokens if t.lower() in hum_lower)
            if present >= 0.6 * len(tokens):
                items_ok += 1
        if items_ok < 0.9 * len(orig_items):
            return False
    return True


def humanize_kg_response(llm, question: str, kg_response: str, history: str = "") -> str:
    """
    Suaviza o tom de uma resposta determinística do KG via LLM, preservando os
    fatos. Em caso de erro, retorna a resposta original (degradação segura).
    Só deve ser chamada quando Config.HUMANIZE_KG está ativo.

    `history`: trocas anteriores - evita re-saudação ("Olá!") a cada turno.
    """
    if not llm or not kg_response or not kg_response.strip():
        return kg_response
    try:
        template = _KG_HUMANIZER_TEMPLATE
        inputs = {"question": question, "kg_response": kg_response}
        if history:
            template = template.replace(
                "Pergunta do aluno: {question}",
                "HISTORICO RECENTE DA CONVERSA:\n{history}\n\n"
                "A conversa JA ESTA EM ANDAMENTO: NAO cumprimente de novo "
                "(nada de 'Ola', 'Oi'); emende direto no assunto.\n\n"
                "Pergunta do aluno: {question}",
                1,
            )
            inputs["history"] = history
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | llm | StrOutputParser()
        softened = chain.invoke(inputs).strip()
        if not _kg_facts_preserved(kg_response, softened):
            return kg_response
        return softened
    except Exception:
        return kg_response


def build_pipeline(rag_instance):
    """
    Constrói e compila o LangGraph com os agentes especializados.

    Args:
        rag_instance: instância de RAGUnifesp já inicializada (sync() chamado)

    Returns:
        Compiled LangGraph app
    """
    agents = {
        "disciplinas": DisciplinasAgent(rag_instance),
        "docentes": DocentesAgent(rag_instance),
        "cursos": CursosAgent(rag_instance),
        "regimentos": RegimentosAgent(rag_instance),
        "conversa": ConversaAgent(rag_instance),
        "montar_grade": MontarGradeAgent(rag_instance),
        "noticias": NoticiasAgent(rag_instance),
        "web_sjc": WebSjcAgent(rag_instance),
    }

    embedding_router = None
    if getattr(rag_instance, "_rag", None) and getattr(rag_instance._rag, "embeddings", None):
        embedding_router = EmbeddingAgentRouter(rag_instance._rag.embeddings, confidence_threshold=0.58)
        embedding_router.initialize()

    def router_node(state: AgentState) -> AgentState:
        """Classifica a intent e decide qual agente chamar."""
        question = state.get("enhanced_question") or state.get("question", "")
        question_lower = question.lower()

        forced = state.get("forced_agent")
        if forced and (forced in agents or forced == "fallback"):
            return {**state, "active_agent": forced}

        meta_response = get_meta_capability_response(question_lower)
        if meta_response:
            return {
                **state,
                "response": meta_response,
                "active_agent": "meta",
            }

        from ..atividades_complementares import (
            is_ac_question,
            is_breakdown_request,
            build_breakdown_response,
        )
        from ..ac_auditor import (
            is_audit_request,
            responder_auditoria,
            parsear_atividades,
            auditar_atividades,
            formatar_auditoria,
            payload_auditoria,
            is_checklist_request,
            responder_checklist,
            registrar_atividades,
            is_reset_ac,
        )
        from ..progresso import (
            is_progresso_request,
            is_matricula_request,
            extrair_cursadas,
            extrair_desejadas,
            auditar_progresso,
            formatar_progresso,
            verificar_matricula,
            formatar_matricula,
            is_requisitos_request,
            extrair_curso_requisitos,
            responder_requisitos,
            is_pergunta_comparativa,
        )
        from ..risco import (
            extrair_disciplina_risco,
            analisar_reprovacao,
            formatar_risco,
        )
        from ..trilhas import is_trilha_request, montar_trilha, formatar_trilha
        from ..oferta import extrair_disciplina_oferta, responder_oferta
        from ..interdisciplinares import (
            is_lista_interdisciplinares,
            extrair_disciplina_check,
            responder_lista,
            responder_check,
        )
        from ..historico import (
            is_cr_request,
            responder_cr,
            is_cursando_decl,
            responder_cursando,
            aprovadas as historico_aprovadas,
            curso_sigla as historico_curso_sigla,
            extrair_disciplina_cursei,
            responder_cursei,
            is_cursadas_decl,
            responder_cursadas_decl,
            registrar_cursadas_declaradas,
            cursadas_da_sessao,
        )

        def _resposta_simbolica(texto_resposta, intent_label, fontes, **extras):
            telemetry_incr(f"agentic_{intent_label}")
            return {
                **state,
                "response": texto_resposta,
                "intent": intent_label,
                "term": "",
                "confidence": 1.0,
                "active_agent": "symbolic_kg",
                "context": texto_resposta,
                "sources": fontes,
                **extras,
            }

        pergunta_bruta = state.get("question_original") or state.get("question") or question

        def _agentico(label: str, disciplina_hint: str = None):
            hist = state.get("historico")

            if label == "cr_consulta":
                return _resposta_simbolica(
                    responder_cr(hist, pergunta_bruta, rag_instance.knowledge_graph),
                    "cr_consulta",
                    ["Histórico Acadêmico (sessão)"] if hist else [],
                )

            if label == "progresso":
                cursadas = extrair_cursadas(pergunta_bruta)
                if hist is not None:
                    registrar_cursadas_declaradas(
                        hist, cursadas, rag_instance.knowledge_graph
                    )
                    da_sessao = cursadas_da_sessao(hist)
                    if da_sessao:
                        cursadas = da_sessao
                curso = None
                if rag_instance.graph_rag:
                    try:
                        curso = rag_instance.graph_rag._find_curso_in_text(pergunta_bruta)
                    except Exception:
                        curso = None
                if not curso and hist:
                    curso = historico_curso_sigla(hist.get("curso", "")) or None
                itens_ac = parsear_atividades(pergunta_bruta)
                if itens_ac:
                    itens_ac = registrar_atividades(hist, itens_ac)
                bloco_ac = ""
                extras_ac = {}
                if itens_ac:
                    resultado_ac = auditar_atividades(itens_ac)
                    bloco_ac = formatar_auditoria(resultado_ac) + "\n\n---\n\n"
                    extras_ac = {"ac_data": payload_auditoria(resultado_ac)}
                if cursadas and curso:
                    resultado = auditar_progresso(
                        rag_instance.knowledge_graph, curso, cursadas,
                        historico=hist,
                    )
                    if resultado:
                        chips = {
                            "type": "discipline_list",
                            "title": "Liberadas para você agora",
                            "items": [
                                {"nome": d["nome"], "hint": f"termo {d['termo']}"}
                                for d in resultado["disponiveis"][:16]
                            ],
                        }
                        return _resposta_simbolica(
                            bloco_ac + formatar_progresso(resultado), "progresso",
                            ["Knowledge Graph"],
                            list_data=chips if chips["items"] else None,
                            **extras_ac,
                        )
                return _resposta_simbolica(
                    bloco_ac
                    + "Sobre as disciplinas: posso auditar seu progresso! Me diga "
                    "o **curso** e liste o que você **já cursou**, por exemplo: "
                    "*Sou do BCC e já cursei Lógica de Programação, Cálculo em Uma "
                    "Variável e Álgebra Linear. Quanto falta para me formar?* Eu "
                    "cruzo com a matriz, aponto o que está liberado, o que está "
                    "bloqueado por pré-requisito e o mínimo de semestres restantes.",
                    "progresso",
                    ["Knowledge Graph"] if not itens_ac else
                    ["Regulamento de AC do BCT (2023)", "Knowledge Graph"],
                    **extras_ac,
                )

            if label == "ac_auditoria":
                itens_novos = parsear_atividades(pergunta_bruta)
                itens_ac = registrar_atividades(
                    hist, itens_novos, reset=is_reset_ac(pergunta_bruta)
                )
                curso_ac = "BCT"
                q_fold = _fold_router(pergunta_bruta)
                if re.search(r"\bbbt\b|biotec", q_fold):
                    curso_ac = "BBT"
                elif re.search(r"\beb\b|biomedica", q_fold):
                    curso_ac = "EB"
                elif re.search(r"engenharia de materiais", q_fold):
                    curso_ac = "EM"
                elif re.search(r"\bbmc\b|matematica computacional", q_fold):
                    curso_ac = "BMC"
                elif re.search(r"\bbcc\b|ciencia da computacao", q_fold):
                    curso_ac = "BCC"
                elif hist and hist.get("curso"):
                    curso_ac = historico_curso_sigla(hist["curso"]) or "BCT"
                if curso_ac not in ("BCT", "BBT", "EB", "EM", "BMC", "BCC"):
                    curso_ac = "BCT"
                fontes_ac = {
                    "BBT": ["Regulamento de AC do BBT (Anexo F do PPC 2023)"],
                    "EB": ["Regulamento de AACC da EB (PPC 2023)"],
                    "EM": ["Regulamento de AACC do EM (2023)"],
                    "BMC": ["Regimento de AACC do BMC"],
                    "BCC": ["PPC do BCC"],
                }.get(curso_ac, ["Regulamento de AC do BCT (2023)", "Manual da DAE (2025)"])
                if itens_ac:
                    resultado_ac = auditar_atividades(itens_ac, curso=curso_ac)
                    texto_ac = formatar_auditoria(resultado_ac)
                    payload_ok = resultado_ac.get("usa_eixos", True)
                    if len(itens_ac) > len(itens_novos):
                        texto_ac += (
                            "\n\n*Somei com o que você já tinha declarado nesta "
                            "conversa. Para recomeçar do zero, diga \"zera minhas "
                            "atividades\".*"
                        )
                    return _resposta_simbolica(
                        texto_ac, "ac_auditoria", fontes_ac,
                        ac_data=payload_auditoria(resultado_ac) if payload_ok else None,
                    )
                return _resposta_simbolica(
                    responder_auditoria(pergunta_bruta), "ac_auditoria", fontes_ac,
                )

            if label == "ac_checklist":
                return _resposta_simbolica(
                    responder_checklist(), "ac_checklist",
                    ["Manual de Atividades Complementares da DAE (2025)"],
                )

            if label == "matricula_check":
                desejadas = extrair_desejadas(pergunta_bruta)
                cursadas = extrair_cursadas(pergunta_bruta)
                if hist is not None:
                    registrar_cursadas_declaradas(
                        hist, cursadas, rag_instance.knowledge_graph
                    )
                    da_sessao = cursadas_da_sessao(hist)
                    if da_sessao:
                        cursadas = da_sessao
                if desejadas and cursadas:
                    resultado = verificar_matricula(
                        rag_instance.knowledge_graph, desejadas, cursadas
                    )
                    return _resposta_simbolica(
                        formatar_matricula(resultado), "matricula_check",
                        ["Knowledge Graph", "Regimento Interno da Prograd (2014)"],
                    )
                return _resposta_simbolica(
                    "Posso pré-verificar sua inscrição! Me diga as UCs que quer "
                    "pedir e o que já cursou, por exemplo: *Posso me matricular em "
                    "Compiladores e Redes de Computadores tendo cursado Linguagens "
                    "Formais e Autômatos e AED I?* Eu confiro pré-requisitos e UC "
                    "repetida, e explico a ordem de prioridade das vagas.",
                    "matricula_check", [],
                )

            if label == "risco_reprovacao":
                alvo = extrair_disciplina_risco(pergunta_bruta) or disciplina_hint
                if not alvo:
                    return None
                resultado = analisar_reprovacao(rag_instance.knowledge_graph, alvo)
                if not resultado:
                    return None
                cascata = None
                if rag_instance.graph_rag and resultado["diretos"]:
                    try:
                        cascata = rag_instance.graph_rag.graph_payload(
                            "dependents", resultado["nome"]
                        )
                    except Exception:
                        cascata = None
                return _resposta_simbolica(
                    formatar_risco(resultado), "risco_reprovacao",
                    ["Knowledge Graph"],
                    graph_data=cascata,
                )

            if label == "requisitos_curso":
                if is_pergunta_comparativa(pergunta_bruta):
                    return None
                sigla = extrair_curso_requisitos(pergunta_bruta)
                curso_texto = ""
                if not sigla and hist:
                    curso_texto = hist.get("curso", "")
                    from ..historico import curso_sigla as _cs
                    sigla = _cs(curso_texto)
                if not sigla:
                    return None
                resposta = responder_requisitos(sigla, curso_texto or pergunta_bruta)
                if not resposta:
                    return None
                return _resposta_simbolica(
                    resposta, "requisitos_curso",
                    ["Matrizes Curriculares oficiais (SIIU/Prograd)"],
                )

            if label == "oferta_check":
                alvo = extrair_disciplina_oferta(pergunta_bruta) or disciplina_hint
                if not alvo:
                    return None
                resposta = responder_oferta(rag_instance.knowledge_graph, alvo)
                if not resposta:
                    return None
                return _resposta_simbolica(
                    resposta, "oferta_check",
                    ["Knowledge Graph (matriz curricular)"],
                )

            if label == "trilha":
                if hist is not None and _refere_proprias_ucs(pergunta_bruta):
                    return None
                resultado = montar_trilha(rag_instance.knowledge_graph, pergunta_bruta)
                if not resultado:
                    return None
                cursadas_set = set()
                if hist is not None:
                    kg_norm = rag_instance.knowledge_graph._normalize_text
                    cursadas_set = {kg_norm(n) for n in cursadas_da_sessao(hist)}

                def _hint_trilha(d):
                    if cursadas_set and rag_instance.knowledge_graph._normalize_text(
                        d["nome"]
                    ) in cursadas_set:
                        return "você já cursou ✓"
                    if d["eletiva"]:
                        return "eletiva"
                    return f"termo {d['termo']}" if d["termo"] is not None else None

                chips = {
                    "type": "discipline_list",
                    "title": f"Trilha: {', '.join(resultado['conceitos'])}",
                    "items": [
                        {"nome": d["nome"], "hint": _hint_trilha(d)}
                        for d in resultado["disciplinas"][:16]
                    ],
                }
                return _resposta_simbolica(
                    formatar_trilha(resultado), "trilha",
                    ["Knowledge Graph (camada de conceitos)"],
                    list_data=chips,
                )
            return None

        hist_sessao = state.get("historico")
        if hist_sessao is not None and is_cursadas_decl(pergunta_bruta):
            return _resposta_simbolica(
                responder_cursadas_decl(
                    hist_sessao, pergunta_bruta, rag_instance.knowledge_graph
                ),
                "cursadas_decl",
                ["Sessão da conversa"],
            )
        if hist_sessao is not None and hist_sessao.get("disciplinas"):
            alvo_cursei = extrair_disciplina_cursei(pergunta_bruta)
            if alvo_cursei:
                resposta_cursei = responder_cursei(
                    hist_sessao, alvo_cursei, rag_instance.knowledge_graph
                )
                if resposta_cursei:
                    return _resposta_simbolica(
                        resposta_cursei, "historico_cursei",
                        ["Histórico Acadêmico (sessão)"],
                    )
        if (
            hist_sessao is not None
            and not is_cr_request(pergunta_bruta)
            and is_cursando_decl(pergunta_bruta)
        ):
            return _resposta_simbolica(
                responder_cursando(
                    hist_sessao, pergunta_bruta, rag_instance.knowledge_graph
                ),
                "cursando_decl",
                ["Sessão da conversa"],
            )

        fast_label = None
        if is_cr_request(question):
            fast_label = "cr_consulta"
        elif is_progresso_request(question):
            fast_label = "progresso"
        elif is_audit_request(question):
            fast_label = "ac_auditoria"
        elif is_checklist_request(question):
            fast_label = "ac_checklist"
        elif is_matricula_request(question):
            fast_label = "matricula_check"
        elif extrair_disciplina_risco(pergunta_bruta):
            fast_label = "risco_reprovacao"
        elif extrair_disciplina_oferta(pergunta_bruta):
            fast_label = "oferta_check"
        elif is_requisitos_request(pergunta_bruta):
            fast_label = "requisitos_curso"
        elif is_trilha_request(question) and not (
            hist_sessao is not None and _refere_proprias_ucs(pergunta_bruta)
        ):
            fast_label = "trilha"
        if fast_label:
            resposta_agentica = _agentico(fast_label)
            if resposta_agentica:
                return resposta_agentica

        disciplina_check = extrair_disciplina_check(question)
        if disciplina_check:
            resposta_check = responder_check(
                rag_instance.knowledge_graph, disciplina_check
            )
            if resposta_check:
                return _resposta_simbolica(
                    resposta_check, "interdisciplinar_check",
                    ["Lista de UCs Eletivas Interdisciplinares (PPC 2023)"],
                )

        if is_lista_interdisciplinares(question):
            resultado_inter = responder_lista(rag_instance.knowledge_graph)
            if resultado_inter:
                return _resposta_simbolica(
                    resultado_inter["texto"], "interdisciplinares_lista",
                    ["Lista de UCs Eletivas Interdisciplinares (PPC 2023)"],
                    list_data=resultado_inter["chips"],
                )
        if is_breakdown_request(question):
            ac_response = build_breakdown_response()
            if ac_response:
                telemetry_incr("ac_breakdown_direct")
                return {
                    **state,
                    "response": ac_response,
                    "intent": "ac_breakdown",
                    "term": "",
                    "confidence": 1.0,
                    "active_agent": "symbolic_kg",
                    "context": ac_response,
                    "sources": ["Regulamento de Atividades Complementares do BCT (2023)"],
                }

        if is_ac_question(question):
            telemetry_incr("ac_routed_regimentos")
            return {
                **state,
                "intent": "faqs",
                "term": "",
                "confidence": 0.95,
                "active_agent": "regimentos",
            }

        if is_regimento_domain(question_lower):
            telemetry_incr("regimento_domain_direct")
            return {
                **state,
                "intent": "faqs",
                "term": "",
                "confidence": 0.9,
                "active_agent": "regimentos",
            }

        if is_conversational(question_lower):
            return {
                **state,
                "intent": "conversa",
                "term": "",
                "confidence": 1.0,
                "active_agent": "conversa",
            }

        if is_montar_grade(question_lower):
            return {
                **state,
                "intent": "plan_curriculum",
                "term": "",
                "confidence": 1.0,
                "active_agent": "montar_grade",
            }

        if is_noticias(question_lower):
            return {
                **state,
                "intent": "noticias",
                "term": "",
                "confidence": 1.0,
                "active_agent": "noticias",
            }

        if is_web_sjc(question_lower):
            return {
                **state,
                "intent": "web_sjc",
                "term": "",
                "confidence": 1.0,
                "active_agent": "web_sjc",
            }

        if is_course_overview(question_lower, rag_instance.knowledge_graph):
            return {
                **state,
                "intent": "web_sjc",
                "term": "",
                "confidence": 0.9,
                "active_agent": "web_sjc",
            }

        intent = "unknown"
        term = ""
        confidence = 0.0
        active_agent = ""

        detected_intent, detected_term = "", ""
        if rag_instance.graph_rag:
            use_graph, di, dt = rag_instance.graph_rag.should_use_graph(question)
            if use_graph and di:
                detected_intent, detected_term = di, dt or ""
                if (
                    (detected_term or detected_intent in _TERM_OPTIONAL_INTENTS)
                    and detected_intent in SYMBOLIC_DIRECT_INTENTS
                ):
                    kg_response = rag_instance.graph_rag.query_graph(
                        detected_intent, detected_term
                    )
                    if kg_response:
                        graph_data = None
                        if detected_intent in (
                            "prerequisite_chain", "dependents",
                            "trajectory_planning", "recommended_before",
                        ):
                            try:
                                graph_data = rag_instance.graph_rag.graph_payload(
                                    detected_intent, detected_term
                                )
                            except Exception:
                                graph_data = None
                        list_data = None
                        if detected_intent in ("eletivas_curso", "disciplinas_termo"):
                            list_data = rag_instance.graph_rag.list_payload(
                                detected_intent, detected_term
                            )
                        response_text = kg_response
                        if getattr(rag_instance.config, "HUMANIZE_KG", False):
                            response_text = humanize_kg_response(
                                rag_instance.llm, question, kg_response,
                                history=state.get("history", ""),
                            )
                        return {
                            **state,
                            "response": response_text,
                            "intent": detected_intent,
                            "term": detected_term,
                            "confidence": 1.0,
                            "active_agent": "symbolic_kg",
                            "context": kg_response,
                            "sources": ["Knowledge Graph"],
                            "graph_data": graph_data,
                            "list_data": list_data,
                        }

        emb_agent, emb_conf = "", 0.0
        if embedding_router:
            emb_agent, emb_conf = embedding_router.route(question)

        override = phrase_override(question_lower, emb_agent)
        if override:
            active_agent = override
            confidence = max(emb_conf, 0.9)
        else:
            routed_llm = None
            if os.getenv("FESPAI_LLM_ROUTE", "1") != "0":
                routed_llm = llm_route(
                    question,
                    state.get("history", ""),
                    rag_instance.knowledge_graph,
                    rag_instance.llm,
                    telemetry_incr=telemetry_incr,
                )
            if routed_llm:
                if routed_llm.get("intent") in AGENTIC_INTENTS:
                    resposta_agentica = _agentico(
                        routed_llm["intent"],
                        disciplina_hint=routed_llm.get("entidades", {}).get("disciplina"),
                    )
                    if resposta_agentica:
                        telemetry_incr("agentic_via_llm_route")
                        return resposta_agentica
                active_agent = routed_llm["agente"]
                confidence = 0.85
                if routed_llm.get("intent"):
                    intent = routed_llm["intent"]
                term = term_from_llm_route(routed_llm)
                telemetry_incr("llm_route_decisor")
            elif emb_agent:
                active_agent = emb_agent
                confidence = emb_conf
                telemetry_incr("llm_route_fallback_embedding")

        if detected_intent and intent == "unknown":
            intent = detected_intent
        if detected_term and not term:
            term = detected_term
        if not active_agent:
            active_agent = route_intent(intent, question_lower)

        return {
            **state,
            "intent": intent,
            "term": term,
            "confidence": confidence,
            "active_agent": active_agent,
        }

    def _ctx_aluno(state: AgentState) -> str:
        from ..historico import contexto_para_prompt
        pergunta = (
            state.get("question_original") or state.get("question") or ""
        )
        return contexto_para_prompt(
            state.get("historico"),
            kg=rag_instance.knowledge_graph,
            incluir_ementas=_refere_proprias_ucs(pergunta),
        )

    def disciplinas_node(state: AgentState) -> AgentState:
        question = state.get("enhanced_question") or state.get("question", "")
        result = agents["disciplinas"].answer(
            question, state.get("intent", ""), state.get("term", ""),
            history=state.get("history", ""),
            student_context=_ctx_aluno(state),
        )
        return {
            **state,
            "response": result["response"],
            "active_agent": "disciplinas",
            "context": result.get("context", ""),
            "sources": result.get("sources", []),
        }

    def docentes_node(state: AgentState) -> AgentState:
        question = state.get("enhanced_question") or state.get("question", "")
        result = agents["docentes"].answer(
            question, state.get("intent", ""), state.get("term", ""),
            history=state.get("history", ""),
            student_context=_ctx_aluno(state),
        )
        return {
            **state,
            "response": result["response"],
            "active_agent": "docentes",
            "context": result.get("context", ""),
            "sources": result.get("sources", []),
        }

    def cursos_node(state: AgentState) -> AgentState:
        question = state.get("enhanced_question") or state.get("question", "")
        result = agents["cursos"].answer(
            question, state.get("intent", ""), state.get("term", ""),
            history=state.get("history", ""),
            student_context=_ctx_aluno(state),
        )
        return {
            **state,
            "response": result["response"],
            "active_agent": "cursos",
            "context": result.get("context", ""),
            "sources": result.get("sources", []),
        }

    def regimentos_node(state: AgentState) -> AgentState:
        question = state.get("enhanced_question") or state.get("question", "")
        result = agents["regimentos"].answer(
            question, state.get("intent", ""), state.get("term", ""),
            history=state.get("history", ""),
            student_context=_ctx_aluno(state),
        )
        return {
            **state,
            "response": result["response"],
            "active_agent": "regimentos",
            "context": result.get("context", ""),
            "sources": result.get("sources", []),
        }

    def conversa_node(state: AgentState) -> AgentState:
        question = state.get("question", "")
        result = agents["conversa"].answer(
            question, "", "", history=state.get("history", ""),
            student_context=_ctx_aluno(state),
        )
        return {
            **state,
            "response": result["response"],
            "active_agent": "conversa",
            "context": "",
            "sources": [],
        }

    def montar_grade_node(state: AgentState) -> AgentState:
        question = state.get("enhanced_question") or state.get("question", "")
        result = agents["montar_grade"].answer(question, state.get("intent", ""), "", history=state.get("history", ""))
        return {
            **state,
            "response": result["response"],
            "active_agent": "montar_grade",
            "context": "",
            "sources": [],
            "plan_request": result.get("plan_request"),
        }

    def noticias_node(state: AgentState) -> AgentState:
        question = state.get("enhanced_question") or state.get("question", "")
        result = agents["noticias"].answer(question, state.get("intent", ""), "", history=state.get("history", ""))
        return {
            **state,
            "response": result["response"],
            "active_agent": "noticias",
            "context": result.get("context", ""),
            "sources": result.get("sources", []),
        }

    def web_sjc_node(state: AgentState) -> AgentState:
        question = state.get("enhanced_question") or state.get("question", "")
        result = agents["web_sjc"].answer(
            question, state.get("intent", ""), "", history=state.get("history", ""),
            student_context=_ctx_aluno(state),
        )
        return {
            **state,
            "response": result["response"],
            "active_agent": "web_sjc",
            "context": result.get("context", ""),
            "sources": result.get("sources", []),
        }

    def fallback_node(state: AgentState) -> AgentState:
        """
        Fallback para perguntas não classificadas. Com FESPAI_DEBATE=1
        (padrão), vira um debate: o agente do site e o RAG geral respondem e o
        juiz simbólico (claims verificados no KG) escolhe a melhor resposta.
        """
        question = state.get("enhanced_question") or state.get("question", "")

        if os.getenv("FESPAI_DEBATE", "1") != "0" and "web_sjc" in agents:
            from .debate import debater

            validador = getattr(agents.get("web_sjc"), "validator", None)

            def validar(resposta: str):
                if not validador:
                    return {}
                laudo = validador.validate_response(resposta, "unknown", "")
                return {
                    "fatos_verificados": laudo.verified_facts,
                    "violacoes": laudo.violations,
                }

            def responder_site():
                return agents["web_sjc"].answer(
                    question, state.get("intent", ""), "",
                    history=state.get("history", ""),
                )

            def responder_rag():
                return {"response": rag_instance.query(question)}

            vencedor = debater(
                question,
                [
                    {"agente": "web_sjc", "responder": responder_site},
                    {"agente": "rag_geral", "responder": responder_rag},
                ],
                validar=validar,
                telemetry_incr=telemetry_incr,
            )
            if vencedor.get("response"):
                agente_final = (
                    "web_sjc" if vencedor.get("agente") == "web_sjc" else "fallback"
                )
                return {
                    **state,
                    "response": vencedor["response"],
                    "active_agent": agente_final,
                    "sources": vencedor.get("sources", []),
                    "context": vencedor.get("context", ""),
                }

        try:
            response = rag_instance.query(question)
        except Exception as e:
            response = f"Desculpe, não consegui processar sua pergunta: {e}"
        return {**state, "response": response, "active_agent": "fallback"}

    def meta_node(state: AgentState) -> AgentState:
        return state

    def symbolic_kg_node(state: AgentState) -> AgentState:
        """
        Nó neurossimbólico: a resposta já foi gerada diretamente pelo KG
        no router_node. Este nó é um pass-through para o END.
        Elimina latência de LLM e alucinações para consultas estruturais.
        """
        return state

    def select_agent(state: AgentState) -> str:
        agent = state.get("active_agent", "fallback")
        if agent in ("meta", "symbolic_kg"):
            return agent
        if agent in agents:
            return agent
        return "fallback"

    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("disciplinas", disciplinas_node)
    graph.add_node("docentes", docentes_node)
    graph.add_node("cursos", cursos_node)
    graph.add_node("regimentos", regimentos_node)
    graph.add_node("conversa", conversa_node)
    graph.add_node("montar_grade", montar_grade_node)
    graph.add_node("noticias", noticias_node)
    graph.add_node("web_sjc", web_sjc_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("meta", meta_node)
    graph.add_node("symbolic_kg", symbolic_kg_node)

    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        select_agent,
        {
            "disciplinas": "disciplinas",
            "docentes": "docentes",
            "cursos": "cursos",
            "regimentos": "regimentos",
            "conversa": "conversa",
            "montar_grade": "montar_grade",
            "noticias": "noticias",
            "web_sjc": "web_sjc",
            "fallback": "fallback",
            "meta": "meta",
            "symbolic_kg": "symbolic_kg",
        },
    )

    for agent_name in ["disciplinas", "docentes", "cursos", "regimentos", "conversa", "montar_grade", "noticias", "web_sjc", "fallback", "meta", "symbolic_kg"]:
        graph.add_edge(agent_name, END)

    return graph.compile()
