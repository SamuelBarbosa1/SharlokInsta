import os
import json
from datetime import datetime
from .config import MONITOR_FILE
from .pool import obter_conta_ativa

def carregar_alvos():
    """Carrega os alvos em monitoramento do arquivo alvos_monitorados.json."""
    if os.path.exists(MONITOR_FILE):
        try:
            with open(MONITOR_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def salvar_alvos(alvos):
    """Salva os alvos em monitoramento no arquivo alvos_monitorados.json."""
    with open(MONITOR_FILE, "w", encoding="utf-8") as f:
        json.dump(alvos, f, indent=4, ensure_ascii=False)


def registrar_novo_alvo(username, is_private=True, conta_usada=None):
    """Registra ou atualiza um alvo, gravando a conta responsável e o histórico de tentativas."""
    alvos = carregar_alvos()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not conta_usada:
        c_ativa = obter_conta_ativa()
        conta_usada = c_ativa.get("user", "desconhecido")

    # Verifica se já existe
    for a in alvos:
        if a["username"].lower() == username.lower():
            a["is_private"] = is_private
            a["status"] = "AGUARDANDO_APROVACAO"
            a["conta_atual"] = conta_usada
            a["atualizado_em"] = agora
            a["cooldown_ate"] = None

            if "tentativas" not in a or not isinstance(a["tentativas"], list):
                a["tentativas"] = []
            a["tentativas"].append({
                "conta": conta_usada,
                "solicitado_em": agora,
                "status": "SOLICITADO"
            })
            salvar_alvos(alvos)
            return

    alvos.append({
        "username": username,
        "is_private": is_private,
        "status": "AGUARDANDO_APROVACAO",
        "conta_atual": conta_usada,
        "tentativas": [
            {
                "conta": conta_usada,
                "solicitado_em": agora,
                "status": "SOLICITADO"
            }
        ],
        "cooldown_ate": None,
        "solicitado_em": agora,
        "atualizado_em": agora
    })
    salvar_alvos(alvos)
