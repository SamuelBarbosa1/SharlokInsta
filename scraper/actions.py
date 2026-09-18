from .browser import criar_contexto_desktop
from .profile import obter_info_perfil

def enviar_follow_com_conta(browser, conta_cfg, target_username):
    """Abre contexto isolado com a conta do pool especificada e envia a solicitação de follow."""
    ctx = criar_contexto_desktop(browser, conta_cfg)
    page = ctx.new_page()
    resultado = "FALHA"
    try:
        info = obter_info_perfil(page, target_username)
        if info["button_status"] == "SEGUINDO":
            resultado = "JA_SEGUINDO"
        elif info["button_status"] == "SOLICITADO":
            resultado = "JA_SOLICITADO"
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
                resultado = "SUCESSO"
    except Exception as e:
        print(f"  [-] Erro ao enviar follow: {e}")
        resultado = "ERRO"
    finally:
        ctx.close()
    return resultado


def cancelar_solicitacao_pendente(page):
    """Clica no botão 'Solicitado' e confirma o cancelamento no Instagram Desktop."""
    try:
        clicked = False
        for btn in page.query_selector_all("header button, main header button, button"):
            txt = (btn.inner_text() or "").strip().lower()
            if txt in ["requested", "solicitado", "solicitação enviada", "solicitada", "pedindo"]:
                btn.click()
                clicked = True
                break

        if not clicked:
            return False

        page.wait_for_timeout(2000)

        # Se abriu um modal de confirmação no Instagram
        modal = page.query_selector("div[role='dialog'], [role='dialog']")
        if modal:
            for m_btn in modal.query_selector_all("button"):
                m_txt = (m_btn.inner_text() or "").strip().lower()
                if any(k in m_txt for k in ["cancelar solicitação", "deixar de seguir", "unfollow", "cancel request"]):
                    m_btn.click()
                    page.wait_for_timeout(2500)
                    return True

        page.wait_for_timeout(2000)
        return True
    except Exception as e:
        print(f"  [-] Erro ao tentar cancelar solicitação: {e}")
        return False
