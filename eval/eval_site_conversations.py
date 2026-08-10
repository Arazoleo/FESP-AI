#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Avaliação conversacional do site do campus - FESP-AI.

10 conversas multi-turno (mesmo conversation_id por conversa) cobrindo todos os
tópicos do corpus do site SJC: página do BCT (visão geral, ingresso, FAQ,
matrizes, comissões), procedimentos de graduação, biblioteca, pós-graduação,
contatos/institucional, outros cursos, robustez a linguagem natural (anáforas)
e honestidade em negativos.

Checagens por turno:
  - agente ativo dentro do conjunto esperado
  - resposta contém ao menos uma keyword esperada (sem acentos, case-insensitive)
  - turnos 2+ NÃO recomeçam com saudação ("Olá!", "Oi!"...) - continuidade
  - negativos: resposta não inventa (proíbe padrões tipo "R$")

Uso:
  python eval_site_conversations.py                  # localhost:8000
  python eval_site_conversations.py --url http://IP:8000
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import datetime

try:
    import requests
except ImportError:
    print("Instale requests: pip install requests")
    sys.exit(1)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


_GREETING_RE = re.compile(
    r"^\s*[*_#\s]*(?:ol[aá]|oi+|opa|e\s*a[ií]|eai|tudo\s+bem|salve)\b", re.IGNORECASE
)


CONVERSAS = [
    ("C1 - BCT: visão geral + fusão KG↔site", [
        ("O que é o BCT?",
         {"web_sjc"}, ["ciencia e tecnologia", "interdisciplinar"], []),
        ("e como eu ingresso nele?",
         {"web_sjc"}, ["sisu", "enem", "ingresso"], []),
        ("quantos termos tem o BCT?",
         None, ["termo", "semestre", "seis", "6"], []),
    ]),
    ("C2 - BCT: FAQ de integralização", [
        ("Quantas horas preciso para integralizar o BCT integral?",
         None, ["horas", "carga"], []),
        ("e qual o prazo máximo para concluir o curso?",
         None, ["prazo", "anos", "termos", "semestres"], []),
        ("o que são atividades curriculares extensionistas?",
         None, ["extensionista", "extensao"], []),
    ]),
    ("C3 - BCT: matrizes e estrutura", [
        ("Como funciona a matriz curricular do BCT?",
         None, ["fixas", "eletivas", "matriz", "unidades curriculares"], []),
        ("entrei em 2021, qual matriz de transição eu sigo?",
         None, ["transicao", "2022", "2-2022"], []),
        ("quem faz parte da comissão de curso do BCT?",
         None, ["comissao", "prof"], []),
    ]),
    ("C4 - Graduação: procedimentos da secretaria", [
        ("Como emito um atestado de matrícula?",
         {"web_sjc"}, ["atestado", "matricula"], []),
        ("e como solicito o diploma?",
         None, ["diploma"], []),
        ("como funciona o aproveitamento de estudos?",
         None, ["aproveitamento"], []),
    ]),
    ("C5 - Biblioteca", [
        ("Como faço o cadastro de usuário na biblioteca?",
         {"web_sjc"}, ["biblioteca", "cadastro"], []),
        ("tem salas de estudo em grupo?",
         None, ["sala"], []),
        ("como funciona a verificação de similaridade para plágio?",
         None, ["similaridade", "plagio"], []),
    ]),
    ("C6 - Pós-graduação e pesquisa", [
        ("Tem mestrado no campus? Como ingresso na pós?",
         {"web_sjc"}, ["mestrado", "pos-graduacao", "pos"], []),
        ("quais programas de pós-graduação existem no ICT?",
         None, ["programa", "pos"], []),
    ]),
    ("C7 - Institucional e contatos", [
        ("Qual o contato da secretaria de graduação?",
         {"web_sjc"}, ["contato", "email", "@", "telefone", "atendimento"], []),
        ("quem é a direção acadêmica do campus?",
         None, ["diretor", "direcao"], []),
        ("o que faz a congregação do instituto?",
         None, ["congregacao"], []),
    ]),
    ("C8 - Outros cursos do site", [
        ("Como funciona a Engenharia Biomédica?",
         {"web_sjc"}, ["biomedica"], []),
        ("O que é o BCC?",
         None, ["computacao"], []),
        ("quem coordena o BCC?",
         None, ["coordenad"], []),
    ]),
    ("C9 - Robustez NL: anáforas (conversa que quebrava)", [
        ("Como funciona a matriz curricular do BCC?",
         None, ["bcc", "matriz", "termos", "computacao"], []),
        ("E tem como saber algumas dessas eletivas?",
         None, ["grupo", "eletiva"],
         [r"nao encontrei o curso"]),
        ("e o coordenador?",
         None, ["coordenad"], []),
    ]),
    ("C10 - Honestidade em negativos", [
        ("Qual a mensalidade do BCT?",
         None, ["nao", "gratuito", "publica"],
         [r"r\$\s*\d"]),
        ("Qual o preço do estacionamento do campus?",
         None, ["nao"],
         [r"r\$\s*\d"]),
        ("valeu, obrigado!",
         {"conversa"}, ["disposicao", "precisar", "ajudar", "nada", ":)", "😊", "por aqui"], []),
    ]),
]


def call_chat(base_url: str, message: str, conversation_id=None, timeout=180) -> dict:
    payload = {"message": message}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    try:
        r = requests.post(f"{base_url}/chat", json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"response": f"[ERRO: {e}]", "active_agent": "ERROR", "conversation_id": conversation_id}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    args = ap.parse_args()

    resultados = []
    total_ok = total_turnos = 0

    for titulo, turnos in CONVERSAS:
        print(f"\n\033[1m{titulo}\033[0m")
        cid = None
        for i, (msg, agentes, keywords, proibidos) in enumerate(turnos, 1):
            t0 = time.time()
            resp = call_chat(args.url, msg, cid)
            dt = time.time() - t0
            cid = resp.get("conversation_id", cid)
            texto = resp.get("response", "")
            agente = resp.get("active_agent", "?")
            texto_norm = _norm(texto)

            falhas = []
            if agente == "ERROR":
                falhas.append("erro de chamada")
            if agentes is not None and agente not in agentes:
                falhas.append(f"agente={agente} (esperado {'/'.join(sorted(agentes))})")
            if keywords and not any(_norm(k) in texto_norm for k in keywords):
                falhas.append(f"sem keywords {keywords}")
            if i >= 2 and _GREETING_RE.match(texto):
                falhas.append("re-saudação no turno ≥2")
            for pat in proibidos:
                if re.search(pat, texto_norm):
                    falhas.append(f"conteúdo proibido: {pat!r}")

            ok = not falhas
            total_ok += ok
            total_turnos += 1
            simbolo = "\033[92m✓\033[0m" if ok else "\033[91m✗\033[0m"
            detalhe = "" if ok else f"  \033[91m[{'; '.join(falhas)}]\033[0m"
            print(f"  {simbolo} [{agente:<12}] {dt:5.1f}s  {msg[:58]}{detalhe}")
            if not ok:
                print(f"      ↳ {texto[:180].replace(chr(10), ' ')}")

            resultados.append({
                "conversa": titulo, "turno": i, "pergunta": msg,
                "agente": agente, "latencia_s": round(dt, 2),
                "ok": ok, "falhas": falhas, "resposta": texto,
            })

    print(f"\n\033[1mResultado: {total_ok}/{total_turnos} turnos passaram "
          f"({100 * total_ok / max(total_turnos, 1):.0f}%)\033[0m")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = f"eval_site_conversations_{stamp}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"timestamp": stamp, "base_url": args.url,
                   "total": total_turnos, "ok": total_ok,
                   "resultados": resultados}, f, ensure_ascii=False, indent=1)
    print(f"Detalhes salvos em {out}")
    sys.exit(0 if total_ok == total_turnos else 1)


if __name__ == "__main__":
    main()
