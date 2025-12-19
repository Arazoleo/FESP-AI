# 📚 Download de Planos de Ensino - AjudaUni

Script Python para baixar automaticamente todos os PDFs dos planos de ensino das disciplinas do site [AjudaUni](https://ajudauni.com/).

## 🎯 O que este script faz?

O script acessa o site AjudaUni, identifica todas as disciplinas disponíveis, acessa cada uma delas, localiza o botão "Plano de Ensino" e baixa o PDF correspondente.

## 📋 Arquivos Disponíveis

### ✅ `baixar_planos_ensino.py` (RECOMENDADO)
Script completo e funcional que usa Selenium para automação.

**Características:**
- ✅ Funciona com conteúdo dinâmico (JavaScript)
- ✅ Clica automaticamente nos botões "Plano de Ensino"
- ✅ Baixa os PDFs diretamente
- ✅ Evita downloads duplicados
- ✅ Mostra progresso detalhado
- ✅ Tratamento de erros robusto

## 🚀 Como Usar

### Passo 1: Instalar Dependências

```bash
pip install selenium requests
```

**Nota:** O Selenium requer o ChromeDriver. Na maioria dos sistemas modernos, ele é instalado automaticamente. Se não funcionar, instale manualmente:

```bash
# Ubuntu/Debian
sudo apt-get install chromium-chromedriver

# macOS
brew install chromedriver

# Windows
# Baixe de: https://chromedriver.chromium.org/
```

### Passo 2: Executar o Script

```bash
python3 baixar_planos_ensino.py
```

### Passo 3: Aguardar o Download

O script irá:
1. Acessar o site AjudaUni
2. Listar todas as disciplinas (aproximadamente 224)
3. Para cada disciplina:
   - Acessar a página
   - Clicar em "Plano de Ensino"
   - Baixar o PDF
4. Salvar os arquivos na pasta `planos_ensino/`

**Tempo estimado:** 10-15 minutos para todas as disciplinas

## 📁 Estrutura de Saída

```
planos_ensino/
├── Calculo_Em_Uma_Variavel.pdf
├── Geometria_Analitica.pdf
├── Algebra_Linear_I.pdf
├── Calculo_Numerico.pdf
├── Matematica_Discreta.pdf
├── ...
└── (todas as disciplinas disponíveis)
```

## 📊 Exemplo de Execução

```
======================================================================
  DOWNLOAD DE PLANOS DE ENSINO - AJUDAUNI.COM
======================================================================
✓ Pasta 'planos_ensino' criada

🔍 Buscando disciplinas...
✓ Encontradas 224 disciplinas

📥 Baixando 224 planos de ensino...

[1/224] Calculo Em Uma Variavel
  ✓ Baixado (245.3 KB)
[2/224] Geometria Analitica
  ✓ Baixado (198.7 KB)
[3/224] Algebra Linear I
  ✓ Baixado (212.4 KB)
[4/224] Calculo Numerico
  ⚠ PDF não encontrado
[5/224] Matematica Discreta
  ✓ Baixado (187.9 KB)
...

======================================================================
  RESUMO
======================================================================
✓ Sucesso: 180
✗ Falha: 5
⚠ Sem PDF: 39
📁 Pasta: /home/user/planos_ensino
======================================================================
```

## ⚙️ Personalização

### Alterar Pasta de Saída

Edite a linha no script:

```python
OUTPUT_DIR = "planos_ensino"  # Altere para o nome desejado
```

### Ajustar Tempo de Espera

Para conexões mais lentas, aumente os valores de `time.sleep()`:

```python
time.sleep(3)  # Aumentar para 5 ou mais
```

## 🔧 Solução de Problemas

### Erro: "No module named 'selenium'"

```bash
pip install selenium
```

### Erro: "ChromeDriver not found"

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install chromium-chromedriver
```

**macOS:**
```bash
brew install chromedriver
```

**Windows:**
1. Baixe o ChromeDriver em https://chromedriver.chromium.org/
2. Adicione ao PATH do sistema

### Erro: "Connection timeout"

- Verifique sua conexão com a internet
- Aumente o timeout no script (linha `timeout=60`)
- Tente novamente mais tarde

### Alguns PDFs não foram baixados

Isso é normal! Algumas disciplinas podem não ter o plano de ensino disponível no site. O script mostra "⚠ PDF não encontrado" nesses casos.

## ⚠️ Observações Importantes

- **Respeito ao servidor:** O script inclui pausas entre requisições para não sobrecarregar o servidor
- **Downloads duplicados:** PDFs já baixados são automaticamente ignorados
- **Execução parcial:** Se o script for interrompido, você pode executá-lo novamente e ele continuará de onde parou
- **Uso responsável:** Use este script de forma responsável e respeite os termos de uso do site AjudaUni

## 📝 Requisitos do Sistema

- **Python:** 3.6 ou superior
- **Sistema Operacional:** Windows, macOS ou Linux
- **Conexão:** Internet estável
- **Espaço em disco:** Aproximadamente 50-100 MB para todos os PDFs

## 🤝 Suporte

Se encontrar problemas:

1. Verifique se todas as dependências estão instaladas
2. Certifique-se de que o ChromeDriver está acessível
3. Verifique sua conexão com a internet
4. Tente executar o script novamente

## 📄 Licença

Este script é fornecido "como está", para fins educacionais. Use com responsabilidade e respeite os direitos autorais dos materiais baixados.

---

**Desenvolvido para facilitar o acesso aos planos de ensino das disciplinas da UNIFESP via AjudaUni** 🎓
