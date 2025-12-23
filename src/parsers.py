import json
from typing import List, Dict, Optional
from langchain_core.documents import Document


class DisciplinaParser:
    
    @staticmethod
    def parse(filepath: str) -> List[Document]:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        docs = []
        d = data.get('disciplina', data)
        nome = d.get('nome', 'N/A')
        codigo = d.get('codigo', 'N/A')
        
        base_meta = {
            'tipo_documento': 'disciplina',
            'disciplina': nome,
            'codigo': codigo,
            'source': filepath
        }
        
        docentes = d.get('docentes', [])
        if isinstance(docentes, str):
            docentes = [docentes]
        
        info = f"""Disciplina: {nome}
Codigo: {codigo}
Campus: {d.get('campus', 'N/A')}
Curso(s): {', '.join(d.get('curso', []))}
Tipo: {d.get('tipo', 'N/A')}
Termo: {d.get('termo', 'N/A')}
Turno: {d.get('turno', 'N/A')}
Docentes: {', '.join(docentes) if docentes else 'N/A'}"""
        docs.append(Document(page_content=info, metadata={**base_meta, 'secao': 'info_geral'}))
        
        carga = d.get('carga_horaria', {})
        if carga:
            ch = f"""Disciplina: {nome}
Carga Horaria Total: {carga.get('total', 'N/A')}h
Teorica: {carga.get('teorica', 'N/A')}h
Pratica: {carga.get('pratica', 'N/A')}h
Extensao: {carga.get('extensao', 'N/A')}h"""
            docs.append(Document(page_content=ch, metadata={**base_meta, 'secao': 'carga_horaria'}))
        
        ementa = d.get('ementa', {})
        if ementa:
            topicos = ementa.get('topicos', [])
            em = f"Disciplina: {nome}\nEmenta: {ementa.get('descricao_completa', 'N/A')}"
            if topicos:
                em += "\nTopicos:\n" + "\n".join(f"- {t}" for t in topicos)
            docs.append(Document(page_content=em, metadata={**base_meta, 'secao': 'ementa'}))
        
        biblio = d.get('bibliografia', {})
        for tipo_bib in ['basica', 'complementar']:
            livros = biblio.get(tipo_bib, [])
            if livros:
                bib = f"Disciplina: {nome}\nBibliografia {tipo_bib.title()}:\n"
                for i, livro in enumerate(livros, 1):
                    autores = ', '.join(livro.get('autores', ['N/A']))
                    bib += f"{i}. {autores}. {livro.get('titulo', 'N/A')}. {livro.get('editora', '')}, {livro.get('ano', '')}.\n"
                docs.append(Document(page_content=bib.strip(), metadata={**base_meta, 'secao': f'bibliografia_{tipo_bib}'}))
        
        return docs


class RegimentoParser:
    
    @staticmethod
    def parse(filepath: str) -> List[Document]:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        docs = []
        doc_info = data.get('documento', {})
        tipo_doc = doc_info.get('tipo', 'Documento Institucional')
        
        base_meta = {
            'tipo_documento': 'institucional',
            'documento': tipo_doc,
            'resolucao': doc_info.get('resolucao', doc_info.get('data_aprovacao', 'N/A')),
            'source': filepath
        }
        
        info_parts = [f"Documento: {tipo_doc}"]
        for campo in ['resolucao', 'instituicao', 'campus', 'data_vigencia', 'data_aprovacao', 'status']:
            if doc_info.get(campo):
                info_parts.append(f"{campo.replace('_', ' ').title()}: {doc_info[campo]}")
        
        docs.append(Document(page_content="\n".join(info_parts), metadata={**base_meta, 'secao': 'info_geral'}))
        
        docs.extend(RegimentoParser._parse_objetivo(data, base_meta))
        docs.extend(RegimentoParser._parse_ponto_encontro(data, base_meta))
        docs.extend(RegimentoParser._parse_recursos(data, base_meta))
        docs.extend(RegimentoParser._parse_riscos(data, base_meta))
        docs.extend(RegimentoParser._parse_procedimentos(data, base_meta))
        docs.extend(RegimentoParser._parse_notas(data, base_meta))
        docs.extend(RegimentoParser._parse_contatos(data, base_meta))
        docs.extend(RegimentoParser._parse_glossario(data, base_meta))
        docs.extend(RegimentoParser._parse_estrutura(data, base_meta))
        docs.extend(RegimentoParser._parse_faqs(data, base_meta))
        
        return docs
    
    @staticmethod
    def _parse_objetivo(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        if 'objetivo' in data:
            obj = data['objetivo']
            obj_txt = "Objetivo do documento:\n"
            if isinstance(obj, dict):
                for k, v in obj.items():
                    obj_txt += f"- {k.replace('_', ' ').title()}: {v}\n"
            docs.append(Document(page_content=obj_txt.strip(), metadata={**base_meta, 'secao': 'objetivo'}))
        return docs
    
    @staticmethod
    def _parse_ponto_encontro(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        if 'ponto_encontro' in data:
            pe = data['ponto_encontro']
            pe_txt = f"Ponto de Encontro em caso de emergencia:\nLocal: {pe.get('localizacao', 'N/A')}\nInstrucoes: {pe.get('instrucoes', 'N/A')}"
            docs.append(Document(page_content=pe_txt, metadata={**base_meta, 'secao': 'ponto_encontro'}))
        return docs
    
    @staticmethod
    def _parse_recursos(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        if 'recursos_materiais' in data:
            rm = data['recursos_materiais']
            rm_txt = "Recursos Materiais de Seguranca:\n"
            if 'extintores' in rm:
                rm_txt += f"Extintores: {rm['extintores'].get('total', 'N/A')} unidades\n"
            if 'hidrantes' in rm:
                rm_txt += f"Hidrantes: {rm['hidrantes']} unidades\n"
            if 'saidas_emergencia' in rm:
                rm_txt += "Saidas de Emergencia:\n" + "\n".join(f"  - {s}" for s in rm['saidas_emergencia'])
            docs.append(Document(page_content=rm_txt.strip(), metadata={**base_meta, 'secao': 'recursos_materiais'}))
        return docs
    
    @staticmethod
    def _parse_riscos(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        if 'riscos_especificos' in data:
            riscos_txt = "Riscos Especificos:\n"
            for r in data['riscos_especificos']:
                riscos_txt += f"\n- {r.get('tipo', 'N/A')} ({r.get('localizacao', 'N/A')}): {', '.join(r.get('riscos', []))}"
            docs.append(Document(page_content=riscos_txt.strip(), metadata={**base_meta, 'secao': 'riscos'}))
        return docs
    
    @staticmethod
    def _parse_procedimentos(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        if 'procedimentos_emergencia' in data:
            for proc_key, proc_data in data['procedimentos_emergencia'].items():
                if isinstance(proc_data, dict):
                    proc_txt = f"Procedimento: {proc_key.replace('_', ' ').title()}\n"
                    for k, v in proc_data.items():
                        if isinstance(v, str):
                            proc_txt += f"- {k.replace('_', ' ').title()}: {v}\n"
                        elif isinstance(v, list):
                            proc_txt += f"- {k.replace('_', ' ').title()}:\n"
                            for item in v:
                                proc_txt += f"  * {item}\n"
                    docs.append(Document(page_content=proc_txt.strip(), metadata={**base_meta, 'secao': f'procedimento_{proc_key}'}))
        return docs
    
    @staticmethod
    def _parse_notas(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        if 'notas_importantes' in data:
            notas_txt = "Notas Importantes de Seguranca:\n" + "\n".join(f"- {n}" for n in data['notas_importantes'])
            docs.append(Document(page_content=notas_txt, metadata={**base_meta, 'secao': 'notas_importantes'}))
        return docs
    
    @staticmethod
    def _parse_contatos(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        if 'contatos_emergencia' in data:
            cont_txt = "Contatos de Emergencia:\n"
            for k, v in data['contatos_emergencia'].items():
                cont_txt += f"- {k.replace('_', ' ').title()}: {v}\n"
            docs.append(Document(page_content=cont_txt.strip(), metadata={**base_meta, 'secao': 'contatos_emergencia'}))
        return docs
    
    @staticmethod
    def _parse_glossario(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        glossario = data.get('glossario', {})
        siglas = glossario.get('siglas', {})
        if siglas:
            siglas_txt = "Glossario de Siglas Unifesp ICT:\n" + "\n".join(f"- {s}: {v}" for s, v in siglas.items())
            docs.append(Document(page_content=siglas_txt, metadata={**base_meta, 'secao': 'glossario'}))
        return docs
    
    @staticmethod
    def _parse_estrutura(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        estrutura = data.get('estrutura', {})
        for secao_key, secao_data in estrutura.items():
            if not isinstance(secao_data, dict):
                continue
            
            secao_titulo = secao_data.get('titulo', secao_data.get('nome', secao_key))
            
            for artigo in secao_data.get('artigos', []):
                doc = RegimentoParser._format_artigo(artigo, secao_titulo, base_meta)
                if doc:
                    docs.append(doc)
            
            for capitulo in secao_data.get('capitulos', []):
                cap_nome = capitulo.get('nome', '')
                for artigo in capitulo.get('artigos', []):
                    doc = RegimentoParser._format_artigo(artigo, secao_titulo, base_meta, cap_nome)
                    if doc:
                        docs.append(doc)
            
            secao_doc = RegimentoParser._format_secao(secao_key, secao_data, base_meta)
            if secao_doc:
                docs.append(secao_doc)
        
        return docs
    
    @staticmethod
    def _parse_faqs(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        for faq in data.get('perguntas_frequentes', []):
            artigo = faq.get('artigo', '')
            artigo_txt = f"Artigo: {artigo}\n" if artigo else ""
            faq_txt = f"{artigo_txt}Pergunta: {faq.get('pergunta', '')}\nResposta: {faq.get('resposta', '')}\nSecao: {faq.get('secao', 'N/A')}"
            docs.append(Document(page_content=faq_txt, metadata={**base_meta, 'secao': 'faq', 'artigo': artigo}))
        return docs
    
    @staticmethod
    def _format_artigo(artigo: Dict, titulo: str, base_meta: Dict, capitulo: str = None) -> Optional[Document]:
        conteudo = artigo.get('conteudo', '')
        if not conteudo:
            return None
        
        numero = artigo.get('numero', 'N/A')
        texto = f"TITULO: {titulo}"
        if capitulo:
            texto += f"\nCAPITULO: {capitulo}"
        texto += f"\n\nArt. {numero}. {conteudo}"
        
        if artigo.get('paragrafo_unico'):
            texto += f"\n\nParagrafo unico. {artigo['paragrafo_unico']}"
        
        for p in artigo.get('paragrafos', []):
            if isinstance(p, dict):
                texto += f"\n\nParagrafo {p.get('numero', '')}. {p.get('conteudo', '')}"
                for key in ['divisoes', 'cursos', 'programas']:
                    items = p.get(key, [])
                    if items:
                        for item in items:
                            if isinstance(item, dict):
                                texto += f"\n  - {item.get('nome', '')}: {', '.join(item.get('modalidades', []))}"
                            else:
                                texto += f"\n  - {item}"
        
        meta = {**base_meta, 'secao': 'artigo', 'titulo': titulo, 'artigo': numero}
        if capitulo:
            meta['capitulo'] = capitulo
        
        return Document(page_content=texto, metadata=meta)
    
    @staticmethod
    def _format_secao(secao_key: str, secao_data: Dict, base_meta: Dict) -> Optional[Document]:
        titulo = secao_data.get('titulo', secao_data.get('nome', secao_key))
        partes = [f"SECAO: {titulo}"]
        
        campos_texto = ['missao', 'visao', 'contexto', 'conclusao_diagnostico']
        for campo in campos_texto:
            if campo in secao_data and isinstance(secao_data[campo], str):
                partes.append(f"{campo.replace('_', ' ').title()}: {secao_data[campo]}")
        
        if 'tres_pilares_identidade' in secao_data:
            partes.append("Tres Pilares da Identidade:")
            for i, pilar in enumerate(secao_data['tres_pilares_identidade'], 1):
                partes.append(f"  {i}. {pilar}")
        
        if 'proposta_horizonte_2020' in secao_data:
            metas = secao_data['proposta_horizonte_2020'].get('numeros_meta_2020', {})
            if metas:
                partes.append("Metas 2020:")
                for k, v in metas.items():
                    partes.append(f"  - {k.replace('_', ' ').title()}: {v}")
        
        if len(partes) <= 1:
            return None
        
        return Document(page_content="\n".join(partes), metadata={**base_meta, 'secao': titulo})


def parse_file(filepath: str) -> List[Document]:
    if 'disciplinas' in filepath:
        return DisciplinaParser.parse(filepath)
    elif 'regimentos' in filepath:
        return RegimentoParser.parse(filepath)
    return []

