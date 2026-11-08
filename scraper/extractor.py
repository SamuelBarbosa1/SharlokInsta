import os
import re
import json
import requests
from core.database import inicializar_banco, registrar_coleta_db


def _anexar_captura_videos_rede(aux_page, fila_videos):
    """Intercepta respostas de rede do player do Instagram para capturar URLs reais (.mp4) de vídeos blob:."""
    def _on_response(resp):
        try:
            u = resp.url or ""
            ct = (resp.headers.get("content-type") or "").lower()
            if (".mp4" in u or "video/mp4" in ct) and u.startswith(("http://", "https://")):
                clean_u = re.sub(r"[&?]byte(?:start|end)=\d+", "", u)
                if clean_u not in fila_videos:
                    fila_videos.append(clean_u)
            elif ("json" in ct or "graphql" in u or "/api/v1/" in u) and resp.status == 200:
                txt = resp.text()
                if "video_versions" in txt:
                    for m in re.findall(r'"video_versions"\s*:\s*\[\s*\{[^}]*?"url"\s*:\s*"([^"]+)"', txt):
                        v_url = m.encode("utf-8").decode("unicode_escape").replace("\\/", "/")
                        if v_url.startswith(("http://", "https://")) and v_url not in fila_videos:
                            fila_videos.append(v_url)
        except Exception:
            pass

    aux_page.on("response", _on_response)


def _fechar_modal(page, modal_el=None):
    """Fecha o modal de seguidores/seguindo com segurança."""
    try:
        btn_fechar = page.query_selector("div[role='dialog'] button svg[aria-label*='Fechar'], div[role='dialog'] button svg[aria-label*='Close'], div[role='dialog'] [aria-label*='Fechar']")
        if btn_fechar:
            btn_fechar.click()
            page.wait_for_timeout(500)
            return
    except Exception:
        pass
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
    except Exception:
        pass

def extrair_lista_usuarios_modal(page, username_alvo, tipo="followers", max_scrolls=12):
    """
    Abre o modal de seguidores (/followers/) ou seguindo (/following/),
    detecta se o perfil restringiu/privou o acesso às listas para evitar falsos positivos,
    rola a lista e extrai os @usernames.
    
    Retorna:
    {
        "status": "SUCESSO" | "RESTRITO" | "VAZIO" | "ERRO",
        "motivo": str,
        "usuarios": list
    }
    """
    tipo_label = "Seguidores" if tipo == "followers" else "Seguindo"
    print(f"  [*] Abrindo modal de {tipo_label} de @{username_alvo}...")

    # Termos de busca em PT e EN
    termos = ["followers", "seguidores"] if tipo == "followers" else ["following", "seguindo"]

    # 1. Tenta clicar no link que tem o texto correspondente (ex: '824 followers', '693 following')
    # evitando pegar o link de mútuos ('mutualOnly')
    clicado = page.evaluate("""(termos) => {
        const links = Array.from(document.querySelectorAll('header a, main header a, a[role="link"], a'));
        for (const a of links) {
            const href = a.getAttribute('href') || '';
            const txt = (a.innerText || '').toLowerCase();
            // Ignora o link de seguidores mútuos ("Followed by...")
            if (href.includes('mutualOnly') || href.includes('mutual')) continue;

            const bateu_texto = termos.some(t => txt.includes(t));
            const bateu_href = termos.some(t => href.includes('/' + t + '/') || href.endsWith('/' + t));

            if (bateu_texto || bateu_href) {
                a.click();
                return true;
            }
        }
        return false;
    }""", termos)

    if not clicado:
        # Fallback via Playwright selector direto
        for t in termos:
            try:
                el = page.query_selector(f"header a:has-text('{t}'), a[role='link']:has-text('{t}')")
                if el:
                    el.click()
                    clicado = True
                    break
            except Exception:
                pass

    if not clicado:
        print(f"  [-] Link de {tipo_label} não encontrado no perfil.")
        return {"status": "ERRO", "motivo": f"Link de {tipo_label} não localizado", "usuarios": []}

    page.wait_for_timeout(2500)

    # Aguarda o modal aparecer
    modal_el = None
    try:
        page.wait_for_selector("div[role='dialog']", timeout=5000)
        modal_el = page.query_selector("div[role='dialog']")
    except Exception:
        print(f"  [-] Modal de {tipo_label} não abriu dentro do tempo esperado.")
        return {"status": "ERRO", "motivo": "Modal não abriu", "usuarios": []}

    modal_text = modal_el.inner_text().lower() if modal_el else ""

    # DETECÇÃO DE RESTRIÇÃO / PRIVACIDADE (Evita falso positivo de 0 seguidores)
    frases_restricao = [
        "para proteger nossa comunidade",
        "limitamos algumas coisas que você pode ver",
        "to protect our community",
        "we limit certain activity",
        "we limit some things you can see",
        "nenhum resultado"
    ]
    
    eh_restrito = any(frase in modal_text for frase in frases_restricao)
    if eh_restrito:
        print(f"  [!] ALERTA DE PRIVACIDADE: O Instagram restringiu a visualização de {tipo_label} de @{username_alvo}!")
        print(f"      (Mensagem detectada: 'Para proteger nossa comunidade, limitamos...')")
        _fechar_modal(page, modal_el)
        return {
            "status": "RESTRITO",
            "motivo": "Instagram restringiu visualização da lista (alvo privou ou limitou público)",
            "usuarios": []
        }

    usuarios_coletados = []
    seen = set()

    for scroll_idx in range(1, max_scrolls + 1):
        links_modal = modal_el.query_selector_all("a[role='link'], a[href^='/']")
        antes = len(usuarios_coletados)
        for lk in links_modal:
            href = lk.get_attribute("href") or ""
            partes = [p for p in href.strip("/").split("/") if p]
            if len(partes) == 1:
                uname = partes[0].lower().replace("@", "").strip()
                if uname and uname not in ["explore", "direct", "reels", "stories", "accounts", "p", "reel", username_alvo.lower()]:
                    if uname not in seen:
                        seen.add(uname)
                        usuarios_coletados.append(uname)

        if scroll_idx % 4 == 0 and len(usuarios_coletados) > antes:
            print(f"  [*] Coletando {tipo_label} de @{username_alvo}: {len(usuarios_coletados)} perfis mapeados...")

        # Rola o container interno
        page.evaluate("""() => {
            const dialog = document.querySelector("div[role='dialog']");
            if (!dialog) return false;
            const scrollables = Array.from(dialog.querySelectorAll('div')).filter(el => {
                const style = window.getComputedStyle(el);
                return (style.overflowY === 'auto' || style.overflowY === 'scroll') && el.scrollHeight > el.clientHeight;
            });
            if (scrollables.length > 0) {
                scrollables[0].scrollTop += 800;
                return true;
            } else {
                dialog.scrollTop += 800;
                return false;
            }
        }""")
        page.wait_for_timeout(1200)

    _fechar_modal(page, modal_el)

    status = "SUCESSO" if usuarios_coletados else "VAZIO"
    print(f"  [+] {tipo_label} coletados de @{username_alvo}: {len(usuarios_coletados)} contas encontradas.")
    return {
        "status": status,
        "motivo": "OK" if usuarios_coletados else "Nenhum usuário listado",
        "usuarios": usuarios_coletados
    }

def extrair_e_baixar_fotos(page, username_alvo, max_scrolls=6):
    """Extrai Bio, Avatar HD, Destaques, Stories ativos, fotos do Feed, Seguidores e Seguindo."""
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
    print("\n[1/5] Extraindo Biografia e Dados do Perfil...")
    header_el = page.query_selector("header")
    header_text = header_el.inner_text() if header_el else ""

    meta_desc = ""
    try:
        meta_el = page.query_selector("meta[name='description'], meta[property='og:description']")
        if meta_el:
            meta_desc = meta_el.get_attribute("content") or ""
    except Exception:
        pass

    texto_combinado = f"{header_text}\n{meta_desc}"

    posts_count = "0 posts"
    seguidores = "0 seguidores"
    seguindo = "0 seguindo"

    m_posts = re.search(r"([\d.,]+\s*(?:mil|mi|k|m)?)\s*\n?\s*(?:posts?|publicaç[õo]es|publica[çc][ãa]o)\b", texto_combinado, re.IGNORECASE)
    if m_posts:
        posts_count = f"{m_posts.group(1).strip()} posts"

    m_seg = re.search(r"([\d.,]+\s*(?:mil|mi|k|m)?)\s*\n?\s*(?:seguidores|followers|seguidor)\b", texto_combinado, re.IGNORECASE)
    if m_seg:
        seguidores = f"{m_seg.group(1).strip()} seguidores"

    m_sdo = re.search(r"([\d.,]+\s*(?:mil|mi|k|m)?)\s*\n?\s*(?:seguindo|following|a\s+seguir)\b", texto_combinado, re.IGNORECASE)
    if not m_sdo:
        m_sdo = re.search(r"(?:seguindo|following|a\s+seguir)\s*\n?\s*([\d.,]+\s*(?:mil|mi|k|m)?)\b", texto_combinado, re.IGNORECASE)
    if m_sdo:
        seguindo = f"{m_sdo.group(1).strip()} seguindo"

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

    # Avatar em alta definição (preserva avatar já baixado pelo motor Go se existir)
    avatar_path = os.path.join(pasta_destino, "avatar_perfil.jpg")
    avatar_salvo = os.path.exists(avatar_path) and os.path.getsize(avatar_path) > 500
    try:
        avatar_img = page.query_selector("header img")
        if avatar_img:
            avatar_src = avatar_img.get_attribute("src")
            if avatar_src and avatar_src.startswith(("http://", "https://")):
                res = requests.get(avatar_src, timeout=15)
                if res.status_code == 200:
                    with open(avatar_path, "wb") as f:
                        f.write(res.content)
                    avatar_salvo = True
                    print("  [>] Foto de perfil (avatar HD) salva com sucesso!")
    except Exception as e:
        print(f"  [-] Aviso ao atualizar avatar: {e}")

    # Salva arquivo bio.txt legível
    bio_txt_path = os.path.join(pasta_destino, "bio.txt")
    with open(bio_txt_path, "w", encoding="utf-8") as f:
        f.write("="*60 + "\n")
        f.write(f" PERFIL DO INSTAGRAM: @{username_alvo}\n")
        f.write(f" {posts_count} | {seguidores} | {seguindo}\n")
        f.write("="*60 + "\n\n")
        f.write("--- BIOGRAFIA E INFORMAÇÕES ---\n")
        f.write((header_text or meta_desc) + "\n\n")
        if links:
            f.write("--- LINKS EXTERNOS NA BIO ---\n")
            for lk in links:
                f.write(f"- {lk['texto'] or 'Link'}: {lk['url']}\n")
            f.write("\n")
        f.write("="*60 + "\n")
    print("  [>] Arquivo bio.txt gerado com sucesso!")

    # 2. DESTAQUES (HIGHLIGHTS)
    print("\n[2/5] Verificando Destaques (Highlights)...")
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
        fila_videos_hl = []
        _anexar_captura_videos_rede(aux_page, fila_videos_hl)

        for h_idx, href in enumerate(hl_urls, 1):
            full_hl_url = f"https://www.instagram.com{href}" if href.startswith("/") else href
            print(f"  [*] Abrindo destaque {h_idx}/{len(hl_urls)}...")
            try:
                fila_videos_hl.clear()
                aux_page.goto(full_hl_url, wait_until="domcontentloaded", timeout=20000)
                aux_page.wait_for_timeout(2000)

                btn = aux_page.locator("text=/View story|Ver story/i")
                if btn.count() > 0:
                    btn.first.click()
                    aux_page.wait_for_timeout(2200)

                seen_slide_urls = set()
                slide_count = 0
                for _ in range(25):  # Percorre os slides do destaque
                    if "/stories/" not in aux_page.url:
                        break

                    # Imagens do slide (ignora blob: e avatares minúsculos)
                    for img in aux_page.query_selector_all("img"):
                        try:
                            w = img.evaluate("el => el.naturalWidth") or 0
                            h = img.evaluate("el => el.naturalHeight") or 0
                            s = img.get_attribute("src") or ""
                            srcset = img.get_attribute("srcset") or ""
                            best = s
                            if srcset:
                                best = srcset.split(",")[-1].strip().split(" ")[0]
                            if (w > 200 or h > 200) and best.startswith(("http://", "https://")) and best not in seen_slide_urls:
                                seen_slide_urls.add(best)
                                slide_count += 1
                                dest_file = os.path.join(pasta_destaques, f"destaque_{h_idx}_slide_{slide_count}.jpg")
                                r = requests.get(best, timeout=15)
                                if r.status_code == 200:
                                    with open(dest_file, "wb") as f:
                                        f.write(r.content)
                                    print(f"    [+] Destaque {h_idx} - Foto salva: {os.path.basename(dest_file)}")
                                    destaques_coletados.append(dest_file)
                        except Exception:
                            pass

                    # Vídeos do slide (suporta URLs diretas HTTP e fluxos MSE blob: capturados via rede/poster)
                    for vid in aux_page.query_selector_all("video, video source"):
                        try:
                            v_src = (vid.get_attribute("src") or "").strip()
                            poster = (vid.get_attribute("poster") or "").strip()
                            if v_src.startswith(("http://", "https://")) and v_src not in seen_slide_urls:
                                seen_slide_urls.add(v_src)
                                slide_count += 1
                                dest_file = os.path.join(pasta_destaques, f"destaque_{h_idx}_slide_{slide_count}.mp4")
                                r = requests.get(v_src, timeout=20)
                                if r.status_code == 200 and len(r.content) > 1000:
                                    with open(dest_file, "wb") as f:
                                        f.write(r.content)
                                    print(f"    [+] Destaque {h_idx} - Vídeo salvo: {os.path.basename(dest_file)}")
                                    destaques_coletados.append(dest_file)
                            elif poster.startswith(("http://", "https://")) and poster not in seen_slide_urls:
                                seen_slide_urls.add(poster)
                                slide_count += 1
                                dest_file = os.path.join(pasta_destaques, f"destaque_{h_idx}_slide_{slide_count}.jpg")
                                r = requests.get(poster, timeout=15)
                                if r.status_code == 200:
                                    with open(dest_file, "wb") as f:
                                        f.write(r.content)
                                    print(f"    [+] Destaque {h_idx} - Capa de vídeo salva: {os.path.basename(dest_file)}")
                                    destaques_coletados.append(dest_file)
                        except Exception:
                            pass

                    # Baixa vídeos .mp4 interceptados pela rede durante o slide (contorna blob:https://...)
                    while fila_videos_hl:
                        v_net = fila_videos_hl.pop(0)
                        if v_net.startswith(("http://", "https://")) and v_net not in seen_slide_urls:
                            seen_slide_urls.add(v_net)
                            try:
                                r = requests.get(v_net, timeout=20)
                                if r.status_code == 200 and len(r.content) > 5000:
                                    slide_count += 1
                                    dest_file = os.path.join(pasta_destaques, f"destaque_{h_idx}_video_{slide_count}.mp4")
                                    with open(dest_file, "wb") as f:
                                        f.write(r.content)
                                    print(f"    [+] Destaque {h_idx} - Vídeo MP4 salvo: {os.path.basename(dest_file)}")
                                    destaques_coletados.append(dest_file)
                            except Exception:
                                pass

                    aux_page.keyboard.press("ArrowRight")
                    aux_page.wait_for_timeout(1000)
            except Exception as e:
                print(f"  [!] Aviso ao verificar destaque {h_idx}: {e}")

        aux_page.close()
    else:
        print("  [i] Nenhum destaque encontrado no perfil.")

    # 3. STATUS / STORIES ATIVOS (24h)
    print("\n[3/5] Verificando Stories Ativos (24 horas)...")
    stories_coletados = []
    aux_page = page.context.new_page()
    fila_videos_st = []
    _anexar_captura_videos_rede(aux_page, fila_videos_st)
    try:
        aux_page.goto(f"https://www.instagram.com/stories/{username_alvo}/", wait_until="domcontentloaded", timeout=20000)
        aux_page.wait_for_timeout(2500)
        if "/stories/" in aux_page.url:
            os.makedirs(pasta_stories, exist_ok=True)
            print("  [+] Perfil possui Stories de 24h ativos! Baixando...")
            btn = aux_page.locator("text=/View story|Ver story/i")
            if btn.count() > 0:
                btn.first.click()
                aux_page.wait_for_timeout(2200)

            seen_st_urls = set()
            st_count = 0
            for _ in range(15):
                if "/stories/" not in aux_page.url:
                    break
                for img in aux_page.query_selector_all("img"):
                    try:
                        w = img.evaluate("el => el.naturalWidth") or 0
                        h = img.evaluate("el => el.naturalHeight") or 0
                        s = (img.get_attribute("src") or "").strip()
                        if (w > 200 or h > 200) and s.startswith(("http://", "https://")) and s not in seen_st_urls:
                            seen_st_urls.add(s)
                            st_count += 1
                            dest_file = os.path.join(pasta_stories, f"story_{st_count}.jpg")
                            r = requests.get(s, timeout=15)
                            if r.status_code == 200:
                                with open(dest_file, "wb") as f:
                                    f.write(r.content)
                                print(f"    [+] Story foto salva: {os.path.basename(dest_file)}")
                                stories_coletados.append(dest_file)
                    except Exception:
                        pass

                for vid in aux_page.query_selector_all("video, video source"):
                    try:
                        v_src = (vid.get_attribute("src") or "").strip()
                        poster = (vid.get_attribute("poster") or "").strip()
                        if v_src.startswith(("http://", "https://")) and v_src not in seen_st_urls:
                            seen_st_urls.add(v_src)
                            st_count += 1
                            dest_file = os.path.join(pasta_stories, f"story_{st_count}.mp4")
                            r = requests.get(v_src, timeout=20)
                            if r.status_code == 200 and len(r.content) > 1000:
                                with open(dest_file, "wb") as f:
                                    f.write(r.content)
                                print(f"    [+] Story vídeo salvo: {os.path.basename(dest_file)}")
                                stories_coletados.append(dest_file)
                        elif poster.startswith(("http://", "https://")) and poster not in seen_st_urls:
                            seen_st_urls.add(poster)
                            st_count += 1
                            dest_file = os.path.join(pasta_stories, f"story_{st_count}.jpg")
                            r = requests.get(poster, timeout=15)
                            if r.status_code == 200:
                                with open(dest_file, "wb") as f:
                                    f.write(r.content)
                                print(f"    [+] Story capa salva: {os.path.basename(dest_file)}")
                                stories_coletados.append(dest_file)
                    except Exception:
                        pass

                while fila_videos_st:
                    v_net = fila_videos_st.pop(0)
                    if v_net.startswith(("http://", "https://")) and v_net not in seen_st_urls:
                        seen_st_urls.add(v_net)
                        try:
                            r = requests.get(v_net, timeout=20)
                            if r.status_code == 200 and len(r.content) > 5000:
                                st_count += 1
                                dest_file = os.path.join(pasta_stories, f"story_video_{st_count}.mp4")
                                with open(dest_file, "wb") as f:
                                    f.write(r.content)
                                print(f"    [+] Story vídeo MP4 salvo: {os.path.basename(dest_file)}")
                                stories_coletados.append(dest_file)
                        except Exception:
                            pass

                aux_page.keyboard.press("ArrowRight")
                aux_page.wait_for_timeout(1000)
        else:
            print("  [i] Perfil não possui Stories de 24h ativos no momento.")
    except Exception as e:
        print(f"  [!] Aviso ao verificar stories: {e}")
    aux_page.close()

    # 4. FOTOS E PUBLICAÇÕES DO FEED
    print(f"\n[4/5] Extraindo fotos do Feed (rolando a página {max_scrolls} vezes)...")
    midias_coletadas = []
    seen_urls = set()

    for s_idx in range(1, max_scrolls + 1):
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

        print(f"  [*] Rolagem do feed {s_idx}/{max_scrolls} concluída ({len(midias_coletadas)} fotos mapeadas)...")
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

    if posts_count == "0 posts" and len(feed_baixados) > 0:
        posts_count = f"{len(feed_baixados)} posts"

    # 5. EXTRAÇÃO DE SEGUIDORES, SEGUINDO E CONEXÕES MÚTUAS
    print("\n[5/5] Analisando Conexões: Quem segue o alvo e quem o alvo segue de volta...")

    # Verifica se o Motor Go Turbo REST já populou listas completas nesta pasta
    json_path = os.path.join(pasta_destino, "dados_perfil.json")
    go_seguidores_prev = []
    go_seguindo_prev = []
    engine_usada = "PLAYWRIGHT_BROWSER"
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as fg:
                prev_data = json.load(fg)
                if prev_data.get("engine_utilizada") in ("GOLANG_TURBO_REST", "HYBRID_GO_PLAYWRIGHT"):
                    go_seguidores_prev = prev_data.get("conexoes", {}).get("seguidores", {}).get("contas", []) or []
                    go_seguindo_prev = prev_data.get("conexoes", {}).get("seguindo", {}).get("contas", []) or []
        except Exception:
            pass

    if go_seguidores_prev or go_seguindo_prev:
        print(f"  [+] Preservando listas completas do Motor Go Turbo REST ({len(go_seguidores_prev)} seguidores | {len(go_seguindo_prev)} seguindo)!")
        res_seguidores = {"status": "SUCESSO", "motivo": "Extraído via Go Turbo REST", "usuarios": go_seguidores_prev}
        res_seguindo = {"status": "SUCESSO", "motivo": "Extraído via Go Turbo REST", "usuarios": go_seguindo_prev}
        engine_usada = "HYBRID_GO_PLAYWRIGHT"
    else:
        try:
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1200)
        except Exception:
            pass

        res_seguidores = extrair_lista_usuarios_modal(page, username_alvo, tipo="followers", max_scrolls=12)
        page.wait_for_timeout(1500)
        res_seguindo = extrair_lista_usuarios_modal(page, username_alvo, tipo="following", max_scrolls=12)

    lista_seguidores = res_seguidores.get("usuarios", [])
    lista_seguindo = res_seguindo.get("usuarios", [])

    if seguidores == "0 seguidores" and len(lista_seguidores) > 0:
        seguidores = f"{len(lista_seguidores)} seguidores"
    if seguindo == "0 seguindo" and len(lista_seguindo) > 0:
        seguindo = f"{len(lista_seguindo)} seguindo"

    # Análise de relacionamentos (mútuos e quem não segue de volta)
    seguem_de_volta = sorted(list(set(lista_seguidores) & set(lista_seguindo)))
    apenas_seguidores = sorted(list(set(lista_seguidores) - set(lista_seguindo)))
    alvo_segue_mas_nao_seguem = sorted(list(set(lista_seguindo) - set(lista_seguidores)))

    # Arquivos TXT para leitura rápida e limpa
    arq_seguidores = os.path.join(pasta_destino, "seguidores.txt")
    with open(arq_seguidores, "w", encoding="utf-8") as f:
        f.write(f"=== SEGUIDORES DE @{username_alvo} ===\n")
        f.write(f"Status da Coleta: {res_seguidores.get('status')} ({res_seguidores.get('motivo')})\n")
        f.write(f"Total Encontrado: {len(lista_seguidores)}\n\n")
        for u in lista_seguidores:
            f.write(f"@{u}\n")

    arq_seguindo = os.path.join(pasta_destino, "seguindo.txt")
    with open(arq_seguindo, "w", encoding="utf-8") as f:
        f.write(f"=== CONTAS QUE @{username_alvo} SEGUE ===\n")
        f.write(f"Status da Coleta: {res_seguindo.get('status')} ({res_seguindo.get('motivo')})\n")
        f.write(f"Total Encontrado: {len(lista_seguindo)}\n\n")
        for u in lista_seguindo:
            f.write(f"@{u}\n")

    arq_mutuos = os.path.join(pasta_destino, "conexoes_mutuas.txt")
    with open(arq_mutuos, "w", encoding="utf-8") as f:
        f.write(f"=== CONEXÕES MÚTUAS DE @{username_alvo} (SEGUE E É SEGUIDO DE VOLTA) ===\n")
        f.write(f"Total de Mútuos: {len(seguem_de_volta)}\n\n")
        for u in seguem_de_volta:
            f.write(f"@{u}\n")

    # 6. RELATÓRIO JSON CONSOLIDADO
    dados_completos = {
        "username": username_alvo,
        "avatar_salvo": avatar_salvo,
        "contadores": {
            "posts": posts_count,
            "seguidores": seguidores,
            "seguindo": seguindo
        },
        "links_bio": links,
        "conexoes": {
            "seguidores": {
                "status": res_seguidores.get("status"),
                "motivo": res_seguidores.get("motivo"),
                "bloqueado_ou_privado": res_seguidores.get("status") == "RESTRITO",
                "total_extraido": len(lista_seguidores),
                "contas": lista_seguidores
            },
            "seguindo": {
                "status": res_seguindo.get("status"),
                "motivo": res_seguindo.get("motivo"),
                "bloqueado_ou_privado": res_seguindo.get("status") == "RESTRITO",
                "total_extraido": len(lista_seguindo),
                "contas": lista_seguindo
            },
            "resumo_relacionamento": {
                "seguem_de_volta_mutuo": seguem_de_volta,
                "total_mutuo": len(seguem_de_volta),
                "apenas_seguidores": apenas_seguidores,
                "alvo_segue_mas_nao_seguem_de_volta": alvo_segue_mas_nao_seguem
            }
        },
        "total_destaques_baixados": len(destaques_coletados),
        "destaques_arquivos": destaques_coletados,
        "total_stories_baixados": len(stories_coletados),
        "stories_arquivos": stories_coletados,
        "total_fotos_feed": len(feed_baixados),
        "feed": midias_coletadas,
        "engine_utilizada": engine_usada
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dados_completos, f, ensure_ascii=False, indent=4)

    total_arquivos = len(feed_baixados) + len(destaques_coletados) + len(stories_coletados)
    if avatar_salvo:
        total_arquivos += 1

    status_final = "CONCLUIDO" if total_arquivos > 0 else "VAZIO"
    registrar_coleta_db(username_alvo, pasta_destino, total_arquivos, status_final)

    print("\n" + "="*60)
    print(f"[+] EXTRAÇÃO E ANÁLISE FINALIZADA PARA @{username_alvo}!")
    print(f"  - Bio & Dados: Salvos em bio.txt e dados_perfil.json")
    print(f"  - Seguidores Coletados: {len(lista_seguidores)} (Status: {res_seguidores.get('status')})")
    print(f"  - Seguindo Coletados: {len(lista_seguindo)} (Status: {res_seguindo.get('status')})")
    print(f"  - Conexões Mútuas (Segue de Volta): {len(seguem_de_volta)}")
    print(f"  - Arquivos Gerados: seguidores.txt, seguindo.txt, conexoes_mutuas.txt")
    print(f"  - Feed: {len(feed_baixados)} fotos baixadas")
    print(f"  - Destaques: {len(destaques_coletados)} arquivos salvos")
    print(f"  - Stories (24h): {len(stories_coletados)} arquivos salvos")
    print(f"  - Total geral de mídias: {total_arquivos} arquivos em {pasta_destino}")
    print("="*60)
    return total_arquivos
