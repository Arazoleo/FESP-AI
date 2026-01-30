#!/usr/bin/env python3
"""
Script para converter arquivos JSON de disciplinas e regimentos para Markdown.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any


def disciplina_to_markdown(data: Dict[str, Any]) -> str:
    """Converte dados de uma disciplina JSON para Markdown."""
    d = data.get('disciplina', data)
    
    md = f"""# {d.get('nome', 'N/A')}

**Código:** {d.get('codigo', 'N/A')}  
**Nome em Inglês:** {d.get('nome_ingles', 'N/A')}  
**Campus:** {d.get('campus', 'N/A')}  
**Curso(s):** {', '.join(d.get('curso', []))}  
**Tipo:** {d.get('tipo', 'N/A')}  
**Formato:** {d.get('formato', 'N/A')}  
**Oferta:** {d.get('oferta', 'N/A')}  
**Termo:** {d.get('termo', 'N/A')}  
**Turno:** {d.get('turno', 'N/A') or 'N/A'}

## Docentes

{chr(10).join(f'- {docente}' for docente in (d.get('docentes', []) or []))}

## Pré-requisitos

"""
    
    pre_req = d.get('pre_requisitos', [])
    if pre_req:
        for req in pre_req:
            if isinstance(req, dict):
                md += f"- {req.get('nome', 'N/A')} (Código: {req.get('codigo', 'N/A')})\n"
            else:
                md += f"- {req}\n"
    else:
        md += "Não há pré-requisitos.\n"
    
    carga = d.get('carga_horaria', {})
    if carga:
        md += f"""
## Carga Horária

- **Total:** {carga.get('total', 'N/A')}h
- **Teórica:** {carga.get('teorica', 'N/A')}h
- **Prática:** {carga.get('pratica', 'N/A')}h
- **Extensão:** {carga.get('extensao', 'N/A')}h
"""
    
    ementa = d.get('ementa', {})
    if ementa:
        md += "\n## Ementa\n\n"
        desc = ementa.get('descricao_completa', '')
        if desc:
            md += f"{desc}\n\n"
        
        topicos = ementa.get('topicos', [])
        if topicos:
            md += "### Tópicos\n\n"
            for topico in topicos:
                md += f"- {topico}\n"
    
    biblio = d.get('bibliografia', {})
    if biblio:
        md += "\n## Bibliografia\n\n"
        
        for tipo in ['basica', 'complementar']:
            livros = biblio.get(tipo, [])
            if livros:
                md += f"### {tipo.title()}\n\n"
                for i, livro in enumerate(livros, 1):
                    autores = ', '.join(livro.get('autores', ['N/A']))
                    titulo = livro.get('titulo', 'N/A')
                    edicao = livro.get('edicao', '')
                    local = livro.get('local', '')
                    editora = livro.get('editora', '')
                    ano = livro.get('ano', '')
                    
                    ref = f"{i}. {autores}. **{titulo}**"
                    if edicao:
                        ref += f", {edicao}"
                    if local or editora or ano:
                        ref += f". {local}: {editora}, {ano}." if local and editora else f". {editora}, {ano}." if editora else f". {ano}."
                    md += f"{ref}\n"
                md += "\n"
    
    return md.strip()


def regimento_to_markdown(data: Dict[str, Any]) -> str:
    """Converte dados de um regimento JSON para Markdown."""
    doc_info = data.get('documento', {})
    
    md = f"""# {doc_info.get('tipo', 'Documento Institucional')}

"""
    
    # Informações gerais
    for campo in ['resolucao', 'instituicao', 'campus', 'data_vigencia', 'data_aprovacao', 'status']:
        valor = doc_info.get(campo)
        if valor:
            md += f"**{campo.replace('_', ' ').title()}:** {valor}  \n"
    
    md += "\n"
    
    # Objetivo
    if 'objetivo' in data:
        md += "## Objetivo\n\n"
        obj = data['objetivo']
        if isinstance(obj, dict):
            for k, v in obj.items():
                md += f"- **{k.replace('_', ' ').title()}:** {v}\n"
        else:
            md += f"{obj}\n"
        md += "\n"
    
    # Estrutura (artigos, seções, etc)
    if 'estrutura' in data:
        md += "## Estrutura\n\n"
        estrutura = data['estrutura']
        
        for secao_key, secao_data in estrutura.items():
            if not isinstance(secao_data, dict):
                continue
            
            titulo = secao_data.get('titulo', secao_data.get('nome', secao_key))
            md += f"### {titulo}\n\n"
            
            # Artigos
            for artigo in secao_data.get('artigos', []):
                numero = artigo.get('numero', 'N/A')
                conteudo = artigo.get('conteudo', '')
                if conteudo:
                    md += f"**Art. {numero}.** {conteudo}\n\n"
                    
                    if artigo.get('paragrafo_unico'):
                        md += f"Parágrafo único. {artigo['paragrafo_unico']}\n\n"
                    
                    for p in artigo.get('paragrafos', []):
                        if isinstance(p, dict):
                            num_p = p.get('numero', '')
                            md += f"**§ {num_p}.** {p.get('conteudo', '')}\n\n"
            
            # Capítulos
            for capitulo in secao_data.get('capitulos', []):
                cap_nome = capitulo.get('nome', '')
                md += f"#### {cap_nome}\n\n"
                for artigo in capitulo.get('artigos', []):
                    numero = artigo.get('numero', 'N/A')
                    conteudo = artigo.get('conteudo', '')
                    if conteudo:
                        md += f"**Art. {numero}.** {conteudo}\n\n"
            
            # Campos de texto da seção
            for campo in ['missao', 'visao', 'contexto', 'conclusao_diagnostico']:
                if campo in secao_data and isinstance(secao_data[campo], str):
                    md += f"**{campo.replace('_', ' ').title()}:** {secao_data[campo]}\n\n"
    
    # FAQs
    if 'perguntas_frequentes' in data:
        md += "## Perguntas Frequentes\n\n"
        for faq in data['perguntas_frequentes']:
            artigo = faq.get('artigo', '')
            if artigo:
                md += f"**Artigo:** {artigo}  \n"
            md += f"**Pergunta:** {faq.get('pergunta', '')}  \n"
            md += f"**Resposta:** {faq.get('resposta', '')}  \n\n"
    
    # Outros campos específicos
    campos_especiais = [
        'ponto_encontro', 'recursos_materiais', 'riscos_especificos',
        'procedimentos_emergencia', 'notas_importantes', 'contatos_emergencia',
        'glossario', 'tipos_atividades', 'artigos', 'fluxo_processo', 'resumo_executivo'
    ]
    
    for campo in campos_especiais:
        if campo in data:
            md += f"## {campo.replace('_', ' ').title()}\n\n"
            # Processar conforme tipo específico
            md += f"*[Conteúdo específico de {campo}]*\n\n"
    
    return md.strip()


def convert_file(json_path: Path, output_dir: Path):
    """Converte um arquivo JSON para Markdown."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if 'disciplinas' in str(json_path):
        md_content = disciplina_to_markdown(data)
        output_path = output_dir / json_path.name.replace('.json', '.md')
    elif 'regimentos' in str(json_path):
        md_content = regimento_to_markdown(data)
        output_path = output_dir / json_path.name.replace('.json', '.md')
    else:
        print(f"Tipo desconhecido para {json_path}")
        return
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"✓ Convertido: {json_path.name} -> {output_path.name}")


def main():
    """Função principal."""
    base_dir = Path(__file__).parent
    
    # Diretórios
    disciplinas_dir = base_dir / 'jsons_disciplinas'
    regimentos_dir = base_dir / 'jsons_regimentos'
    
    # Criar diretórios de saída
    md_disciplinas_dir = base_dir / 'markdown_disciplinas'
    md_regimentos_dir = base_dir / 'markdown_regimentos'
    
    md_disciplinas_dir.mkdir(exist_ok=True)
    md_regimentos_dir.mkdir(exist_ok=True)
    
    # Converter disciplinas
    print("Convertendo disciplinas...")
    for json_file in disciplinas_dir.glob('*.json'):
        convert_file(json_file, md_disciplinas_dir)
    
    # Converter regimentos
    print("\nConvertendo regimentos...")
    for json_file in regimentos_dir.glob('*.json'):
        convert_file(json_file, md_regimentos_dir)
    
    print("\n✓ Conversão concluída!")


if __name__ == '__main__':
    main()


