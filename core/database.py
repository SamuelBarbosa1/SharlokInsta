import sqlite3
from datetime import datetime
from .config import DB_NAME

def inicializar_banco():
    """Garante a criação da tabela de coletas no SQLite."""
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
    conn.commit()
    conn.close()


def registrar_coleta_db(username: str, diretorio: str, qtd_midias: int, status: str):
    """Registra uma extração no banco de dados SQLite."""
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
