"""
Motor de normas: regulamentos formalizados em ASP (clingo), com prova e crença.

Cada regra vem anotada com o dispositivo que a originou:

    %! art148_I | Art. 148, I | É vedado o trancamento no primeiro ano do curso.
    impedimento_trancar(art148_I) :- ingresso(P0), periodo_atual(P), P - P0 < 2.

O motor reescreve cada regra `H :- B.` acrescentando `_why(Rotulo, H, (b1,...))
:- B.` (transformação no AST do clingo, não por texto), então TODA conclusão sai
com a cadeia de dispositivos e fatos que a sustentam — vale igualmente para
regras escritas à mão e para regras autoformalizadas por LLM.

Crença: cada norma tem um intervalo [l, u] (1,1 para a formalização curada;
painel/testes para a aprendida). Uma conclusão herda o elo mais fraco da sua
melhor prova (Gödel: min ao longo da prova, max entre provas alternativas),
a mesma semântica do PyReasonEngine. Fatos do histórico valem [1, 1].
Literais negados (negação por falha) entram na prova como `nao(...)` e não
movem a crença: o histórico é tratado como completo para o que declara.

Vigência (tempo): `%@ vigencia | <rotulo ou *> | <início AAAA/S> | <fim ou -> |
<nota>` diz desde quando a norma vale (`*` = todas as normas do arquivo).
Cada conclusão tem um MOMENTO: o período do fato que ela classifica
(aprovado(C, P) ⟶ P) ou, se for direito/estado presente, o período atual.
Norma usada fora da sua vigência é ANACRONISMO: o resultado é registrado e o
limite inferior da crença cai para 0 (a norma vigente à época não está
formalizada), salvo quando o registro oficial do histórico confirma.

Leituras (ambiguidade): `%? <ambiguidade> | <leitura> | <descrição>` declara
interpretações alternativas de um dispositivo; as regras de cada uma são
guardadas por `leitura(<ambiguidade>, <leitura>)`. A primeira é a padrão;
`avaliar_leituras` roda todas e expõe onde a resposta depende da leitura.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import clingo
from clingo import ast

REGRAS_DIR = Path(__file__).resolve().parent / "regras"
_ANOTACAO = re.compile(r"^%!\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*$")
_VIGENCIA = re.compile(r"^%@\s*vigencia\s*\|\s*([^|]+?)\s*\|\s*(\d{4})/([12])\s*\|"
                       r"\s*(?:(\d{4})/([12])|-)\s*\|\s*(.*?)\s*$")
_LEITURA = re.compile(r"^%\?\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(.+?)\s*$")

# Argumento que carrega o período, nos predicados de entrada (estado.py).
PERIODO_ARG = {"matricula": 1, "freq": 1, "nota10": 1, "media10": 1, "exame10": 1,
               "situacao": 1, "em_rer": 1, "trancamento": 0, "ingresso": 0,
               "periodo_atual": 0}
# Registro oficial que confirma a classificação de um evento passado.
_CORROBORA = {"aprovado": {"aprovado", "cumprido"},
              "reprovado": {"reprovado"}, "reprovado_nota": {"reprovado"},
              "reprovado_frequencia": {"reprovado"}, "reprovado_sem_exame": {"reprovado"}}
_WHY = "_why"
_WHY_EL = "_why_el"
_ANONIMA = re.compile(r"(?<![A-Za-z0-9_])_(?![A-Za-z0-9_])")


@dataclass
class Norma:
    rotulo: str
    dispositivo: str
    texto: str
    fonte: str = ""
    intervalo: Tuple[float, float] = (1.0, 1.0)
    vigencia: Optional[Tuple[int, Optional[int], str]] = None   # (início, fim, nota)

    @property
    def auxiliar(self) -> bool:
        return self.dispositivo.startswith("(")


@dataclass
class Justificativa:
    rotulo: str
    premissas: List[clingo.Symbol]


@dataclass
class Resultado:
    atomos: List[clingo.Symbol]
    justificativas: Dict[clingo.Symbol, List[Justificativa]]
    crenca: Dict[clingo.Symbol, Tuple[float, float]]
    normas: Dict[str, Norma]
    fatos: set = field(default_factory=set)
    avisos: List[str] = field(default_factory=list)
    anacronismos: List[Dict] = field(default_factory=list)
    leitura: Dict[str, str] = field(default_factory=dict)

    def tem(self, nome: str, *args) -> bool:
        return any(self._casa(a, nome, args) for a in self.atomos)

    def todos(self, nome: str) -> List[clingo.Symbol]:
        return [a for a in self.atomos if a.name == nome]

    def valor(self, nome: str) -> Optional[int]:
        """Primeiro argumento do átomo unário `nome(X)` (ex.: prazo_maximo)."""
        for a in self.todos(nome):
            if len(a.arguments) == 1:
                return a.arguments[0].number
        return None

    def explicar(self, atomo, profundidade: int = 6) -> str:
        if isinstance(atomo, str):
            atomo = clingo.parse_term(atomo)
        linhas: List[str] = []
        self._explicar(atomo, 0, profundidade, set(), linhas)
        return "\n".join(linhas)

    def _explicar(self, a, nivel, prof, vistos, linhas):
        pad = "  " * nivel
        if a.name == "nao" and len(a.arguments) == 1:
            linhas.append(f"{pad}- não consta: {a.arguments[0]}")
            return
        if a not in self.crenca:
            linhas.append(f"{pad}- {a}  não se segue das normas e dos fatos")
            return
        l, u = self.crenca[a]
        if a in self.fatos or a not in self.justificativas:
            linhas.append(f"{pad}- {a}  (fato do histórico)")
            return
        j = self._melhor(a)
        n = self.normas.get(j.rotulo)
        rot = f"{n.dispositivo}: {n.texto}" if n else j.rotulo
        linhas.append(f"{pad}- {a}  [{l:.2f}, {u:.2f}]  ⟸ {rot}")
        for an in self.anacronismos:
            if an["atomo"] == a and an["rotulo"] == j.rotulo:
                linhas.append(f"{pad}  ⚠ norma fora de vigência em {an['momento_rotulo']} "
                              f"(vale desde {an['inicio_rotulo']}){'; ' + an['nota'] if an['nota'] else ''}")
        if a in vistos or nivel >= prof:
            return
        vistos = vistos | {a}
        for p in j.premissas:
            self._explicar(p, nivel + 1, prof, vistos, linhas)

    def _melhor(self, a) -> Justificativa:
        js = self.justificativas[a]
        return max(js, key=lambda j: self._forca(j))

    def _forca(self, j: Justificativa) -> float:
        l = self.normas[j.rotulo].intervalo[0] if j.rotulo in self.normas else 1.0
        for p in j.premissas:
            if p.name != "nao":
                l = min(l, self.crenca.get(p, (1.0, 1.0))[0])
        return l

    def dispositivos(self, atomo) -> List[str]:
        """Dispositivos citados na prova de `atomo` (para a resposta ao aluno)."""
        if isinstance(atomo, str):
            atomo = clingo.parse_term(atomo)
        vistos, saida, pilha = set(), [], [atomo]
        while pilha:
            a = pilha.pop()
            if a in vistos or a not in self.justificativas:
                continue
            vistos.add(a)
            j = self._melhor(a)
            n = self.normas.get(j.rotulo)
            if n and not n.dispositivo.startswith("(") and n.dispositivo not in saida:
                saida.append(n.dispositivo)
            pilha.extend(p for p in j.premissas if p.name != "nao")
        return saida

    @staticmethod
    def _casa(a, nome, args) -> bool:
        if a.name != nome or (args and len(a.arguments) != len(args)):
            return False
        return all(str(x) == str(y) or (y.type == clingo.SymbolType.String and x == y.string)
                   for x, y in zip(args, a.arguments))


# ------------------------------------------------------------------ carga

def ler_normas(texto: str, fonte: str = "",
               intervalos: Optional[Dict[str, Tuple[float, float]]] = None
               ) -> Tuple[List[Tuple[str, str]], Dict[str, Norma]]:
    """Divide o programa em blocos por anotação. Devolve [(rotulo, codigo)]."""
    intervalos = intervalos or {}
    blocos: List[Tuple[str, List[str]]] = [("_sem_rotulo", [])]
    normas: Dict[str, Norma] = {}
    vigencias: Dict[str, Tuple[int, Optional[int], str]] = {}
    for linha in texto.splitlines():
        v = _VIGENCIA.match(linha.strip())
        if v:
            rot, a0, s0, a1, s1, nota = v.groups()
            fim = int(a1) * 2 + int(s1) - 1 if a1 else None
            vigencias[rot] = (int(a0) * 2 + int(s0) - 1, fim, nota)
            continue
        m = _ANOTACAO.match(linha.strip())
        if m:
            rot, disp, txt = m.groups()
            normas[rot] = Norma(rot, disp, txt, fonte, intervalos.get(rot, (1.0, 1.0)))
            blocos.append((rot, []))
        else:
            blocos[-1][1].append(linha)
    for rot, n in normas.items():
        if not n.auxiliar:
            n.vigencia = vigencias.get(rot, vigencias.get("*"))
    return [(r, "\n".join(ls)) for r, ls in blocos if "\n".join(ls).strip()], normas


class _NomeiaAnonimas(ast.Transformer):
    """`_` vira variável nomeada para que cabeça e corpo do `_why` compartilhem
    a ligação (o clingo renomeia cada `_` de forma independente)."""

    def __init__(self):
        self.n = 0

    def visit_Variable(self, v):
        if v.name == "_":
            self.n += 1
            return ast.Variable(v.location, f"WHY_ANON_{self.n}")
        return v


def _positivo(lit) -> bool:
    return (lit.ast_type == ast.ASTType.Literal and lit.sign == ast.Sign.NoSign
            and lit.atom.ast_type == ast.ASTType.SymbolicAtom)


def _preparar(stm):
    """Nomeia as anônimas dos literais positivos (as dos negativos têm de
    continuar anônimas, senão a regra fica insegura)."""
    if stm.ast_type != ast.ASTType.Rule:
        return stm
    t = _NomeiaAnonimas()
    return stm.update(body=[t(l) if _positivo(l) else l for l in stm.body])


def _instrumentar(stm, rotulo: str):
    """Para `H :- B.` devolve `_why(rotulo, H, (premissas)) :- B.`; senão None."""
    if stm.ast_type != ast.ASTType.Rule:
        return None
    head = stm.head
    if head.ast_type != ast.ASTType.Literal or head.atom.ast_type != ast.ASTType.SymbolicAtom:
        return None
    loc = stm.location
    premissas = []
    for lit in stm.body:
        if lit.ast_type != ast.ASTType.Literal or lit.atom.ast_type != ast.ASTType.SymbolicAtom:
            continue  # comparações e agregados: o valor aparece nos átomos ligados
        termo = lit.atom.symbol
        if lit.sign == ast.Sign.Negation:
            if _ANONIMA.search(str(termo)):
                termo = ast.SymbolicTerm(loc, clingo.String(str(termo)))
            termo = ast.Function(loc, "nao", [termo], 0)
        elif lit.sign != ast.Sign.NoSign:
            continue
        premissas.append(termo)
    why = ast.Function(loc, _WHY, [
        ast.SymbolicTerm(loc, clingo.String(rotulo)),
        head.atom.symbol,
        ast.Function(loc, "", premissas, 0),
    ], 0)
    return ast.Rule(loc, ast.Literal(loc, ast.Sign.NoSign, ast.SymbolicAtom(why)), stm.body)


class _Variaveis(ast.Transformer):
    def __init__(self):
        self.nomes = set()

    def visit_Variable(self, v):
        self.nomes.add(v.name)
        return v


class _Renomeia(ast.Transformer):
    def __init__(self, manter, sufixo):
        self.manter, self.sufixo = manter, sufixo

    def visit_Variable(self, v):
        if v.name in self.manter or v.name == "_":
            return v
        return ast.Variable(v.location, f"{v.name}_{self.sufixo}")


def _nomes(*nos) -> set:
    t = _Variaveis()
    for n in nos:
        t(n)
    return t.nomes


def _instrumentar_agregados(stm, rotulo: str) -> list:
    """Para cada elemento `t : cond` de agregado no corpo, devolve
    `_why_el(rotulo, H, (atomos de cond)) :- B, cond.` — a prova passa a
    listar QUAIS fatos foram contados/somados, não só o total."""
    if stm.ast_type != ast.ASTType.Rule:
        return []
    head = stm.head
    if head.ast_type != ast.ASTType.Literal or head.atom.ast_type != ast.ASTType.SymbolicAtom:
        return []
    loc, extras = stm.location, []
    for i, lit in enumerate(stm.body):
        if lit.ast_type != ast.ASTType.Literal or lit.atom.ast_type != ast.ASTType.BodyAggregate:
            continue
        # variáveis locais ao elemento não podem vazar para fora do agregado
        globais = _nomes(stm.head, *[l for k, l in enumerate(stm.body) if k != i])
        for g in (lit.atom.left_guard, lit.atom.right_guard):
            if g is not None:
                globais |= _nomes(g.term)
        for n, el in enumerate(lit.atom.elements):
            t, r = _NomeiaAnonimas(), _Renomeia(globais, f"EL{i}_{n}")
            cond = [r(t(c)) if _positivo(c) else r(c) for c in el.condition]
            atomos = [c.atom.symbol for c in cond if _positivo(c)]
            if not atomos:
                continue
            why = ast.Function(loc, _WHY_EL, [
                ast.SymbolicTerm(loc, clingo.String(rotulo)), head.atom.symbol,
                ast.Function(loc, "", atomos, 0)], 0)
            extras.append(ast.Rule(loc, ast.Literal(loc, ast.Sign.NoSign, ast.SymbolicAtom(why)),
                                   list(stm.body) + cond))
    return extras


class Motor:
    def __init__(self, arquivos: Optional[Iterable[Path]] = None,
                 programa: Optional[str] = None,
                 intervalos: Optional[Dict[str, Tuple[float, float]]] = None,
                 vigencia: bool = True):
        self.blocos: List[Tuple[str, str]] = []
        self.normas: Dict[str, Norma] = {}
        self.leituras: Dict[str, List[Tuple[str, str]]] = {}
        self.vigencia = vigencia
        self._programa: Optional[list] = None
        self._chave: list = []
        if programa is None and arquivos is None:
            arquivos = sorted(REGRAS_DIR.glob("*.lp"))
        for arq in arquivos or []:
            self._add(Path(arq).read_text(encoding="utf-8"), Path(arq).name, intervalos)
        if programa:
            self._add(programa, "programa", intervalos)

    def _add(self, texto, fonte, intervalos):
        blocos, normas = ler_normas(texto, fonte, intervalos)
        for linha in texto.splitlines():
            m = _LEITURA.match(linha.strip())
            if m:
                amb, leit, desc = m.groups()
                self.leituras.setdefault(amb, []).append((leit, desc))
        self.blocos += blocos
        self.normas.update(normas)
        self._programa = None

    def _compilar(self, logs: List[str]) -> list:
        """AST das normas já instrumentado (prova + agregados), feito uma vez."""
        if getattr(self, "_programa", None) is not None and self._chave == self.blocos:
            return self._programa
        programa: list = []
        for rotulo, codigo in self.blocos:
            def add(stm, rotulo=rotulo):
                stm = _preparar(stm)
                programa.append(stm)
                extra = _instrumentar(stm, rotulo)
                if extra is not None:
                    programa.append(extra)
                programa.extend(_instrumentar_agregados(stm, rotulo))
            ast.parse_string(codigo, add, logger=lambda _c, msg: logs.append(msg))
        self._programa, self._chave = programa, list(self.blocos)
        return programa

    def avaliar(self, fatos: Iterable[str]) -> Resultado:
        """`fatos`: termos ASP sem ponto final, ex. 'matricula("2832",4047)'."""
        fatos = list(fatos)
        escolhidas = {}
        for amb, opcoes in self.leituras.items():
            dada = next((f for f in fatos if f.replace(" ", "").startswith(f"leitura({amb},")), None)
            if dada is None:
                fatos.append(f"leitura({amb},{opcoes[0][0]})")
                escolhidas[amb] = opcoes[0][0]
            else:
                escolhidas[amb] = dada.replace(" ", "")[len(f"leitura({amb},"):-1]
        logs: List[str] = []
        ctl = clingo.Control(["--warn=none", "--warn=operation-undefined"],
                             logger=lambda _c, msg: logs.append(msg))
        try:
            programa = self._compilar(logs)
            with ast.ProgramBuilder(ctl) as b:
                for stm in programa:
                    b.add(stm)
                ast.parse_string("".join(f"{f}.\n" for f in fatos), b.add)
            ctl.ground([("base", [])])
        except RuntimeError as e:
            detalhe = "\n".join(m.strip() for m in logs if m.strip())
            raise RuntimeError(f"{e}: {detalhe}" if detalhe else str(e)) from None

        modelos = []
        with ctl.solve(yield_=True) as h:
            for m in h:
                modelos.append(m.symbols(atoms=True))
                if len(modelos) > 1:
                    break
        if len(modelos) != 1:
            raise ValueError(f"programa sem modelo único ({len(modelos)} modelos): "
                             "normas contraditórias ou negação não estratificada")

        atomos, just, elementos = [], {}, {}
        for s in modelos[0]:
            if s.name == _WHY:
                rot, cab, prem = s.arguments
                just.setdefault(cab, []).append(Justificativa(rot.string, list(prem.arguments)))
            elif s.name == _WHY_EL:
                rot, cab, prem = s.arguments
                elementos.setdefault((rot.string, cab), []).extend(prem.arguments)
            else:
                atomos.append(s)
        for cab, js in just.items():
            for j in js:
                for e in elementos.get((j.rotulo, cab), []):
                    if e not in j.premissas:
                        j.premissas.append(e)
        fatos_simb = {clingo.parse_term(f) for f in fatos}
        anacr = self._anacronismos(atomos, just, fatos_simb) if self.vigencia else []
        rebaixar = {(a["atomo"], a["rotulo"]) for a in anacr if not a["corroborado"]}
        crenca = self._propagar(atomos, just, rebaixar)
        r = Resultado(sorted(atomos), just, crenca, self.normas, fatos_simb,
                      anacronismos=anacr, leitura=escolhidas)
        # aritmética sobre termo não numérico: o átomo some sem erro
        r.avisos = [m.strip() for m in logs if "operation undefined" in m]
        return r

    def avaliar_leituras(self, fatos: Iterable[str], ambiguidade: str) -> Dict[str, Resultado]:
        """Uma avaliação por leitura declarada de `ambiguidade`."""
        base = [f for f in fatos if not f.replace(" ", "").startswith(f"leitura({ambiguidade},")]
        return {leit: self.avaliar(base + [f"leitura({ambiguidade},{leit})"])
                for leit, _ in self.leituras.get(ambiguidade, [])}

    @staticmethod
    def divergencia(por_leitura: Dict[str, "Resultado"], predicado: str) -> Optional[Dict[str, List[str]]]:
        """Valores de `predicado` por leitura, ou None se todas concordam."""
        valores = {l: sorted(str(a) for a in r.todos(predicado)) for l, r in por_leitura.items()}
        return valores if len({tuple(v) for v in valores.values()}) > 1 else None

    def _anacronismos(self, atomos, just, fatos) -> List[Dict]:
        """Conclusões derivadas por norma fora da vigência no momento delas."""
        from .estado import rotulo_periodo
        atual = next((f.arguments[0].number for f in fatos if f.name == "periodo_atual"), None)
        situacoes = {(f.arguments[0], f.arguments[1].number): f.arguments[2].name
                     for f in fatos if f.name == "situacao" and len(f.arguments) == 3}
        memo: Dict = {}

        def momento(a, pilha=frozenset()):
            if a in memo:
                return memo[a]
            if a in fatos or a not in just:
                i = PERIODO_ARG.get(a.name)
                m = a.arguments[i].number if i is not None and len(a.arguments) > i else None
            elif a in pilha:
                return None
            else:
                prem = [momento(p, pilha | {a}) for p in just[a][0].premissas if p.name != "nao"]
                dentro = [m for m in prem if m is not None and clingo.Number(m) in a.arguments]
                m = max(dentro) if dentro else atual
            memo[a] = m
            return m

        saida = []
        for cab, js in just.items():
            for j in js:
                n = self.normas.get(j.rotulo)
                if not n or not n.vigencia:
                    continue
                ini, fim, nota = n.vigencia
                m = momento(cab)
                if m is None or (m >= ini and (fim is None or m <= fim)):
                    continue
                sit = (situacoes.get((cab.arguments[0], m))
                       if cab.name in _CORROBORA and len(cab.arguments) >= 2 else None)
                saida.append({
                    "atomo": cab, "rotulo": j.rotulo, "dispositivo": n.dispositivo,
                    "momento": m, "momento_rotulo": rotulo_periodo(m),
                    "inicio": ini, "inicio_rotulo": rotulo_periodo(ini), "nota": nota,
                    "corroborado": bool(sit and sit in _CORROBORA.get(cab.name, ())),
                })
        return saida

    def _propagar(self, atomos, just, rebaixar=frozenset()) -> Dict[clingo.Symbol, Tuple[float, float]]:
        crenca = {a: ((0.0, 0.0) if a in just else (1.0, 1.0)) for a in atomos}
        for _ in range(len(atomos) + 1):
            mudou = False
            for cab, js in just.items():
                melhor_l = melhor_u = 0.0
                for j in js:
                    rl, ru = self.normas[j.rotulo].intervalo if j.rotulo in self.normas else (1.0, 1.0)
                    if (cab, j.rotulo) in rebaixar:
                        rl = 0.0
                    for p in j.premissas:
                        if p.name == "nao":
                            continue
                        pl, pu = crenca.get(p, (1.0, 1.0))
                        rl, ru = min(rl, pl), min(ru, pu)
                    melhor_l, melhor_u = max(melhor_l, rl), max(melhor_u, ru)
                if (melhor_l, melhor_u) != crenca.get(cab):
                    crenca[cab] = (melhor_l, melhor_u)
                    mudou = True
            if not mudou:
                break
        return crenca
