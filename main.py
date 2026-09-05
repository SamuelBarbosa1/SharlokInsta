import os
import sys
import time
import json
import sqlite3
import random
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

# Força UTF-8 no console Windows para evitar UnicodeEncodeError
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# =====================================================================
# CONFIGURAÇÕES DA CONTA (VARIÁVEIS DE AMBIENTE .ENV & DESKTOP)
# =====================================================================
CONFIG_FILE = "config_conta.json"
MONITOR_FILE = "alvos_monitorados.json"
DB_NAME = "osint_coletas.db"
ENV_FILE = ".env"

def carregar_dotenv(caminho=".env"):
    """Carrega variáveis do arquivo .env sem exigir dependências externas."""
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k:
                            os.environ[k] = v
        except Exception:
            pass

carregar_dotenv()

def carregar_config():
    """Carrega configurações da conta priorizando .env e com fallback em config_conta.json."""
    carregar_dotenv()
    cfg = {
        "user": os.getenv("IG_USER", ""),
        "ds_user_id": os.getenv("IG_DS_USER_ID", ""),
        "sessionid": os.getenv("IG_SESSIONID", "")
    }

    # Se faltar algum campo, tenta ler do config_conta.json local
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for k in ["user", "ds_user_id", "sessionid"]:
                    if not cfg.get(k) and saved.get(k):
                        cfg[k] = saved[k]
        except Exception:
            pass

    # Se sessionid contiver o user_id antes do %3A ou :, deduz o ds_user_id
    if cfg.get("sessionid") and not cfg.get("ds_user_id"):
        uid = cfg["sessionid"].split("%3A")[0].split(":")[0]
        if uid.isdigit():
            cfg["ds_user_id"] = uid

    return cfg

def salvar_config(cfg):
    """Salva as credenciais no .env e no config_conta.json local."""
    # 1. Salva em config_conta.json
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
    except Exception:
        pass

    # 2. Salva ou atualiza o .env local
    try:
        linhas = [
            "# Credenciais da conta de automação do Instagram (MANTENHA PRIVADO)\n",
            f"IG_USER={cfg.get('user', '')}\n",
            f"IG_DS_USER_ID={cfg.get('ds_user_id', '')}\n",
            f"IG_SESSIONID={cfg.get('sessionid', '')}\n"
        ]
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(linhas)
    except Exception:
        pass


# =====================================================================
# BANCO DE DADOS LOCAL (HISTÓRICO DE COLETAS)
# =====================================================================
def inicializar_banco():
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

# =====================================================================
# GESTÃO DE ALVOS MONITORADOS (JSON)
# =====================================================================
def carregar_alvos():
    if os.path.exists(MONITOR_FILE):
        try:
            with open(MONITOR_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def salvar_alvos(alvos):
    with open(MONITOR_FILE, "w", encoding="utf-8") as f:
        json.dump(alvos, f, indent=4, ensure_ascii=False)

def registrar_novo_alvo(username, is_private=True):
    alvos = carregar_alvos()
    # Verifica se já existe
    for a in alvos:
        if a["username"].lower() == username.lower():
            a["status"] = "AGUARDANDO_APROVACAO" if is_private else "SEGUINDO"
            a["atualizado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            salvar_alvos(alvos)
            return
    alvos.append({
        "username": username,
        "is_private": is_private,
        "status": "AGUARDANDO_APROVACAO" if is_private else "SEGUINDO",
        "solicitado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "atualizado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    salvar_alvos(alvos)

# =====================================================================
# NAVEGADOR PLAYWRIGHT (DESKTOP / PC CHROME)
# =====================================================================
def criar_contexto_desktop(browser, cfg):
    """Cria um contexto simulando 100% o Google Chrome Desktop no Windows."""
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 768},
        locale="pt-BR"
    )
    # Injeta os cookies da sessão de desktop
    cookies = [
        {"name": "sessionid", "value": cfg["sessionid"], "domain": ".instagram.com", "path": "/"},
        {"name": "ds_user_id", "value": cfg["ds_user_id"], "domain": ".instagram.com", "path": "/"}
    ]
    context.add_cookies(cookies)
    return context

def obter_info_perfil(page, username):
    """Lê metadados da tela de perfil de desktop do Instagram."""
    print(f"[*] Acessando https://www.instagram.com/{username}/ na versão Desktop...")
    page.goto(f"https://www.instagram.com/{username}/", wait_until="domcontentloaded")
    page.wait_for_timeout(3500)
    
    content = page.content().lower()
    is_private = "esta conta é privada" in content or "this account is private" in content
    
    # Detecta estado do botão de seguir
    btn_status = "Desconhecido"
    buttons = page.query_selector_all("header button, main header button, button")
    for btn in buttons:
        txt = (btn.inner_text() or "").strip().lower()
        if txt in ["follow", "seguir"]:
            btn_status = "NAO_SEGUINDO"
            break
        elif txt in ["requested", "solicitado"]:
            btn_status = "SOLICITADO"
            break
        elif txt in ["following", "seguindo"]:
            btn_status = "SEGUINDO"
            break
            
    # Tenta coletar cabeçalho
    header_text = ""
    try:
        header_el = page.query_selector("header")
        if header_el:
            header_text = header_el.inner_text()
    except Exception:
        pass

    return {
        "username": username,
        "is_private": is_private,
        "button_status": btn_status,
        "header_snippet": header_text[:200].replace("\n", " | ") if header_text else ""
    }

# =====================================================================
# EXTRAÇÃO E DOWNLOAD COMPLETO (PERFIL, BIO, DESTAQUES, STORIES E FEED)
# =====================================================================
def extrair_e_baixar_fotos(page, username_alvo, max_scrolls=6):
    """Extrai Bio, Avatar HD, Destaques, Stories ativos e todas as fotos do Feed em 1080x1080."""
    inicializar_banco()
    username_alvo = username_alvo.replace("@", "").strip()
    pasta_destino = os.path.join("downloads", f"@{username_alvo}")
    os.makedirs(pasta_destino, exist_ok=True)
    pasta_destaques = os.path.join(pasta_destino, "destaques")
    pasta_stories = os.path.join(pasta_destino, "stories")

    print(f"\n" + "="*60)
    print(f"[*] INICIANDO EXTRAÇÃO COMPLETA DE @{username_alvo}")
    print("="*60)

    # 1. CABEÇALHO, BIOGRAFIA E AVATAR HD
    print("\n[1/4] Extraindo Biografia e Dados do Perfil...")
    header_el = page.query_selector("header")
    header_text = header_el.inner_text() if header_el else ""

    posts_count = "N/A"
    seguidores = "N/A"
    seguindo = "N/A"
    for line in header_text.split("\n"):
        l = line.strip().lower()
        if "posts" in l or "publicações" in l:
            posts_count = line.strip()
        elif "seguidores" in l or "followers" in l:
            seguidores = line.strip()
        elif "seguindo" in l or "following" in l:
            seguindo = line.strip()

    # Links da bio (ignora links internos do Instagram)
    links = []
    link_els = page.query_selector_all("header a")
    for el in link_els:
        href = el.get_attribute("href") or ""
        txt = (el.inner_text() or "").strip()
        if href and not href.startswith("#") and "/followers/" not in href and "/following/" not in href and "/mutualOnly" not in href and f"/{username_alvo}/" != href:
            full_url = f"https://www.instagram.com{href}" if href.startswith("/") else href
            if full_url not in [lk["url"] for lk in links]:
                links.append({"texto": txt, "url": full_url})

    # Avatar em alta definição
    avatar_salvo = False
    try:
        avatar_img = page.query_selector("header img")
        if avatar_img:
            avatar_src = avatar_img.get_attribute("src")
            if avatar_src and avatar_src.startswith("http"):
                res = requests.get(avatar_src, timeout=15)
                if res.status_code == 200:
                    with open(os.path.join(pasta_destino, "avatar_perfil.jpg"), "wb") as f:
                        f.write(res.content)
                    avatar_salvo = True
                    print("  [>] Foto de perfil (avatar HD) salva com sucesso!")
    except Exception as e:
        print(f"  [-] Erro ao salvar avatar: {e}")

    # Salva arquivo bio.txt legível
    bio_txt_path = os.path.join(pasta_destino, "bio.txt")
    with open(bio_txt_path, "w", encoding="utf-8") as f:
        f.write("="*60 + "\n")
        f.write(f" PERFIL DO INSTAGRAM: @{username_alvo}\n")
        f.write(f" {posts_count} | {seguidores} | {seguindo}\n")
        f.write("="*60 + "\n\n")
        f.write("--- BIOGRAFIA E INFORMAÇÕES ---\n")
        f.write(header_text + "\n\n")
        if links:
            f.write("--- LINKS EXTERNOS NA BIO ---\n")
            for lk in links:
                f.write(f"- {lk['texto'] or 'Link'}: {lk['url']}\n")
            f.write("\n")
        f.write("="*60 + "\n")
    print("  [>] Arquivo bio.txt gerado com sucesso!")

    # 2. DESTAQUES (HIGHLIGHTS)
    print("\n[2/4] Verificando Destaques (Highlights)...")
    highlight_anchors = page.query_selector_all("a[href*='/stories/highlights/']")
    hl_urls = []
    for a in highlight_anchors:
        h_href = a.get_attribute("href")
        if h_href and h_href not in hl_urls:
            hl_urls.append(h_href)

    destaques_coletados = []
    if hl_urls:
        os.makedirs(pasta_destaques, exist_ok=True)
        print(f"  [+] {len(hl_urls)} pasta(s) de destaques identificada(s)!")
        aux_page = page.context.new_page()

        for h_idx, href in enumerate(hl_urls, 1):
            full_hl_url = f"https://www.instagram.com{href}" if href.startswith("/") else href
            print(f"  [*] Abrindo destaque {h_idx}/{len(hl_urls)}...")
            try:
                aux_page.goto(full_hl_url, wait_until="domcontentloaded")
                aux_page.wait_for_timeout(2000)

                # Se houver confirmação "View story", clica
                btn = aux_page.locator("text=/View story|Ver story/i")
                if btn.count() > 0:
                    btn.first.click()
                    aux_page.wait_for_timeout(2500)

                seen_slide_urls = set()
                slide_count = 0
                for _ in range(25):  # Percorre os slides do destaque
                    if "/stories/" not in aux_page.url:
                        break

                    # Imagens do slide
                    for img in aux_page.query_selector_all("img"):
                        w = img.evaluate("el => el.naturalWidth")
                        h = img.evaluate("el => el.naturalHeight")
                        s = img.get_attribute("src")
                        srcset = img.get_attribute("srcset")
                        best = s
                        if srcset:
                            best = srcset.split(",")[-1].strip().split(" ")[0]
                        if w and h and (w > 200 or h > 200) and best and best not in seen_slide_urls:
                            seen_slide_urls.add(best)
                            slide_count += 1
                            dest_file = os.path.join(pasta_destaques, f"destaque_{h_idx}_slide_{slide_count}.jpg")
                            r = requests.get(best, timeout=15)
                            if r.status_code == 200:
                                with open(dest_file, "wb") as f:
                                    f.write(r.content)
                                print(f"    [✔] Destaque {h_idx} - Foto salva: {dest_file}")
                                destaques_coletados.append(dest_file)

                    # Vídeos do slide
                    for vid in aux_page.query_selector_all("video, video source"):
                        v_src = vid.get_attribute("src")
                        if v_src and v_src not in seen_slide_urls:
                            seen_slide_urls.add(v_src)
                            slide_count += 1
                            dest_file = os.path.join(pasta_destaques, f"destaque_{h_idx}_slide_{slide_count}.mp4")
                            r = requests.get(v_src, timeout=20)
                            if r.status_code == 200:
                                with open(dest_file, "wb") as f:
                                    f.write(r.content)
                                print(f"    [✔] Destaque {h_idx} - Vídeo salvo: {dest_file}")
                                destaques_coletados.append(dest_file)

                    aux_page.keyboard.press("ArrowRight")
                    aux_page.wait_for_timeout(1000)
            except Exception as e:
                print(f"  [-] Erro ao processar destaque {h_idx}: {e}")

        aux_page.close()
    else:
        print("  [i] Nenhum destaque encontrado no perfil.")

    # 3. STATUS / STORIES ATIVOS (24h)
    print("\n[3/4] Verificando Stories Ativos (24 horas)...")
    stories_coletados = []
    aux_page = page.context.new_page()
    try:
        aux_page.goto(f"https://www.instagram.com/stories/{username_alvo}/", wait_until="domcontentloaded")
        aux_page.wait_for_timeout(2500)
        if "/stories/" in aux_page.url:
            os.makedirs(pasta_stories, exist_ok=True)
            print("  [+] Perfil possui Stories de 24h ativos! Baixando...")
            btn = aux_page.locator("text=/View story|Ver story/i")
            if btn.count() > 0:
                btn.first.click()
                aux_page.wait_for_timeout(2500)

            seen_st_urls = set()
            st_count = 0
            for _ in range(15):
                if "/stories/" not in aux_page.url:
                    break
                for img in aux_page.query_selector_all("img"):
                    w = img.evaluate("el => el.naturalWidth")
                    h = img.evaluate("el => el.naturalHeight")
                    s = img.get_attribute("src")
                    if w and h and (w > 200 or h > 200) and s and s not in seen_st_urls:
                        seen_st_urls.add(s)
                        st_count += 1
                        dest_file = os.path.join(pasta_stories, f"story_{st_count}.jpg")
                        r = requests.get(s, timeout=15)
                        if r.status_code == 200:
                            with open(dest_file, "wb") as f:
                                f.write(r.content)
                            print(f"    [✔] Story foto salva: {dest_file}")
                            stories_coletados.append(dest_file)

                for vid in aux_page.query_selector_all("video, video source"):
                    v_src = vid.get_attribute("src")
                    if v_src and v_src not in seen_st_urls:
                        seen_st_urls.add(v_src)
                        st_count += 1
                        dest_file = os.path.join(pasta_stories, f"story_{st_count}.mp4")
                        r = requests.get(v_src, timeout=20)
                        if r.status_code == 200:
                            with open(dest_file, "wb") as f:
                                f.write(r.content)
                            print(f"    [✔] Story vídeo salvo: {dest_file}")
                            stories_coletados.append(dest_file)

                aux_page.keyboard.press("ArrowRight")
                aux_page.wait_for_timeout(1000)
        else:
            print("  [i] Perfil não possui Stories de 24h ativos no momento.")
    except Exception as e:
        print(f"  [-] Checagem de stories: {e}")
    aux_page.close()

    # 4. FOTOS E PUBLICAÇÕES DO FEED
    print(f"\n[4/4] Extraindo fotos do Feed (rolando a página {max_scrolls} vezes)...")
    midias_coletadas = []
    seen_urls = set()

    for _ in range(max_scrolls):
        anchors = page.query_selector_all("a")
        p_links = [a for a in anchors if a.get_attribute("href") and ("/p/" in a.get_attribute("href") or "/reel/" in a.get_attribute("href"))]

        for a in p_links:
            post_href = a.get_attribute("href")
            img = a.query_selector("img")
            if not img:
                continue

            src = img.get_attribute("src")
            srcset = img.get_attribute("srcset")
            alt = img.get_attribute("alt") or "Sem legenda"

            # Pega a melhor resolução do srcset (1080x1080)
            best_url = src
            if srcset:
                parts = srcset.split(",")
                best_url = parts[-1].strip().split(" ")[0]

            if best_url and best_url.startswith("http") and best_url not in seen_urls:
                seen_urls.add(best_url)
                full_post_url = f"https://www.instagram.com{post_href}" if post_href.startswith("/") else post_href
                midias_coletadas.append({
                    "id": len(midias_coletadas) + 1,
                    "post_url": full_post_url,
                    "url": best_url,
                    "legenda": alt
                })

        # Rola a página para baixo de forma suave como um usuário de desktop
        page.evaluate("window.scrollBy(0, 1000)")
        page.wait_for_timeout(1800)

    feed_baixados = []
    if midias_coletadas:
        print(f"  [+] Total de {len(midias_coletadas)} foto(s) identificada(s) no feed! Baixando arquivos...")
        for idx, item in enumerate(midias_coletadas, 1):
            try:
                res = requests.get(item["url"], timeout=15)
                if res.status_code == 200:
                    filepath = os.path.join(pasta_destino, f"foto_{idx}.jpg")
                    with open(filepath, "wb") as f:
                        f.write(res.content)
                    item["arquivo_local"] = filepath
                    feed_baixados.append(filepath)
                    print(f"    [>] Baixada foto {idx}/{len(midias_coletadas)}")
            except Exception as err:
                print(f"    [-] Erro ao baixar foto {idx}: {err}")
    else:
        print(f"  [-] Nenhuma foto localizada na grade do feed.")

    # 5. RELATÓRIO JSON CONSOLIDADO
    dados_completos = {
        "username": username_alvo,
        "avatar_salvo": avatar_salvo,
        "contadores": {
            "posts": posts_count,
            "seguidores": seguidores,
            "seguindo": seguindo
        },
        "links_bio": links,
        "total_destaques_baixados": len(destaques_coletados),
        "destaques_arquivos": destaques_coletados,
        "total_stories_baixados": len(stories_coletados),
        "stories_arquivos": stories_coletados,
        "total_fotos_feed": len(feed_baixados),
        "feed": midias_coletadas
    }

    json_path = os.path.join(pasta_destino, "dados_perfil.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dados_completos, f, ensure_ascii=False, indent=4)

    total_arquivos = len(feed_baixados) + len(destaques_coletados) + len(stories_coletados)
    if avatar_salvo:
        total_arquivos += 1

    status_final = "CONCLUIDO" if total_arquivos > 0 else "VAZIO"
    registrar_coleta_db(username_alvo, pasta_destino, total_arquivos, status_final)

    print("\n" + "="*60)
    print(f"[✔] DOWNLOAD COMPLETO FINALIZADO PARA @{username_alvo}!")
    print(f"  - Bio & Dados: Salvos em bio.txt e dados_perfil.json")
    print(f"  - Feed: {len(feed_baixados)} fotos baixadas")
    print(f"  - Destaques: {len(destaques_coletados)} arquivos salvos")
    print(f"  - Stories (24h): {len(stories_coletados)} arquivos salvos")
    print(f"  - Total geral: {total_arquivos} arquivos em {pasta_destino}")
    print("="*60)
    return total_arquivos


# =====================================================================
# FLUXOS DE OPERAÇÃO DO MENU
# =====================================================================

def fluxo_seguir_alvo():
    """Acessa o perfil, clica no botão oficial de Seguir no PC e registra no monitoramento."""
    cfg = carregar_config()
    target = input("\n>> Digite o username do alvo a seguir (sem @): ").strip().replace("@", "")
    if not target:
        print("Username inválido.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = criar_contexto_desktop(browser, cfg)
        page = ctx.new_page()

        info = obter_info_perfil(page, target)
        print("\n" + "="*50)
        print(f" Perfil: @{target}")
        print(f" Privado: {'SIM 🔒' if info['is_private'] else 'NÃO 🌐'}")
        print(f" Situação: {info['button_status']}")
        print("="*50)

        if info["button_status"] == "SEGUINDO":
            print(f"[i] Você já segue @{target}! O feed já está acessível.")
            registrar_novo_alvo(target, is_private=info["is_private"])
            baixar_agora = input("Deseja baixar as fotos agora? (s/n): ").strip().lower()
            if baixar_agora in ["s", "sim", "y"]:
                extrair_e_baixar_fotos(page, target)
            browser.close()
            return

        if info["button_status"] == "SOLICITADO":
            print(f"[⏳] A solicitação já foi enviada anteriormente e está pendente de aprovação.")
            registrar_novo_alvo(target, is_private=info["is_private"])
            browser.close()
            return

        # Botão está disponível para seguir
        confirma = input(f"\n>> Deseja enviar a solicitação para @{target}? (s/n): ").strip().lower()
        if confirma in ["s", "sim", "y"]:
            print(f"[*] Clicando no botão oficial de seguir pelo Chrome Desktop...")
            clicked = False
            for btn in page.query_selector_all("header button, main header button, button"):
                txt = (btn.inner_text() or "").strip().lower()
                if txt in ["follow", "seguir"]:
                    btn.click()
                    clicked = True
                    break
            
            page.wait_for_timeout(3000)
            if clicked:
                print(f"[+] Solicitação enviada com sucesso para @{target}!")
                registrar_novo_alvo(target, is_private=info["is_private"])
            else:
                print(f"[-] Não foi possível localizar o botão de seguir.")
        else:
            print("[i] Ação cancelada.")

        browser.close()

def fluxo_verificar_e_baixar():
    """Varre a lista de alvos não concluídos. Se aceito ou seguindo, baixa tudo automaticamente."""
    alvos = carregar_alvos()
    pendentes = [a for a in alvos if a.get("status") != "CONCLUIDO"]
    
    if not pendentes:
        print("\n[i] Todos os alvos registrados já foram baixados e concluídos!")
        return

    print(f"\n[+] Verificando {len(pendentes)} alvo(s) em monitoramento...")
    cfg = carregar_config()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = criar_contexto_desktop(browser, cfg)
        page = ctx.new_page()

        for alvo in pendentes:
            username = alvo["username"]
            print(f"\n--- Checando status de @{username} ---")
            info = obter_info_perfil(page, username)

            if info["button_status"] == "SEGUINDO" or not info["is_private"]:
                print(f"[🎉] SUCESSO! O perfil @{username} está ACESSÍVEL (Solicitação Aceita)! ")
                print(f"[*] Disparando download automático de todo o conteúdo...")
                
                qtd = extrair_e_baixar_fotos(page, username)
                alvo["status"] = "CONCLUIDO"
                alvo["qtd_fotos_baixadas"] = qtd
                alvo["concluido_em"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                salvar_alvos(alvos)
            elif info["button_status"] == "SOLICITADO":
                print(f"[⏳] @{username} ainda não aceitou a solicitação. Continuando monitoramento.")
            else:
                print(f"[!] Situação atual de @{username}: {info['button_status']}")

        browser.close()

def fluxo_baixar_direto():
    """Baixa fotos de qualquer perfil que já esteja aberto ou aprovado."""
    target = input("\n>> Digite o username do perfil a baixar (sem @): ").strip().replace("@", "")
    if not target:
        return
        
    cfg = carregar_config()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = criar_contexto_desktop(browser, cfg)
        page = ctx.new_page()
        
        info = obter_info_perfil(page, target)
        if info["is_private"] and info["button_status"] != "SEGUINDO":
            print(f"[!] O perfil @{target} é privado e você ainda não foi aceito. Envie a solicitação primeiro pela opção [1].")
        else:
            scrolls_input = input(">> Quantas rolagens de tela fazer no feed? (Padrão 6, cada rolagem traz ~12 fotos): ").strip()
            max_s = int(scrolls_input) if scrolls_input.isdigit() else 6
            extrair_e_baixar_fotos(page, target, max_scrolls=max_s)
            
        browser.close()

def fluxo_historico():
    """Exibe alvos monitorados e histórico salvo."""
    alvos = carregar_alvos()
    print("\n" + "="*75)
    print(f"{'ALVO':<22} | {'STATUS':<24} | {'SOLICITADO EM'}")
    print("="*75)
    if not alvos:
        print(" Nenhum alvo registrado ainda.")
    else:
        for a in alvos:
            print(f"@{a['username']:<21} | {a['status']:<24} | {a.get('solicitado_em', '-')}")
    print("="*75)

def fluxo_configuracao():
    """Permite alterar o sessionid ou dados da conta direto no terminal."""
    cfg = carregar_config()
    print("\n" + "="*50)
    print(" 🔑 CONFIGURAÇÃO DA CONTA FONTOCHE (DESKTOP)")
    print("="*50)
    print(f" Usuário: @{cfg.get('user')}")
    print(f" ID do Usuário: {cfg.get('ds_user_id')}")
    print(f" SessionID atual: {cfg.get('sessionid')[:35]}...")
    print("--------------------------------------------------")
    novo_sess = input("Cole o novo SessionID (ou aperte Enter para manter): ").strip()
    if novo_sess:
        cfg["sessionid"] = novo_sess
        # Atualiza ds_user_id se puder extrair do sessionid
        if "%3A" in novo_sess or ":" in novo_sess:
            uid = novo_sess.split("%3A")[0].split(":")[0]
            if uid.isdigit():
                cfg["ds_user_id"] = uid
        salvar_config(cfg)
        print("[+] SessionID atualizado com sucesso!")

# =====================================================================
# MENU PRINCIPAL
# =====================================================================
def main():
    carregar_config()
    inicializar_banco()
    
    while True:
        print("\n" + "╔" + "═"*58 + "╗")
        print("║       🕵️‍♂️ SHARLOK INSTA - DESKTOP AUTOMATION (PC)         ║")
        print("║          Follow, Monitoramento & Scraper Automático      ║")
        print("╚" + "═"*58 + "╝")
        print(" [1] 🎯 Enviar Solicitação para Alvo Privado & Monitorar")
        print(" [2] 🔄 Verificar se Alvos Aceitaram & Baixar Fotos Auto")
        print(" [3] ⚡ Baixar Perfil Agora (Alvos Já Aceitos ou Públicos)")
        print(" [4] 📋 Ver Histórico de Alvos e Downloads")
        print(" [5] 🔑 Configurar / Atualizar SessionID da Conta")
        print(" [0] 🚪 Sair")
        
        escolha = input("\n>> Escolha uma opção [0-5]: ").strip()
        
        if escolha == "1":
            fluxo_seguir_alvo()
        elif escolha == "2":
            fluxo_verificar_e_baixar()
        elif escolha == "3":
            fluxo_baixar_direto()
        elif escolha == "4":
            fluxo_historico()
        elif escolha == "5":
            fluxo_configuracao()
        elif escolha == "0":
            print("\nEncerrando SharlokInsta Desktop. Até logo!\n")
            sys.exit(0)
        else:
            print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    main()
