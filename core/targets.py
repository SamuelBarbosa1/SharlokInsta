import os
import json
from datetime import datetime
from .config import MONITOR_FILE, ALVOS_TXT_FILE
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


def carregar_alvos_do_arquivo(caminho=ALVOS_TXT_FILE):
    """
    Lê o arquivo alvos.txt e retorna uma lista de usernames limpos e únicos.
    Ignora linhas vazias, espaços em branco e comentários iniciados com '#'.
    """
    if not os.path.exists(caminho):
        return []

    alvos = []
    with open(caminho, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                user = line.replace("@", "").strip().lower()
                if user and user not in alvos:
                    alvos.append(user)
    return alvos


def distribuir_alvos_em_massa(alvos, pool_contas):
    """
    Distribui uma lista de alvos entre as contas ativas do pool em round-robin.
    Retorna uma lista de tuplas: [(alvo_username, conta_dict), ...]
    """
    contas_ativas = [c for c in pool_contas if c.get("ativo", True) and c.get("sessionid")]
    if not contas_ativas or not alvos:
        return []

    distribuicao = []
    for idx, alvo in enumerate(alvos):
        conta = contas_ativas[idx % len(contas_ativas)]
        distribuicao.append((alvo, conta))
    return distribuicao
