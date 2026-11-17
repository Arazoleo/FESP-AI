"""
Estado do(a) estudante → fatos do motor de normas.

Vocabulário de ENTRADA (o que as regras podem consultar; a autoformalização
recebe esta mesma lista):

  matricula(C, P)          UC C (código, string) cursada no período P
  carga(C, H)              carga horária da UC, em horas
  grupo(C, G)              fixa | eletiva | interdisciplinar | outro
  natureza(C, N)           tcc | estagio | ac  (quando aplicável)
  freq(C, P, F)            frequência em % (inteiro)
  freq_minima_ppc(C, F)    frequência mínima própria fixada no PPC
  nota10(C, P, N)          nota FINAL registrada ×10 (5,9 → 59)
  media10(C, P, M)         média antes do exame ×10 (cenários "e se")
  exame10(C, P, E)         nota do exame ×10
  situacao(C, P, S)        registro oficial: aprovado | reprovado | cumprido |
                           nao_cumprido | em_curso | aproveitamento | outro
  em_rer(C, P)             matrícula em Regime Especial de Recuperação
  uc_pratica(C)            UC exclusivamente prática
  rer_vedado(C)            UC que a Comissão não lista como cursável em RER
  prereq(A, B)             A é pré-requisito de B (Knowledge Graph)
  ingresso(P0)             período de ingresso
  ano_ingresso(A)
  periodo_atual(P)
  integral | parcial       regime do curso
  duracao_minima(D)        duração mínima do curso em semestres (PPC)
  trancamento(P, T)        regular | especial | administrativo
  transferido_no_ano(A)
  processo_disciplinar
  horas(Comp, H)           carga cumprida por componente
  exigido(Comp, H)         carga exigida por componente (matriz ATIVA, SIIU)

Período P = ano*2 + (semestre-1): 2023/1 → 4046, 2023/2 → 4047.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

VOCABULARIO_ENTRADA = __doc__.split("Vocabulário de ENTRADA")[1].split("Período P")[0]


def periodo(ano: int, semestre: int) -> int:
    return ano * 2 + (semestre - 1)


def periodo_de(ano_sem: str) -> Optional[int]:
    m = re.match(r"\s*(\d{4})\s*/\s*([12])", ano_sem or "")
    return periodo(int(m.group(1)), int(m.group(2))) if m else None


def periodo_hoje(hoje: Optional[date] = None) -> int:
    hoje = hoje or date.today()
    return periodo(hoje.year, 1 if hoje.month <= 7 else 2)


def rotulo_periodo(p: int) -> str:
    return f"{p // 2}/{p % 2 + 1}"


def _q(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _slug(s: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", (s or "").lower())
                if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_") or "outro"


@dataclass
class Cursada:
    codigo: str
    periodo: int
    carga: int
    grupo: str = "outro"
    freq: Optional[int] = None
    nota: Optional[float] = None      # nota final registrada
    media: Optional[float] = None     # média antes do exame (cenário)
    exame: Optional[float] = None
    situacao: Optional[str] = None
    rer: bool = False
    natureza: Optional[str] = None    # tcc | estagio | ac


@dataclass
class Aluno:
    ano_ingresso: int
    semestre_ingresso: int = 1
    periodo_atual: Optional[int] = None
    integral: bool = True
    duracao_minima: Optional[int] = None
    cursadas: List[Cursada] = field(default_factory=list)
    trancamentos: List[Tuple[int, str]] = field(default_factory=list)
    transferido_no_ano: Optional[int] = None
    processo_disciplinar: bool = False
    horas: Dict[str, int] = field(default_factory=dict)
    exigido: Dict[str, int] = field(default_factory=dict)
    prereqs: List[Tuple[str, str]] = field(default_factory=list)
    uc_pratica: List[str] = field(default_factory=list)
    rer_vedado: List[str] = field(default_factory=list)
    freq_minima_ppc: Dict[str, int] = field(default_factory=dict)

    def fatos(self) -> List[str]:
        f: List[str] = []
        p0 = periodo(self.ano_ingresso, self.semestre_ingresso)
        f += [f"ingresso({p0})", f"ano_ingresso({self.ano_ingresso})",
              f"periodo_atual({self.periodo_atual or periodo_hoje()})",
              "integral" if self.integral else "parcial"]
        if self.duracao_minima:
            f.append(f"duracao_minima({self.duracao_minima})")
        for c in self.cursadas:
            uc = _q(c.codigo)
            f += [f"matricula({uc},{c.periodo})", f"carga({uc},{c.carga})",
                  f"grupo({uc},{c.grupo})"]
            if c.natureza:
                f.append(f"natureza({uc},{c.natureza})")
            if c.freq is not None:
                f.append(f"freq({uc},{c.periodo},{int(c.freq)})")
            for nome, v in (("nota10", c.nota), ("media10", c.media), ("exame10", c.exame)):
                if v is not None:
                    f.append(f"{nome}({uc},{c.periodo},{round(v * 10)})")
            if c.situacao:
                f.append(f"situacao({uc},{c.periodo},{_slug(c.situacao)})")
            if c.rer:
                f.append(f"em_rer({uc},{c.periodo})")
        for p, tipo in self.trancamentos:
            f.append(f"trancamento({p},{tipo})")
        if self.transferido_no_ano:
            f.append(f"transferido_no_ano({self.transferido_no_ano})")
        if self.processo_disciplinar:
            f.append("processo_disciplinar")
        for comp, h in self.horas.items():
            f.append(f"horas({_slug(comp)},{int(h)})")
        for comp, h in self.exigido.items():
            f.append(f"exigido({_slug(comp)},{int(h)})")
        for a, b in self.prereqs:
            f.append(f"prereq({_q(a)},{_q(b)})")
        f += [f"uc_pratica({_q(c)})" for c in self.uc_pratica]
        f += [f"rer_vedado({_q(c)})" for c in self.rer_vedado]
        f += [f"freq_minima_ppc({_q(c)},{v})" for c, v in self.freq_minima_ppc.items()]
        return list(dict.fromkeys(f))


# ------------------------------------------- adaptador do histórico real

_GRUPOS = {"121": "fixa", "102": "eletiva", "182": "interdisciplinar"}
_SITUACOES = {"APROVADO": "aprovado", "REPROVADO": "reprovado", "CUMPRIDO": "cumprido",
              "NÃO CUMPRIDO": "nao_cumprido", "NAO CUMPRIDO": "nao_cumprido",
              "EM CURSO": "em_curso"}


def aluno_de_historico(dados: Dict, periodo_atual: Optional[int] = None,
                       duracao_minima: Optional[int] = None,
                       exigido: Optional[Dict[str, int]] = None) -> Aluno:
    """Converte a saída de `historico.parsear_historico` em `Aluno`.

    O histórico não traz o semestre de ingresso nem trancamentos; esses
    campos ficam com o padrão (1º semestre, nenhum) e podem ser completados
    pela conversa.
    """
    cursadas = []
    for d in dados.get("disciplinas", []):
        p = periodo_de(d.get("ano_sem", ""))
        if p is None:
            continue
        sit = (d.get("situacao") or "").upper()
        cursadas.append(Cursada(
            codigo=str(d["codigo"]), periodo=p, carga=int(d.get("ch") or 0),
            grupo=_GRUPOS.get(str(d.get("grupo")), "outro"),
            freq=d.get("freq"), nota=d.get("nota"),
            situacao=_SITUACOES.get(sit, _slug(sit)),
        ))
    curso = (dados.get("curso") or "").upper()
    horas = {k: v for k, v in (dados.get("horas") or {}).items() if k != "total"}
    return Aluno(
        ano_ingresso=dados.get("ano_ingresso") or min((c.periodo for c in cursadas), default=periodo_hoje()) // 2,
        periodo_atual=periodo_atual, integral="NOTURNO" not in curso,
        duracao_minima=duracao_minima, cursadas=cursadas, horas=horas,
        exigido=exigido or {},
    )
