import os
import sys
import shutil
import json
from datetime import datetime

# Garante suporte a UTF-8 no Windows Console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BACKUP_DIR = "_backup_local"
DOWNLOADS_DIR = "downloads"

ARQUIVOS_LIMPAR = [
    "contas_pool.json",
    "alvos_monitorados.json",
    "casos_investigacao.json",
    "alvos.txt",
    "osint_coletas.db",
    "osint_coletas.db-journal"
]


def fazer_backup_e_limpar():
    print("=" * 65)
    print("  SHARLOKINSTA - HIGIENIZADOR PARA SUBIDA AO GITHUB")
    print("=" * 65)

    os.makedirs(BACKUP_DIR, exist_ok=True)
    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Faz backup de segurança dos dados locais
    print(f"\n[1/4] Criando backup de seguranca em '{BACKUP_DIR}/'...")
    itens_salvos = 0
    for arq in ARQUIVOS_LIMPAR:
        if os.path.exists(arq):
            dest = os.path.join(BACKUP_DIR, arq)
            # Se o arquivo atual for vazio/resetado mas o backup já contiver dados reais, preserva o backup existente!
            if os.path.exists(dest) and os.path.getsize(arq) <= 4 and os.path.getsize(dest) > 4:
                print(f"  [i] Preservando backup com dados existente: {dest}")
                itens_salvos += 1
                continue
            shutil.copy2(arq, dest)
            itens_salvos += 1
            print(f"  [+] Backup: {arq} -> {dest}")

    with open(os.path.join(BACKUP_DIR, "info_backup.txt"), "w", encoding="utf-8") as f:
        f.write(f"Backup realizado com sucesso em {agora_str}\n")
        f.write(f"Total de arquivos protegidos: {itens_salvos}\n")

    # 2. Reseta arquivos JSON e TXT do repositório para estado virgem/limpo
    print("\n[2/4] Resetando arquivos de banco e configuracao para estado limpo...")
    with open("contas_pool.json", "w", encoding="utf-8") as f:
        json.dump([], f, indent=4)
    print("  [OK] contas_pool.json resetado para [] (nenhum cookie/conta exposta).")

    with open("alvos_monitorados.json", "w", encoding="utf-8") as f:
        json.dump([], f, indent=4)
    print("  [OK] alvos_monitorados.json resetado para [].")

    with open("casos_investigacao.json", "w", encoding="utf-8") as f:
        json.dump([], f, indent=4)
    print("  [OK] casos_investigacao.json resetado para [].")

    with open("alvos.txt", "w", encoding="utf-8") as f:
        f.write("# Insira um @username por linha\n")
    print("  [OK] alvos.txt limpo.")

    # 3. Limpa arquivos temporários (banco SQLite local, logs e cache)
    print("\n[3/4] Removendo banco SQLite local e logs de execucao...")
    for db_file in ["osint_coletas.db", "osint_coletas.db-journal"]:
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
                print(f"  [OK] {db_file} removido.")
            except Exception as e:
                print(f"  [-] Aviso: {db_file} em uso ({e}).")

    for f in os.listdir("."):
        if f.endswith(".log"):
            try:
                os.remove(f)
                print(f"  [OK] Log {f} removido.")
            except Exception:
                pass

    # 4. Limpa pasta de downloads (mantém a pasta vazia com .gitkeep se desejar)
    print("\n[4/4] Limpando pasta de midias baixadas (downloads/)...")
    if os.path.exists(DOWNLOADS_DIR):
        for item in os.listdir(DOWNLOADS_DIR):
            p = os.path.join(DOWNLOADS_DIR, item)
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p)
                elif os.path.isfile(p) and item != ".gitkeep":
                    os.remove(p)
            except Exception as e:
                print(f"  [-] Aviso ao remover {item}: {e}")
    else:
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)

    gitkeep = os.path.join(DOWNLOADS_DIR, ".gitkeep")
    if not os.path.exists(gitkeep):
        with open(gitkeep, "w") as f:
            pass
    print("  [OK] downloads/ limpa com sucesso.")

    print("\n" + "=" * 65)
    print("[OK] REPOSITORIO 100% HIGIENIZADO E SEGURO PARA SUBIR NO GITHUB!")
    print("=" * 65)
    print("\nComandos recomendados para subir:")
    print("  git add .")
    print("  git commit -m \"feat: atualizacoes do sistema\"")
    print("  git push origin main")
    print("\nApos subir para o GitHub, para restaurar seus dados locais:")
    print("  python limpar_para_github.py --restaurar")
    print("  (ou execute: .\\restaurar.bat)")
    print("=" * 65)


def restaurar_backup():
    # Garante suporte a UTF-8 no Windows Console
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("=" * 65)
    print("  SHARLOKINSTA - RESTAURAR DADOS LOCAIS APOS GITHUB")
    print("=" * 65)

    if not os.path.exists(BACKUP_DIR):
        print(f"[-] Erro: Pasta de backup '{BACKUP_DIR}' nao encontrada!")
        return

    restaurados = 0
    for arq in ARQUIVOS_LIMPAR:
        src = os.path.join(BACKUP_DIR, arq)
        if os.path.exists(src):
            shutil.copy2(src, arq)
            restaurados += 1
            print(f"  [+] Restaurado: {arq}")

    print("\n" + "=" * 65)
    print(f"[OK] SUCESSO! {restaurados} arquivo(s) restaurados com suas contas, casos e alvos!")
    print("     Seu ambiente local de trabalho voltou ao estado normal.")
    print("=" * 65)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].lower() in ["--restaurar", "-r", "restaurar", "--restore"]:
        restaurar_backup()
    else:
        fazer_backup_e_limpar()
