"""
Autoformalização: o LLM lê o dispositivo e escreve as regras ASP; o lado
simbólico verifica e devolve o erro até a formalização passar.

Verificações SEM gabarito (podem guiar o reparo sem vazar a resposta):
  1. sintaxe       — o clingo consegue ler o programa;
  2. contrato      — define todos os predicados de saída com a aridade pedida;
  3. vocabulário   — todo predicado usado no corpo existe (entrada, upstream ou
                     definido no próprio programa). Predicado inexistente é
                     sempre falso no ASP: é o erro silencioso mais perigoso;
  4. execução      — aterra e tem modelo único em cenários sintéticos
                     (variável insegura, negação circular, contradição) e sem
                     aritmética indefinida (no clingo ela some sem erro);
  5. contratos     — propriedades que decorrem do significado das saídas
                     (exclusão mútua, totalidade, valor único, faixa). A
                     violação volta ao LLM com o cenário-contraexemplo, mas
                     sem a resposta esperada.

A comparação com a formalização escrita à mão NÃO entra no laço de reparo:
ela só mede o resultado depois (eval/eval_normas_autoformalizacao.py).
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import clingo
from clingo import ast

from .estado import VOCABULARIO_ENTRADA
from .grupos import Grupo
from .motor import Motor, REGRAS_DIR

OLLAMA = "http://localhost:11434"

_ENTRADA = {
    "matricula/2", "carga/2", "grupo/2", "natureza/2", "freq/3", "freq_minima_ppc/2",
    "nota10/3", "media10/3", "exame10/3", "situacao/3", "em_rer/2", "uc_pratica/1",
    "rer_vedado/1", "prereq/2", "ingresso/1", "ano_ingresso/1", "periodo_atual/1",
    "integral/0", "parcial/0", "duracao_minima/1", "trancamento/2",
    "transferido_no_ano/1", "processo_disciplinar/0", "horas/2", "exigido/2",
}

PROMPT = """Você formaliza regulamentos acadêmicos em Answer Set Programming (clingo 5).

TAREFA: escreva as regras que implementam EXATAMENTE os dispositivos abaixo.

## Dispositivos (texto oficial)
{texto}

## Predicados de ENTRADA (fatos do estudante; não os redefina)
{entrada}
## Predicados já definidos por outras normas (pode usar no corpo)
{upstream}
## Predicados de SAÍDA que você DEVE definir
{saidas}

## Convenções
- Período P = ano*2 + (semestre-1). Notas ×10 em inteiros (5,9 → 59). Frequência em % inteiro.
- Só aritmética inteira; "/" é divisão inteira (trunca). Arredondar para cima: (A + B - 1) / B.
- Sintaxe clingo: comparações são <, <=, >, >=, =, != (NÃO use =< nem <>).
- Programa estratificado: sem regras de escolha, sem restrições de integridade, sem #show,
  sem #minimize. Use negação por falha ("not") para exceções e vedações.
- Predicados auxiliares são permitidos; use nomes descritivos em português.
- Antes de cada bloco de regras, uma linha de anotação:
  %! <id_curto> | <dispositivo, ex. Art. 122, I> | <paráfrase de uma linha>

Responda SOMENTE com o programa dentro de um bloco ```asp ... ```."""

REPARO = """O programa tem problemas detectados pelo verificador:

{erros}

Corrija e responda de novo SOMENTE com o programa completo dentro de ```asp ... ```."""


@dataclass
class Tentativa:
    programa: str
    erros: List[str]
    segundos: float


@dataclass
class Formalizacao:
    grupo: str
    modelo: str
    programa: Optional[str]
    valida: bool
    tentativas: List[Tentativa] = field(default_factory=list)


GROQ = "https://api.groq.com/openai/v1/chat/completions"


def _chat_groq(modelo: str, mensagens: List[Dict], timeout: int) -> str:
    """`groq:<modelo>`, p.ex. groq:openai/gpt-oss-120b. Espera o retry-after em 429."""
    import os
    chave = os.environ["GROQ_API_KEY"]
    corpo = json.dumps({"model": modelo, "messages": mensagens, "temperature": 0.0,
                        "include_reasoning": False}).encode()
    for t in range(8):
        req = urllib.request.Request(GROQ, corpo, {"Content-Type": "application/json",
                                                   "Authorization": f"Bearer {chave}",
                                                   "User-Agent": "normas-eval"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())["choices"][0]["message"].get("content") or ""
        except urllib.error.HTTPError as e:
            if e.code == 429 and t < 7:
                time.sleep(min(float(e.headers.get("retry-after") or 30), 600))
                continue
            if e.code >= 500 and t < 7:
                time.sleep(10 * 2 ** min(t, 4))
                continue
            raise RuntimeError(f"Groq {e.code}: {e.read()[:300]!r}") from e
    return ""


def _chat(modelo: str, mensagens: List[Dict], timeout: int = 600) -> str:
    if modelo.startswith("groq:"):
        return _chat_groq(modelo[len("groq:"):], mensagens, timeout)
    corpo = json.dumps({"model": modelo, "messages": mensagens, "stream": False,
                        "options": {"temperature": 0.0}}).encode()
    for t in range(5):
        try:
            req = urllib.request.Request(f"{OLLAMA}/api/chat", corpo,
                                         {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())["message"]["content"]
        except Exception:
            if t == 4:
                raise
            time.sleep(10 * 2 ** t)
    return ""


def extrair_programa(resposta: str) -> str:
    resposta = re.sub(r"<think>.*?</think>", "", resposta, flags=re.S)
    blocos = re.findall(r"```(?:asp|clingo|prolog|lp)?\s*\n(.*?)```", resposta, re.S)
    return (max(blocos, key=len) if blocos else resposta).strip()


def _assinaturas(programa: str) -> Tuple[Set[str], Set[str], List[str]]:
    """(cabeças, predicados usados no corpo, proibições encontradas)."""
    cabecas, corpo, proib = set(), set(), []

    class _Coleta(ast.Transformer):
        def visit_SymbolicAtom(self, a):
            s = a.symbol
            if s.ast_type == ast.ASTType.Function:
                corpo.add(f"{s.name}/{len(s.arguments)}")
            return a

    def cb(stm):
        if stm.ast_type == ast.ASTType.Rule:
            h = stm.head
            if h.ast_type == ast.ASTType.Literal and h.atom.ast_type == ast.ASTType.SymbolicAtom:
                s = h.atom.symbol
                if s.ast_type == ast.ASTType.Function:
                    cabecas.add(f"{s.name}/{len(s.arguments)}")
            elif h.ast_type == ast.ASTType.Literal and h.atom.ast_type == ast.ASTType.BooleanConstant:
                proib.append("restrição de integridade (`:- ...`) não é permitida")
            else:
                proib.append(f"cabeça não permitida (escolha/agregado/disjunção): {h}")
            for l in stm.body:
                _Coleta()(l)
        elif stm.ast_type in (ast.ASTType.ShowSignature, ast.ASTType.ShowTerm, ast.ASTType.Minimize):
            proib.append(f"diretiva não permitida: {stm}")

    logs: List[str] = []
    try:
        ast.parse_string(programa, cb, logger=lambda _c, m: logs.append(m))
    except RuntimeError:
        linhas = programa.splitlines()
        detalhes = []
        for m in logs:
            pos = re.match(r"<string>:(\d+):(\d+)", m)
            trecho = linhas[int(pos.group(1)) - 1].strip() if pos and int(pos.group(1)) <= len(linhas) else ""
            detalhes.append(f"{m.strip()}  →  linha: `{trecho}`")
        raise RuntimeError("; ".join(detalhes) or "syntax error") from None
    return cabecas, corpo, proib


def violacoes(motor: Motor, aluno) -> List[str]:
    """Violações de contrato num cenário (motor já com o programa de contratos)."""
    r = motor.avaliar(aluno.fatos())
    return [f"{v.arguments[0].string} — testemunha {v.arguments[1]}" for v in r.todos("violacao")]


def com_contratos(motor: Motor, grupo: Grupo) -> Motor:
    m = Motor(arquivos=[])
    m.blocos, m.normas = list(motor.blocos), dict(motor.normas)
    m._add(f"%! _contrato | (contrato) | contratos de saída\n{grupo.contratos}", "contrato", None)
    return m


def verificar(programa: str, grupo: Grupo, base: Motor, cenarios,
              contratos: bool = True) -> List[str]:
    erros: List[str] = []
    try:
        cabecas, corpo, proib = _assinaturas(programa)
    except RuntimeError as e:
        return [f"erro de sintaxe do clingo: {e}"]
    erros += proib
    for s in grupo.saidas:
        if s not in cabecas:
            erros.append(f"o predicado de saída {s} não é definido")
    conhecidos = _ENTRADA | set(grupo.upstream) | cabecas | set(grupo.saidas)
    for p in sorted(corpo - conhecidos):
        erros.append(f"o predicado {p} é usado mas nunca é definido nem é de entrada "
                     "(no ASP ele seria sempre falso)")
    redefinidos = cabecas & _ENTRADA
    for p in sorted(redefinidos):
        erros.append(f"o predicado de entrada {p} não pode ser redefinido")
    if erros:
        return erros
    motor = combinar(base, grupo, programa)
    for i, aluno in enumerate(cenarios):
        try:
            r = motor.avaliar(aluno.fatos())
        except (RuntimeError, ValueError) as e:
            erros.append(f"falha ao executar no cenário {i}: {e}")
            break
        if r.avisos:
            erros.append("operação aritmética indefinida (termo não numérico numa conta; "
                         f"o átomo é descartado em silêncio): {r.avisos[0]}")
            break
    if erros or not (contratos and grupo.contratos):
        return erros
    mc, vistos = com_contratos(motor, grupo), set()
    for aluno in cenarios:
        for v in violacoes(mc, aluno):
            msg = v.split(" — ")[0]
            if msg in vistos:
                continue
            vistos.add(msg)
            erros.append(f"contrato violado: {v}. Fatos do cenário: "
                         + ". ".join(aluno.fatos())[:1500])
    return erros


def combinar(base: Motor, grupo: Grupo, programa: str) -> Motor:
    """Formalização manual sem os rótulos do grupo + programa autoformalizado."""
    m = Motor(arquivos=[])
    m.blocos = [(r, c) for r, c in base.blocos if r not in set(grupo.rotulos_manuais)]
    m.normas = {k: v for k, v in base.normas.items() if k not in set(grupo.rotulos_manuais)}
    m._add(programa, f"auto:{grupo.nome}", None)
    return m


def autoformalizar(grupo: Grupo, modelo: str, base: Motor, cenarios,
                   max_tentativas: int = 3, contratos: bool = True) -> Formalizacao:
    prompt = PROMPT.format(
        texto=grupo.texto(), entrada=VOCABULARIO_ENTRADA,
        upstream="\n".join(f"  {v}" for v in grupo.upstream.values()) or "  (nenhum)",
        saidas="\n".join(f"  {k}: {v}" for k, v in grupo.saidas.items()),
    )
    msgs = [{"role": "user", "content": prompt}]
    f = Formalizacao(grupo.nome, modelo, None, False)
    for _ in range(max_tentativas):
        t0 = time.time()
        resp = _chat(modelo, msgs)
        prog = extrair_programa(resp)
        erros = verificar(prog, grupo, base, cenarios, contratos)
        f.tentativas.append(Tentativa(prog, erros, round(time.time() - t0, 1)))
        f.programa = prog
        if not erros:
            f.valida = True
            break
        msgs += [{"role": "assistant", "content": resp},
                 {"role": "user", "content": REPARO.format(erros="\n".join(f"- {e}" for e in erros[:12]))}]
    return f
