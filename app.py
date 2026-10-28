import os
import json
import threading
import queue
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory, Response

from core.database import inicializar_banco
from core.pool import carregar_pool_contas, salvar_pool_contas, obter_conta_ativa
from core.targets import carregar_alvos, salvar_alvos, registrar_novo_alvo
from core.config import CONTAS_POOL_FILE, ALVOS_TXT_FILE

from scraper.browser import criar_contexto_desktop
from scraper.profile import obter_info_perfil
from scraper.extractor import extrair_e_baixar_fotos
from flows.monitor import fluxo_verificar_e_baixar
from flows.sentinel import modo_sentinela
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# Buffer circular de logs em memória para o frontend
LOG_MESSAGES = []
LOG_LOCK = threading.Lock()
MAX_LOGS = 300

sentinela_thread = None
sentinela_ativo = False

def log_event(mensagem: str, nivel: str = "INFO"):
    """Registra uma mensagem com timestamp para exibição no frontend."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = {
        "timestamp": timestamp,
        "nivel": nivel,
        "mensagem": mensagem
    }
    with LOG_LOCK:
        LOG_MESSAGES.append(entry)
        if len(LOG_MESSAGES) > MAX_LOGS:
            LOG_MESSAGES.pop(0)
    print(f"[{timestamp}] [{nivel}] {mensagem}")

# Rota principal
@app.route("/")
def index():
    return render_template("index.html")

# API: Status e Estatísticas Rápidas
@app.route("/api/stats", methods=["GET"])
def api_stats():
    contas = carregar_pool_contas()
    contas_ativas = [c for c in contas if c.get("ativo") in [True, "Sim", "true", "1"]]
    alvos = carregar_alvos()
    
    concluidos = len([a for a in alvos if a.get("status") == "CONCLUIDO"])
    pendentes = len([a for a in alvos if a.get("status") in ["AGUARDANDO_APROVACAO", "SOLICITADO", "COOLDOWN"]])
    
    # Contabiliza downloads locais
    downloads_dir = "downloads"
    perfis_baixados = 0
    if os.path.exists(downloads_dir):
        perfis_baixados = len([d for d in os.listdir(downloads_dir) if os.path.isdir(os.path.join(downloads_dir, d))])

    return jsonify({
        "total_contas": len(contas),
        "contas_ativas": len(contas_ativas),
        "total_alvos": len(alvos),
        "alvos_concluidos": concluidos,
        "alvos_pendentes": pendentes,
        "perfis_baixados": perfis_baixados,
        "sentinela_ativo": sentinela_ativo
    })

# API: Pool de Contas
@app.route("/api/contas", methods=["GET", "POST"])
def api_contas():
    if request.method == "GET":
        return jsonify(carregar_pool_contas())
    
    data = request.json or {}
    contas = carregar_pool_contas()
    
    ds_user_id = data.get("ds_user_id", "").strip()
    sessionid = data.get("sessionid", "").strip()
    if not ds_user_id and ("%3A" in sessionid or ":" in sessionid):
        uid = sessionid.split("%3A")[0].split(":")[0]
        if uid.isdigit():
            ds_user_id = uid

    novo_id = max([c.get("id", 0) for c in contas], default=0) + 1
    nova_conta = {
        "id": novo_id,
        "user": data.get("user", "").strip().replace("@", ""),
        "ds_user_id": ds_user_id,
        "sessionid": sessionid,
        "ativo": "Sim" if data.get("ativo", True) else "Não",
        "adicionado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    contas.append(nova_conta)
    salvar_pool_contas(contas)
    log_event(f"Conta @{nova_conta['user']} adicionada ao pool.", "SUCESSO")
    return jsonify({"sucesso": True, "conta": nova_conta})

@app.route("/api/contas/<int:conta_id>/toggle", methods=["POST"])
def api_conta_toggle(conta_id):
    contas = carregar_pool_contas()
    for c in contas:
        if c.get("id") == conta_id:
            ativo_atual = c.get("ativo") in [True, "Sim", "true", "1"]
            c["ativo"] = "Não" if ativo_atual else "Sim"
            salvar_pool_contas(contas)
            log_event(f"Conta @{c.get('user')} agora está {'ATIVA' if c['ativo'] == 'Sim' else 'INATIVA'}.")
            return jsonify({"sucesso": True, "novo_status": c["ativo"]})
    return jsonify({"sucesso": False, "erro": "Conta não encontrada"}), 404

@app.route("/api/contas/<int:conta_id>", methods=["DELETE", "PUT"])
def api_conta_update(conta_id):
    contas = carregar_pool_contas()
    if request.method == "DELETE":
        novas = [c for c in contas if c.get("id") != conta_id]
        salvar_pool_contas(novas)
        log_event(f"Conta ID {conta_id} removida do pool.", "AVISO")
        return jsonify({"sucesso": True})
    
    data = request.json or {}
    for c in contas:
        if c.get("id") == conta_id:
            if "user" in data: c["user"] = data["user"].strip().replace("@", "")
            if "sessionid" in data:
                new_session = data["sessionid"].strip()
                c["sessionid"] = new_session
                if ("%3A" in new_session or ":" in new_session) and not data.get("ds_user_id"):
                    uid = new_session.split("%3A")[0].split(":")[0]
                    if uid.isdigit():
                        c["ds_user_id"] = uid
            if "ds_user_id" in data and data["ds_user_id"]:
                c["ds_user_id"] = data["ds_user_id"].strip()
            salvar_pool_contas(contas)
            log_event(f"Credenciais da conta @{c.get('user')} atualizadas com sucesso.", "SUCESSO")
            return jsonify({"sucesso": True, "conta": c})
    return jsonify({"sucesso": False, "erro": "Conta não encontrada"}), 404

# API: Testar Sessão de uma Conta
@app.route("/api/contas/<int:conta_id>/testar", methods=["POST"])
def api_testar_conta(conta_id):
    contas = carregar_pool_contas()
    conta = next((c for c in contas if c.get("id") == conta_id), None)
    if not conta:
        return jsonify({"sucesso": False, "erro": "Conta não encontrada"}), 404

    sessionid = conta.get("sessionid")
    if not sessionid:
        return jsonify({"sucesso": False, "status": "SEM_SESSIONID", "mensagem": "Sem sessionid configurado"})

    def _test():
        log_event(f"Testando login da conta @{conta.get('user')}...")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = criar_contexto_desktop(browser, conta)
                page = ctx.new_page()
                page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
                page.wait_for_timeout(3500)
                url_final = page.url.lower()
                content = page.content().lower()
                browser.close()

                # Se redirecionou para accounts/login ou tiver tela de boas-vindas com 'entrar' sem feed
                if "accounts/login" in url_final or ("cadastre-se" in content and "entrar" in content and "feed" not in content):
                    log_event(f"Conta @{conta.get('user')} EXPIRADA ou INVÁLIDA.", "ERRO")
                    return False
                log_event(f"Conta @{conta.get('user')} autenticada com SUCESSO!", "SUCESSO")
                return True
        except Exception as e:
            log_event(f"Erro ao testar conta @{conta.get('user')}: {e}", "ERRO")
            return False

    valido = _test()
    return jsonify({"sucesso": True, "autenticado": valido})

# API: Alvos
@app.route("/api/alvos", methods=["GET", "POST"])
def api_alvos():
    if request.method == "GET":
        return jsonify(carregar_alvos())

    data = request.json or {}
    usernames = data.get("usernames", [])
    if isinstance(usernames, str):
        usernames = [u.strip() for u in usernames.replace("\r", "").split("\n") if u.strip()]

    limpos = [u.replace("@", "").strip() for u in usernames if u.replace("@", "").strip() and not u.strip().startswith("#")]
    if not limpos:
        return jsonify({"sucesso": False, "erro": "Nenhum alvo válido informado"}), 400

    conta_ativa = obter_conta_ativa()
    if not conta_ativa or not conta_ativa.get("sessionid"):
        return jsonify({"sucesso": False, "erro": "Nenhuma conta ativa no Pool para enviar solicitação!"}), 400

    def _job_enviar_solicitacoes():
        log_event(f"Iniciando envio de solicitação para {len(limpos)} alvo(s) usando @{conta_ativa.get('user')}...", "INFO")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                for u in limpos:
                    ctx = criar_contexto_desktop(browser, conta_ativa)
                    page = ctx.new_page()
                    try:
                        info = obter_info_perfil(page, u)
                        st = info["button_status"]
                        if st == "SEGUINDO":
                            log_event(f"Conta @{conta_ativa.get('user')} JÁ SEGUE @{u}! Feed liberado.", "SUCESSO")
                            registrar_novo_alvo(u, is_private=info["is_private"], conta_usada=conta_ativa.get("user"))
                        elif st == "SOLICITADO":
                            log_event(f"Solicitação para @{u} já estava pendente de aprovação.", "AVISO")
                            registrar_novo_alvo(u, is_private=info["is_private"], conta_usada=conta_ativa.get("user"))
                        else:
                            clicked = False
                            for btn in page.query_selector_all("header button, main header button, button"):
                                txt = (btn.inner_text() or "").strip().lower()
                                if txt in ["follow", "seguir"]:
                                    btn.click()
                                    clicked = True
                                    break
                            page.wait_for_timeout(3000)
                            if clicked:
                                log_event(f"✔ Solicitação enviada com sucesso para @{u} usando @{conta_ativa.get('user')}!", "SUCESSO")
                                registrar_novo_alvo(u, is_private=info["is_private"], conta_usada=conta_ativa.get("user"))
                            else:
                                log_event(f"[-] Botão de seguir não encontrado no perfil @{u}.", "ERRO")
                    except Exception as err:
                        log_event(f"Erro ao abordar @{u}: {err}", "ERRO")
                    finally:
                        ctx.close()
                browser.close()
            log_event("Processamento da lista de alvos finalizado.", "SUCESSO")
        except Exception as e:
            log_event(f"Erro no envio de solicitações: {e}", "ERRO")

    threading.Thread(target=_job_enviar_solicitacoes, daemon=True).start()
    return jsonify({"sucesso": True, "total_adicionados": len(limpos), "mensagem": f"Enviando solicitações para {len(limpos)} alvo(s) em segundo plano!"})

@app.route("/api/alvos/<username>", methods=["DELETE"])
def api_remover_alvo(username):
    alvos = carregar_alvos()
    novos = [a for a in alvos if a.get("username", "").lower() != username.lower()]
    salvar_alvos(novos)
    log_event(f"Alvo @{username} removido da lista de monitoramento.", "AVISO")
    return jsonify({"sucesso": True})

@app.route("/api/alvos/limpar_todos", methods=["POST"])
def api_limpar_todos_alvos():
    salvar_alvos([])
    log_event("Todos os alvos monitorados foram excluídos com sucesso.", "AVISO")
    return jsonify({"sucesso": True})

@app.route("/api/alvos/remover_selecionados", methods=["POST"])
def api_remover_alvos_selecionados():
    data = request.json or {}
    selecionados = [u.lower().strip().replace("@", "") for u in data.get("usernames", [])]
    alvos = carregar_alvos()
    novos = [a for a in alvos if a.get("username", "").lower() not in selecionados]
    salvar_alvos(novos)
    log_event(f"{len(selecionados)} alvo(s) selecionado(s) removido(s) do monitoramento.", "AVISO")
    return jsonify({"sucesso": True, "total_removidos": len(selecionados)})

# API: Ações de Execução
@app.route("/api/acoes/baixar_direto", methods=["POST"])
def api_baixar_direto():
    data = request.json or {}
    target = data.get("username", "").replace("@", "").strip()
    if not target:
        return jsonify({"sucesso": False, "erro": "Username obrigatório"}), 400

    def _job():
        log_event(f"Iniciando extração do perfil @{target}...", "INFO")
        conta_ativa = obter_conta_ativa()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = criar_contexto_desktop(browser, conta_ativa)
                page = ctx.new_page()
                info = obter_info_perfil(page, target)
                if info["is_private"] and info["button_status"] != "SEGUINDO":
                    log_event(f"Alvo @{target} é privado e @{conta_ativa.get('user')} não foi aceito.", "AVISO")
                else:
                    extrair_e_baixar_fotos(page, target, max_scrolls=6)
                    log_event(f"Extração de @{target} finalizada com sucesso!", "SUCESSO")
                browser.close()
        except Exception as err:
            log_event(f"Erro ao baixar perfil @{target}: {err}", "ERRO")

    threading.Thread(target=_job, daemon=True).start()
    return jsonify({"sucesso": True, "mensagem": f"Download de @{target} iniciado em segundo plano."})

@app.route("/api/acoes/verificar_cascata", methods=["POST"])
def api_verificar_cascata():
    def _job():
        log_event("Iniciando varredura e cascata de solicitações...", "INFO")
        try:
            fluxo_verificar_e_baixar()
            log_event("Varredura de solicitações concluída.", "SUCESSO")
        except Exception as e:
            log_event(f"Erro na verificação de solicitações: {e}", "ERRO")

    threading.Thread(target=_job, daemon=True).start()
    return jsonify({"sucesso": True, "mensagem": "Varredura iniciada em segundo plano."})

# API: Modo Sentinela
@app.route("/api/acoes/sentinela/toggle", methods=["POST"])
def api_sentinela_toggle():
    global sentinela_ativo, sentinela_thread
    data = request.json or {}
    intervalo_min = int(data.get("intervalo", 30))

    if sentinela_ativo:
        sentinela_ativo = False
        log_event("Modo Sentinela 24/7 INTERROMPIDO.", "AVISO")
        return jsonify({"sucesso": True, "ativo": False})

    sentinela_ativo = True
    def _loop():
        log_event(f"Modo Sentinela 24/7 INICIADO (Ciclos a cada {intervalo_min} min).", "SUCESSO")
        while sentinela_ativo:
            try:
                log_event("[Sentinela] Executando ciclo de verificação...")
                fluxo_verificar_e_baixar()
            except Exception as e:
                log_event(f"[Sentinela] Erro no ciclo: {e}", "ERRO")
            
            # Aguarda com checagens frequentes para interromper rápido se o usuário desativar
            for _ in range(intervalo_min * 60):
                if not sentinela_ativo:
                    break
                time.sleep(1)

    sentinela_thread = threading.Thread(target=_loop, daemon=True)
    sentinela_thread.start()
    return jsonify({"sucesso": True, "ativo": True})

# API: Mídias e Perfis Baixados
@app.route("/api/downloads", methods=["GET"])
def api_listar_downloads():
    base_dir = "downloads"
    if not os.path.exists(base_dir):
        return jsonify([])

    perfis = []
    for item in os.listdir(base_dir):
        perfil_path = os.path.join(base_dir, item)
        if os.path.isdir(perfil_path):
            json_file = os.path.join(perfil_path, "dados_perfil.json")
            info = {}
            if os.path.exists(json_file):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        info = json.load(f)
                except Exception:
                    pass

            perfis.append({
                "pasta": item,
                "username": item.replace("@", ""),
                "dados": info,
                "total_arquivos": len(os.listdir(perfil_path))
            })
    return jsonify(perfis)

# Servir arquivos de mídia da pasta downloads
@app.route("/midia/<path:filepath>")
def servir_midia(filepath):
    return send_from_directory("downloads", filepath)

# Excluir mídia extraída de um perfil
@app.route("/api/downloads/<username>", methods=["DELETE"])
def api_remover_download(username):
    import shutil
    clean_user = username.replace("@", "").strip()
    pasta_alvo = os.path.join("downloads", f"@{clean_user}")
    if not os.path.exists(pasta_alvo):
        pasta_alvo = os.path.join("downloads", clean_user)

    if os.path.exists(pasta_alvo):
        try:
            shutil.rmtree(pasta_alvo)
            log_event(f"Pasta de mídias de @{clean_user} excluída do disco.", "AVISO")
            return jsonify({"sucesso": True})
        except Exception as e:
            return jsonify({"sucesso": False, "erro": str(e)}), 500
    return jsonify({"sucesso": False, "erro": "Pasta não encontrada"}), 404

# Excluir todas as mídias da pasta downloads/
@app.route("/api/downloads/limpar_todas", methods=["POST"])
def api_limpar_todas_midias():
    import shutil
    base_dir = "downloads"
    removidos = 0
    if os.path.exists(base_dir):
        for item in os.listdir(base_dir):
            item_path = os.path.join(base_dir, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    removidos += 1
                else:
                    os.remove(item_path)
                    removidos += 1
            except Exception:
                pass
    log_event(f"Todas as mídias extraídas ({removidos} pastas/arquivos) foram excluídas.", "AVISO")
    return jsonify({"sucesso": True, "total_removidos": removidos})

# Download de pacote completo em ZIP de um perfil
@app.route("/api/downloads/<username>/zip", methods=["GET"])
def baixar_zip_perfil(username):
    import zipfile
    import io
    from flask import send_file

    clean_user = username.replace("@", "").strip()
    pasta_alvo = os.path.join("downloads", f"@{clean_user}")
    if not os.path.exists(pasta_alvo):
        pasta_alvo = os.path.join("downloads", clean_user)

    if not os.path.exists(pasta_alvo):
        return jsonify({"sucesso": False, "erro": "Pasta do perfil não encontrada"}), 404

    # Cria o arquivo ZIP em memória
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(pasta_alvo):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, pasta_alvo)
                zipf.write(full_path, arcname=os.path.join(f"@{clean_user}", rel_path))

    memory_file.seek(0)
    log_event(f"Pacote ZIP gerado para download: @{clean_user}.zip", "SUCESSO")
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"@{clean_user}_extracao_completa.zip"
    )

# API: Logs
@app.route("/api/logs", methods=["GET"])
def api_logs():
    with LOG_LOCK:
        return jsonify(LOG_MESSAGES)

@app.route("/api/logs/limpar", methods=["POST"])
def api_limpar_logs():
    with LOG_LOCK:
        LOG_MESSAGES.clear()
    log_event("Logs limpos pelo usuário.", "INFO")
    return jsonify({"sucesso": True})

if __name__ == "__main__":
    inicializar_banco()
    log_event("Painel Web SharlokInsta iniciado em http://localhost:5000", "SUCESSO")
    app.run(host="127.0.0.1", port=5000, debug=False)
