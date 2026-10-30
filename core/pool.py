import os
import json
from datetime import datetime
from .config import CONTAS_POOL_FILE, carregar_config
from .database import salvar_estado_db, carregar_estado_db


def conta_esta_ativa(c: dict) -> bool:
    """Verifica se uma conta do pool está marcada como ativa."""
    val = c.get("ativo", True)
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ["true", "sim", "1", "ativo", "yes"]


def carregar_pool_contas():
    """Carrega todas as contas do pool (sincronizado entre JSON e SQLite)."""
    if os.path.exists(CONTAS_POOL_FILE):
        try:
            with open(CONTAS_POOL_FILE, "r", encoding="utf-8") as f:
                contas = json.load(f)
                if isinstance(contas, list):
                    salvar_estado_db("pool_contas", contas)
                    return contas
        except Exception:
            pass

    # Tenta recuperar do banco SQLite caso o JSON não exista
    contas_db = carregar_estado_db("pool_contas")
    if isinstance(contas_db, list) and contas_db:
        salvar_pool_contas(contas_db)
        return contas_db

    # Inicialização caso nem arquivo nem banco tenham dados
    cfg = carregar_config()
    contas = []
    if cfg.get("sessionid"):
        contas.append({
            "id": 1,
            "user": cfg.get("user") or "conta_1",
            "ds_user_id": cfg.get("ds_user_id", ""),
            "sessionid": cfg.get("sessionid", ""),
            "ativo": "Sim",
            "adicionado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    salvar_pool_contas(contas)
    return contas


def salvar_pool_contas(contas):
    """Salva o pool de contas no arquivo contas_pool.json e no banco SQLite."""
    with open(CONTAS_POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(contas, f, indent=4, ensure_ascii=False)
    salvar_estado_db("pool_contas", contas)


def listar_contas_ativas():
    """Retorna todas as contas ativas e com sessionid válido."""
    pool = carregar_pool_contas()
    return [c for c in pool if conta_esta_ativa(c) and c.get("sessionid")]


def obter_conta_ativa():
    """Retorna a primeira conta ativa e configurada do pool."""
    ativas = listar_contas_ativas()
    if ativas:
        return ativas[0]
    pool = carregar_pool_contas()
    if pool:
        return pool[0]
    return carregar_config()


def obter_conta_por_user(username):
    """Retorna os dados da conta no pool pelo nome de usuário."""
    if not username:
        return None
    pool = carregar_pool_contas()
    for c in pool:
        if c.get("user", "").lower() == username.lower().replace("@", "").strip():
            return c
    return None
