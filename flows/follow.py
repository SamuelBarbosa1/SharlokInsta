import os
import time
import random
from playwright.sync_api import sync_playwright
from core.config import ALVOS_TXT_FILE, DELAY_MIN_SEGS, DELAY_MAX_SEGS
from core.pool import carregar_pool_contas
from core.targets import (
    carregar_alvos,
    registrar_novo_alvo,
    carregar_alvos_do_arquivo,
    distribuir_alvos_em_massa
)
from scraper.browser import criar_contexto_desktop
from scraper.profile import obter_info_perfil
from scraper.extractor import extrair_e_baixar_fotos

def fluxo_seguir_alvo():
    """Menu para escolha entre abordagem individual ou importação em massa via alvos.txt."""
    while True:
        print("\n" + "="*60)
        print(" 🎯 SELEÇÃO DE ALVOS PARA MONITORAMENTO")
        print("="*60)
        print(" [1] 👤 Abordar 1 Alvo Manualmente")
        print(" [2] 📂 Carregar Lista de Alvos em Massa (alvos.txt)")
        print(" [0] 🔙 Voltar ao Menu Principal")

        opc = input("\n>> Escolha uma opção [0-2]: ").strip()

        if opc == "1":
            fluxo_seguir_individual()
            break
        elif opc == "2":
            fluxo_seguir_em_massa()
            break
        elif opc == "0":
            break
        else:
            print("Opção inválida. Tente novamente.")


def fluxo_seguir_individual():
    """Acessa um único perfil alvo, clica no botão de Seguir e registra no monitoramento."""
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


def fluxo_seguir_em_massa():
    """Lê alvos de alvos.txt, distribui uniformemente pelas contas do pool e envia follows com delays."""
    pool = carregar_pool_contas()
    contas_ativas = [c for c in pool if c.get("ativo", True) and c.get("sessionid")]

    if not contas_ativas:
        print("\n[!] Nenhuma conta ativa encontrada no Pool! Configure contas na opção [5] primeiro.")
        return

    # Garante que alvos.txt existe
    if not os.path.exists(ALVOS_TXT_FILE):
        with open(ALVOS_TXT_FILE, "w", encoding="utf-8") as f:
            f.write("# Insira um username por linha (com ou sem @)\n")
        print(f"\n[i] Arquivo {ALVOS_TXT_FILE} criado! Abra-o, cole os perfis e execute novamente.")
        return

    alvos_brutos = carregar_alvos_do_arquivo(ALVOS_TXT_FILE)
    if not alvos_brutos:
        print(f"\n[!] O arquivo {ALVOS_TXT_FILE} está vazio ou contém apenas comentários.")
        print(f"    Abra o arquivo {ALVOS_TXT_FILE}, insira os usernames (um por linha) e tente novamente.")
        return

    # Filtra alvos que já estão em monitoramento
    alvos_existentes = [a["username"].lower() for a in carregar_alvos()]
    alvos_novos = []
    for a in alvos_brutos:
        if a in alvos_existentes:
            print(f"  [i] @{a} já está registrado no monitoramento (ignorado para evitar duplicidade).")
        else:
            alvos_novos.append(a)

    if not alvos_novos:
        print("\n[i] Todos os alvos do arquivo já constam na lista de monitoramento.")
        return

    # Distribuição equilibrada entre as contas ativas
    distribuicao = distribuir_alvos_em_massa(alvos_novos, contas_ativas)

    print("\n" + "="*70)
    print(" 📋 DISTRIBUIÇÃO DOS ALVOS ENTRE AS CONTAS DO POOL (ROUND-ROBIN)")
    print("="*70)
    print(f" {'#':<4} | {'ALVO':<25} | {'CONTA BOT DESIGNADA'}")
    print("-"*70)
    for idx, (target, conta) in enumerate(distribuicao, 1):
        print(f" {idx:<4} | @{target:<24} | @{conta.get('user')}")
    print("="*70)
    print(f"Total: {len(distribuicao)} alvo(s) distribuído(s) entre {len(contas_ativas)} conta(s) ativa(s).")
    print(f"Intervalo de proteção anti-bloqueio entre envios: {DELAY_MIN_SEGS} a {DELAY_MAX_SEGS} segundos.")

    confirma = input("\n>> Deseja iniciar o envio das solicitações em massa? (s/n): ").strip().lower()
    if confirma not in ["s", "sim", "y"]:
        print("[i] Operação cancelada.")
        return

    print("\n[*] Iniciando navegador para disparos em massa...")
    sucessos = 0
    falhas = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for idx, (target, conta) in enumerate(distribuicao, 1):
            print(f"\n[{idx}/{len(distribuicao)}] Abordando @{target} com a conta @{conta.get('user')}...")
            ctx = criar_contexto_desktop(browser, conta)
            page = ctx.new_page()

            try:
                info = obter_info_perfil(page, target)
                btn_st = info["button_status"]

                if btn_st == "SEGUINDO":
                    print(f"  [i] A conta @{conta.get('user')} já segue @{target}! Feed acessível.")
                    sucessos += 1
                elif btn_st == "SOLICITADO":
                    print(f"  [⏳] Solicitação já enviada anteriormente e está pendente.")
                    registrar_novo_alvo(target, is_private=info["is_private"], conta_usada=conta.get("user"))
                    sucessos += 1
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
                        print(f"  [+] Solicitação enviada com sucesso para @{target}!")
                        registrar_novo_alvo(target, is_private=info["is_private"], conta_usada=conta.get("user"))
                        sucessos += 1
                    else:
                        print(f"  [-] Botão de seguir não encontrado para @{target}.")
                        falhas += 1
            except Exception as e:
                print(f"  [-] Erro ao processar @{target}: {e}")
                falhas += 1
            finally:
                ctx.close()

            # Delay humanizado entre disparos para segurança anti-bloqueio
            if idx < len(distribuicao):
                espera = random.randint(DELAY_MIN_SEGS, DELAY_MAX_SEGS)
                print(f"  [⏳] Aguardando {espera}s antes da próxima abordagem (proteção anti-spam)...")
                time.sleep(espera)

        browser.close()

    print("\n" + "="*70)
    print(f"[✔] DISPARO EM MASSA CONCLUÍDO! ({sucessos} com sucesso, {falhas} falhas)")
    print("    Todos os alvos confirmados foram adicionados ao monitoramento.")
    print("    Você pode checar o status na opção [4] ou ativar o [6] Modo Sentinela.")
    print("="*70)
