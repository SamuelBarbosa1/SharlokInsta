import os
import sys
import shutil
import subprocess
from datetime import datetime
from core.database import inicializar_banco, registrar_coleta_db
from core.targets import carregar_alvos, salvar_alvos

GO_BIN_PATH = os.path.join("bin", "sharlok-engine.exe" if sys.platform == "win32" else "sharlok-engine")


def is_go_engine_disponivel() -> bool:
    """Verifica se o binário compilado em Go está pronto para execução."""
    return os.path.exists(GO_BIN_PATH) and os.path.isfile(GO_BIN_PATH)


def _limpar_pasta_se_vazia(pasta_destino: str):
    """Remove a pasta do perfil caso nenhuma mídia/relatório válido tenha sido salvo."""
    if not os.path.isdir(pasta_destino):
        return
    total = 0
    for _r, _d, files in os.walk(pasta_destino):
        total += len(files)
    if total == 0:
        try:
            shutil.rmtree(pasta_destino)
        except Exception:
            pass


def extrair_perfil_via_go(
    username: str,
    sessionid: str,
    ds_user_id: str = "",
    max_feed: int = 120,
    max_followers: int = 0,
    max_following: int = 0,
    workers: int = 12,
    delay_ms: int = 350
) -> dict:
    """
    Executa a engine Go em subprocess transmitindo logs linha a linha em tempo real
    para o StdoutInterceptor do Flask (aparecendo instantaneamente no painel Web).

    Códigos de saída da Engine Go:
      0 -> Sucesso (perfil público ou já aceito extraído)
      3 -> Perfil Privado e bot ainda não aceito (evita fallback inútil e pasta vazia)
      4 -> Perfil não encontrado / inexistente no Instagram
      5 -> SessionID expirado / redirecionado para tela de login
      2 -> Restrição/erro REST (elegível para fallback automático via Playwright)
    """
    inicializar_banco()
    clean_user = username.replace("@", "").strip()
    pasta_destino = os.path.join("downloads", f"@{clean_user}")

    if not is_go_engine_disponivel():
        print(f"[-] Binário da Engine Go ({GO_BIN_PATH}) não encontrado. Compile com 'go build' na pasta engine-go/.")
        return {"status": "BINARIO_AUSENTE", "arquivos": 0, "codigo": -1}

    cmd = [
        os.path.abspath(GO_BIN_PATH),
        "-username", clean_user,
        "-sessionid", sessionid,
        "-out", os.path.abspath(pasta_destino),
        "-max_feed", str(max_feed),
        "-max_followers", str(max_followers),
        "-max_following", str(max_following),
        "-workers", str(workers),
        "-delay_ms", str(delay_ms)
    ]
    if ds_user_id:
        cmd.extend(["-ds_user_id", ds_user_id])

    print(f"[*] [Go Engine] Disparando worker de alta velocidade para @{clean_user}...")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1
    )

    for line in iter(process.stdout.readline, ""):
        line_clean = line.rstrip("\r\n")
        if line_clean:
            print(line_clean)

    process.stdout.close()
    return_code = process.wait()

    total_arquivos = 0
    if os.path.exists(pasta_destino):
        for _r, _d, files in os.walk(pasta_destino):
            total_arquivos += len(files)

    if return_code == 0 and total_arquivos > 0:
        registrar_coleta_db(clean_user, pasta_destino, total_arquivos, "CONCLUIDO")

        alvos_atuais = carregar_alvos()
        alterou = False
        agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for a in alvos_atuais:
            if a.get("username", "").lower() == clean_user.lower():
                a["status"] = "CONCLUIDO"
                a["qtd_fotos_baixadas"] = total_arquivos
                a["concluido_em"] = agora_str
                a["atualizado_em"] = agora_str
                alterou = True
        if alterou:
            salvar_alvos(alvos_atuais)

        try:
            from core.cases import atualizar_status_automatico_casos
            atualizar_status_automatico_casos()
        except Exception:
            pass

        print(f"[✔] [Go Engine] Finalizado com sucesso! {total_arquivos} arquivo(s) salvos em {pasta_destino}.")
        return {"status": "SUCESSO", "arquivos": total_arquivos, "codigo": 0}

    # Limpa pasta caso tenha ficado vazia em tentativa interrompida
    _limpar_pasta_se_vazia(pasta_destino)

    if return_code == 3:
        return {"status": "PRIVADO_NAO_ACEITO", "arquivos": 0, "codigo": 3}
    if return_code == 4:
        return {"status": "PERFIL_INEXISTENTE", "arquivos": 0, "codigo": 4}
    if return_code == 5:
        return {"status": "SESSAO_EXPIRADA", "arquivos": 0, "codigo": 5}

    print(f"[-] [Go Engine] Processo encerrou com código {return_code}.")
    return {"status": "ERRO_REST", "arquivos": total_arquivos, "codigo": return_code}
