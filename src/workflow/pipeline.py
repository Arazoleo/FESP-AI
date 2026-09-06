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


def _disciplinas_por_area(pergunta: str, kg) -> "Optional[tuple]":
    """
    Detecta 'disciplinas da ÁREA de X' e aterra X num nó de área do KG, usando a
    ponte APRENDIDA conceito→área. Âncora robusta: a palavra 'área' (a intenção
    de área de pesquisa) + grounding do termo num nó AREA com resultado. Precede
    a oferta no roteamento (que senão captura o nome de disciplina homônimo).
    Retorna (area_termo, [disciplinas]) ou None (auto-gated pelo grounding).
    """
    if not pergunta or kg is None:
        return None
    # para na 1ª pontuação; depois apara cláusula ("... que disciplinas vejo")
    m = re.search(r'[áa]reas?\s+(?:de\s+|d[oa]s?\s+)?([^,?.;!]+)', pergunta, re.IGNORECASE)
    if not m:
        return None
    termo = re.split(
        r'\s+(?:que|qual|quais|pra|para|onde|devo|posso|no\s+curso|do\s+curso)\b',
        m.group(1), maxsplit=1, flags=re.IGNORECASE)[0].strip(" ?.!,")
    if not termo:
        return None
    try:
        ds = kg.disciplinas_da_area(termo)
    except Exception:
        return None
    return (termo, ds) if ds else None


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
        from .. import oferta_real
        from .. import contatos_docentes
        from .. import semantic_router
        try:  # intenção por SIMILARIDADE semântica (não por lista de palavras)
            oferta_real.configurar_semantica(getattr(rag_instance, "embeddings", None))
            contatos_docentes.configurar(getattr(rag_instance, "embeddings", None))
            semantic_router.configurar(getattr(rag_instance, "embeddings", None))
        except Exception:
            pass
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
                elif re.search(r"\becomp\b|\bec\b|engenharia de computacao", q_fold):
                    curso_ac = "EC"
                elif hist and hist.get("curso"):
                    curso_ac = historico_curso_sigla(hist["curso"]) or "BCT"
                if curso_ac not in ("BCT", "BBT", "EB", "EM", "BMC", "BCC", "EC"):
                    curso_ac = "BCT"
                fontes_ac = {
                    "BBT": ["Regulamento de AC do BBT (Anexo F do PPC 2023)"],
                    "EB": ["Regulamento de AACC da EB (PPC 2023)"],
                    "EM": ["Regulamento de AACC do EM (2023)"],
                    "BMC": ["Regimento de AACC do BMC"],
                    "BCC": ["PPC do BCC"],
                    "EC": ["Regulamento de AC da EC (ecomp.unifesp.br)"],
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

            _kg = rag_instance.knowledge_graph
            _h = state.get("historico")
            _octx = _h.setdefault("oferta_ctx", {}) if isinstance(_h, dict) else {}

            if label == "oferta_raciocinio":
                # cruza a oferta com o grafo: por docente ("o que o Prof X dá")
                # ou por sala ("o que tem na sala 302")
                resposta = oferta_real.responder_raciocinio(pergunta_bruta, _kg)
                if not resposta:
                    return None
                # lembra a disciplina p/ follow-up ("qual dia e sala") quando o
                # docente ministra apenas uma neste semestre
                prof = oferta_real._extrai_docente(pergunta_bruta, _kg)
                if prof:
                    discs = _kg.disciplinas_do_docente_no_semestre(prof)
                    if len(discs) == 1:
                        _octx["disciplina"] = discs[0]
                    _octx["docente"] = prof
                return _resposta_simbolica(
                    resposta, "oferta_raciocinio",
                    ["Agenda de salas do campus SJC (oferta do semestre)"],
                )

            if label == "oferta_ambiguo":
                # sigla ambígua (ex.: 'AED' = I ou II) → follow-up de esclarecimento
                resposta = oferta_real.responder_ambiguo(pergunta_bruta, _kg)
                if not resposta:
                    return None
                return _resposta_simbolica(
                    resposta, "oferta_ambiguo",
                    ["Agenda de salas do campus SJC (oferta do semestre)"],
                )

            if label == "oferta_agenda":
                # oferta REAL do semestre (sala/dia/horário/professor) da agenda
                alvo = oferta_real.detectar(pergunta_bruta, _kg, _octx)
                # disciplina(s) explícita(s) → responde TODAS (composta 'X e Y');
                # sem disciplina na frase → follow-up, usa a do contexto (alvo)
                if oferta_real._todas_disciplinas(pergunta_bruta):
                    resposta = oferta_real.responder(pergunta_bruta, kg=_kg)
                else:
                    resposta = oferta_real.responder(pergunta_bruta, disciplina=alvo, kg=_kg)
                if not resposta:
                    return None
                if alvo:
                    _octx["disciplina"] = alvo  # lembra p/ follow-up
                return _resposta_simbolica(
                    resposta, "oferta_agenda",
                    ["Agenda de salas do campus SJC (oferta do semestre)"],
                )

            if label == "oferta_check":
                alvo = extrair_disciplina_oferta(pergunta_bruta) or disciplina_hint
                if not alvo:
                    return None
                # se estiver na oferta real, responde com sala/dia/prof; senão heurística
                resposta = oferta_real.responder(
                    pergunta_bruta, kg=rag_instance.knowledge_graph) \
                    or responder_oferta(rag_instance.knowledge_graph, alvo)
                if not resposta:
                    return None
                return _resposta_simbolica(
                    resposta, "oferta_check",
                    ["Agenda de salas do campus SJC / Knowledge Graph"],
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

        # ── Relatório de Progresso em PDF: fluxo GUIADO em etapas ─────────
        # O assistente entrevista o aluno (histórico → atividades →
        # identificação) e só oferece o download quando o dossiê está completo.
        hist_sessao = state.get("historico") if isinstance(state.get("historico"), dict) else {}
        fluxo_rel = hist_sessao.get("relatorio_fluxo") or {}
        pediu_relatorio = bool(re.search(
            r"relat[oó]rio|\bem pdf\b|\bpdf\b.*(progresso|relat)|baixar.*(progresso|pdf)",
            pergunta_bruta.lower(),
        ))
        q_bruta = pergunta_bruta.lower()
        _SKIP_RE = re.compile(r"\b(pular|pula|sem essa|deixa|depois|nao precisa|não precisa|sem identifica\w*|anonimo|anônimo|skip)\b")
        _AVANCA_RE = re.compile(r"\b(pronto|carreguei|enviei|feito|mandei|subi|ok|blz|beleza)\b")

        def _etapa_relatorio():
            if not hist_sessao.get("disciplinas") and not fluxo_rel.get("hist_pulado"):
                return "historico"
            if not hist_sessao.get("ac_itens") and not fluxo_rel.get("ac_pulado"):
                return "ac"
            if fluxo_rel.get("nome") is None and not fluxo_rel.get("sem_ident"):
                return "identificacao"
            return "pronto"

        def _pergunta_da_etapa(etapa):
            if etapa == "historico":
                return (
                    "Bora montar seu **Relatório de Progresso** direitinho. "
                    "Primeiro: envia seu **Histórico Acadêmico** (botão "
                    "*Histórico* aqui do chat) para eu preencher o quadro de "
                    "integralização com seus dados reais. Se preferir sem ele, "
                    "diz **\"pular\"**."
                )
            if etapa == "ac":
                return (
                    "Boa! Agora as **Atividades Complementares**: me manda a "
                    "lista para eu simular por eixo (ex.: *40h de monitoria, "
                    "20h de palestras, 1h de doação de sangue*). Se não quiser "
                    "incluir, diz **\"pular\"**."
                )
            if etapa == "identificacao":
                return (
                    "Última coisa: quer o PDF **identificado**? Me manda "
                    "*Nome, RA* (ex.: `Maria Silva, 123456`) ou diz "
                    "**\"sem identificação\"**."
                )
            return None

        def _resposta_fluxo(texto, extra_relatorio=False):
            hist_sessao["relatorio_fluxo"] = fluxo_rel
            return _resposta_simbolica(
                texto, "relatorio_pdf", ["Sessão da conversa"],
                relatorio=True if extra_relatorio else None,
            )

        def _finalizar_fluxo():
            fluxo_rel["ativo"] = False
            partes = ["Dossiê completo! Seu **Relatório de Progresso** vai com:"]
            partes.append(
                f"- Histórico: {len(hist_sessao.get('disciplinas') or [])} UCs e "
                "quadro de integralização" if hist_sessao.get("disciplinas")
                else "- Histórico: não incluído (quadro sai com os requisitos do curso)"
            )
            itens_ac = hist_sessao.get("ac_itens") or []
            partes.append(
                f"- Atividades Complementares: {len(itens_ac)} atividade(s) "
                "simuladas por eixo" if itens_ac
                else "- Atividades Complementares: não incluídas"
            )
            partes.append(
                f"- Identificação: {fluxo_rel.get('nome')}"
                + (f", RA {fluxo_rel['ra']}" if fluxo_rel.get("ra") else "")
                if fluxo_rel.get("nome") else "- Sem identificação nominal"
            )
            partes.append("\nClique abaixo para baixar. 📄")
            return _resposta_fluxo("\n".join(partes), extra_relatorio=True)

        if fluxo_rel.get("ativo") and not pediu_relatorio:
            etapa = _etapa_relatorio()
            consumiu = False
            if etapa == "historico":
                if hist_sessao.get("disciplinas") or _AVANCA_RE.search(q_bruta):
                    consumiu = True
                elif _SKIP_RE.search(q_bruta):
                    fluxo_rel["hist_pulado"] = True
                    consumiu = True
            elif etapa == "ac":
                itens_msg = parsear_atividades(pergunta_bruta)
                if itens_msg:
                    registrar_atividades(hist_sessao, itens_msg)
                    consumiu = True
                elif _SKIP_RE.search(q_bruta):
                    fluxo_rel["ac_pulado"] = True
                    consumiu = True
            elif etapa == "identificacao":
                if _SKIP_RE.search(q_bruta):
                    fluxo_rel["sem_ident"] = True
                    consumiu = True
                else:
                    digitos = re.sub(r"\D", "", pergunta_bruta)
                    ra_ok = digitos if 5 <= len(digitos) <= 9 else None
                    nome_limpo = re.sub(r"\s+", " ",
                                        re.sub(r"[\d.,;:]+", " ", pergunta_bruta)).strip()
                    # tira a afirmação do começo ("Sim, Leonardo..." → "Leonardo...")
                    nome_limpo = re.sub(
                        r"^(?:(?:sim|claro|quero|pode(?:\s+ser)?|ok|blz|beleza|"
                        r"aceito|isso|por favor|opa|boa)[\s!]*)+",
                        "", nome_limpo, flags=re.IGNORECASE,
                    ).strip()
                    nome_limpo = re.sub(
                        r"^(?:meu nome (?:é|e)|me chamo|sou o|sou a|sou)\s+",
                        "", nome_limpo, flags=re.IGNORECASE,
                    ).strip()
                    if 3 < len(nome_limpo) < 70 and "?" not in pergunta_bruta:
                        fluxo_rel["nome"] = nome_limpo.title()
                        fluxo_rel["ra"] = ra_ok
                        consumiu = True
            if consumiu:
                nova = _etapa_relatorio()
                if nova == "pronto":
                    return _finalizar_fluxo()
                return _resposta_fluxo(_pergunta_da_etapa(nova))
            # mensagem não é do fluxo: segue o pipeline normal (fluxo fica pendente)

        if pediu_relatorio:
            fluxo_rel["ativo"] = True
            etapa = _etapa_relatorio()
            if etapa == "pronto":
                return _finalizar_fluxo()
            return _resposta_fluxo(_pergunta_da_etapa(etapa))

        fast_label = None
        _h_of = state.get("historico")
        _octx_of = _h_of.setdefault("oferta_ctx", {}) if isinstance(_h_of, dict) else {}

        # Anáfora de grupo ("como falo com eles" após uma lista de docentes):
        # usa as entidades já aterradas + grounding no grafo + intenção semântica.
        _resp_grupo = contatos_docentes.responder_grupo(
            getattr(rag_instance, "graph_rag", None),
            pergunta_bruta,
            _h_of.get("_docentes_ativos") if isinstance(_h_of, dict) else None,
        )
        if _resp_grupo:
            return _resposta_simbolica(
                _resp_grupo, "contatos_grupo", ["Corpo docente / agenda do ICT"]
            )

        # Disciplinas por ÁREA de pesquisa (ponte APRENDIDA conceito→área):
        # precede a oferta, que senão captura o nome de disciplina homônimo.
        _area_res = _disciplinas_por_area(pergunta_bruta, rag_instance.knowledge_graph)
        if _area_res:
            _area_nome, _area_ds = _area_res
            _area_linhas = "\n".join(
                f"- **{d['nome']}** — cobre {', '.join(d['conceitos'][:4])}"
                for d in _area_ds)
            return _resposta_simbolica(
                f"**Disciplinas ligadas à área de {_area_nome}:**\n\n{_area_linhas}"
                "\n\n_Derivado da ponte aprendida conceito→área (`PERTENCE_A`, "
                "ponderada por crença) — não é a lista oficial da matriz._",
                "disciplinas_by_area", ["Ponte conceito→área (KG, aprendida)"],
            )

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
        elif oferta_real.detectar_raciocinio(pergunta_bruta, rag_instance.knowledge_graph):
            fast_label = "oferta_raciocinio"
        elif oferta_real.detectar(pergunta_bruta, rag_instance.knowledge_graph, _octx_of):
            fast_label = "oferta_agenda"
        elif oferta_real.detectar_ambiguo(pergunta_bruta, rag_instance.knowledge_graph):
            fast_label = "oferta_ambiguo"
        elif extrair_disciplina_oferta(pergunta_bruta):
            fast_label = "oferta_check"
        elif is_requisitos_request(pergunta_bruta):
            fast_label = "requisitos_curso"
        elif is_trilha_request(question) and not (
            hist_sessao is not None and _refere_proprias_ucs(pergunta_bruta)
        ):
            fast_label = "trilha"

        # Rede semântica (NÃO lexical): se os detectores lexicais não pegaram,
        # o router NN captura PARÁFRASES de intent de fluxo que a phrase-list
        # perde (limiar alto rejeita conteúdo). Lexical = precisão; semântico =
        # robustez a reformulações.
        if not fast_label:
            try:
                _sem = semantic_router.rotulo(pergunta_bruta)
                if _sem:
                    fast_label = _sem
            except Exception:
                pass

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

        # Rede semântica de DOMÍNIO (fallback): paráfrases de noticias/web_sjc que
        # a phrase-list perde. Margem grande (conteúdo <0.30, limiar 0.45) →
        # não sequestra pergunta de conteúdo.
        try:
            _dom = semantic_router.rotulo_dominio(question_lower)
        except Exception:
            _dom = None
        if _dom:
            return {
                **state, "intent": _dom, "term": "", "confidence": 0.85,
                "active_agent": _dom,
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
