import networkx as nx
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path

class KnowledgeGraph:
    """" Grafo de conhecimento """

    def __init__(self):
        self.graph = nx.MultiDiGraph()

    def build_from_directories(self, disciplinas_dir: str, regimentos_dir: str, docentes_dir: str = None, cursos_dir: str = None):
        """Constrói o grafo a partir de todos os diretórios."""
     
        disciplinas_path = Path(disciplinas_dir)
        for md_file in disciplinas_path.glob("*.md"):
            self._process_discipline_file(md_file)
        
        
        regimentos_path = Path(regimentos_dir)
        for md_file in regimentos_path.glob("*.md"):
            self._process_regimento_file(md_file)
        
        # Processar docentes com especialidades
        if docentes_dir:
            docentes_path = Path(docentes_dir)
            for md_file in docentes_path.glob("*.md"):
                self._process_docentes_file(md_file)
        
        # Processar matrizes curriculares
        if cursos_dir:
            cursos_path = Path(cursos_dir)
            for md_file in cursos_path.glob("*.md"):
                self._process_matriz_curricular(md_file)
        
        stats = self.get_stats()
        print(f"Grafo construído:")
        print(f"  - {stats['disciplinas']} disciplinas")
        print(f"  - {stats['docentes']} docentes")
        print(f"  - {stats['cursos']} cursos")
        print(f"  - {stats['matrizes']} matrizes curriculares")
        print(f"  - {stats['areas']} áreas de especialização")
        print(f"  - {stats['documentos']} documentos institucionais")
        print(f"  - {stats['orgaos']} órgãos/setores")
        print(f"  - {stats['artigos']} artigos")
        print(f"  - Total: {stats['total_nos']} nós, {stats['total_arestas']} arestas")
    
    def _process_discipline_file(self, file_path: Path):
        """Processa um arquivo de disciplina."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        nome_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        if not nome_match:
            return
        
        nome = nome_match.group(1).strip()

        codigo = self._extract_field(content, 'Código')
        sigla = self._extract_field(content, 'Sigla')
        termo = self._extract_field(content, 'Termo')

        curso_match = re.search(r'\*\*Curso\(s\):\*\*\s*(.+)', content)
        cursos = [c.strip() for c in curso_match.group(1).split(',')] if curso_match else []

        docentes = self._extract_list_section(content, 'Docentes')

        prereqs = []

        prereq_match = re.search(r'## Pré-requisitos\n\n(.*?)(?=\n## |$)', content, re.DOTALL)

        if prereq_match:
            prereqs_found = re.findall(r'-\s*(.+?)\s*\(Código:\s*(\S+)\)', prereq_match.group(1))
            prereqs = [(p[0].strip(), p[1].strip()) for p in prereqs_found]

        
        disc_id = f"DISC:{nome}"
        self.graph.add_node(disc_id, tipo="disciplina", nome=nome, codigo=codigo, sigla=sigla, termo=termo)
        
        for docente in docentes:
            if docente:
                doc_id = f"DOC:{docente}"
                self.graph.add_node(doc_id, tipo="docente", nome=docente)
                self.graph.add_edge(doc_id, disc_id, relacao="LECIONA")
        

        for curso in cursos:
            if curso:
                curso_id = f"CURSO:{curso}"
                self.graph.add_node(curso_id, tipo="curso", nome=curso)
                self.graph.add_edge(curso_id, disc_id, relacao="OFERECE")
        
        for prereq_nome, prereq_codigo in prereqs:
            prereq_id = f"DISC:{prereq_nome}"
            if not self.graph.has_node(prereq_id):
                self.graph.add_node(prereq_id, tipo="disciplina", nome=prereq_nome, codigo=prereq_codigo)
            self.graph.add_edge(prereq_id, disc_id, relacao="PREREQUISITO_DE")

    def _process_regimento_file(self, filepath: Path):
        """Processa um arquivo de regimento/documento institucional."""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        titulo_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        titulo = titulo_match.group(1).strip() if titulo_match else filepath.stem
        
        resolucao = self._extract_field(content, 'Resolucao')
        
        doc_id = f"REGIMENTO:{titulo}"
        self.graph.add_node(doc_id, tipo="documento", nome=titulo, resolucao=resolucao, source=str(filepath))
        
        artigos = re.findall(r'\*\*Art\. (\d+)\.\*\*\s*(.+?)(?=\*\*Art\. |\n## |$)', content, re.DOTALL)
        
        for num, conteudo in artigos:
            artigo_id = f"ART:{titulo}:{num}"
            conteudo_limpo = conteudo.strip()[:500]  
            
            self.graph.add_node(artigo_id, tipo="artigo", numero=num, conteudo=conteudo_limpo, documento=titulo)
            self.graph.add_edge(doc_id, artigo_id, relacao="CONTEM")
            
            orgaos = self._extract_orgaos(conteudo)
            for orgao in orgaos:
                orgao_id = f"ORGAO:{orgao}"
                if not self.graph.has_node(orgao_id):
                    self.graph.add_node(orgao_id, tipo="orgao", nome=orgao)
                self.graph.add_edge(artigo_id, orgao_id, relacao="MENCIONA")

            refs = re.findall(r'art\.\s*(\d+)', conteudo, re.IGNORECASE)
            for ref_num in refs:
                if ref_num != num: 
                    ref_id = f"ART:{titulo}:{ref_num}"
                    self.graph.add_edge(artigo_id, ref_id, relacao="REFERENCIA")
            
        faq_match = re.search(r'## Perguntas Frequentes\n\n(.*?)(?=\n## |$)', content, re.DOTALL)
        if faq_match:
            faqs = re.findall(r'\*\*Pergunta:\*\*\s*(.+?)\s*\*\*Resposta:\*\*\s*(.+?)(?=\*\*Pergunta:|$)', 
                            faq_match.group(1), re.DOTALL)
            for i, (pergunta, resposta) in enumerate(faqs):
                faq_id = f"FAQ:{titulo}:{i+1}"
                self.graph.add_node(faq_id, tipo="faq", pergunta=pergunta.strip(), 
                                   resposta=resposta.strip(), documento=titulo)
                self.graph.add_edge(doc_id, faq_id, relacao="CONTEM_FAQ")
        

    
    def _extract_orgaos(self, texto: str) -> List[str]:
        """Extrai nomes de órgãos/setores mencionados no texto."""
        orgaos_conhecidos = [
            'Câmara de Graduação', 'Câmara de Pós-graduação', 'Câmara de Extensão',
            'Congregação', 'Conselho de Campus', 'Conselho do Departamento',
            'NAE', 'SAE', 'Biblioteca', 'GTAE', 'DCT', 'ICT',
            'CONSU', 'CPPD', 'CoTAE', 'SAG', 'PRAE',
            'Núcleo de Apoio ao Estudante', 'Serviço de Atendimento ao Estudante',
            'Diretoria', 'Departamento de Ciência e Tecnologia'
        ]
        
        encontrados = []
        texto_lower = texto.lower()
        for orgao in orgaos_conhecidos:
            if orgao.lower() in texto_lower:
                encontrados.append(orgao)
        
        return encontrados
    
    def _extract_field(self, content: str, field: str) -> Optional[str]:
        """Extrai um campo do formato **Campo:** valor"""
        match = re.search(rf'\*\*{field}:\*\*\s*(.+)', content)
        return match.group(1).strip() if match else None
    
    def _process_docentes_file(self, filepath: Path):
        """Processa arquivo de docentes com especialidades, email e sala."""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Encontrar blocos de docentes (do ### até o próximo ### ou ---)
        docente_blocks = re.split(r'(?=###\s+Prof)', content)
        
        for block in docente_blocks:
            if not block.strip() or not block.startswith('###'):
                continue
            
            # Extrair nome
            nome_match = re.search(r'###\s+(?:Prof(?:a)?\.?\s+)?(?:Dr(?:a)?\.?\s+)?(.+)', block)
            if not nome_match:
                continue
            nome = nome_match.group(1).strip()
            
            # Extrair áreas
            areas_match = re.search(r'\*\*Áreas?:\*\*\s*(.+?)(?=\n-|\n###|\n---|\Z)', block, re.DOTALL)
            areas_str = areas_match.group(1).strip() if areas_match else ""
            
            # Extrair email
            email_match = re.search(r'\*\*Email:\*\*\s*(.+?)(?=\n|\Z)', block)
            email = email_match.group(1).strip() if email_match else ""
            
            # Extrair sala
            sala_match = re.search(r'\*\*Sala:\*\*\s*(.+?)(?=\n|\Z)', block)
            sala = sala_match.group(1).strip() if sala_match else ""
            
            doc_id = f"DOC:{nome}"
            
            # Atualizar ou criar nó do docente
            if self.graph.has_node(doc_id):
                self.graph.nodes[doc_id]['areas'] = areas_str
                self.graph.nodes[doc_id]['email'] = email
                self.graph.nodes[doc_id]['sala'] = sala
            else:
                self.graph.add_node(doc_id, tipo="docente", nome=nome, areas=areas_str, email=email, sala=sala)
            
            # Extrair áreas individuais e criar nós
            areas = [a.strip() for a in areas_str.split(',') if a.strip()]
            for area in areas:
                # Limpar área (remover quebras de linha, etc)
                area = re.sub(r'\s+', ' ', area).strip()
                if area and len(area) > 2:
                    area_id = f"AREA:{area}"
                    if not self.graph.has_node(area_id):
                        self.graph.add_node(area_id, tipo="area", nome=area)
                    self.graph.add_edge(doc_id, area_id, relacao="ESPECIALISTA_EM")
    
    def _extract_list_section(self, content: str, section: str) -> List[str]:
        """Extrai itens de uma seção com lista."""
        match = re.search(rf'## {section}\n\n(.*?)(?=\n## |$)', content, re.DOTALL)
        if match:
            return [item.replace('- ', '').strip() for item in match.group(1).split('\n') 
                   if item.strip() and item.strip().startswith('-')]
        return []
    
    def _process_matriz_curricular(self, filepath: Path):
        """Processa arquivo de matriz curricular."""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extrair título (nome do curso)
        titulo_match = re.search(r'^# Matriz Curricular - (.+)$', content, re.MULTILINE)
        if not titulo_match:
            titulo_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        
        if not titulo_match:
            return
        
        curso_nome = titulo_match.group(1).strip()
        
        # Extrair sigla (ex: BCC, BCT)
        sigla_match = re.search(r'\(([A-Z]{2,5})\)', curso_nome)
        sigla = sigla_match.group(1) if sigla_match else ""
        
        # Extrair carga horária total
        carga_match = re.search(r'\*\*Carga Horária Total:\*\*\s*(\d+)', content)
        carga_total = carga_match.group(1) if carga_match else ""
        
        # Extrair duração em termos
        duracao_match = re.search(r'\*\*Duração:\*\*\s*(\d+)\s*termos?', content, re.IGNORECASE)
        duracao_termos = duracao_match.group(1) if duracao_match else ""
        
        # Extrair coordenador e vice-coordenador
        coordenador = ""
        vice_coordenador = ""
        coord_match = re.search(r'\*\*Coordenador[a]?:\*\*\s*(.+?)(?:\n|$)', content)
        if coord_match:
            coordenador = coord_match.group(1).strip()
        vice_match = re.search(r'\*\*Vice-?[Cc]oordenador[a]?:\*\*\s*(.+?)(?:\n|$)', content)
        if vice_match:
            vice_coordenador = vice_match.group(1).strip()
        
        # Criar nó da matriz curricular
        matriz_id = f"MATRIZ:{curso_nome}"
        self.graph.add_node(matriz_id, 
                           tipo="matriz_curricular", 
                           nome=curso_nome, 
                           sigla=sigla,
                           carga_horaria=carga_total,
                           duracao_termos=duracao_termos,
                           coordenador=coordenador,
                           vice_coordenador=vice_coordenador,
                           source=str(filepath))
        
        # Conectar com o curso
        curso_id = f"CURSO:{curso_nome}"
        if not self.graph.has_node(curso_id):
            self.graph.add_node(curso_id, tipo="curso", nome=curso_nome, sigla=sigla)
        self.graph.add_edge(matriz_id, curso_id, relacao="MATRIZ_DE")
        
        # Extrair disciplinas por termo (suporta "### Termo 1", "### 1º Semestre", "### 1º Termo")
        # Lookahead simplificado: próximo ### com número, ou --- ou ## ou fim
        termo_pattern = r'###\s+(?:Termo\s+)?(\d+)[º°]?\s*(?:Semestre|Termo)?[^\n]*\n(.*?)(?=\n###\s+|\n---|\n## |\Z)'
        termos = re.findall(termo_pattern, content, re.DOTALL)
        
        for termo_num, termo_content in termos:
            # Encontrar disciplinas na tabela (suporta 2 ou 3+ colunas)
            # Captura: | Nome | Créditos | [resto opcional]
            disc_pattern = r'\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|'
            disciplinas = re.findall(disc_pattern, termo_content)
            
            for disc_nome, creditos in disciplinas:
                disc_nome = disc_nome.strip()
                if disc_nome and disc_nome != "Disciplina" and not disc_nome.startswith('-'):
                    disc_id = f"DISC:{disc_nome}"
                    
                    # Criar nó da disciplina se não existir
                    # NOTA: Uma disciplina pode aparecer em múltiplos termos de diferentes cursos
                    # Então não atualizamos o termo, mantemos o nó genérico
                    if not self.graph.has_node(disc_id):
                        self.graph.add_node(disc_id, tipo="disciplina", nome=disc_nome)
                    
                    # Conectar disciplina com a matriz
                    # A informação do termo fica na ARESTA, não no nó
                    # Assim a mesma disciplina pode estar em múltiplos termos
                    self.graph.add_edge(matriz_id, disc_id, relacao="INCLUI", termo=termo_num, creditos=creditos)
        
        # Extrair eletivas - usando padrões mais flexíveis para os títulos
        # Procurar todas as seções de eletivas no documento
        eletivas_sections = [
            (r"##\s*Eletivas?\s+(?:do\s+)?Grupo\s+1", "eletiva_grupo1"),
            (r"##\s*Eletivas?\s+(?:do\s+)?Grupo\s+2", "eletiva_grupo2"),
            (r"##\s*Eletivas?\s+(?:do\s+)?Grupo\s+3", "eletiva_grupo3"),
            (r"##\s*Eletivas?\s+Extensionistas?", "eletiva_extensionista"),
        ]
        
        for section_pattern, eletiva_tipo in eletivas_sections:
            # Buscar seção com padrão flexível - termina em próximo ## ou ---
            match = re.search(rf'{section_pattern}[^\n]*\n(.*?)(?=\n##\s|\n---|\Z)', content, re.DOTALL | re.IGNORECASE)
            if match:
                section_content = match.group(1)
                # Extrair itens da lista (- item)
                eletivas = re.findall(r'^-\s+(.+)$', section_content, re.MULTILINE)
                for eletiva in eletivas:
                    # Limpar nome da eletiva (remover parênteses com horas, "OU qualquer", etc)
                    if eletiva.upper().startswith('OU '):
                        continue  # Pular linhas que começam com "OU"
                    eletiva = re.sub(r'\s*\([^)]*\)\s*$', '', eletiva).strip()
                    if eletiva and len(eletiva) > 3 and not eletiva.startswith('*'):
                        eletiva_id = f"DISC:{eletiva}"
                        if not self.graph.has_node(eletiva_id):
                            self.graph.add_node(eletiva_id, tipo="disciplina", nome=eletiva, tipo_eletiva=eletiva_tipo)
                        self.graph.add_edge(matriz_id, eletiva_id, relacao="ELETIVA_DE", grupo=eletiva_tipo)

    
    def get_prerequisite_chain(self, disciplina: str, max_depth: int = 10) -> List[str]:
        """Retorna a cadeia completa de pré-requisitos."""
        disc_id = self._find_node(disciplina, "disciplina")
        if not disc_id:
            return []
        
        chain = []
        visited = set()
        
        def dfs(node, depth):
            if depth > max_depth or node in visited:
                return
            visited.add(node)
            
            for predecessor in self.graph.predecessors(node):
                edge = self.graph.get_edge_data(predecessor, node)
                if edge and edge.get('relacao') == 'PREREQUISITO_DE':
                    node_data = self.graph.nodes[predecessor]
                    if node_data.get('tipo') == 'disciplina':
                        chain.append(node_data.get('nome'))
                        dfs(predecessor, depth + 1)
        
        dfs(disc_id, 0)
        return chain
    
    def get_dependent_disciplines(self, disciplina: str) -> List[str]:
        """Disciplinas que dependem desta (esta é pré-requisito)."""
        disc_id = self._find_node(disciplina, "disciplina")
        if not disc_id:
            return []
        
        dependentes = []
        for successor in self.graph.successors(disc_id):
            edge = self.graph.get_edge_data(disc_id, successor)
            if edge and edge.get('relacao') == 'PREREQUISITO_DE':
                dependentes.append(self.graph.nodes[successor].get('nome'))
        
        return dependentes
    
    def get_docentes_of_discipline(self, disciplina: str) -> List[str]:
        """Docentes de uma disciplina."""
        disc_id = self._find_node(disciplina, "disciplina")
        if not disc_id:
            return []
        
        docentes = []
        for p in self.graph.predecessors(disc_id):
            # MultiDiGraph: get_edge_data retorna dict de dicts
            edges_data = self.graph.get_edge_data(p, disc_id)
            if edges_data:
                # Iterar sobre todas as arestas entre os mesmos nós
                for edge_key, edge in edges_data.items():
                    if edge.get('relacao') == 'LECIONA':
                        docentes.append(self.graph.nodes[p].get('nome'))
                        break  # Evita duplicatas se houver múltiplas arestas LECIONA
        return docentes

    def get_disciplines_of_docente(self, docente: str) -> List[str]:
        """Disciplinas que um docente leciona."""
        docente_id = f"DOC:{docente}"
        
        if not self.graph.has_node(docente_id):
            docente_lower = docente.lower()
            for node in self.graph.nodes():
                if node.startswith("DOC:"):
                    node_name = node.replace("DOC:", "").lower()
                    # Evitar match com nomes muito curtos (< 3 chars)
                    if len(node_name) >= 3 and (docente_lower in node_name or node_name in docente_lower):
                        docente_id = node
                        break
            else:
                return []
        
        disciplinas = []
        for successor in self.graph.successors(docente_id):
            # MultiDiGraph: get_edge_data retorna dict de dicts
            edges_data = self.graph.get_edge_data(docente_id, successor)
            if edges_data:
                # Iterar sobre todas as arestas entre os mesmos nós
                for edge_key, edge in edges_data.items():
                    if edge.get('relacao') == 'LECIONA':
                        nome = self.graph.nodes[successor].get('nome')
                        if nome:
                            disciplinas.append(nome)
                        break  # Evita duplicatas se houver múltiplas arestas LECIONA
        
        return disciplinas


    def get_artigos_sobre(self, tema: str) -> List[Dict]:
        """Busca artigos que mencionam um tema."""
        tema_lower = tema.lower()
        resultados = []
        
        for node, data in self.graph.nodes(data=True):
            if data.get('tipo') == 'artigo':
                conteudo = data.get('conteudo', '').lower()
                if tema_lower in conteudo:
                    resultados.append({
                        'numero': data.get('numero'),
                        'documento': data.get('documento'),
                        'conteudo': data.get('conteudo')[:200] + '...'
                    })
        
        return resultados
    
    def get_artigos_de_orgao(self, orgao: str) -> List[Dict]:
        """Busca artigos que mencionam um órgão."""
        orgao_id = self._find_node(orgao, "orgao")
        if not orgao_id:
            return []
        
        resultados = []
        for predecessor in self.graph.predecessors(orgao_id):
            edge = self.graph.get_edge_data(predecessor, orgao_id)
            if edge and edge.get('relacao') == 'MENCIONA':
                data = self.graph.nodes[predecessor]
                if data.get('tipo') == 'artigo':
                    resultados.append({
                        'numero': data.get('numero'),
                        'documento': data.get('documento'),
                        'conteudo': data.get('conteudo')[:200] + '...'
                    })
        
        return resultados

    def get_faqs_sobre(self, tema: str) -> List[Dict]:
        """Busca FAQs relacionadas a um tema."""
        tema_lower = tema.lower()
        resultados = []
        
        for node, data in self.graph.nodes(data=True):
            if data.get('tipo') == 'faq':
                pergunta = data.get('pergunta', '').lower()
                resposta = data.get('resposta', '').lower()
                if tema_lower in pergunta or tema_lower in resposta:
                    resultados.append({
                        'pergunta': data.get('pergunta'),
                        'resposta': data.get('resposta'),
                        'documento': data.get('documento')
                    })
        
        return resultados

    def get_artigos_relacionados(self, artigo_num: str, documento: str) -> List[Dict]:
        """Busca artigos que referenciam ou são referenciados por este."""
        artigo_id = f"ART:{documento}:{artigo_num}"
        if not self.graph.has_node(artigo_id):
            return []
        
        relacionados = []
        
        for successor in self.graph.successors(artigo_id):
            edge = self.graph.get_edge_data(artigo_id, successor)
            if edge and edge.get('relacao') == 'REFERENCIA':
                data = self.graph.nodes.get(successor, {})
                if data.get('tipo') == 'artigo':
                    relacionados.append({
                        'numero': data.get('numero'),
                        'documento': data.get('documento'),
                        'relacao': 'referenciado_por_este'
                    })
        
        for predecessor in self.graph.predecessors(artigo_id):
            edge = self.graph.get_edge_data(predecessor, artigo_id)
            if edge and edge.get('relacao') == 'REFERENCIA':
                data = self.graph.nodes.get(predecessor, {})
                if data.get('tipo') == 'artigo':
                    relacionados.append({
                        'numero': data.get('numero'),
                        'documento': data.get('documento'),
                        'relacao': 'referencia_este'
                    })
        
        return relacionados

    def _find_node(self, termo: str, tipo: str = None) -> Optional[str]:
        """Encontra um nó por nome, código ou sigla."""
        termo_lower = termo.lower().strip()
        
        for node, data in self.graph.nodes(data=True):
            if tipo and data.get('tipo') != tipo:
                continue
            
            nome = data.get('nome', '').lower()
            codigo = str(data.get('codigo', '')).lower()
            sigla = (data.get('sigla') or '').lower()
            
            if termo_lower in [nome, codigo, sigla] or termo_lower in nome or (sigla and termo_lower in sigla):
                return node
        
        return None
    
    def get_stats(self) -> Dict:
        """Estatísticas do grafo."""
        tipos = {}
        for _, data in self.graph.nodes(data=True):
            t = data.get('tipo', 'unknown')
            tipos[t] = tipos.get(t, 0) + 1
        
        return {
            'total_nos': self.graph.number_of_nodes(),
            'total_arestas': self.graph.number_of_edges(),
            'disciplinas': tipos.get('disciplina', 0),
            'docentes': tipos.get('docente', 0),
            'cursos': tipos.get('curso', 0),
            'matrizes': tipos.get('matriz_curricular', 0),
            'areas': tipos.get('area', 0),
            'documentos': tipos.get('documento', 0),
            'artigos': tipos.get('artigo', 0),
            'orgaos': tipos.get('orgao', 0),
            'faqs': tipos.get('faq', 0)
        }
    
    def get_disciplinas_do_termo(self, curso: str, termo: int) -> List[Dict]:
        """Retorna disciplinas de um termo específico de um curso."""
        resultados = []
        cursos_to_search = self._expand_curso_search(curso)
        
        # Encontrar a matriz do curso
        for node, data in self.graph.nodes(data=True):
            if data.get('tipo') == 'matriz_curricular':
                nome = data.get('nome', '').lower()
                sigla = data.get('sigla', '').lower()
                
                # Verificar match - MAIS ESPECÍFICO
                match_found = False
                for curso_term in cursos_to_search:
                    # Priorizar match exato de sigla
                    if curso_term == sigla:
                        match_found = True
                        break
                    # Ou se o nome completo do curso está no termo de busca ou vice-versa
                    # Mas evitar substring matches acidentais (ex: 'ec' em 'ciência')
                    if len(curso_term) > 3:  # Para termos longos, usar substring
                        if curso_term in nome or nome in curso_term:
                            match_found = True
                            break
                
                if match_found:
                    # Encontrar disciplinas conectadas
                    for successor in self.graph.successors(node):
                        # MultiDiGraph: get_edge_data retorna dict de dicts
                        edges_data = self.graph.get_edge_data(node, successor)
                        if edges_data:
                            # Iterar sobre todas as arestas entre os mesmos nós
                            for edge_key, edge in edges_data.items():
                                if edge.get('relacao') == 'INCLUI' and edge.get('termo') == str(termo):
                                    disc_data = self.graph.nodes[successor]
                                    resultados.append({
                                        'nome': disc_data.get('nome'),
                                        'creditos': edge.get('creditos'),
                                        'termo': termo
                                    })
                    break
        
        return resultados
    
    def get_todos_termos_do_curso(self, curso: str) -> Dict[int, List[Dict]]:
        """Retorna todas as disciplinas de todos os termos de um curso."""
        resultados = {}
        cursos_to_search = self._expand_curso_search(curso)
        
        # Encontrar a matriz do curso
        for node, data in self.graph.nodes(data=True):
            if data.get('tipo') == 'matriz_curricular':
                nome = data.get('nome', '').lower()
                sigla = data.get('sigla', '').lower()
                duracao = data.get('duracao_termos', '8')
                
                # Verificar match - MAIS ESPECÍFICO
                match_found = False
                for curso_term in cursos_to_search:
                    # Priorizar match exato de sigla
                    if curso_term == sigla:
                        match_found = True
                        break
                    # Ou se o nome completo do curso está no termo de busca ou vice-versa
                    # Mas evitar substring matches acidentais (ex: 'ec' em 'ciência')
                    if len(curso_term) > 3:  # Para termos longos, usar substring
                        if curso_term in nome or nome in curso_term:
                            match_found = True
                            break
                
                if match_found:
                    # Encontrar disciplinas conectadas e agrupar por termo
                    for successor in self.graph.successors(node):
                        # MultiDiGraph: get_edge_data retorna dict de dicts
                        edges_data = self.graph.get_edge_data(node, successor)
                        if edges_data:
                            # Iterar sobre todas as arestas entre os mesmos nós
                            for edge_key, edge in edges_data.items():
                                if edge.get('relacao') == 'INCLUI':
                                    termo_str = edge.get('termo', '0')
                                    try:
                                        termo_num = int(termo_str)
                                    except ValueError:
                                        continue
                                    
                                    if termo_num not in resultados:
                                        resultados[termo_num] = []
                                    
                                    disc_data = self.graph.nodes[successor]
                                    resultados[termo_num].append({
                                        'nome': disc_data.get('nome'),
                                        'creditos': edge.get('creditos'),
                                        'termo': termo_num
                                    })
                    break
        
        return resultados
    
    # Mapeamento de siglas/abreviações para nomes de cursos
    CURSO_ALIASES = {
        'bcc': ['ciência da computação', 'ciencia da computacao', 'computação', 'computacao'],
        'cc': ['ciência da computação', 'ciencia da computacao', 'computação'],
        'ec': ['engenharia de computação', 'engenharia de computacao'],
        'bct': ['bacharelado interdisciplinar', 'ciência e tecnologia'],
        'mat comp': ['matemática computacional', 'matematica computacional'],
        'bio': ['biotecnologia'],
        'eb': ['engenharia biomédica', 'engenharia biomedica'],
        'em': ['engenharia de materiais'],
    }
    
    def _expand_curso_search(self, curso: str) -> List[str]:
        """Expande a busca de curso incluindo aliases."""
        curso_lower = curso.lower().strip()
        cursos_to_search = [curso_lower]
        
        # Adicionar aliases
        if curso_lower in self.CURSO_ALIASES:
            cursos_to_search.extend(self.CURSO_ALIASES[curso_lower])
        
        return cursos_to_search
    
    def get_eletivas_do_curso(self, curso: str, grupo: str = None) -> List[Dict]:
        """Retorna eletivas de um curso (opcionalmente filtrado por grupo)."""
        resultados = []
        cursos_to_search = self._expand_curso_search(curso)
        
        for node, data in self.graph.nodes(data=True):
            if data.get('tipo') == 'matriz_curricular':
                nome = data.get('nome', '').lower()
                sigla = data.get('sigla', '').lower()
                
                # Verificar se algum termo de busca combina - MAIS ESPECÍFICO
                match_found = False
                for curso_term in cursos_to_search:
                    # Priorizar match exato de sigla
                    if curso_term == sigla:
                        match_found = True
                        break
                    # Ou se o nome completo do curso está no termo de busca ou vice-versa
                    # Mas evitar substring matches acidentais (ex: 'ec' em 'ciência')
                    if len(curso_term) > 3:  # Para termos longos, usar substring
                        if curso_term in nome or nome in curso_term:
                            match_found = True
                            break
                
                if match_found:
                    for successor in self.graph.successors(node):
                        # MultiDiGraph: get_edge_data retorna dict de dicts
                        edges_data = self.graph.get_edge_data(node, successor)
                        if edges_data:
                            # Iterar sobre todas as arestas entre os mesmos nós
                            for edge_key, edge in edges_data.items():
                                if edge.get('relacao') == 'ELETIVA_DE':
                                    grupo_eletiva = edge.get('grupo', '')
                                    if grupo is None or grupo.lower() in grupo_eletiva.lower():
                                        disc_data = self.graph.nodes[successor]
                                        resultados.append({
                                            'nome': disc_data.get('nome'),
                                            'grupo': grupo_eletiva
                                        })
                    break
        
        return resultados
    
    def get_info_matriz(self, curso: str) -> Optional[Dict]:
        """Retorna informações da matriz curricular de um curso."""
        cursos_to_search = self._expand_curso_search(curso)
        
        for node, data in self.graph.nodes(data=True):
            if data.get('tipo') == 'matriz_curricular':
                nome = data.get('nome', '').lower()
                sigla = data.get('sigla', '').lower()
                
                # Verificar match - MAIS ESPECÍFICO
                match_found = False
                for curso_term in cursos_to_search:
                    # Priorizar match exato de sigla
                    if curso_term == sigla:
                        match_found = True
                        break
                    # Ou se o nome completo do curso está no termo de busca ou vice-versa
                    # Mas evitar substring matches acidentais (ex: 'ec' em 'ciência')
                    if len(curso_term) > 3:  # Para termos longos, usar substring
                        if curso_term in nome or nome in curso_term:
                            match_found = True
                            break
                
                if match_found:
                    return {
                        'nome': data.get('nome'),
                        'sigla': data.get('sigla'),
                        'carga_horaria': data.get('carga_horaria'),
                        'duracao_termos': data.get('duracao_termos'),
                        'coordenador': data.get('coordenador', ''),
                        'vice_coordenador': data.get('vice_coordenador', ''),
                    }
        
        return None
    
    def get_coordenador(self, curso: str) -> Optional[Dict]:
        """Retorna informações do coordenador de um curso."""
        info = self.get_info_matriz(curso)
        if info and (info.get('coordenador') or info.get('vice_coordenador')):
            return {
                'curso': info.get('nome'),
                'sigla': info.get('sigla'),
                'coordenador': info.get('coordenador'),
                'vice_coordenador': info.get('vice_coordenador'),
            }
        return None
    
    def get_all_cursos(self) -> List[Dict]:
        """Retorna lista de todos os cursos com matriz curricular."""
        cursos = []
        for node, data in self.graph.nodes(data=True):
            if data.get('tipo') == 'matriz_curricular':
                cursos.append({
                    'nome': data.get('nome', ''),
                    'sigla': data.get('sigla', ''),
                    'duracao_termos': data.get('duracao_termos', ''),
                    'carga_horaria': data.get('carga_horaria', ''),
                    'coordenador': data.get('coordenador', ''),
                })
        return cursos
    
    # Sinônimos de áreas para melhor busca
    AREA_SYNONYMS = {
        'machine learning': ['aprendizado de máquina', 'aprendizagem de máquina', 'inteligência artificial', 'redes neurais'],
        'aprendizado de máquina': ['machine learning', 'inteligência artificial', 'redes neurais'],
        'ia': ['inteligência artificial'],
        'ai': ['inteligência artificial', 'artificial intelligence'],
        'deep learning': ['aprendizado profundo', 'redes neurais', 'inteligência artificial'],
        'ml': ['machine learning', 'aprendizado de máquina'],
        'redes neurais': ['neural networks', 'deep learning', 'inteligência artificial'],
        'data science': ['ciência de dados', 'mineração de dados'],
        'ciência de dados': ['data science', 'mineração de dados', 'inteligência artificial'],
    }
    
    def _expand_area_search(self, area: str) -> List[str]:
        """Expande a busca de área incluindo sinônimos."""
        area_lower = area.lower().strip()
        areas_to_search = [area_lower]
        
        # Adicionar sinônimos
        if area_lower in self.AREA_SYNONYMS:
            areas_to_search.extend(self.AREA_SYNONYMS[area_lower])
        
        return areas_to_search
    
    def get_docentes_by_area(self, area: str) -> List[str]:
        """Retorna docentes especialistas em uma área (com suporte a sinônimos)."""
        areas_to_search = self._expand_area_search(area)
        docentes = []
        
        for search_area in areas_to_search:
            area_lower = search_area.lower().strip()
            area_words = set(area_lower.split())
            
            for node, data in self.graph.nodes(data=True):
                if data.get('tipo') != 'area':
                    continue
                
                nome_area = data.get('nome', '').lower()
                nome_words = set(nome_area.split())
                
                # Match por palavras (evita "ia" dar match em "engenharia")
                is_match = False
                
                # Match exato
                if area_lower == nome_area:
                    is_match = True
                # Todas as palavras da query estão na área
                elif len(area_lower) > 3 and area_words.issubset(nome_words):
                    is_match = True
                # Substring match (apenas para termos maiores que 5 chars)
                elif len(area_lower) > 5 and area_lower in nome_area:
                    is_match = True
                
                if is_match:
                    # Encontrar docentes que apontam para essa área
                    for pred in self.graph.predecessors(node):
                        edge = self.graph.get_edge_data(pred, node)
                        if edge and edge.get('relacao') == 'ESPECIALISTA_EM':
                            nome = self.graph.nodes[pred].get('nome')
                            if nome and nome not in docentes:
                                docentes.append(nome)
        
        return docentes
    
    def _find_docente_id(self, docente: str) -> Optional[str]:
        """Encontra o ID do docente por nome (com fuzzy search, preferindo nós com mais info)."""
        docente_lower = docente.lower().strip()
        docente_words = set(docente_lower.split())
        
        # Buscar todos os matches possíveis
        matches = []
        
        for node in self.graph.nodes():
            if not node.startswith("DOC:"):
                continue
            
            node_name = node.replace("DOC:", "").lower()
            node_words = set(node_name.split())
            data = self.graph.nodes[node]
            
            # Match exato
            if node_name == docente_lower:
                matches.append((node, 100, data))
            # Todas as palavras da query estão no nome do docente
            elif docente_words.issubset(node_words):
                matches.append((node, 80, data))
            # Substring match
            elif len(node_name) >= 3 and (docente_lower in node_name or node_name in docente_lower):
                matches.append((node, 50, data))
        
        if not matches:
            return None
        
        # Ordenar por: 1) se tem email (info mais completa), 2) score de match
        matches.sort(key=lambda x: (1 if x[2].get('email') else 0, x[1]), reverse=True)
        
        return matches[0][0]
    
    def get_areas_of_docente(self, docente: str) -> List[str]:
        """Retorna as áreas de especialização de um docente."""
        docente_id = self._find_docente_id(docente)
        if not docente_id:
            return []
        
        areas = []
        
        # 1. Verificar atributo 'areas' no nó do docente
        node_areas = self.graph.nodes[docente_id].get('areas', '')
        if node_areas:
            if isinstance(node_areas, list):
                areas.extend(node_areas)
            elif isinstance(node_areas, str):
                # Pode ser uma string única ou separada por vírgulas
                areas.extend([a.strip() for a in node_areas.split(',') if a.strip()])
        
        # 2. Verificar conexões com nós de área (ESPECIALISTA_EM)
        for successor in self.graph.successors(docente_id):
            # MultiDiGraph: get_edge_data retorna dict de dicts
            edges_data = self.graph.get_edge_data(docente_id, successor)
            if edges_data:
                for edge_key, edge in edges_data.items():
                    if edge.get('relacao') == 'ESPECIALISTA_EM':
                        nome = self.graph.nodes[successor].get('nome')
                        if nome and nome not in areas:
                            areas.append(nome)
                        break
        
        return areas
    
    def get_docente_info(self, docente: str) -> Optional[Dict]:
        """Retorna informações completas de um docente (nome, email, sala, áreas)."""
        docente_id = self._find_docente_id(docente)
        if not docente_id:
            return None
        
        data = self.graph.nodes[docente_id]
        return {
            'nome': data.get('nome', ''),
            'email': data.get('email', ''),
            'sala': data.get('sala', ''),
            'areas': data.get('areas', ''),
        }