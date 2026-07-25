"""
Crawler dos sites do campus UNIFESP São José dos Campos.

Escopos rastreados (ver SCOPES):
  - campus.unifesp.br/sjc/  — site institucional (template Joomla/Gantry,
    container `com-content-article__body`);
  - dae-sjc.unifesp.br/     — DAE / Divisão de Assuntos Educacionais
    (Google Sites: container `role="main"`, corte no `<footer`).

Descobre as páginas seguindo os links internos a partir das seeds (BFS),
extrai título + corpo de cada página e guarda um corpus local em cache
(JSON). Esse corpus alimenta o WebSjcAgent, que responde perguntas sobre
qualquer parte dos sites citando a fonte.

Educado por padrão: User-Agent próprio, timeout, delay entre requisições,
limite de páginas/profundidade e cache em disco (não re-rastreia a cada boot).
"""

import os
import re
import json
import time
import logging
from collections import deque
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Optional

import requests

logger = logging.getLogger("fespai.crawler")

BASE = "https://campus.unifesp.br"
# (domínio, prefixo de path) aceitos pelo crawler; URLs fora disso são descartadas.
SCOPES = [
    ("campus.unifesp.br", "/sjc/"),
    ("dae-sjc.unifesp.br", "/"),
]
SEEDS = [
    f"{BASE}/sjc/",
    f"{BASE}/sjc/mapa-do-site",
    "https://dae-sjc.unifesp.br/inicio",
    "https://dae-sjc.unifesp.br/materiais",
]

USER_AGENT = "FESP-AI/1.0 (assistente academico UNIFESP ICT; +https://campus.unifesp.br/sjc)"
TIMEOUT = 12

# Diretórios/arquivos técnicos e binários que não são conteúdo.
_SKIP_DIR = re.compile(
    r"/(templates|modules|plugins|media|images|component|components|cache|administrator|api|libraries)/",
    re.IGNORECASE,
)
_SKIP_EXT = re.compile(
    r"\.(css|js|png|jpe?g|gif|svg|webp|ico|pdf|docx?|xlsx?|pptx?|zip|rar|mp4|mp3|avi)(\?|$)",
    re.IGNORECASE,
)

_BODY_MAX = 8000      # corpo guardado por página SEM headings (fallback)
_SECTION_MAX = 6000   # corpo guardado por seção de página longa
_MAX_SECTIONS = 60    # limite de seções por página (proteção)
_MIN_TEXT = 80        # texto mínimo para valer uma entrada no corpus

DEFAULT_CACHE = os.path.join(
    os.getenv("FESPAI_DATA_DIR", "./chroma_db_unifesp"), "sjc_crawl.json"
)


def _canonical(url: str) -> Optional[str]:
    """Normaliza para path sem query/fragment; retorna None se fora dos SCOPES."""
    p = urlparse(url)
    host = p.netloc or "campus.unifesp.br"
    path = p.path or "/"
    for domain, prefix in SCOPES:
        if host == domain and (path.startswith(prefix) or path == prefix.rstrip("/")):
            break
    else:
        return None
    if _SKIP_DIR.search(path) or _SKIP_EXT.search(path):
        return None
    # Artigos de notícia são cobertos pelo agente de Notícias (RSS ao vivo);
    # não duplicar no corpus institucional. Mantém só a página-índice /sjc/noticias.
    if host == "campus.unifesp.br" and re.match(r"^/sjc/noticias/.+", path):
        return None
    if path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")
    return f"https://{host}{path}"


def _extract_title(html: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
    if not m:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not m:
        return ""
    t = re.sub(r"<[^>]+>", " ", m.group(1))
    t = re.sub(r"\s+", " ", t).strip()
    # remove sufixo "- UNIFESP" do <title>
    return re.sub(r"\s*[-|]\s*UNIFESP.*$", "", t, flags=re.IGNORECASE).strip()


def _article_region(html: str) -> str:
    """Isola o HTML do corpo principal (Joomla/Gantry do campus ou Google Sites da DAE)."""
    m = (
        re.search(r'com-content-article__body"?\s*>', html)
        or re.search(r'class="[^"]*item-page[^"]*"\s*>', html)
        or re.search(r'unifesp-article-introtext"?\s*>', html)
        # Google Sites (dae-sjc.unifesp.br): conteúdo no container role="main"
        or re.search(r'role="main"[^>]*>', html)
    )
    if not m:
        return ""
    rest = html[m.end():]
    cut = re.search(r"g-content g-particle|<footer|id=\"g-footer\"|class=\"g-footer\"", rest)
    if cut:
        rest = rest[:cut.start()]
    return rest


def _html_to_text(fragment: str) -> str:
    """Converte um fragmento de HTML em texto plano normalizado."""
    t = re.sub(r"<script.*?</script>", " ", fragment, flags=re.DOTALL)
    t = re.sub(r"<style.*?</style>", " ", t, flags=re.DOTALL)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&nbsp;?", " ", t)
    t = re.sub(r"&amp;", "&", t)
    t = re.sub(r"&[a-z]+;", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _extract_body(html: str) -> str:
    """Extrai o corpo inteiro da página (fallback para páginas sem headings)."""
    rest = _html_to_text(_article_region(html))
    if len(rest) > _BODY_MAX:
        rest = rest[:_BODY_MAX].rsplit(" ", 1)[0] + "…"
    return rest


_HEADING_RE = re.compile(r"<h([23])[^>]*>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)


def _slugify(titulo: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", titulo.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")


def _extract_sections(html: str) -> List[Dict]:
    """
    Divide o corpo em seções por h2/h3, uma entrada por seção.

    Páginas de curso do campus (ex.: BCT) têm dezenas de seções em abas e
    acordeões (apresentação, ingresso, matriz curricular, FAQ...) que somam
    muito mais que _BODY_MAX — sem o split, tudo depois do corte era perdido.

    Retorna [] quando a página tem menos de 2 headings (usar _extract_body).
    Cada seção: {"titulo": str ("" para a introdução), "texto": str, "anchor": str}.
    """
    region = _article_region(html)
    if not region:
        return []
    matches = list(_HEADING_RE.finditer(region))
    if len(matches) < 2:
        return []

    sections: List[Dict] = []
    intro = _html_to_text(region[: matches[0].start()])
    if len(intro) > _MIN_TEXT:
        sections.append({"titulo": "", "texto": intro[:_SECTION_MAX], "anchor": ""})

    for i, m in enumerate(matches):
        titulo = _html_to_text(m.group(2))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(region)
        texto = _html_to_text(region[m.start():end])
        if len(texto) <= _MIN_TEXT:
            continue
        # Abas/acordeões do template usam ids "rlta-<slug>" — usar como âncora
        slug = _slugify(titulo)
        anchor = f"rlta-{slug}" if slug and f'id="rlta-{slug}"' in region else ""
        sections.append({
            "titulo": titulo,
            "texto": texto[:_SECTION_MAX],
            "anchor": anchor,
        })
        if len(sections) >= _MAX_SECTIONS:
            break
    return sections


def _secao(url: str) -> str:
    p = urlparse(url)
    parts = [x for x in p.path.split("/") if x]
    if p.netloc == "campus.unifesp.br" or not p.netloc:
        return parts[1] if len(parts) >= 2 else "sjc"
    # Outros domínios (ex.: dae-sjc.unifesp.br): prefixo do domínio + 1ª parte
    # do path -> "dae-materiais", "dae-estagios", "dae-inicio"...
    prefixo = re.sub(r"-sjc$", "", p.netloc.split(".")[0])
    return f"{prefixo}-{parts[0]}" if parts else prefixo


def _internal_links(html: str, base_url: str) -> List[str]:
    out = []
    for href in re.findall(r'href="([^"#]+)"', html):
        canon = _canonical(urljoin(base_url, href))
        if canon:
            out.append(canon)
    return out


def crawl_sjc(
    max_pages: int = 400,
    max_depth: int = 3,
    delay: float = 0.4,
    cache_path: str = DEFAULT_CACHE,
    save: bool = True,
) -> List[Dict]:
    """
    Rastreia o site /sjc em BFS e retorna a lista de páginas
    {url, titulo, secao, texto}. Salva o corpus em cache (JSON) se `save`.
    """
    visited = set()
    queue = deque((s, 0) for s in SEEDS)
    pages: List[Dict] = []
    fetched = 0
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    while queue and fetched < max_pages:
        url, depth = queue.popleft()
        canon = _canonical(url)
        if not canon or canon in visited:
            continue
        visited.add(canon)
        try:
            resp = session.get(canon, timeout=TIMEOUT)
            if resp.status_code != 200 or "html" not in resp.headers.get("Content-Type", "").lower():
                continue
            html = resp.text
        except Exception as e:
            logger.warning("[crawler] falha em %s: %s", canon, e)
            continue
        fetched += 1

        titulo_pagina = _extract_title(html) or canon
        secao = _secao(canon)

        # Páginas longas com headings viram uma entrada por seção — sem isso,
        # tudo além de _BODY_MAX (matriz curricular, FAQs...) era descartado.
        secoes = _extract_sections(html)
        if secoes:
            for s in secoes:
                titulo = (
                    f"{titulo_pagina} — {s['titulo']}" if s["titulo"] else titulo_pagina
                )
                url_secao = f"{canon}#{s['anchor']}" if s["anchor"] else canon
                pages.append({
                    "url": url_secao,
                    "titulo": titulo,
                    "secao": secao,
                    "texto": s["texto"],
                })
        else:
            texto = _extract_body(html)
            if texto and len(texto) > _MIN_TEXT:
                pages.append({
                    "url": canon,
                    "titulo": titulo_pagina,
                    "secao": secao,
                    "texto": texto,
                })

        if depth < max_depth:
            for link in _internal_links(html, canon):
                if link not in visited:
                    queue.append((link, depth + 1))

        time.sleep(delay)

    logger.info(
        "[crawler] %d entradas de %d páginas (%d visitadas)",
        len(pages), fetched, len(visited),
    )
    if save and pages:
        _save_cache(pages, cache_path)
    return pages


def _save_cache(pages: List[Dict], cache_path: str) -> None:
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "pages": pages}, f, ensure_ascii=False)
    except Exception as e:
        logger.warning("[crawler] não consegui salvar cache: %s", e)


def load_cache(cache_path: str = DEFAULT_CACHE) -> Optional[Dict]:
    """Carrega o corpus do cache: {ts, pages} ou None."""
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
