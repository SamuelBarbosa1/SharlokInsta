import os
import json

# Arquivos locais do sistema
CONFIG_FILE = "config_conta.json"
CONTAS_POOL_FILE = "contas_pool.json"
MONITOR_FILE = "alvos_monitorados.json"
DB_NAME = "osint_coletas.db"
ENV_FILE = ".env"

# Cooldown entre tentativas de contas diferentes após uma recusa
# (Ajustado para 3 MINUTOS para testes rápidos! Altere para 60 ou 120 min para produção)
COOLDOWN_MINUTOS = 3

# Tempo de espera em minutos para resposta do alvo (vácuo) antes de cancelar e tentar a próxima conta
# (Ajustado para 3 MINUTOS para testes rápidos! Altere para 1440 min / 24h para produção)
TIMEOUT_VACUO_MINUTOS = 3


def carregar_dotenv(caminho=".env"):
    """Carrega variáveis do arquivo .env sem exigir dependências externas."""
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k:
                            os.environ[k] = v
        except Exception:
            pass

carregar_dotenv()


def carregar_config():
    """Carrega configurações da conta principal priorizando .env e com fallback em config_conta.json."""
    carregar_dotenv()
    cfg = {
        "user": os.getenv("IG_USER", ""),
        "ds_user_id": os.getenv("IG_DS_USER_ID", ""),
        "sessionid": os.getenv("IG_SESSIONID", "")
    }

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for k in ["user", "ds_user_id", "sessionid"]:
                    if not cfg.get(k) and saved.get(k):
                        cfg[k] = saved[k]
        except Exception:
            pass

    if cfg.get("sessionid") and not cfg.get("ds_user_id"):
        uid = cfg["sessionid"].split("%3A")[0].split(":")[0]
        if uid.isdigit():
            cfg["ds_user_id"] = uid

    return cfg


def salvar_config(cfg):
    """Salva as credenciais no .env e no config_conta.json local."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
    except Exception:
        pass

    try:
        linhas = [
            "# Credenciais da conta de automação do Instagram (MANTENHA PRIVADO)\n",
            f"IG_USER={cfg.get('user', '')}\n",
            f"IG_DS_USER_ID={cfg.get('ds_user_id', '')}\n",
            f"IG_SESSIONID={cfg.get('sessionid', '')}\n"
        ]
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(linhas)
    except Exception:
        pass
