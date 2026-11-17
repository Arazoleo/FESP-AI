"""
Autoevolução verificada do KG: das falhas em produção a correções de dado com
proveniência, sob aprovação humana.

1. CLASSIFICAR pela própria base, não por palpite: para a pergunta que falhou
   (miss ou cobertura incompleta), o contrato do intent diz qual atributo foi
   pedido e o KG diz se tem o valor.
     - KG tem o valor e a resposta não trouxe → CÓDIGO (roteamento/handler/
       grounding): vira work order.
     - KG não tem o valor → DADO: vira lacuna na fila de curadoria.
2. PROPOR o valor que falta a partir das fontes da própria base (markdowns e
   crawl do site): o LLM devolve valor + citação literal + arquivo.
3. VERIFICAR sem LLM: a citação existe literalmente no arquivo, o valor está
   na citação, a citação é sobre a entidade e o valor tem o tipo do atributo
   (email, número de créditos, docente que existe no KG...). Só proposta
   verificada vai para o humano aprovar; nada entra no KG sozinho.

Diferente de ajustar pesos a partir de feedback (EvoRAG): a mudança é um fato
simbólico, com fonte citada e checagem determinística, auditável no PR.
"""

import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from .coverage import CONTRATOS, _conteudo, _tokens, entidade_coberta, entidades_da_pergunta

# atributos guardados no PRÓPRIO nó (não em arestas): intent -> (tipo, atributo, chaves)
ATRIBUTOS_NO = {
    "matriz_info": ("disciplina", "créditos ou carga horária", ("creditos", "carga_horaria")),
}

FONTES_PADRAO = ("markdown_disciplinas", "markdown_docentes", "markdown_cursos",
                 "markdown_regimentos")


def _valores(kg, intent: str, tipo_ent: str, nome: str) -> Optional[list]:
    """Valores que o KG tem para o atributo do intent; None = intent sem contrato."""
    if intent in CONTRATOS:
        tipo, _, valores_de = CONTRATOS[intent]
        if tipo != tipo_ent:
            return None
        try:
            return valores_de(kg, nome)
        except Exception:
            return []
    if intent in ATRIBUTOS_NO:
        tipo, _, chaves = ATRIBUTOS_NO[intent]
        if tipo != tipo_ent:
            return None
        node = kg._find_node(nome, tipo)
        dados = kg.graph.nodes[node] if node else {}
        return [dados[c] for c in chaves if kg._has_real_value(dados.get(c))]
    return None


def atributo_do_intent(intent: str) -> str:
    if intent in CONTRATOS:
        return CONTRATOS[intent][1]
    if intent in ATRIBUTOS_NO:
        return ATRIBUTOS_NO[intent][1]
    return ""


def classificar(kg, pergunta: str, intent: str) -> List[Dict]:
    """[{entidade, tipo_entidade, atributo, classe}] para a pergunta que falhou."""
    out = []
    for tipo, nome in entidades_da_pergunta(kg, pergunta):
        valores = _valores(kg, intent, tipo, nome)
        if valores is None:
            continue
        out.append({"entidade": nome, "tipo_entidade": tipo,
                    "atributo": atributo_do_intent(intent), "intent": intent,
                    "classe": "codigo" if valores else "dado"})
    return out


def lacunas_do_log(kg, turnos: Iterable[Dict]) -> List[Dict]:
    """Agrega os turnos com falha (miss ou cobertura_faltante) por
    (classe, entidade, atributo), com frequência e exemplos."""
    agreg: "OrderedDict[tuple, Dict]" = OrderedDict()
    for t in turnos:
        if not (t.get("miss") or t.get("cobertura_faltante")):
            continue
        for c in classificar(kg, t.get("question", ""), t.get("intent", "")):
            chave = (c["classe"], c["entidade"], c["atributo"])
            a = agreg.setdefault(chave, {**c, "frequencia": 0, "exemplos": []})
            a["frequencia"] += 1
            q = t.get("question", "")
            if q and q not in a["exemplos"] and len(a["exemplos"]) < 5:
                a["exemplos"].append(q)
    return sorted(agreg.values(), key=lambda a: -a["frequencia"])


# ----------------------------------------------------------- proposta + prova

def _dobra(t: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFD", (t or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def _posicoes(seq: List[str], frase: List[str]) -> List[int]:
    n = len(frase)
    return [i for i in range(len(seq) - n + 1) if seq[i:i + n] == frase]


def trechos_fonte(raiz: Path, entidade: str, fontes=FONTES_PADRAO,
                  janela: int = 2, limite: int = 12) -> List[Dict]:
    """Trechos dos markdowns da base que citam a entidade (com contexto),
    os mais prováveis primeiro: nome exato (não "Álgebra Linear II" para
    "Álgebra Linear"), linha de tabela, arquivo da própria entidade."""
    alvo = _conteudo(entidade)
    if not alvo:
        return []
    nome = _dobra(entidade)
    achados = []
    for d in fontes:
        for arq in sorted((raiz / d).glob("*.md")):
            linhas = arq.read_text(encoding="utf-8", errors="ignore").splitlines()
            proprio = _conteudo(arq.stem.replace("_", " ")) == alvo
            for i, l in enumerate(linhas):
                toks = _conteudo(l)
                pos = _posicoes(toks, alvo)
                if not pos:
                    continue
                # nome inteiro numa célula/frase: termina em delimitador
                exato = bool(re.search(re.escape(nome) + r"\s*(\||$|[,.;:)])", _dobra(l)))
                score = 4 * exato + 2 * ("|" in l) + proprio
                ini, fim = max(0, i - janela), min(len(linhas), i + janela + 1)
                achados.append((-score, len(achados), {
                    "arquivo": str(arq.relative_to(raiz)), "linha": i + 1,
                    "texto": "\n".join(linhas[ini:fim])}))
    return [t for _, _, t in sorted(achados)[:limite]]


_PROMPT = """Você completa uma base de conhecimento acadêmica. Falta o atributo
"{atributo}" da entidade "{entidade}" ({tipo}).

Use SÓ os trechos abaixo. Se nenhum trecho traz o valor, responda {{"valor": null}}.
Senão responda com o valor, a CITAÇÃO LITERAL (copiada exatamente do trecho,
uma linha) que o contém e o arquivo de onde veio.

TRECHOS:
{trechos}

Responda APENAS com JSON: {{"valor": "...", "citacao": "...", "arquivo": "..."}}"""


def propor(lacuna: Dict, raiz: Path, llm: Callable[[str], str]) -> Optional[Dict]:
    trechos = trechos_fonte(raiz, lacuna["entidade"])
    if not trechos:
        return None
    texto = "\n\n".join(f"[{t['arquivo']}:{t['linha']}]\n{t['texto']}" for t in trechos)
    bruto = llm(_PROMPT.format(atributo=lacuna["atributo"], entidade=lacuna["entidade"],
                               tipo=lacuna["tipo_entidade"], trechos=texto))
    m = re.search(r"\{.*\}", bruto or "", re.DOTALL)
    if not m:
        return None
    try:
        prop = json.loads(m.group(0))
    except ValueError:
        return None
    return prop if prop.get("valor") not in (None, "", "null") else None


def _sem_espaco(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


_TIPO_VALOR = {
    "créditos ou carga horária": lambda v, kg: bool(re.fullmatch(r"\d{1,3}\s*(h|horas)?", v.strip())),
    "contato ou áreas": lambda v, kg: bool(re.fullmatch(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", v.strip()))
    or 2 <= len(v) <= 120,
    "docentes": lambda v, kg: all(kg.docente_mencionado(p) for p in re.split(r",| e ", v) if p.strip()),
    "áreas de pesquisa": lambda v, kg: 2 <= len(v) <= 200,
    "ementa": lambda v, kg: len(v) >= 40,
}


def verificar(proposta: Dict, lacuna: Dict, raiz: Path, kg=None,
              fontes=FONTES_PADRAO) -> Dict:
    """Checagens determinísticas da proposta. {"ok": bool, "motivos": [...]}"""
    motivos = []
    arq = (raiz / str(proposta.get("arquivo", ""))).resolve()
    permitido = any(str(arq).startswith(str((raiz / d).resolve()) + "/") for d in fontes)
    if not permitido or not arq.is_file():
        motivos.append("arquivo fora das fontes da base ou inexistente")
        return {"ok": False, "motivos": motivos}
    fonte = _sem_espaco(arq.read_text(encoding="utf-8", errors="ignore"))
    citacao = _sem_espaco(proposta.get("citacao", ""))
    if not citacao or citacao not in fonte:
        motivos.append("citação não existe literalmente no arquivo")
    valor = str(proposta.get("valor", ""))
    if not valor or " ".join(_tokens(valor)) not in " ".join(_tokens(citacao)):
        motivos.append("valor não está na citação")
    sobre = (entidade_coberta(lacuna["tipo_entidade"], lacuna["entidade"], citacao)
             or all(w in _tokens(arq.stem.replace("_", " ")) for w in _conteudo(lacuna["entidade"])))
    if not sobre:
        motivos.append("citação não é sobre a entidade")
    tipo_ok = _TIPO_VALOR.get(lacuna["atributo"], lambda v, kg: True)
    try:
        if not tipo_ok(valor, kg):
            motivos.append(f"valor não tem o tipo de '{lacuna['atributo']}'")
    except Exception:
        motivos.append("checagem de tipo falhou")
    return {"ok": not motivos, "motivos": motivos}
