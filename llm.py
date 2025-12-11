from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document
import os
import json
import shutil
from pathlib import Path
from typing import List

class RAGUnifespJSON:
    def __init__(self, 
                 model_name="qwen2.5:14b", 
                 embedding_model="nomic-embed-text",
                 persist_directory="./chroma_db_unifesp_json"):
        """
        Inicializa o sistema RAG para disciplinas da Unifesp ICT usando JSONs estruturados
        
        Args:
            model_name: Nome do modelo Ollama para LLM
            embedding_model: Nome do modelo Ollama para embeddings
            persist_directory: Diretório para persistir o banco vetorial
        """
        self.llm = OllamaLLM(model=model_name)
        self.embeddings = OllamaEmbeddings(model=embedding_model)
        self.persist_directory = persist_directory
        self.db = None
        self.retriever = None
    
    def reiniciar_banco_vetorial(self, confirmar=True):
        """
        Remove o banco vetorial existente para recriá-lo do zero
        ÚTIL quando você alterou a estrutura dos JSONs ou adicionou novos campos
        
        Args:
            confirmar: Se True, pede confirmação antes de deletar
        
        Returns:
            bool: True se deletado, False se cancelado
        """
        if not os.path.exists(self.persist_directory):
            print(f"ℹ️  Banco vetorial não existe em: {self.persist_directory}")
            print(f"   Você pode criar um novo normalmente.")
            return False
        
        print("\n" + "="*80)
        print("⚠️  REINICIAR BANCO VETORIAL")
        print("="*80)
        print(f"\n📂 Localização: {self.persist_directory}")
        
        # Calcular tamanho
        total_size = sum(
            os.path.getsize(os.path.join(dirpath, filename))
            for dirpath, _, filenames in os.walk(self.persist_directory)
            for filename in filenames
        )
        size_mb = total_size / (1024**2)
        print(f"💾 Tamanho: {size_mb:.2f} MB")
        
        if confirmar:
            print(f"\n⚠️  ATENÇÃO: Esta ação vai DELETAR permanentemente o banco vetorial!")
            print(f"   Motivos comuns:")
            print(f"   • Você adicionou novos campos nos JSONs")
            print(f"   • Você alterou a estrutura dos dados")
            print(f"   • Você quer reprocessar tudo do zero")
            resposta = input(f"\n   Confirma a exclusão? (sim/não): ").strip().lower()
            
            if resposta not in ['sim', 's', 'yes', 'y']:
                print("\n🚫 Operação cancelada. Banco vetorial mantido.")
                return False
        
        try:
            shutil.rmtree(self.persist_directory)
            print(f"\n✅ Banco vetorial deletado com sucesso!")
            print(f"\n💡 Próximo passo: Execute o método para recriar:")
            print(f"   documentos = rag.carregar_jsons_diretorio('./seu_diretorio')")
            print(f"   splits = rag.processar_documentos(documentos)")
            print(f"   rag.criar_banco_vetorial(splits)")
            return True
        except Exception as e:
            print(f"\n❌ Erro ao deletar banco vetorial: {e}")
            return False
    
    def recriar_banco_completo(self, diretorio_jsons, confirmar=True):
        """
        Deleta o banco antigo e recria automaticamente do zero
        PERFEITO para quando você alterou os JSONs e precisa reindexar tudo
        
        Args:
            diretorio_jsons: Caminho do diretório com os arquivos JSON
            confirmar: Se True, pede confirmação antes de deletar o banco antigo
        
        Returns:
            bool: True se bem-sucedido, False se houve erro
        """
        print("\n" + "="*80)
        print("🔄 RECRIAR BANCO VETORIAL COMPLETO")
        print("="*80 + "\n")
        
        # Verificar se diretório de JSONs existe
        if not os.path.exists(diretorio_jsons):
            print(f"❌ ERRO: Diretório não encontrado: {diretorio_jsons}")
            return False
        
        arquivos = list(Path(diretorio_jsons).glob("*.json"))
        if not arquivos:
            print(f"❌ ERRO: Nenhum arquivo JSON encontrado em: {diretorio_jsons}")
            return False
        
        print(f"📁 Diretório de JSONs: {diretorio_jsons}")
        print(f"📄 Arquivos JSON encontrados: {len(arquivos)}")
        
        # Passo 1: Deletar banco antigo
        if os.path.exists(self.persist_directory):
            print(f"\n🗑️  PASSO 1: Deletando banco vetorial antigo...")
            if not self.reiniciar_banco_vetorial(confirmar=confirmar):
                return False
        else:
            print(f"\nℹ️  PASSO 1: Nenhum banco antigo encontrado (OK)")
        
        # Passo 2: Carregar JSONs
        print(f"\n📚 PASSO 2: Carregando arquivos JSON...")
        try:
            documentos = self.carregar_jsons_diretorio(diretorio_jsons)
            if not documentos:
                print(f"❌ ERRO: Nenhum documento foi carregado!")
                return False
        except Exception as e:
            print(f"❌ ERRO ao carregar JSONs: {e}")
            return False
        
        # Passo 3: Processar documentos
        print(f"\n✂️  PASSO 3: Processando documentos em chunks...")
        try:
            splits = self.processar_documentos(documentos, chunk_size=1000, chunk_overlap=200)
        except Exception as e:
            print(f"❌ ERRO ao processar documentos: {e}")
            return False
        
        # Passo 4: Criar banco vetorial
        print(f"\n🔧 PASSO 4: Criando novo banco vetorial...")
        try:
            self.criar_banco_vetorial(splits, persistir=True)
        except Exception as e:
            print(f"❌ ERRO ao criar banco vetorial: {e}")
            return False
        
        # Sucesso!
        print(f"\n" + "="*80)
        print(f"✅ BANCO VETORIAL RECRIADO COM SUCESSO!")
        print(f"="*80)
        print(f"\n📊 Resumo:")
        print(f"   • Arquivos JSON: {len(arquivos)}")
        print(f"   • Documentos originais: {len(documentos)}")
        print(f"   • Chunks indexados: {len(splits)}")
        print(f"   • Localização: {self.persist_directory}")
        print(f"\n💡 Agora você pode usar:")
        print(f"   rag.configurar_chain()")
        print(f"   rag.consultar('sua pergunta')")
        
        return True
        
    def carregar_json_disciplina(self, caminho_json):
        """
        Carrega um arquivo JSON de disciplina e converte em documentos estruturados
        
        Args:
            caminho_json: Caminho para o arquivo JSON da disciplina
        
        Returns:
            Lista de documentos com diferentes aspectos da disciplina
        """
        with open(caminho_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        disciplina = data['disciplina']
        documentos = []
        
        # 1. Documento com informações gerais
        docentes = disciplina.get('docentes', [])
        docentes_str = ', '.join(docentes) if docentes else 'N/A'
        
        info_geral = f"""
Disciplina: {disciplina['nome']}
Nome em Inglês: {disciplina.get('nome_ingles', 'N/A')}
Código: {disciplina.get('codigo', 'N/A')}
Campus: {disciplina.get('campus', 'N/A')}
Curso(s): {', '.join(disciplina.get('curso', []))}
Tipo: {disciplina.get('tipo', 'N/A')}
Formato: {disciplina.get('formato', 'N/A')}
Termo: {disciplina.get('termo', 'N/A')}
Turno: {disciplina.get('turno', 'N/A')}
Oferta: {disciplina.get('oferta', 'N/A')}
Docentes: {docentes_str}
"""
        documentos.append(Document(
            page_content=info_geral.strip(),
            metadata={
                'disciplina': disciplina['nome'],
                'codigo': disciplina.get('codigo', 'N/A'),
                'tipo_conteudo': 'informacoes_gerais',
                'source': caminho_json
            }
        ))
        
        # 2. Documento com carga horária
        carga = disciplina.get('carga_horaria', {})
        carga_horaria = f"""
Disciplina: {disciplina['nome']}
Carga Horária:
- Total: {carga.get('total', 'N/A')} horas
- Teórica: {carga.get('teorica', 'N/A')} horas
- Prática: {carga.get('pratica', 'N/A')} horas
- Extensão: {carga.get('extensao', 'N/A')} horas
"""
        documentos.append(Document(
            page_content=carga_horaria.strip(),
            metadata={
                'disciplina': disciplina['nome'],
                'codigo': disciplina.get('codigo', 'N/A'),
                'tipo_conteudo': 'carga_horaria',
                'source': caminho_json
            }
        ))
        
        # 3. Documento com pré-requisitos
        pre_reqs = disciplina.get('pre_requisitos', [])
        if pre_reqs:
            pre_requisitos = f"Disciplina: {disciplina['nome']}\nPré-requisitos:\n"
            for req in pre_reqs:
                pre_requisitos += f"- {req.get('codigo', 'N/A')} - {req.get('nome', 'N/A')}\n"
        else:
            pre_requisitos = f"Disciplina: {disciplina['nome']}\nPré-requisitos: Não há pré-requisitos"
        
        documentos.append(Document(
            page_content=pre_requisitos.strip(),
            metadata={
                'disciplina': disciplina['nome'],
                'codigo': disciplina.get('codigo', 'N/A'),
                'tipo_conteudo': 'pre_requisitos',
                'source': caminho_json
            }
        ))
        
        # 4. Documento com ementa completa
        ementa_data = disciplina.get('ementa', {})
        ementa = f"""
Disciplina: {disciplina['nome']}
Ementa: {ementa_data.get('descricao_completa', 'N/A')}

Tópicos principais:
"""
        for topico in ementa_data.get('topicos', []):
            ementa += f"- {topico}\n"
        
        documentos.append(Document(
            page_content=ementa.strip(),
            metadata={
                'disciplina': disciplina['nome'],
                'codigo': disciplina.get('codigo', 'N/A'),
                'tipo_conteudo': 'ementa',
                'source': caminho_json
            }
        ))
        
        # 5. Documento com bibliografia básica
        biblio = disciplina.get('bibliografia', {})
        if biblio.get('basica'):
            biblio_basica = f"Disciplina: {disciplina['nome']}\nBibliografia Básica:\n\n"
            for i, livro in enumerate(biblio['basica'], 1):
                autores = ', '.join(livro.get('autores', ['N/A']))
                titulo = livro.get('titulo', 'N/A')
                editora = livro.get('editora', 'N/A')
                ano = livro.get('ano', 'N/A')
                biblio_basica += f"{i}. {autores}. {titulo}. {editora}, {ano}.\n"
            
            documentos.append(Document(
                page_content=biblio_basica.strip(),
                metadata={
                    'disciplina': disciplina['nome'],
                    'codigo': disciplina.get('codigo', 'N/A'),
                    'tipo_conteudo': 'bibliografia_basica',
                    'source': caminho_json
                }
            ))
        
        # 6. Documento com bibliografia complementar
        if biblio.get('complementar'):
            biblio_comp = f"Disciplina: {disciplina['nome']}\nBibliografia Complementar:\n\n"
            for i, livro in enumerate(biblio['complementar'], 1):
                autores = ', '.join(livro.get('autores', ['N/A']))
                titulo = livro.get('titulo', 'N/A')
                editora = livro.get('editora', 'N/A')
                ano = livro.get('ano', 'N/A')
                biblio_comp += f"{i}. {autores}. {titulo}. {editora}, {ano}.\n"
            
            documentos.append(Document(
                page_content=biblio_comp.strip(),
                metadata={
                    'disciplina': disciplina['nome'],
                    'codigo': disciplina.get('codigo', 'N/A'),
                    'tipo_conteudo': 'bibliografia_complementar',
                    'source': caminho_json
                }
            ))
        
        # 7. Documento específico para docentes (facilita buscas por professor)
        docentes = disciplina.get('docentes', [])
        if docentes:
            docentes_doc = f"Disciplina: {disciplina['nome']}\nCódigo: {disciplina.get('codigo', 'N/A')}\n\nDocentes que ministram esta disciplina:\n"
            for i, docente in enumerate(docentes, 1):
                docentes_doc += f"{i}. {docente}\n"
            
            documentos.append(Document(
                page_content=docentes_doc.strip(),
                metadata={
                    'disciplina': disciplina['nome'],
                    'codigo': disciplina.get('codigo', 'N/A'),
                    'tipo_conteudo': 'docentes',
                    'source': caminho_json
                }
            ))
        
        return documentos
    
    def carregar_jsons_diretorio(self, diretorio_jsons):
        """
        Carrega todos os arquivos JSON de um diretório
        
        Args:
            diretorio_jsons: Caminho para o diretório com os JSONs
        """
        print(f"📚 Carregando JSONs do diretório: {diretorio_jsons}")
        
        todos_documentos = []
        arquivos_json = list(Path(diretorio_jsons).glob("*.json"))
        
        print(f"📄 Encontrados {len(arquivos_json)} arquivos JSON")
        
        for json_file in arquivos_json:
            try:
                docs = self.carregar_json_disciplina(str(json_file))
                todos_documentos.extend(docs)
                print(f"  ✅ {json_file.name}: {len(docs)} documentos")
            except Exception as e:
                print(f"  ❌ Erro ao carregar {json_file.name}: {e}")
        
        print(f"\n✅ Total: {len(todos_documentos)} documentos carregados de {len(arquivos_json)} disciplinas")
        return todos_documentos
    
    def processar_documentos(self, documentos, chunk_size=1000, chunk_overlap=200):
        """
        Divide documentos em chunks para melhor recuperação
        Para JSONs estruturados, chunks maiores preservam melhor o contexto
        
        Args:
            documentos: Lista de documentos carregados
            chunk_size: Tamanho de cada chunk (1000 é bom para conteúdo estruturado)
            chunk_overlap: Sobreposição entre chunks
        """
        print(f"✂️  Dividindo documentos em chunks...")
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len
        )
        
        splits = splitter.split_documents(documentos)
        print(f"✅ {len(splits)} chunks criados")
        return splits
    
    def criar_banco_vetorial(self, splits, persistir=True):
        """
        Cria o banco vetorial com os chunks processados
        
        Args:
            splits: Documentos divididos em chunks
            persistir: Se True, salva o banco em disco para reutilização
        """
        print(f"🔧 Criando banco vetorial...")
        
        if persistir:
            self.db = Chroma.from_documents(
                splits, 
                embedding=self.embeddings,
                persist_directory=self.persist_directory
            )
            print(f"💾 Banco vetorial salvo em: {self.persist_directory}")
        else:
            self.db = Chroma.from_documents(splits, embedding=self.embeddings)
            print(f"✅ Banco vetorial criado (apenas em memória)")
        
        self.retriever = self.db.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 6}  # Retorna top 6 chunks mais relevantes
        )
        
        # Estatísticas
        print(f"📊 Total de documentos no banco: {len(splits)}")
        disciplinas = set(doc.metadata.get('disciplina', 'Desconhecida') for doc in splits)
        print(f"📚 Disciplinas indexadas: {len(disciplinas)}")
        
        # Tipos de conteúdo
        tipos = set(doc.metadata.get('tipo_conteudo', 'Desconhecido') for doc in splits)
        print(f"📋 Tipos de conteúdo: {', '.join(tipos)}")
    
    def carregar_banco_existente(self):
        """Carrega um banco vetorial já criado anteriormente"""
        if not os.path.exists(self.persist_directory):
            raise FileNotFoundError(f"Banco vetorial não encontrado em {self.persist_directory}")
        
        print(f"📂 Carregando banco vetorial existente...")
        self.db = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings
        )
        self.retriever = self.db.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 6}
        )
        print(f"✅ Banco vetorial carregado")
    
    def buscar_por_disciplina(self, disciplina, k=5):
        """Busca chunks específicos de uma disciplina"""
        if not self.db:
            raise ValueError("Banco vetorial não foi criado ou carregado")
        
        resultados = self.db.similarity_search(
            disciplina,
            k=k,
            filter={"disciplina": disciplina}
        )
        return resultados
    
    def buscar_por_tipo_conteudo(self, tipo_conteudo, disciplina=None, k=5):
        """
        Busca por tipo específico de conteúdo
        
        Args:
            tipo_conteudo: 'informacoes_gerais', 'ementa', 'bibliografia_basica', etc.
            disciplina: Nome da disciplina (opcional, para filtrar)
            k: Número de resultados
        """
        if not self.db:
            raise ValueError("Banco vetorial não foi criado ou carregado")
        
        filtro = {"tipo_conteudo": tipo_conteudo}
        if disciplina:
            filtro["disciplina"] = disciplina
        
        resultados = self.db.similarity_search(
            tipo_conteudo,
            k=k,
            filter=filtro
        )
        return resultados
    
    def listar_disciplinas(self):
        """Lista todas as disciplinas no banco vetorial"""
        if not self.db:
            raise ValueError("Banco vetorial não foi criado ou carregado")
        
        resultados = self.db.get()
        disciplinas = set()
        
        if resultados and 'metadatas' in resultados:
            for metadata in resultados['metadatas']:
                if 'disciplina' in metadata:
                    disciplinas.add(metadata['disciplina'])
        
        return sorted(list(disciplinas))
    
    def listar_disciplinas_com_codigo(self):
        """Lista todas as disciplinas com seus códigos"""
        if not self.db:
            raise ValueError("Banco vetorial não foi criado ou carregado")
        
        resultados = self.db.get()
        disciplinas_dict = {}
        
        if resultados and 'metadatas' in resultados:
            for metadata in resultados['metadatas']:
                nome = metadata.get('disciplina')
                codigo = metadata.get('codigo')
                if nome and codigo and codigo != 'N/A':
                    disciplinas_dict[nome] = codigo
        
        return disciplinas_dict
    
    def configurar_chain(self):
        """Configura a chain RAG para consultas"""
        template = """Você é um assistente especializado nas disciplinas da Unifesp ICT (Instituto de Ciência e Tecnologia) em São José dos Campos.

Responda a pergunta baseado APENAS no seguinte contexto estruturado das disciplinas:

{context}

Pergunta: {question}

Instruções para responder:
- Use EXATAMENTE as informações do contexto fornecido
- Cite o nome da disciplina e código quando disponível
- Para carga horária, pré-requisitos, ementa ou bibliografia, use os dados estruturados
- Seja específico: mencione horas exatas, códigos de disciplinas, nomes de autores/livros
- Se a informação não estiver no contexto, diga claramente "Não encontrei essa informação"
- Organize a resposta de forma clara (use tópicos quando apropriado)
- Se houver múltiplas disciplinas relevantes, compare-as

Resposta:"""
        
        prompt = ChatPromptTemplate.from_template(template)
        
        def format_docs(docs):
            formatted = []
            for doc in docs:
                disciplina = doc.metadata.get('disciplina', 'Disciplina desconhecida')
                codigo = doc.metadata.get('codigo', '')
                tipo = doc.metadata.get('tipo_conteudo', '')
                
                header = f"[{disciplina}"
                if codigo and codigo != 'N/A':
                    header += f" - Código: {codigo}"
                if tipo:
                    header += f" - {tipo.replace('_', ' ').title()}"
                header += "]"
                
                formatted.append(f"{header}\n{doc.page_content}")
            return "\n\n---\n\n".join(formatted)
        
        self.rag_chain = (
            {"context": self.retriever | format_docs, "question": RunnablePassthrough()}
            | prompt
            | self.llm
            | StrOutputParser()
        )
        
        print("🔗 Chain RAG configurada")
    
    def consultar(self, pergunta):
        """Faz uma consulta ao sistema RAG"""
        if not hasattr(self, 'rag_chain'):
            self.configurar_chain()
        
        print(f"\n❓ Pergunta: {pergunta}")
        print("🤔 Processando...\n")
        
        resultado = self.rag_chain.invoke(pergunta)
        return resultado


# ====================
# EXEMPLOS DE USO
# ====================

def exemplo_1_criar_novo_banco():
    """Exemplo: Criar banco vetorial do zero com JSONs de disciplinas"""
    rag = RAGUnifespJSON()
    
    # Carregar todos os JSONs do diretório
    documentos = rag.carregar_jsons_diretorio("./jsons_disciplinas")
    
    # Processar e criar banco vetorial
    splits = rag.processar_documentos(documentos, chunk_size=1000, chunk_overlap=200)
    rag.criar_banco_vetorial(splits, persistir=True)
    
    # Configurar e fazer consultas de teste
    rag.configurar_chain()
    
    print("\n" + "="*80)
    print("🧪 TESTANDO O SISTEMA")
    print("="*80 + "\n")
    
    perguntas_teste = [
        "Qual a carga horária de Banco de Dados?",
        "Quais são os pré-requisitos de Algoritmos e Estruturas de Dados II?",
        "Me fale sobre a ementa de Sistemas Operacionais"
    ]
    
    for pergunta in perguntas_teste:
        resposta = rag.consultar(pergunta)
        print(f"💬 {resposta}")
        print("\n" + "-"*80 + "\n")

def exemplo_2_usar_banco_existente():
    """Exemplo: Usar banco vetorial já criado"""
    rag = RAGUnifespJSON()
    
    # Carregar banco existente
    rag.carregar_banco_existente()
    
    # Listar disciplinas disponíveis
    print("\n📚 Disciplinas disponíveis com códigos:")
    disciplinas_dict = rag.listar_disciplinas_com_codigo()
    for nome, codigo in sorted(disciplinas_dict.items()):
        print(f"  {codigo} - {nome}")
    
    print(f"\n📊 Total: {len(disciplinas_dict)} disciplinas\n")
    
    # Configurar chain
    rag.configurar_chain()

def exemplo_reiniciar_banco():
    """Exemplo: Reiniciar banco quando você alterou os JSONs"""
    rag = RAGUnifespJSON()
    
    # OPÇÃO 1: Apenas deletar o banco (você recria manualmente depois)
    # rag.reiniciar_banco_vetorial()
    
    # OPÇÃO 2: Deletar E recriar automaticamente (RECOMENDADO!)
    rag.recriar_banco_completo(diretorio_jsons="./jsons_disciplinas")
    
    # Agora pode usar normalmente
    rag.configurar_chain()
    resposta = rag.consultar("Teste com os novos campos")
    print(resposta)

def exemplo_4_modo_interativo():
    """Exemplo: Modo interativo para fazer perguntas"""
    rag = RAGUnifespJSON()
    rag.carregar_banco_existente()
    rag.configurar_chain()
    
    print("\n" + "="*80)
    print("🎓 MODO INTERATIVO - Sistema RAG Unifesp ICT")
    print("="*80)
    print("\nDigite suas perguntas sobre as disciplinas.")
    print("Digite 'sair' para encerrar, 'disciplinas' para listar todas.")
    print("Digite 'reiniciar' para recriar o banco vetorial.\n")
    
    while True:
        pergunta = input("❓ Você: ").strip()
        
        if pergunta.lower() in ['sair', 'exit', 'quit']:
            print("\n👋 Até logo!")
            break
        
        if pergunta.lower() == 'disciplinas':
            disciplinas = rag.listar_disciplinas()
            print(f"\n📚 {len(disciplinas)} disciplinas disponíveis:")
            for i, disc in enumerate(disciplinas, 1):
                print(f"  {i}. {disc}")
            print()
            continue
        
        if pergunta.lower() == 'reiniciar':
            print("\n🔄 Você quer reiniciar o banco vetorial.")
            diretorio = input("Digite o diretório dos JSONs [./jsons_disciplinas]: ").strip()
            if not diretorio:
                diretorio = "./jsons_disciplinas"
            
            if rag.recriar_banco_completo(diretorio):
                rag.configurar_chain()
                print("\n✅ Banco reiniciado! Continue fazendo perguntas.\n")
            else:
                print("\n❌ Falha ao reiniciar. Continuando com banco atual.\n")
            continue
        
        if not pergunta:
            continue
        
        try:
            resposta = rag.consultar(pergunta)
            print(f"\n🤖 Assistente: {resposta}\n")
        except Exception as e:
            print(f"\n❌ Erro: {e}\n")


if __name__ == "__main__":
    # Descomente o exemplo que quiser executar:
    
    # 1. PRIMEIRA VEZ: Criar o banco vetorial a partir dos JSONs
    # exemplo_1_criar_novo_banco()
    
    # 2. CONSULTAS NORMAIS: Usar banco já criado
    # exemplo_2_usar_banco_existente()
    
    # 3. REINICIAR: Quando você alterou os JSONs (NOVO!)
    # exemplo_reiniciar_banco()
    
    # 4. MODO INTERATIVO: Perguntas em tempo real (com opção de reiniciar)
    exemplo_4_modo_interativo()
    
    print("""
    🎓 Sistema RAG Unifesp ICT - Disciplinas (JSON)
    
    ══════════════════════════════════════════════════════════════
    
    🔄 REINICIAR BANCO (QUANDO VOCÊ ALTEROU OS JSONs):
    
    rag = RAGUnifespJSON()
    
    # Deletar E recriar automaticamente
    rag.recriar_banco_completo(diretorio_jsons="./jsons_disciplinas")
    
    # Ou apenas deletar (você recria depois)
    rag.reiniciar_banco_vetorial()
    
    ══════════════════════════════════════════════════════════════
    
    📋 GUIA DE USO:
    
    1️⃣  PRIMEIRA VEZ - Criar o banco vetorial:
       exemplo_1_criar_novo_banco()
    
    2️⃣  USO NORMAL - Consultas rápidas:
       exemplo_2_usar_banco_existente()
    
    3️⃣  REINICIAR - Alterou os JSONs? (NOVO!)
       exemplo_reiniciar_banco()
    
    4️⃣  MODO INTERATIVO - Chat com opção de reiniciar:
       exemplo_4_modo_interativo()
    
    ══════════════════════════════════════════════════════════════
    """)