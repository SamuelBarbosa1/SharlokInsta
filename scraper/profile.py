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
