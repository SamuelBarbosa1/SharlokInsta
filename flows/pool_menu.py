from datetime import datetime
from playwright.sync_api import sync_playwright
from core.pool import carregar_pool_contas, salvar_pool_contas
from scraper.browser import criar_contexto_desktop

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
