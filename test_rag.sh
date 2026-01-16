#!/bin/bash

echo "========================================"
echo "🧪 BATERIA DE TESTES DO RAG - FESP-AI"
echo "========================================"
echo ""

# Função para testar
test_query() {
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📝 $1"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    response=$(curl -s -X POST "http://localhost:8000/chat" -H "Content-Type: application/json" -d "{\"message\": \"$1\"}" | jq -r '.response')
    echo "$response"
    echo ""
    sleep 2
}

echo "========================================"
echo "📚 TESTE 1: DISCIPLINAS NOVAS"
echo "========================================"

test_query "Fale sobre a disciplina de Transdução de Grandezas Biomédicas"
test_query "Quais os pré-requisitos de Técnicas Experimentais?"
test_query "Quem leciona Tópicos em Tecnologia da Computação I?"
test_query "Qual a carga horária de Resolução de Problemas via Modelagem Matemática?"

echo "========================================"
echo "👨‍🏫 TESTE 2: INFORMAÇÕES DE DOCENTES"
echo "========================================"

test_query "Qual o email do Bruno Kimura?"
test_query "Onde fica a sala da Lilian Berton?"
test_query "Informações do Elbert Macau"
test_query "Como entro em contato com Denise Stringhini?"

echo "========================================"
echo "🔬 TESTE 3: ÁREAS DE ESPECIALIZAÇÃO"
echo "========================================"

test_query "Quais professores trabalham com Inteligência Artificial?"
test_query "Quem é especialista em Redes de Computadores?"
test_query "Professores que trabalham com Aprendizado de Máquina"
test_query "Em que área o Marcos Quiles é especialista?"

echo "========================================"
echo "🔗 TESTE 4: PRÉ-REQUISITOS E DEPENDÊNCIAS"
echo "========================================"

test_query "Quais são os pré-requisitos de Inteligência Artificial?"
test_query "Quais disciplinas dependem de Algoritmos e Estruturas de Dados I?"
test_query "Qual a cadeia de pré-requisitos de Redes de Computadores?"
test_query "Pré-requisitos de Programação Orientada a Objetos"

echo "========================================"
echo "📜 TESTE 5: REGIMENTOS E NORMAS"
echo "========================================"

test_query "O que são atividades complementares?"
test_query "Quantas horas de atividades complementares preciso?"
test_query "O que diz o artigo 35 do regimento?"
test_query "Como funciona o aproveitamento de disciplinas?"

echo "========================================"
echo "🎓 TESTE 6: CURSOS"
echo "========================================"

test_query "Quais cursos o ICT oferece?"
test_query "Disciplinas do curso de Ciência da Computação"
test_query "Disciplinas do curso de Engenharia Biomédica"

echo "========================================"
echo "✅ TESTES CONCLUÍDOS!"
echo "========================================"
