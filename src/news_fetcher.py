"""
Busca de notícias oficiais da UNIFESP (campus São José dos Campos / ICT).

Fonte primária: feed RSS do Joomla (robusto, estruturado). Fallback: raspagem
leve do HTML. Resultado em cache (TTL) para não martelar o site nem somar
latência a cada pergunta.

Esta é uma fonte EXTERNA - o conteúdo não passa pela validação simbólica do KG.
Por isso o agente sempre cita fonte + data + link ao responder.
"""

import re
import time
import logging
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger("fespai.news")

BASE_URL = "https://campus.unifesp.br"
NEWS_PATH = "/sjc/noticias"
NEWS_URL = f"{BASE_URL}{NEWS_PATH}"
RSS_URL = f"{NEWS_URL}?format=feed&type=rss"

USER_AGENT = "FESP-AI/1.0 (assistente academico UNIFESP ICT; +https://campus.unifesp.br)"
TIMEOUT = 10
DEFAULT_TTL = 1200
ARTICLE_TTL = 3600
_RESUMO_MAX = 200
_ARTICLE_MAX = 4000

_MESES_PT = [
    "", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]

_cache: Dict[str, object] = {"ts": 0.0, "data": None}
_article_cache: Dict[str, tuple] = {}


def _strip_html(text: str) -> str:
    """Remove tags HTML e normaliza espaços de um trecho."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;?", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _format_date(pubdate: str) -> str:
    """Converte um pubDate RFC-822 em '24 de junho de 2026'. Falha → string original."""
    if not pubdate:
        return ""
    try:
        dt = parsedate_to_datetime(pubdate)
        return f"{dt.day} de {_MESES_PT[dt.month]} de {dt.year}"
    except Exception:
        return pubdate


def _date_sort_key(pubdate: str) -> float:
    try:
        return parsedate_to_datetime(pubdate).timestamp()
    except Exception:
        return 0.0


def _fetch_rss() -> Optional[List[Dict]]:
    """Busca e parseia o feed RSS. Retorna lista de itens ou None em caso de falha."""
    try:
        resp = requests.get(RSS_URL, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        logger.warning("[news] RSS indisponível: %s", e)
        return None

    channel = root.find("channel")
    if channel is None:
        return None

    itens = []
    for item in channel.findall("item"):
        titulo = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not titulo or not link:
            continue
        pubdate = (item.findtext("pubDate") or "").strip()
        resumo = _strip_html(item.findtext("description") or "")
        if len(resumo) > _RESUMO_MAX:
            resumo = resumo[:_RESUMO_MAX].rsplit(" ", 1)[0] + "…"
        itens.append({
            "titulo": titulo,
            "url": link,
            "data": _format_date(pubdate),
            "_ts": _date_sort_key(pubdate),
            "resumo": resumo,
        })
    itens.sort(key=lambda x: x["_ts"], reverse=True)
    return itens or None


def _fetch_html() -> Optional[List[Dict]]:
    """Fallback leve: extrai títulos/links das notícias direto do HTML da página."""
    try:
        resp = requests.get(NEWS_URL, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        logger.warning("[news] HTML indisponível: %s", e)
        return None

    pattern = re.compile(
        r'<a[^>]+href="([^"]*?/sjc/noticias/[a-z0-9][^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    vistos = set()
    itens = []
    for href, inner in pattern.findall(html):
        titulo = _strip_html(inner)
        if not titulo or len(titulo) < 8:
            continue
        url = href if href.startswith("http") else BASE_URL + href
        if url in vistos:
            continue
        vistos.add(url)
        itens.append({"titulo": titulo, "url": url, "data": "", "_ts": 0.0, "resumo": ""})
    return itens or None


def _extract_article_body(html: str) -> str:
    """Extrai o corpo textual de uma página de notícia (Joomla/Gantry)."""
    m = re.search(r'com-content-article__body"?\s*>', html)
    if not m:
        m = re.search(r'unifesp-article-introtext"?\s*>', html)
        if not m:
            return ""
    rest = html[m.end():]
    cut = re.search(r'g-content g-particle|<footer|id="g-footer"|class="g-footer"', rest)
    if cut:
        rest = rest[:cut.start()]
    rest = re.sub(r"<script.*?</script>", " ", rest, flags=re.DOTALL)
    rest = re.sub(r"<style.*?</style>", " ", rest, flags=re.DOTALL)
    rest = re.sub(r"<[^>]+>", " ", rest)
    rest = re.sub(r"&nbsp;?", " ", rest)
    rest = re.sub(r"&amp;", "&", rest)
    rest = re.sub(r"&[a-z]+;", " ", rest)
    rest = re.sub(r"\s+", " ", rest).strip()
    if len(rest) > _ARTICLE_MAX:
        rest = rest[:_ARTICLE_MAX].rsplit(" ", 1)[0] + "…"
    return rest


def fetch_article(url: str, ttl: int = ARTICLE_TTL) -> str:
    """
    Busca e extrai o corpo de uma notícia individual (com cache TTL).
    Retorna o texto limpo, ou "" se não conseguir.
    """
    if not url:
        return ""
    now = time.time()
    cached = _article_cache.get(url)
    if cached and (now - cached[0]) < ttl:
        return cached[1]
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        resp.raise_for_status()
        body = _extract_article_body(resp.text)
    except Exception as e:
        logger.warning("[news] artigo indisponível (%s): %s", url, e)
        body = cached[1] if cached else ""
    if body:
        _article_cache[url] = (now, body)
    return body


def fetch_news(limit: int = 8, ttl: int = DEFAULT_TTL, force: bool = False) -> List[Dict]:
    """
    Retorna as últimas notícias da UNIFESP SJC (com cache TTL).

    Cada item: {titulo, url, data, resumo}. Lista vazia se a fonte estiver fora
    do ar e não houver cache.
    """
    now = time.time()
    cached = _cache.get("data")
    if not force and cached is not None and (now - float(_cache["ts"])) < ttl:
        return cached[:limit]

    itens = _fetch_rss()
    if itens is None:
        itens = _fetch_html()

    if itens:
        for it in itens:
            it.pop("_ts", None)
        _cache["ts"] = now
        _cache["data"] = itens
        return itens[:limit]

    return (cached or [])[:limit] if cached else []
