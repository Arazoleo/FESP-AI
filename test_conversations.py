#!/usr/bin/env python3
"""
Script de teste para conversas contextuais.
Testa a capacidade do sistema de manter contexto entre perguntas.
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def chat(message: str, conversation_id: str = None) -> dict:
    """Envia mensagem e retorna resposta."""
    payload = {"message": message}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat",
            json=payload,
            timeout=120
        )
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def print_header(title: str):
    print("\n" + "━" * 70)
    print(f"📝 {title}")
    print("━" * 70)


def print_exchange(user_msg: str, response: dict, show_full: bool = True):
    print(f"\n👤 User: {user_msg}")
    if "error" in response:
        print(f"❌ Erro: {response['error']}")
    else:
        resp_text = response.get("response", "")
        if show_full or len(resp_text) < 400:
            print(f"🤖 Assistant: {resp_text}")
        else:
            print(f"🤖 Assistant: {resp_text[:400]}...")


def test_docente_flow():
    """Testa fluxo de perguntas sobre docente."""
    print_header("CONVERSA 1: Fluxo sobre Docente (pronomes)")
    
    # Pergunta inicial
    r1 = chat("Quem é a professora Lilian Berton?")
    print_exchange("Quem é a professora Lilian Berton?", r1)
    conv_id = r1.get("conversation_id")
    
    time.sleep(1)
    
    # Perguntas contextuais com pronomes
    r2 = chat("Qual o email dela?", conv_id)
    print_exchange("Qual o email dela?", r2)
    
    time.sleep(1)
    
    r3 = chat("E as áreas de pesquisa dela?", conv_id)
    print_exchange("E as áreas de pesquisa dela?", r3)
    
    time.sleep(1)
    
    r4 = chat("Qual a sala dela?", conv_id)
    print_exchange("Qual a sala dela?", r4)
    
    return conv_id


def test_curso_flow():
    """Testa fluxo de perguntas sobre curso."""
    print_header("CONVERSA 2: Fluxo sobre Curso (herança de contexto)")
    
    r1 = chat("Quais são as disciplinas do termo 3 de BCC?")
    print_exchange("Quais são as disciplinas do termo 3 de BCC?", r1)
    conv_id = r1.get("conversation_id")
    
    time.sleep(1)
    
    # Pergunta contextual - deve herdar "BCC"
    r2 = chat("E no termo 5?", conv_id)
    print_exchange("E no termo 5?", r2)
    
    time.sleep(1)
    
    # Pergunta sobre coordenador - deve herdar "BCC"
    r3 = chat("Quem é o coordenador desse curso?", conv_id)
    print_exchange("Quem é o coordenador desse curso?", r3)
    
    time.sleep(1)
    
    # Pergunta sobre eletivas - deve herdar "BCC"
    r4 = chat("Quais são as eletivas?", conv_id)
    print_exchange("Quais são as eletivas?", r4, show_full=False)
    
    return conv_id


def test_disciplina_flow():
    """Testa fluxo de perguntas sobre disciplina."""
    print_header("CONVERSA 3: Fluxo sobre Disciplina (pré-requisitos)")
    
    r1 = chat("Quais são os pré-requisitos de Inteligência Artificial?")
    print_exchange("Quais são os pré-requisitos de Inteligência Artificial?", r1)
    conv_id = r1.get("conversation_id")
    
    time.sleep(1)
    
    # Pergunta sobre docentes da disciplina
    r2 = chat("Quem leciona essa disciplina?", conv_id)
    print_exchange("Quem leciona essa disciplina?", r2)
    
    time.sleep(1)
    
    # Mudar para outra disciplina
    r3 = chat("E de Compiladores, quais são os pré-requisitos?", conv_id)
    print_exchange("E de Compiladores, quais são os pré-requisitos?", r3)
    
    time.sleep(1)
    
    # Perguntar sobre docentes dessa nova disciplina
    r4 = chat("Quem leciona?", conv_id)
    print_exchange("Quem leciona?", r4)
    
    return conv_id


def test_lista_docentes():
    """Testa referência a lista de docentes."""
    print_header("CONVERSA 4: Referência a Lista de Docentes")
    
    r1 = chat("Quais professores são especialistas em machine learning?")
    print_exchange("Quais professores são especialistas em machine learning?", r1)
    conv_id = r1.get("conversation_id")
    
    time.sleep(1)
    
    # Perguntar sobre um específico da lista
    r2 = chat("Qual o email do primeiro?", conv_id)
    print_exchange("Qual o email do primeiro?", r2)
    
    time.sleep(1)
    
    # Perguntar sobre outro
    r3 = chat("E do segundo?", conv_id)
    print_exchange("E do segundo?", r3)
    
    return conv_id


def test_mixed_context():
    """Testa mudança de contexto na mesma conversa."""
    print_header("CONVERSA 5: Mudança de Contexto")
    
    # Começar com disciplina
    r1 = chat("Quais são os pré-requisitos de Banco de Dados?")
    print_exchange("Quais são os pré-requisitos de Banco de Dados?", r1)
    conv_id = r1.get("conversation_id")
    
    time.sleep(1)
    
    # Mudar para docente
    r2 = chat("Quem é o professor Fabrício Olivetti?")
    print_exchange("Quem é o professor Fabrício Olivetti?", r2)
    
    time.sleep(1)
    
    # Perguntar sobre o docente (novo contexto)
    r3 = chat("Quais as áreas dele?", conv_id)
    print_exchange("Quais as áreas dele?", r3)
    
    time.sleep(1)
    
    # Voltar para disciplina anterior
    r4 = chat("Voltando ao Banco de Dados, quem leciona?", conv_id)
    print_exchange("Voltando ao Banco de Dados, quem leciona?", r4)
    
    return conv_id


def print_summary():
    print("\n" + "=" * 70)
    print("📊 RESUMO DOS TESTES")
    print("=" * 70)
    print("""
    ✅ Testes realizados:
    
    1. Fluxo Docente: pronomes (ela, dela) → email, áreas, sala
    2. Fluxo Curso: herança de contexto → termo 5, coordenador, eletivas  
    3. Fluxo Disciplina: pré-requisitos → docentes, mudança de disciplina
    4. Lista Docentes: referência ordinal → primeiro, segundo
    5. Mudança Contexto: disciplina → docente → voltar disciplina
    
    Observe as respostas para verificar:
    - Se os pronomes foram resolvidos corretamente
    - Se o contexto foi herdado entre perguntas
    - Se referências a listas funcionaram
    - Se mudanças de contexto foram tratadas
    """)


if __name__ == "__main__":
    print("\n" + "╔" + "═" * 68 + "╗")
    print("║" + " 🧪 TESTE DE CONVERSAS CONTEXTUAIS - FESP-AI (Qwen 7B) ".center(68) + "║")
    print("╚" + "═" * 68 + "╝")
    
    try:
        # Verificar se API está rodando
        health = requests.get(f"{BASE_URL}/health", timeout=5)
        if health.status_code != 200:
            print("❌ API não está saudável")
            exit(1)
        print("\n✅ API está rodando!")
        
        # Executar testes
        test_docente_flow()
        test_curso_flow()
        test_disciplina_flow()
        test_lista_docentes()
        test_mixed_context()
        
        # Resumo
        print_summary()
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Não foi possível conectar à API.")
        print("   Execute: docker compose up -d backend")
    except Exception as e:
        print(f"\n❌ Erro: {e}")

