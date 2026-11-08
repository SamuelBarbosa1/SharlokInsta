def obter_info_perfil(page, username):
    """Lê metadados da tela de perfil de desktop do Instagram."""
    clean_u = username.replace("@", "").strip()
    print(f"[*] Acessando https://www.instagram.com/{clean_u}/ na versão Desktop...")
    page.goto(f"https://www.instagram.com/{clean_u}/", wait_until="domcontentloaded")
    page.wait_for_timeout(3500)

    current_url = (page.url or "").lower()
    login_required = "/accounts/login" in current_url or "/challenge/" in current_url

    content = page.content().lower()
    not_found_phrases = [
        "sorry, this page isn't available",
        "esta página não está disponível",
        "a página não está disponível",
        "profile isn't available",
        "o perfil não está disponível",
        "o link em que você clicou pode não estar funcionando"
    ]
    exists = not any(p in content for p in not_found_phrases)

    is_private = (
        "this profile is private" in content or
        "este perfil é privado" in content or
        "this account is private" in content or
        "esta conta é privada" in content or
        "follow to see their photos and videos" in content or
        "siga para ver suas fotos e vídeos" in content or
        "siga para ver suas fotos" in content
    )

    # Detecta estado do botão de seguir (suporta <button> e <div role="button"> da UI atual do Instagram)
    btn_status = "Desconhecido"
    if login_required:
        btn_status = "SESSAO_EXPIRADA"
    elif not exists:
        btn_status = "NAO_ENCONTRADO"
    else:
        buttons = page.query_selector_all("header button, main header button, header div[role='button'], main header div[role='button'], button")
        for btn in buttons:
            txt = (btn.inner_text() or "").strip().lower()
            if txt in ["follow", "seguir", "follow back", "seguir de volta"]:
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
        "username": clean_u,
        "exists": exists,
        "login_required": login_required,
        "is_private": is_private,
        "button_status": btn_status,
        "header_snippet": header_text[:200].replace("\n", " | ") if header_text else ""
    }
