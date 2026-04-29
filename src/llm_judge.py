import json
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class JudgeResult:
    groundedness: int
    correctness: int
    completeness: int
    clarity: int
    unsupported_claims: int
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "groundedness": self.groundedness,
            "correctness": self.correctness,
            "completeness": self.completeness,
            "clarity": self.clarity,
            "unsupported_claims": self.unsupported_claims,
            "rationale": self.rationale,
        }


JUDGE_PROMPT = """Você é um avaliador rigoroso (LLM-as-a-Judge) para um sistema GraphRAG + neurossimbólico.
Você deve julgar a resposta do assistente usando SOMENTE as evidências fornecidas em EVIDENCIAS.
Se a resposta trouxer algo que NÃO esteja nas evidências, isso conta como afirmação não suportada.

Tarefa:
- Dê notas inteiras de 0 a 5 para:
  (1) groundedness: quanto do que foi dito está explicitamente suportado pelas evidências?
  (2) correctness: a resposta está correta em relação às evidências?
  (3) completeness: cobre o que foi perguntado, dentro do que as evidências permitem?
  (4) clarity: está clara, direta e bem estruturada?
- Conte unsupported_claims: número aproximado de afirmações relevantes NÃO suportadas pelas evidências.
- Escreva rationale curto (1-4 frases) EM PORTUGUÊS BRASILEIRO, citando o motivo principal.

Formato de saída OBRIGATÓRIO: um JSON válido, sem texto fora do JSON.
Chaves obrigatórias: groundedness, correctness, completeness, clarity, unsupported_claims, rationale

PERGUNTA:
{question}

EVIDENCIAS (use somente isso):
{evidence}

RESPOSTA DO ASSISTENTE:
{answer}
"""


def _safe_int(x: Any, default: int) -> int:
    try:
        v = int(x)
    except Exception:
        return default
    return max(0, min(5, v))


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    text = text.strip()
    # Já é JSON
    if text.startswith("{") and text.endswith("}"):
        try:
            return json.loads(text)
        except Exception:
            pass
    # Tentar capturar o maior bloco JSON
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        blob = text[start : end + 1]
        try:
            return json.loads(blob)
        except Exception:
            return None
    return None


def _looks_like_english(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    # Heurística simples: presença de várias stopwords comuns do inglês
    hits = sum(
        1
        for w in (
            "the",
            "and",
            "are",
            "is",
            "all",
            "every",
            "explicitly",
            "evidence",
            "therefore",
            "supported",
            "grounded",
        )
        if w in t
    )
    return hits >= 3


def _rewrite_rationale_pt_br(llm, rationale: str) -> str:
    prompt = (
        "Reescreva o texto abaixo EM PORTUGUÊS BRASILEIRO, mantendo o sentido e sendo conciso "
        "(1-4 frases). Não inclua aspas nem explicações extras; responda apenas com o texto reescrito.\n\n"
        f"TEXTO:\n{rationale.strip()}\n"
    )
    try:
        out = llm.invoke(prompt)
        return (out or "").strip()
    except Exception:
        return rationale


def judge_answer(llm, question: str, answer: str, evidence: str) -> JudgeResult:
    prompt = JUDGE_PROMPT.format(
        question=question.strip(),
        answer=(answer or "").strip(),
        evidence=(evidence or "").strip(),
    )
    raw = llm.invoke(prompt)
    parsed = _extract_json(raw) or {}

    groundedness = _safe_int(parsed.get("groundedness"), 0)
    correctness = _safe_int(parsed.get("correctness"), 0)
    completeness = _safe_int(parsed.get("completeness"), 0)
    clarity = _safe_int(parsed.get("clarity"), 0)
    try:
        unsupported = int(parsed.get("unsupported_claims", 0))
        if unsupported < 0:
            unsupported = 0
    except Exception:
        unsupported = 0
    rationale = str(parsed.get("rationale", "")).strip()
    if rationale and _looks_like_english(rationale):
        rationale = _rewrite_rationale_pt_br(llm, rationale)

    return JudgeResult(
        groundedness=groundedness,
        correctness=correctness,
        completeness=completeness,
        clarity=clarity,
        unsupported_claims=unsupported,
        rationale=rationale,
    )

