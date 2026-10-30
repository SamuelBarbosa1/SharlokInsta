import sqlite3
import json
from datetime import datetime
from .config import DB_NAME

def inicializar_banco():
    """Garante a criação das tabelas de coletas, logs e estado persistente no SQLite."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS coletas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            data_execucao TEXT NOT NULL,
            diretorio_local TEXT NOT NULL,
            qtd_midias INTEGER DEFAULT 0,
            status TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs_sistema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            data_hora TEXT NOT NULL,
            nivel TEXT NOT NULL,
            mensagem TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS estado_sistema (
            chave TEXT PRIMARY KEY,
            valor_json TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def registrar_coleta_db(username: str, diretorio: str, qtd_midias: int, status: str):
    """Registra uma extração no banco de dados SQLite."""
    try:
        inicializar_banco()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO coletas (username, data_execucao, diretorio_local, qtd_midias, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            username,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            diretorio,
            qtd_midias,
            status
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass


def salvar_log_db(timestamp: str, nivel: str, mensagem: str):
    """Salva uma linha de log no banco SQLite mantendo até 500 registros recentes."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO logs_sistema (timestamp, data_hora, nivel, mensagem)
            VALUES (?, ?, ?, ?)
        """, (timestamp, agora, nivel, mensagem))
        cursor.execute("""
            DELETE FROM logs_sistema
            WHERE id NOT IN (
                SELECT id FROM logs_sistema ORDER BY id DESC LIMIT 500
            )
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass


def carregar_logs_db(limite: int = 300):
    """Carrega os últimos logs persistidos no banco SQLite."""
    try:
        inicializar_banco()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, nivel, mensagem
            FROM (
                SELECT id, timestamp, nivel, mensagem
                FROM logs_sistema
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
        """, (limite,))
        rows = cursor.fetchall()
        conn.close()
        return [{"timestamp": r[0], "nivel": r[1], "mensagem": r[2]} for r in rows]
    except Exception:
        return []


def limpar_logs_db():
    """Remove todos os logs armazenados no banco SQLite."""
    try:
        inicializar_banco()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM logs_sistema")
        conn.commit()
        conn.close()
    except Exception:
        pass


def salvar_estado_db(chave: str, dados):
    """Salva uma estrutura JSON (como pool de contas ou alvos) no SQLite."""
    try:
        inicializar_banco()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        valor_str = json.dumps(dados, ensure_ascii=False)
        cursor.execute("""
            INSERT INTO estado_sistema (chave, valor_json, atualizado_em)
            VALUES (?, ?, ?)
            ON CONFLICT(chave) DO UPDATE SET
                valor_json = excluded.valor_json,
                atualizado_em = excluded.atualizado_em
        """, (chave, valor_str, agora))
        conn.commit()
        conn.close()
    except Exception:
        pass


def carregar_estado_db(chave: str, padrao=None):
    """Recupera uma estrutura JSON salva no SQLite."""
    try:
        inicializar_banco()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT valor_json FROM estado_sistema WHERE chave = ?", (chave,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return json.loads(row[0])
    except Exception:
        pass
    return padrao
