import os
import json
import sqlite3
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

DB_NAME = "osint_coletas.db"

# ==========================================
# BANCO DE DADOS (SQLite)
# ==========================================
def inicializar_banco():
    """Garante que a tabela de histórico de coletas exista."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS coletas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            data_execucao TEXT NOT NULL,
            diretorio_local TEXT NOT NULL,
            qtd_midias INTEGER DEFAULT 0,
            status TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def registrar_coleta_db(username: str, diretorio: str, qtd_midias: int, status: str):
    """Registra uma extração no banco de dados SQLite."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO coletas (username, data_execucao, diretorio_local, qtd_midias, status)
        VALUES (?, ?, ?, ?, ?)
    """, (
        username,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        diretorio,
        qtd_midias,
        status
    ))
    conn.commit()
    conn.close()

# ==========================================
# EXTRAÇÃO E DOWNLOAD
# ==========================================
def extrair_conteudo_perfil(sessionid: str, username_alvo: str, max_scrolls: int = 5):
    """
    Navega até o perfil do alvo usando o sessionid injetado no Playwright,
    rola a página para carregar todas as fotos, extrai em alta qualidade e salva no disco.
    """
    inicializar_banco()
    username_alvo = username_alvo.replace("@", "").strip()
    pasta_destino = os.path.join("downloads", f"@{username_alvo}")
    os.makedirs(pasta_destino, exist_ok=True)
    
    midias_coletadas = []
    seen_urls = set()

    with sync_playwright() as p:
        print("[*] Iniciando navegador Chromium...")
        browser = p.chromium.launch(headless=True)
        
        # Cria contexto e injeta o cookie de sessão do Instagram
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        # Se for um arquivo de storage_state do Playwright existente, carrega
        if os.path.exists(sessionid):
            context = browser.new_context(storage_state=sessionid)
        else:
            # Injeta o cookie sessionid diretamente no domínio do Instagram
            context.add_cookies([{
                "name": "sessionid",
                "value": sessionid,
                "domain": ".instagram.com",
                "path": "/"
            }])

        page = context.new_page()

        print(f"[*] Acessando perfil @{username_alvo}...")
        page.goto(f"https://www.instagram.com/{username_alvo}/", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Checa se o perfil é privado e a conta ainda não foi aceita
        content = page.content()
        if "Esta conta é privada" in content or "This account is private" in content:
            print(f"[!] O perfil @{username_alvo} é privado e a conta usada ainda não foi aceita!")
            registrar_coleta_db(username_alvo, pasta_destino, 0, "PENDENTE: Não aceito ainda")
            browser.close()
            return

        # Rola a página para forçar o carregamento dinâmico de todas as fotos
        print(f"[*] Carregando fotos da grade (rolando página {max_scrolls} vezes)...")
        for i in range(max_scrolls):
            # Coleta as imagens visíveis no momento
            images = page.query_selector_all("article img, main img")
            for img in images:
                src = img.get_attribute("src")
                srcset = img.get_attribute("srcset")
                alt = img.get_attribute("alt") or "Sem legenda"
                
                # Pega a melhor resolução do srcset se disponível
                best_url = src
                if srcset:
                    parts = srcset.split(",")
                    best_url = parts[-1].strip().split(" ")[0]
                
                if best_url and "scontent" in best_url and best_url not in seen_urls:
                    seen_urls.add(best_url)
                    midias_coletadas.append({
                        "id": len(midias_coletadas) + 1,
                        "url": best_url,
                        "legenda": alt
                    })

            # Rola para baixo e aguarda novas imagens carregarem
            page.evaluate("window.scrollBy(0, 1200)")
            page.wait_for_timeout(1500)

        browser.close()

    if not midias_coletadas:
        print("[-] Nenhuma foto encontrada no feed.")
        registrar_coleta_db(username_alvo, pasta_destino, 0, "VAZIO")
        return

    # Download das fotos para a pasta local
    print(f"\n[+] Total de {len(midias_coletadas)} foto(s) identificada(s)! Iniciando downloads...")
    count_download = 0
    for idx, item in enumerate(midias_coletadas, 1):
        try:
            res = requests.get(item["url"], timeout=15)
            if res.status_code == 200:
                filepath = os.path.join(pasta_destino, f"foto_{idx}.jpg")
                with open(filepath, "wb") as f:
                    f.write(res.content)
                count_download += 1
                print(f"  [>] Baixada foto {idx}/{len(midias_coletadas)}")
        except Exception as err:
            print(f"  [-] Falha ao baixar foto {idx}: {err}")

    # Salva relatório JSON com legendas e metadados
    json_path = os.path.join(pasta_destino, "dados_perfil.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(midias_coletadas, f, ensure_ascii=False, indent=4)

    # Registra o resultado no banco SQLite
    registrar_coleta_db(username_alvo, pasta_destino, count_download, "CONCLUIDO")
    print(f"\n[✔] Extração finalizada com sucesso! {count_download} fotos salvas em: {pasta_destino}")

# ==========================================
# EXECUÇÃO
# ==========================================
if __name__ == "__main__":
    # Carrega sessionid do ambiente ou solicita ao usuário
    SESSION_ID = os.getenv("IG_SESSIONID", "")
    if not SESSION_ID and os.path.exists(".env"):
        with open(".env", "r") as f:
            for l in f:
                if l.startswith("IG_SESSIONID="):
                    SESSION_ID = l.split("=", 1)[1].strip().strip("'\"")
                    
    if not SESSION_ID:
        SESSION_ID = input("Cole o sessionid da sua conta do Instagram: ").strip()
    
    # Nome do alvo (sem @)
    ALVO = input("Digite o username do alvo a extrair (sem @): ").strip().replace("@", "")
    
    if ALVO and SESSION_ID:
        extrair_conteudo_perfil(SESSION_ID, ALVO, max_scrolls=6)
    else:
        print("Dados insuficientes fornecidos.")