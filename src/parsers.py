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
        docs.extend(RegimentoParser._parse_tipos_atividades(data, base_meta))
        docs.extend(RegimentoParser._parse_eixos_ac(data, base_meta))
        docs.extend(RegimentoParser._parse_fluxo_processo(data, base_meta))
        docs.extend(RegimentoParser._parse_resumo_executivo(data, base_meta))
        
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


    @staticmethod
    def _parse_tipos_atividades(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        if 'tipos_atividades' in data:
            for sigla, info in data['tipos_atividades'].items():
                txt = f"Tipo de Atividade: {sigla} - {info.get('nome_completo', '')}\n"
                txt += f"Carater: {info.get('carater', 'N/A')}\n"
                txt += f"Carga Horaria Minima: {info.get('carga_horaria_minima', 'N/A')}\n"
                if info.get('carga_horaria_maxima'):
                    txt += f"Carga Horaria Maxima: {info['carga_horaria_maxima']}\n"
                txt += f"Descricao: {info.get('descricao', 'N/A')}"
                if info.get('unidades_curriculares'):
                    txt += "\nUnidades Curriculares:\n" + "\n".join(f"- {uc}" for uc in info['unidades_curriculares'])
                docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': f'tipo_atividade_{sigla}'}))
        return docs
    
    @staticmethod
    def _parse_eixos_ac(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        artigos = data.get('artigos', {})
        artigo_3 = artigos.get('artigo_3', {})
        eixos = artigo_3.get('eixos', {})
        
        if eixos:
            for eixo_key, eixo_info in eixos.items():
                nome = eixo_info.get('nome', eixo_key)
                txt = f"EIXO DE ATIVIDADES COMPLEMENTARES: {nome}\n"
                txt += f"Limite de Horas: {eixo_info.get('limite_horas', 'Nao especificado')}\n"
                
                atividades = eixo_info.get('atividades_aceitas', [])
                if atividades:
                    txt += "\nAtividades Aceitas:\n"
                    for atv in atividades:
                        txt += f"- {atv.get('tipo', '')}: {atv.get('descricao', '')}\n"
                
                docs.append(Document(page_content=txt.strip(), metadata={**base_meta, 'secao': f'eixo_ac_{eixo_key}'}))
        
        requisito = artigo_3.get('requisito_geral', {})
        if requisito:
            txt = f"Requisito Geral para Atividades Complementares:\n{requisito.get('conteudo', '')}\nMinimo por Eixo: {requisito.get('minimo_por_eixo', 'N/A')}"
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'requisito_eixos'}))
        
        return docs
    
    @staticmethod
    def _parse_fluxo_processo(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        fluxo = data.get('fluxo_processo', {})
        etapas = fluxo.get('etapas', [])
        
        if etapas:
            txt = "Fluxo do Processo de Acreditacao de Atividades Complementares:\n\n"
            for etapa in etapas:
                txt += f"{etapa.get('ordem', '')}. {etapa.get('responsavel', '')}: {etapa.get('acao', '')}\n"
            docs.append(Document(page_content=txt.strip(), metadata={**base_meta, 'secao': 'fluxo_processo'}))
        
        return docs
    
    @staticmethod
    def _parse_resumo_executivo(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        resumo = data.get('resumo_executivo', {})
        
        ac = resumo.get('atividades_complementares_AC', {})
        if ac:
            txt = "RESUMO - Atividades Complementares (AC):\n"
            txt += f"Carater: {ac.get('carater', 'N/A')}\n"
            txt += f"Carga Horaria Total Obrigatoria: {ac.get('carga_horaria_total', 'N/A')}\n"
            txt += f"Quantidade de Eixos: {ac.get('quantidade_eixos', 'N/A')}\n"
            txt += f"Minimo por Eixo: {ac.get('requisito_minimo_por_eixo', 'N/A')}\n"
            txt += f"Limite Eixo 1 (Formacao Cidada): {ac.get('limite_eixo_1', 'N/A')}\n"
            txt += f"Consequencia se nao cumprir: {ac.get('consequencia_nao_cumprimento', 'N/A')}"
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'resumo_ac'}))
        
        ace = resumo.get('atividades_complementares_extensionistas_ACE', {})
        if ace:
            txt = "RESUMO - Atividades Complementares Extensionistas (ACE):\n"
            txt += f"Carater: {ace.get('carater', 'N/A')}\n"
            txt += f"Carga Horaria Minima: {ace.get('carga_horaria_minima', 'N/A')}\n"
            txt += f"Carga Horaria Maxima: {ace.get('carga_horaria_maxima', 'N/A')}\n"
            txt += f"Lancamento: {ace.get('lancamento', 'N/A')}\n"
            txt += f"Comprovacao: {ace.get('comprovacao', 'N/A')}"
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'resumo_ace'}))
        
        return docs


def parse_file(filepath: str) -> List[Document]:
    if 'disciplinas' in filepath:
        return DisciplinaParser.parse(filepath)
    elif 'regimentos' in filepath:
        # Detectar se é o Projeto Pedagógico do BCC
        if 'projeto_pedagogico_bcc' in filepath:
            return ProjetoPedagogicoBCCParser.parse(filepath)
        return RegimentoParser.parse(filepath)
    return []



class ProjetoPedagogicoBCCParser:
    """Parser dedicado para o Projeto Pedagógico do Curso de Ciência da Computação"""
    
    @staticmethod
    def parse(filepath: str) -> List[Document]:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        docs = []
        doc_info = data.get('documento', {})
        
        base_meta = {
            'tipo_documento': 'projeto_pedagogico',
            'curso': doc_info.get('curso', 'BCC'),
            'campus': doc_info.get('campus', 'São José dos Campos'),
            'ano': doc_info.get('ano_reformulacao', 2023),
            'source': filepath
        }
        
        # Info geral do documento
        docs.extend(ProjetoPedagogicoBCCParser._parse_dados_curso(data, base_meta))
        docs.extend(ProjetoPedagogicoBCCParser._parse_historico(data, base_meta))
        docs.extend(ProjetoPedagogicoBCCParser._parse_perfil_curso(data, base_meta))
        docs.extend(ProjetoPedagogicoBCCParser._parse_objetivos(data, base_meta))
        docs.extend(ProjetoPedagogicoBCCParser._parse_perfil_egresso(data, base_meta))
        docs.extend(ProjetoPedagogicoBCCParser._parse_organizacao_curricular(data, base_meta))
        docs.extend(ProjetoPedagogicoBCCParser._parse_matriz_curricular(data, base_meta))
        docs.extend(ProjetoPedagogicoBCCParser._parse_ementas(data, base_meta))
        docs.extend(ProjetoPedagogicoBCCParser._parse_atividades_complementares(data, base_meta))
        docs.extend(ProjetoPedagogicoBCCParser._parse_tcc(data, base_meta))
        docs.extend(ProjetoPedagogicoBCCParser._parse_estagio(data, base_meta))
        docs.extend(ProjetoPedagogicoBCCParser._parse_infraestrutura(data, base_meta))
        docs.extend(ProjetoPedagogicoBCCParser._parse_apoio_discente(data, base_meta))
        
        return docs
    
    @staticmethod
    def _parse_dados_curso(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        dc = data.get('dados_curso', {})
        if dc:
            txt = f"""DADOS DO CURSO - Bacharelado em Ciência da Computação (BCC)
Grau: {dc.get('grau', 'Bacharelado')}
Código: {dc.get('codigo_curso', 'BCC')}
Vagas: {dc.get('vagas_totais', 50)} vagas
Turno: {dc.get('turno', 'Integral')}
Carga Horária Total: {dc.get('carga_horaria_total', 3204)} horas
Regime: {dc.get('regime', 'Semestral')}
Forma de Ingresso: {dc.get('forma_ingresso', 'Progressão Pós BCT')}
Tempo de Integralização: Mínimo {dc.get('tempo_integralizacao', {}).get('minimo', '8 semestres')}
Endereço: {dc.get('endereco', 'Parque Tecnológico SJC')}"""
            
            aval = dc.get('avaliacoes', {})
            if aval:
                txt += f"\n\nAVALIAÇÕES DO CURSO:\n- CPC 2017: {aval.get('cpc_2017', 'N/A')}\n- CC 2012: {aval.get('cc_2012', 'N/A')}\n- ENADE 2021: {aval.get('enade_2021', 'N/A')}"
            
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'dados_curso'}))
        
        di = data.get('dados_institucionais', {})
        if di:
            txt = f"""DADOS INSTITUCIONAIS - UNIFESP
Mantenedora: {di.get('mantenedora', 'UNIFESP')}
Lei de Criação: {di.get('lei_criacao', 'N/A')}
Missão: {di.get('missao', 'N/A')}
Número de Campi: {di.get('campi', 7)}
Regiões de Atuação: {', '.join(di.get('regioes_atuacao', []))}"""
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'dados_institucionais'}))
        
        return docs
    
    @staticmethod
    def _parse_historico(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        hist = data.get('historico', {})
        
        univ = hist.get('universidade', {})
        if univ:
            txt = f"""HISTÓRICO DA UNIFESP
Origem: {univ.get('origem', 'Escola Paulista de Medicina')}
Fundação EPM: {univ.get('fundacao_epm', '1933')}
Transformação em UNIFESP: {univ.get('transformacao_unifesp', 1994)}
Expansão REUNI: {univ.get('expansao_reuni', 2005)}
{univ.get('descricao', '')}"""
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'historico_unifesp'}))
        
        sjc = hist.get('campus_sjc', {})
        if sjc:
            txt = f"""HISTÓRICO DO CAMPUS SÃO JOSÉ DOS CAMPOS
Início das Atividades: {sjc.get('inicio_atividades', 2007)}
Instituto: {sjc.get('instituto', 'ICT')}

Cursos de Graduação:
{chr(10).join('- ' + c for c in sjc.get('cursos_graduacao', []))}

Programas de Pós-Graduação:
{chr(10).join('- ' + p for p in sjc.get('programas_pos_graduacao', []))}"""
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'historico_campus'}))
        
        bcc = hist.get('curso_bcc', {})
        if bcc:
            txt = f"""HISTÓRICO DO CURSO DE CIÊNCIA DA COMPUTAÇÃO
Primeiro Curso do Campus: {bcc.get('primeiro_curso_campus', True)}
Início do Planejamento: {bcc.get('inicio_planejamento', 2005)}
Primeira Turma: {bcc.get('primeira_turma', 2007)}
Corpo Docente Atual: {bcc.get('corpo_docente_atual', '~25 professores')}
Vínculo Pós-Graduação: {bcc.get('vinculo_pos_graduacao', '~80% ligados ao PPGCC')}"""
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'historico_bcc'}))
        
        return docs
    
    @staticmethod
    def _parse_perfil_curso(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        pc = data.get('perfil_curso', {})
        
        if pc:
            txt = f"""PERFIL DO CURSO DE CIÊNCIA DA COMPUTAÇÃO
Caracterização: {pc.get('caracterizacao', 'N/A')}
Adequação às Diretrizes: {pc.get('adequacao_diretrizes', 'Resolução nº 5/2016 MEC')}
Essência Profissional: {pc.get('essencia_profissional', 'Resolver problemas com computação')}

Características Desejadas do Aluno:
{chr(10).join('- ' + c for c in pc.get('caracteristicas_desejadas', []))}"""
            
            dif = pc.get('diferenciais', {})
            if dif:
                txt += f"""

DIFERENCIAIS DO CURSO:
- Organização Interdisciplinar: {dif.get('organizacao_interdisciplinar', 'N/A')}
- Formação Extensionista: {dif.get('formacao_extensionista', 'N/A')}
- Localização: {dif.get('localizacao_parque_tecnologico', 'Parque Tecnológico SJC')}"""
            
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'perfil_curso'}))
        
        ctx = pc.get('contexto_regional', {})
        if ctx:
            txt = f"""CONTEXTO REGIONAL - SÃO JOSÉ DOS CAMPOS
Região: {ctx.get('regiao', 'Vale do Paraíba')}
Principais Cidades: {', '.join(ctx.get('principais_cidades', []))}
População SJC (2017): {ctx.get('sjc_populacao_2017', 'N/A')}
Ranking Estadual: {ctx.get('sjc_ranking_populacao', {}).get('estado_sp', 'N/A')}

EMPRESAS NA REGIÃO:
{chr(10).join('- ' + e for e in ctx.get('empresas_principais', []))}

INSTITUIÇÕES DE PESQUISA:
{chr(10).join('- ' + i for i in ctx.get('instituicoes_pesquisa', []))}

Caracterização: {ctx.get('caracterizacao_polo', 'Polo tecnológico')}"""
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'contexto_regional'}))
        
        return docs
    
    @staticmethod
    def _parse_objetivos(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        obj = data.get('objetivos', {})
        
        if obj:
            txt = f"""OBJETIVOS DO CURSO DE CIÊNCIA DA COMPUTAÇÃO

OBJETIVO GERAL:
{obj.get('geral', 'N/A')}

OBJETIVOS ESPECÍFICOS:
{chr(10).join(f'{i+1}. {o}' for i, o in enumerate(obj.get('especificos', [])))}

SUBÁREAS DE FORMAÇÃO:
{chr(10).join('- ' + s for s in obj.get('subareas_formacao', []))}"""
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'objetivos'}))
        
        return docs
    
    @staticmethod
    def _parse_perfil_egresso(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        pe = data.get('perfil_egresso', {})
        
        if pe:
            txt = f"""PERFIL DO EGRESSO - CIÊNCIA DA COMPUTAÇÃO

ÁREAS DE ATUAÇÃO:
{chr(10).join('- ' + a for a in pe.get('areas_atuacao', []))}"""
            
            ca = pe.get('carreira_academica', {})
            if ca:
                txt += f"""

CARREIRA ACADÊMICA:
Possibilidades: {', '.join(ca.get('possibilidades', []))}
Áreas de Atuação: {', '.join(ca.get('atuacao', []))}

Contribuições Potenciais:
{chr(10).join('- ' + c for c in ca.get('contribuicoes_potenciais', []))}"""
            
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'perfil_egresso'}))
        
        # Competências técnicas em documento separado
        comps = pe.get('competencias_tecnicas', [])
        if comps:
            txt = "COMPETÊNCIAS TÉCNICAS DO EGRESSO - CIÊNCIA DA COMPUTAÇÃO:\n\n"
            for c in comps:
                txt += f"{c.get('id', '')}. {c.get('descricao', '')}\n"
            docs.append(Document(page_content=txt.strip(), metadata={**base_meta, 'secao': 'competencias_tecnicas'}))
        
        # Habilidades gerais
        habs = pe.get('habilidades_gerais', [])
        if habs:
            txt = "HABILIDADES GERAIS DO EGRESSO - CIÊNCIA DA COMPUTAÇÃO:\n\n"
            txt += "\n".join(f"- {h}" for h in habs)
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'habilidades_gerais'}))
        
        return docs
    
    @staticmethod
    def _parse_organizacao_curricular(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        oc = data.get('organizacao_curricular', {})
        
        nucleos = oc.get('nucleos', [])
        for nucleo in nucleos:
            nome = nucleo.get('nome', 'Núcleo')
            txt = f"""NÚCLEO CURRICULAR: {nome}
Tipo: {nucleo.get('tipo', 'N/A')}
Carga Horária Mínima: {nucleo.get('carga_horaria_minima', 'N/A')} horas

Unidades Curriculares:
{chr(10).join('- ' + uc for uc in nucleo.get('unidades_curriculares', []))}"""
            
            grupos = nucleo.get('grupos', [])
            for grupo in grupos:
                txt += f"""

GRUPO {grupo.get('grupo', '')}: {grupo.get('nome', '')}
Carga Horária Mínima: {grupo.get('carga_horaria_minima', 'N/A')}h
Exemplos:
{chr(10).join('- ' + ex for ex in grupo.get('exemplos', [])[:5])}..."""
            
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': f'nucleo_{nome[:20]}'}))
        
        tcc = oc.get('trabalhos_conclusao_curso', {})
        if tcc:
            txt = f"""TRABALHO DE CONCLUSÃO DE CURSO (TCC):
Carga Horária Total: {tcc.get('carga_horaria_total', 144)}h
TCC I: {tcc.get('tcc_i', 72)}h
TCC II: {tcc.get('tcc_ii', 72)}h"""
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'tcc_resumo'}))
        
        ext = oc.get('curricularizacao_extensao', {})
        if ext:
            txt = f"""CURRICULARIZAÇÃO DA EXTENSÃO - BCC:
Exigência Mínima: {ext.get('exigencia_minima', '10% - 321h')}
Base Legal: {', '.join(ext.get('base_legal', []))}"""
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'extensao_resumo'}))
        
        return docs
    
    @staticmethod
    def _parse_matriz_curricular(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        mc = data.get('matriz_curricular', {})
        
        semestres = mc.get('semestres', [])
        for sem in semestres:
            termo = sem.get('termo', 'N/A')
            txt = f"MATRIZ CURRICULAR - {termo}º TERMO/SEMESTRE\n\n"
            
            for disc in sem.get('disciplinas', []):
                nome = disc.get('nome', 'N/A')
                creditos = disc.get('creditos', 'N/A')
                ch = disc.get('carga_horaria', 'N/A')
                tipo = disc.get('tipo', 'N/A')
                prereq = disc.get('pre_requisitos', [])
                
                txt += f"- {nome}\n"
                txt += f"  Créditos: {creditos} | CH: {ch}h | Tipo: {tipo}\n"
                if prereq:
                    txt += f"  Pré-requisitos: {', '.join(prereq)}\n"
                txt += "\n"
            
            txt += f"Total de Créditos no Termo: {sem.get('total_creditos', 'N/A')}"
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': f'matriz_termo_{termo}', 'termo': termo}))
        
        resumo = mc.get('quadro_resumo', {})
        if resumo:
            txt = f"""RESUMO DA MATRIZ CURRICULAR - BCC:
UCs Fixas: {resumo.get('ucs_fixas', 'N/A')}h
TCC: {resumo.get('tcc', 'N/A')}h
Atividades Complementares: {resumo.get('atividades_complementares', 'N/A')}h
UCs Eletivas: {resumo.get('ucs_eletivas', 'N/A')}h
CARGA HORÁRIA TOTAL: {resumo.get('carga_horaria_total', 'N/A')}h"""
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'matriz_resumo'}))
        
        return docs
    
    @staticmethod
    def _parse_ementas(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        ementas = data.get('ementas_disciplinas_fixas', {})
        
        for semestre_key, disciplinas in ementas.items():
            for disc in disciplinas:
                codigo = disc.get('codigo', 'N/A')
                nome = disc.get('nome', 'N/A')
                termo = disc.get('termo', 'N/A')
                
                txt = f"""EMENTA - {nome} (Código: {codigo})
Termo: {termo}º semestre
Carga Horária: {disc.get('carga_horaria_total', 'N/A')}h (Teórica: {disc.get('carga_horaria_teorica', 0)}h, Prática: {disc.get('carga_horaria_pratica', 0)}h, Extensão: {disc.get('carga_horaria_extensao', 0)}h)
Pré-requisitos: {disc.get('pre_requisitos', 'Não há')}

EMENTA:
{disc.get('ementa', 'N/A')}

BIBLIOGRAFIA BÁSICA:"""
                
                biblio = disc.get('bibliografia_basica', [])
                if isinstance(biblio, list):
                    for i, b in enumerate(biblio, 1):
                        txt += f"\n{i}. {b}"
                
                docs.append(Document(page_content=txt, metadata={
                    **base_meta,
                    'secao': 'ementa',
                    'disciplina': nome,
                    'codigo': codigo,
                    'termo': termo
                }))
        
        return docs
    
    @staticmethod
    def _parse_atividades_complementares(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        ac = data.get('atividades_complementares', {})
        
        if ac:
            txt = f"""ATIVIDADES COMPLEMENTARES - BCC

Objetivo: {ac.get('objetivo', 'N/A')}
Obrigatoriedade: {ac.get('obrigatoredade', 'Sim')}
Carga Horária Total: {ac.get('carga_horaria_total', 144)}h
Momento de Realização: {ac.get('momento_realizacao', 'Qualquer momento do curso')}

TIPOS DE ATIVIDADES ACEITAS:
{chr(10).join('- ' + t for t in ac.get('tipos_atividades', []))}

Validação: {ac.get('validacao', {}).get('procedimento', 'Entrega de documentos comprobatórios')}"""
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'atividades_complementares'}))
        
        return docs
    
    @staticmethod
    def _parse_tcc(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        tcc = data.get('trabalho_conclusao_curso', {})
        
        if tcc:
            txt = f"""TRABALHO DE CONCLUSÃO DE CURSO (TCC) - BCC

Objetivo: {tcc.get('objetivo', 'N/A')}
Realização: {tcc.get('caracteristicas', {}).get('realizacao', 'Individual')}

Estrutura:
- TCC I: {tcc.get('estrutura', {}).get('tcc_i', {}).get('carga_horaria', 72)}h (7º semestre)
- TCC II: {tcc.get('estrutura', {}).get('tcc_ii', {}).get('carga_horaria', 72)}h (8º semestre)
- Total: {tcc.get('estrutura', {}).get('total_horas', 144)}h

Capacitação Desenvolvida:
{chr(10).join('- ' + c for c in tcc.get('caracteristicas', {}).get('capacitacao', []))}

RESPONSABILIDADES DO ALUNO:
{chr(10).join('- ' + r for r in tcc.get('responsabilidades_aluno', []))}"""
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'tcc'}))
        
        return docs
    
    @staticmethod
    def _parse_estagio(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        est = data.get('estagio_curricular', {})
        
        if est:
            req = est.get('requisitos_aluno', {})
            txt = f"""ESTÁGIO CURRICULAR - BCC

Caracterização: {est.get('caracterizacao', 'Não obrigatório')}
Função: {est.get('funcao', 'Contribuir para maturidade profissional')}
Carga Horária Máxima Semanal: {est.get('carga_horaria_maxima_semanal', 30)}h

REQUISITOS DO ALUNO:
- Matrícula: {req.get('matricula', 'Regular no BCC')}
- Disciplinas Obrigatórias: {', '.join(req.get('disciplinas_obrigatorias', []))}
- Rendimento: {req.get('rendimento', 'Bom rendimento acadêmico')}"""
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'estagio'}))
        
        return docs
    
    @staticmethod
    def _parse_infraestrutura(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        infra = data.get('infraestrutura', {})
        
        unidades = infra.get('unidades_fisicas', [])
        for unid in unidades:
            nome = unid.get('nome', 'Unidade')
            txt = f"""INFRAESTRUTURA - {nome}
Área Total: {unid.get('area_total', 'N/A')}
Localização: {unid.get('localizacao', 'N/A')}
Uso: {unid.get('uso', unid.get('uso_atual', 'N/A'))}"""
            
            espacos = unid.get('espacos', {})
            if espacos:
                txt += "\n\nEspaços:"
                for k, v in espacos.items():
                    txt += f"\n- {k.replace('_', ' ').title()}: {v}"
            
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': f'infraestrutura_{nome[:15]}'}))
        
        equip = infra.get('equipamentos_informatica', {})
        if equip:
            txt = f"""EQUIPAMENTOS DE INFORMÁTICA - ICT UNIFESP
Total de Computadores Didáticos: {equip.get('total_computadores_didaticos', 'N/A')}
Sistemas Operacionais: {', '.join(equip.get('sistemas_operacionais', []))}
Plataformas: {', '.join(equip.get('plataformas', []))}"""
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'equipamentos'}))
        
        biblio = infra.get('biblioteca', {})
        if biblio:
            acervo = biblio.get('acervo', {})
            txt = f"""BIBLIOTECA - ICT UNIFESP
Objetivo: {biblio.get('objetivo', 'N/A')}
Títulos: {acervo.get('titulos', 'N/A')}
Exemplares: {acervo.get('exemplares', 'N/A')}
Postos de Estudo Individual: {biblio.get('espacos_estudo', {}).get('postos_individuais', 'N/A')}
Salas de Estudo em Grupo: {biblio.get('espacos_estudo', {}).get('salas_estudo', 'N/A')}"""
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': 'biblioteca'}))
        
        return docs
    
    @staticmethod
    def _parse_apoio_discente(data: Dict, base_meta: Dict) -> List[Document]:
        docs = []
        apoio = data.get('apoio_discente', {})
        
        orgaos = apoio.get('orgaos_principais', [])
        for orgao in orgaos:
            nome = orgao.get('nome', 'Órgão')
            txt = f"""APOIO AO DISCENTE - {nome}
Responsabilidade: {orgao.get('responsabilidade', 'N/A')}"""
            
            comps = orgao.get('competencias', [])
            if comps:
                txt += "\n\nCompetências:"
                for c in comps:
                    txt += f"\n- {c}"
            
            docs.append(Document(page_content=txt, metadata={**base_meta, 'secao': f'apoio_{nome[:15]}'}))
        
        return docs
