"""
Agente Conversacional do FESP-AI.

Domínio: saudações, agradecimentos, despedidas, identidade do assistente e
conversa social (small talk). Responde de forma calorosa e humana, como um
chatbot de verdade, e convida o usuário a perguntar sobre a UNIFESP ICT.

Diferente dos demais agentes, este NÃO faz retrieval nem validação simbólica:
conversa social não precisa de contexto da base de dados, então sobrescrevemos
`answer()` para gerar a resposta diretamente pelo LLM.
"""

from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .base_agent import BaseAgent


class ConversaAgent(BaseAgent):

    name = "conversa"
    description = "Assistente conversacional para saudações e conversa do dia a dia"
    color = "#22c55e"  # Green

    def retrieve(self, question: str, intent: str, term: str) -> str:
        # Conversa social não consulta a base de dados.
        return ""

    def get_prompt_template(self) -> str:
        return """Voce e o assistente virtual da UNIFESP ICT — simpatico, acolhedor e bem-humorado, como um colega que adora ajudar. Fale sempre em PORTUGUES BRASILEIRO, de forma curta e natural.

O usuario disse: {question}

Como responder:
- Tom caloroso e humano, como num bate-papo real. NAO use emojis.
- Se for uma saudacao, retribua com simpatia e pergunte como pode ajudar.
- Se for um agradecimento, responda com gentileza e se coloque a disposicao.
- Se for uma despedida, despeca-se de forma amigavel.
- Se perguntarem quem voce e, explique em uma frase que voce e o assistente virtual da UNIFESP ICT, criado para ajudar a comunidade academica.
- Sempre que fizer sentido, lembre brevemente que voce pode ajudar com disciplinas, professores, cursos, pre-requisitos e regimentos da UNIFESP ICT.
- Seja breve: 1 a 3 frases. Nada de listas longas nem texto institucional engessado.

Resposta:"""

    def answer(self, question: str, intent: str, term: str, history: str = "") -> Dict[str, Any]:
        """Gera resposta conversacional direta — sem retrieval nem validação simbólica."""
        template = self.get_prompt_template()
        if history:
            template = template.replace(
                "O usuario disse: {question}",
                "HISTORICO RECENTE DA CONVERSA:\n{history}\n\n"
                "A conversa JA ESTA EM ANDAMENTO: nao se reapresente nem cumprimente "
                "de novo (a menos que o usuario esteja claramente cumprimentando agora).\n\n"
                "O usuario disse: {question}",
                1,
            )
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm | StrOutputParser()
        try:
            inputs = {"question": question}
            if history:
                inputs["history"] = history
            response = chain.invoke(inputs)
        except Exception:
            response = (
                "Oi! 😊 Sou o assistente da UNIFESP ICT. Posso te ajudar com "
                "disciplinas, professores, cursos e regimentos. O que voce gostaria de saber?"
            )
        return {
            "response": response,
            "agent": self.name,
            "agent_description": self.description,
            "context_length": 0,
            "context": "",
            "sources": [],
        }
