"""
Auditoria de integralização e pré-verificação de matrícula.

- auditar_progresso: cruza as disciplinas cursadas com a matriz do curso no KG
  e devolve obrigatórias faltantes, disponíveis agora, bloqueadas (com o
  pré-requisito que falta) e o mínimo de semestres restantes pelo caminho
  crítico do DAG de pré-requisitos.
- verificar_matricula: aplica os motivos de indeferimento verificáveis
  (pré-requisito não cumprido, UC já cursada) e explica a prioridade do
  art. 143 do Regulamento dos Cursos de Graduação (Res. CONSU 246/2023).

Entradas em linguagem natural são aterradas no KG; o que não resolve é
reportado ao aluno, nunca inventado.
"""

import re
import unicodedata
from typing import Dict, List, Optional, Tuple


def _norm(text: str) -> str:
    t = "".join(
        c for c in unicodedata.normalize("NFD", str(text or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", t).strip()


_PLACEHOLDERS_MATRIZ = {
    "eletiva", "eletivas", "eletiva interdisciplinar",
    "eletivas interdisciplinares", "optativa", "optativas",
    "uc eletiva", "uc optativa",
}

BCT_EXTRAS_PPC2023 = {"extensao_h": 240, "interdisciplinares": 4}

_requisitos_cache = None


def _carregar_requisitos() -> List[Dict]:
    global _requisitos_cache
    if _requisitos_cache is None:
        import json
        from pathlib import Path

        caminho = Path(__file__).parent / "requisitos_seed.json"
        try:
            _requisitos_cache = json.loads(caminho.read_text())
        except (OSError, ValueError):
            _requisitos_cache = []
    return _requisitos_cache


def requisitos_do_curso(sigla: str, curso_texto: str = "") -> Optional[Dict]:
    sigla = (sigla or "").upper()
    entradas = [e for e in _carregar_requisitos() if e["sigla"] == sigla]
    if not entradas:
        return None
    turno = "noturno" if "noturno" in _norm(curso_texto) else "integral"
    for e in entradas:
        if e["turno"] == turno:
            return e
    return entradas[0]


def _matriz_do_curso(kg, curso: str) -> Optional[Dict[str, Dict]]:
    termos = kg.get_todos_termos_do_curso(curso)
    if not termos:
        return None
    info = {}
    for termo_num, discs in termos.items():
        for d in discs:
            nome = d.get("nome")
            if not nome:
                continue
            if _norm(nome) in _PLACEHOLDERS_MATRIZ:
                continue
            key = kg._normalize_text(nome)
            try:
                t = int(re.match(r"(\d+)", str(termo_num)).group(1))
            except (AttributeError, ValueError):
                t = 99
            if key not in info or t < info[key]["termo"]:
                info[key] = {"nome": nome, "termo": t}
    return info


def auditar_progresso(kg, curso: str, cursadas: List[str],
                      historico: Optional[Dict] = None) -> Optional[Dict]:
    info = _matriz_do_curso(kg, curso)
    if not info:
        return None
    norm = kg._normalize_text

    cursadas_norm = set()
    eletivas_cursadas = []
    desconhecidas = []
    for c in cursadas:
        if not c or not c.strip():
            continue
        k = norm(c)
        if k in info:
            cursadas_norm.add(k)
            continue
        node = kg._find_node(c, "disciplina")
        if node:
            nome_kg = kg.graph.nodes[node].get("nome", c)
            k2 = norm(nome_kg)
            if k2 in info:
                cursadas_norm.add(k2)
            else:
                eletivas_cursadas.append(nome_kg)
            continue
        desconhecidas.append(c)

    pendentes = {k: v for k, v in info.items() if k not in cursadas_norm}

    prereqs = {}
    for k, v in pendentes.items():
        directs = kg.get_direct_prerequisites(v["nome"]) or []
        prereqs[k] = {norm(p) for p in directs if p and norm(p) in info}

    disponiveis, bloqueadas = [], []
    for k, v in sorted(pendentes.items(), key=lambda kv: (kv[1]["termo"], kv[1]["nome"])):
        faltando = [
            info[p]["nome"] for p in prereqs[k]
            if p not in cursadas_norm
        ]
        if faltando:
            bloqueadas.append({**v, "faltando": sorted(faltando)})
        else:
            base_pendente = []
            try:
                for b in kg.get_base_recomendada(v["nome"]):
                    if norm(b["nome"]) not in cursadas_norm:
                        base_pendente.append(b["nome"])
            except Exception:
                pass
            try:
                paridade = kg.paridade_oferta(v["nome"])
            except Exception:
                paridade = None
            disponiveis.append({
                **v,
                "base_pendente": base_pendente[:2],
                "paridade": paridade,
            })

    interdisciplinares_cursadas = []
    for c in cursadas:
        node = kg._find_node(c, "disciplina")
        if node and kg.graph.nodes[node].get("interdisciplinar"):
            nome_i = kg.graph.nodes[node].get("nome", c)
            if nome_i not in interdisciplinares_cursadas:
                interdisciplinares_cursadas.append(nome_i)

    nivel: Dict[str, int] = {}

    def _nivel(k: str, trilha=frozenset()) -> int:
        if k in nivel:
            return nivel[k]
        if k in trilha:
            return 1
        pend_prereqs = [p for p in prereqs.get(k, set()) if p in pendentes]
        n = 1 + max((_nivel(p, trilha | {k}) for p in pend_prereqs), default=0)
        nivel[k] = n
        return n

    semestres_min = max((_nivel(k) for k in pendentes), default=0)

    return {
        "curso": curso,
        "total_matriz": len(info),
        "cursadas": sorted(info[k]["nome"] for k in cursadas_norm),
        "eletivas_cursadas": sorted(set(eletivas_cursadas)),
        "desconhecidas": desconhecidas,
        "pendentes": len(pendentes),
        "disponiveis": disponiveis,
        "bloqueadas": bloqueadas,
        "semestres_minimos": semestres_min,
        "interdisciplinares_cursadas": interdisciplinares_cursadas,
        "integralizacao": _quadro_integralizacao(
            curso, historico, len(pendentes), interdisciplinares_cursadas
        ),
    }


def _rotulo_criterio(c: Dict) -> str:
    tipo, expressao = c["tipo"], c["expressao"].upper()
    if tipo == "DISCIPLINA" and "FIXAS" in expressao:
        return "UCs fixas (obrigatórias)"
    if tipo == "DISCIPLINA" and "ELETIVAS" in expressao:
        return "UCs eletivas"
    if tipo == "ATIVIDADE COMPLEMENTAR":
        return "Atividades Complementares"
    if tipo == "ESTÁGIO":
        return "Estágio obrigatório"
    if tipo == "TRABALHO DE CONCLUSÃO DE CURSO":
        return "Trabalho de Conclusão de Curso (TCC)"
    return c["expressao"].title()


_SIGLA_CURSO_RE = re.compile(r"\b(bct|bcc|bmc|bbt|ec|eb)\b")

_NOMES_CURSOS_NORM = (
    ("ciencia e tecnologia", "BCT"), ("interdisciplinar", "BCT"),
    ("ciencia da computacao", "BCC"), ("matematica computacional", "BMC"),
    ("biotecnologia", "BBT"), ("engenharia de computacao", "EC"),
    ("engenharia biomedica", "EB"), ("engenharia de materiais", "EM"),
)


def cursos_citados(texto: str) -> List[str]:
    q = _norm(texto)
    achados = []
    for nome, sigla in _NOMES_CURSOS_NORM:
        if nome in q and sigla not in achados:
            achados.append(sigla)
    for m in _SIGLA_CURSO_RE.finditer(q):
        s = m.group(1).upper()
        if s not in achados:
            achados.append(s)
    return achados


def is_pergunta_comparativa(texto: str) -> bool:
    q = _norm(texto)
    if re.search(r"\bdiferen\w+|\bcompar\w+|\bversus\b|\bou\s+melhor\b", q):
        return True
    return len(cursos_citados(texto)) >= 2


def extrair_curso_requisitos(texto: str) -> str:
    from .historico import curso_sigla

    sigla = curso_sigla(texto)
    if sigla:
        return sigla
    m = _SIGLA_CURSO_RE.search(_norm(texto))
    return m.group(1).upper() if m else ""


_REQUISITOS_CUES_RES = [re.compile(p) for p in (
    r"\bo\s*que\s+(?:eu\s+)?(?:preciso|necessito)\s+(?:para|pra)\s+(?:me\s+)?formar",
    r"quantas?\s+horas.*\b(?:formar|integralizar|concluir|colar\s+grau)",
    r"\b(?:carga\s+horaria|horas)\b.*\b(?:para|pra|de)\s+integraliza",
    r"\brequisitos?\s+(?:de|para)\s+(?:integralizacao|formatura|conclusao|se\s+formar)",
    r"\bo\s+que\s+(?:o\s+curso\s+)?exige\s+para\s+(?:se\s+)?formar",
    r"\bpreciso\s+de\s+quantas\s+horas\b",
)]


def is_requisitos_request(texto: str) -> bool:
    q = _norm(texto)
    return any(p.search(q) for p in _REQUISITOS_CUES_RES)


def responder_requisitos(sigla: str, curso_texto: str = "") -> Optional[str]:
    req = requisitos_do_curso(sigla, curso_texto)
    if not req:
        return None
    rotulo_curso = req["sigla"]
    if req["sigla"] == "BCT":
        rotulo_curso += f" ({req['turno']})"
    linhas = [
        f"**O que o {rotulo_curso} exige para você se formar**",
        "",
        f"Pela matriz ATIVA oficial ({req['nome'].title()}), a integralização "
        f"pede **{req['total_h']} horas** no total:",
        "",
    ]
    for c in req["criterios"]:
        linhas.append(f"- **{_rotulo_criterio(c)}**: {c['para_total_h']}h")
    if req["sigla"] == "BCT":
        linhas.append(
            f"- **Extensão curricularizada**: "
            f"{BCT_EXTRAS_PPC2023['extensao_h']}h (PPC 2023; cumpridas em "
            "Eletivas ou Atividades Complementares Extensionistas)"
        )
        linhas.append(
            f"- **UCs Eletivas Interdisciplinares**: "
            f"{BCT_EXTRAS_PPC2023['interdisciplinares']} UCs, independentemente "
            "da carga horária (PPC 2023)"
        )
    linhas.append("")
    linhas.append(
        "Quer ver quanto **você** já cumpriu de cada item? Envie seu Histórico "
        "Acadêmico (PDF) pelo botão **Histórico** e pergunte *\"quanto falta "
        "para me formar?\"*."
    )
    linhas.append("")
    linhas.append(
        f"*Fonte: sistema oficial de Cursos e Matrizes Curriculares da Unifesp "
        f"(SIIU/Prograd), matriz {req['matriz']}.*"
    )
    return "\n".join(linhas)


def _quadro_integralizacao(curso: str, historico: Optional[Dict],
                           obrigatorias_pendentes: int,
                           interdisciplinares: List[str]) -> Optional[Dict]:
    req = requisitos_do_curso(curso, (historico or {}).get("curso", ""))
    horas = (historico or {}).get("horas") or {}
    if not req or not horas:
        return None

    componentes = []

    def comp(nome, cumprido, exigido, unidade="h", obs=""):
        ok = None if cumprido is None else cumprido >= exigido
        componentes.append({
            "nome": nome,
            "cumprido": cumprido,
            "exigido": exigido,
            "unidade": unidade,
            "ok": ok,
            "obs": obs,
        })

    for c in req["criterios"]:
        tipo, expressao, exigido = c["tipo"], c["expressao"].upper(), c["para_total_h"]
        if tipo == "DISCIPLINA" and "FIXAS" in expressao:
            comp(
                "UCs fixas (obrigatórias)", horas.get("fixas"), exigido,
                obs="" if obrigatorias_pendentes == 0
                else f"{obrigatorias_pendentes} obrigatória(s) ainda pendente(s) na matriz",
            )
        elif tipo == "DISCIPLINA" and "ELETIVAS" in expressao:
            comp("UCs eletivas", horas.get("eletivas"), exigido)
        elif tipo == "ATIVIDADE COMPLEMENTAR":
            if horas.get("ac"):
                comp("Atividades Complementares", horas["ac"], exigido)
            else:
                obs_ac = "não constam no histórico; são validadas em processo próprio (SEI)"
                itens_ac = (historico or {}).get("ac_itens") or []
                if itens_ac:
                    try:
                        from .ac_auditor import auditar_atividades
                        validas = auditar_atividades(itens_ac)["total_valido"]
                        obs_ac += (
                            f"; você declarou ~{int(validas)}h válidas nesta "
                            "conversa (simulação)"
                        )
                    except Exception:
                        pass
                comp("Atividades Complementares", None, exigido, obs=obs_ac)
        elif tipo == "ESTÁGIO":
            comp(
                "Estágio obrigatório", None, exigido,
                obs="confira no histórico se a UC de estágio consta como aprovada",
            )
        elif tipo == "TRABALHO DE CONCLUSÃO DE CURSO":
            comp(
                "TCC", None, exigido,
                obs="confira no histórico se a UC de TCC consta como aprovada",
            )

    if req["sigla"] == "BCT":
        ano_ingresso = (historico or {}).get("ano_ingresso")
        if ano_ingresso and ano_ingresso <= 2022:
            componentes.append({
                "nome": "Extensão curricularizada",
                "cumprido": horas.get("extensao"),
                "exigido": BCT_EXTRAS_PPC2023["extensao_h"],
                "unidade": "h",
                "ok": True,
                "obs": f"dispensada - ingressantes até 2/2022 (você entrou em {ano_ingresso})",
            })
        else:
            comp(
                "Extensão curricularizada", horas.get("extensao"),
                BCT_EXTRAS_PPC2023["extensao_h"],
            )
        comp(
            "UCs Eletivas Interdisciplinares", len(interdisciplinares),
            BCT_EXTRAS_PPC2023["interdisciplinares"], unidade="UCs",
        )
        fonte = "matriz ATIVA oficial (SIIU/Prograd) e PPC 2023"
    else:
        fonte = "matriz ATIVA oficial (SIIU/Prograd)"

    faltando = [c for c in componentes if c["ok"] is False]
    a_confirmar = [c for c in componentes if c["ok"] is None]
    return {
        "fonte": fonte,
        "total_h": req.get("total_h"),
        "componentes": componentes,
        "completo_verificavel": not faltando,
        "faltando": faltando,
        "a_confirmar": a_confirmar,
    }


def _fmt_h(v) -> str:
    return f"{v}h" if isinstance(v, (int, float)) else str(v)


def formatar_progresso(r: Dict) -> str:
    quadro = r.get("integralizacao")
    if quadro:
        return _formatar_progresso_com_historico(r, quadro)
    return _formatar_progresso_matriz(r)


def _formatar_progresso_com_historico(r: Dict, quadro: Dict) -> str:
    curso = r["curso"].upper()
    linhas = [f"**Quanto falta para você se formar no {curso}?**", ""]

    if quadro["completo_verificavel"]:
        pend_nomes = [c["nome"] for c in quadro["a_confirmar"]]
        if pend_nomes:
            linhas.append(
                "Boa notícia: **tudo o que dá para conferir pelo histórico está "
                "completo**. O que resta confirmar por fora: "
                + ", ".join(f"**{n}**" for n in pend_nomes) + "."
            )
        else:
            linhas.append(
                "**Tudo completo pelo que consigo verificar no seu histórico!**"
            )
    else:
        nomes = ", ".join(f"**{c['nome']}**" for c in quadro["faltando"])
        linhas.append(f"Pelo seu histórico, ainda falta: {nomes}.")

    linhas.append("")
    linhas.append("O quadro, requisito por requisito:")
    for c in quadro["componentes"]:
        if c["ok"] is True:
            folga = (
                c["cumprido"] - c["exigido"]
                if isinstance(c["cumprido"], (int, float)) else 0
            )
            det = f" (+{folga}{'' if c['unidade'] == 'UCs' else 'h'} além do mínimo)" if folga > 0 else ""
            simbolo, situacao = "✓", f"completo{det}"
        elif c["ok"] is False:
            falta = c["exigido"] - c["cumprido"]
            simbolo = "✗"
            situacao = f"faltam {falta}{'' if c['unidade'] == 'UCs' else 'h'}"
        else:
            simbolo, situacao = "…", "a confirmar"
        exigido = (
            f"{c['exigido']} exigidas" if c["unidade"] == "UCs"
            else f"{_fmt_h(c['exigido'])} exigidas"
        )
        if c["cumprido"] is None:
            quadro_valores = exigido
        else:
            cumprido = (
                f"{c['cumprido']} de" if c["unidade"] == "UCs"
                else f"{_fmt_h(c['cumprido'])} de"
            )
            quadro_valores = f"{cumprido} {exigido}"
        linha = f"- {simbolo} **{c['nome']}**: {quadro_valores} - {situacao}"
        if c["obs"]:
            linha += f" ({c['obs']})"
        linhas.append(linha)

    if r["pendentes"]:
        nomes_pend = ", ".join(
            d["nome"] for d in (r["disponiveis"] + r["bloqueadas"])
        )
        linhas.append("")
        linhas.append(
            f"Obrigatórias da matriz ainda não cursadas: {nomes_pend}."
        )
    inter = r.get("interdisciplinares_cursadas") or []
    if inter:
        linhas.append("")
        linhas.append(
            "Suas UCs Eletivas Interdisciplinares: " + ", ".join(inter) + "."
        )
    linhas.append("")
    linhas.append(
        f"*Comparei as horas do RESUMO do seu histórico com os requisitos do "
        f"{quadro['fonte']} ({curso}). Confirme a situação oficial no sistema "
        "da Unifesp - especialmente as Atividades Complementares, que têm "
        "deferimento próprio.*"
    )
    return "\n".join(linhas)


def _formatar_progresso_matriz(r: Dict) -> str:
    curso = r["curso"].upper()
    feitas, total = len(r["cursadas"]), r["total_matriz"]
    linhas = [f"**Quanto falta para você se formar no {curso}?**", ""]
    if r["pendentes"] == 0:
        linhas.append(
            f"Você já cursou **todas as {total} obrigatórias** da matriz do "
            f"{curso} que constam no sistema."
        )
    else:
        linhas.append(
            f"Das **{total} obrigatórias** da matriz, você já fez **{feitas}** "
            f"- faltam **{r['pendentes']}**, e dá para fechá-las em pelo menos "
            f"**{r['semestres_minimos']} semestre(s)** (pela cadeia de "
            "pré-requisitos)."
        )
    if r["disponiveis"]:
        from .oferta import ofertada_em, proximo_semestre, rotulo, proxima_oferta

        prox = proximo_semestre()
        linhas.append("")
        linhas.append(
            f"**Você já pode cursar** (pré-requisitos cumpridos; oferta prevista "
            f"pela paridade do termo, vale confirmar com a coordenação):"
        )
        for d in r["disponiveis"][:12]:
            extra = ""
            if d.get("base_pendente"):
                extra = f" - base recomendada pendente: {', '.join(d['base_pendente'])}"
            oferta = ofertada_em(d.get("paridade"), prox)
            if oferta is True:
                extra += f" - oferta esperada em {rotulo(prox)} ✓"
            elif oferta is False:
                extra += (
                    f" - termo {'par' if d.get('paridade') == 'par' else 'ímpar'}: "
                    f"oferta esperada só em {rotulo(proxima_oferta(d.get('paridade')))}"
                )
            linhas.append(f"- {d['nome']} (termo {d['termo']}){extra}")
        if len(r["disponiveis"]) > 12:
            linhas.append(f"- ... e mais {len(r['disponiveis']) - 12}")
    if r["bloqueadas"]:
        linhas.append("")
        linhas.append("**Bloqueadas por pré-requisito:**")
        for d in r["bloqueadas"][:10]:
            linhas.append(
                f"- {d['nome']} (termo {d['termo']}) ← falta {', '.join(d['faltando'])}"
            )
        if len(r["bloqueadas"]) > 10:
            linhas.append(f"- ... e mais {len(r['bloqueadas']) - 10}")
    if r.get("eletivas_cursadas"):
        linhas.append("")
        linhas.append(
            f"Fora das obrigatórias, você já cursou **{len(r['eletivas_cursadas'])} "
            f"eletivas/outras UCs** reconhecidas no sistema."
        )
    if r["desconhecidas"]:
        linhas.append("")
        linhas.append(
            "Não reconheci no sistema (confira o nome): "
            + ", ".join(r["desconhecidas"])
        )
    linhas.append("")
    inter = r.get("interdisciplinares_cursadas") or []
    curso_norm = _norm(r["curso"])
    if "bct" in curso_norm or "ciencia e tecnologia" in curso_norm:
        status_inter = (
            f"**{len(inter)} de 4** UCs Eletivas Interdisciplinares cursadas"
            + (f" ({', '.join(inter)})" if inter else "")
        )
        linhas.append(f"- Interdisciplinares (requisito do PPC 2023): {status_inter}")
        linhas.append("")
    linhas.append(
        "Formar não é só a matriz de obrigatórias: também contam as eletivas, "
        "as horas de extensão, as 312h de Atividades Complementares e, no BCT, "
        "4 UCs Eletivas Interdisciplinares. **Envie seu Histórico Acadêmico "
        "(PDF) pelo botão Histórico** que eu confiro as horas de cada requisito "
        "para você."
    )
    linhas.append("")
    linhas.append(
        "*Auditoria pelas regras de pré-requisito do Knowledge Graph. Confirme "
        "sempre com o Histórico Escolar oficial.*"
    )
    return "\n".join(linhas)


def verificar_matricula(kg, desejadas: List[str], cursadas: List[str]) -> Dict:
    norm = kg._normalize_text
    cursadas_norm = set()
    for c in cursadas:
        node = kg._find_node(c, "disciplina")
        if node:
            cursadas_norm.add(norm(kg.graph.nodes[node].get("nome", c)))
        else:
            cursadas_norm.add(norm(c))

    pareceres = []
    for d in desejadas:
        node = kg._find_node(d, "disciplina")
        if not node:
            pareceres.append({
                "disciplina": d,
                "status": "desconhecida",
                "motivos": ["não encontrei essa UC no sistema"],
                "base_pendente": [],
            })
            continue
        nome = kg.graph.nodes[node].get("nome", d)
        motivos = []
        if norm(nome) in cursadas_norm:
            motivos.append("UC já cursada (motivo de indeferimento)")
        faltando = [
            p for p in (kg.get_direct_prerequisites(nome) or [])
            if norm(p) not in cursadas_norm
        ]
        if faltando:
            motivos.append(
                "falta pré-requisito: " + ", ".join(sorted(faltando))
                + " (motivo de indeferimento)"
            )
        base_pendente = []
        try:
            for b in kg.get_base_recomendada(nome):
                if norm(b["nome"]) not in cursadas_norm:
                    base_pendente.append(
                        f"{b['nome']} ({', '.join(b['conceitos'])})"
                    )
        except Exception:
            pass
        try:
            paridade = kg.paridade_oferta(nome)
        except Exception:
            paridade = None
        pareceres.append({
            "disciplina": nome,
            "status": "risco" if motivos else "ok",
            "motivos": motivos,
            "base_pendente": base_pendente[:3],
            "paridade": paridade,
        })
    return {"pareceres": pareceres}


def formatar_matricula(r: Dict) -> str:
    linhas = ["**Pré-verificação da sua inscrição em UCs**", ""]
    for p in r["pareceres"]:
        if p["status"] == "ok":
            linhas.append(
                f"- **{p['disciplina']}**: ✓ sem impedimento nos critérios que "
                "consigo verificar (pré-requisitos e UC repetida)"
            )
        else:
            linhas.append(f"- **{p['disciplina']}**: ⚠ {'; '.join(p['motivos'])}")
        if p.get("base_pendente"):
            linhas.append(
                f"  - base recomendada que você ainda não cursou: "
                f"{'; '.join(p['base_pendente'])} - não impede o deferimento, "
                "mas a disciplina pressupõe esses conceitos (regra `base_recomendada`)"
            )
        from .oferta import nota_oferta

        nota = nota_oferta(p.get("paridade"))
        if nota:
            linhas.append(f"  - {nota} (vale confirmar com a coordenação)")
    linhas.append("")
    linhas.append(
        "O que não consigo verificar por aqui: falta de vagas, choque de "
        "horário (duas UCs no mesmo dia e horário) e matrícula em "
        "curso/termo/turno diferente do seu."
    )
    linhas.append("")
    linhas.append(
        "Se houver disputa por vagas, o art. 143 do Regulamento dos Cursos "
        "de Graduação (Resolução CONSU 246/2023; antigo art. 112) "
        "prioriza nesta ordem: seguir o currículo padrão; estar mais próximo "
        "de integralizar; não ter reprovação por frequência na UC; maior CR; "
        "cursos do mesmo campus; cursos de outros campi. Rematrícula concedida "
        "fora do prazo perde prioridade."
    )
    linhas.append("")
    linhas.append(
        "*Regras aplicadas: `unlock_condition` (pré-requisitos no Knowledge "
        "Graph) e os motivos de indeferimento do Regimento Interno da Prograd "
        "(2014).*"
    )
    return "\n".join(linhas)


_CURSADAS_RE = re.compile(
    r"(?:cursei|conclui|concluí|terminei|fiz|ja\s+cursei|ja\s+fiz|tendo\s+cursado|ja\s+tenho)\s*:?\s+(.+?)(?=\.\s|\?|$)",
    re.IGNORECASE,
)
_DESEJADAS_RE = re.compile(
    r"(?:matricular(?:-me)?\s+em|me\s+inscrever\s+em|inscricao\s+em|vagas?\s+em|pegar|pedir|cursar)\s*:?\s+(.+?)(?=\s+(?:tendo|ja\b|se\s+eu|sendo)|[.?]\s|\?$|\.$|$)",
    re.IGNORECASE,
)


def _split_lista(trecho: str) -> List[str]:
    partes = re.split(r",| e |;", trecho or "")
    return [p.strip(" .?!") for p in partes if p and p.strip(" .?!")]


def extrair_cursadas(texto: str) -> List[str]:
    m = _CURSADAS_RE.search(_strip_question(texto))
    return _split_lista(m.group(1)) if m else []


def extrair_desejadas(texto: str) -> List[str]:
    m = _DESEJADAS_RE.search(_strip_question(texto))
    return _split_lista(m.group(1)) if m else []


def _strip_question(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


_PROGRESSO_CUES_RES = [re.compile(p) for p in (
    r"\bquanto\s+(?:ainda\s+)?falta\b.*\b(?:formar|integralizar|concluir|terminar)",
    r"\b(?:o\s+que|oq)\s+(?:ainda\s+)?falta\s+(?:cursar|fazer)\b",
    r"\b(?:o\s+que|oq|quanto)\s+falta\s+(?:pra|para|p)\s+(?:eu\s+)?(?:me\s+)?(?:formar|concluir|terminar)",
    r"\bfalta\s+(?:pra|para|p)\s+(?:eu\s+)?(?:me\s+)?(?:formar|concluir|terminar)",
    r"\baudit\w*\b.*\b(?:situacao|progresso|curso)\b",
    r"\bmeu\s+progresso\b",
    r"\bconsigo\s+me\s+formar\b",
    r"\b(?:devendo|pendencias?|pendente)\b.*\b(?:diploma|formar|formatura|me\s+formar)\b",
    r"\bpegar\s+(?:o\s+|meu\s+)?diploma\b",
)]


def is_progresso_request(texto: str) -> bool:
    q = _norm(texto)
    return any(p.search(q) for p in _PROGRESSO_CUES_RES)


_MATRICULA_CUES_RES = [re.compile(p) for p in (
    r"\b(?:posso|consigo)\s+(?:me\s+)?(?:matricular|inscrever|pegar|cursar|pedir)\b",
    r"\b(?:vao|vai|sera|serao)\s+(?:deferir|deferida?s?|aceitar|indeferir)\b",
    r"\bminha\s+inscricao\s+(?:vai|sera)\b",
    r"\bvai\s+aceitar\b.*\b(?:pedido|inscricao|matricula|vagas?)\b",
)]


def is_matricula_request(texto: str) -> bool:
    q = _norm(texto)
    if not any(p.search(q) for p in _MATRICULA_CUES_RES):
        return False
    return bool(extrair_desejadas(texto))
