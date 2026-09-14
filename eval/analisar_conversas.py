"""
Análise de gargalo por CONVERSA INTEIRA (fecha o ponto cego do oráculo de miss).

O oráculo de runtime (is_miss_response) só pega falha CONFESSA. Este analisador
olha a jornada completa e usa um LLM para achar o GARGALO — inclusive resposta
confiante mas errada, usuário reformulando e desistência, que a confissão não vê.

Fluxo (captura híbrida — a resposta do assistente só foi gravada nos turnos
suspeitos, ver interaction_log):
  1. agrupa interactions.jsonl por cid, ordena por ts → conversas;
  2. sinais BARATOS de atrito por conversa (sem LLM): reformulação (perguntas
     consecutivas ~iguais), cadeia de miss, pingue-pongue de agente, latência
     alta, abandono após atrito;
  3. só nas conversas SUSPEITAS, chama o LLM com o transcript disponível e pede
     o gargalo estruturado (tipo, turno, severidade, evidência, correção);
  4. escreve conversation_bottlenecks.jsonl + ranking. Alimenta o mesmo loop
     (self_heal / curadoria). Merge continua humano.

Roda no container (usa Ollama/embeddings). Sem LLM/embeddings, degrada para só
os sinais heurísticos (nunca quebra).

Uso:
    python eval/analisar_conversas.py [--max-llm N]
Env: MODEL_NAME, EMBEDDING_MODEL, OLLAMA_BASE_URL, FESPAI_DATA_DIR.
"""

import os
import re
import sys
import json
from difflib import SequenceMatcher
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.getenv("FESPAI_DATA_DIR", os.path.join(ROOT, "chroma_db_unifesp"))
INTERACTIONS = os.path.join(DATA, "interactions.jsonl")
OUT = os.path.join(DATA, "conversation_bottlenecks.jsonl")

REFORMULACAO_SIM = 0.82   # perguntas consecutivas acima disto ~ reformulação
SLOW_MS = int(os.getenv("FESPAI_SLOW_MS", "12000"))


def _load(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    return out


def _conversas(turnos):
    """Agrupa por cid e ordena por ts. Retorna [(cid, [turnos...]), ...]."""
    porcid = defaultdict(list)
    for t in turnos:
        porcid[t.get("cid", "")].append(t)
    convs = []
    for cid, ts in porcid.items():
        if not cid:
            continue
        ts.sort(key=lambda x: x.get("ts", ""))
        if len(ts) >= 1:
            convs.append((cid, ts))
    return convs


# ---- sinais baratos de atrito (sem LLM) ------------------------------------

def _embed_sims(perguntas, emb):
    """Similaridade semântica entre perguntas consecutivas (0..1). Fallback
    lexical (SequenceMatcher) se não houver embeddings."""
    if len(perguntas) < 2:
        return []
    if emb is not None:
        try:
            import numpy as np
            m = np.array(emb.embed_documents(perguntas), dtype="float32")
            m /= (np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)
            return [float(m[i] @ m[i + 1]) for i in range(len(perguntas) - 1)]
        except Exception:
            pass
    return [SequenceMatcher(None, perguntas[i].lower(), perguntas[i + 1].lower()
                            ).ratio() for i in range(len(perguntas) - 1)]


def _sinais(turnos, emb):
    perguntas = [t.get("question", "") for t in turnos]
    sims = _embed_sims(perguntas, emb)
    reformulou = sum(1 for s in sims if s >= REFORMULACAO_SIM)
    misses = sum(1 for t in turnos if t.get("miss"))
    agentes = [t.get("agent", "") for t in turnos]
    trocas = sum(1 for i in range(len(agentes) - 1) if agentes[i] != agentes[i + 1])
    lat_max = max((t.get("latency_ms") or 0) for t in turnos)
    ultimo = turnos[-1]
    # abandono: conversa curta que termina logo após um turno de atrito
    abandono = len(turnos) <= 3 and (ultimo.get("miss") or
               (sims and sims[-1] >= REFORMULACAO_SIM))
    sinais = {
        "reformulacoes": reformulou,
        "misses": misses,
        "trocas_agente": trocas,
        "latencia_max_ms": int(lat_max),
        "abandono": bool(abandono),
        "n_turnos": len(turnos),
    }
    suspeita = (reformulou >= 1 or misses >= 1 or trocas >= 2
                or lat_max >= SLOW_MS or abandono)
    return suspeita, sinais


# ---- LLM: diagnóstico do gargalo -------------------------------------------

def _get_llm(max_predict=700):
    model = os.getenv("MODEL_NAME", "gemma4:31b-cloud")
    base = (os.getenv("OLLAMA_BASE_URL") or "").strip() or "http://ollama:11434"
    try:
        from langchain_ollama import OllamaLLM
        return OllamaLLM(model=model, base_url=base, temperature=0.0,
                         num_predict=max_predict, keep_alive=1800)
    except Exception:
        return None


def _get_emb():
    model = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large")
    base = (os.getenv("OLLAMA_BASE_URL") or "").strip() or "http://ollama:11434"
    try:
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(model=model, base_url=base)
    except Exception:
        return None


def _transcript(turnos):
    linhas = []
    for i, t in enumerate(turnos, 1):
        linhas.append(f"[turno {i}] usuário ({t.get('agent','?')}/"
                      f"{t.get('intent','?')}): {t.get('question','')}")
        if t.get("answer"):
            linhas.append(f"          assistente: {t['answer']}")
        elif t.get("miss"):
            linhas.append("          assistente: (falha confessa — não gravada)")
    return "\n".join(linhas)


_PROMPT = """Você audita uma conversa entre um estudante e um assistente \
acadêmico da universidade. Ache o GARGALO: o ponto onde a experiência falhou \
ou travou. Inclua respostas confiantes porém erradas, roteamento para o agente \
errado, dado faltante, lentidão e frustração/abandono.

Conversa (nem toda resposta foi gravada — só as de turnos com atrito):
{transcript}

Sinais automáticos: {sinais}

Responda SÓ com um JSON:
{{"gargalo": "<1 frase do problema central>", "tipo": "<roteamento|dado|\
qualidade|latencia|ux>", "turno": <inteiro do turno onde ocorre>, \
"severidade": <1 a 5>, "evidencia": "<trecho/observação>", \
"correcao_sugerida": "<o que mudar no assistente>"}}"""


def _parse_json(texto):
    m = re.search(r"\{.*\}", texto or "", re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def main():
    max_llm = 40
    if "--max-llm" in sys.argv:
        try:
            max_llm = int(sys.argv[sys.argv.index("--max-llm") + 1])
        except Exception:
            pass

    turnos = _load(INTERACTIONS)
    if not turnos:
        print(f"Sem interações em {INTERACTIONS}. Rode o assistente primeiro.")
        return
    convs = _conversas(turnos)
    emb = _get_emb()

    suspeitas = []
    for cid, ts in convs:
        susp, sinais = _sinais(ts, emb)
        if susp:
            suspeitas.append((cid, ts, sinais))
    # mais atrito primeiro (reformulação+miss+abandono pesam)
    suspeitas.sort(key=lambda x: (x[2]["reformulacoes"] + x[2]["misses"]
                   + (2 if x[2]["abandono"] else 0)), reverse=True)

    print(f"{len(convs)} conversas | {len(suspeitas)} suspeitas de gargalo")

    llm = _get_llm() if suspeitas else None
    resultados = []
    for cid, ts, sinais in suspeitas[:max_llm]:
        item = {"cid": cid, "n_turnos": sinais["n_turnos"], "sinais": sinais}
        if llm is not None:
            try:
                resp = llm.invoke(_PROMPT.format(
                    transcript=_transcript(ts),
                    sinais=json.dumps(sinais, ensure_ascii=False)))
                diag = _parse_json(resp)
                if diag:
                    item["diagnostico"] = diag
            except Exception as e:
                item["erro_llm"] = str(e)[:120]
        resultados.append(item)

    with open(OUT, "w", encoding="utf-8") as f:
        for r in resultados:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(resultados)} análises → {OUT}")
    if llm is None and suspeitas:
        print("(LLM indisponível — só sinais heurísticos; rode no container p/ o diagnóstico)")

    # ranking por tipo de gargalo (o que o loop deve atacar primeiro)
    portipo = defaultdict(list)
    for r in resultados:
        d = r.get("diagnostico")
        if d:
            portipo[d.get("tipo", "?")].append(d)
    if portipo:
        print("\n== GARGALOS por tipo (severidade média × ocorrências) ==")
        linhas = []
        for tipo, ds in portipo.items():
            sev = sum(int(d.get("severidade", 0) or 0) for d in ds) / len(ds)
            linhas.append((sev * len(ds), tipo, len(ds), sev))
        for score, tipo, n, sev in sorted(linhas, reverse=True):
            ex = next((d.get("gargalo", "") for d in portipo[tipo]), "")
            print(f"  {tipo:10} [{n}x, sev~{sev:.1f}]  {ex[:60]}")


if __name__ == "__main__":
    main()
