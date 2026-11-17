"""
Planejamento contrafactual com prova: "e se eu reprovar em X, quanto atraso?".

A matriz do curso e os pré-requisitos vêm do KG; o histórico do aluno vem do
parser real; as regras de aprovação são as do regulamento (res246_2023.lp) e
as de progressão estão em progressao.lp. Tudo roda num programa só, então o
atraso previsto carrega a cadeia inteira: o artigo que reprovou, o
pré-requisito que bloqueia, a oferta que empurra para o ano seguinte.

Cada pergunta "e se" é a MESMA avaliação com um fato de hipótese a mais
(hipotese_reprova / hipotese_nao_cursa / hipotese_tranca); o atraso é a
diferença entre as duas formaturas previstas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .estado import Aluno, _q, rotulo_periodo
from .motor import REGRAS_DIR, Motor, Resultado

PROGRESSAO_LP = REGRAS_DIR.parent / "progressao.lp"
_STATUS = {"aprovado", "reprovado", "reprovado_nota", "reprovado_frequencia",
           "reprovado_sem_exame"}


def motor_planejamento() -> Motor:
    return Motor(arquivos=sorted(REGRAS_DIR.glob("*.lp")) + [PROGRESSAO_LP])


# ------------------------------------------------------------------ dados

@dataclass
class Matriz:
    curso: str
    termo: Dict[str, int]                 # id da UC -> termo
    nome: Dict[str, str]                  # id da UC -> nome para exibir
    prereqs: List[Tuple[str, str]]        # (pré-requisito, UC)

    def fatos(self) -> List[str]:
        f = [f"uc_matriz({_q(u)},{t})" for u, t in self.termo.items()]
        f += [f"prereq({_q(a)},{_q(b)})" for a, b in self.prereqs]
        return f


def matriz_do_kg(kg, curso: str) -> Optional[Matriz]:
    """UCs fixas do curso por termo + pré-requisitos entre elas (KG)."""
    termos = kg.get_todos_termos_do_curso(curso)
    if not termos:
        return None
    termo, nome, no = {}, {}, {}
    for t, discs in termos.items():
        try:
            t = int(str(t).split()[0])
        except ValueError:
            continue
        for d in discs:
            n = d.get("nome") or ""
            uid = kg._normalize_text(n)
            if not uid or uid.startswith("eletiva") or uid in termo and termo[uid] <= t:
                continue
            termo[uid], nome[uid] = t, n
            node = kg._find_node(n, "disciplina")
            if node:
                no[node] = uid
    prereqs = []
    for a, b, dados in kg.graph.edges(data=True):
        if dados.get("relacao") == "PREREQUISITO_DE" and a in no and b in no and a != b:
            prereqs.append((no[a], no[b]))
    return Matriz(curso, termo, nome, sorted(set(prereqs)))


def vincular_historico(kg, matriz: Matriz, dados: Dict) -> Dict[str, str]:
    """código do histórico -> id da UC na matriz (por nome, via grounding)."""
    vinculo = {}
    for d in dados.get("disciplinas", []):
        uid = kg._normalize_text(d.get("nome", ""))
        if uid not in matriz.termo:
            node = kg._find_node(d.get("nome", ""), "disciplina")
            uid = kg._normalize_text(kg.graph.nodes[node].get("nome", "")) if node else ""
        if uid in matriz.termo:
            vinculo[str(d["codigo"])] = uid
    return vinculo


def fatos_plano(aluno: Aluno, matriz: Matriz, vinculo: Dict[str, str],
                hipoteses: Optional[List[str]] = None) -> List[str]:
    atual = aluno.periodo_atual
    f = aluno.fatos() + matriz.fatos()
    f += [f"uc_codigo({_q(c)},{_q(u)})" for c, u in vinculo.items()]
    if atual is None:
        atual = int(next(x for x in f if x.startswith("periodo_atual("))[14:-1])
    f.append(f"inicio_plano({atual + 1})")
    return f + list(hipoteses or [])


# ------------------------------------------------------------------ plano

@dataclass
class Plano:
    formatura: Optional[int]
    cursa: Dict[str, int]
    nao_planejavel: List[str]
    estoura_prazo: bool
    resultado: Resultado
    hipoteses: List[str] = field(default_factory=list)

    def premissas(self) -> List[str]:
        """Suposições (não normas) usadas na prova da formatura prevista."""
        r = self.resultado
        alvo = next(iter(r.todos("formatura_matriz")), None)
        if alvo is None:
            return []
        vistos, saida, pilha = set(), [], [alvo]
        while pilha:
            a = pilha.pop()
            if a in vistos or a not in r.justificativas:
                continue
            vistos.add(a)
            j = r._melhor(a)
            n = r.normas.get(j.rotulo)
            if n and n.dispositivo.startswith("(premissa"):
                rot = n.dispositivo.strip("()").split(":", 1)[1].strip()
                if rot not in saida:
                    saida.append(rot)
            pilha.extend(p for p in j.premissas if p.name != "nao")
        return saida


def planejar(motor: Motor, fatos: List[str]) -> Plano:
    r = motor.avaliar(fatos)
    cursa = {a.arguments[0].string: a.arguments[1].number for a in r.todos("cursa")}
    return Plano(
        formatura=r.valor("formatura_matriz"),
        cursa=cursa,
        nao_planejavel=[a.arguments[0].string for a in r.todos("nao_planejavel")],
        estoura_prazo=bool(r.todos("estoura_prazo")),
        resultado=r,
        hipoteses=[f for f in fatos if f.startswith("hipotese_")],
    )


def cadeia_critica(plano: Plano, matriz: Matriz,
                   uc: Optional[str] = None) -> List[Tuple[str, int, str, str]]:
    """Por que a UC (por padrão, a que fecha a formatura) não sai antes:
    [(uc, período, motivo, causa)]. Olha a última oferta ANTERIOR possível
    (mesma paridade e não antes do semestre ideal) e diz o que a impediu:
    hipotese (a reprovação suposta), prereq (segue a cadeia pela causa),
    reprova_em_curso, ou oferta (é a primeira oferta possível)."""
    r = plano.resultado
    if uc is None:
        if plano.formatura is None:
            return []
        uc = sorted(u for u, p in plano.cursa.items() if p == plano.formatura)[0]
    slots = {a.arguments[0].number for a in r.todos("slot")}
    ing = r.valor("ingresso")
    hip = {(a.arguments[0].string, a.arguments[1].number) for a in r.todos("hipotese_nao_cursa")}
    reprova = {a.arguments[0].string for a in r.todos("hipotese_reprova")}
    bloqueios: Dict[Tuple[str, int], List[str]] = {}
    for a in r.todos("bloqueada"):
        bloqueios.setdefault((a.arguments[0].string, a.arguments[1].number), []).append(
            a.arguments[2].string)

    def possivel(u, q):
        t = matriz.termo[u]
        return q in slots and (q + t) % 2 == 1 and (ing is None or q >= ing + t - 1)

    cadeia, vistos = [], set()
    while uc and uc not in vistos and uc in plano.cursa:
        vistos.add(uc)
        p = plano.cursa[uc]
        antes = [q for q in slots if q < p and possivel(uc, q)]
        if not antes:
            cadeia.append((uc, p, "reprova_em_curso" if uc in reprova else "oferta", ""))
            break
        q = max(antes)
        if (uc, q) in hip:
            cadeia.append((uc, p, "hipotese", str(q)))
            break
        if (uc, q) not in bloqueios:
            cadeia.append((uc, p, "oferta", ""))
            break
        # o pré-requisito que sai por último é o que segura a UC
        causa = max(bloqueios[(uc, q)], key=lambda b: plano.cursa.get(b, 10 ** 6))
        cadeia.append((uc, p, "prereq", causa))
        uc = causa
    return cadeia


# ------------------------------------------------------------ contrafactual

@dataclass
class Contrafactual:
    pergunta: str
    base: Plano
    hipotese: Plano
    efeito: str                   # "atrasa" | "nao_atrasa" | "ja_concluida" | "fora_da_matriz"

    @property
    def atraso(self) -> Optional[int]:
        if self.base.formatura is None or self.hipotese.formatura is None:
            return None
        return self.hipotese.formatura - self.base.formatura


def e_se_reprovar(motor: Motor, fatos_base: List[str], plano_base: Plano,
                  matriz: Matriz, uc: str) -> Contrafactual:
    """Reprovação em `uc`: se está em curso, vira pendente; se ainda vai ser
    cursada, não conta no período planejado e volta na próxima oferta."""
    r = plano_base.resultado
    if uc not in matriz.termo:
        return Contrafactual(uc, plano_base, plano_base, "fora_da_matriz")
    em_curso = r.tem("em_curso", uc)
    if not em_curso and uc not in plano_base.cursa:
        return Contrafactual(uc, plano_base, plano_base, "ja_concluida")
    hip = (f"hipotese_reprova({_q(uc)})" if em_curso
           else f"hipotese_nao_cursa({_q(uc)},{plano_base.cursa[uc]})")
    plano_h = planejar(motor, fatos_base + [hip])
    cf = Contrafactual(uc, plano_base, plano_h, "nao_atrasa")
    if cf.atraso is None or cf.atraso > 0:
        cf.efeito = "atrasa"
    return cf


def folgas(motor: Motor, fatos_base: List[str], plano_base: Plano) -> Dict[str, int]:
    """Quantos semestres a formatura atrasa se cada UC planejada escorregar
    uma oferta. 0 = tem folga; > 0 = UC crítica."""
    out = {}
    for uc, p in plano_base.cursa.items():
        h = planejar(motor, fatos_base + [f"hipotese_nao_cursa({_q(uc)},{p})"])
        if h.formatura is None or plano_base.formatura is None:
            out[uc] = 99
        else:
            out[uc] = h.formatura - plano_base.formatura
    return out


# --------------------------------------------------------------- resposta

def responder_e_se(cf: Contrafactual, matriz: Matriz) -> Dict:
    """Texto determinístico + as afirmações que ele faz (para o contrato de
    resposta: um texto reescrito por LLM tem de manter estes valores)."""
    nome = lambda u: matriz.nome.get(u, u)  # noqa: E731
    uc = nome(cf.pergunta)
    afirm: Dict = {"uc": uc, "efeito": cf.efeito}
    if cf.efeito == "fora_da_matriz":
        return {"texto": f"{uc} não está entre as UCs fixas da matriz do {matriz.curso}; "
                         f"reprovar nela não muda a previsão das obrigatórias.",
                "afirmacoes": afirm}
    if cf.efeito == "ja_concluida":
        return {"texto": f"Pelo seu histórico você já concluiu {uc}, então essa "
                         f"reprovação não se aplica.", "afirmacoes": afirm}
    fb, fh = cf.base.formatura, cf.hipotese.formatura
    afirm.update(formatura_base=rotulo_periodo(fb) if fb else None,
                 formatura_hipotese=rotulo_periodo(fh) if fh else None,
                 atraso=cf.atraso)
    linhas = []
    if fh is None:
        linhas.append(f"Se reprovar em {uc}, não consigo fechar a matriz dentro do "
                      f"horizonte planejado: {', '.join(nome(u) for u in cf.hipotese.nao_planejavel)}.")
    elif cf.atraso == 0:
        linhas.append(f"Se reprovar em {uc}, sua previsão de concluir as obrigatórias "
                      f"continua em {rotulo_periodo(fh)}: dá para refazê-la sem atrasar.")
    else:
        linhas.append(f"Se reprovar em {uc}, as obrigatórias passam de {rotulo_periodo(fb)} "
                      f"para {rotulo_periodo(fh)}: atraso de {cf.atraso} semestre(s).")
        cadeia = cadeia_critica(cf.hipotese, matriz)
        passos = []
        for u, p, motivo, causa in cadeia:
            t = matriz.termo[u]
            oferta = f"oferta anual: {'1º' if t % 2 else '2º'} semestre, termo {t}"
            if motivo == "prereq":
                passos.append(f"{nome(u)} ({rotulo_periodo(p)}) depende de {nome(causa)}")
            elif motivo == "hipotese":
                passos.append(f"reprovando em {nome(u)} em {rotulo_periodo(int(causa))}, "
                              f"ela só volta em {rotulo_periodo(p)} ({oferta})")
            elif motivo == "reprova_em_curso":
                passos.append(f"reprovando agora em {nome(u)}, ela só volta em "
                              f"{rotulo_periodo(p)} ({oferta})")
            else:
                passos.append(f"{nome(u)} entra em {rotulo_periodo(p)} ({oferta})")
        if passos:
            linhas.append("Por quê: " + "; ".join(passos) + ".")
        afirm["cadeia"] = [(nome(u), rotulo_periodo(p), m, nome(c) if c else "")
                           for u, p, m, c in cadeia]
    cascata = [(u, cf.base.cursa[u], p) for u, p in sorted(cf.hipotese.cursa.items(), key=lambda x: x[1])
               if u in cf.base.cursa and cf.base.cursa[u] != p and u != cf.pergunta]
    if cascata:
        linhas.append("Também mudam: " + "; ".join(
            f"{nome(u)} {rotulo_periodo(a)} → {rotulo_periodo(b)}" for u, a, b in cascata) + ".")
    afirm["cascata"] = [(nome(u), rotulo_periodo(a), rotulo_periodo(b)) for u, a, b in cascata]
    if cf.hipotese.estoura_prazo:
        linhas.append("Atenção: com esse atraso a previsão passa do prazo máximo de "
                      "integralização (Art. 151).")
        afirm["estoura_prazo"] = True
    # só os que mexem no plano: a classificação aprovado/reprovado de UCs
    antigos = sorted({an["momento_rotulo"] for an in cf.base.resultado.anacronismos
                      if not an["corroborado"] and an["atomo"].name in _STATUS})
    if antigos:
        linhas.append(f"Atenção: há registros de {', '.join(antigos)}, anteriores à Res. 246/2023 "
                      f"(em vigor desde 2024/1); o regimento da época não está formalizado, "
                      f"então confira esses resultados no histórico oficial.")
        afirm["anacronismos"] = antigos
    premissas = cf.hipotese.premissas()
    if premissas:
        linhas.append("Supondo: " + "; ".join(premissas) + ".")
    afirm["premissas"] = premissas
    return {"texto": "\n".join(linhas), "afirmacoes": afirm}


def prazo_por_leitura(motor: Motor, fatos: List[str]) -> Dict:
    """Prazo máximo e último semestre permitido em cada leitura declarada da
    Portaria 566; `diverge` diz se a resposta depende da interpretação."""
    por = motor.avaliar_leituras(fatos, "port566")
    out = {l: {"prazo_maximo": r.valor("prazo_maximo"),
               "ultimo_semestre": r.valor("ultimo_semestre_permitido"),
               "descricao": dict(motor.leituras["port566"])[l]}
           for l, r in por.items()}
    return {"leituras": out,
            "diverge": len({v["prazo_maximo"] for v in out.values()}) > 1}
