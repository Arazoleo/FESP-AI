"""
Gera markdown_cursos/quadro_ucs_bct_dae.md e atualiza
src/interdisciplinares_seed.json a partir da planilha oficial "LISTA DE UCs -
BCT" publicada pela DAE-SJC (linkada em /materiais/quadros-de-ucs).

Uso: python3 gerar_quadro_ucs_dae.py
Rodar quando a DAE atualizar o quadro; o resultado é commitado no repo.
"""

import csv
import io
import json
import urllib.request

PLANILHA = "1uOFS9nw3GPWgK7xGMLiDNe6OKqfjBcuuKKtByK-prqQ"
ABAS = {
    "todas": "1513963780",
    "interdisciplinares": "997166242",
    "extensionistas": "1838229186",
}
UA = {"User-Agent": "FESP-AI/1.0"}


def baixar_csv(gid: str):
    url = (
        f"https://docs.google.com/spreadsheets/d/{PLANILHA}/pub"
        f"?gid={gid}&single=true&output=csv"
    )
    req = urllib.request.Request(url, headers=UA)
    dados = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    linhas = []
    for row in csv.reader(io.StringIO(dados)):
        if len(row) > 7 and row[2].strip().isdigit():
            linhas.append({
                "categoria": row[0].strip(),
                "termo": row[1].strip(),
                "codigo": row[2].strip(),
                "nome": row[3].strip(),
                "ch_extensao": row[6].strip(),
                "ch_total": row[7].strip(),
                "prereqs": row[8].strip(),
                "equivalentes": row[9].strip() if len(row) > 9 else "",
            })
    return linhas


def tabela(ucs, com_extensao=False):
    cab = "| Termo | Código | UC | CH Total |"
    sep = "|-------|--------|----|----------|"
    if com_extensao:
        cab += " CH Extensão |"
        sep += "-------------|"
    cab += " Pré-requisitos (código) | Equivalentes (código) |"
    sep += "------------------------|----------------------|"
    linhas = [cab, sep]
    for u in ucs:
        linha = f"| {u['termo']} | {u['codigo']} | {u['nome']} | {u['ch_total']}h |"
        if com_extensao:
            linha += f" {u['ch_extensao'] or '-'}h |" if u["ch_extensao"] else " - |"
        linha += f" {u['prereqs'] or '-'} | {u['equivalentes'] or '-'} |"
        linhas.append(linha)
    return linhas


def main():
    todas = baixar_csv(ABAS["todas"])
    inter = baixar_csv(ABAS["interdisciplinares"])
    ext = baixar_csv(ABAS["extensionistas"])
    print(f"todas: {len(todas)} | interdisciplinares: {len(inter)} | extensionistas: {len(ext)}")

    seed_atual = json.load(open("src/interdisciplinares_seed.json"))
    oficiais = {u["codigo"] for u in inter}
    ucs_seed = [
        {"codigo": u["codigo"], "nome": u["nome"].title(), "fonte": "dae_quadro_ucs"}
        for u in inter
    ]
    mantidas_ppc = []
    for u in seed_atual.get("ucs", []):
        cod = str(u.get("codigo") or "").strip()
        if cod and cod in oficiais:
            continue
        nomes_oficiais = {x["nome"].lower() for x in inter}
        if u["nome"].lower() in nomes_oficiais:
            continue
        mantidas_ppc.append({**u, "fonte": "ppc_2023"})
    seed_novo = {
        "regra": seed_atual.get("regra"),
        "fonte": (
            "Lista oficial da DAE-SJC (planilha Quadro de UCs, aba Eletivas "
            "Interdisciplinares) + UCs remanescentes do anexo do PPC 2023"
        ),
        "ucs": ucs_seed + mantidas_ppc,
    }
    with open("src/interdisciplinares_seed.json", "w") as f:
        json.dump(seed_novo, f, ensure_ascii=False, indent=2)
    print(f"seed: {len(ucs_seed)} oficiais + {len(mantidas_ppc)} mantidas do PPC")

    por_cat = {}
    for u in todas:
        por_cat.setdefault(u["categoria"], []).append(u)

    linhas = [
        "# Quadro de UCs do BCT - Lista oficial da DAE-SJC",
        "",
        "Lista completa das Unidades Curriculares do Bacharelado Interdisciplinar",
        "em Ciência e Tecnologia (BCT), mantida pela DAE-SJC (Divisão de Assuntos",
        "Educacionais). Inclui termo de referência, código, carga horária,",
        "pré-requisitos e UCs equivalentes (por código, para aproveitamento de",
        "estudos).",
        "",
        "Fonte: página Materiais > Quadros de UCs do site da DAE-SJC",
        "(https://dae-sjc.unifesp.br/materiais/quadros-de-ucs)",
        "",
    ]
    for cat in sorted(por_cat):
        ucs = por_cat[cat]
        linhas.append(f"## UCs {cat.title()} do BCT ({len(ucs)} UCs)")
        linhas.append("")
        linhas.extend(tabela(ucs))
        linhas.append("")

    linhas.append(f"## UCs Eletivas Interdisciplinares do BCT ({len(inter)} UCs)")
    linhas.append("")
    linhas.append(
        "O PPC 2023 do BCT exige **4 UCs Eletivas Interdisciplinares**, "
        "independentemente da carga horária. Estas são as UCs que contam:"
    )
    linhas.append("")
    linhas.extend(tabela(inter))
    linhas.append("")

    linhas.append(
        f"## UCs Eletivas com Carga Horária Extensionista - BCT ({len(ext)} UCs)"
    )
    linhas.append("")
    linhas.append(
        "O BCT (PPC 2023) exige **240 horas de extensão** cumpridas em Eletivas "
        "Extensionistas ou Atividades Complementares Extensionistas. Estudantes "
        "que ingressaram ANTES de 2023 estão dispensados das 240 horas "
        "extensionistas. Estas são as eletivas que dão horas de extensão:"
    )
    linhas.append("")
    linhas.extend(tabela(ext, com_extensao=True))
    linhas.append("")

    with open("markdown_cursos/quadro_ucs_bct_dae.md", "w") as f:
        f.write("\n".join(linhas))
    print("markdown_cursos/quadro_ucs_bct_dae.md gerado")


if __name__ == "__main__":
    main()
