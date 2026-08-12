"""
Gera src/requisitos_seed.json e markdown_cursos/criterios_integralizacao_siiu.md
a partir do sistema oficial de Cursos e Matrizes Curriculares da Unifesp (SIIU).

Uso: python3 gerar_requisitos_siiu.py
Rodar quando a Prograd publicar matriz nova; o resultado é commitado no repo.
"""

import base64
import json
import re
import html as html_mod
import urllib.request

BASE = "https://cursos.siiu.unifesp.br/graduacao/curso"
UA = "FESP-AI/1.0 (assistente academico UNIFESP ICT)"

CURSOS = [
    {"id": "1337", "sigla": "BCT", "turno": "integral"},
    {"id": "1621", "sigla": "BCT", "turno": "noturno"},
    {"id": "1670", "sigla": "EM", "turno": "integral"},
    {"id": "1671", "sigla": "BCC", "turno": "integral"},
    {"id": "1672", "sigla": "BBT", "turno": "integral"},
    {"id": "1673", "sigla": "BMC", "turno": "integral"},
    {"id": "1674", "sigla": "EB", "turno": "integral"},
    {"id": "1675", "sigla": "EC", "turno": "integral"},
]


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def _texto(html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    t = html_mod.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


def _matriz_ativa_url(curso_id: str, detalhes_html: str):
    cods = sorted(set(re.findall(r"matriz-curricular/([A-Za-z0-9+/=]+)/detalhes", detalhes_html)))
    for b64 in cods:
        try:
            info = json.loads(base64.b64decode(b64))
        except Exception:
            continue
        if str(info.get("curso_id_curso")) != curso_id:
            continue
        url = f"{BASE}/matriz-curricular/{b64}/detalhes"
        page = _get(url)
        m = re.search(r"Matriz:\s*(\d+)\s*-\s*ATIVA", _texto(page))
        if m:
            return url, page, f"{m.group(1)} - ATIVA"
    return None, None, None


_CRIT_RE = re.compile(
    r"(C\d+)\s+(DISCIPLINA|ATIVIDADE COMPLEMENTAR|ESTÁGIO|TRABALHO DE CONCLUSÃO DE CURSO|MÓDULO)\s+"
    r"(.+?)\s+(\d+)\s+(\d+)\s+(\d+)"
)


def _parse_criterios(texto: str):
    i = texto.rfind("Carga Horária para Total")
    if i < 0:
        return None, []
    trecho = texto[i:i + 1200]
    total = None
    m = re.search(r"Carga Horária para Total:\s*(\d+)", trecho)
    if m:
        total = int(m.group(1))
    fim = trecho.find("Tipos de Unidade Curricular")
    if fim > 0:
        trecho = trecho[:fim]
    criterios = []
    for c in _CRIT_RE.finditer(trecho):
        criterios.append({
            "criterio": c.group(1),
            "tipo": c.group(2),
            "expressao": c.group(3).strip(),
            "minimo_h": int(c.group(4)),
            "maximo_h": int(c.group(5)),
            "para_total_h": int(c.group(6)),
        })
    return total, criterios


def main():
    seed = []
    for curso in CURSOS:
        detalhes_url = f"{BASE}/{curso['id']}/detalhes"
        detalhes = _get(detalhes_url)
        texto_det = _texto(detalhes)
        m = re.search(r"Curso:\s*([A-ZÀ-Ü][^()]{5,80})\(", texto_det)
        nome = m.group(1).strip() if m else curso["sigla"]
        matriz_url, matriz_page, matriz_nome = _matriz_ativa_url(curso["id"], detalhes)
        if not matriz_page:
            print(f"AVISO: matriz ativa nao encontrada para {curso['sigla']} {curso['turno']}")
            continue
        total, criterios = _parse_criterios(_texto(matriz_page))
        seed.append({
            "sigla": curso["sigla"],
            "turno": curso["turno"],
            "curso_id": curso["id"],
            "nome": nome,
            "matriz": matriz_nome,
            "total_h": total,
            "criterios": criterios,
            "fonte": matriz_url,
        })
        resumo = ", ".join(f"{c['expressao']} {c['para_total_h']}h" for c in criterios)
        print(f"{curso['sigla']} ({curso['turno']}): total {total}h -> {resumo}")

    with open("src/requisitos_seed.json", "w") as f:
        json.dump(seed, f, ensure_ascii=False, indent=2)
    print(f"\nsrc/requisitos_seed.json: {len(seed)} matrizes")

    linhas = [
        "# Critérios Oficiais de Integralização - Cursos do ICT (SIIU/Unifesp)",
        "",
        "Fonte: sistema oficial de Cursos e Matrizes Curriculares da Unifesp",
        "(cursos.siiu.unifesp.br), matriz ATIVA de cada curso do campus São José",
        "dos Campos. Carga horária mínima exigida por componente para colar grau.",
        "",
    ]
    def rotulo_componente(c):
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

    for s in seed:
        titulo = f"{s['nome']} ({s['sigla']}"
        titulo += f" - {s['turno']})" if s["sigla"] == "BCT" else ")"
        linhas.append(f"## {titulo}")
        linhas.append("")
        linhas.append(
            f"Para integralizar (concluir e colar grau) o curso {s['nome']} "
            f"({s['sigla']}) são exigidas **{s['total_h']} horas** no total, "
            "divididas assim:"
        )
        linhas.append("")
        linhas.append("| Componente | Carga horária exigida |")
        linhas.append("|------------|----------------------|")
        for c in s["criterios"]:
            linhas.append(f"| {rotulo_componente(c)} | {c['para_total_h']}h |")
        if s["sigla"] == "BCT":
            linhas.append("| Extensão curricularizada (PPC 2023) | 240h |")
            linhas.append("| UCs Eletivas Interdisciplinares (PPC 2023) | 4 UCs |")
        linhas.append("")
        linhas.append(f"Matriz: {s['matriz']}. Fonte: {s['fonte']}")
        linhas.append("")
    with open("markdown_cursos/criterios_integralizacao_siiu.md", "w") as f:
        f.write("\n".join(linhas))
    print("markdown_cursos/criterios_integralizacao_siiu.md gerado")


if __name__ == "__main__":
    main()
