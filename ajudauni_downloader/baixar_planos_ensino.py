#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para baixar PDFs dos Planos de Ensino do site AjudaUni
Usa Selenium para clicar nos botões e capturar os links dos PDFs
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import os
import time
import re

# Configurações
OUTPUT_DIR = "planos_ensino"
BASE_URL = "https://ajudauni.com"

def criar_pasta():
    """Cria a pasta de saída"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Pasta '{OUTPUT_DIR}' criada\n")

def criar_driver():
    """Cria o driver do Selenium"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(options=options)

def limpar_nome(nome):
    """Limpa o nome do arquivo"""
    return re.sub(r'[<>:"/\\|?*]', '', nome).replace(' ', '_')

def obter_disciplinas(driver):
    """Obtém lista de disciplinas"""
    print("Buscando disciplinas...")
    driver.get(BASE_URL)
    time.sleep(3)
    
    links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/subject/"]')
    disciplinas = []
    
    for link in links:
        href = link.get_attribute('href')
        if href and href not in disciplinas:
            disciplinas.append(href)
    
    print(f"Encontradas {len(disciplinas)} disciplinas\n")
    return disciplinas

def baixar_pdf_disciplina(driver, url_disciplina):
    """Acessa a disciplina e baixa o PDF"""
    nome = url_disciplina.split('/')[-1].replace('-', ' ').title()
    
    try:
        # Acessar página da disciplina
        driver.get(url_disciplina)
        time.sleep(2)
        
        # Procurar link do Plano de Ensino
        try:
            plano_link = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'Plano de Ensino')]"))
            )
            
            # Clicar no link
            plano_link.click()
            time.sleep(2)
            
            # Obter URL do PDF
            pdf_url = driver.current_url
            
            # Voltar para a página anterior
            driver.back()
            time.sleep(1)
            
            # Baixar o PDF
            if pdf_url.endswith('.pdf'):
                nome_arquivo = limpar_nome(nome) + '.pdf'
                caminho = os.path.join(OUTPUT_DIR, nome_arquivo)
                
                if os.path.exists(caminho):
                    print(f"  Ja existe")
                    return True
                
                response = requests.get(pdf_url, timeout=60, stream=True)
                response.raise_for_status()
                
                with open(caminho, 'wb') as f:
                    for chunk in response.iter_content(8192):
                        f.write(chunk)
                
                tamanho = os.path.getsize(caminho) / 1024
                print(f"  Baixado ({tamanho:.1f} KB)")
                return True
            else:
                print(f"  Aviso: Nao e PDF")
                return None
                
        except:
            print(f"  Aviso: PDF nao encontrado")
            return None
            
    except Exception as e:
        print(f"  Erro: {str(e)[:40]}")
        return False

def main():
    """Função principal"""
    print("=" * 70)
    print("  DOWNLOAD DE PLANOS DE ENSINO - AJUDAUNI.COM")
    print("=" * 70 + "\n")
    
    criar_pasta()
    
    driver = None
    try:
        driver = criar_driver()
        disciplinas = obter_disciplinas(driver)
        
        total = len(disciplinas)
        sucesso = 0
        falha = 0
        sem_pdf = 0
        
        print(f"Baixando {total} planos de ensino...\n")
        
        for i, url in enumerate(disciplinas, 1):
            nome = url.split('/')[-1].replace('-', ' ').title()
            print(f"[{i}/{total}] {nome}")
            
            resultado = baixar_pdf_disciplina(driver, url)
            
            if resultado is True:
                sucesso += 1
            elif resultado is False:
                falha += 1
            else:
                sem_pdf += 1
        
        # Resumo
        print("\n" + "=" * 70)
        print("  RESUMO")
        print("=" * 70)
        print(f"Sucesso: {sucesso}")
        print(f"Falha: {falha}")
        print(f"Sem PDF: {sem_pdf}")
        print(f"Pasta: {os.path.abspath(OUTPUT_DIR)}")
        print("=" * 70)
        
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
