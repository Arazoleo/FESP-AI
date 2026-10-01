"""
Ingestão dos COMUNICADOS INSTITUCIONAIS da UNIFESP que chegam por email.

Objetivo: dar ao assistente CONTEXTO dos avisos em massa (editais, eventos,
prazos) enviados às listas de alunos — NUNCA emails privados, NUNCA responder
ou enviar nada. O acesso ao Gmail é estritamente READ-ONLY (escopo
`gmail.readonly`): enviar é tecnicamente impossível.

Como o privado fica de fora (defesa em profundidade):
  1. A query do Gmail já restringe a mensagens endereçadas a uma lista pública
     conhecida (To/Cc) E vindas de remetente @unifesp.br.
  2. Cada mensagem é RE-verificada em Python: só vira arquivo se o To/Cc casar
     um dos aliases de lista configurados. Email endereçado só a você nunca casa.

Esta é uma fonte EXTERNA — não passa pela validação simbólica do KG. Por isso
cada comunicado é gravado carimbado com assunto + remetente + data + links, para
o agente citar a fonte ao responder (mesmo padrão do news_fetcher).

Saída: um .md por comunicado em markdown_comunicados/, que o RAG indexa
incrementalmente. O conteúdo NÃO é versionado (ver .gitignore) — são dados
institucionais e o repositório é público.

Config e segredos ficam em ~/.fespai-ops/ (fora do repo):
  - gmail_credentials.json  OAuth Client (baixado do Google Cloud)
  - gmail_token.json        token gerado no 1º consentimento (auto)
  - email_config.json       aliases de lista e parâmetros (editável)
  - email_cursor.json       ids já processados (auto)
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
import unicodedata
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("fespai.email")

OPS_DIR = Path.home() / ".fespai-ops"
CREDENTIALS_PATH = OPS_DIR / "gmail_credentials.json"
TOKEN_PATH = OPS_DIR / "gmail_token.json"
CONFIG_PATH = OPS_DIR / "email_config.json"
CURSOR_PATH = OPS_DIR / "email_cursor.json"

SAIDA_DIR = Path(__file__).resolve().parent.parent / "markdown_comunicados"

# Escopo mínimo: só leitura. Enviar/apagar é impossível com este escopo.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Parâmetros default — sobrescrevíveis por ~/.fespai-ops/email_config.json
DEFAULT_CONFIG = {
    # Aliases de lista pública a que os comunicados são endereçados. SÓ entra
    # email cujo To/Cc casa um destes. Edite à vontade (sem o @unifesp.br final;
    # o casamento é por substring do endereço).
    "listas": [
        "lista.discentes.posgrad.sjc",
        "conecta.digr.ict",
    ],
    # Só aceita remetentes deste domínio (guarda extra contra spoof/externo).
    "dominio_remetente": "unifesp.br",
    # Janela de busca.
    "lookback_days": 60,
    # Teto de mensagens por execução (evita avalanche no 1º run).
    "max_por_execucao": 40,
    # Tamanho máximo do corpo gravado (chars).
    "corpo_max": 6000,
}


# ── config / cursor ─────────────────────────────────────────────────────────
def carregar_config() -> Dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception as e:
            logger.warning("[email] config inválida, usando defaults: %s", e)
    return cfg


def _carregar_cursor() -> set:
    if CURSOR_PATH.exists():
        try:
            return set(json.loads(CURSOR_PATH.read_text(encoding="utf-8")).get("ids", []))
        except Exception:
            return set()
    return set()


def _salvar_cursor(ids: set) -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)
    # Mantém só os ids mais recentes para o arquivo não crescer sem limite.
    recentes = list(ids)[-5000:]
    CURSOR_PATH.write_text(json.dumps({"ids": recentes}, ensure_ascii=False), encoding="utf-8")


# ── Gmail (read-only) ────────────────────────────────────────────────────────
def _servico_gmail():
    """Autentica via OAuth (read-only) e devolve o service do Gmail.

    1º uso: abre o navegador para consentimento e grava o token. Depois usa o
    token salvo (refresh automático). Levanta FileNotFoundError se faltar o
    gmail_credentials.json (baixado do Google Cloud).
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Falta o OAuth Client em {CREDENTIALS_PATH}. Baixe do Google "
                    "Cloud (Credenciais → OAuth Client ID → Desktop) e salve aí."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        OPS_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _executar(req, tentativas: int = 6):
    """Executa uma request do Gmail com backoff em rate limit / erro transitório."""
    from googleapiclient.errors import HttpError

    for i in range(tentativas):
        try:
            return req.execute()
        except HttpError as e:
            status = getattr(e, "status_code", None) or getattr(e.resp, "status", None)
            transitorio = str(status) in {"403", "429", "500", "503"}
            if not transitorio or i == tentativas - 1:
                raise
            espera = min(60, 2 ** i)  # 1,2,4,8,16,32s
            logger.warning("[email] %s — backoff %ss (tentativa %d)", status, espera, i + 1)
            time.sleep(espera)


def _montar_query(cfg: Dict) -> str:
    """Monta a query do Gmail: endereçado a alguma lista E de remetente @unifesp."""
    listas = cfg.get("listas") or []
    alvo = " OR ".join(f"to:{a} OR cc:{a}" for a in listas) or "to:me"
    dom = cfg.get("dominio_remetente", "unifesp.br")
    dias = int(cfg.get("lookback_days", 60))
    return f"from:({dom}) ({alvo}) newer_than:{dias}d"


# ── parsing / limpeza ─────────────────────────────────────────────────────────
_RODAPE_OBRIGATORIO = re.compile(
    r"-+\s*É obrigatória a utilização do e-mail @unifesp.*?(?=$|\n-{2,})",
    re.IGNORECASE | re.DOTALL,
)
_FORWARD_HDR = re.compile(
    r"-{3,}\s*Forwarded message\s*-{3,}.*?(?=\n\n)", re.IGNORECASE | re.DOTALL
)


def _strip_html(texto: str) -> str:
    if not texto:
        return ""
    texto = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", texto, flags=re.DOTALL | re.IGNORECASE)
    texto = re.sub(r"<br\s*/?>", "\n", texto, flags=re.IGNORECASE)
    texto = re.sub(r"</p>", "\n", texto, flags=re.IGNORECASE)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"&nbsp;?", " ", texto)
    texto = re.sub(r"&amp;", "&", texto)
    texto = re.sub(r"&[a-z]+;", " ", texto)
    return texto


def _limpar_corpo(texto: str, limite: int) -> str:
    texto = _RODAPE_OBRIGATORIO.sub(" ", texto)
    texto = _FORWARD_HDR.sub(" ", texto)
    # normaliza espaços preservando parágrafos
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    texto = texto.strip()
    if len(texto) > limite:
        texto = texto[:limite].rsplit(" ", 1)[0] + "…"
    return texto


def _extrair_corpo(payload: Dict) -> str:
    """Varre as partes MIME e devolve o melhor texto (prefere text/plain)."""
    plain, html = [], []

    def _b64(data: str) -> str:
        if not data:
            return ""
        try:
            return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", "replace")
        except Exception:
            return ""

    def _walk(part: Dict):
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")
        if part.get("parts"):
            for p in part["parts"]:
                _walk(p)
        elif mime == "text/plain" and data:
            plain.append(_b64(data))
        elif mime == "text/html" and data:
            html.append(_strip_html(_b64(data)))

    _walk(payload)
    if plain:
        return "\n".join(plain)
    return "\n".join(html)


def _header(headers: List[Dict], nome: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == nome.lower():
            return h.get("value", "")
    return ""


def _casa_lista(destinatarios: str, listas: List[str]) -> Optional[str]:
    """Defesa em profundidade: confirma que To/Cc realmente contém uma lista."""
    alvo = destinatarios.lower()
    for a in listas:
        if a.lower() in alvo:
            return a
    return None


def _slug(texto: str, n: int = 50) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto).strip("-").lower()
    return (texto[:n] or "comunicado")


def _data_fmt(raw: str) -> tuple:
    try:
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "sem-data", raw


def _extrair_links(texto: str) -> List[str]:
    urls = re.findall(r"https?://[^\s<>\")]+", texto)
    vistos, out = set(), []
    for u in urls:
        u = u.rstrip(".,);")
        if u not in vistos:
            vistos.add(u)
            out.append(u)
    return out[:15]


def _para_markdown(msg: Dict, lista: str, cfg: Dict) -> tuple:
    """Monta (nome_arquivo, conteudo_md) a partir de uma mensagem do Gmail."""
    headers = msg.get("payload", {}).get("headers", [])
    assunto = _header(headers, "Subject") or "(sem assunto)"
    remetente = _header(headers, "From")
    destino = f"{_header(headers, 'To')} {_header(headers, 'Cc')}".strip()
    data_raw = _header(headers, "Date")
    data_iso, data_hum = _data_fmt(data_raw)

    corpo = _limpar_corpo(_extrair_corpo(msg.get("payload", {})), int(cfg.get("corpo_max", 6000)))
    links = _extrair_links(corpo)

    nome = f"{data_iso}_{_slug(assunto)}_{msg.get('id', '')[:8]}.md"
    linhas = [
        f"# Comunicado institucional: {assunto}",
        "",
        "> Fonte: email institucional UNIFESP (comunicado em massa a lista de alunos).",
        f"> Remetente: {remetente}",
        f"> Lista: {lista}",
        f"> Data: {data_hum}",
        "> Esta é uma fonte externa (não validada pelo KG). Cite remetente, data e link ao usar.",
        "",
        "## Conteúdo",
        "",
        corpo or "(sem corpo textual)",
    ]
    if links:
        linhas += ["", "## Links", ""] + [f"- {u}" for u in links]
    linhas.append("")
    return nome, "\n".join(linhas)


# ── orquestração ──────────────────────────────────────────────────────────────
def ingerir(dry_run: bool = False) -> Dict:
    """Busca comunicados novos e grava um .md por mensagem. Retorna um resumo.

    Idempotente: ids já processados (cursor) são pulados. Nunca grava email que
    não case um alias de lista configurado.
    """
    cfg = carregar_config()
    listas = cfg.get("listas") or []
    cursor = _carregar_cursor()
    resumo = {"novos": 0, "pulados": 0, "ignorados_privado": 0, "arquivos": []}

    service = _servico_gmail()
    query = _montar_query(cfg)
    logger.info("[email] query: %s", query)

    # Pagina a listagem até o teto (maxResults do Gmail é por página, máx. 500).
    teto = int(cfg.get("max_por_execucao", 40))
    throttle = float(cfg.get("throttle_s", 0.3))
    mensagens, page_token = [], None
    while len(mensagens) < teto:
        resp = _executar(service.users().messages().list(
            userId="me", q=query, pageToken=page_token,
            maxResults=min(500, teto - len(mensagens)),
        ))
        mensagens.extend(resp.get("messages", []) or [])
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    if not dry_run:
        SAIDA_DIR.mkdir(parents=True, exist_ok=True)

    # Prefixos de id já gravados em disco → resume sem re-buscar (barato: evita o
    # get() caro quando o cursor se perdeu numa falha anterior).
    prefixos_no_disco = set()
    if not dry_run:
        for f in SAIDA_DIR.glob("*.md"):
            m = re.search(r"_([0-9a-f]{8})\.md$", f.name)
            if m:
                prefixos_no_disco.add(m.group(1))

    try:
        for ref in mensagens:
            mid = ref.get("id")
            if not mid or mid in cursor:
                resumo["pulados"] += 1
                continue
            if mid[:8] in prefixos_no_disco:
                resumo["pulados"] += 1
                cursor.add(mid)
                continue
            msg = _executar(service.users().messages().get(userId="me", id=mid, format="full"))
            time.sleep(throttle)  # respira p/ não estourar o rate limit por usuário
            headers = msg.get("payload", {}).get("headers", [])
            destino = f"{_header(headers, 'To')} {_header(headers, 'Cc')}"
            lista = _casa_lista(destino, listas)
            if not lista:
                # Não casou nenhuma lista pública → trata como privado e ignora.
                resumo["ignorados_privado"] += 1
                cursor.add(mid)
                continue

            nome, conteudo = _para_markdown(msg, lista, cfg)
            if not dry_run:
                (SAIDA_DIR / nome).write_text(conteudo, encoding="utf-8")
            resumo["novos"] += 1
            resumo["arquivos"].append(nome)
            cursor.add(mid)
            # Salva o cursor a cada 20 → progresso parcial sobrevive a falha.
            if not dry_run and resumo["novos"] % 20 == 0:
                _salvar_cursor(cursor)
    finally:
        # Garante que o já-processado não será refeito, mesmo se algo falhar.
        if not dry_run:
            _salvar_cursor(cursor)

    logger.info(
        "[email] novos=%d pulados=%d ignorados_privado=%d",
        resumo["novos"], resumo["pulados"], resumo["ignorados_privado"],
    )
    return resumo
