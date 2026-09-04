import os
import time
import random
import json
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, ChallengeRequired

# =====================================================================
# POOL DE CONTAS (SOCKPUPPETS)
# Dica: Cole o novo sessionid (gerado após atualizar a página no navegador)
# =====================================================================
accounts_pool = [
    {
        "user": "samu_oliveira5",
        "pass": "84716676gbg",
        "sessionid": "69735835949%3ArRsIrSMjXiCCxw%3A7%3AAYhW_X3OBkytee1rBxl6y3HgLtBQB_EWI5SS_r9URQ",
        "proxy": None,  # Exemplo: "http://usuario:senha@ip:porta"
        "status": "ready"
    }
]

def get_authenticated_client(acc):
    """Cria e autentica o cliente com persistência de sessão."""
    cl = Client()
    # Define delay razoável entre requisições internas da biblioteca
    cl.delay_range = [2, 5]
    
    if acc.get("proxy"):
        cl.set_proxy(acc["proxy"])
        
    session_file = f"session_{acc['user']}.json"
    
    # 1. Tenta carregar sessão do arquivo local
    if os.path.exists(session_file):
        try:
            cl.load_settings(session_file)
            cl.get_timeline_feed()
            print(f"[+] Sessão em cache validada para @{acc['user']}.")
            return cl
        except Exception:
            print(f"[*] Sessão local de @{acc['user']} expirou. Renovando...")
            if os.path.exists(session_file):
                os.remove(session_file)

    # 2. Login via sessionid (Mais seguro contra checkpoints)
    if acc.get("sessionid") and acc["sessionid"] != "COLE_O_NOVO_SESSIONID_AQUI":
        try:
            print(f"[*] Autenticando @{acc['user']} via sessionid...")
            cl.login_by_sessionid(acc["sessionid"])
            cl.dump_settings(session_file)
            print(f"[+] Autenticação via sessionid concluída com sucesso!")
            return cl
        except Exception as e:
            print(f"[-] Falha no login por sessionid: {e}")

    # 3. Login tradicional (usuário e senha)
    print(f"[*] Tentando login por senha para @{acc['user']}...")
    try:
        cl.login(acc["user"], acc["pass"])
        cl.dump_settings(session_file)
        print(f"[+] Login concluído e sessão salva!")
        return cl
    except Exception as e:
        raise e

def gather_osint_data(cl, target_username):
    """Coleta e estrutura metadados públicos do alvo (OSINT)."""
    print(f"\n[+] Coletando inteligência de @{target_username}...")
    user_info = cl.user_info_by_username(target_username)
    
    data = {
        "id": str(user_info.pk),
        "username": user_info.username,
        "full_name": user_info.full_name,
        "is_private": user_info.is_private,
        "is_verified": user_info.is_verified,
        "biography": user_info.biography,
        "external_url": str(user_info.external_url) if user_info.external_url else None,
        "followers_count": user_info.follower_count,
        "following_count": user_info.following_count,
        "media_count": user_info.media_count,
        "category": getattr(user_info, "category", None),
        "public_email": getattr(user_info, "public_email", None),
        "public_phone": getattr(user_info, "public_phone_number", None),
    }
    
    print("\n" + "="*50)
    print(" 📊 RELATÓRIO DE INTELIGÊNCIA (OSINT)")
    print("="*50)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print("="*50)
    
    # Salva o relatório em arquivo JSON
    report_file = f"relatorio_{target_username}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[+] Relatório exportado com sucesso: {report_file}")
    
    return user_info

def follow_target(cl, user_info, acc_user):
    """Executa a ação de seguir/solicitar com delay humanizado."""
    delay = random.randint(4, 8)
    print(f"\n[*] Aguardando delay de segurança ({delay}s) antes de enviar solicitação...")
    time.sleep(delay)
    
    try:
        target_pk = str(user_info.pk)
        result = cl.user_follow(target_pk)
        
        status_msg = "Solicitação enviada (perfil privado)" if user_info.is_private else "Seguindo com sucesso (perfil público)"
        print(f"[+] SUCESSO com @{acc_user}: {status_msg} para @{user_info.username} (ID: {target_pk})! Resposta: {result}")
        return True
    except LoginRequired:
        print(f"[-] A sessão da conta @{acc_user} foi revogada pelo Instagram. Atualize o sessionid.")
        return False
    except Exception as e:
        print(f"[-] Erro ao seguir @{user_info.username}: {e}")
        return False

def run(target_username):
    for acc in accounts_pool:
        if acc["status"] != "ready":
            continue
            
        try:
            cl = get_authenticated_client(acc)
            user_info = gather_osint_data(cl, target_username)
            
            # Pergunta se deseja seguir o alvo
            priv_info = "Privado" if user_info.is_private else "Público"
            print(f"\n[?] O perfil @{target_username} é [{priv_info}].")
            escolha = input(f">> Deseja seguir / enviar solicitação para @{target_username}? (s/n): ").strip().lower()
            
            if escolha in ["s", "sim", "y", "yes"]:
                follow_target(cl, user_info, acc["user"])
            else:
                print("[i] Operação concluída. Apenas inteligência coletada.")
                
            return
        except Exception as e:
            print(f"[-] Erro na conta @{acc['user']}: {e}")
            acc["status"] = "error"
            time.sleep(3)
            
    print("\n[-] Nenhuma conta da pool conseguiu completar a requisição.")

if __name__ == "__main__":
    target = input("Digite o username do alvo (sem @): ").strip().replace("@", "")
    if target:
        run(target)
    else:
        print("Username inválido.")
