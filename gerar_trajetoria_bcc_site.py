"""
Gera markdown_regimentos/trajetoria_academica_bcc_site.md a partir do
expandível "Trajetória acadêmica" da página oficial do BCC no site do campus
(a fonte que a coordenação mantém atualizada, ao contrário do PPC).

Extrai o texto e converte as tabelas de requisitos (núcleos, componentes,
carga horária por grupo de UCs) para tabelas markdown.

Uso: python3 gerar_trajetoria_bcc_site.py
Rodar quando a coordenação atualizar a página; o resultado é commitado.
"""

import html as html_mod
import re
import urllib.request

URL = (
    "https://campus.unifesp.br/sjc/graduacao/cursos/"
    "bacharelado-em-ciencia-da-computacao"
)
UA = {"User-Agent": "FESP-AI/1.0 (assistente academico UNIFESP ICT)"}
SAIDA = "markdown_regimentos/trajetoria_academica_bcc_site.md"


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


def main():
    req = urllib.request.Request(URL, headers=UA)
    pagina = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

    ini = pagina.find('id="rlta-panel-trajetoria-academica"')
    fim = pagina.find('id="rlta-matriz-curricular"')
    if ini < 0 or fim < 0:
        raise SystemExit("ERRO: secao 'Trajetoria academica' nao encontrada - layout mudou?")
    ini = pagina.find(">", ini) + 1
    painel = pagina[ini:fim]
    painel = painel[:painel.rfind("<div")] if "<div" in painel[-200:] else painel

    blocos = []
    pos = 0
    for m in re.finditer(r"<table.*?</table>", painel, re.S):
        antes = _texto(painel[pos:m.start()])
        if len(antes) > 40:
            blocos.append(antes)
        blocos.append(_tabela_md(m.group(0)))
        pos = m.end()
    resto = _texto(painel[pos:])
    if len(resto) > 40:
        blocos.append(resto)

    corpo = "\n\n".join(blocos)
    n_tabelas = corpo.count("|---")
    if n_tabelas < 2 or len(corpo) < 2000:
        raise SystemExit(
            f"ERRO: extracao suspeita ({n_tabelas} tabelas, {len(corpo)} chars) - "
            "verifique o layout da pagina antes de sobrescrever."
        )

    cabecalho = (
        "# Trajetória Acadêmica do BCC - requisitos por grupos de UCs "
        "(página oficial do curso)\n\n"
        "Fonte: expandível \"Trajetória acadêmica\" da página do Bacharelado em "
        "Ciência da Computação no site do campus, mantida pela coordenação do "
        "curso (mais atualizada que o PPC).\n"
        f"URL: {URL}#rlta-trajetoria-academica\n\n"
        "Cada crédito em unidades curriculares equivale a 18 horas.\n\n---\n\n"
    )
    with open(SAIDA, "w") as f:
        f.write(cabecalho + corpo + "\n")
    print(f"{SAIDA}: {len(corpo)} chars, {n_tabelas} tabelas")


if __name__ == "__main__":
    main()
