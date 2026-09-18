from playwright.sync_api import sync_playwright
from core.pool import carregar_pool_contas
from core.targets import registrar_novo_alvo
from scraper.browser import criar_contexto_desktop
from scraper.profile import obter_info_perfil
from scraper.extractor import extrair_e_baixar_fotos

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
