"""
Relatório de Progresso Acadêmico em PDF — inspirado no relatório oficial da
DAE, gerado sob demanda com o histórico carregado na conversa e as regras do
curso (KG + regulamentos). NÃO OFICIAL: nada é armazenado.

Vai além do oficial: audita as Atividades Complementares POR EIXO com os
fatores e tetos do regulamento do curso (o oficial mostra apenas o total).
"""

from datetime import date
from typing import Dict, List, Optional

from fpdf import FPDF

from .ac_auditor import auditar_atividades
from .progresso import auditar_progresso, requisitos_do_curso

CINZA = (229, 229, 229)
VERDE = (217, 234, 211)
AMARELO = (255, 229, 153)
AZUL = (17, 85, 204)
VERMELHO = (204, 0, 0)
TINTA = (30, 30, 30)

EIXOS_NOMES = {
    1: "Eixo 1 - Formação Cidadã, Cultural ou Artística",
    2: "Eixo 2 - Orientação Acadêmica ou Monitoria",
    3: "Eixo 3 - Formação Pessoal, Científica ou Profissional",
}


def _limpo(s) -> str:
    return str(s or "").replace("–", "-").replace("—", "-") \
        .replace("→", "->").replace("≥", ">=").replace("·", "-") \
        .encode("latin-1", "replace").decode("latin-1")


class _PDF(FPDF):
    def __init__(self):
        super().__init__(format="A4")
        self.set_auto_page_break(auto=True, margin=18)

    def header(self):
        self.set_font("helvetica", "B", 10)
        self.set_text_color(*TINTA)
        self.cell(0, 5, "Universidade Federal de São Paulo", align="C",
                  new_x="LMARGIN", new_y="NEXT")
        self.set_font("helvetica", "", 8.5)
        self.cell(0, 4, "Campus São José dos Campos", align="C",
                  new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 4, "Assistente FESP-AI (documento de acompanhamento)",
                  align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def footer(self):
        self.set_y(-14)
        self.set_font("helvetica", "I", 7.5)
        self.set_text_color(120, 120, 120)
        self.cell(0, 4, "Gerado pelo FESP-AI - NÃO OFICIAL. O relatório oficial "
                        "é emitido pela DAE (https://dae-sjc.unifesp.br/).",
                  align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 4, f"Página {self.page_no()}", align="C")

    def titulo(self):
        self.set_font("helvetica", "B", 13)
        self.set_text_color(*TINTA)
        self.cell(0, 8, "RELATÓRIO DE PROGRESSO ACADÊMICO", align="C",
                  new_x="LMARGIN", new_y="NEXT")
        self.set_font("helvetica", "", 9)
        self.cell(0, 5, date.today().strftime("%d/%m/%Y"), align="C",
                  new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def secao(self, texto: str):
        self.ln(2)
        self.set_font("helvetica", "B", 10.5)
        self.set_text_color(*TINTA)
        self.cell(0, 7, _limpo(texto), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def linha_info(self, rotulo, valor, rotulo2="", valor2=""):
        self.set_font("helvetica", "B", 9)
        self.set_fill_color(*CINZA)
        self.cell(28, 7, _limpo(rotulo), border=1, fill=True)
        self.set_font("helvetica", "", 9)
        if rotulo2:
            self.cell(92, 7, _limpo(valor), border=1)
            self.set_font("helvetica", "B", 9)
            self.cell(30, 7, _limpo(rotulo2), border=1, fill=True)
            self.set_font("helvetica", "", 9)
            self.cell(0, 7, _limpo(valor2), border=1, new_x="LMARGIN", new_y="NEXT")
        else:
            self.cell(0, 7, _limpo(valor), border=1, new_x="LMARGIN", new_y="NEXT")

    def cabecalho_tabela(self, item_rotulo="Item", largura=110):
        self.set_font("helvetica", "B", 9)
        self.set_fill_color(*CINZA)
        self.cell(largura, 7, _limpo(item_rotulo), border=1, fill=True, align="C")
        self.set_fill_color(*VERDE)
        self.cell(40, 7, "Cumprido", border=1, fill=True, align="C")
        self.set_fill_color(*AMARELO)
        self.cell(0, 7, "A cumprir", border=1, fill=True, align="C",
                  new_x="LMARGIN", new_y="NEXT")

    def linha_tabela(self, item, feito, falta, largura=110, negrito=False):
        self.set_font("helvetica", "B" if negrito else "", 9)
        self.set_text_color(*TINTA)
        self.cell(largura, 7, _limpo(item), border=1)
        self.set_text_color(*AZUL)
        self.cell(40, 7, _limpo(feito), border=1, align="C")
        self.set_text_color(*VERMELHO)
        self.cell(0, 7, _limpo(falta), border=1, align="C",
                  new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*TINTA)

    def paragrafo(self, texto, tamanho=9):
        self.set_font("helvetica", "", tamanho)
        self.set_text_color(*TINTA)
        self.multi_cell(0, 5, _limpo(texto), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)


def gerar_relatorio_graduacao(kg, curso: str, dados: Dict,
                              nome: Optional[str] = None,
                              ra: Optional[str] = None) -> bytes:
    """
    kg: knowledge graph; curso: sigla (BCT...); dados: sessão do histórico
    (parsear_historico + ac_itens registrados na conversa).
    """
    from .historico import aprovadas

    cursadas = aprovadas(dados or {})
    resultado = None
    if cursadas and kg is not None:
        try:
            resultado = auditar_progresso(kg, curso, cursadas, historico=dados)
        except Exception:
            resultado = None
    quadro = (resultado or {}).get("integralizacao")
    req = requisitos_do_curso(curso, (dados or {}).get("curso", ""))

    pdf = _PDF()
    pdf.add_page()
    pdf.titulo()

    # 1 - Identificação
    pdf.secao("1 - IDENTIFICAÇÃO")
    pdf.linha_info("Nome", nome or "-", "RA", ra or "-")
    pdf.linha_info("Curso", (dados or {}).get("curso") or curso,
                   "Ingresso", str((dados or {}).get("ano_ingresso") or "-"))
    cr = (dados or {}).get("cr_geral")
    pdf.linha_info("CR geral", f"{cr}" if cr is not None else "-",
                   "Emitido em", date.today().strftime("%d/%m/%Y"))

    # 2 - Quadro de integralização
    pdf.secao(f"2 - REQUISITOS PARA CONCLUSÃO DO {curso}")
    obs_notas: List[str] = []
    if quadro and quadro.get("componentes"):
        pdf.cabecalho_tabela("Requisito")
        tot_feito = tot_falta = 0
        for c in quadro["componentes"]:
            cumprido = c.get("cumprido")
            exigido = c.get("exigido") or 0
            unidade = c.get("unidade", "h")
            if cumprido is None:
                feito_txt, falta_txt = "-", f"{exigido}{unidade}"
            else:
                falta = max(0, exigido - cumprido)
                feito_txt = f"{int(cumprido)}{unidade}"
                falta_txt = f"{int(falta)}{unidade}"
                tot_feito += int(cumprido) if unidade == "h" else 0
                tot_falta += int(falta) if unidade == "h" else 0
            rotulo = c["nome"]
            if c.get("obs"):
                obs_notas.append(f"{c['nome']}: {c['obs']}")
                rotulo += " *"
            pdf.linha_tabela(rotulo, feito_txt, falta_txt)
        pdf.linha_tabela("Total (em horas)", f"{tot_feito}h", f"{tot_falta}h",
                         negrito=True)
        for nota in obs_notas:
            pdf.ln(1)
            pdf.paragrafo(f"* {nota}", tamanho=8)
    elif req:
        pdf.paragrafo(
            f"O {curso} exige {req['total_h']}h no total. Carregue seu histórico "
            "no chat (botão de upload) para o quadro detalhado cumprido × a cumprir."
        )
        pdf.cabecalho_tabela("Requisito")
        for c in req["criterios"]:
            pdf.linha_tabela(c["expressao"].title(), "-", f"{c['para_total_h']}h")
    else:
        pdf.paragrafo("Curso sem requisitos estruturados; consulte a página do curso.")

    # 3 - Atividades Complementares por eixo (diferencial do FESP-AI)
    itens_ac = (dados or {}).get("ac_itens") or []
    pdf.secao("3 - ATIVIDADES COMPLEMENTARES (SIMULAÇÃO POR EIXO)")
    if itens_ac:
        ac = auditar_atividades(itens_ac, curso=curso)
        validas = ac.get("horas_validas") or {}
        if validas:
            pdf.cabecalho_tabela("Eixo")
            for eixo, horas in sorted(validas.items()):
                nome_eixo = EIXOS_NOMES.get(eixo, f"Eixo {eixo}") \
                    if isinstance(eixo, int) else str(eixo)
                pdf.linha_tabela(nome_eixo, f"{int(horas)}h", "")
        pdf.ln(1)
        pdf.linha_tabela(
            f"Total válido (exigido: {ac['total_exigido']}h)",
            f"{int(ac['total_valido'])}h", f"{int(ac['faltam'])}h", negrito=True,
        )
        for aviso in (ac.get("avisos") or [])[:4]:
            pdf.ln(1)
            pdf.paragrafo(f"! {aviso}", tamanho=8)
        for p in (ac.get("pendencias") or [])[:3]:
            pdf.paragrafo(f"! {p}", tamanho=8)
        pdf.paragrafo(
            "Simulação com os fatores e tetos do regulamento do curso; a "
            "validação oficial é feita pela Comissão de AC em processo próprio (SEI).",
            tamanho=8,
        )
    else:
        pdf.paragrafo(
            "Nenhuma atividade declarada nesta conversa. Liste suas atividades "
            "no chat (ex.: '40h de monitoria, 20h de palestras') e gere o "
            "relatório novamente para a simulação por eixo."
        )

    # 4 - Obrigatórias pendentes (sempre presente, para a numeração não pular)
    pendentes = (resultado or {}).get("pendentes") or []
    pdf.secao("4 - UCs OBRIGATÓRIAS AINDA PENDENTES NA MATRIZ")
    if pendentes:
        for p in pendentes[:14]:
            nome_uc = p.get("nome") if isinstance(p, dict) else str(p)
            termo = f" (termo {p['termo']})" if isinstance(p, dict) and p.get("termo") else ""
            pdf.paragrafo(f"- {nome_uc}{termo}", tamanho=9)
        if len(pendentes) > 14:
            pdf.paragrafo(f"... e mais {len(pendentes) - 14}.", tamanho=8)
    elif resultado:
        pdf.paragrafo(
            "Nenhuma: todas as UCs obrigatórias da matriz constam como aprovadas "
            "no seu histórico. ✓"
        )
    else:
        pdf.paragrafo(
            "Carregue seu histórico no chat para eu conferir as obrigatórias da matriz."
        )

    # 5 - Links
    pdf.secao("5 - LINKS IMPORTANTES")
    pdf.paragrafo("- DAE (relatório oficial de progresso): https://dae-sjc.unifesp.br/")
    pdf.paragrafo("- Secretaria de Graduação: atendimento.secretaria.sjc@unifesp.br")
    pdf.paragrafo("- Páginas dos cursos: https://campus.unifesp.br/sjc/graduacao")

    return bytes(pdf.output())
