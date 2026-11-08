import os
import re
import json
import time
import uuid
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .database import DB_NAME, inicializar_banco

SHERLOCK_DATA_PATH = os.path.join("Sherlock", "resources", "data.json")

# Lista selecionada das redes mais populares para o modo "Principais Redes (Rápido)"
POPULAR_SITES = [
    "GitHub", "GitLab", "Twitter", "TikTok", "Telegram", "Reddit", "Pinterest",
    "Spotify", "Steam Community (User)", "Twitch", "YouTube", "LinkedIn", "Linktree",
    "Discord.bio", "Medium", "Duolingo", "Chess", "Roblox", "Snapchat", "Patreon",
    "DeviantArt", "Behance", "Flickr", "Vimeo", "Wattpad", "SoundCloud", "Letterboxd",
    "Lichess", "Disqus", "HackTheBox", "Codecademy", "Docker Hub", "Dribbble",
    "Goodreads", "Gravatar", "Imgur", "Kaggle", "Keybase", "Pastebin", "ProductHunt",
    "Quora", "Slack", "Substack", "Trello", "VK", "Wikipedia", "WordPress",
    "About.me", "AskFM", "Bandcamp", "Blogger", "BuyMeACoffee", "Cash App",
    "DailyMotion", "Etsy", "Fandom", "Freelancer", "Giphy", "Habbo", "MixCloud"
]

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

# Memória de escaneamentos em andamento / recentes
scans_em_andamento = {}


def carregar_manifesto_sherlock() -> dict:
    """Carrega o manifesto de sites data.json do Sherlock."""
    if not os.path.exists(SHERLOCK_DATA_PATH):
        # Tenta caminho alternativo
        alt_path = os.path.join(os.path.dirname(__file__), "..", "Sherlock", "resources", "data.json")
        if os.path.exists(alt_path):
            with open(alt_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    with open(SHERLOCK_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def criar_sessao_http() -> requests.Session:
    """Cria uma sessão HTTP reutilizável com pool de conexões rápido."""
    s = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=40,
        pool_maxsize=40,
        max_retries=Retry(total=1, backoff_factor=0.2, status_forcelist=[502, 503, 504])
    )
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update({
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"'
    })
    return s


def verificar_site_individual(site_name: str, site_data: dict, username: str, session: requests.Session) -> dict | None:
    """
    Executa a sonda (probe) para um site específico seguindo as regras do Sherlock.
    Retorna o dict do resultado se encontrado, ou None se inexistente/erro.
    """
    try:
        url_template = site_data.get("url", "")
        if not url_template:
            return None

        # 1. Checagem de regex do username (se houver regra no site)
        regex_check = site_data.get("regexCheck")
        if regex_check:
            try:
                if not re.search(regex_check, username):
                    return None
            except Exception:
                pass

        url_final = url_template.replace("{}", username)
        url_probe = site_data.get("urlProbe", url_final).replace("{}", username)

        req_method = site_data.get("request_method", "GET").upper()
        headers = dict(session.headers)
        if "headers" in site_data and isinstance(site_data["headers"], dict):
            headers.update(site_data["headers"])

        # Timeout curto para velocidade (4 segundos por site)
        timeout = 4.5

        if req_method == "HEAD":
            resp = session.head(url_probe, headers=headers, timeout=timeout, allow_redirects=True)
        elif req_method == "POST":
            payload = site_data.get("request_payload", {})
            if isinstance(payload, dict):
                # Substitui {} pelo username dentro dos valores do payload
                payload_proc = {k: str(v).replace("{}", username) for k, v in payload.items()}
                resp = session.post(url_probe, data=payload_proc, headers=headers, timeout=timeout, allow_redirects=True)
            else:
                resp = session.post(url_probe, headers=headers, timeout=timeout, allow_redirects=True)
        else:
            resp = session.get(url_probe, headers=headers, timeout=timeout, allow_redirects=True)

        error_type = site_data.get("errorType")
        if isinstance(error_type, str):
            error_types = [error_type]
        elif isinstance(error_type, list):
            error_types = error_type
        else:
            error_types = ["status_code"]

        found = (resp.status_code == 200)

        # Validação 1: Status Code
        if "status_code" in error_types:
            err_code = site_data.get("errorCode")
            if err_code is not None:
                if isinstance(err_code, int) and resp.status_code == err_code:
                    found = False
                elif isinstance(err_code, list) and resp.status_code in err_code:
                    found = False
            elif resp.status_code in [404, 400, 410, 403, 500, 502, 503]:
                found = False

        # Validação 2: Mensagem de erro no corpo
        if "message" in error_types and found:
            msgs = site_data.get("errorMsg", [])
            if isinstance(msgs, str):
                msgs = [msgs]
            text_body = resp.text
            if any(m in text_body for m in msgs):
                found = False

        # Validação 3: Redirecionamento para URL de erro / login
        if "response_url" in error_types and found:
            err_url = site_data.get("errorUrl") or site_data.get("response_url")
            if err_url and err_url in resp.url:
                found = False
            main_url = site_data.get("urlMain", "").rstrip("/")
            if main_url and resp.url.rstrip("/") == main_url:
                found = False

        if found:
            return {
                "site": site_name,
                "url": url_final,
                "url_main": site_data.get("urlMain", ""),
                "is_nsfw": bool(site_data.get("isNSFW", False)),
                "status_code": resp.status_code,
                "encontrado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

    except Exception:
        pass

    return None


def iniciar_scan_sherlock_background(username: str, modo: str = "principais", incluir_nsfw: bool = False, caso_id=None) -> str:
    """
    Inicia uma varredura do Sherlock em thread em background.
    Retorna o scan_id para acompanhamento em tempo real via API.
    """
    clean_user = str(username).replace("@", "").strip()
    scan_id = str(uuid.uuid4())[:12]

    manifesto = carregar_manifesto_sherlock()
    sites_alvo = {}

    for k, v in manifesto.items():
        if k.startswith("$"):
            continue
        if not incluir_nsfw and v.get("isNSFW", False):
            continue

        if modo == "principais":
            if k in POPULAR_SITES:
                sites_alvo[k] = v
        else:
            sites_alvo[k] = v

    total_sites = len(sites_alvo)

    estado = {
        "scan_id": scan_id,
        "username": clean_user,
        "modo": modo,
        "incluir_nsfw": incluir_nsfw,
        "caso_id": int(caso_id) if caso_id and str(caso_id).isdigit() and int(caso_id) > 0 else None,
        "status": "PROCURANDO",
        "total": total_sites,
        "processados": 0,
        "encontrados": [],
        "inicio_epoch": time.time(),
        "fim_epoch": None,
        "tempo_decorrido_s": 0,
        "cancelar": False
    }

    scans_em_andamento[scan_id] = estado

    def _worker():
        session = criar_sessao_http()
        max_workers = 35 if modo == "todos" else 20

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_site = {
                executor.submit(verificar_site_individual, sname, sdata, clean_user, session): sname
                for sname, sdata in sites_alvo.items()
            }

            for future in as_completed(future_to_site):
                if estado.get("cancelar"):
                    estado["status"] = "CANCELADO"
                    break

                estado["processados"] += 1
                estado["tempo_decorrido_s"] = round(time.time() - estado["inicio_epoch"], 1)

                try:
                    res = future.result()
                    if res:
                        estado["encontrados"].append(res)
                except Exception:
                    pass

        if estado["status"] != "CANCELADO":
            estado["status"] = "CONCLUIDO"

        estado["fim_epoch"] = time.time()
        estado["tempo_decorrido_s"] = round(estado["fim_epoch"] - estado["inicio_epoch"], 1)

        # Salva resultados no disco e banco de dados SQLite
        _salvar_resultados_scan(estado)

    threading.Thread(target=_worker, daemon=True).start()
    return scan_id


def obter_status_scan_sherlock(scan_id: str) -> dict | None:
    """Retorna o status em tempo real de um scan ativo ou histórico recente."""
    if scan_id in scans_em_andamento:
        st = scans_em_andamento[scan_id]
        if st["status"] == "PROCURANDO":
            st["tempo_decorrido_s"] = round(time.time() - st["inicio_epoch"], 1)
        return st

    # Se não está na memória recente, tenta buscar do banco SQLite
    return _obter_scan_do_banco(scan_id)


def cancelar_scan_sherlock(scan_id: str) -> bool:
    """Cancela um escaneamento em andamento."""
    if scan_id in scans_em_andamento:
        scans_em_andamento[scan_id]["cancelar"] = True
        scans_em_andamento[scan_id]["status"] = "CANCELADO"
        return True
    return False


def _salvar_resultados_scan(estado: dict):
    """
    Grava as descobertas exclusivamente no banco SQLite (sherlock_scans).
    NÃO cria nem polui pastas na aba de mídias baixadas (downloads/).
    """
    username = estado["username"]
    encontrados = estado["encontrados"]

    # Salva no banco de dados SQLite
    try:
        import sqlite3
        inicializar_banco()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sherlock_scans (
                scan_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                modo TEXT NOT NULL,
                total INTEGER DEFAULT 0,
                encontrados_count INTEGER DEFAULT 0,
                tempo_decorrido_s REAL DEFAULT 0,
                encontrados_json TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                caso_id INTEGER
            )
        """)
        cursor.execute("""
            INSERT OR REPLACE INTO sherlock_scans 
            (scan_id, username, modo, total, encontrados_count, tempo_decorrido_s, encontrados_json, criado_em, caso_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            estado["scan_id"],
            username,
            estado["modo"],
            estado["total"],
            len(encontrados),
            estado.get("tempo_decorrido_s", 0),
            json.dumps(encontrados, ensure_ascii=False),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            estado.get("caso_id")
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[-] Erro ao persistir scan Sherlock no SQLite: {e}")


def excluir_scan_sherlock_db(scan_id: str) -> bool:
    """Exclui um registro específico de varredura do Sherlock da memória e do SQLite."""
    if scan_id in scans_em_andamento:
        try:
            del scans_em_andamento[scan_id]
        except Exception:
            pass

    try:
        import sqlite3
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sherlock_scans WHERE scan_id = ?", (scan_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[-] Erro ao excluir scan Sherlock {scan_id}: {e}")
        return False


def limpar_todo_historico_sherlock_db() -> bool:
    """Limpa todo o histórico de varreduras do Sherlock da memória e do SQLite."""
    scans_em_andamento.clear()
    try:
        import sqlite3
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sherlock_scans")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[-] Erro ao limpar histórico completo do Sherlock: {e}")
        return False


def _obter_scan_do_banco(scan_id: str) -> dict | None:
    try:
        import sqlite3
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT scan_id, username, modo, total, encontrados_count, tempo_decorrido_s, encontrados_json, criado_em, caso_id
            FROM sherlock_scans WHERE scan_id = ?
        """, (scan_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "scan_id": row[0],
            "username": row[1],
            "modo": row[2],
            "total": row[3],
            "processados": row[3],
            "encontrados": json.loads(row[6]),
            "tempo_decorrido_s": row[5],
            "status": "CONCLUIDO",
            "caso_id": row[8],
            "criado_em": row[7]
        }
    except Exception:
        return None


def listar_historico_sherlock_db(limite: int = 25) -> list:
    """Retorna os escaneamentos recentes persistidos no SQLite."""
    try:
        import sqlite3
        inicializar_banco()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sherlock_scans (
                scan_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                modo TEXT NOT NULL,
                total INTEGER DEFAULT 0,
                encontrados_count INTEGER DEFAULT 0,
                tempo_decorrido_s REAL DEFAULT 0,
                encontrados_json TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                caso_id INTEGER
            )
        """)
        cursor.execute("""
            SELECT scan_id, username, modo, total, encontrados_count, tempo_decorrido_s, criado_em, caso_id
            FROM sherlock_scans ORDER BY criado_em DESC LIMIT ?
        """, (limite,))
        rows = cursor.fetchall()
        conn.close()

        lista = []
        for r in rows:
            lista.append({
                "scan_id": r[0],
                "username": r[1],
                "modo": r[2],
                "total": r[3],
                "encontrados_count": r[4],
                "tempo_decorrido_s": r[5],
                "criado_em": r[6],
                "caso_id": r[7]
            })
        return lista
    except Exception:
        return []
