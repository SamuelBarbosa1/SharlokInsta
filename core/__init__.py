# core/__init__.py
from .config import (
    CONFIG_FILE,
    CONTAS_POOL_FILE,
    MONITOR_FILE,
    ALVOS_TXT_FILE,
    DB_NAME,
    ENV_FILE,
    COOLDOWN_MINUTOS,
    TIMEOUT_VACUO_MINUTOS,
    DELAY_MIN_SEGS,
    DELAY_MAX_SEGS,
    carregar_dotenv,
    carregar_config,
    salvar_config
)
from .database import inicializar_banco, registrar_coleta_db
from .pool import (
    carregar_pool_contas,
    salvar_pool_contas,
    obter_conta_ativa,
    obter_conta_por_user
)
from .targets import (
    carregar_alvos,
    salvar_alvos,
    registrar_novo_alvo,
    carregar_alvos_do_arquivo,
    distribuir_alvos_em_massa
)
