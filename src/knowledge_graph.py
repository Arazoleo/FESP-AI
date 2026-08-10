import networkx as nx
import re
import unicodedata
from typing import List, Dict, Optional, Set, Tuple
from pathlib import Path

class KnowledgeGraph:
    """" Grafo de conhecimento """

    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self._index_by_name: Dict[str, str] = {}
        self._index_by_sigla: Dict[str, str] = {}
        self._index_by_codigo: Dict[str, str] = {}
        self._authoritative_nodes: Set[str] = set()
        self._curso_name_to_sigla: Dict[str, str] = {}
        self._kgc: Optional["KGCompletion"] = None

    @property
    def kgc(self) -> "KGCompletion":
        """Acesso lazy ao KGCompletion - inicializado na primeira chamada."""
        if self._kgc is None:
            self._kgc = KGCompletion(self)
        return self._kgc
    
    @staticmethod
    def _normalize_text(text: str) -> str:
        """Remove acentos e normaliza texto para busca."""
        if not text:
            return ""
        normalized = unicodedata.normalize('NFD', text.lower().strip())
        normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        normalized = re.sub(r"\b(de|da|do|das|dos|e)\b", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized
    
    @staticmethod
    def _has_real_value(value) -> bool:
        """True se o valor é real (não vazio nem o literal 'None'/'N/A')."""
        return bool(value) and str(value).strip().lower() not in ("none", "null", "n/a")

    def _index_node(self, node_id: str, data: dict, authoritative: bool = False):
        """
        Adiciona nó aos índices para busca rápida.

        `authoritative=True` marca nós definidos pelo próprio arquivo da
        entidade (título do markdown). Nomes distintos podem colidir após a
        normalização (ex.: o pré-requisito com typo "Séries e Equações
        Diferenciais e Ordinárias" colide com a disciplina real "Séries e
        Equações Diferenciais Ordinárias" porque "e" é stopword) - sem esta
        regra, um nó fantasma sem arestas LECIONA sombreava a disciplina real
        no índice e "quem leciona SEDO?" retornava vazio.
        """
        nome = self._normalize_text(data.get('nome', ''))
        sigla = self._normalize_text(data.get('sigla') or '') if self._has_real_value(data.get('sigla')) else ''
        codigo = self._normalize_text(str(data.get('codigo', ''))) if self._has_real_value(data.get('codigo')) else ''

        if authoritative:
            self._authoritative_nodes.add(node_id)

        def _set(index: dict, key: str):
            if not key:
                return
            existing = index.get(key)
            if existing is None or existing == node_id:
                index[key] = node_id
            elif authoritative or existing not in self._authoritative_nodes:
                index[key] = node_id

        _set(self._index_by_name, nome)
        _set(self._index_by_sigla, sigla)
        _set(self._index_by_codigo, codigo)
    
    def _get_edge_relation(self, edge_data: dict) -> Optional[str]:
        """Helper para extrair relação de edge data do MultiDiGraph."""
        if not edge_data:
            return None
        for edge_key, edge in edge_data.items():
            return edge.get('relacao')
        return None
    
    def _has_edge_relation(self, edge_data: dict, relacao: str) -> bool:
        """Verifica se alguma aresta tem a relação especificada."""
        if not edge_data:
            return False
        for edge_key, edge in edge_data.items():
            if edge.get('relacao') == relacao:
                return True
        return False

    def build_from_directories(self, disciplinas_dir: str, regimentos_dir: str, docentes_dir: str = None, cursos_dir: str = None):
        """Constrói o grafo a partir de todos os diretórios."""
        if cursos_dir:
            cursos_path = Path(cursos_dir)
            for md_file in cursos_path.glob("*.md"):
                self._process_matriz_curricular(md_file)
            self._build_curso_name_mapping()

        disciplinas_path = Path(disciplinas_dir)
        for md_file in disciplinas_path.glob("*.md"):
            self._process_discipline_file(md_file)

        regimentos_path = Path(regimentos_dir)
        for md_file in regimentos_path.glob("*.md"):
            self._process_regimento_file(md_file)

        if docentes_dir:
            docentes_path = Path(docentes_dir)
            for md_file in docentes_path.glob("*.md"):
                self._process_docentes_file(md_file)
        
        try:
            issues = self.lint()
            problemas = {k: len(v) for k, v in issues.items() if v}
            if problemas:
                print(f"[KG lint] Inconsistências detectadas: {problemas}")
            duplicadas = issues.get("disciplinas_duplicadas") or []
            if duplicadas:
                print("=" * 70)
                print(f"[KG lint] WARNING: {len(duplicadas)} disciplina(s) "
                      "DUPLICADA(S) no grafo - corrija os nomes na fonte "
                      "(markdown_disciplinas/ e markdown_cursos/):")
                for a, b in duplicadas:
                    print(f"  - {a!r} != {b!r}")
                print("=" * 70)
        except Exception as e:
            print(f"[KG lint] falhou: {e}")

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
    
    def lint(self) -> Dict[str, list]:
        """
        NSAI-2: lint de consistência simbólica do grafo.

        Um sistema simbólico vale o que vale seu grafo - detecta:
        - disciplinas duplicadas por nome normalizado ("de/da Biologia Moderna")
        - ciclos no DAG de pré-requisitos (quebrariam o BFS topológico)
        - disciplinas sem vínculo com curso/matriz nem termo
        - nós de pré-requisito "pendurados" (criados só pela aresta, sem código)
        """
        import networkx as nx
        issues: Dict[str, list] = {
            "disciplinas_duplicadas": [],
            "ciclos_prereq": [],
            "disciplinas_sem_curso": [],
            "prereqs_pendurados": [],
        }

        vistos: Dict[str, str] = {}
        for _, d in self.graph.nodes(data=True):
            if d.get("tipo") != "disciplina":
                continue
            chave = self._normalize_text(d.get("nome", ""))
            if not chave:
                continue
            if chave in vistos and vistos[chave] != d.get("nome"):
                issues["disciplinas_duplicadas"].append((vistos[chave], d.get("nome")))
            else:
                vistos[chave] = d.get("nome")

        prereq_edges = [
            (u, v) for u, v, dd in self.graph.edges(data=True)
            if dd.get("relacao") == "PREREQUISITO_DE"
        ]
        sub = nx.DiGraph(prereq_edges)
        try:
            ciclo = nx.find_cycle(sub)
            issues["ciclos_prereq"].append(
                [self.graph.nodes[a].get("nome", a) for a, _ in ciclo]
            )
        except nx.NetworkXNoCycle:
            pass

        com_curso = {
            v for _, v, dd in self.graph.edges(data=True)
            if dd.get("relacao") in ("INCLUI", "OFERECE")
        }
        pendurados = set()
        for u, _ in prereq_edges:
            du = self.graph.nodes[u]
            if du.get("tipo") == "disciplina" and not du.get("codigo"):
                pendurados.add(du.get("nome"))
        issues["prereqs_pendurados"] = sorted(pendurados)

        for n, d in self.graph.nodes(data=True):
            if (
                d.get("tipo") == "disciplina"
                and n not in com_curso
                and not d.get("termo")
                and d.get("codigo")
            ):
                issues["disciplinas_sem_curso"].append(d.get("nome"))

        return issues

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

        ementa = ""
        ementa_match = re.search(r'##\s+Ementa\s*\n+(.*?)(?=\n#{2,3}\s|\Z)', content, re.DOTALL)
        if ementa_match:
            ementa = re.sub(r'\s+', ' ', ementa_match.group(1)).strip()[:800]

        prereqs = []

        prereq_match = re.search(r'## Pré-requisitos\n\n(.*?)(?=\n## |$)', content, re.DOTALL)

        if prereq_match:
            prereqs_found = re.findall(r'-\s*(.+?)\s*\(Código:\s*(\S+)\)', prereq_match.group(1))
            prereqs = [(p[0].strip(), p[1].strip()) for p in prereqs_found]

        
        disc_id = f"DISC:{nome}"
        self.graph.add_node(disc_id, tipo="disciplina", nome=nome, codigo=codigo, sigla=sigla, termo=termo, ementa=ementa)
        self._index_node(disc_id, {"nome": nome, "codigo": codigo, "sigla": sigla}, authoritative=True)
        
        for docente in docentes:
            if docente:
                doc_id = f"DOC:{docente}"
                self.graph.add_node(doc_id, tipo="docente", nome=docente)
                self.graph.add_edge(doc_id, disc_id, relacao="LECIONA", confidence=1.0)
        

        for curso in cursos:
            if not curso:
                continue
            if self._is_curso_blocked(curso):
                continue
            sigla = self._resolve_curso_to_sigla(curso)
            if sigla:
                curso_id = f"CURSO:{sigla}"
                if not self.graph.has_node(curso_id):
                    self.graph.add_node(curso_id, tipo="curso", nome=curso, sigla=sigla)
                self.graph.add_edge(curso_id, disc_id, relacao="OFERECE", confidence=1.0)
            else:
                curso_id = f"CURSO:{curso}"
                self.graph.add_node(curso_id, tipo="curso", nome=curso)
                self.graph.add_edge(curso_id, disc_id, relacao="OFERECE", confidence=1.0)
        
        for prereq_nome, prereq_codigo in prereqs:
            if not self._has_real_value(prereq_codigo):
                prereq_codigo = ""
            existing = (
                self._index_by_name.get(self._normalize_text(prereq_nome))
                or (self._index_by_codigo.get(self._normalize_text(prereq_codigo))
                    if prereq_codigo else None)
            )
            if existing and self.graph.nodes.get(existing, {}).get('tipo') == 'disciplina':
                prereq_id = existing
            else:
                prereq_id = f"DISC:{prereq_nome}"
                if not self.graph.has_node(prereq_id):
                    self.graph.add_node(prereq_id, tipo="disciplina", nome=prereq_nome, codigo=prereq_codigo)
                    self._index_node(prereq_id, {"nome": prereq_nome, "codigo": prereq_codigo})
            self.graph.add_edge(prereq_id, disc_id, relacao="PREREQUISITO_DE", confidence=1.0)

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
        
        docente_blocks = re.split(r'(?=###\s+Prof)', content)
        
        for block in docente_blocks:
            if not block.strip() or not block.startswith('###'):
                continue
            
            nome_match = re.search(r'###\s+(?:Prof(?:a)?\.?\s+)?(?:Dr(?:a)?\.?\s+)?(.+)', block)
            if not nome_match:
                continue
            nome = nome_match.group(1).strip()
            
            areas_match = re.search(r'\*\*Áreas?:\*\*\s*(.+?)(?=\n-|\n###|\n---|\Z)', block, re.DOTALL)
            areas_str = areas_match.group(1).strip() if areas_match else ""
            
            email_match = re.search(r'\*\*Email:\*\*\s*(.+?)(?=\n|\Z)', block)
            email = email_match.group(1).strip() if email_match else ""
            
            sala_match = re.search(r'\*\*Sala:\*\*\s*(.+?)(?=\n|\Z)', block)
            sala = sala_match.group(1).strip() if sala_match else ""
            
            doc_id = f"DOC:{nome}"
            
            if self.graph.has_node(doc_id):
                self.graph.nodes[doc_id]['areas'] = areas_str
                self.graph.nodes[doc_id]['email'] = email
                self.graph.nodes[doc_id]['sala'] = sala
            else:
                self.graph.add_node(doc_id, tipo="docente", nome=nome, areas=areas_str, email=email, sala=sala)
            
            areas = [a.strip() for a in areas_str.split(',') if a.strip()]
            for area in areas:
                area = re.sub(r'\s+', ' ', area).strip()
                if area and len(area) > 2:
                    area_id = f"AREA:{area}"
                    if not self.graph.has_node(area_id):
                        self.graph.add_node(area_id, tipo="area", nome=area)
                    self.graph.add_edge(doc_id, area_id, relacao="ESPECIALISTA_EM", confidence=1.0)
    
    def _build_curso_name_mapping(self):
        """Preenche _curso_name_to_sigla a partir dos nós curso já no grafo (sigla canônica)."""
        self._curso_name_to_sigla.clear()
        for node_id, data in self.graph.nodes(data=True):
            if data.get("tipo") != "curso":
                continue
            sigla = (data.get("sigla") or "").strip()
            nome = (data.get("nome") or "").strip()
            if not sigla:
                continue
            norm_sigla = self._normalize_text(sigla)
            norm_nome = self._normalize_text(nome)
            self._curso_name_to_sigla[norm_sigla] = sigla
            self._curso_name_to_sigla[norm_nome] = sigla
            nome_sem_sigla = re.sub(r'\s*\([A-Z]{2,5}\)\s*$', '', nome).strip()
            if nome_sem_sigla:
                self._curso_name_to_sigla[self._normalize_text(nome_sem_sigla)] = sigla
        alias = [
            ("ciência da computação", "BCC"), ("ciencia da computacao", "BCC"),
            ("ciências da computação", "BCC"), ("ciencias da computacao", "BCC"),
            ("ciência e tecnologia", "BCT"), ("ciencia e tecnologia", "BCT"),
            ("bacharelado interdisciplinar em ciência e tecnologia", "BCT"),
            ("engenharia de computação", "EC"), ("engenharia da computação", "EC"),
            ("engenharia biomédica", "EB"), ("engenharia biomedica", "EB"),
            ("engenharia de materiais", "EM"), ("bacharelado em biotecnologia", "BBT"),
            ("biotecnologia", "BBT"), ("matemática computacional", "BMC"), ("matematica computacional", "BMC"),
        ]
        for nome_key, sig in alias:
            key = self._normalize_text(nome_key)
            if key and key not in self._curso_name_to_sigla:
                self._curso_name_to_sigla[key] = sig

    CURSO_BLOCKLIST = frozenset({
        "ict", "instituto de ciência e tecnologia", "instituto de ciencia e tecnologia",
        "unifesp ict", "são josé dos campos/ict", "sao jose dos campos/ict",
    })

    def _is_curso_blocked(self, curso_nome: str) -> bool:
        """Retorna True se não deve criar nó de curso (ex.: ICT)."""
        key = self._normalize_text(curso_nome)
        if not key or len(key) <= 2:
            return True
        if key in self.CURSO_BLOCKLIST:
            return True
        if key == "ict" or key.startswith("ict ") or key.endswith(" ict"):
            return True
        return False

    def _resolve_curso_to_sigla(self, curso_nome: str) -> Optional[str]:
        """Resolve nome/variante de curso para sigla canônica (para unificar nós)."""
        if not curso_nome or not self._curso_name_to_sigla:
            return None
        key = self._normalize_text(curso_nome)
        if key in self._curso_name_to_sigla:
            return self._curso_name_to_sigla[key]
        for mapped_key, sigla in self._curso_name_to_sigla.items():
            if len(mapped_key) < 4:
                continue
            if mapped_key in key or key in mapped_key:
                return sigla
        return None

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
        
        titulo_match = re.search(r'^# Matriz Curricular - (.+)$', content, re.MULTILINE)
        if not titulo_match:
            titulo_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        
        if not titulo_match:
            return
        
        curso_nome = titulo_match.group(1).strip()
        
        sigla_match = re.search(r'\(([A-Z]{2,5})\)', curso_nome)
        sigla = sigla_match.group(1) if sigla_match else ""
        
        carga_match = re.search(r'\*\*Carga Horária Total:\*\*\s*(\d+)', content)
        carga_total = carga_match.group(1) if carga_match else ""
        
        duracao_match = re.search(r'\*\*Duração:\*\*\s*(\d+)\s*termos?', content, re.IGNORECASE)
        duracao_termos = duracao_match.group(1) if duracao_match else ""
        
        coordenador = ""
        vice_coordenador = ""
        coord_match = re.search(r'\*\*Coordenador[a]?:\*\*\s*(.+?)(?:\n|$)', content)
        if coord_match:
            coordenador = coord_match.group(1).strip()
        vice_match = re.search(r'\*\*Vice-?[Cc]oordenador[a]?:\*\*\s*(.+?)(?:\n|$)', content)
        if vice_match:
            vice_coordenador = vice_match.group(1).strip()
        
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
        
        curso_id = f"CURSO:{sigla}" if sigla else f"CURSO:{curso_nome}"
        if not self.graph.has_node(curso_id):
            self.graph.add_node(curso_id, tipo="curso", nome=curso_nome, sigla=sigla or "")
        self.graph.add_edge(matriz_id, curso_id, relacao="MATRIZ_DE")
        
        termo_pattern = r'###\s+(?:Termo\s+)?(\d+)[º°]?\s*(?:Semestre|Termo)?[^\n]*\n(.*?)(?=\n###\s+|\n---|\n## |\Z)'
        termos = re.findall(termo_pattern, content, re.DOTALL)
        
        for termo_num, termo_content in termos:
            disc_pattern = r'\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|'
            disciplinas = re.findall(disc_pattern, termo_content)
            
            for disc_nome, creditos in disciplinas:
                disc_nome = disc_nome.strip()
                if disc_nome and disc_nome != "Disciplina" and not disc_nome.startswith('-'):
                    disc_id = f"DISC:{disc_nome}"
                    
                    if not self.graph.has_node(disc_id):
                        self.graph.add_node(disc_id, tipo="disciplina", nome=disc_nome)
                    
                    self.graph.add_edge(matriz_id, disc_id, relacao="INCLUI", termo=termo_num, creditos=creditos, confidence=1.0)
        
        eletivas_sections = [
            (r"##\s*Eletivas?\s+(?:do\s+)?Grupo\s+1", "eletiva_grupo1"),
            (r"##\s*Eletivas?\s+(?:do\s+)?Grupo\s+2", "eletiva_grupo2"),
            (r"##\s*Eletivas?\s+(?:do\s+)?Grupo\s+3", "eletiva_grupo3"),
            (r"##\s*Eletivas?\s+Extensionistas?", "eletiva_extensionista"),
        ]
        
        for section_pattern, eletiva_tipo in eletivas_sections:
            match = re.search(rf'{section_pattern}[^\n]*\n(.*?)(?=\n##\s|\n---|\Z)', content, re.DOTALL | re.IGNORECASE)
            if match:
                section_content = match.group(1)
                eletivas = re.findall(r'^-\s+(.+)$', section_content, re.MULTILINE)
                for eletiva in eletivas:
                    if eletiva.upper().startswith('OU '):
                        continue
                    eletiva = re.sub(r'\s*\([^)]*\)\s*$', '', eletiva).strip()
                    if eletiva and len(eletiva) > 3 and not eletiva.startswith('*'):
                        eletiva_id = f"DISC:{eletiva}"
                        if not self.graph.has_node(eletiva_id):
                            self.graph.add_node(eletiva_id, tipo="disciplina", nome=eletiva, tipo_eletiva=eletiva_tipo)
                        self.graph.add_edge(matriz_id, eletiva_id, relacao="ELETIVA_DE", grupo=eletiva_tipo, confidence=1.0)

    
    def get_prerequisite_chain(self, disciplina: str, max_depth: int = 10, min_confidence: float = 0.0) -> List[str]:
        """Retorna a cadeia completa de pré-requisitos, filtrando por confiança mínima."""
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
                edge_data = self.graph.get_edge_data(predecessor, node)
                if not edge_data:
                    continue
                for edge in edge_data.values():
                    if (edge.get('relacao') == 'PREREQUISITO_DE' and
                            edge.get('confidence', 1.0) >= min_confidence):
                        node_data = self.graph.nodes[predecessor]
                        if node_data.get('tipo') == 'disciplina':
                            chain.append(node_data.get('nome'))
                            dfs(predecessor, depth + 1)
                        break

        dfs(disc_id, 0)
        return chain

    def get_direct_prerequisites(self, disciplina: str) -> List[str]:
        """Retorna apenas os pré-requisitos DIRETOS (um salto) da disciplina."""
        disc_id = self._find_node(disciplina, "disciplina")
        if not disc_id:
            return []
        diretos = []
        for pred in self.graph.predecessors(disc_id):
            edge_data = self.graph.get_edge_data(pred, disc_id)
            if (self._has_edge_relation(edge_data, 'PREREQUISITO_DE')
                    and self.graph.nodes[pred].get('tipo') == 'disciplina'):
                nome = self.graph.nodes[pred].get('nome')
                if nome:
                    diretos.append(nome)
        return diretos

    def get_dependent_disciplines(self, disciplina: str) -> List[str]:
        """Disciplinas que dependem desta (esta é pré-requisito)."""
        disc_id = self._find_node(disciplina, "disciplina")
        if not disc_id:
            return []
        
        dependentes = []
        for successor in self.graph.successors(disc_id):
            edge_data = self.graph.get_edge_data(disc_id, successor)
            if self._has_edge_relation(edge_data, 'PREREQUISITO_DE'):
                dependentes.append(self.graph.nodes[successor].get('nome'))
        
        return dependentes
    
    def get_docentes_of_discipline(self, disciplina: str) -> List[str]:
        """Docentes de uma disciplina."""
        disc_id = self._find_node(disciplina, "disciplina")
        if not disc_id:
            return []
        
        docentes = []
        for p in self.graph.predecessors(disc_id):
            edges_data = self.graph.get_edge_data(p, disc_id)
            if edges_data:
                for edge_key, edge in edges_data.items():
                    if edge.get('relacao') == 'LECIONA':
                        docentes.append(self.graph.nodes[p].get('nome'))
                        break
        return docentes

    def get_disciplines_of_docente(self, docente: str) -> List[str]:
        """Disciplinas que um docente leciona."""
        docente_id = f"DOC:{docente}"
        
        if not self.graph.has_node(docente_id):
            docente_lower = docente.lower()
            for node in self.graph.nodes():
                if node.startswith("DOC:"):
                    node_name = node.replace("DOC:", "").lower()
                    if len(node_name) >= 3 and (docente_lower in node_name or node_name in docente_lower):
                        docente_id = node
                        break
            else:
                return []
        
        disciplinas = []
        for successor in self.graph.successors(docente_id):
            edges_data = self.graph.get_edge_data(docente_id, successor)
            if edges_data:
                for edge_key, edge in edges_data.items():
                    if edge.get('relacao') == 'LECIONA':
                        nome = self.graph.nodes[successor].get('nome')
                        if nome:
                            disciplinas.append(nome)
                        break
        
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
            edge_data = self.graph.get_edge_data(predecessor, orgao_id)
            if self._has_edge_relation(edge_data, 'MENCIONA'):
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
            edge_data = self.graph.get_edge_data(artigo_id, successor)
            if self._has_edge_relation(edge_data, 'REFERENCIA'):
                data = self.graph.nodes.get(successor, {})
                if data.get('tipo') == 'artigo':
                    relacionados.append({
                        'numero': data.get('numero'),
                        'documento': data.get('documento'),
                        'relacao': 'referenciado_por_este'
                    })
        
        for predecessor in self.graph.predecessors(artigo_id):
            edge_data = self.graph.get_edge_data(predecessor, artigo_id)
            if self._has_edge_relation(edge_data, 'REFERENCIA'):
                data = self.graph.nodes.get(predecessor, {})
                if data.get('tipo') == 'artigo':
                    relacionados.append({
                        'numero': data.get('numero'),
                        'documento': data.get('documento'),
                        'relacao': 'referencia_este'
                    })
        
        return relacionados

    def _find_node(self, termo: str, tipo: str = None) -> Optional[str]:
        """Encontra um nó por nome, código ou sigla usando índices O(1)."""
        termo_normalized = self._normalize_text(termo)
        
        node_id = (
            self._index_by_name.get(termo_normalized) or
            self._index_by_sigla.get(termo_normalized) or
            self._index_by_codigo.get(termo_normalized)
        )
        
        if node_id:
            if tipo is None or self.graph.nodes.get(node_id, {}).get('tipo') == tipo:
                return node_id
        
        for node, data in self.graph.nodes(data=True):
            if tipo and data.get('tipo') != tipo:
                continue
            
            nome = self._normalize_text(data.get('nome', ''))
            codigo = self._normalize_text(str(data.get('codigo', '')))
            sigla = self._normalize_text(data.get('sigla') or '')
            
            if termo_normalized in nome or (sigla and termo_normalized in sigla):
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

    def export_for_visualization(self) -> Dict:
        """
        Exporta o grafo em formato para visualização (vis-network, D3, etc.).
        Retorna: { "nodes": [ { id, label, tipo, ... } ], "edges": [ { from, to, label } ] }
        """
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            nome = data.get('nome', node_id)
            tipo = data.get('tipo', 'unknown')
            if tipo == 'curso' and isinstance(nome, str):
                sigla = (data.get('sigla') or "").strip()
                nome_curto = re.sub(r'^Bacharelado\s+em\s+', '', nome, flags=re.IGNORECASE).strip()
                nome_curto = re.sub(r'\s*\([A-Z]{2,5}\)\s*$', '', nome_curto).strip()
                label = f"{nome_curto} ({sigla})" if sigla else nome_curto or nome
                if len(label) > 50:
                    label = label[:47] + "..."
            elif isinstance(nome, str) and len(nome) > 60:
                label = nome[:57] + "..."
            else:
                label = nome or node_id.replace("DISC:", "").replace("DOC:", "").replace("CURSO:", "")
            nodes.append({
                "id": node_id,
                "label": label,
                "tipo": tipo,
                "titulo": nome,
            })
        edges = []
        for u, v, key, edge_data in self.graph.edges(keys=True, data=True):
            rel = edge_data.get('relacao', '')
            edges.append({
                "from": u,
                "to": v,
                "label": rel,
            })
        return {"nodes": nodes, "edges": edges}

    def get_disciplinas_do_termo(self, curso: str, termo: int) -> List[Dict]:
        """Retorna disciplinas de um termo específico de um curso."""
        resultados = []
        cursos_to_search = self._expand_curso_search(curso)
        
        for node, data in self.graph.nodes(data=True):
            if data.get('tipo') == 'matriz_curricular':
                nome = data.get('nome', '').lower()
                sigla = data.get('sigla', '').lower()
                
                match_found = False
                for curso_term in cursos_to_search:
                    if curso_term == sigla:
                        match_found = True
                        break
                    if len(curso_term) > 3:
                        if curso_term in nome or nome in curso_term:
                            match_found = True
                            break
                
                if match_found:
                    for successor in self.graph.successors(node):
                        edges_data = self.graph.get_edge_data(node, successor)
                        if edges_data:
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
        
        for node, data in self.graph.nodes(data=True):
            if data.get('tipo') == 'matriz_curricular':
                nome = data.get('nome', '').lower()
                sigla = data.get('sigla', '').lower()
                duracao = data.get('duracao_termos', '8')
                
                match_found = False
                for curso_term in cursos_to_search:
                    if curso_term == sigla:
                        match_found = True
                        break
                    if len(curso_term) > 3:
                        if curso_term in nome or nome in curso_term:
                            match_found = True
                            break
                
                if match_found:
                    for successor in self.graph.successors(node):
                        edges_data = self.graph.get_edge_data(node, successor)
                        if edges_data:
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
                
                match_found = False
                for curso_term in cursos_to_search:
                    if curso_term == sigla:
                        match_found = True
                        break
                    if len(curso_term) > 3:
                        if curso_term in nome or nome in curso_term:
                            match_found = True
                            break
                
                if match_found:
                    for successor in self.graph.successors(node):
                        edges_data = self.graph.get_edge_data(node, successor)
                        if edges_data:
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
                
                match_found = False
                for curso_term in cursos_to_search:
                    if curso_term == sigla:
                        match_found = True
                        break
                    if len(curso_term) > 3:
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
        'data mining': ['mineração de dados'],
        'mineração de dados': ['data mining'],
    }
    
    def _expand_area_search(self, area: str) -> List[str]:
        """Expande a busca de área incluindo sinônimos."""
        area_lower = area.lower().strip()
        areas_to_search = [area_lower]
        
        if area_lower in self.AREA_SYNONYMS:
            areas_to_search.extend(self.AREA_SYNONYMS[area_lower])
        
        return areas_to_search
    
    @staticmethod
    def _stem_words(words: Set[str]) -> Set[str]:
        """Singular/plural simples: 'redes complexas' ≈ 'rede complexa'."""
        return {w[:-1] if len(w) > 3 and w.endswith('s') else w for w in words}

    def get_docentes_by_area(self, area: str) -> List[str]:
        """Retorna docentes especialistas em uma área (com suporte a sinônimos)."""
        areas_to_search = self._expand_area_search(area)
        docentes = []

        for search_area in areas_to_search:
            area_normalized = self._normalize_text(search_area)
            area_words = set(area_normalized.split())

            for node, data in self.graph.nodes(data=True):
                if data.get('tipo') != 'area':
                    continue

                nome_area = self._normalize_text(data.get('nome', ''))
                nome_words = set(nome_area.split())

                is_match = False

                if area_normalized == nome_area:
                    is_match = True
                elif len(area_normalized) > 3 and (
                    area_words.issubset(nome_words)
                    or self._stem_words(area_words).issubset(self._stem_words(nome_words))
                ):
                    is_match = True
                elif len(area_normalized) > 5 and area_normalized in nome_area:
                    is_match = True
                
                if is_match:
                    for pred in self.graph.predecessors(node):
                        edge_data = self.graph.get_edge_data(pred, node)
                        if self._has_edge_relation(edge_data, 'ESPECIALISTA_EM'):
                            nome = self.graph.nodes[pred].get('nome')
                            if nome and nome not in docentes:
                                docentes.append(nome)
        
        return docentes
    
    def _find_docente_id(self, docente: str) -> Optional[str]:
        """Encontra o ID do docente por nome (com fuzzy search, preferindo nós com mais info)."""
        docente_lower = docente.lower().strip()
        docente_words = set(docente_lower.split())
        
        matches = []
        
        for node in self.graph.nodes():
            if not node.startswith("DOC:"):
                continue
            
            node_name = node.replace("DOC:", "").lower()
            node_words = set(node_name.split())
            data = self.graph.nodes[node]
            
            if node_name == docente_lower:
                matches.append((node, 100, data))
            elif docente_words.issubset(node_words):
                matches.append((node, 80, data))
            elif len(node_name) >= 3 and (docente_lower in node_name or node_name in docente_lower):
                matches.append((node, 50, data))
        
        if not matches:
            return None
        
        matches.sort(key=lambda x: (1 if x[2].get('email') else 0, x[1]), reverse=True)
        
        return matches[0][0]
    
    def get_areas_of_docente(self, docente: str) -> List[str]:
        """Retorna as áreas de especialização de um docente."""
        docente_id = self._find_docente_id(docente)
        if not docente_id:
            return []
        
        areas = []
        
        node_areas = self.graph.nodes[docente_id].get('areas', '')
        if node_areas:
            if isinstance(node_areas, list):
                areas.extend(node_areas)
            elif isinstance(node_areas, str):
                areas.extend([a.strip() for a in node_areas.split(',') if a.strip()])
        
        for successor in self.graph.successors(docente_id):
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


    def get_all_ancestors(self, disciplina: str, min_confidence: float = 0.0) -> List[str]:
        """
        Retorna TODOS os pré-requisitos transitivos via nx.ancestors().
        Suporta filtragem por confiança mínima da aresta.
        """
        disc_id = self._find_node(disciplina, "disciplina")
        if not disc_id:
            return []

        prereq_graph = nx.DiGraph()
        for u, v, data in self.graph.edges(data=True):
            if (data.get('relacao') == 'PREREQUISITO_DE' and
                    data.get('confidence', 1.0) >= min_confidence):
                prereq_graph.add_edge(u, v)

        if disc_id not in prereq_graph:
            return []

        ancestor_ids = nx.ancestors(prereq_graph, disc_id)
        result = []
        for anc_id in ancestor_ids:
            node_data = self.graph.nodes.get(anc_id, {})
            if node_data.get('tipo') == 'disciplina':
                nome = node_data.get('nome', anc_id.replace('DISC:', ''))
                result.append(nome)
        return result

    def verify_discipline_exists(self, nome: str) -> bool:
        """Verifica se uma disciplina existe no grafo (por nome, sigla ou código)."""
        return self._find_node(nome, "disciplina") is not None

    def verify_prerequisite(self, disc_a: str, disc_b: str) -> bool:
        """
        Verifica se disc_a é pré-requisito DIRETO de disc_b.
        Para verificar pré-requisito indireto use get_all_ancestors().
        """
        id_a = self._find_node(disc_a, "disciplina")
        id_b = self._find_node(disc_b, "disciplina")
        if not id_a or not id_b:
            return False
        edge_data = self.graph.get_edge_data(id_a, id_b)
        if not edge_data:
            return False
        return self._has_edge_relation(edge_data, 'PREREQUISITO_DE')

    def verify_docente_in_discipline(self, docente: str, disciplina: str) -> bool:
        """Verifica se um docente leciona uma disciplina (com base no KG)."""
        docentes = self.get_docentes_of_discipline(disciplina)
        docente_norm = self._normalize_text(docente)
        return any(
            docente_norm in self._normalize_text(d) or self._normalize_text(d) in docente_norm
            for d in docentes
        )

    def get_prerequisite_confidence(self, disc_a: str, disc_b: str) -> float:
        """Retorna a confiança da aresta PREREQUISITO_DE entre disc_a e disc_b."""
        id_a = self._find_node(disc_a, "disciplina")
        id_b = self._find_node(disc_b, "disciplina")
        if not id_a or not id_b:
            return 0.0
        edge_data = self.graph.get_edge_data(id_a, id_b)
        if not edge_data:
            return 0.0
        for edge in edge_data.values():
            if edge.get('relacao') == 'PREREQUISITO_DE':
                return edge.get('confidence', 1.0)
        return 0.0

    def get_unlocked_disciplines(self, completed: List[str]) -> List[str]:
        """
        Dado um conjunto de disciplinas já cursadas, retorna todas as disciplinas
        cujos pré-requisitos diretos estão inteiramente satisfeitos.
        """
        completed_ids = set()
        for disc in completed:
            node_id = self._find_node(disc, "disciplina")
            if node_id:
                completed_ids.add(node_id)

        if not completed_ids:
            return []

        unlocked = []
        for node_id, data in self.graph.nodes(data=True):
            if data.get('tipo') != 'disciplina' or node_id in completed_ids:
                continue

            direct_prereqs = [
                pred for pred in self.graph.predecessors(node_id)
                if (self._has_edge_relation(self.graph.get_edge_data(pred, node_id), 'PREREQUISITO_DE')
                    and self.graph.nodes[pred].get('tipo') == 'disciplina')
            ]

            if direct_prereqs and all(p in completed_ids for p in direct_prereqs):
                nome = data.get('nome')
                if nome:
                    unlocked.append(nome)

        return sorted(unlocked)

    def get_symbolic_facts(self, disciplina: str) -> Dict:
        """
        Retorna dicionário com todos os fatos estruturados do KG para uma disciplina.
        Usado pelo SymbolicValidator para enriquecimento e validação.
        """
        node_id = self._find_node(disciplina, "disciplina")
        if not node_id:
            return {}

        node_data = self.graph.nodes[node_id]
        prereqs_diretos = self.get_prerequisite_chain(disciplina, max_depth=1)
        todos_prereqs = self.get_all_ancestors(disciplina)
        docentes = self.get_docentes_of_discipline(disciplina)
        dependentes = self.get_dependent_disciplines(disciplina)

        return {
            'nome': node_data.get('nome', disciplina),
            'codigo': node_data.get('codigo', ''),
            'sigla': node_data.get('sigla', ''),
            'termo': node_data.get('termo', ''),
            'prerequisitos_diretos': prereqs_diretos,
            'prerequisitos_transitivos': todos_prereqs,
            'docentes': docentes,
            'dependentes': dependentes,
        }


class KGCompletion:
    """
    Knowledge Graph Completion leve para o domínio UNIFESP ICT.

    Inspirado em dois módulos do artigo "Enhancing KGC with GNN Distillation
    and Probabilistic Interaction Modeling" (Wang et al., 2025):

    1. **Assinatura estrutural** (GNN neighborhood aggregation sem pesos treináveis):
       Para cada disciplina, agrega características de vizinhos em 1-hop e 2-hop
       - pré-requisitos, docentes, dependentes, co-pré-requisitos.

    2. **Score de interação** (APIM simplificado):
       Jaccard ponderado entre assinaturas, com pesos diferentes por tipo de
       relação (análogo à matriz de transição Pr do APIM).

    Com isso é possível:
    - Encontrar disciplinas estruturalmente similares (sem match exato de nome)
    - Inferir arestas prováveis ausentes (KGC propriamente dito)
    - Enriquecer contexto dos agentes com relações latentes
    """

    _RELATION_WEIGHTS: Dict[str, float] = {
        "prereqs_1":   0.35,
        "docentes":    0.30,
        "dependents":  0.20,
        "co_prereqs":  0.10,
        "prereqs_2":   0.05,
    }

    def __init__(self, kg: "KnowledgeGraph"):
        self.kg = kg
        self._cache: Dict[str, Dict[str, Set[str]]] = {}

    def invalidate_cache(self) -> None:
        self._cache.clear()
        self._rec_cache = {}
        self._rec_doc_vecs = None
        self._depth_cache = {}


    def _signature(self, discipline: str) -> Dict[str, Set[str]]:
        """Agrega vizinhança em até 2 hops - equivalente a 2 camadas de MPNN."""
        norm = self.kg._normalize_text(discipline)
        if norm in self._cache:
            return self._cache[norm]

        prereqs_1: Set[str] = set(self.kg.get_prerequisite_chain(discipline, max_depth=1))
        docentes: Set[str]   = set(self.kg.get_docentes_of_discipline(discipline))
        dependents: Set[str] = set(self.kg.get_dependent_disciplines(discipline))

        co_prereqs: Set[str] = set()
        for dep in dependents:
            co_prereqs.update(self.kg.get_prerequisite_chain(dep, max_depth=1))
        co_prereqs -= prereqs_1
        co_prereqs.discard(discipline)

        prereqs_2: Set[str] = set()
        for p in prereqs_1:
            prereqs_2.update(self.kg.get_prerequisite_chain(p, max_depth=1))
        prereqs_2 -= prereqs_1
        prereqs_2.discard(discipline)

        sig = {
            "prereqs_1":  prereqs_1,
            "docentes":   docentes,
            "dependents": dependents,
            "co_prereqs": co_prereqs,
            "prereqs_2":  prereqs_2,
        }
        self._cache[norm] = sig
        return sig


    def structural_similarity(self, disc_a: str, disc_b: str) -> float:
        """
        Score de interação entre duas disciplinas.
        Análogo a f(h, r, t) = ã_h^T · Pr · ã_t do APIM, porém calculado
        como Jaccard ponderado entre assinaturas estruturais.
        """
        sig_a = self._signature(disc_a)
        sig_b = self._signature(disc_b)

        total = 0.0
        denom = 0.0
        for key, w in self._RELATION_WEIGHTS.items():
            a, b = sig_a[key], sig_b[key]
            union = a | b
            if union:
                total += w * (len(a & b) / len(union))
                denom += w

        return total / denom if denom > 0 else 0.0


    def _name_similarity(self, query: str, candidate: str) -> float:
        """Token Jaccard similarity between normalized names (fallback for unknown disciplines)."""
        _STOPWORDS = {"de", "da", "do", "das", "dos", "e", "em", "com", "para", "um", "uma"}
        def tokens(s: str) -> Set[str]:
            return {t for t in self.kg._normalize_text(s).split() if t not in _STOPWORDS and len(t) > 2}
        a, b = tokens(query), tokens(candidate)
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    def find_similar(
        self,
        discipline: str,
        n: int = 5,
        threshold: float = 0.08,
    ) -> List[Tuple[str, float]]:
        """Retorna as n disciplinas estruturalmente mais similares a `discipline`.

        Se a disciplina não existe no KG, usa similaridade por nome (token Jaccard)
        como fallback - útil para sugerir disciplinas reais para termos mal grafados
        ou que não constam na base.
        """
        norm_discipline = self.kg._normalize_text(discipline)
        candidates = [
            data.get("nome", nid)
            for nid, data in self.kg.graph.nodes(data=True)
            if data.get("tipo") == "disciplina"
            and data.get("nome") != discipline
            and self.kg._normalize_text(data.get("nome", "")) != norm_discipline
        ]

        in_kg = self.kg._find_node(discipline, "disciplina") is not None

        semantic = self._semantic_scores(discipline, candidates)

        scores: List[Tuple[str, float]] = []
        for other in candidates:
            try:
                if in_kg:
                    sim = self.structural_similarity(discipline, other)
                else:
                    sim = self._name_similarity(discipline, other)
                if other in semantic:
                    sim = 0.6 * sim + 0.4 * semantic[other]
                if sim >= threshold:
                    scores.append((other, sim))
            except Exception:
                continue

        return sorted(scores, key=lambda x: -x[1])[:n]


    def set_embeddings(self, model) -> None:
        """Injeta o modelo de embeddings (chamado no sync, quando existe)."""
        self._emb_model = model
        self._emb_names: List[str] = []
        self._emb_vecs: List[List[float]] = []

    def _semantic_scores(self, discipline: str, candidates: List[str]) -> Dict[str, float]:
        """Cosseno entre o termo e os nomes das candidatas (cache lazy dos vetores)."""
        model = getattr(self, "_emb_model", None)
        if model is None:
            return {}
        import math
        try:
            if not getattr(self, "_emb_names", None):
                self._emb_names = candidates
                self._emb_vecs = model.embed_documents(candidates)
            qv = model.embed_query(discipline)

            def _cos(a, b):
                num = sum(x * y for x, y in zip(a, b))
                na = math.sqrt(sum(x * x for x in a))
                nb = math.sqrt(sum(y * y for y in b))
                return num / (na * nb) if na and nb else 0.0

            return {
                nome: _cos(qv, vec)
                for nome, vec in zip(self._emb_names, self._emb_vecs)
            }
        except Exception:
            return {}


    REC_BEFORE_THRESHOLD: float = 0.65

    def _termo_ordem(self, node_data: dict) -> Optional[int]:
        """Parse do atributo `termo` do nó ("4", "4º", None...) → int ou None."""
        termo = node_data.get("termo")
        if termo is None:
            return None
        m = re.search(r'\d+', str(termo))
        return int(m.group()) if m else None

    def _dag_depth(self, nome: str) -> int:
        """Profundidade no DAG de pré-requisitos (maior cadeia de ancestrais)."""
        cache = getattr(self, "_depth_cache", None)
        if cache is None:
            cache = self._depth_cache = {}
        norm = self.kg._normalize_text(nome)
        if norm in cache:
            return cache[norm]
        cache[norm] = 0
        prereqs = self.kg.get_prerequisite_chain(nome, max_depth=1)
        depth = 1 + max((self._dag_depth(p) for p in prereqs), default=-1)
        cache[norm] = depth
        return depth

    def _ordem_pair(self, data_a: dict, data_b: dict) -> Tuple[float, float]:
        """
        ordem() dos dois lados na MESMA escala: termo da matriz quando ambos
        os nós têm o atributo; senão profundidade no DAG de pré-requisitos.
        """
        ta, tb = self._termo_ordem(data_a), self._termo_ordem(data_b)
        if ta is not None and tb is not None:
            return float(ta), float(tb)
        return (
            float(self._dag_depth(data_a.get("nome", ""))),
            float(self._dag_depth(data_b.get("nome", ""))),
        )

    def _doc_text(self, data: dict) -> str:
        """Documento de embedding da disciplina: NOME + EMENTA (quando existe)."""
        nome = data.get("nome", "")
        ementa = (data.get("ementa") or "").strip()
        return f"{nome}. {ementa}" if ementa else nome

    def _doc_vectors(self) -> Dict[str, List[float]]:
        """
        Vetores de NOME+EMENTA de todas as disciplinas autoritativas do KG
        (cache lazy: UMA chamada batch de embeddings na primeira consulta -
        nunca o produto cartesiano de pares no build).
        """
        model = getattr(self, "_emb_model", None)
        if model is None:
            return {}
        vecs = getattr(self, "_rec_doc_vecs", None)
        if vecs is not None:
            return vecs
        try:
            entries: List[Tuple[str, str]] = []
            seen: Set[str] = set()
            for _, data in self.kg.graph.nodes(data=True):
                if data.get("tipo") != "disciplina":
                    continue
                nome = data.get("nome", "")
                norm = self.kg._normalize_text(nome)
                if not norm or norm in seen:
                    continue
                seen.add(norm)
                entries.append((norm, self._doc_text(data)))
            vectors = model.embed_documents([doc for _, doc in entries])
            self._rec_doc_vecs = {
                norm: vec for (norm, _), vec in zip(entries, vectors)
            }
        except Exception:
            return {}
        return self._rec_doc_vecs

    def _descendants_norm(self, nome: str) -> Set[str]:
        """Fecho transitivo dos dependentes (normalizado) - ancestral(nome, ·)."""
        result: Set[str] = set()
        queue = [nome]
        while queue:
            atual = queue.pop()
            for dep in self.kg.get_dependent_disciplines(atual):
                dn = self.kg._normalize_text(dep)
                if dn not in result:
                    result.add(dn)
                    queue.append(dep)
        return result

    def get_recommended_before(
        self,
        discipline: str,
        n: int = 3,
        threshold: Optional[float] = None,
    ) -> List[Tuple[str, float]]:
        """
        Disciplinas RECOMENDADAS ANTES de `discipline` (não pré-requisitos):
        conteúdo (ementa) fortemente sobreposto, fora da cadeia do DAG, e que
        vêm antes na ordem do currículo. Confiança da aresta = similaridade
        (sempre < 1.0 → renderizada tracejada no grafo do chat).

        Sem embeddings injetados (set_embeddings) retorna [] (graceful).
        """
        model = getattr(self, "_emb_model", None)
        if model is None:
            return []
        th = self.REC_BEFORE_THRESHOLD if threshold is None else threshold

        target_id = self.kg._find_node(discipline, "disciplina")
        if not target_id:
            return []
        data_b = self.kg.graph.nodes[target_id]
        nome_b = data_b.get("nome", discipline)
        norm_b = self.kg._normalize_text(nome_b)

        cache = getattr(self, "_rec_cache", None)
        if cache is None:
            cache = self._rec_cache = {}
        cache_key = (norm_b, th)
        if cache_key in cache:
            return cache[cache_key][:n]

        vecs = self._doc_vectors()
        vec_b = vecs.get(norm_b)
        if vec_b is None:
            return []

        import math

        def _cos(a, b):
            num = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(y * y for y in b))
            return num / (na * nb) if na and nb else 0.0

        ancestors_b = {
            self.kg._normalize_text(a) for a in self.kg.get_all_ancestors(nome_b)
        }
        descendants_b = self._descendants_norm(nome_b)

        results: List[Tuple[str, float]] = []
        vistos: Set[str] = set()
        for _, data_a in self.kg.graph.nodes(data=True):
            if data_a.get("tipo") != "disciplina":
                continue
            nome_a = data_a.get("nome", "")
            norm_a = self.kg._normalize_text(nome_a)
            if not norm_a or norm_a == norm_b or norm_a in vistos:
                continue
            vistos.add(norm_a)
            if norm_a in ancestors_b or norm_a in descendants_b:
                continue
            vec_a = vecs.get(norm_a)
            if vec_a is None:
                continue
            sim = _cos(vec_a, vec_b)
            if sim < th:
                continue
            ordem_a, ordem_b = self._ordem_pair(data_a, data_b)
            if ordem_a >= ordem_b:
                continue
            results.append((nome_a, round(min(sim, 0.99), 4)))

        results.sort(key=lambda x: -x[1])
        cache[cache_key] = results
        return results[:n]


    def predict_missing_prerequisites(
        self,
        discipline: str,
        threshold: float = 0.6,
        top_k: int = 5,
    ) -> List[Tuple[str, float]]:
        """
        Prediz pré-requisitos prováveis ausentes.
        Estratégia: disciplinas similares que têm pré-req X em comum → X é
        candidato para `discipline` também.
        Score = proporção de similares que possuem o candidato como pré-req.
        """
        known_prereqs_norm = {
            self.kg._normalize_text(p)
            for p in self.kg.get_all_ancestors(discipline)
        }
        similar = self.find_similar(discipline, n=10, threshold=0.08)
        if not similar:
            return []

        counts: Dict[str, int] = {}
        for (sim_disc, _) in similar:
            for p in self.kg.get_prerequisite_chain(sim_disc, max_depth=1):
                pn = self.kg._normalize_text(p)
                if pn not in known_prereqs_norm and pn != self.kg._normalize_text(discipline):
                    counts[p] = counts.get(p, 0) + 1

        scored = [
            (disc, count / len(similar))
            for disc, count in counts.items()
            if count / len(similar) >= threshold
        ]
        return sorted(scored, key=lambda x: -x[1])[:top_k]


    def get_enrichment_block(self, discipline: str, max_similar: int = 3) -> str:
        """
        Gera bloco de contexto com insights de KGC para uso nos prompts.
        Inclui disciplinas estruturalmente similares e pré-requisitos inferidos.
        """
        similar = self.find_similar(discipline, n=max_similar, threshold=0.1)
        if not similar:
            return ""

        lines = [f"[KGC - Relações Estruturais Inferidas para {discipline}]"]

        sim_parts = []
        for (disc, score) in similar:
            prereqs = self.kg.get_prerequisite_chain(disc, max_depth=1)
            docentes = self.kg.get_docentes_of_discipline(disc)
            tags = []
            if prereqs:
                tags.append(f"pré-req: {', '.join(prereqs[:2])}")
            if docentes:
                tags.append(f"docentes: {', '.join(docentes[:2])}")
            tag_str = f" [{'; '.join(tags)}]" if tags else ""
            sim_parts.append(f"{disc} (sim={score:.0%}){tag_str}")
        lines.append("  • Similares: " + " | ".join(sim_parts))

        inferred = self.predict_missing_prerequisites(discipline, threshold=0.5, top_k=3)
        if inferred:
            inf_strs = [f"{p} ({s:.0%} confiança)" for p, s in inferred]
            lines.append("  • Pré-requisitos prováveis não cadastrados: " + ", ".join(inf_strs))

        return "\n".join(lines)
