"""
Parsers para arquivos Markdown de disciplinas e regimentos.
Versão otimizada para RAG com metadados ricos e chunking semântico.
"""

import re
from typing import List, Dict, Optional, Tuple
from langchain_core.documents import Document


def _chunk_texto(texto: str, tamanho: int = 1400) -> List[str]:
    """Divide texto longo em pedaços por parágrafo, respeitando o tamanho."""
    paragrafos = re.split(r"\n\n+", texto or "")
    pedacos, atual = [], ""
    for p in paragrafos:
        p = p.strip()
        if not p:
            continue
        if atual and len(atual) + len(p) + 2 > tamanho:
            pedacos.append(atual)
            atual = p
        else:
            atual = f"{atual}\n\n{p}" if atual else p
        while len(atual) > tamanho * 2:
            pedacos.append(atual[:tamanho])
            atual = atual[tamanho:]
    if atual:
        pedacos.append(atual)
    return pedacos


class DisciplinaMarkdownParser:
    """Parser otimizado para arquivos Markdown de disciplinas."""
    
    @staticmethod
    def parse(filepath: str) -> List[Document]:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        docs = []
        
        meta_info = DisciplinaMarkdownParser._extract_all_metadata(content)
        nome = meta_info.get('nome', 'N/A')
        codigo = meta_info.get('codigo', 'N/A')
        
        sigla = meta_info.get('sigla', '')
        base_meta = {
            'tipo_documento': 'disciplina',
            'disciplina': nome,
            'codigo': codigo,
            'sigla': sigla,
            'campus': meta_info.get('campus', 'N/A'),
            'curso': meta_info.get('curso', 'N/A'),
            'termo': meta_info.get('termo', 'N/A'),
            'turno': meta_info.get('turno', 'N/A'),
            'tipo': meta_info.get('tipo', 'N/A'),
            'source': filepath
        }
        
        docentes = DisciplinaMarkdownParser._extract_docentes(content)
        docentes_str = ', '.join(docentes) if docentes else 'N/A'
        
        pre_requisitos = DisciplinaMarkdownParser._extract_pre_requisitos(content)
        pre_req_str = '; '.join(pre_requisitos) if pre_requisitos else 'Nenhum'
        
        carga_horaria = DisciplinaMarkdownParser._extract_carga_horaria(content)
        
        sigla_info = f"\nSigla: {sigla}" if sigla else ""
        info_completa = f"""DISCIPLINA: {nome}
Código: {codigo}{sigla_info}
Campus: {base_meta['campus']}
Curso: {base_meta['curso']}
Termo: {base_meta['termo']}
Turno: {base_meta['turno']}
Tipo: {base_meta['tipo']}

DOCENTES: {docentes_str}

PRÉ-REQUISITOS: {pre_req_str}

CARGA HORÁRIA:
- Total: {carga_horaria.get('total', 'N/A')}
- Teórica: {carga_horaria.get('teorica', 'N/A')}
- Prática: {carga_horaria.get('pratica', 'N/A')}
- Extensão: {carga_horaria.get('extensao', 'N/A')}"""
        
        docs.append(Document(
            page_content=info_completa.strip(),
            metadata={**base_meta, 'secao': 'info_geral', 'docentes': docentes_str, 'pre_requisitos': pre_req_str}
        ))
        
        doc_docentes = f"""DISCIPLINA: {nome} (Código: {codigo})
QUEM LECIONA / PROFESSORES / DOCENTES:
{chr(10).join(f'- {d}' for d in docentes) if docentes else 'Informação não disponível'}

Os professores da disciplina {nome} são: {docentes_str}"""
        
        docs.append(Document(
            page_content=doc_docentes.strip(),
            metadata={**base_meta, 'secao': 'docentes', 'docentes': docentes_str}
        ))
        
        if pre_requisitos:
            doc_pre_req = f"""DISCIPLINA: {nome} (Código: {codigo})
PRÉ-REQUISITOS / REQUISITOS / DEPENDÊNCIAS:
{chr(10).join(f'- {p}' for p in pre_requisitos)}

Para cursar {nome}, o aluno deve ter aprovação em: {pre_req_str}"""
            
            docs.append(Document(
                page_content=doc_pre_req.strip(),
                metadata={**base_meta, 'secao': 'pre_requisitos', 'pre_requisitos': pre_req_str}
            ))
        
        doc_carga = f"""DISCIPLINA: {nome} (Código: {codigo})
CARGA HORÁRIA:
- Carga horária total: {carga_horaria.get('total', 'N/A')}
- Carga horária teórica: {carga_horaria.get('teorica', 'N/A')}
- Carga horária prática: {carga_horaria.get('pratica', 'N/A')}
- Carga horária de extensão: {carga_horaria.get('extensao', 'N/A')}

A disciplina {nome} tem {carga_horaria.get('total', 'N/A')} de carga horária total."""
        
        docs.append(Document(
            page_content=doc_carga.strip(),
            metadata={**base_meta, 'secao': 'carga_horaria', **carga_horaria}
        ))
        
        ementa_match = re.search(r'## Ementa\n\n(.*?)(?=\n## |$)', content, re.DOTALL)
        if ementa_match:
            ementa_raw = ementa_match.group(1).strip()
            ementa_texto = ementa_raw.split('###')[0].strip()
            
            topicos = []
            topicos_match = re.search(r'### Tópicos\n\n(.*?)(?=\n## |$)', content, re.DOTALL)
            if topicos_match:
                topicos = [t.replace('- ', '').strip() for t in topicos_match.group(1).split('\n') if t.strip()]
            
            doc_ementa = f"""DISCIPLINA: {nome} (Código: {codigo})
EMENTA / CONTEÚDO PROGRAMÁTICO:
{ementa_texto}

TÓPICOS ABORDADOS:
{chr(10).join(f'- {t}' for t in topicos) if topicos else 'Não especificados'}

O que é estudado em {nome}: {ementa_texto}"""
            
            docs.append(Document(
                page_content=doc_ementa.strip(),
                metadata={**base_meta, 'secao': 'ementa', 'topicos': ', '.join(topicos)}
            ))
        
        biblio_match = re.search(r'## Bibliografia\n\n(.*?)(?=\n## |$)', content, re.DOTALL)
        if biblio_match:
            biblio_text = biblio_match.group(1)
            
            for tipo in ['Basica', 'Complementar']:
                tipo_match = re.search(rf'### {tipo}\n\n(.*?)(?=\n### |$)', biblio_text, re.DOTALL)
                if tipo_match:
                    livros_text = tipo_match.group(1).strip()
                    livros = [l.strip() for l in livros_text.split('\n') if l.strip() and l.strip().startswith(('1.', '2.', '3.', '4.', '5.', '-'))]
                    
                    doc_bib = f"""DISCIPLINA: {nome} (Código: {codigo})
BIBLIOGRAFIA {tipo.upper()}:
{chr(10).join(livros) if livros else livros_text}

Livros recomendados ({tipo.lower()}) para {nome}."""
                    
                    docs.append(Document(
                        page_content=doc_bib.strip(),
                        metadata={**base_meta, 'secao': f'bibliografia_{tipo.lower()}'}
                    ))
        
        return docs
    
    @staticmethod
    def _extract_all_metadata(content: str) -> Dict[str, str]:
        """Extrai todos os metadados do cabeçalho do markdown."""
        meta = {}
        
        nome_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        meta['nome'] = nome_match.group(1).strip() if nome_match else 'N/A'
        
        campos = ['Código', 'Campus', 'Curso', 'Tipo', 'Termo', 'Turno', 'Formato', 'Oferta', 'Sigla']
        for campo in campos:
            patterns = [
                rf'\*\*{campo}(?:\(s\))?:\*\*\s*(.+)',
                rf'{campo}(?:\(s\))?:\s*(.+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    key = campo.lower().replace('(s)', '').replace('ó', 'o')
                    value = match.group(1).strip()
                    value = re.sub(r'\s*\*\*.*$', '', value).strip()
                    meta[key] = value
                    break
        
        return meta
    
    @staticmethod
    def _extract_docentes(content: str) -> List[str]:
        """Extrai lista de docentes."""
        docentes_match = re.search(r'## Docentes\n\n(.*?)(?=\n## |$)', content, re.DOTALL)
        if docentes_match:
            docentes_text = docentes_match.group(1).strip()
            return [d.replace('- ', '').strip() for d in docentes_text.split('\n') if d.strip() and d.strip().startswith('-')]
        return []
    
    @staticmethod
    def _extract_pre_requisitos(content: str) -> List[str]:
        """Extrai lista de pré-requisitos."""
        pre_req_match = re.search(r'## Pré-requisitos\n\n(.*?)(?=\n## |$)', content, re.DOTALL)
        if pre_req_match:
            pre_req_text = pre_req_match.group(1).strip()
            return [p.replace('- ', '').strip() for p in pre_req_text.split('\n') if p.strip() and p.strip().startswith('-')]
        return []
    
    @staticmethod
    def _extract_carga_horaria(content: str) -> Dict[str, str]:
        """Extrai informações de carga horária."""
        carga = {'total': 'N/A', 'teorica': 'N/A', 'pratica': 'N/A', 'extensao': 'N/A'}
        
        carga_match = re.search(r'## Carga Horária\n\n(.*?)(?=\n## |$)', content, re.DOTALL)
        if carga_match:
            carga_text = carga_match.group(1)
            
            for campo, key in [('Total', 'total'), ('Teórica', 'teorica'), ('Prática', 'pratica'), ('Extensão', 'extensao')]:
                match = re.search(rf'-\s*\*\*{campo}:\*\*\s*(.+)', carga_text)
                if match:
                    carga[key] = match.group(1).strip()
        
        return carga

class RegimentoMarkdownParser:
    """Parser otimizado para arquivos Markdown de regimentos institucionais."""
    
    @staticmethod
    def parse(filepath: str) -> List[Document]:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        docs = []
        
        doc_tipo_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        doc_tipo = doc_tipo_match.group(1) if doc_tipo_match else 'Documento Institucional'
        
        resolucao_match = re.search(r'\*\*Resolucao:\*\* (.+)', content)
        resolucao = resolucao_match.group(1).strip() if resolucao_match else 'N/A'
        
        base_meta = {
            'tipo_documento': 'institucional',
            'documento': doc_tipo,
            'resolucao': resolucao,
            'source': filepath
        }
        
        info_parts = [f"DOCUMENTO INSTITUCIONAL UNIFESP: {doc_tipo}"]
        for campo in ['resolucao', 'instituicao', 'campus', 'data_vigencia', 'data_aprovacao', 'status']:
            match = re.search(rf'\*\*{campo.replace("_", " ").title()}:\*\* (.+)', content, re.IGNORECASE)
            if match:
                info_parts.append(f"{campo.replace('_', ' ').title()}: {match.group(1).strip()}")
        
        docs.append(Document(page_content="\n".join(info_parts), metadata={**base_meta, 'secao': 'info_geral'}))
        
        objetivo_match = re.search(r'## Objetivo\n\n(.*?)(?=\n## |$)', content, re.DOTALL)
        if objetivo_match:
            obj_text = f"DOCUMENTO: {doc_tipo}\nOBJETIVO: {objetivo_match.group(1).strip()}"
            docs.append(Document(page_content=obj_text, metadata={**base_meta, 'secao': 'objetivo'}))
        
        estrutura_match = re.search(r'## Estrutura\n\n(.*?)(?=\n## |$)', content, re.DOTALL)
        if estrutura_match:
            estrutura_text = estrutura_match.group(1)
            
            artigos = re.finditer(r'\*\*Art\. (\d+)\.\*\* (.+?)(?=\n\*\*Art\. |\n## |$)', estrutura_text, re.DOTALL)
            for artigo_match in artigos:
                numero = artigo_match.group(1)
                conteudo = artigo_match.group(2).strip()
                    
                pos = artigo_match.start()
                titulo = "Geral"
                for titulo_match in re.finditer(r'### (.+?)\n', estrutura_text[:pos]):
                    titulo = titulo_match.group(1).strip()
                    
                texto = f"DOCUMENTO: {doc_tipo}\nSEÇÃO: {titulo}\n\nArt. {numero}. {conteudo}"
                        
                meta = {**base_meta, 'secao': 'artigo', 'titulo': titulo, 'artigo': numero}
                docs.append(Document(page_content=texto, metadata=meta))
                
        faqs_match = re.search(r'## Perguntas Frequentes\n\n(.*?)(?=\n## |$)', content, re.DOTALL)
        if faqs_match:
            faqs_text = faqs_match.group(1)
            
            faq_blocks = re.split(r'(?=\*\*(?:Artigo|Pergunta):\*\*)', faqs_text)
            
            current_artigo = ''
            for block in faq_blocks:
                block = block.strip()
                if not block:
                    continue
                
                artigo_match = re.search(r'\*\*Artigo:\*\*\s*(\d+)', block)
                if artigo_match:
                    current_artigo = artigo_match.group(1)
                
                pergunta_match = re.search(r'\*\*Pergunta:\*\*\s*(.+?)(?:\s*\n|\s{2,})', block)
                resposta_match = re.search(r'\*\*Resposta:\*\*\s*(.+?)(?:\s*$|\n\n)', block, re.DOTALL)
                
                if pergunta_match and resposta_match:
                    pergunta = pergunta_match.group(1).strip()
                    resposta = resposta_match.group(1).strip()
                    
                    faq_txt = f"DOCUMENTO: {doc_tipo}\n"
                    if current_artigo:
                        faq_txt += f"Artigo: {current_artigo}\n"
                    faq_txt += f"PERGUNTA: {pergunta}\nRESPOSTA: {resposta}"
                    
                    docs.append(Document(
                        page_content=faq_txt, 
                        metadata={**base_meta, 'secao': 'faq', 'artigo': current_artigo, 'pergunta': pergunta[:50]}
                    ))
        
        resumo = f"""DOCUMENTO INSTITUCIONAL UNIFESP: {doc_tipo}
Resolução: {resolucao}

Este documento contém informações sobre:
- Estrutura organizacional do Campus São José dos Campos
- Regras e regulamentos da UNIFESP
- Cursos de graduação e pós-graduação
- Atividades complementares e extensão

Para perguntas específicas, consulte os artigos e FAQs deste documento."""

        docs.append(Document(page_content=resumo, metadata={**base_meta, 'secao': 'resumo'}))

        especiais = {"Objetivo", "Estrutura", "Perguntas Frequentes"}
        secoes_gen = re.finditer(
            r'^## (.+?)\n(.*?)(?=\n## |\Z)', content, re.DOTALL | re.MULTILINE
        )
        capturou_generica = False
        for sm in secoes_gen:
            titulo_sec = sm.group(1).strip()
            if titulo_sec in especiais:
                continue
            corpo_sec = sm.group(2).strip()
            if len(corpo_sec) < 80:
                continue
            capturou_generica = True
            for pedaco in _chunk_texto(corpo_sec):
                docs.append(Document(
                    page_content=(
                        f"DOCUMENTO: {doc_tipo}\nSEÇÃO: {titulo_sec}\n\n{pedaco}"
                    ),
                    metadata={**base_meta, 'secao': 'conteudo', 'titulo': titulo_sec},
                ))

        if not capturou_generica and len(docs) <= 2:
            corpo_total = re.sub(r'^# .+$', '', content, count=1, flags=re.MULTILINE).strip()
            for pedaco in _chunk_texto(corpo_total):
                docs.append(Document(
                    page_content=f"DOCUMENTO: {doc_tipo}\n\n{pedaco}",
                    metadata={**base_meta, 'secao': 'conteudo'},
                ))

        return docs


class MatrizCurricularParser:
    """Parser para arquivos de matriz curricular."""
    
    @staticmethod
    def parse(filepath: str) -> List[Document]:
        """Parseia arquivo de matriz curricular em documentos."""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        docs = []
        
        titulo_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        titulo = titulo_match.group(1).strip() if titulo_match else Path(filepath).stem
        
        sigla_match = re.search(r'\(([A-Z]{2,5})\)', titulo)
        sigla = sigla_match.group(1) if sigla_match else ""
        
        carga_match = re.search(r'\*\*Carga Horária Total:\*\*\s*(\d+)', content)
        carga_total = carga_match.group(1) if carga_match else ""
        
        base_meta = {
            'source': filepath,
            'tipo': 'matriz_curricular',
            'titulo': titulo,
            'sigla': sigla,
            'carga_horaria_total': carga_total
        }
        
        termo_pattern = r'### (?:Termo\s+)?(\d+)[º°]?\s*(?:Semestre|Termo)?'
        termos_encontrados = re.findall(termo_pattern, content)
        num_termos = len(termos_encontrados)
        
        resumo = f"""# {titulo}

**Sigla:** {sigla}
**Carga Horária Total:** {carga_total} horas
**Duração:** {num_termos} termos (semestres)

O curso de {titulo} possui **{num_termos} termos** (semestres), totalizando **{carga_total} horas**.

Estrutura do curso:
- Termos 1-2: Núcleo básico com disciplinas fundamentais
- Termos 3-6: Formação específica na área
- Termos 7-8: TCC e disciplinas eletivas

A matriz curricular contém:
- Disciplinas fixas organizadas por termo/semestre (8 termos)
- Eletivas do Grupo 1 (Eletivas Limitadas da área)
- Eletivas do Grupo 2 (Matemática e Computação)
- Eletivas do Grupo 3 (Ciências Humanas, Econômicas e Sociais)
- Eletivas Extensionistas
- Trabalho de Conclusão de Curso (TCC I e TCC II)
- Atividades Complementares (144 horas)"""
        
        docs.append(Document(page_content=resumo, metadata={**base_meta, 'secao': 'resumo', 'num_termos': num_termos}))
        
        termo_pattern = r'###\s+(?:Termo\s+)?(\d+)[º°]?\s*(?:Semestre|Termo)?[^\n]*\n(.*?)(?=\n###\s+|\n---|\n## |\Z)'
        termos = re.findall(termo_pattern, content, re.DOTALL)
        
        for termo_num, termo_content in termos:
            termo_doc = f"**Termo {termo_num} - {titulo}**\n\n"
            disc_pattern = r'\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|'
            disciplinas = re.findall(disc_pattern, termo_content)
            
            for disc_nome, creditos in disciplinas:
                disc_nome = disc_nome.strip()
                if disc_nome and disc_nome != "Disciplina" and not disc_nome.startswith('-'):
                    termo_doc += f"- {disc_nome} ({creditos} créditos)\n"
            
            if termo_doc.count('-') > 0:
                docs.append(Document(
                    page_content=termo_doc,
                    metadata={**base_meta, 'secao': f'termo_{termo_num}', 'termo': termo_num}
                ))
        
        eletiva_sections = [
            ('Eletivas do Grupo 1', 'eletivas_grupo1'),
            ('Eletivas do Grupo 2', 'eletivas_grupo2'),
            ('Eletivas do Grupo 3', 'eletivas_grupo3'),
            ('Eletivas Extensionistas', 'eletivas_extensionistas'),
        ]
        
        for section_name, section_key in eletiva_sections:
            match = re.search(rf'## {section_name}.*?\n(.*?)(?=\n## |$)', content, re.DOTALL)
            if match:
                section_content = match.group(1).strip()
                docs.append(Document(
                    page_content=f"**{section_name} - {titulo}**\n\n{section_content}",
                    metadata={**base_meta, 'secao': section_key}
                ))
        
        return docs


def parse_file(filepath: str) -> List[Document]:
    """Função principal para parsear arquivos Markdown."""
    with open(filepath, 'r', encoding='utf-8') as f:
        first_lines = ''.join(f.readlines()[:10])
    
    if 'regimentos' in filepath.lower() or 'regimento' in filepath.lower():
        return RegimentoMarkdownParser.parse(filepath)
    
    if 'Matriz Curricular' in first_lines or 'markdown_cursos' in filepath:
        return MatrizCurricularParser.parse(filepath)
    
    if 'Código:' in first_lines or 'Docentes' in first_lines or 'disciplinas' in filepath:
        return DisciplinaMarkdownParser.parse(filepath)
    
    if filepath.endswith('.md'):
        return RegimentoMarkdownParser.parse(filepath)
    
    return []
