import os
import json
from datetime import datetime
from .config import CONTAS_POOL_FILE, carregar_config

def carregar_pool_contas():
    """Carrega todas as contas do pool. Se não existir, migra a conta do .env automaticamente."""
    if os.path.exists(CONTAS_POOL_FILE):
        try:
            with open(CONTAS_POOL_FILE, "r", encoding="utf-8") as f:
                contas = json.load(f)
                if isinstance(contas, list) and len(contas) > 0:
                    return contas
        except Exception:
            pass

    # Migração automática inicial da conta existente
    cfg = carregar_config()
    contas = []
    if cfg.get("sessionid"):
        contas.append({
            "id": 1,
            "user": cfg.get("user") or "conta_1",
            "ds_user_id": cfg.get("ds_user_id", ""),
            "sessionid": cfg.get("sessionid", ""),
            "ativo": True,
            "adicionado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        salvar_pool_contas(contas)
    return contas


def salvar_pool_contas(contas):
    """Salva o pool de contas no arquivo contas_pool.json."""
    with open(CONTAS_POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(contas, f, indent=4, ensure_ascii=False)


def obter_conta_ativa():
    """Retorna a primeira conta ativa e configurada do pool."""
    pool = carregar_pool_contas()
    for c in pool:
        if c.get("ativo", True) and c.get("sessionid"):
            return c
    if pool:
        return pool[0]
    return carregar_config()


def obter_conta_por_user(username):
    """Retorna os dados da conta no pool pelo nome de usuário."""
    pool = carregar_pool_contas()
    for c in pool:
        if c.get("user", "").lower() == username.lower():
            return c
    return None
