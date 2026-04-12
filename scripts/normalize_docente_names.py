#!/usr/bin/env python3
"""
Normaliza nomes de docentes nos arquivos markdown de disciplinas.

Estratégia:
1. Extrai nomes canônicos de markdown_docentes/corpo_docente_ict.md
2. Para cada docente em ## Docentes de cada disciplina:
   - Tenta matching por subset de palavras (normalizado sem acentos)
   - Se encontrar, substitui pelo nome canônico completo
   - Se não encontrar, mantém e registra no relatório
3. Reescreve o arquivo se houve alguma substituição
"""

import re
import sys
import unicodedata
from pathlib import Path
from typing import Optional

CORPUS_FILE = Path(__file__).parent.parent / "markdown_docentes" / "corpo_docente_ict.md"
DISCIPLINAS_DIR = Path(__file__).parent.parent / "markdown_disciplinas"

# Palavras ignoradas no matching (preposições e artigos)
STOPWORDS = {"de", "da", "do", "dos", "das", "e", "a", "o"}

# Mapeamentos manuais para casos que o algoritmo não consegue resolver automaticamente:
# - Grafias alternativas (Luiz/Luis)
# - Typos (Martin/Martini)
# - Nomes muito curtos ou ambíguos resolvidos manualmente
MANUAL_OVERRIDES = {
    "leandro batista": "Leandro Candido",
    "luiz felipe": "Luis Felipe Cesar da Rocha Bueno",
    "thiago martin": "Thiago Martini Pereira",
    "erwin doescher": "Erwin Doescher",
    # "erwin" sozinho → Erwin Doescher (único Erwin no corpus)
    "erwin": "Erwin Doescher",
    # Cláudia Santos em disciplinas de Matemática → Cláudia Aline A. S. Mesquita
    "cláudia santos": "Cláudia Aline A. S. Mesquita",
    "claudia santos": "Cláudia Aline A. S. Mesquita",
}


def normalize(text):
    # type: (str) -> str
    """Remove acentos, lowercase, strip."""
    nfd = unicodedata.normalize("NFD", text.lower().strip())
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def tokenize(name):
    # type: (str) -> frozenset
    """
    Tokeniza um nome em palavras normalizadas, expandindo hifens e
    filtrando stopwords, abreviações com ponto e palavras muito curtas.
    """
    # Expandir hifens: "Vega-Oliveros" → "Vega Oliveros"
    expanded = name.replace("-", " ")
    words = set()
    for w in expanded.split():
        w_norm = normalize(w)
        # Ignorar stopwords, abreviações (terminam com ponto), muito curtas
        if w_norm in STOPWORDS:
            continue
        if w_norm.endswith("."):
            # Abreviação: guardar apenas a inicial (ex: "F." → "f")
            initial = w_norm[0]
            if initial.isalpha():
                words.add("INIT:" + initial)
            continue
        if len(w_norm) <= 1:
            continue
        words.add(w_norm)
    return frozenset(words)


def clean_discipline_name(raw):
    # type: (str) -> str
    """
    Remove prefixos Prof./Dr. e sufixos com e-mail/departamento
    que possam estar no campo de docente de alguns arquivos.
    """
    # Remover e-mail entre parênteses ou após "/"
    raw = re.sub(r'\s*/.*$', '', raw)
    raw = re.sub(r'\s*\(.*?\)', '', raw)
    # Remover prefixos acadêmicos
    raw = re.sub(
        r'^(?:Prof(?:a)?\.?\s+)?(?:Dr(?:a)?\.?\s+)?',
        '', raw, flags=re.IGNORECASE
    )
    return raw.strip()


def extract_canonical_names(corpus_path):
    """Extrai nomes canônicos do corpo docente."""
    content = corpus_path.read_text(encoding="utf-8")
    names = []
    for match in re.finditer(
        r"###\s+(?:Prof(?:a)?\.?\s+)?(?:Dr(?:a)?\.?\s+)?(.+)", content
    ):
        name = match.group(1).strip()
        if name:
            names.append(name)
    return names


def build_lookup(canonical_names):
    """
    Constrói mapa: frozenset_of_tokens -> canonical_name
    Para cada nome canônico, armazena o conjunto de seus tokens normalizados.
    """
    lookup = {}
    for name in canonical_names:
        tokens = tokenize(name)
        if tokens:
            lookup[tokens] = name
    return lookup


def find_canonical(short_name, lookup):
    # type: (str, dict) -> Optional[str]
    """
    Tenta encontrar o nome canônico para um nome curto via três estratégias:

    1. Forward subset: tokens(short) ⊆ tokens(canonical)
       Ex: "Thaciana Malaspina" → "Thaciana Valentina Malaspina Fileti"

    2. Reverse subset: tokens(canonical) ⊆ tokens(short)
       Ex: "Regiane Albertini de Carvalho" → "Regiane Albertini"
       (disciplina tem sobrenome extra que não está no canônico)

    3. Initial matching: abreviações (INIT:x) devem ser compatíveis com a
       primeira letra do token correspondente no canônico.
    """
    cleaned = clean_discipline_name(short_name)
    short_tokens = tokenize(cleaned)

    # Separar tokens reais de iniciais
    short_real = frozenset(t for t in short_tokens if not t.startswith("INIT:"))
    short_inits = frozenset(t[5:] for t in short_tokens if t.startswith("INIT:"))

    if len(short_real) < 2 and not short_inits:
        return None  # muito curto para matching seguro

    candidates = []

    for canonical_tokens, canonical_name in lookup.items():
        canon_real = frozenset(t for t in canonical_tokens if not t.startswith("INIT:"))

        # Verificar se as iniciais do nome curto são compatíveis com o canônico
        inits_ok = all(
            any(ct.startswith(init) for ct in canon_real)
            for init in short_inits
        )
        if not inits_ok:
            continue

        # Estratégia 1: tokens reais do curto ⊆ tokens canônicos
        if short_real and short_real.issubset(canon_real):
            overlap = len(short_real & canon_real)
            candidates.append((overlap, len(canonical_name), canonical_name))
            continue

        # Estratégia 2: tokens canônicos ⊆ tokens reais do curto
        # (nome na disciplina tem palavras extras não presentes no canônico)
        if canon_real and canon_real.issubset(short_real) and len(canon_real) >= 2:
            overlap = len(short_real & canon_real)
            candidates.append((overlap, len(canonical_name), canonical_name))

    if not candidates:
        return None

    # Preferir maior sobreposição; em empate, nome canônico menor (mais seguro)
    candidates.sort(key=lambda x: (-x[0], x[1]))
    return candidates[0][2]


def extract_docentes_section(content):
    """
    Retorna (start_idx, end_idx, lista_de_nomes) da seção ## Docentes.
    start/end são índices da linha do primeiro '-' ao final da seção.
    """
    match = re.search(r"## Docentes\n\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if not match:
        return -1, -1, []

    section_text = match.group(1)
    names = [
        item.replace("- ", "").strip()
        for item in section_text.split("\n")
        if item.strip().startswith("- ")
    ]
    return match.start(1), match.end(1), names


def rebuild_docentes_section(names: list[str]) -> str:
    """Reconstrói o texto da seção de docentes."""
    return "\n".join(f"- {name}" for name in names) + "\n"


def process_file(
    filepath: Path,
    lookup: dict[frozenset, str],
    not_found: dict[str, list[str]],
    dry_run: bool = False,
) -> int:
    """
    Processa um arquivo de disciplina.
    Retorna número de substituições feitas.
    """
    content = filepath.read_text(encoding="utf-8")
    start, end, names = extract_docentes_section(content)

    if not names:
        return 0

    new_names = []
    changes = 0
    for name in names:
        # Verificar overrides manuais primeiro
        override = MANUAL_OVERRIDES.get(name.lower().strip())
        if override and override != name:
            new_names.append(override)
            changes += 1
            continue

        canonical = find_canonical(name, lookup)
        if canonical and canonical != name:
            new_names.append(canonical)
            changes += 1
        else:
            new_names.append(name)
            if canonical is None and not override:
                not_found.setdefault(name, []).append(filepath.name)

    if changes > 0 and not dry_run:
        new_section = rebuild_docentes_section(new_names)
        new_content = content[:start] + new_section + content[end:]
        filepath.write_text(new_content, encoding="utf-8")

    return changes


def main():
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("Normalizador de Nomes de Docentes")
    print("=" * 60)
    if dry_run:
        print("MODO: dry-run (nenhum arquivo será alterado)\n")
    else:
        print("MODO: escrita (arquivos serão alterados)\n")

    # 1. Extrair nomes canônicos
    canonical_names = extract_canonical_names(CORPUS_FILE)
    print(f"Nomes canônicos extraídos do corpus: {len(canonical_names)}")

    # 2. Construir lookup
    lookup = build_lookup(canonical_names)

    # 3. Processar arquivos
    md_files = sorted(DISCIPLINAS_DIR.glob("*.md"))
    print(f"Arquivos de disciplinas encontrados: {len(md_files)}\n")

    total_files_changed = 0
    total_substitutions = 0
    not_found: dict[str, list[str]] = {}

    for filepath in md_files:
        changes = process_file(filepath, lookup, not_found, dry_run=dry_run)
        if changes > 0:
            total_files_changed += 1
            total_substitutions += changes
            print(f"  [{changes} troca(s)] {filepath.name}")

    # 4. Relatório
    print(f"\n{'=' * 60}")
    print("RELATÓRIO FINAL")
    print(f"{'=' * 60}")
    print(f"Arquivos modificados: {total_files_changed}/{len(md_files)}")
    print(f"Substituições totais: {total_substitutions}")

    if not_found:
        print(f"\nNOMES NÃO ENCONTRADOS NO CORPUS ({len(not_found)} únicos):")
        print("(Mantidos como estão — verificar manualmente)\n")
        for name, files in sorted(not_found.items()):
            print(f"  '{name}'")
            for f in files[:3]:
                print(f"    → {f}")
            if len(files) > 3:
                print(f"    → ... e mais {len(files) - 3} arquivo(s)")
    else:
        print("\nTodos os nomes foram mapeados com sucesso.")

    print(f"\n{'=' * 60}")


if __name__ == "__main__":
    main()
