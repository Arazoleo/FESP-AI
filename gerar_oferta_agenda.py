"""
Extrator rerodável da OFERTA DO SEMESTRE a partir da Agenda de salas do campus
UNIFESP São José dos Campos (Booked Scheduler, público).

A agenda de reservas de salas funciona, na prática, como a grade de oferta: cada
reserva de aula traz "Disciplina - Turma X - Prof. Nome", a sala (recurso), o dia
e o horário. Uma semana típica já expõe o horário semanal de cada turma.

Coleta (headless, porque o feed JSON só responde dentro da sessão do navegador):
carrega view-schedule.php, intercepta a resposta de `dr=reservations` (JSON com
todas as reservas) e lê o mapa recurso->sala do próprio HTML. Depois parseia,
agrupa por (disciplina, turma, professor), filtra o que é aula de graduação
(tem "Turma"; descarta pós "PPG*", monitorias e eventos) e emite um markdown
carimbado com fonte e data de coleta, que entra no RAG do assistente.

Uso:
    python3 gerar_oferta_agenda.py            # coleta a semana atual e escreve o md
    python3 gerar_oferta_agenda.py --data 2026-09-14   # ancora noutra semana
"""

from __future__ import annotations

import argparse
import html as H
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

BASE = "https://agendamentos.unifesp.br/sjc/Web"
URL_AGENDA = f"{BASE}/view-schedule.php"
SAIDA = Path(__file__).parent / "markdown_regimentos" / "oferta_semestre_agenda.md"
SAIDA_JSON = Path(__file__).parent / "jsons_regimentos" / "oferta_semestre.json"

DIAS = {0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"}
DIAS_EXT = {"Seg": "segunda", "Ter": "terça", "Qua": "quarta", "Qui": "quinta",
            "Sex": "sexta", "Sáb": "sábado", "Dom": "domingo"}


# ── coleta ────────────────────────────────────────────────────────────────────
def coletar(sd: str | None = None, tentativas: int = 3):
    """Retorna (reservations:list[dict], salas:dict[id->nome]) via headless.

    Espera ativamente a resposta de `dr=reservations` (o feed pode demorar) e
    tenta de novo se vier vazio — evita gravar uma coleta falha.
    """
    from playwright.sync_api import sync_playwright

    url = URL_AGENDA + (f"?sd={sd}" if sd else "")
    for tent in range(1, tentativas + 1):
        dados, html = {}, ""
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()

            def on_response(resp):
                if "dr=reservations" in resp.url:
                    try:
                        dados["res"] = resp.json().get("reservations", [])
                    except Exception as e:
                        dados["err"] = str(e)

            pg.on("response", on_response)
            try:
                pg.goto(url, wait_until="networkidle", timeout=90_000)
            except Exception as e:
                print(f"[agenda] tentativa {tent}: erro ao carregar ({e})")
            # espera ativa até ~20s pela captura das reservas
            for _ in range(40):
                if dados.get("res"):
                    break
                pg.wait_for_timeout(500)
            html = pg.content()
            b.close()

        res = dados.get("res", [])
        if res:
            salas = {}
            for m in re.finditer(
                r'<td class="resourcename"[^>]*data-resourceid="(\d+)"[^>]*>(.*?)</td>',
                html, re.S,
            ):
                nome = re.sub(r"\s+", " ",
                              H.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
                if nome:
                    salas[m.group(1)] = nome
            return res, salas
        print(f"[agenda] tentativa {tent}/{tentativas}: coleta vazia, repetindo...")
    return [], {}


# ── parse do rótulo ───────────────────────────────────────────────────────────
_POS = re.compile(r"^\s*(PPG|PPGCC|PPGMAT|PPG-CC|Mestrado|Doutorado|POS|PÓS)\b", re.I)
_NAO_AULA = re.compile(r"^\s*(Monitoria|Ensaio|Reuni|Defesa|Prova|Palestra|Evento|"
                       r"Semin[aá]rio|Banca|Atendimento|Manuten|Reserva)\b", re.I)


def parse_label(label: str) -> dict | None:
    """'Disciplina - Turma X - Prof. Nome' -> dict, ou None se não for aula de grad."""
    lab = label.split("Solicitante:")[0].strip()
    if not lab or _POS.search(lab) or _NAO_AULA.search(lab):
        return None
    # precisa ter Turma (marca de disciplina de graduação)
    mt = re.search(r"-\s*Turm[a]?\s*([A-Za-z0-9]+)", lab)
    if not mt:
        return None
    disciplina = lab[: mt.start()].strip(" -")
    turma = mt.group(1).upper()
    prof = None
    mp = re.search(r"-\s*Prof[a]?\.?\s*(.+)$", lab[mt.start():], re.I)
    if mp:
        prof = mp.group(1).strip(" .-")
    if not disciplina or len(disciplina) < 3:
        return None
    return {"disciplina": disciplina, "turma": turma, "professor": prof}


def _norm(s: str) -> str:
    n = unicodedata.normalize("NFD", (s or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in n if unicodedata.category(c) != "Mn")).strip()


# ── montagem da oferta ────────────────────────────────────────────────────────
def montar(reservations, salas):
    """Agrupa por (disciplina, turma, prof) -> encontros [(dia, ini, fim, sala)]."""
    grupos = defaultdict(lambda: {"professor": None, "encontros": set()})
    for r in reservations:
        info = parse_label(r.get("Label", ""))
        if not info:
            continue
        try:
            dia = DIAS[date(*map(int, r["StartDateString"].split("-"))).weekday()]
        except Exception:
            continue
        sala = salas.get(str(r.get("ResourceId")), f"recurso {r.get('ResourceId')}")
        chave = (info["disciplina"], info["turma"])
        g = grupos[chave]
        if info["professor"]:
            g["professor"] = info["professor"]
        g["encontros"].add((dia, r.get("StartTime", ""), r.get("EndTime", ""), sala))
    return grupos


def carregar_disciplinas_grad():
    """Nomes normalizados das disciplinas de graduação já na base (p/ marcar)."""
    d = Path(__file__).parent / "markdown_disciplinas"
    nomes = set()
    for f in d.glob("*.md"):
        try:
            t = f.read_text(encoding="utf-8")
        except Exception:
            continue
        m = re.search(r"^#\s+(.+)$", t, re.M)
        if m:
            nomes.add(_norm(m.group(1)))
        nomes.add(_norm(f.stem.replace("_", " ")))
    return nomes


# ── emissão do markdown ───────────────────────────────────────────────────────
def _ordena_encontros(enc):
    ordem = {d: i for i, d in enumerate(DIAS.values())}
    return sorted(enc, key=lambda e: (ordem.get(e[0], 9), e[1]))


def emitir(grupos, semestre_rotulo, coletado_em, na_base):
    linhas = [
        "# Oferta de disciplinas do semestre (grade de aulas)",
        "",
        f"**Semestre:** {semestre_rotulo}. **Fonte:** Agenda de salas do campus "
        f"São José dos Campos ({URL_AGENDA}), **coletado em** {coletado_em}.",
        "",
        "Esta é a grade de oferta do semestre extraída da agenda de reservas de "
        "salas do campus: para cada turma, o **professor**, os **dias e horários** "
        "e a **sala**. É a oferta real do semestre (não a previsão por paridade). "
        "Reservas de pós-graduação, monitorias e eventos foram descartadas. Como a "
        "fonte é a agenda de salas, vale confirmar mudanças pontuais com a coordenação.",
        "",
    ]
    # ordena por disciplina
    por_disc = defaultdict(list)
    for (disc, turma), g in grupos.items():
        por_disc[disc].append((turma, g))
    for disc in sorted(por_disc, key=_norm):
        marca = "" if _norm(disc) in na_base else "  _(não consta no catálogo da base)_"
        linhas.append(f"## {disc}{marca}")
        for turma, g in sorted(por_disc[disc]):
            prof = g["professor"] or "professor não informado na agenda"
            # agrupa dias com mesmo horário/sala
            enc = _ordena_encontros(g["encontros"])
            partes = []
            for dia, ini, fim, sala in enc:
                partes.append(f"{DIAS_EXT.get(dia, dia)} {ini}–{fim} ({sala})")
            linhas.append(f"- **Turma {turma}** — Prof. {prof} — " + "; ".join(partes))
        linhas.append("")
    SAIDA.write_text("\n".join(linhas), encoding="utf-8")
    return SAIDA


def emitir_json(grupos, semestre_rotulo, coletado_em, na_base):
    """Emite a oferta estruturada (p/ consulta determinística via oferta_real)."""
    disc = defaultdict(list)
    for (nome, turma), g in grupos.items():
        encontros = [
            {"dia": d, "inicio": ini, "fim": fim, "sala": sala}
            for d, ini, fim, sala in _ordena_encontros(g["encontros"])
        ]
        disc[nome].append({
            "turma": turma,
            "professor": g["professor"],
            "encontros": encontros,
            "no_catalogo": _norm(nome) in na_base,
        })
    payload = {
        "semestre": semestre_rotulo,
        "coletado_em": coletado_em,
        "fonte": URL_AGENDA,
        "disciplinas": dict(disc),
    }
    SAIDA_JSON.parent.mkdir(parents=True, exist_ok=True)
    SAIDA_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return SAIDA_JSON


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", help="ancora a semana (YYYY-MM-DD)", default=None)
    args = ap.parse_args()

    hoje = datetime.now().date() if args.data is None else date(*map(int, args.data.split("-")))
    semestre = f"{hoje.year}/{1 if hoje.month <= 6 else 2}"
    coletado = hoje.isoformat()

    print(f"[agenda] coletando oferta ({semestre}) da agenda do campus...")
    reservations, salas = coletar(args.data)
    print(f"[agenda] {len(reservations)} reservas, {len(salas)} salas")
    # SEGURANÇA: nunca sobrescrever os dados bons com uma coleta vazia/insuficiente
    MINIMO = 20
    if len(reservations) < MINIMO:
        print(f"[agenda] ABORTADO: só {len(reservations)} reservas (< {MINIMO}). "
              f"Mantendo a oferta anterior — nada foi sobrescrito.")
        raise SystemExit(1)
    grupos = montar(reservations, salas)
    na_base = carregar_disciplinas_grad()
    n_base = sum(1 for (d, _t) in grupos if _norm(d) in na_base)
    caminho = emitir(grupos, semestre, coletado, na_base)
    caminho_json = emitir_json(grupos, semestre, coletado, na_base)
    print(f"[agenda] {len(grupos)} turmas de graduação "
          f"({n_base} casadas com o catálogo da base)")
    print(f"[agenda] escrito em {caminho}")
    print(f"[agenda] json em {caminho_json}")


if __name__ == "__main__":
    main()
