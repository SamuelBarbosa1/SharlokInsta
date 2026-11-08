def criar_contexto_desktop(browser, cfg):
    """Cria um contexto simulando 100% o Google Chrome Desktop no Windows."""
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 768},
        locale="pt-BR"
    )
    sessionid = str(cfg.get("sessionid") or "").strip().strip("\"' ;")
    ds_user_id = str(cfg.get("ds_user_id") or "").strip()
    if not ds_user_id and sessionid:
        if "%3A" in sessionid:
            cand = sessionid.split("%3A", 1)[0]
            if cand.isdigit():
                ds_user_id = cand
        elif ":" in sessionid:
            cand = sessionid.split(":", 1)[0]
            if cand.isdigit():
                ds_user_id = cand

    cookies = []
    if sessionid:
        cookies.append({"name": "sessionid", "value": sessionid, "domain": ".instagram.com", "path": "/"})
    if ds_user_id:
        cookies.append({"name": "ds_user_id", "value": ds_user_id, "domain": ".instagram.com", "path": "/"})
    if cookies:
        context.add_cookies(cookies)
    return context
