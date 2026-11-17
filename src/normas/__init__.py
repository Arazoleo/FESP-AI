"""Regulamentos acadêmicos formalizados como normas executáveis (ASP) com prova."""

from .estado import Aluno, Cursada, aluno_de_historico, periodo, rotulo_periodo
from .motor import Motor, Norma, Resultado

__all__ = ["Aluno", "Cursada", "Motor", "Norma", "Resultado",
           "aluno_de_historico", "periodo", "rotulo_periodo"]
