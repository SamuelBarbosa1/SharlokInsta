import os
import json

# Arquivos locais do sistema
CONFIG_FILE = "config_conta.json"
CONTAS_POOL_FILE = "contas_pool.json"
MONITOR_FILE = "alvos_monitorados.json"
CASOS_FILE = "casos_investigacao.json"
ALVOS_TXT_FILE = "alvos.txt"
DB_NAME = "osint_coletas.db"
ENV_FILE = ".env"

# Controle de Visibilidade para Equipe Técnica vs Cliente Final
# Altere para False quando for entregar o painel aos clientes finais para ocultar a aba "Atualizações"
EXIBIR_ABA_ATUALIZACOES = True

# Valores padrão iniciais (podem ser alterados em tempo real na aba Configurações do Painel Web)
COOLDOWN_MINUTOS = 120          # 2 horas após recusa
TIMEOUT_VACUO_MINUTOS = 2880    # 48 horas (2 dias) aguardando resposta antes de rotacionar
DELAY_MIN_SEGS = 5              # Delay mínimo anti-bloqueio entre envios
DELAY_MAX_SEGS = 10             # Delay máximo anti-bloqueio entre envios
MAX_SCROLLS_PADRAO = 6          # Rolagens no feed (~70 fotos)


def obter_parametros_automacao() -> dict:
    """Retorna os parâmetros de tempo ativos (salvos no SQLite ou valores padrão)."""
    padrao = {
        "cooldown_minutos": COOLDOWN_MINUTOS,
        "timeout_vacuo_minutos": TIMEOUT_VACUO_MINUTOS,
        "delay_min_segs": DELAY_MIN_SEGS,
        "delay_max_segs": DELAY_MAX_SEGS,
        "max_scrolls_padrao": MAX_SCROLLS_PADRAO
    }
    try:
        from .database import carregar_estado_db
        salvos = carregar_estado_db("parametros_automacao")
        if isinstance(salvos, dict):
            padrao.update({k: int(v) for k, v in salvos.items() if k in padrao and str(v).isdigit()})
    except Exception:
        pass
    return padrao


def salvar_parametros_automacao(novos_params: dict) -> dict:
    """Salva os parâmetros de automação no SQLite e retorna o dicionário consolidado."""
    atuais = obter_parametros_automacao()
    for chave in ["cooldown_minutos", "timeout_vacuo_minutos", "delay_min_segs", "delay_max_segs", "max_scrolls_padrao"]:
        if chave in novos_params:
            try:
                val = int(novos_params[chave])
                if val >= 1:
                    atuais[chave] = val
            except Exception:
                pass
    if atuais["delay_max_segs"] < atuais["delay_min_segs"]:
        atuais["delay_max_segs"] = atuais["delay_min_segs"]

    try:
        from .database import salvar_estado_db
        salvar_estado_db("parametros_automacao", atuais)
    except Exception:
        pass
    return atuais


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
