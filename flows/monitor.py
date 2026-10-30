import random
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from core.config import obter_parametros_automacao
from core.pool import carregar_pool_contas, obter_conta_ativa, obter_conta_por_user, conta_esta_ativa
from core.targets import carregar_alvos, salvar_alvos
from scraper.browser import criar_contexto_desktop
from scraper.profile import obter_info_perfil
from scraper.actions import enviar_follow_com_conta, cancelar_solicitacao_pendente
from scraper.extractor import extrair_e_baixar_fotos

def fluxo_verificar_e_baixar():
    """
    Varre alvos em monitoramento:
    - Se aceito: baixa tudo automaticamente.
    - Se vácuo (não respondeu dentro do limite): cancela solicitação e rotaciona para próxima conta.
    - Se recusado: ativa cooldown.
    - Se cooldown terminou: passa para a próxima conta ativa do pool em cascata.
    """
    alvos = carregar_alvos()
    pendentes = [a for a in alvos if a.get("status") not in ["CONCLUIDO", "ESGOTADO"]]

    if not pendentes:
        print("[i] Não há alvos pendentes no momento (todos concluídos ou esgotados).")
        return

    params = obter_parametros_automacao()
    cooldown_minutos = params["cooldown_minutos"]
    timeout_vacuo_minutos = params["timeout_vacuo_minutos"]
    max_scrolls_padrao = params["max_scrolls_padrao"]

    print(f"[+] Verificando {len(pendentes)} alvo(s) em monitoramento (Vácuo: {timeout_vacuo_minutos}m | Cooldown: {cooldown_minutos}m)...")
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

            print(f"[*] Checando alvo @{username} (Status atual: {status_atual} | Bot: @{conta_cfg.get('user')})...")

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
                        print(f"[+] SUCESSO! @{username} ACEITOU a solicitação de @{conta_cfg.get('user')}!")
                        print(f"[*] Disparando download automático de todo o conteúdo de @{username}...")
                        qtd = extrair_e_baixar_fotos(page, username, max_scrolls=max_scrolls_padrao)
                        alvo["status"] = "CONCLUIDO"
                        alvo["qtd_fotos_baixadas"] = qtd
                        alvo["concluido_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")
                        alvo["atualizado_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")

                        # Atualiza histórico de tentativas
                        if "tentativas" in alvo and alvo["tentativas"]:
                            alvo["tentativas"][-1]["status"] = "ACEITO"
                        salvar_alvos(alvos)

                    # Caso B: Ainda pendente (verifica timeout de vácuo)
                    elif btn_st == "SOLICITADO":
                        solicitado_dt = None
                        if "tentativas" in alvo and alvo["tentativas"]:
                            dt_str = alvo["tentativas"][-1].get("solicitado_em")
                            if dt_str:
                                try:
                                    solicitado_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                                except Exception:
                                    pass
                        if not solicitado_dt and alvo.get("solicitado_em"):
                            try:
                                solicitado_dt = datetime.strptime(alvo["solicitado_em"], "%Y-%m-%d %H:%M:%S")
                            except Exception:
                                pass
                        if not solicitado_dt:
                            solicitado_dt = agora

                        tempo_passado = (agora - solicitado_dt).total_seconds()
                        tempo_limite = timeout_vacuo_minutos * 60

                        if tempo_passado < tempo_limite:
                            restante_seg = int(tempo_limite - tempo_passado)
                            m_rest, s_rest = divmod(restante_seg, 60)
                            print(f"[AGUARDANDO] @{username} ainda não respondeu à solicitação de @{conta_cfg.get('user')} (Espera: {int(tempo_passado // 60)}m {int(tempo_passado % 60)}s | Limite vácuo em {m_rest}m {s_rest}s).")
                        else:
                            print(f"[VACUO] @{username} não respondeu à solicitação de @{conta_cfg.get('user')} após {timeout_vacuo_minutos} min.")
                            print(f"[*] Cancelando solicitação pendente no perfil @{username} com @{conta_cfg.get('user')}...")
                            cancelado = cancelar_solicitacao_pendente(page)
                            if cancelado:
                                print(f"[+] Solicitação de @{conta_cfg.get('user')} cancelada com sucesso no Instagram!")
                            else:
                                print(f"[!] Não foi possível confirmar clique de cancelamento, prosseguindo com a rotação.")

                            if "tentativas" in alvo and alvo["tentativas"]:
                                alvo["tentativas"][-1]["status"] = "CANCELADO_VACUO"
                                alvo["tentativas"][-1]["cancelado_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")

                            # Fecha a página e contexto da conta atual antes de abrir a próxima
                            page.close()
                            ctx.close()
                            ctx = None

                            # Seleciona próxima conta no pool
                            contas_usadas = [t.get("conta", "").lower() for t in alvo.get("tentativas", []) if t.get("status") in ["REJEITADO", "CANCELADO_VACUO"]]
                            candidatas = [c for c in pool if conta_esta_ativa(c) and c.get("sessionid") and c.get("user", "").lower() not in contas_usadas]

                            # Se todas as contas ativas já passaram pelo vácuo nesta rodada, reinicia o loop
                            if not candidatas:
                                print(f"[*] Todas as contas ativas do pool completaram a rodada de espera. Reiniciando o loop de rotação...")
                                contas_recusadas = [t.get("conta", "").lower() for t in alvo.get("tentativas", []) if t.get("status") == "REJEITADO"]
                                candidatas = [c for c in pool if conta_esta_ativa(c) and c.get("sessionid") and c.get("user", "").lower() not in contas_recusadas]
                                if "tentativas" in alvo and alvo["tentativas"]:
                                    for t in alvo["tentativas"]:
                                        if t.get("status") == "CANCELADO_VACUO":
                                            t["status"] = "VACUO_RODADA_ANTERIOR"

                            if candidatas:
                                random.shuffle(candidatas)
                                proxima_conta = candidatas[0]
                                print(f"[*] Rotacionando (sorteio aleatório): enviando nova solicitação para @{username} via @{proxima_conta.get('user')}...")
                                res_follow = enviar_follow_com_conta(browser, proxima_conta, username)
                                if res_follow in ["SUCESSO", "JA_SOLICITADO"]:
                                    alvo["conta_atual"] = proxima_conta.get("user")
                                    alvo["status"] = "AGUARDANDO_APROVACAO"
                                    alvo["solicitado_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")
                                    alvo["atualizado_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")
                                    alvo["cooldown_ate"] = None
                                    if "tentativas" not in alvo or not isinstance(alvo["tentativas"], list):
                                        alvo["tentativas"] = []
                                    alvo["tentativas"].append({
                                        "conta": proxima_conta.get("user"),
                                        "solicitado_em": agora.strftime("%Y-%m-%d %H:%M:%S"),
                                        "status": "SOLICITADO"
                                    })
                                    print(f"[+] Nova solicitação enviada com sucesso para @{username} pela conta @{proxima_conta.get('user')}!")
                                else:
                                    print(f"[-] Falha ao enviar solicitação via @{proxima_conta.get('user')} ({res_follow}).")
                            else:
                                alvo["status"] = "ESGOTADO"
                                print(f"[-] Nenhuma conta disponível no pool para @{username}.")

                            salvar_alvos(alvos)

                    # Caso C: Botão voltou para 'Seguir' -> RECUSA DETECTADA!
                    elif btn_st == "NAO_SEGUINDO":
                        cooldown_limite = agora + timedelta(minutes=cooldown_minutos)
                        cooldown_str = cooldown_limite.strftime("%Y-%m-%d %H:%M:%S")
                        alvo["status"] = "REJEITADO_COOLDOWN"
                        alvo["cooldown_ate"] = cooldown_str
                        alvo["atualizado_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")

                        # Marca recusa no histórico de tentativas
                        if "tentativas" not in alvo or not isinstance(alvo["tentativas"], list):
                            alvo["tentativas"] = []
                        if alvo["tentativas"]:
                            alvo["tentativas"][-1]["status"] = "REJEITADO"
                            alvo["tentativas"][-1]["rejeitado_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")

                        salvar_alvos(alvos)
                        print(f"[RECUSA] @{username} recusou a solicitação de @{conta_cfg.get('user')}.")
                        print(f"[COOLDOWN] Entrando em espera de {cooldown_minutos} min para @{username}. Próxima conta tentará após: {cooldown_str}")

                    else:
                        print(f"[!] Situação atual de @{username}: {btn_st}")
                finally:
                    if ctx:
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
                            print(f"[COOLDOWN] @{username} ainda em cooldown após recusa. Tempo restante: {tempo_formatado} (até {cooldown_str}).")
                    except Exception:
                        cooldown_expirado = True
                else:
                    cooldown_expirado = True

                # Se o cooldown terminou, aciona a cascata para a próxima conta
                if cooldown_expirado:
                    print(f"[*] Cooldown de {cooldown_minutos} min finalizado para @{username}! Procurando próxima conta ativa no pool...")

                    # Descobre quais contas já foram recusadas para esse alvo
                    contas_recusadas = [t.get("conta", "").lower() for t in alvo.get("tentativas", []) if t.get("status") == "REJEITADO"]

                    # Contas disponíveis que ainda não foram recusadas
                    candidatas = [c for c in pool if conta_esta_ativa(c) and c.get("sessionid") and c.get("user", "").lower() not in contas_recusadas]

                    if candidatas:
                        random.shuffle(candidatas)
                        proxima_conta = candidatas[0]
                        print(f"[*] Nova tentativa em cascata (sorteio aleatório): enviando follow para @{username} via @{proxima_conta.get('user')}...")
                        res_follow = enviar_follow_com_conta(browser, proxima_conta, username)

                        if res_follow in ["SUCESSO", "JA_SOLICITADO"]:
                            alvo["conta_atual"] = proxima_conta.get("user")
                            alvo["status"] = "AGUARDANDO_APROVACAO"
                            alvo["cooldown_ate"] = None
                            alvo["atualizado_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")
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
                            print(f"[+] A conta @{proxima_conta.get('user')} já segue @{username}! Baixando conteúdo...")
                            ctx = criar_contexto_desktop(browser, proxima_conta)
                            page = ctx.new_page()
                            qtd = extrair_e_baixar_fotos(page, username, max_scrolls=max_scrolls_padrao)
                            ctx.close()
                            alvo["status"] = "CONCLUIDO"
                            alvo["qtd_fotos_baixadas"] = qtd
                            alvo["concluido_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")
                            alvo["atualizado_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")
                            salvar_alvos(alvos)
                        else:
                            print(f"[-] Não foi possível enviar solicitação via @{proxima_conta.get('user')} ({res_follow}).")
                    else:
                        alvo["status"] = "ESGOTADO"
                        alvo["atualizado_em"] = agora.strftime("%Y-%m-%d %H:%M:%S")
                        salvar_alvos(alvos)
                        print(f"[-] Todas as contas disponíveis no pool foram recusadas por @{username}. Alvo marcado como ESGOTADO.")

        browser.close()
