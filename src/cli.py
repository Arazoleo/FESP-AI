from .rag import RAGUnifesp


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

