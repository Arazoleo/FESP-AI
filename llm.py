from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
from pathlib import Path
from typing import List, Dict, Optional
import hashlib
import json
import os


class RAGUnifesp:
    def __init__(self, 
                 model_name: str = "qwen2.5:14b", 
                 embedding_model: str = "nomic-embed-text",
                 persist_directory: str = "./chroma_db_unifesp"):
        
        self.llm = OllamaLLM(model=model_name)
        self.embeddings = OllamaEmbeddings(model=embedding_model)
        self.persist_directory = persist_directory
        self.index_file = os.path.join(persist_directory, "index.json")
        self.db = None
        self.retriever = None
        self.chain = None
        
        self.sources = {
            "disciplinas": "./jsons_disciplinas",
            "regimentos": "./jsons_regimentos"
        }
    
    def _get_file_hash(self, filepath: str) -> str:
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _load_index(self) -> Dict:
        if os.path.exists(self.index_file):
            with open(self.index_file, 'r') as f:
                return json.load(f)
        return {"files": {}}
    
    def _save_index(self, index: Dict):
        os.makedirs(self.persist_directory, exist_ok=True)
        with open(self.index_file, 'w') as f:
            json.dump(index, f, indent=2)
    
    def _detect_changes(self) -> Dict[str, List[str]]:
        index = self._load_index()
        changes = {"new": [], "modified": [], "deleted": []}
        current_files = {}
        
        for source_type, directory in self.sources.items():
            if not os.path.exists(directory):
                continue
            for json_file in Path(directory).glob("*.json"):
                filepath = str(json_file)
                file_hash = self._get_file_hash(filepath)
                current_files[filepath] = file_hash
                
                if filepath not in index["files"]:
                    changes["new"].append(filepath)
                elif index["files"][filepath] != file_hash:
                    changes["modified"].append(filepath)
        
        for filepath in index["files"]:
            if filepath not in current_files:
                changes["deleted"].append(filepath)
        
        return changes, current_files
    
    def _parse_disciplina(self, filepath: str) -> List[Document]:
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
    
    def _parse_regimento(self, filepath: str) -> List[Document]:
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
        if doc_info.get('resolucao'):
            info_parts.append(f"Resolucao: {doc_info['resolucao']}")
        if doc_info.get('instituicao'):
            info_parts.append(f"Instituicao: {doc_info['instituicao']}")
        if doc_info.get('campus'):
            info_parts.append(f"Campus: {doc_info['campus']}")
        if doc_info.get('data_vigencia'):
            info_parts.append(f"Data Vigencia: {doc_info['data_vigencia']}")
        if doc_info.get('data_aprovacao'):
            info_parts.append(f"Data Aprovacao: {doc_info['data_aprovacao']}")
        if doc_info.get('status'):
            info_parts.append(f"Status: {doc_info['status']}")
        
        docs.append(Document(page_content="\n".join(info_parts), metadata={**base_meta, 'secao': 'info_geral'}))
        
        if 'objetivo' in data:
            obj = data['objetivo']
            obj_txt = "Objetivo do documento:\n"
            if isinstance(obj, dict):
                for k, v in obj.items():
                    obj_txt += f"- {k.replace('_', ' ').title()}: {v}\n"
            docs.append(Document(page_content=obj_txt.strip(), metadata={**base_meta, 'secao': 'objetivo'}))
        
        if 'ponto_encontro' in data:
            pe = data['ponto_encontro']
            pe_txt = f"Ponto de Encontro em caso de emergencia:\nLocal: {pe.get('localizacao', 'N/A')}\nInstrucoes: {pe.get('instrucoes', 'N/A')}"
            docs.append(Document(page_content=pe_txt, metadata={**base_meta, 'secao': 'ponto_encontro'}))
        
        if 'recursos_materiais' in data:
            rm = data['recursos_materiais']
            rm_txt = "Recursos Materiais de Seguranca:\n"
            if 'extintores' in rm:
                ext = rm['extintores']
                rm_txt += f"Extintores: {ext.get('total', 'N/A')} unidades\n"
            if 'hidrantes' in rm:
                rm_txt += f"Hidrantes: {rm['hidrantes']} unidades\n"
            if 'saidas_emergencia' in rm:
                rm_txt += "Saidas de Emergencia:\n" + "\n".join(f"  - {s}" for s in rm['saidas_emergencia'])
            docs.append(Document(page_content=rm_txt.strip(), metadata={**base_meta, 'secao': 'recursos_materiais'}))
        
        if 'riscos_especificos' in data:
            riscos = data['riscos_especificos']
            riscos_txt = "Riscos Especificos:\n"
            for r in riscos:
                riscos_txt += f"\n- {r.get('tipo', 'N/A')} ({r.get('localizacao', 'N/A')}): {', '.join(r.get('riscos', []))}"
            docs.append(Document(page_content=riscos_txt.strip(), metadata={**base_meta, 'secao': 'riscos'}))
        
        if 'procedimentos_emergencia' in data:
            proc = data['procedimentos_emergencia']
            for proc_key, proc_data in proc.items():
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
        
        if 'notas_importantes' in data:
            notas = data['notas_importantes']
            notas_txt = "Notas Importantes de Seguranca:\n" + "\n".join(f"- {n}" for n in notas)
            docs.append(Document(page_content=notas_txt, metadata={**base_meta, 'secao': 'notas_importantes'}))
        
        if 'contatos_emergencia' in data:
            cont = data['contatos_emergencia']
            cont_txt = "Contatos de Emergencia:\n"
            for k, v in cont.items():
                cont_txt += f"- {k.replace('_', ' ').title()}: {v}\n"
            docs.append(Document(page_content=cont_txt.strip(), metadata={**base_meta, 'secao': 'contatos_emergencia'}))
        
        glossario = data.get('glossario', {})
        siglas = glossario.get('siglas', {})
        if siglas:
            siglas_txt = "Glossario de Siglas Unifesp ICT:\n" + "\n".join(f"- {s}: {v}" for s, v in siglas.items())
            docs.append(Document(page_content=siglas_txt, metadata={**base_meta, 'secao': 'glossario'}))
        
        estrutura = data.get('estrutura', {})
        for secao_key, secao_data in estrutura.items():
            if not isinstance(secao_data, dict):
                continue
            
            secao_titulo = secao_data.get('titulo', secao_data.get('nome', secao_key))
            
            for artigo in secao_data.get('artigos', []):
                doc = self._format_artigo(artigo, secao_titulo, base_meta)
                if doc:
                    docs.append(doc)
            
            for capitulo in secao_data.get('capitulos', []):
                cap_nome = capitulo.get('nome', '')
                for artigo in capitulo.get('artigos', []):
                    doc = self._format_artigo(artigo, secao_titulo, base_meta, cap_nome)
                    if doc:
                        docs.append(doc)
            
            secao_doc = self._format_secao(secao_key, secao_data, base_meta)
            if secao_doc:
                docs.append(secao_doc)
        
        for faq in data.get('perguntas_frequentes', []):
            faq_txt = f"Pergunta: {faq.get('pergunta', '')}\nResposta: {faq.get('resposta', '')}\nArtigo: {faq.get('artigo', 'N/A')}"
            docs.append(Document(page_content=faq_txt, metadata={**base_meta, 'secao': 'faq'}))
        
        return docs
    
    def _format_artigo(self, artigo: Dict, titulo: str, base_meta: Dict, capitulo: str = None) -> Optional[Document]:
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
    
    def _format_secao(self, secao_key: str, secao_data: Dict, base_meta: Dict) -> Optional[Document]:
        titulo = secao_data.get('titulo', secao_data.get('nome', secao_key))
        partes = [f"SECAO: {titulo}"]
        
        campos_texto = ['missao', 'visao', 'contexto', 'justificativa', 'problema_identificado', 
                        'conclusao_diagnostico', 'relevancia_regional']
        for campo in campos_texto:
            if campo in secao_data and isinstance(secao_data[campo], str):
                partes.append(f"{campo.replace('_', ' ').title()}: {secao_data[campo]}")
        
        if 'tres_pilares_identidade' in secao_data:
            partes.append("Tres Pilares da Identidade:")
            for i, pilar in enumerate(secao_data['tres_pilares_identidade'], 1):
                partes.append(f"  {i}. {pilar}")
        
        for sub_key, sub_data in secao_data.items():
            if sub_key.startswith('subsecao_') and isinstance(sub_data, dict):
                sub_titulo = sub_data.get('titulo', sub_key)
                partes.append(f"\n{sub_titulo}:")
                self._extract_nested_content(sub_data, partes, indent=1)
        
        if 'perfil_geral' in secao_data:
            perfil = secao_data['perfil_geral']
            if 'formacao' in perfil:
                partes.append(f"Formacao: {perfil['formacao']}")
            if 'capacidades' in perfil:
                partes.append("Capacidades:")
                for cap in perfil['capacidades']:
                    partes.append(f"  - {cap}")
        
        if 'possibilidades_atuacao' in secao_data:
            partes.append("Possibilidades de Atuacao:")
            for pos in secao_data['possibilidades_atuacao']:
                partes.append(f"  - {pos}")
        
        if 'proposta_horizonte_2020' in secao_data:
            metas = secao_data['proposta_horizonte_2020'].get('numeros_meta_2020', {})
            if metas:
                partes.append("Metas 2020:")
                for k, v in metas.items():
                    partes.append(f"  - {k.replace('_', ' ').title()}: {v}")
        
        if 'cronograma_cursos' in secao_data:
            crono = secao_data['cronograma_cursos']
            for tipo in ['existentes', 'aprovados_2011', 'planejados']:
                if tipo in crono:
                    partes.append(f"Cursos {tipo.replace('_', ' ').title()}:")
                    for item in crono[tipo]:
                        if 'curso' in item:
                            partes.append(f"  - {item.get('ano', '')}: {item['curso']} ({item.get('vagas', '')} vagas)")
                        elif 'cursos' in item:
                            partes.append(f"  - {item.get('ano', item.get('anos', ''))}: {', '.join(item['cursos'])}")
        
        if len(partes) <= 1:
            return None
        
        meta = {**base_meta, 'secao': titulo}
        return Document(page_content="\n".join(partes), metadata=meta)
    
    def _extract_nested_content(self, data: Dict, partes: List[str], indent: int = 0):
        prefix = "  " * indent
        
        campos_simples = ['duracao', 'diploma', 'autoria_texto_base', 'geracao', 'area_doada', 
                          'data_doacao', 'previsao_obras', 'metodologia', 'funcao', 'vinculacao']
        for campo in campos_simples:
            if campo in data and isinstance(data[campo], str):
                partes.append(f"{prefix}{campo.replace('_', ' ').title()}: {data[campo]}")
        
        if 'caracteristicas' in data and isinstance(data['caracteristicas'], dict):
            carac = data['caracteristicas']
            for k, v in carac.items():
                if isinstance(v, str):
                    partes.append(f"{prefix}{k.replace('_', ' ').title()}: {v}")
                elif isinstance(v, list):
                    partes.append(f"{prefix}{k.replace('_', ' ').title()}: {', '.join(str(x) for x in v)}")
        
        if 'trajetorias_pos_bct' in data:
            partes.append(f"{prefix}Trajetorias pos-BCT:")
            for traj in data['trajetorias_pos_bct']:
                partes.append(f"{prefix}  - {traj}")
        
        if 'objetivos' in data and isinstance(data['objetivos'], list):
            partes.append(f"{prefix}Objetivos:")
            for obj in data['objetivos']:
                partes.append(f"{prefix}  - {obj}")
        
        if 'cursos_implantados_inicialmente' in data:
            partes.append(f"{prefix}Cursos implantados:")
            for item in data['cursos_implantados_inicialmente']:
                ano = item.get('ano', '')
                cursos = item.get('cursos', [])
                partes.append(f"{prefix}  - {ano}: {', '.join(cursos)}")
        
        if 'aprovacao_consu_2009' in data:
            aprov = data['aprovacao_consu_2009']
            partes.append(f"{prefix}Aprovacao CONSU 2009:")
            if 'novos_cursos_aprovados' in aprov:
                for curso in aprov['novos_cursos_aprovados']:
                    partes.append(f"{prefix}  - {curso}")
    
    def _parse_file(self, filepath: str) -> List[Document]:
        if 'disciplinas' in filepath:
            return self._parse_disciplina(filepath)
        elif 'regimentos' in filepath:
            return self._parse_regimento(filepath)
        return []
    
    def sync(self, force: bool = False) -> bool:
        changes, current_files = self._detect_changes()
        
        has_changes = any(changes.values())
        db_exists = os.path.exists(self.persist_directory) and os.path.exists(
            os.path.join(self.persist_directory, "chroma.sqlite3")
        )
        
        if not has_changes and db_exists and not force:
            print("Banco atualizado, nenhuma mudanca detectada.")
            self._load_db()
            return False
        
        if force or not db_exists:
            print("Recriando banco vetorial...")
            all_docs = []
            for filepath in current_files:
                all_docs.extend(self._parse_file(filepath))
            
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            splits = splitter.split_documents(all_docs)
            
            self.db = Chroma.from_documents(splits, self.embeddings, persist_directory=self.persist_directory)
            self._save_index({"files": current_files})
            print(f"Banco criado: {len(splits)} chunks de {len(current_files)} arquivos.")
        else:
            self._load_db()
            
            if changes["deleted"]:
                print(f"Removendo {len(changes['deleted'])} arquivos deletados...")
                for filepath in changes["deleted"]:
                    ids_to_delete = []
                    results = self.db.get(where={"source": filepath})
                    if results and results['ids']:
                        ids_to_delete.extend(results['ids'])
                    if ids_to_delete:
                        self.db._collection.delete(ids=ids_to_delete)
            
            files_to_update = changes["new"] + changes["modified"]
            if files_to_update:
                print(f"Atualizando {len(files_to_update)} arquivos...")
                
                for filepath in changes["modified"]:
                    results = self.db.get(where={"source": filepath})
                    if results and results['ids']:
                        self.db._collection.delete(ids=results['ids'])
                
                new_docs = []
                for filepath in files_to_update:
                    new_docs.extend(self._parse_file(filepath))
                
                if new_docs:
                    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
                    splits = splitter.split_documents(new_docs)
                    self.db.add_documents(splits)
                    print(f"Adicionados {len(splits)} novos chunks.")
            
            self._save_index({"files": current_files})
        
        self.retriever = self.db.as_retriever(search_type="similarity", search_kwargs={"k": 6})
        self._setup_chain()
        return True
    
    def _load_db(self):
        self.db = Chroma(persist_directory=self.persist_directory, embedding_function=self.embeddings)
        self.retriever = self.db.as_retriever(search_type="similarity", search_kwargs={"k": 6})
        self._setup_chain()
    
    def _setup_chain(self):
        template = """Voce e um assistente da Unifesp ICT (Instituto de Ciencia e Tecnologia) em Sao Jose dos Campos.
Responda baseado APENAS no contexto abaixo:

{context}

Pergunta: {question}

Instrucoes:
- Use as informacoes do contexto
- Para disciplinas: cite nome, codigo, carga horaria
- Para regimentos: cite artigo e secao
- Se nao encontrar a informacao, diga claramente
- Seja objetivo e direto

Resposta:"""
        
        prompt = ChatPromptTemplate.from_template(template)
        
        def format_docs(docs):
            parts = []
            for doc in docs:
                tipo = doc.metadata.get('tipo_documento', 'documento')
                if tipo == 'disciplina':
                    header = f"[Disciplina: {doc.metadata.get('disciplina', 'N/A')} - {doc.metadata.get('secao', '')}]"
                else:
                    header = f"[Regimento {doc.metadata.get('resolucao', '')} - {doc.metadata.get('secao', '')}]"
                parts.append(f"{header}\n{doc.page_content}")
            return "\n\n---\n\n".join(parts)
        
        self.chain = (
            {"context": self.retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )
        
    def query(self, question: str) -> str:
        if not self.chain:
            self.sync()
        return self.chain.invoke(question)
    
    def list_sources(self) -> Dict[str, int]:
        if not self.db:
            self.sync()
        
        results = self.db.get()
        counts = {"disciplinas": 0, "regimentos": 0}
        seen = set()
        
        for meta in results.get('metadatas', []):
            source = meta.get('source', '')
            if source in seen:
                continue
            seen.add(source)
            if 'disciplinas' in source:
                counts["disciplinas"] += 1
            elif 'regimentos' in source:
                counts["regimentos"] += 1
        
        return counts


def main():
    rag = RAGUnifesp()
    rag.sync()
    
    print("\nSistema RAG Unifesp ICT")
    print("Comandos: 'sair', 'sync', 'status'\n")
    
    while True:
        try:
            pergunta = input("Pergunta: ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        
        if not pergunta:
            continue
        
        if pergunta.lower() in ['sair', 'exit', 'quit']:
            break
        
        if pergunta.lower() == 'sync':
            rag.sync(force=True)
            continue
        
        if pergunta.lower() == 'status':
            counts = rag.list_sources()
            print(f"Disciplinas: {counts['disciplinas']}, Regimentos: {counts['regimentos']}")
            continue
        
        resposta = rag.query(pergunta)
        print(f"\n{resposta}\n")


if __name__ == "__main__":
    main()
