from playwright.sync_api import sync_playwright
from core.pool import obter_conta_ativa
from scraper.browser import criar_contexto_desktop
from scraper.profile import obter_info_perfil
from scraper.extractor import extrair_e_baixar_fotos

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
