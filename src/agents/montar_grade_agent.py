"""
Agente "Montar Grade" — planejador de trajetória curricular.

Detecta o pedido de montar a grade, tenta identificar o curso na mensagem e
sinaliza ao front para abrir o painel do planejador (canvas ao vivo). A coleta
precisa dos dados (disciplinas já cursadas, teto de créditos) acontece no
próprio painel, com inputs estruturados — bem mais confiável do que extrair uma
lista de disciplinas de texto livre.

O plano em si é calculado pelo módulo simbólico `planner.plan_curriculum`
(servido pelo endpoint /plan/stream), não pelo LLM: zero alucinação. O LLM aqui
só gera a fala conversacional de abertura.
"""

import random
from typing import Dict, Any, Optional, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .base_agent import BaseAgent

# Tokens genéricos que não distinguem um curso de outro.
_GENERIC_CURSO_TOKENS = frozenset({
    "bacharelado", "licenciatura", "curso", "em", "interdisciplinar", "superior",
})

# Teto de créditos por semestre assumido quando o aluno não informa.
_DEFAULT_MAX_CREDITOS = 24

# Pistas (já normalizadas: sem acento, sem de/da/do) de que o aluno está
# declarando disciplinas que JÁ cursou.
_COMPLETION_CUES = (
    "ja cursei", "ja passei", "ja fiz", "ja conclui", "ja completei",
    "ja tenho", "cursei", "passei em", "completei", "conclui", "tirei",
    "fechei", "fiz ",
)


class MontarGradeAgent(BaseAgent):

    name = "montar_grade"
    description = "Planeja sua trajetória curricular semestre a semestre"
    color = "#a855f7"  # Purple

    def retrieve(self, question: str, intent: str, term: str) -> str:
        return ""

    def get_prompt_template(self) -> str:
        return (
            "Voce e o assistente virtual da UNIFESP ICT, simpatico e animado. "
            "O aluno pediu para montar a grade dele e voce vai ABRIR um painel "
            "(planejador) ao lado que JA COMECA a desenhar a trajetoria sozinho.\n\n"
            "Curso identificado: {curso}\n"
            "Disciplinas que ele disse ja ter cursado: {cursadas}\n\n"
            "Escreva UMA fala curta (1-2 frases), calorosa e natural em PORTUGUES "
            "BRASILEIRO, avisando que ja esta montando a grade ao lado. "
            "Se houver um curso identificado, mencione-o. Se ele citou disciplinas "
            "cursadas, de a entender que voce ja as considerou. Diga que ele pode "
            "ajustar curso, disciplinas ou o teto de creditos ali no painel se quiser. "
            "No maximo 1 emoji. Nao use listas nem texto institucional.\n\nResposta:"
        )

    def _resolve_curso(self, question: str) -> Optional[str]:
        """Casa um curso conhecido (nome ou sigla) na mensagem, de forma tolerante."""
        kg = self.knowledge_graph
        if not kg:
            return None
        norm = kg._normalize_text
        q = norm(question)
        qtokens = set(q.split())
        try:
            cursos: List[Dict] = kg.get_all_cursos()
        except Exception:
            return None

        def tok_match(t: str, qtokens: set) -> bool:
            # Leniência singular/plural: ciencia ~ ciencias.
            return (
                t in qtokens
                or (t + "s") in qtokens
                or (t.endswith("s") and t[:-1] in qtokens)
            )

        melhor, melhor_score = None, 0
        for c in cursos:
            nome = (c.get("nome") or "").strip()
            sigla = (c.get("sigla") or "").strip()

            # Sigla como palavra inteira (evita "ec" dentro de "ciencia").
            if sigla and len(sigla) >= 2 and norm(sigla) in qtokens:
                if 100 > melhor_score:
                    melhor, melhor_score = nome or sigla, 100

            if not nome:
                continue
            nnome = norm(nome)
            if not nnome:
                continue

            # Nome completo aparece na pergunta.
            if nnome in q:
                score = 50 + len(nnome)
                if score > melhor_score:
                    melhor, melhor_score = nome, score
                continue

            # Overlap de tokens distintivos: todos presentes na pergunta.
            distintos = [
                t for t in nnome.split()
                if len(t) > 2 and t not in _GENERIC_CURSO_TOKENS
            ]
            if distintos and all(tok_match(t, qtokens) for t in distintos):
                score = sum(len(t) for t in distintos)
                if score > melhor_score:
                    melhor, melhor_score = nome, score

        return melhor

    def _extract_completed(self, question: str) -> List[str]:
        """
        Extrai disciplinas já cursadas mencionadas na frase, validando contra os
        nomes reais do KG. Só age se houver pista de conclusão (ex.: "já cursei"),
        para não confundir o curso/assunto com disciplinas concluídas.
        """
        kg = self.knowledge_graph
        if not kg:
            return []
        norm = kg._normalize_text
        nq = norm(question)
        if not any(cue in nq for cue in _COMPLETION_CUES):
            return []

        # Disciplinas conhecidas (nome normalizado → nome original).
        candidatos = []
        for _, data in kg.graph.nodes(data=True):
            if data.get("tipo") != "disciplina":
                continue
            nome = data.get("nome")
            if not nome:
                continue
            nn = norm(nome)
            if len(nn) >= 4 and nn in nq:
                candidatos.append((nn, nome))

        # Mais longos primeiro; descarta os contidos em outro já escolhido
        # (ex.: "calculo" dentro de "calculo 1").
        candidatos.sort(key=lambda x: -len(x[0]))
        escolhidos_norm: List[str] = []
        resultado: List[str] = []
        for nn, nome in candidatos:
            if any(nn != outro and nn in outro for outro in escolhidos_norm):
                continue
            if nome in resultado:
                continue
            escolhidos_norm.append(nn)
            resultado.append(nome)
        return resultado

    def _fallback_message(self, curso: Optional[str]) -> str:
        """Mensagem de reserva (variada) caso o LLM falhe."""
        if curso:
            opts = [
                f"Show! Já tô abrindo o planejador de **{curso}** aqui do lado 👉 "
                "me diz lá as disciplinas que você já cursou e o teto de créditos.",
                f"Bora montar sua grade de **{curso}**! 🎓 Abri o painel ao lado — "
                "é só informar o que você já cursou e quantos créditos por semestre.",
            ]
        else:
            opts = [
                "Boa! Abri o planejador aqui do lado 👉 escolhe o curso, me diz o que "
                "já cursou e o teto de créditos por semestre que eu desenho sua trajetória.",
                "Vamos lá! 🎓 No painel ao lado, escolhe o curso e informa as "
                "disciplinas já cursadas + o teto de créditos — eu cuido do resto.",
            ]
        return random.choice(opts)

    def answer(self, question: str, intent: str, term: str, history: str = "") -> Dict[str, Any]:
        curso = self._resolve_curso(question)
        completed = self._extract_completed(question)

        # Fala conversacional via LLM, com fallback seguro/variado.
        response = None
        if self.llm:
            try:
                prompt = ChatPromptTemplate.from_template(self.get_prompt_template())
                chain = prompt | self.llm | StrOutputParser()
                response = chain.invoke({
                    "curso": curso or "nenhum (o aluno vai escolher no painel)",
                    "cursadas": ", ".join(completed) if completed else "nenhuma informada",
                }).strip()
            except Exception:
                response = None
        if not response:
            response = self._fallback_message(curso)

        return {
            "response": response,
            "agent": self.name,
            "agent_description": self.description,
            "context_length": 0,
            "context": "",
            "sources": [],
            # Sinaliza ao front para abrir o canvas e já montar a grade sozinho.
            "plan_request": {
                "curso": curso,
                "completed": completed,
                "max_creditos": _DEFAULT_MAX_CREDITOS,
            },
        }
