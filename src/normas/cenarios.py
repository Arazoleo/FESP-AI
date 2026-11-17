"""
Banco de cenários sintéticos para comparar formalizações.

Gera estudantes aleatórios (semente fixa) concentrados nos limiares que as
normas usam: frequência 74/75/76, média 2,9/3,0/5,9/6,0, exame que fecha
5,95 x 6,0, trancamentos de tipos mistos, ingresso antes, durante e depois
de 2020-2022, cursos integrais e parciais. São só ENTRADAS: a resposta de
referência de uma avaliação de verdade tem de vir de quem aplica a norma.
"""

from __future__ import annotations

import random
from typing import List

from .estado import Aluno, Cursada, periodo

UCS = [f"U{i}" for i in range(1, 11)]


def gerar(n: int = 300, semente: int = 7) -> List[Aluno]:
    rnd = random.Random(semente)
    alunos = []
    for _ in range(n):
        ano, sem = rnd.randint(2016, 2025), rnd.choice([1, 2])
        p0 = periodo(ano, sem)
        atual = p0 + rnd.choice([0, 1, 2, 3, 5, 8, 11, 13, 15, 17])
        pers = list(range(p0, atual + 1))
        tranc = []
        for p in rnd.sample(pers, k=min(len(pers), rnd.choice([0, 0, 1, 2, 3]))):
            tranc.append((p, rnd.choice(["regular", "regular", "especial", "administrativo"])))
        livres = [p for p in pers if p not in {t[0] for t in tranc}] or pers
        # como num histórico real: todo semestre não trancado tem matrícula
        # (semestre vazio seria abandono, Art. 145, IV); o atual pode estar vazio
        chaves = [(u, p) for p in livres if p != atual or rnd.random() < 0.5
                  for u in rnd.sample(UCS, rnd.randint(1, 3))]
        cursadas = []
        for chave in chaves:
            c = Cursada(chave[0], chave[1], rnd.choice([36, 72, 72, 108]),
                        rnd.choice(["fixa", "eletiva", "interdisciplinar"]),
                        freq=rnd.choice([0, 30, 74, 75, 76, 90, 100]))
            if rnd.random() < 0.25:
                c.media = rnd.choice([2.9, 3.0, 4.5, 5.9, 6.0, 8.0])
                c.exame = rnd.choice([None, 7.4, 7.5, 9.0])
            else:
                c.nota = rnd.choice([None, 2.9, 3.0, 4.8, 5.9, 6.0, 7.5, 10.0])
                if c.nota is None and rnd.random() < 0.5:
                    c.situacao = "cumprido"
            c.rer = rnd.random() < 0.08
            if rnd.random() < 0.05:
                c.natureza = rnd.choice(["tcc", "estagio", "ac"])
            if rnd.random() < 0.04:
                c.situacao, c.freq = "aproveitamento", None
            cursadas.append(c)
        exig = {"fixas": rnd.choice([468, 2484]), "eletivas": rnd.choice([252, 432])}
        horas = {k: v + rnd.choice([-40, 0, 0, 10]) for k, v in exig.items()}
        if rnd.random() < 0.5:
            exig["ac"] = 144
            if rnd.random() < 0.6:
                horas["ac"] = rnd.choice([100, 144, 200])
        alunos.append(Aluno(
            ano_ingresso=ano, semestre_ingresso=sem, periodo_atual=atual,
            integral=rnd.random() < 0.7, duracao_minima=rnd.choice([6, 8, 10]),
            cursadas=cursadas, trancamentos=tranc,
            transferido_no_ano=rnd.choice([None] * 8 + [atual // 2, ano]),
            processo_disciplinar=rnd.random() < 0.05,
            horas=horas, exigido=exig,
            prereqs=[tuple(rnd.sample(UCS, 2)) for _ in range(rnd.randint(0, 4))],
            uc_pratica=rnd.sample(UCS, rnd.choice([0, 0, 1])),
            rer_vedado=rnd.sample(UCS, rnd.choice([0, 0, 1])),
            freq_minima_ppc={rnd.choice(UCS): 85} if rnd.random() < 0.1 else {},
        ))
    return alunos
