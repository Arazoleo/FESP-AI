"""
Testes do motor de normas (src/normas): a formalização escrita à mão da
Resolução CONSU 246/2023 + Portaria 566/2022 em ASP.

Cada cenário fixa um limiar literal do texto da norma (média 2,9 x 3,0 no
Art. 122; 2 semestres no Art. 147 § 1º; +50%/+75% no Art. 151 ...), e o
backtest confere que as normas reproduzem a situação OFICIAL gravada nos
históricos de exemplo do parser. Executa sem Ollama:

    .venv-normas/bin/python -m pytest test_normas.py -q
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from normas import Aluno, Cursada, Motor, aluno_de_historico, periodo  # noqa: E402

MOTOR = Motor()
P = periodo


def _historico():
    spec = importlib.util.spec_from_file_location("historico", ROOT / "src/historico.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def avaliar(**kw):
    kw.setdefault("ano_ingresso", 2022)
    kw.setdefault("periodo_atual", P(2024, 2))
    return MOTOR.avaliar(Aluno(**kw).fatos())


def uc(cod="100", per=None, carga=72, **kw):
    return Cursada(cod, per or P(2023, 1), carga, **kw)


# ------------------------------------------------------------- Arts. 109-123

def test_frequencia_abaixo_de_75_reprova_mesmo_com_nota_alta():
    r = avaliar(cursadas=[uc(freq=74, nota=9.5)])
    assert r.tem("reprovado_frequencia", "100", P(2023, 1))
    assert not r.tem("aprovado")


def test_frequencia_minima_propria_do_ppc():
    r = avaliar(cursadas=[uc(freq=80, nota=9.0)], freq_minima_ppc={"100": 85})
    assert r.tem("reprovado_frequencia")


def test_limiares_do_art_122():
    r = avaliar(cursadas=[uc("a", freq=80, media=2.9), uc("b", freq=80, media=3.0),
                          uc("c", freq=80, media=5.9), uc("d", freq=80, media=6.0)])
    assert r.tem("reprovado_sem_exame", "a", P(2023, 1))
    assert r.tem("deve_fazer_exame", "b", P(2023, 1))
    assert r.tem("deve_fazer_exame", "c", P(2023, 1))
    assert r.tem("aprovado", "d", P(2023, 1))


def test_exame_art_123_comparacao_exata():
    r = avaliar(cursadas=[uc("a", freq=80, media=4.5, exame=7.4),   # 5,95
                          uc("b", freq=80, media=4.5, exame=7.5)])  # 6,0
    assert r.tem("reprovado_nota", "a", P(2023, 1))
    assert r.tem("aprovado", "b", P(2023, 1))


# --------------------------------------------------------- RER (Arts. 124-130)

def test_rer_possivel_com_uma_reprovacao_por_nota():
    r = avaliar(cursadas=[uc("a", freq=90, nota=4.0), uc("b", freq=90, nota=8.0)])
    assert r.tem("pode_rer", "a")


def test_rer_vedado_para_pre_requisito_art_124_III():
    r = avaliar(cursadas=[uc("a", freq=90, nota=4.0)], prereqs=[("a", "z")])
    assert not r.tem("pode_rer", "a")
    assert r.tem("impedimento_rer", "a", "art124_III")
    assert "Art. 124, III" in r.dispositivos('deve_cursar_presencial("a")')


def test_rer_vedado_com_duas_reprovacoes_por_nota_art_124_II():
    r = avaliar(cursadas=[uc("a", freq=90, nota=4.0), uc("b", freq=90, nota=5.0)])
    assert not r.tem("pode_rer")
    assert r.tem("impedimento_rer", "a", "art124_II")


def test_rer_vedado_por_frequencia_e_uma_unica_vez():
    r = avaliar(cursadas=[uc("a", freq=50, nota=7.0),
                          uc("b", freq=90, nota=4.0),
                          uc("b", per=P(2023, 2), freq=90, nota=5.0, rer=True)])
    assert r.tem("impedimento_rer", "a", "art124_I")
    assert r.tem("impedimento_rer", "b", "art130_3")


def test_reprovacao_ja_recuperada_nao_fica_pendente():
    r = avaliar(cursadas=[uc("a", freq=90, nota=4.0),
                          uc("a", per=P(2023, 2), freq=90, nota=7.0)])
    assert not r.tem("pendente", "a")
    assert not r.tem("deve_cursar_presencial")


# --------------------------------------------------- Trancamento (147-150)

def test_primeiro_ano_nao_tranca():
    r = avaliar(ano_ingresso=2024, periodo_atual=P(2024, 2))
    assert not r.tem("pode_trancar")
    assert r.tem("impedimento_trancar", "art148_I")


def test_limite_de_um_ano_de_trancamento_regular():
    r1 = avaliar(trancamentos=[(P(2023, 1), "regular")])
    assert r1.tem("pode_trancar") and r1.valor("saldo_trancamento") == 1
    r2 = avaliar(trancamentos=[(P(2023, 1), "regular"), (P(2023, 2), "regular")])
    assert not r2.tem("pode_trancar")
    assert r2.tem("impedimento_trancar", "art147_1")


def test_trancamento_especial_e_administrativo_nao_consomem_o_regular():
    r = avaliar(trancamentos=[(P(2023, 1), "especial"), (P(2023, 2), "administrativo")])
    assert r.tem("pode_trancar") and r.valor("saldo_trancamento") == 2


def test_processo_disciplinar_e_transferencia_no_ano():
    assert not avaliar(processo_disciplinar=True).tem("pode_trancar")
    assert not avaliar(transferido_no_ano=2024).tem("pode_trancar")
    assert avaliar(transferido_no_ano=2023).tem("pode_trancar")


# ------------------------------------------------- Prazo (Art. 151 + Port. 566)

def test_prazo_integral_e_parcial_arredonda_para_cima():
    assert avaliar(ano_ingresso=2024, periodo_atual=P(2025, 1),
                   duracao_minima=8).valor("prazo_maximo") == 12
    assert avaliar(ano_ingresso=2024, periodo_atual=P(2025, 1), integral=False,
                   duracao_minima=6).valor("prazo_maximo") == 11  # 10,5 → 11


def test_portaria_566_leitura_literal_matriculados_2020_2022():
    # ingressou em 2018 e estava matriculado em 2020: tem direito pela letra do Art. 27
    assert avaliar(ano_ingresso=2018, periodo_atual=P(2024, 1),
                   duracao_minima=8).valor("prazo_maximo") == 14
    assert avaliar(ano_ingresso=2023, periodo_atual=P(2024, 1),
                   duracao_minima=8).valor("prazo_maximo") == 12


def test_trancamento_nao_conta_no_prazo_e_risco_de_cancelamento():
    base = dict(ano_ingresso=2023, periodo_atual=P(2029, 2), duracao_minima=8)
    r = avaliar(**base)                       # 14 semestres computados > 12
    assert r.tem("risco_cancelamento", "prazo_excedido")
    r = avaliar(**base, trancamentos=[(P(2025, 1), "regular"), (P(2025, 2), "regular")])
    assert r.valor("semestres_restantes") == 0
    assert not r.tem("risco_cancelamento", "prazo_excedido")


def test_cancelamento_por_frequencia_dois_semestres_consecutivos():
    r = avaliar(cursadas=[uc("a", per=P(2023, 1), freq=10), uc("b", per=P(2023, 1), freq=0),
                          uc("c", per=P(2023, 2), freq=20)])
    assert r.tem("risco_cancelamento", "reprovacao_total_frequencia")
    r = avaliar(cursadas=[uc("a", per=P(2023, 1), freq=10), uc("c", per=P(2023, 2), freq=80)])
    assert not r.tem("risco_cancelamento", "reprovacao_total_frequencia")


# ------------------------------------------------------------- CR (132-136)

def test_cr_truncado_e_reprovacao_por_frequencia_vale_zero():
    r = avaliar(cursadas=[uc("a", freq=90, nota=7.0, carga=72),
                          uc("b", freq=90, nota=8.0, carga=36)])
    assert r.valor("cr_x1000") == 7333           # 7,333... truncado
    r = avaliar(cursadas=[uc("a", freq=90, nota=8.0), uc("b", freq=50, nota=9.0)])
    assert r.valor("cr_x1000") == 4000           # 9,0 por frequência conta 0


def test_cr_exclui_tcc_e_aproveitamento():
    r = avaliar(cursadas=[uc("a", freq=90, nota=6.0), uc("t", freq=100, nota=10.0, natureza="tcc"),
                          uc("x", nota=10.0, situacao="aproveitamento")])
    assert r.valor("cr_x1000") == 6000


# ------------------------------------------------------ Integralização (160)

def test_integralizacao_aponta_o_que_falta():
    r = avaliar(horas={"fixas": 2484, "eletivas": 400}, exigido={"fixas": 2484, "eletivas": 432, "ac": 144})
    assert r.tem("falta", "eletivas", 32)
    assert r.tem("a_confirmar", "ac")
    assert not r.tem("apto_colar_grau")
    r = avaliar(horas={"fixas": 2484}, exigido={"fixas": 2484})
    assert r.tem("apto_colar_grau")


# ----------------------------------------------- Prova e crença propagada

def test_prova_cita_dispositivos_e_fatos():
    r = avaliar(trancamentos=[(P(2023, 1), "regular"), (P(2023, 2), "regular")])
    txt = r.explicar("impedimento_trancar(art147_1)")
    assert "Art. 147, § 1º" in txt and "trancamento(4046,regular)" in txt


def test_crenca_da_norma_propaga_pelo_elo_mais_fraco():
    m = Motor(intervalos={"port566_27": (0.6, 0.9)})
    r = m.avaliar(Aluno(ano_ingresso=2018, periodo_atual=P(2024, 1), duracao_minima=8).fatos())
    assert r.crenca[next(a for a in r.todos("prazo_maximo"))] == (0.6, 0.9)
    assert r.crenca[next(a for a in r.todos("prazo_base"))] == (1.0, 1.0)


# --------------------------------------- Backtest contra o registro oficial

def test_normas_reproduzem_a_situacao_oficial_dos_historicos():
    h = _historico()
    fixtures = [v for k, v in vars(sys.modules[__name__]).items() if k.startswith("FIXTURE")]
    for texto in fixtures:
        dados = h.parsear_historico(texto)
        r = MOTOR.avaliar(aluno_de_historico(dados, periodo_atual=P(2025, 2)).fatos())
        assert not r.todos("divergencia_registro"), [str(a) for a in r.todos("divergencia_registro")]
        assert r.todos("aprovado") or r.todos("reprovado")


def test_cr_das_normas_bate_com_o_cr_impresso():
    h = _historico()
    dados = h.parsear_historico(FIXTURE_HISTORICO)
    r = MOTOR.avaliar(aluno_de_historico(dados, periodo_atual=P(2024, 1)).fatos())
    assert abs(r.valor("cr_x1000") / 1000 - dados["cr_geral"]) < 0.05


FIXTURE_HISTORICO = """Curso: INTERDISCIPLINAR EM CIÊNCIA E TECNOLOGIA - NOTURNO
Situação Acadêmica: EM CURSO Coeficiente de Rendimento (CR) Geral: 6.6
ANO/SEM | 2023/1 Coeficiente de Rendimento (CR): 7.5
Unidade Curricular Cod.
Grupo Tipo UC CH CHEXT Crédito Freq.
(%) Conceito Situação
9394 - LÓGICA DE PROGRAMAÇÃO
Docente: FULANA DE TAL Titulação: Doutorado 121 DF 72 - 4 94 8,0 APROVADO
2609 - PROBABILIDADE E ESTATÍSTICA
Docente: BELTRANO SILVA Titulação: Doutorado 182 DE 72 18 4 86 7,0 APROVADO
ANO/SEM | 2023/2 Coeficiente de Rendimento (CR): 4.8
2832 - ALGORITMOS E ESTRUTURAS DE DADOS I
Docente: CICLANA SOUZA Titulação: Doutorado 102 DE 72 - 4 97 4,8 REPROVADO
RESUMO
Totais de carga horária por tipo de UC
FIXAS 72
ELETIVAS 72
Total de horas cumpridas pelo estudante (teórica + prática) 144
Carga horária extensionista: 18 horas do total cumprido pelo(a) estudante.
"""

FIXTURE_HISTORICO_2025 = """Curso: INTERDISCIPLINAR EM CIÊNCIA E TECNOLOGIA - INTEGRAL
Ano de ingresso: 2021 Forma de Ingresso: SISTEMA DE SELEÇÃO UNIFICADA
Situação Acadêmica: EM CURSO Coeficiente de Rendimento (CR) Geral: 7.0
ANO/SEM | 2021/1 Coeficiente de Rendimento (CR): 0
Unidade Curricular Cod.
Grupo Tipo UC CH Crédito Freq.
(%) Conceito Situação
9394 - LÓGICA DE PROGRAMAÇÃO
Docente: FULANA DE TAL Titulação: Doutorado 121 DF 72 4 - CUMPRIDO
5704 - QUÍMICA GERAL
Docente: BELTRANA SILVA Titulação: Doutorado 121 DF 72 4 NÃO CUMPRIDO
ANO/SEM | 2022/1 Coeficiente de Rendimento (CR): 7.0
2609 - PROBABILIDADE E ESTATÍSTICA
Docente: CICLANO SOUZA Titulação: Doutorado 182 DE 72 4 90 7,0 APROVADO
ANO/SEM | 2025/2 Coeficiente de Rendimento (CR): 0
2831 - BANCO DE DADOS
Docente: FULANO LIMA Titulação: Doutorado 102 DE 72 4 EM CURSO
RESUMO
Totais de carga horária por tipo de UC
ATIVIDADES COMPLEMENTARES 312
FIXAS 72
ELETIVAS 72
Total de horas cumpridas pelo estudante (teórica + prática) 456
Carga horária extensionista: 96 horas do total cumprido pelo(a) estudante.
"""


def test_explicar_atomo_ausente_nao_finge_ser_fato():
    r = avaliar(processo_disciplinar=True)
    assert "não se segue" in r.explicar("pode_trancar")
    assert "fato do histórico" in r.explicar("impedimento_trancar(art148_III)")


def test_atividade_cumprida_com_frequencia_insuficiente_nao_aprova():
    # bug da formalização manual achado pelos contratos de saída (Art. 106, V x Art. 120 § 2º)
    r = avaliar(cursadas=[uc(freq=0, situacao="cumprido")])
    assert not r.tem("aprovado") and r.tem("reprovado_frequencia")
