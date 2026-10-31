import os
import json
from datetime import datetime
from .config import CASOS_FILE
from .database import salvar_estado_db, carregar_estado_db


def carregar_casos() -> list:
    """Carrega a lista de Casos / Perfis de Investigação do JSON local ou SQLite."""
    if os.path.exists(CASOS_FILE):
        try:
            with open(CASOS_FILE, "r", encoding="utf-8") as f:
                casos = json.load(f)
                if isinstance(casos, list):
                    salvar_estado_db("casos_investigacao", casos)
                    return casos
        except Exception:
            pass

    casos_db = carregar_estado_db("casos_investigacao")
    if isinstance(casos_db, list):
        salvar_casos(casos_db)
        return casos_db
    return []


def salvar_casos(casos: list):
    """Salva os Casos / Perfis de Investigação no arquivo JSON e sincroniza no SQLite."""
    with open(CASOS_FILE, "w", encoding="utf-8") as f:
        json.dump(casos, f, indent=4, ensure_ascii=False)
    salvar_estado_db("casos_investigacao", casos)


def obter_caso_por_id(caso_id) -> dict | None:
    if not caso_id:
        return None
    try:
        cid = int(caso_id)
    except Exception:
        return None
    for c in carregar_casos():
        if int(c.get("id", 0)) == cid:
            return c
    return None


def criar_caso(nome: str, referencia: str = "", descricao: str = "", alvos_iniciais: list | None = None) -> dict:
    """Cria um novo Perfil / Caso de Investigação e vincula eventuais alvos iniciais."""
    casos = carregar_casos()
    novo_id = max([int(c.get("id", 0)) for c in casos], default=0) + 1
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    alvos_limpos = []
    if alvos_iniciais:
        for u in alvos_iniciais:
            clean = str(u).replace("@", "").strip().lower()
            if clean and clean not in alvos_limpos:
                alvos_limpos.append(clean)

    novo = {
        "id": novo_id,
        "nome": nome.strip(),
        "referencia": referencia.strip(),
        "descricao": descricao.strip(),
        "status": "EM_ANDAMENTO",
        "alvos": alvos_limpos,
        "criado_em": agora,
        "atualizado_em": agora
    }

    # Garante que se um alvo foi colocado neste novo caso, ele saia de outro caso anterior (1 caso ativo por alvo)
    if alvos_limpos:
        for c in casos:
            c["alvos"] = [a for a in c.get("alvos", []) if a.lower() not in alvos_limpos]

    casos.append(novo)
    salvar_casos(casos)

    if alvos_limpos:
        _sincronizar_caso_nos_alvos_monitorados(alvos_limpos, novo_id)

    return novo


def atualizar_caso(caso_id: int, dados: dict) -> dict | None:
    """Atualiza informações básicas (nome, referência, descrição, status) de um caso."""
    casos = carregar_casos()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    alvo_caso = None
    for c in casos:
        if int(c.get("id", 0)) == int(caso_id):
            if "nome" in dados and str(dados["nome"]).strip():
                c["nome"] = str(dados["nome"]).strip()
            if "referencia" in dados:
                c["referencia"] = str(dados["referencia"]).strip()
            if "descricao" in dados:
                c["descricao"] = str(dados["descricao"]).strip()
            if "status" in dados and dados["status"] in ["EM_ANDAMENTO", "CONCLUIDO", "ARQUIVADO"]:
                c["status"] = dados["status"]
            c["atualizado_em"] = agora
            alvo_caso = c
            break

    if alvo_caso:
        salvar_casos(casos)
    return alvo_caso


def remover_caso(caso_id: int) -> bool:
    """Remove o caso e desvincula seus alvos (mantendo alvos e mídias intactos)."""
    casos = carregar_casos()
    cid = int(caso_id)
    removido = None
    novos = []
    for c in casos:
        if int(c.get("id", 0)) == cid:
            removido = c
        else:
            novos.append(c)

    if not removido:
        return False

    salvar_casos(novos)
    alvos_antigos = removido.get("alvos", [])
    if alvos_antigos:
        _sincronizar_caso_nos_alvos_monitorados(alvos_antigos, None)
    return True


def vincular_alvo_ao_caso(username: str, caso_id=None) -> bool:
    """Vincula (ou desvincula se caso_id=None/0) uma conta investigada a um Caso."""
    clean_u = str(username).replace("@", "").strip().lower()
    if not clean_u:
        return False

    casos = carregar_casos()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cid = int(caso_id) if caso_id and str(caso_id).isdigit() and int(caso_id) > 0 else None

    for c in casos:
        atuais = [str(x).lower() for x in c.get("alvos", [])]
        if cid and int(c.get("id", 0)) == cid:
            if clean_u not in atuais:
                atuais.append(clean_u)
            c["alvos"] = atuais
            c["atualizado_em"] = agora
        else:
            if clean_u in atuais:
                c["alvos"] = [x for x in atuais if x != clean_u]
                c["atualizado_em"] = agora

    salvar_casos(casos)
    _sincronizar_caso_nos_alvos_monitorados([clean_u], cid)
    return True


def desvincular_alvos_excluidos(usernames_list: list):
    """Remove alvos excluídos de todos os casos para não deixar contadores ou tags fantasmas."""
    if not usernames_list:
        return
    excluir_set = {str(u).replace("@", "").strip().lower() for u in usernames_list if str(u).strip()}
    casos = carregar_casos()
    alterou = False
    for c in casos:
        atuais = [str(x).lower() for x in c.get("alvos", [])]
        novos = [x for x in atuais if x not in excluir_set]
        if len(novos) != len(atuais):
            c["alvos"] = novos
            c["atualizado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            alterou = True
    if alterou:
        salvar_casos(casos)


def obter_mapa_alvo_caso() -> dict:
    """Retorna dicionário {username_lower: {'caso_id': id, 'caso_nome': nome, 'caso_ref': ref}}."""
    mapa = {}
    for c in carregar_casos():
        cid = c.get("id")
        cnome = c.get("nome", "")
        cref = c.get("referencia", "")
        for u in c.get("alvos", []):
            mapa[str(u).lower()] = {
                "caso_id": cid,
                "caso_nome": cnome,
                "caso_ref": cref
            }
    return mapa


def _sincronizar_caso_nos_alvos_monitorados(usernames_lower: list, caso_id):
    """Atualiza o campo caso_id dentro de alvos_monitorados.json se o alvo já existir lá."""
    try:
        from .targets import carregar_alvos, salvar_alvos
        alvos = carregar_alvos()
        alterou = False
        uset = {u.lower() for u in usernames_lower}
        for a in alvos:
            if a.get("username", "").lower() in uset:
                a["caso_id"] = caso_id
                alterou = True
        if alterou:
            salvar_alvos(alvos)
    except Exception:
        pass


def atualizar_status_automatico_casos() -> list:
    """
    Sincroniza automaticamente o status de cada Caso:
    - Se todos os alvos do caso estão CONCLUIDOS (ou extraídos em disco), marca como CONCLUIDO.
    - Se houver alvos pendentes e o caso não foi arquivado manualmente, mantém EM_ANDAMENTO.
    - Preserva o status ARQUIVADO se definido manualmente pelo operador.
    """
    try:
        from .targets import carregar_alvos
        casos = carregar_casos()
        alvos_map = {a.get("username", "").lower(): a for a in carregar_alvos()}

        pastas_dl = set()
        if os.path.exists("downloads"):
            for item in os.listdir("downloads"):
                if os.path.isdir(os.path.join("downloads", item)):
                    pastas_dl.add(item.replace("@", "").lower())

        alterou = False
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for c in casos:
            status_atual = c.get("status", "EM_ANDAMENTO")
            if status_atual == "ARQUIVADO":
                continue

            lista_u = c.get("alvos", [])
            if not lista_u:
                continue

            total = len(lista_u)
            concluidos = 0
            for u in lista_u:
                u_low = str(u).lower()
                reg = alvos_map.get(u_low, {})
                st = reg.get("status", "")
                tem_pasta = u_low in pastas_dl
                if st == "CONCLUIDO" or tem_pasta:
                    concluidos += 1

            if total > 0 and concluidos >= total:
                if status_atual != "CONCLUIDO":
                    c["status"] = "CONCLUIDO"
                    c["atualizado_em"] = agora
                    alterou = True
            elif concluidos < total:
                if status_atual == "CONCLUIDO":
                    c["status"] = "EM_ANDAMENTO"
                    c["atualizado_em"] = agora
                    alterou = True

        if alterou:
            salvar_casos(casos)
        return casos
    except Exception as err:
        print(f"[-] Erro ao atualizar status automático dos casos: {err}")
        return carregar_casos()


