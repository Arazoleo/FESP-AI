"""
Grupos de normas para a autoformalização.

Cada grupo junta os dispositivos de um tema, as conclusões (predicados de
SAÍDA) que a formalização tem de definir e os rótulos da formalização escrita
à mão que ela substitui. Os predicados dos grupos anteriores entram como
vocabulário disponível ("upstream"), então um erro fica atribuído ao grupo
que o cometeu.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]
RES246 = ROOT / "markdown_regimentos/regulamento_cursos_graduacao_resolucao_246_2023.md"

PORTARIA_566_ART27 = (
    "Portaria ProGrad 566/2022, Art. 27º. Todos(as) estudantes matriculados(a) nos anos "
    "de 2020, 2021 e 2022, terão acrescidos dois semestres letivos, ou 1 (um) ano letivo "
    "no caso de cursos anuais, adicionais ao prazo máximo de integralização definido no "
    "Projeto Pedagógico do Curso."
)


@dataclass
class Grupo:
    nome: str
    artigos: List[int]
    saidas: Dict[str, str]                 # "pred/aridade" -> significado
    rotulos_manuais: List[str]
    upstream: Dict[str, str] = field(default_factory=dict)
    texto_extra: str = ""
    # Contratos de saída: propriedades que decorrem do SIGNIFICADO das
    # conclusões (exclusão mútua, totalidade, valor único, faixa), nunca do
    # conteúdo da norma. Cada violação deriva violacao(Mensagem, Testemunha).
    contratos: str = ""

    def texto(self) -> str:
        partes = [artigo(n) for n in self.artigos]
        if self.texto_extra:
            partes.append(self.texto_extra)
        return "\n\n".join(p for p in partes if p)


@lru_cache(maxsize=1)
def _artigos() -> Dict[int, str]:
    txt = RES246.read_text(encoding="utf-8")
    blocos = re.split(r"(?=\*\*Art\. \d+)", txt)
    saida = {}
    for b in blocos:
        m = re.match(r"\*\*Art\. (\d+)", b)
        if m:
            corpo = re.split(r"\n## ", b)[0]
            saida[int(m.group(1))] = re.sub(r"\s*\n\s*", " ", corpo.replace("**", "")).strip()
    return saida


def artigo(n: int) -> str:
    return _artigos().get(n, "")


_AVALIACAO_SAIDAS = {
    "reprovado_frequencia/2": "reprovado_frequencia(C,P): reprovado(a) por frequência na UC C no período P",
    "reprovado_sem_exame/2": "reprovado_sem_exame(C,P): reprovado(a) sem direito a exame",
    "deve_fazer_exame/2": "deve_fazer_exame(C,P): deve se submeter a exame",
    "aprovado/2": "aprovado(C,P): aprovado(a) na UC C no período P",
    "reprovado_nota/2": "reprovado_nota(C,P): reprovado(a) por nota (com frequência mínima)",
}

GRUPOS: List[Grupo] = [
    Grupo(
        "avaliacao", [109, 120, 122, 123],
        dict(_AVALIACAO_SAIDAS),
        ["art109", "art109_pu", "art120_2", "art122_I", "art122_II", "art122_III",
         "art123", "art122_I_rep", "art120_final", "art106_V"],
        contratos="""
violacao("aprovado e reprovado_nota ao mesmo tempo", (C,P)) :- aprovado(C,P), reprovado_nota(C,P).
violacao("aprovado e reprovado_frequencia ao mesmo tempo", (C,P)) :- aprovado(C,P), reprovado_frequencia(C,P).
violacao("reprovado_sem_exame e deve_fazer_exame ao mesmo tempo", (C,P)) :- reprovado_sem_exame(C,P), deve_fazer_exame(C,P).
violacao("reprovado_sem_exame sem reprovado_nota (reprovar sem direito a exame é reprovar por nota)", (C,P)) :- reprovado_sem_exame(C,P), not reprovado_nota(C,P).
contrato_desfecho(C,P) :- aprovado(C,P).
contrato_desfecho(C,P) :- reprovado_nota(C,P).
contrato_desfecho(C,P) :- reprovado_frequencia(C,P).
violacao("nota final registrada (nota10) e frequência sem desfecho: nem aprovado, nem reprovado_nota, nem reprovado_frequencia", (C,P)) :- nota10(C,P,_), freq(C,P,_), not contrato_desfecho(C,P).
""",
        texto_extra=("Observação de dados: o histórico registra a NOTA FINAL (nota10, já com "
                     "exame, se houve). media10/exame10 aparecem só em cenários hipotéticos. "
                     "UCs sem nota com situacao(C,P,cumprido) contam como aprovadas."),
    ),
    Grupo(
        "rer", [124, 128, 129, 130],
        {"pode_rer/1": "pode_rer(C): pode cursar a UC C (reprovação pendente) em Regime Especial de Recuperação",
         "deve_cursar_presencial/1": "deve_cursar_presencial(C): UC C reprovada e pendente deve ser refeita de forma presencial"},
        ["art130", "art124_I", "art124_II", "art124_III", "art129", "art130_3", "art130_rer", "art124"],
        contratos="""
violacao("pode_rer e deve_cursar_presencial ao mesmo tempo (são complementares)", C) :- pode_rer(C), deve_cursar_presencial(C).
violacao("reprovação pendente sem destino: nem pode_rer nem deve_cursar_presencial", C) :- pendente(C), not pode_rer(C), not deve_cursar_presencial(C).
violacao("pode_rer para UC sem reprovação pendente", C) :- pode_rer(C), not pendente(C).
""",
        upstream={**_AVALIACAO_SAIDAS,
                  "reprovado/2": "reprovado(C,P): reprovado(a) por nota ou por frequência",
                  "pendente/1": "pendente(C): UC C reprovada e ainda não aprovada depois",
                  "periodo/1": "periodo(P): período letivo com alguma matrícula"},
    ),
    Grupo(
        "trancamento", [146, 147, 148, 149, 150],
        {"pode_trancar/0": "pode_trancar: o(a) estudante pode pedir trancamento regular de matrícula agora"},
        ["art148_I", "art148_II", "art148_III", "art147_1", "art147"],
        upstream={"ano_atual/1": "ano_atual(A): ano civil do período atual"},
    ),
    Grupo(
        "prazo", [145, 146, 151],
        {"prazo_maximo/1": "prazo_maximo(N): prazo máximo de integralização em semestres, já com acréscimos (sem o caso excepcional do inciso III)",
         "semestres_restantes/1": "semestres_restantes(R): prazo_maximo menos os semestres já computados para integralização, contando o período atual",
         "risco_cancelamento/1": "risco_cancelamento(prazo_excedido) quando excede o prazo máximo; "
                                 "risco_cancelamento(reprovacao_total_frequencia) pelo inciso VIII do Art. 145"},
        ["art151_I", "art151_II", "art151_III", "port566_27", "art151_max", "art146",
         "art151_rest", "art145_VI", "art145_VIII"],
        contratos="""
violacao("prazo_maximo com mais de um valor", (A,B)) :- prazo_maximo(A), prazo_maximo(B), A < B.
violacao("semestres_restantes com mais de um valor", (A,B)) :- semestres_restantes(A), semestres_restantes(B), A < B.
violacao("prazo_maximo menor que a duração mínima do curso", (N,D)) :- prazo_maximo(N), duracao_minima(D), N < D.
contrato_tem_prazo :- prazo_maximo(_).
violacao("prazo_maximo não definido embora duracao_minima seja conhecida", D) :- duracao_minima(D), not contrato_tem_prazo.
contrato_tem_restantes :- semestres_restantes(_).
violacao("semestres_restantes não definido embora prazo_maximo, ingresso e periodo_atual sejam conhecidos", M) :- prazo_maximo(M), ingresso(_), periodo_atual(_), not contrato_tem_restantes.
violacao("risco_cancelamento(prazo_excedido) com semestres_restantes não negativo", R) :- risco_cancelamento(prazo_excedido), semestres_restantes(R), R >= 0.
violacao("semestres_restantes negativo sem risco_cancelamento(prazo_excedido)", R) :- semestres_restantes(R), R < 0, not risco_cancelamento(prazo_excedido).
""",
        upstream={"reprovado_frequencia/2": _AVALIACAO_SAIDAS["reprovado_frequencia/2"],
                  "periodo/1": "periodo(P): período letivo com alguma matrícula",
                  "ano_atual/1": "ano_atual(A): ano civil do período atual"},
        texto_extra=PORTARIA_566_ART27,
    ),
    Grupo(
        "cr", [132, 133, 134, 135, 136],
        {"cr_x1000/1": "cr_x1000(X): CR acumulado ×1000 (inteiro; 7,333 → 7333)"},
        ["art136", "art135_I", "art135_II", "art134"],
        contratos="""
violacao("cr_x1000 com mais de um valor", (A,B)) :- cr_x1000(A), cr_x1000(B), A < B.
violacao("cr_x1000 fora da faixa 0..10000", X) :- cr_x1000(X), X < 0.
violacao("cr_x1000 fora da faixa 0..10000", X) :- cr_x1000(X), X > 10000.
""",
        upstream={"reprovado_frequencia/2": _AVALIACAO_SAIDAS["reprovado_frequencia/2"]},
        texto_extra=("Observação: a fórmula do Art. 134 não foi extraída do PDF; o Art. 133 "
                     "define os indicadores (nota final N e carga horária H de cada UC)."),
    ),
    Grupo(
        "integralizacao", [104, 160],
        {"falta/2": "falta(Comp, D): componente Comp da matriz com D horas abaixo do exigido",
         "apto_colar_grau/0": "apto_colar_grau: todas as exigências de integralização verificáveis estão cumpridas"},
        ["art104", "art160"],
        contratos="""
violacao("apto_colar_grau mas há falta", Comp) :- apto_colar_grau, falta(Comp,_).
violacao("falta com valor não positivo", (Comp,D)) :- falta(Comp,D), D <= 0.
""",
        texto_extra=("Dados: exigido(Comp,H) vem da matriz ATIVA do curso (SIIU); horas(Comp,H) "
                     "é o cumprido. Componente sem horas(Comp,_) registrado não pode ser dado "
                     "como cumprido."),
    ),
]

POR_NOME = {g.nome: g for g in GRUPOS}
