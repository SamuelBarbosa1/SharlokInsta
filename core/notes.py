import sqlite3
from datetime import datetime
from .config import DB_NAME
from .database import inicializar_banco, salvar_estado_db, carregar_estado_db


def inicializar_tabela_notas():
    """Garante a existência da tabela bloco_notas no banco SQLite."""
    inicializar_banco()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bloco_notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            conteudo TEXT NOT NULL,
            categoria TEXT DEFAULT 'GERAL',
            alvo_vinculado TEXT DEFAULT '',
            caso_id INTEGER DEFAULT NULL,
            fixada INTEGER DEFAULT 0,
            criado_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def _row_to_dict(row) -> dict:
    return {
        "id": row[0],
        "titulo": row[1],
        "conteudo": row[2],
        "categoria": row[3] or "GERAL",
        "alvo_vinculado": row[4] or "",
        "caso_id": row[5],
        "fixada": bool(row[6]),
        "criado_em": row[7],
        "atualizado_em": row[8]
    }


def listar_notas(caso_id=None) -> list:
    """Lista todas as anotações ordenadas por fixadas primeiro e mais recentes."""
    inicializar_tabela_notas()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if caso_id and str(caso_id).isdigit() and int(caso_id) > 0:
        cursor.execute("""
            SELECT id, titulo, conteudo, categoria, alvo_vinculado, caso_id, fixada, criado_em, atualizado_em
            FROM bloco_notas
            WHERE caso_id = ?
            ORDER BY fixada DESC, atualizado_em DESC, id DESC
        """, (int(caso_id),))
    else:
        cursor.execute("""
            SELECT id, titulo, conteudo, categoria, alvo_vinculado, caso_id, fixada, criado_em, atualizado_em
            FROM bloco_notas
            ORDER BY fixada DESC, atualizado_em DESC, id DESC
        """)
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def contar_notas() -> int:
    try:
        inicializar_tabela_notas()
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bloco_notas")
        total = cursor.fetchone()[0]
        conn.close()
        return int(total or 0)
    except Exception:
        return 0


def criar_nota(titulo: str, conteudo: str, categoria: str = "GERAL", alvo_vinculado: str = "", caso_id=None, fixada: bool = False) -> dict:
    """Cria uma nova anotação operacional no banco SQLite."""
    inicializar_tabela_notas()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cat = (categoria or "GERAL").strip().upper()
    if cat not in ("ONDE_PAREI", "PISTA", "PENDENCIA", "GERAL"):
        cat = "GERAL"

    alvo_clean = str(alvo_vinculado or "").replace("@", "").strip()
    cid = int(caso_id) if (caso_id and str(caso_id).isdigit() and int(caso_id) > 0) else None
    titulo_final = (titulo or "").strip() or "Anotação Rápida"

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO bloco_notas (titulo, conteudo, categoria, alvo_vinculado, caso_id, fixada, criado_em, atualizado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        titulo_final,
        (conteudo or "").strip(),
        cat,
        alvo_clean,
        cid,
        1 if fixada else 0,
        agora,
        agora
    ))
    novo_id = cursor.lastrowid
    conn.commit()
    cursor.execute("""
        SELECT id, titulo, conteudo, categoria, alvo_vinculado, caso_id, fixada, criado_em, atualizado_em
        FROM bloco_notas WHERE id = ?
    """, (novo_id,))
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row)


def atualizar_nota(nota_id: int, dados: dict) -> dict | None:
    """Atualiza uma anotação existente."""
    inicializar_tabela_notas()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, titulo, conteudo, categoria, alvo_vinculado, caso_id, fixada, criado_em, atualizado_em
        FROM bloco_notas WHERE id = ?
    """, (int(nota_id),))
    atual = cursor.fetchone()
    if not atual:
        conn.close()
        return None

    nota = _row_to_dict(atual)
    titulo = str(dados.get("titulo", nota["titulo"])).strip() or "Anotação Rápida"
    conteudo = str(dados.get("conteudo", nota["conteudo"])).strip()
    cat = str(dados.get("categoria", nota["categoria"])).strip().upper()
    if cat not in ("ONDE_PAREI", "PISTA", "PENDENCIA", "GERAL"):
        cat = "GERAL"

    alvo_clean = str(dados.get("alvo_vinculado", nota["alvo_vinculado"]) or "").replace("@", "").strip()
    if "caso_id" in dados:
        raw_cid = dados.get("caso_id")
        cid = int(raw_cid) if (raw_cid and str(raw_cid).isdigit() and int(raw_cid) > 0) else None
    else:
        cid = nota["caso_id"]

    fixada = int(bool(dados["fixada"])) if "fixada" in dados else (1 if nota["fixada"] else 0)
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE bloco_notas
        SET titulo = ?, conteudo = ?, categoria = ?, alvo_vinculado = ?, caso_id = ?, fixada = ?, atualizado_em = ?
        WHERE id = ?
    """, (titulo, conteudo, cat, alvo_clean, cid, fixada, agora, int(nota_id)))
    conn.commit()

    cursor.execute("""
        SELECT id, titulo, conteudo, categoria, alvo_vinculado, caso_id, fixada, criado_em, atualizado_em
        FROM bloco_notas WHERE id = ?
    """, (int(nota_id),))
    row = cursor.fetchone()
    conn.close()
    return _row_to_dict(row)


def alternar_fixar_nota(nota_id: int) -> dict | None:
    """Fixa ou desafixa uma nota no topo."""
    inicializar_tabela_notas()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT fixada FROM bloco_notas WHERE id = ?", (int(nota_id),))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    novo_val = 0 if row[0] else 1
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE bloco_notas SET fixada = ?, atualizado_em = ? WHERE id = ?", (novo_val, agora, int(nota_id)))
    conn.commit()
    cursor.execute("""
        SELECT id, titulo, conteudo, categoria, alvo_vinculado, caso_id, fixada, criado_em, atualizado_em
        FROM bloco_notas WHERE id = ?
    """, (int(nota_id),))
    atualizada = cursor.fetchone()
    conn.close()
    return _row_to_dict(atualizada)


def excluir_nota(nota_id: int) -> bool:
    """Remove uma nota individual."""
    inicializar_tabela_notas()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bloco_notas WHERE id = ?", (int(nota_id),))
    afetados = cursor.rowcount
    conn.commit()
    conn.close()
    return afetados > 0


def limpar_todas_notas() -> int:
    """Apaga todos os cartões de notas (preservando o rascunho rápido salvo separadamente)."""
    inicializar_tabela_notas()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bloco_notas")
    afetados = cursor.rowcount
    conn.commit()
    conn.close()
    return afetados


def obter_rascunho_rapido() -> dict:
    """Retorna o texto do quadro rápido 'Onde Parei / Próximos Passos'."""
    dados = carregar_estado_db("bloco_notas_rascunho_rapido")
    if isinstance(dados, dict):
        return {
            "texto": str(dados.get("texto", "")),
            "atualizado_em": str(dados.get("atualizado_em", ""))
        }
    return {"texto": "", "atualizado_em": ""}


def salvar_rascunho_rapido(texto: str) -> dict:
    """Salva o quadro rápido 'Onde Parei / Próximos Passos' no SQLite."""
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "texto": str(texto or ""),
        "atualizado_em": agora
    }
    salvar_estado_db("bloco_notas_rascunho_rapido", payload)
    return payload
