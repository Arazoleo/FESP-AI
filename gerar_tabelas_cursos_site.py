"""
Extrai automaticamente os expandíveis COM TABELAS das páginas oficiais dos
cursos no site do campus (as seções que a coordenação mantém atualizadas, ao
contrário dos PPCs) e gera um markdown por curso em markdown_regimentos/.

Só painéis com <table> entram: prosa já é coberta pelo índice do site; o valor
aqui é preservar a estrutura tabular (o índice achata tabelas em texto).
Autodescoberta: cursos sem tabelas são pulados; se uma página ganhar tabela
nova, a próxima execução captura.

Uso: python3 gerar_tabelas_cursos_site.py
Rodar quando a coordenação atualizar as páginas; o resultado é commitado.
"""

import html as html_mod
import re
import urllib.request

UA = {"User-Agent": "FESP-AI/1.0 (assistente academico UNIFESP ICT)"}
BASE = "https://campus.unifesp.br/sjc/graduacao/cursos"
CURSOS = {
    "bct": ("bacharelado-interdisciplinar-em-ciencia-e-tecnologia",
            "Bacharelado Interdisciplinar em Ciência e Tecnologia (BCT)"),
    "bcc": ("bacharelado-em-ciencia-da-computacao",
            "Bacharelado em Ciência da Computação (BCC)"),
    "bmc": ("bacharelado-em-matematica-computacional",
            "Bacharelado em Matemática Computacional (BMC)"),
    "bbt": ("bacharelado-em-biotecnologia", "Bacharelado em Biotecnologia (BBT)"),
    "eb": ("engenharia-biomedica", "Engenharia Biomédica (EB)"),
    "em": ("engenharia-de-materiais", "Engenharia de Materiais (EM)"),
}


def _texto(trecho: str) -> str:
    limpo = html_mod.unescape(re.sub(r"<[^>]+>", " ", trecho))
    return re.sub(r"\s+", " ", limpo).strip()


def _tabela_md(table_html: str) -> str:
    linhas_md = []
    for i, tr in enumerate(re.findall(r"<tr.*?</tr>", table_html, re.S)):
        celulas = [
            _texto(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
        ]
        if not any(celulas):
            continue
        linhas_md.append("| " + " | ".join(celulas) + " |")
        if i == 0:
            linhas_md.append("|" + "---|" * len(celulas))
    return "\n".join(linhas_md)


def _titulos_dos_botoes(pagina: str) -> dict:
    titulos = {}
    for bm in re.finditer(
        r'<div id="rlta-([a-z0-9-]+)"[^>]*data-rlta-element="button"[^>]*>(.*?)</div>',
        pagina, re.S,
    ):
        titulos[bm.group(1)] = _texto(bm.group(2))
    return titulos


def _painel_para_md(painel_html: str) -> str:
    ini = painel_html.find(">") + 1
    corpo = painel_html[ini:]
    blocos = []
    pos = 0
    for m in re.finditer(r"<table.*?</table>", corpo, re.S):
        antes = _texto(corpo[pos:m.start()])
        if len(antes) > 40:
            blocos.append(antes)
        blocos.append(_tabela_md(m.group(0)))
        pos = m.end()
    resto = _texto(corpo[pos:])
    if len(resto) > 40:
        blocos.append(resto)
    return "\n\n".join(blocos)


def main():
    for sigla, (slug, nome) in CURSOS.items():
        url = f"{BASE}/{slug}"
        req = urllib.request.Request(url, headers=UA)
        try:
            pagina = urllib.request.urlopen(req, timeout=30).read().decode(
                "utf-8", "replace"
            )
        except Exception as e:
            print(f"{sigla.upper()}: ERRO ao buscar ({e}) - pulando")
            continue

        titulos = _titulos_dos_botoes(pagina)
        paineis = list(re.finditer(r'<div id="rlta-panel-([a-z0-9-]+)"', pagina))
        secoes = []
        for i, pm in enumerate(paineis):
            fim = paineis[i + 1].start() if i + 1 < len(paineis) else len(pagina)
            trecho = pagina[pm.start():fim]
            if "<table" not in trecho:
                continue
            slug_sec = pm.group(1)
            titulo = titulos.get(slug_sec) or slug_sec.replace("-", " ").title()
            corpo = _painel_para_md(trecho)
            if corpo.count("|---") < 1 or len(corpo) < 200:
                print(f"{sigla.upper()}: secao '{slug_sec}' suspeita - pulando")
                continue
            secoes.append((titulo, slug_sec, corpo))

        if not secoes:
            print(f"{sigla.upper()}: nenhuma secao com tabela - nada gerado")
            continue

        linhas = [
            f"# {nome} - seções oficiais com tabelas (página do curso no site do campus)",
            "",
            "Fonte: expandíveis da página oficial do curso, mantidos pela",
            "coordenação (mais atualizados que o PPC). Extração automática de",
            "gerar_tabelas_cursos_site.py.",
            f"URL: {url}",
            "",
            "---",
            "",
        ]
        for titulo, slug_sec, corpo in secoes:
            linhas.append(f"## {titulo}")
            linhas.append(f"(âncora: {url}#rlta-{slug_sec})")
            linhas.append("")
            linhas.append(corpo)
            linhas.append("")
        saida = f"markdown_regimentos/secoes_oficiais_{sigla}_site.md"
        with open(saida, "w") as f:
            f.write("\n".join(linhas))
        print(f"{sigla.upper()}: {len(secoes)} secoes -> {saida}")


if __name__ == "__main__":
    main()
