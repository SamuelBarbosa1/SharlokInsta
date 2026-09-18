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
