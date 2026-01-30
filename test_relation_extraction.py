#!/usr/bin/env python3
"""
Script de teste para extração de relações via LLM.
Demonstra a capacidade do sistema de extrair conhecimento de textos não estruturados.
"""
import sys
sys.path.insert(0, '.')

from src.relation_extractor import RelationExtractor
from src.config import Config

# Textos de exemplo para teste
SAMPLE_TEXTS = [
    # Texto 1: Informações sobre docente
    """
    A Professora Lilian Berton é especialista em Inteligência Artificial e Machine Learning.
    Ela leciona as disciplinas de Aprendizado de Máquina e Redes Neurais no curso de 
    Ciência da Computação (BCC). Suas principais áreas de pesquisa incluem Deep Learning,
    Mineração de Dados e Redes Complexas.
    """,
    
    # Texto 2: Relações entre disciplinas
    """
    A disciplina de Inteligência Artificial tem como pré-requisitos Estrutura de Dados 
    e Probabilidade e Estatística. Ela está relacionada com Machine Learning e aborda
    conceitos como busca heurística, representação do conhecimento e agentes inteligentes.
    O Professor Fabrício Olivetti de França é responsável por essa disciplina.
    """,
    
    # Texto 3: Estrutura de curso
    """
    O curso de Bacharelado em Ciência da Computação (BCC) é coordenado pelo Prof. Tiago Agostinho
    de Almeida. O BCC inclui disciplinas como Algoritmos, Banco de Dados e Compiladores.
    As eletivas do grupo 1 incluem Computação Gráfica e Visão Computacional.
    """,
    
    # Texto 4: Texto mais genérico (teste de robustez)
    """
    Na área de Computação, os conceitos de grafos são fundamentais para entender 
    algoritmos de busca e estruturas de dados avançadas. A teoria de grafos está
    relacionada com redes neurais e otimização combinatória.
    """
]


def test_extraction():
    """Testa a extração de relações."""
    print("=" * 60)
    print(" TESTE DE EXTRAÇÃO DE RELAÇÕES VIA LLM")
    print("=" * 60)
    print(f"\nUsando modelo: {Config.MODEL_NAME}")
    print("-" * 60)
    
    # Inicializar extrator
    print("\n📦 Inicializando extrator de relações...")
    extractor = RelationExtractor(model_name=Config.MODEL_NAME)
    
    all_relations = []
    
    for i, text in enumerate(SAMPLE_TEXTS, 1):
        print(f"\n\n{'='*60}")
        print(f" 📄 TEXTO {i}")
        print("=" * 60)
        print(text.strip()[:200] + "..." if len(text) > 200 else text.strip())
        print("-" * 60)
        
        print("\n🔍 Extraindo relações...")
        relations = extractor.extract_from_text(text, min_confidence=0.5)
        
        if relations:
            print(f"\n✅ {len(relations)} relações encontradas:\n")
            for rel in relations:
                conf_bar = "█" * int(rel.confidence * 10) + "░" * (10 - int(rel.confidence * 10))
                print(f"  [{conf_bar}] {rel.confidence:.2f}")
                print(f"     {rel.subject} ({rel.subject_type})")
                print(f"        --[{rel.relation}]-->")
                print(f"     {rel.object} ({rel.object_type})")
                print()
            all_relations.extend(relations)
        else:
            print("\n⚠️  Nenhuma relação encontrada")
    
    # Resumo
    print("\n" + "=" * 60)
    print(" 📊 RESUMO FINAL")
    print("=" * 60)
    print(f"\n Total de relações extraídas: {len(all_relations)}")
    
    # Estatísticas por tipo de relação
    relation_counts = {}
    for rel in all_relations:
        r = rel.relation
        relation_counts[r] = relation_counts.get(r, 0) + 1
    
    print("\n Por tipo de relação:")
    for r, count in sorted(relation_counts.items(), key=lambda x: -x[1]):
        print(f"   - {r}: {count}")
    
    # Estatísticas por tipo de entidade
    entity_counts = {}
    for rel in all_relations:
        for t in [rel.subject_type, rel.object_type]:
            entity_counts[t] = entity_counts.get(t, 0) + 1
    
    print("\n Por tipo de entidade:")
    for t, count in sorted(entity_counts.items(), key=lambda x: -x[1]):
        print(f"   - {t}: {count}")
    
    # Confiança média
    if all_relations:
        avg_conf = sum(r.confidence for r in all_relations) / len(all_relations)
        print(f"\n Confiança média: {avg_conf:.2f}")
    
    # Converter para formato de grafo
    print("\n\n" + "-" * 60)
    print("📤 Formato para Knowledge Graph:")
    print("-" * 60)
    graph_format = extractor.relations_to_graph_format(all_relations)
    for gf in graph_format[:5]:
        print(f"\n  {gf['source_id']}")
        print(f"    --[{gf['relation']}]--> ")
        print(f"  {gf['target_id']}")
    
    if len(graph_format) > 5:
        print(f"\n  ... e mais {len(graph_format) - 5} relações")
    
    print("\n\n✅ Teste concluído!")
    return all_relations


def test_with_api():
    """Testa via API (se estiver rodando)."""
    import requests
    
    print("\n\n" + "=" * 60)
    print(" TESTE VIA API")
    print("=" * 60)
    
    try:
        # Testar extração
        response = requests.post(
            "http://localhost:8000/extract-relations",
            json={
                "text": SAMPLE_TEXTS[0],
                "min_confidence": 0.5
            },
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ API funcionando!")
            print(f"   Relações extraídas: {data['count']}")
            for rel in data['relations']:
                print(f"   - {rel['subject']} --[{rel['relation']}]--> {rel['object']}")
        else:
            print(f"\n⚠️  Erro na API: {response.status_code}")
            print(response.text)
    
    except requests.exceptions.ConnectionError:
        print("\n⚠️  API não está rodando. Inicie com: docker compose up -d backend")
    except Exception as e:
        print(f"\n❌ Erro: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Testa extração de relações via LLM")
    parser.add_argument("--api", action="store_true", help="Também testar via API")
    args = parser.parse_args()
    
    # Teste local
    relations = test_extraction()
    
    # Teste via API (opcional)
    if args.api:
        test_with_api()

