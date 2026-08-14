"""
Testes de regressão do site_crawler - seccionamento de páginas longas.

Motivação: a página do BCT (campus.unifesp.br/sjc/graduacao/cursos/
bacharelado-interdisciplinar-em-ciencia-e-tecnologia) tem ~74KB de corpo com
dezenas de seções (matriz curricular, ingresso, FAQ...); o extrator antigo
cortava em 8000 chars e perdia tudo o que vinha depois.

Executa offline com HTML sintético no mesmo template Joomla/Gantry do campus.
"""

import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location("site_crawler", ROOT / "src/site_crawler.py")
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

GREEN, RED, BOLD, RESET = "\033[92m", "\033[91m", "\033[1m", "\033[0m"
_passed, _failed = 0, 0


def check(desc, cond, detail=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"{GREEN}✓{RESET} {desc}")
    else:
        _failed += 1
        print(f"{RED}✗ {desc}{RESET}" + (f" - {detail}" if detail else ""))


def _page(body: str) -> str:
    return (
        "<html><head><title>Curso X - UNIFESP</title></head><body>"
        "<h1>Curso X</h1>"
        f'<div class="com-content-article__body">{body}</div>'
        '<footer id="g-footer">rodape</footer></body></html>'
    )


LONGA = _page(
    "<p>" + ("Introducao do curso. " * 10) + "</p>"
    '<h3 id="rlta-sobre-o-curso">Sobre o curso</h3>'
    "<p>" + ("Descricao geral do curso com bastante texto. " * 20) + "</p>"
    "<h3>Matriz curricular</h3>"
    "<table><tr><td>Calculo I</td><td>72h</td></tr>"
    "<tr><td>Algoritmos</td><td>72h</td></tr></table>"
    "<p>" + ("Detalhes das unidades curriculares fixas e eletivas. " * 20) + "</p>"
    "<h3>1. Quantas horas para integralizar?</h3>"
    "<p>" + ("Sao 2400 horas no total para o curso integral. " * 5) + "</p>"
)

CURTA = _page("<p>" + ("Pagina simples sem headings. " * 10) + "</p>")


print(f"{BOLD}── Seccionamento de página longa ──{RESET}")
secs = sc._extract_sections(LONGA)
titulos = [s["titulo"] for s in secs]
check("página com headings gera múltiplas seções", len(secs) == 4, f"{len(secs)} seções: {titulos}")
check("introdução (antes do 1º heading) é preservada", secs and secs[0]["titulo"] == "")
check("seção 'Matriz curricular' existe", "Matriz curricular" in titulos)
check(
    "conteúdo da tabela da matriz está na seção",
    any("Calculo I" in s["texto"] and "Algoritmos" in s["texto"] for s in secs),
)
check(
    "âncora rlta-<slug> detectada quando o id existe",
    any(s["anchor"] == "rlta-sobre-o-curso" for s in secs),
    str([s["anchor"] for s in secs]),
)
check(
    "seção sem id correspondente fica sem âncora",
    next(s for s in secs if s["titulo"] == "Matriz curricular")["anchor"] == "",
)
check(
    "FAQ vira seção própria",
    any("integralizar" in s["titulo"] for s in secs),
)

print(f"\n{BOLD}── Fallback para página sem headings ──{RESET}")
check("página curta sem headings não gera seções", sc._extract_sections(CURTA) == [])
body = sc._extract_body(CURTA)
check("_extract_body continua funcionando no fallback", "Pagina simples" in body)

print(f"\n{BOLD}── Corte por seção, não por página ──{RESET}")
gigante = _page(
    "<h3>A</h3><p>" + ("a" * 10000) + "</p><h3>B</h3><p>" + ("b" * 10000) + "</p>"
)
secs = sc._extract_sections(gigante)
check(
    "seções longas viram partes (nada é truncado nem descartado)",
    len(secs) == 4 and all(len(s["texto"]) <= sc._SECTION_MAX for s in secs)
    and sum(len(s["texto"]) for s in secs) >= 20000,
    f"{len(secs)} seções, tamanhos {[len(s['texto']) for s in secs]}",
)
check(
    "partes ganham sufixo e mantêm a âncora da seção",
    secs[1]["titulo"].endswith("(parte 2)") and secs[1]["anchor"] == secs[0]["anchor"],
    str([(s['titulo'], s['anchor']) for s in secs[:2]]),
)

print(f"\n{BOLD}── Multi-domínio (dae-sjc.unifesp.br, Google Sites) ──{RESET}")
check(
    "_canonical aceita URL da DAE",
    sc._canonical("https://dae-sjc.unifesp.br/materiais") == "https://dae-sjc.unifesp.br/materiais",
    str(sc._canonical("https://dae-sjc.unifesp.br/materiais")),
)
check(
    "_canonical mantém escopo /sjc do campus",
    sc._canonical("https://campus.unifesp.br/sjc/graduacao") == "https://campus.unifesp.br/sjc/graduacao",
)
check(
    "_canonical rejeita domínio fora dos SCOPES",
    sc._canonical("https://unifesp.br/campus/sjc/apresentacao-bct") is None,
)
check(
    "_canonical rejeita PDF também na DAE",
    sc._canonical("https://dae-sjc.unifesp.br/docs/manual.pdf") is None,
)
check(
    "secao da DAE ganha prefixo do domínio",
    sc._secao("https://dae-sjc.unifesp.br/materiais") == "dae-materiais",
    sc._secao("https://dae-sjc.unifesp.br/materiais"),
)
check(
    "secao do campus continua sem prefixo",
    sc._secao("https://campus.unifesp.br/sjc/graduacao/cursos") == "graduacao",
)

GSITES = (
    "<html><head><title>dae-sjc - Materiais de Apoio</title></head><body>"
    '<div role="navigation">menu lateral</div>'
    '<div class="tyJCtd mGzaTb" role="main" tabindex="0">'
    "<h1>MATERIAIS DE APOIO</h1>"
    "<h3>1 - Dicas para ingressantes</h3>"
    "<p>" + ("Dicas de organizacao dos estudos para quem chega ao BCT. " * 5) + "</p>"
    "<h3>4 - Quadro Geral da Graduação</h3>"
    '<p><a href="https://docs.google.com/spreadsheets/d/xyz">CLIQUE AQUI E ACESSE '
    "O QUADRO GERAL DA GRADUAÇÃO</a> " + ("com todas as unidades curriculares. " * 5) + "</p>"
    "</div><footer>rodape do google sites</footer></body></html>"
)
gsecs = sc._extract_sections(GSITES)
check(
    "template Google Sites (role=main) gera seções por h3",
    len(gsecs) == 2 and "Quadro Geral" in gsecs[1]["titulo"],
    f"{len(gsecs)} seções: {[s['titulo'] for s in gsecs]}",
)
check(
    "texto âncora dos materiais (links externos) fica no texto da seção",
    any("CLIQUE AQUI E ACESSE O QUADRO GERAL" in s["texto"] for s in gsecs),
)
check(
    "rodapé do Google Sites é cortado",
    all("rodape" not in s["texto"] for s in gsecs),
)

print(f"\n{BOLD}── _slugify ──{RESET}")
check(
    "slug remove acentos e pontuação",
    sc._slugify("Transferência interna e externa") == "transferencia-interna-e-externa",
    sc._slugify("Transferência interna e externa"),
)

print(f"\n{BOLD}{_passed} passed, {_failed} failed{RESET}")
sys.exit(1 if _failed else 0)
