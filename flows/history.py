from datetime import datetime
from core.targets import carregar_alvos

def fluxo_historico():
    """Exibe alvos monitorados, status detalhado da cascata e histórico salvo."""
    alvos = carregar_alvos()
    print("\n" + "="*85)
    print(f"{'ALVO':<18} | {'STATUS':<20} | {'CONTA ATUAL':<18} | {'COOLDOWN ATÉ / INFO'}")
    print("="*85)
    if not alvos:
        print(" Nenhum alvo registrado ainda.")
    else:
        for a in alvos:
            status = a.get("status", "-")
            u_alvo = f"@{a['username']}"
            c_atual = f"@{a.get('conta_atual', '-')}"
            info_extra = "-"
            if status == "REJEITADO_COOLDOWN":
                info_extra = f"Até {a.get('cooldown_ate', '-')}"
            elif status == "CONCLUIDO":
                info_extra = f"Concluído ({a.get('qtd_fotos_baixadas', 0)} mídias)"
            elif status == "ESGOTADO":
                info_extra = "Todas as contas recusadas"
            elif status == "AGUARDANDO_APROVACAO":
                tentativas_qtd = len(a.get("tentativas", []))
                solic_str = a.get("solicitado_em")
                if solic_str:
                    try:
                        s_dt = datetime.strptime(solic_str, "%Y-%m-%d %H:%M:%S")
                        decorrido = int((datetime.now() - s_dt).total_seconds() // 60)
                        info_extra = f"Tentativa #{tentativas_qtd} (esperando há {decorrido} min)"
                    except Exception:
                        info_extra = f"Tentativa #{tentativas_qtd}"
                else:
                    info_extra = f"Tentativa #{tentativas_qtd}"

            print(f"{u_alvo:<18} | {status:<20} | {c_atual:<18} | {info_extra}")
    print("="*85)
