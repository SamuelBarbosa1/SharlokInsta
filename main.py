import os
import sys
import time
import json
import sqlite3
import random
import requests
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# Força UTF-8 no console Windows para evitar UnicodeEncodeError
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# =====================================================================
# CONFIGURAÇÕES DA CONTA & POOL DE CONTAS (DESKTOP)
# =====================================================================
CONFIG_FILE = "config_conta.json"
CONTAS_POOL_FILE = "contas_pool.json"
MONITOR_FILE = "alvos_monitorados.json"
DB_NAME = "osint_coletas.db"
ENV_FILE = ".env"

# Cooldown entre tentativas de contas diferentes após uma recusa
# (Ajustado para 3 MINUTOS para testes rápidos! Altere para 60 ou 120 min para produção)
COOLDOWN_MINUTOS = 3


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
    """Carrega configurações da conta principal priorizando .env e com fallback em config_conta.json."""
    carregar_dotenv()
    cfg = {
        "user": os.getenv("IG_USER", ""),
        "ds_user_id": os.getenv("IG_DS_USER_ID", ""),
        "sessionid": os.getenv("IG_SESSIONID", "")
    }

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for k in ["user", "ds_user_id", "sessionid"]:
                    if not cfg.get(k) and saved.get(k):
                        cfg[k] = saved[k]
        except Exception:
            pass

    if cfg.get("sessionid") and not cfg.get("ds_user_id"):
        uid = cfg["sessionid"].split("%3A")[0].split(":")[0]
        if uid.isdigit():
            cfg["ds_user_id"] = uid

    return cfg

def salvar_config(cfg):
    """Salva as credenciais no .env e no config_conta.json local."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
    except Exception:
        pass

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
# GERENCIAMENTO DO POOL DE MÚLTIPLAS CONTAS
# =====================================================================
def carregar_pool_contas():
    """Carrega todas as contas do pool. Se não existir, migra a conta do .env automaticamente."""
    if os.path.exists(CONTAS_POOL_FILE):
        try:
            with open(CONTAS_POOL_FILE, "r", encoding="utf-8") as f:
                contas = json.load(f)
                if isinstance(contas, list) and len(contas) > 0:
                    return contas
        except Exception:
            pass

    # Migração automática inicial da conta existente
    cfg = carregar_config()
    contas = []
    if cfg.get("sessionid"):
        contas.append({
            "id": 1,
            "user": cfg.get("user") or "conta_1",
            "ds_user_id": cfg.get("ds_user_id", ""),
            "sessionid": cfg.get("sessionid", ""),
            "ativo": True,
            "adicionado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        salvar_pool_contas(contas)
    return contas

def salvar_pool_contas(contas):
    """Salva o pool de contas no arquivo contas_pool.json."""
    with open(CONTAS_POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(contas, f, indent=4, ensure_ascii=False)

def obter_conta_ativa():
    """Retorna a primeira conta ativa e configurada do pool."""
    pool = carregar_pool_contas()
    for c in pool:
        if c.get("ativo", True) and c.get("sessionid"):
            return c
    if pool:
        return pool[0]
    return carregar_config()

def obter_conta_por_user(username):
    """Retorna os dados da conta no pool pelo nome de usuário."""
    pool = carregar_pool_contas()
    for c in pool:
        if c.get("user", "").lower() == username.lower():
            return c
    return None

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
# GESTÃO DE ALVOS MONITORADOS (JSON COM SUPORTE A CASCATA)
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

def registrar_novo_alvo(username, is_private=True, conta_usada=None):
    """Registra ou atualiza um alvo, gravando a conta responsável e o histórico de tentativas."""
    alvos = carregar_alvos()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not conta_usada:
        c_ativa = obter_conta_ativa()
        conta_usada = c_ativa.get("user", "desconhecido")

    # Verifica se já existe
    for a in alvos:
        if a["username"].lower() == username.lower():
            a["is_private"] = is_private
            a["status"] = "AGUARDANDO_APROVACAO"
            a["conta_atual"] = conta_usada
            a["atualizado_em"] = agora

            if "tentativas" not in a or not isinstance(a["tentativas"], list):
                a["tentativas"] = []
            a["tentativas"].append({
                "conta": conta_usada,
                "solicitado_em": agora,
                "status": "SOLICITADO"
            })
            salvar_alvos(alvos)
            return

    alvos.append({
        "username": username,
        "is_private": is_private,
        "status": "AGUARDANDO_APROVACAO",
        "conta_atual": conta_usada,
        "tentativas": [
            {
                "conta": conta_usada,
                "solicitado_em": agora,
                "status": "SOLICITADO"
            }
        ],
        "cooldown_ate": None,
        "solicitado_em": agora,
        "atualizado_em": agora
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
    is_private = (
        "this profile is private" in content or
        "este perfil é privado" in content or
        "this account is private" in content or
        "esta conta é privada" in content or
        "follow to see their photos and videos" in content or
        "siga para ver suas fotos e vídeos" in content or
        "siga para ver suas fotos" in content
    )

    
    # Detecta estado do botão de seguir
    btn_status = "Desconhecido"
    buttons = page.query_selector_all("header button, main header button, button")
    for btn in buttons:
        txt = (btn.inner_text() or "").strip().lower()
        if txt in ["follow", "seguir"]:
            btn_status = "NAO_SEGUINDO"
            break
        elif txt in ["requested", "solicitado", "solicitação enviada", "solicitada", "pedindo"]:
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
# AUXILIARES DE ENVIO DE FOLLOW COM CONTA ESPECÍFICA
# =====================================================================
def enviar_follow_com_conta(browser, conta_cfg, target_username):
    """Abre contexto isolado com a conta do pool especificada e envia a solicitação de follow."""
    ctx = criar_contexto_desktop(browser, conta_cfg)
    page = ctx.new_page()
    resultado = "FALHA"
    try:
        info = obter_info_perfil(page, target_username)
        if info["button_status"] == "SEGUINDO":
            resultado = "JA_SEGUINDO"
        elif info["button_status"] == "SOLICITADO":
            resultado = "JA_SOLICITADO"
        else:
            clicked = False
            for btn in page.query_selector_all("header button, main header button, button"):
                txt = (btn.inner_text() or "").strip().lower()
                if txt in ["follow", "seguir"]:
                    btn.click()
                    clicked = True
                    break
            page.wait_for_timeout(3000)
            if clicked:
                resultado = "SUCESSO"
    except Exception as e:
        print(f"  [-] Erro ao enviar follow: {e}")
        resultado = "ERRO"
    finally:
        ctx.close()
    return resultado

# =====================================================================
# FLUXOS DE OPERAÇÃO DO MENU
# =====================================================================

def fluxo_seguir_alvo():
    """Acessa o perfil, clica no botão de Seguir e registra no monitoramento com a conta escolhida."""
    pool = carregar_pool_contas()
    contas_ativas = [c for c in pool if c.get("ativo", True) and c.get("sessionid")]
    
    if not contas_ativas:
        print("\n[!] Nenhuma conta ativa encontrada no Pool! Configure uma conta na opção [5] primeiro.")
        return

    # Se tiver mais de uma conta ativa, permite escolher qual usar
    conta_selecionada = contas_ativas[0]
    if len(contas_ativas) > 1:
        print("\n--- Selecione a conta fantoche para iniciar a abordagem ---")
        for idx, c in enumerate(contas_ativas, 1):
            print(f" [{idx}] @{c.get('user', 'conta')} (ID: {c.get('id')})")
        escolha_c = input(f">> Escolha a conta [1-{len(contas_ativas)}] (Padrão 1): ").strip()
        if escolha_c.isdigit() and 1 <= int(escolha_c) <= len(contas_ativas):
            conta_selecionada = contas_ativas[int(escolha_c) - 1]

    target = input("\n>> Digite o username do alvo a seguir (sem @): ").strip().replace("@", "")
    if not target:
        print("Username inválido.")
        return

    print(f"[*] Usando conta @{conta_selecionada.get('user')} para abordar @{target}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = criar_contexto_desktop(browser, conta_selecionada)
        page = ctx.new_page()

        info = obter_info_perfil(page, target)
        print("\n" + "="*50)
        print(f" Perfil Alvo: @{target}")
        print(f" Privado: {'SIM 🔒' if info['is_private'] else 'NÃO 🌐'}")
        print(f" Situação: {info['button_status']}")
        print(f" Conta Abordando: @{conta_selecionada.get('user')}")
        print("="*50)

        if info["button_status"] == "SEGUINDO":
            print(f"[i] A conta @{conta_selecionada.get('user')} já segue @{target}! O feed já está acessível.")
            baixar_agora = input("Deseja baixar o conteúdo agora? (s/n): ").strip().lower()
            if baixar_agora in ["s", "sim", "y"]:
                extrair_e_baixar_fotos(page, target)
            browser.close()
            return

        if info["button_status"] == "SOLICITADO":
            print(f"[⏳] A solicitação já foi enviada anteriormente e está pendente de aprovação.")
            registrar_novo_alvo(target, is_private=info["is_private"], conta_usada=conta_selecionada.get("user"))
            browser.close()
            return

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
                print(f"[+] Solicitação enviada com sucesso para @{target} usando @{conta_selecionada.get('user')}!")
                registrar_novo_alvo(target, is_private=info["is_private"], conta_usada=conta_selecionada.get("user"))
            else:
                print(f"[-] Não foi possível localizar o botão de seguir.")
        else:
            print("[i] Ação cancelada.")

        browser.close()

def fluxo_verificar_e_baixar():
    """
    Varre alvos em monitoramento:
    - Se aceito: baixa tudo automaticamente.
    - Se recusado: ativa cooldown de 2 horas.
    - Se cooldown terminou: passa para a próxima conta ativa do pool em cascata.
    """
    alvos = carregar_alvos()
    pendentes = [a for a in alvos if a.get("status") not in ["CONCLUIDO", "ESGOTADO"]]

    if not pendentes:
        print("\n[i] Não há alvos pendentes no momento (todos concluídos ou esgotados).")
        return

    print(f"\n[+] Verificando {len(pendentes)} alvo(s) em monitoramento...")
    pool = carregar_pool_contas()
    agora = datetime.now()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for alvo in pendentes:
            username = alvo["username"]
            status_atual = alvo.get("status", "AGUARDANDO_APROVACAO")
            conta_nome = alvo.get("conta_atual")
            conta_cfg = obter_conta_por_user(conta_nome) if conta_nome else obter_conta_ativa()

            if not conta_cfg or not conta_cfg.get("sessionid"):
                conta_cfg = obter_conta_ativa()

            print(f"\n--- Checando @{username} (Status: {status_atual}) ---")

            # ---------------------------------------------------------
            # CENÁRIO 1: ALVO AGUARDANDO APROVAÇÃO
            # ---------------------------------------------------------
            if status_atual in ["AGUARDANDO_APROVACAO", "SEGUINDO"]:
                ctx = criar_contexto_desktop(browser, conta_cfg)
                page = ctx.new_page()
                try:
                    info = obter_info_perfil(page, username)
                    btn_st = info["button_status"]

                    # Caso A: Foi aceito
                    if btn_st == "SEGUINDO":
                        print(f"[🎉] SUCESSO! @{username} ACEITOU a solicitação de @{conta_cfg.get('user')}!")
                        print(f"[*] Disparando download automático de todo o conteúdo...")
                        qtd = extrair_e_baixar_fotos(page, username)
                        alvo["status"] = "CONCLUIDO"
                        alvo["qtd_fotos_baixadas"] = qtd
                        alvo["concluido_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")

                        # Atualiza histórico de tentativas
                        if "tentativas" in alvo and alvo["tentativas"]:
                            alvo["tentativas"][-1]["status"] = "ACEITO"
                        salvar_alvos(alvos)

                    # Caso B: Ainda pendente
                    elif btn_st == "SOLICITADO":
                        print(f"[⏳] @{username} ainda não respondeu à solicitação de @{conta_cfg.get('user')}. Continuando espera.")

                    # Caso C: Botão voltou para 'Seguir' -> RECUSA DETECTADA!
                    elif btn_st == "NAO_SEGUINDO":
                        cooldown_limite = agora + timedelta(minutes=COOLDOWN_MINUTOS)
                        cooldown_str = cooldown_limite.strftime("%Y-%m-%d %H:%M:%S")
                        alvo["status"] = "REJEITADO_COOLDOWN"
                        alvo["cooldown_ate"] = cooldown_str

                        # Marca recusa no histórico de tentativas
                        if "tentativas" not in alvo or not isinstance(alvo["tentativas"], list):
                            alvo["tentativas"] = []
                        if alvo["tentativas"]:
                            alvo["tentativas"][-1]["status"] = "REJEITADO"
                            alvo["tentativas"][-1]["rejeitado_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")

                        salvar_alvos(alvos)
                        print(f"[🚫] RECUSA DETECTADA! @{username} recusou a solicitação de @{conta_cfg.get('user')}.")
                        print(f"[⏳] Entrando em cooldown de {COOLDOWN_MINUTOS} min. Próxima conta poderá tentar a partir de: {cooldown_str}")

                    else:
                        print(f"[!] Situação atual de @{username}: {btn_st}")
                finally:
                    ctx.close()

            # ---------------------------------------------------------
            # CENÁRIO 2: ALVO EM COOLDOWN DE REJEIÇÃO
            # ---------------------------------------------------------
            elif status_atual == "REJEITADO_COOLDOWN":
                cooldown_str = alvo.get("cooldown_ate")
                cooldown_expirado = False

                if cooldown_str:
                    try:
                        cooldown_dt = datetime.strptime(cooldown_str, "%Y-%m-%d %H:%M:%S")
                        if agora >= cooldown_dt:
                            cooldown_expirado = True
                        else:
                            restante = cooldown_dt - agora
                            total_segs = int(restante.total_seconds())
                            min_rest, seg_rest = divmod(total_segs, 60)
                            horas_rest, min_rest = divmod(min_rest, 60)
                            tempo_formatado = f"{horas_rest}h {min_rest}m" if horas_rest > 0 else f"{min_rest}m {seg_rest}s"
                            print(f"[⏳] @{username} ainda em cooldown após recusa. Tempo restante: {tempo_formatado} (até {cooldown_str}).")
                    except Exception:
                        cooldown_expirado = True
                else:
                    cooldown_expirado = True

                # Se o cooldown terminou, aciona a cascata para a próxima conta
                if cooldown_expirado:
                    print(f"[🚀] Cooldown de {COOLDOWN_MINUTOS} min finalizado para @{username}! Procurando próxima conta no pool...")


                    # Descobre quais contas já foram recusadas para esse alvo
                    contas_recusadas = [t.get("conta", "").lower() for t in alvo.get("tentativas", []) if t.get("status") == "REJEITADO"]

                    # Contas disponíveis que ainda não foram recusadas
                    candidatas = [c for c in pool if c.get("ativo", True) and c.get("sessionid") and c.get("user", "").lower() not in contas_recusadas]

                    if candidatas:
                        proxima_conta = candidatas[0]
                        print(f"[*] Nova tentativa em cascata: enviando follow via @{proxima_conta.get('user')}...")
                        res_follow = enviar_follow_com_conta(browser, proxima_conta, username)

                        if res_follow in ["SUCESSO", "JA_SOLICITADO"]:
                            alvo["conta_atual"] = proxima_conta.get("user")
                            alvo["status"] = "AGUARDANDO_APROVACAO"
                            alvo["cooldown_ate"] = None
                            if "tentativas" not in alvo or not isinstance(alvo["tentativas"], list):
                                alvo["tentativas"] = []
                            alvo["tentativas"].append({
                                "conta": proxima_conta.get("user"),
                                "solicitado_em": agora.strftime("%Y-%m-%d %H:%M:%S"),
                                "status": "SOLICITADO"
                            })
                            salvar_alvos(alvos)
                            print(f"[+] Nova solicitação enviada com sucesso para @{username} pela conta @{proxima_conta.get('user')}!")
                        elif res_follow == "JA_SEGUINDO":
                            print(f"[🎉] A conta @{proxima_conta.get('user')} já segue @{username}! Baixando conteúdo...")
                            ctx = criar_contexto_desktop(browser, proxima_conta)
                            page = ctx.new_page()
                            qtd = extrair_e_baixar_fotos(page, username)
                            ctx.close()
                            alvo["status"] = "CONCLUIDO"
                            alvo["concluido_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")
                            salvar_alvos(alvos)
                        else:
                            print(f"[-] Não foi possível enviar solicitação via @{proxima_conta.get('user')} ({res_follow}).")
                    else:
                        alvo["status"] = "ESGOTADO"
                        salvar_alvos(alvos)
                        print(f"[-] Todas as contas disponíveis no pool ({len(pool)}) foram recusadas por @{username}. Alvo finalizado como ESGOTADO.")

        browser.close()

def fluxo_baixar_direto():
    """Baixa fotos de qualquer perfil que já esteja aberto ou aprovado."""
    target = input("\n>> Digite o username do perfil a baixar (sem @): ").strip().replace("@", "")
    if not target:
        return

    conta_ativa = obter_conta_ativa()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = criar_contexto_desktop(browser, conta_ativa)
        page = ctx.new_page()

        info = obter_info_perfil(page, target)
        if info["is_private"] and info["button_status"] != "SEGUINDO":
            print(f"[!] O perfil @{target} é privado e a conta @{conta_ativa.get('user')} ainda não foi aceita.")
            print("Envie a solicitação primeiro pela opção [1].")
        else:
            scrolls_input = input(">> Quantas rolagens de tela fazer no feed? (Padrão 6, cada rolagem traz ~12 fotos): ").strip()
            max_s = int(scrolls_input) if scrolls_input.isdigit() else 6
            extrair_e_baixar_fotos(page, target, max_scrolls=max_s)

        browser.close()

def fluxo_historico():
    """Exibe alvos monitorados, status detalhado da cascata e histórico salvo."""
    alvos = carregar_alvos()
    print("\n" + "="*85)
    print(f"{'ALVO':<18} | {'STATUS':<20} | {'CONTA ATUAL':<18} | {'COOLDOWN ATÉ / INFO'}")
    print("="*85)
    if not alvos:
        print(" Nenhum alvo registrado ainda.")
    else:
        for a in alvos:
            status = a.get("status", "-")
            u_alvo = f"@{a['username']}"
            c_atual = f"@{a.get('conta_atual', '-')}"
            info_extra = "-"
            if status == "REJEITADO_COOLDOWN":
                info_extra = f"Até {a.get('cooldown_ate', '-')}"
            elif status == "CONCLUIDO":
                info_extra = f"Concluído ({a.get('qtd_fotos_baixadas', 0)} mídias)"
            elif status == "ESGOTADO":
                info_extra = "Todas as contas recusadas"
            elif status == "AGUARDANDO_APROVACAO":
                tentativas_qtd = len(a.get("tentativas", []))
                info_extra = f"Tentativa #{tentativas_qtd}"

            print(f"{u_alvo:<18} | {status:<20} | {c_atual:<18} | {info_extra}")
    print("="*85)

# =====================================================================
# GERENCIAMENTO DO POOL DE CONTAS (SUBMENU)
# =====================================================================
def fluxo_gerenciar_pool():
    """Submenu para visualizar, adicionar, ativar/desativar e testar contas do pool."""
    while True:
        contas = carregar_pool_contas()
        print("\n" + "="*70)
        print(" 👥 GERENCIADOR DE POOL DE CONTAS (DESKTOP)")
        print("="*70)
        if not contas:
            print(" Nenhuma conta cadastrada no pool.")
        else:
            for c in contas:
                status_txt = "ATIVA ✔️" if c.get("ativo", True) else "INATIVA ❌"
                sess_preview = c.get("sessionid", "")[:28] + "..." if c.get("sessionid") else "Sem sessionid"
                print(f" [{c['id']}] @{c.get('user', 'sem_user'):<18} | {status_txt:<12} | {sess_preview}")
        print("="*70)
        print(" [1] ➕ Adicionar Nova Conta Fantoche ao Pool")
        print(" [2] 🔄 Alternar Status (Ativar / Desativar Conta)")
        print(" [3] ✏️ Atualizar SessionID de uma Conta Existente")
        print(" [4] 🧪 Testar Login de Todas as Contas do Pool")
        print(" [0] 🔙 Voltar ao Menu Principal")

        opc = input("\n>> Escolha uma opção [0-4]: ").strip()

        if opc == "1":
            user_novo = input("\n>> Digite o username da nova conta (sem @): ").strip().replace("@", "")
            if not user_novo:
                print("Username inválido.")
                continue
            sess_novo = input(">> Cole o SessionID da nova conta: ").strip()
            if not sess_novo:
                print("SessionID não pode ser vazio.")
                continue

            uid_novo = ""
            if "%3A" in sess_novo or ":" in sess_novo:
                uid_part = sess_novo.split("%3A")[0].split(":")[0]
                if uid_part.isdigit():
                    uid_novo = uid_part

            novo_id = max([c.get("id", 0) for c in contas], default=0) + 1
            contas.append({
                "id": novo_id,
                "user": user_novo,
                "ds_user_id": uid_novo,
                "sessionid": sess_novo,
                "ativo": True,
                "adicionado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            salvar_pool_contas(contas)
            print(f"\n[✔] Conta @{user_novo} adicionada ao Pool com sucesso (ID #{novo_id})!")

        elif opc == "2":
            if not contas:
                print("Não há contas para alterar.")
                continue
            id_input = input(">> Digite o ID da conta a alternar (Ativar/Desativar): ").strip()
            if id_input.isdigit():
                alvo_id = int(id_input)
                encontrou = False
                for c in contas:
                    if c.get("id") == alvo_id:
                        c["ativo"] = not c.get("ativo", True)
                        novo_st = "ATIVA ✔️" if c["ativo"] else "INATIVA ❌"
                        salvar_pool_contas(contas)
                        print(f"[+] Status da conta @{c.get('user')} alterado para: {novo_st}")
                        encontrou = True
                        break
                if not encontrou:
                    print("ID não encontrado.")

        elif opc == "3":
            if not contas:
                print("Não há contas para editar.")
                continue
            id_input = input(">> Digite o ID da conta que deseja atualizar o SessionID: ").strip()
            if id_input.isdigit():
                alvo_id = int(id_input)
                conta_alvo = next((c for c in contas if c.get("id") == alvo_id), None)
                if conta_alvo:
                    novo_s = input(f">> Cole o novo SessionID para @{conta_alvo.get('user')}: ").strip()
                    if novo_s:
                        conta_alvo["sessionid"] = novo_s
                        if "%3A" in novo_s or ":" in novo_s:
                            uid = novo_s.split("%3A")[0].split(":")[0]
                            if uid.isdigit():
                                conta_alvo["ds_user_id"] = uid
                        salvar_pool_contas(contas)
                        print("[+] SessionID atualizado com sucesso!")
                else:
                    print("ID não encontrado.")

        elif opc == "4":
            print("\n[*] Testando conexão e autenticação de cada conta do pool...")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                for c in contas:
                    print(f"  [*] Testando sessão de @{c.get('user')}...")
                    ctx = criar_contexto_desktop(browser, c)
                    page = ctx.new_page()
                    try:
                        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
                        page.wait_for_timeout(3000)
                        content = page.content().lower()
                        # Se estiver na página de login, sessão expirou
                        if "accounts/login" in page.url or "cadastre-se" in content and "entrar" in content and "feed" not in content:
                            print(f"  [❌] @{c.get('user')}: Sessão expirada ou deslogada.")
                        else:
                            print(f"  [✔] @{c.get('user')}: Sessão ATIVA e conectada com sucesso!")
                    except Exception as e:
                        print(f"  [-] Erro ao testar @{c.get('user')}: {e}")
                    finally:
                        ctx.close()
                browser.close()
            print("[*] Testes finalizados.")

        elif opc == "0":
            break

# =====================================================================
# MODO SENTINELA (LOOP AUTOMÁTICO 24/7)
# =====================================================================
def modo_sentinela():
    """Executa checagens periódicas automáticas de alvos e cascata sem intervenção manual."""
    print("\n" + "╔" + "═"*62 + "╗")
    print("║                 👁️ MODO SENTINELA ATIVO (24/7)              ║")
    print("║     Monitoramento Contínuo, Cascata e Download Automático    ║")
    print("╚" + "═"*62 + "╝")

    intervalo_input = input(">> Intervalo entre checagens em minutos (Padrão 30): ").strip()
    intervalo_min = int(intervalo_input) if intervalo_input.isdigit() and int(intervalo_input) > 0 else 30
    intervalo_seg = intervalo_min * 60

    print(f"\n[*] Modo Sentinela iniciado! Intervalo de checagem: {intervalo_min} minutos.")
    print("[*] Pressione Ctrl + C a qualquer momento para pausar e voltar ao menu principal.\n")

    ciclo = 1
    try:
        while True:
            agora_str = datetime.now().strftime("%H:%M:%S")
            print("="*65)
            print(f"[{agora_str}] [Ciclo #{ciclo}] Executando verificação de alvos...")
            print("="*65)

            try:
                fluxo_verificar_e_baixar()
            except Exception as e:
                print(f"[-] Ocorreu um erro durante a verificação no ciclo #{ciclo}: {e}")

            proxima_hora = (datetime.now() + timedelta(seconds=intervalo_seg)).strftime("%H:%M:%S")
            print(f"\n[💤] Ciclo #{ciclo} concluído. Próxima checagem automática às {proxima_hora}...")

            # Aguarda o intervalo dormindo em passos de 1s para responder de imediato ao Ctrl+C
            for _ in range(intervalo_seg):
                time.sleep(1)

            ciclo += 1
    except KeyboardInterrupt:
        print("\n\n[i] Modo Sentinela pausado pelo usuário. Retornando ao menu principal...\n")
        time.sleep(1)

# =====================================================================
# MENU PRINCIPAL
# =====================================================================
def main():
    inicializar_banco()
    carregar_pool_contas()

    while True:
        print("\n" + "╔" + "═"*58 + "╗")
        print("║       🕵️‍♂️ SHARLOK INSTA - DESKTOP AUTOMATION (PC)         ║")
        print("║       Multi-Contas, Cascata & Monitoramento Sentinela    ║")
        print("╚" + "═"*58 + "╝")
        print(" [1] 🎯 Enviar Solicitação para Alvo Privado & Monitorar")
        print(" [2] 🔄 Verificar Solicitações & Cascata de Rejeição")
        print(" [3] ⚡ Baixar Perfil Agora (Alvos Já Aceitos ou Públicos)")
        print(" [4] 📋 Ver Histórico de Alvos e Status da Cascata")
        print(" [5] 👥 Gerenciar Pool de Contas (Adicionar Conta 2, Listar)")
        print(" [6] 👁️ Iniciar Modo Sentinela (Loop Automático 24/7)")
        print(" [0] 🚪 Sair")

        escolha = input("\n>> Escolha uma opção [0-6]: ").strip()

        if escolha == "1":
            fluxo_seguir_alvo()
        elif escolha == "2":
            fluxo_verificar_e_baixar()
        elif escolha == "3":
            fluxo_baixar_direto()
        elif escolha == "4":
            fluxo_historico()
        elif escolha == "5":
            fluxo_gerenciar_pool()
        elif escolha == "6":
            modo_sentinela()
        elif escolha == "0":
            print("\nEncerrando SharlokInsta Desktop. Até logo!\n")
            sys.exit(0)
        else:
            print("Opção inválida. Tente novamente.")

if __name__ == "__main__":
    main()

