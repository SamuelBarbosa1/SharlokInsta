import os
import sys
import json
import random
import threading
import time
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory

from core.database import (
    inicializar_banco,
    salvar_log_db,
    carregar_logs_db,
    limpar_logs_db
)
from core.pool import (
    carregar_pool_contas,
    salvar_pool_contas,
    obter_conta_ativa,
    obter_conta_por_user,
    listar_contas_ativas,
    conta_esta_ativa
)
from core.targets import (
    carregar_alvos,
    salvar_alvos,
    registrar_novo_alvo,
    carregar_alvos_do_arquivo
)
from core.cases import (
    carregar_casos,
    criar_caso,
    atualizar_caso,
    remover_caso,
    vincular_alvo_ao_caso,
    obter_mapa_alvo_caso,
    obter_caso_por_id,
    desvincular_alvos_excluidos,
    atualizar_status_automatico_casos
)
from core.config import (
    CONTAS_POOL_FILE,
    ALVOS_TXT_FILE,
    DB_NAME,
    EXIBIR_ABA_ATUALIZACOES,
    obter_parametros_automacao,
    salvar_parametros_automacao
)

from scraper.browser import criar_contexto_desktop
from scraper.profile import obter_info_perfil
from scraper.extractor import extrair_e_baixar_fotos
from scraper.go_runner import is_go_engine_disponivel, extrair_perfil_via_go
from flows.monitor import fluxo_verificar_e_baixar
from playwright.sync_api import sync_playwright

# Força UTF-8 no console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Silencia logs de polling HTTP do Werkzeug para manter o terminal limpo
logging.getLogger("werkzeug").setLevel(logging.ERROR)

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Buffer circular de logs em memória sincronizado com SQLite
inicializar_banco()
LOG_MESSAGES = carregar_logs_db(300)
LOG_LOCK = threading.Lock()
MAX_LOGS = 400

sentinela_thread = None
sentinela_ativo = False
sentinela_intervalo = 30
tarefa_atual = None  # Ex: "Extraindo @perfil...", "Enviando solicitações (1/5)..."

ORIG_STDOUT = sys.__stdout__ or sys.stdout


def _append_log_internal(mensagem: str, nivel: str = "INFO", print_console: bool = True):
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
    salvar_log_db(timestamp, nivel, mensagem)

    if print_console and ORIG_STDOUT:
        try:
            ORIG_STDOUT.write(f"[{timestamp}] [{nivel}] {mensagem}\n")
            ORIG_STDOUT.flush()
        except Exception:
            pass


class StdoutInterceptor:
    """Captura todos os prints do scraper (extractor, monitor, profile) e transmite para o painel Web."""
    def __init__(self, orig_stdout):
        self._stdout = orig_stdout
        self._buffer = ""

    def write(self, text):
        if self._stdout:
            try:
                self._stdout.write(text)
            except UnicodeEncodeError:
                enc = getattr(self._stdout, "encoding", "utf-8") or "utf-8"
                self._stdout.write(text.encode(enc, errors="replace").decode(enc, errors="replace"))
            except Exception:
                pass

        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._process_line(line)

    def _process_line(self, line: str):
        clean = line.strip()
        if not clean:
            return
        if set(clean) <= {"=", "-", "*"} and len(clean) >= 10:
            return
        if "127.0.0.1 - -" in clean or "HTTP/1.1" in clean or "Serving Flask app" in clean or "Running on http://" in clean:
            return

        nivel = "INFO"
        up = clean.upper()
        if any(k in clean for k in ["[+]", "[✔]", "[>]"]) or "SUCESSO" in up or "FINALIZADA" in up:
            nivel = "SUCESSO"
        elif any(k in clean for k in ["[-]", "[ERRO]"]) or "ERRO" in up or "FALHA" in up or "TRACEBACK" in up:
            nivel = "ERRO"
        elif any(k in clean for k in ["[!]", "[AGUARDANDO]", "[VACUO]", "[RECUSA]", "[COOLDOWN]", "[⏳]"]) or "RESTRITO" in up or "PRIVACIDADE" in up:
            nivel = "AVISO"

        _append_log_internal(clean, nivel, print_console=False)

    def flush(self):
        if self._stdout:
            try:
                self._stdout.flush()
            except Exception:
                pass


# Instala o interceptador de logs no stdout se ainda não estiver instalado
if not isinstance(sys.stdout, StdoutInterceptor):
    sys.stdout = StdoutInterceptor(ORIG_STDOUT)


def log_event(mensagem: str, nivel: str = "INFO"):
    """Registra uma mensagem com timestamp para exibição no frontend e persistência SQLite."""
    _append_log_internal(mensagem, nivel, print_console=True)


def set_tarefa_atual(texto):
    global tarefa_atual
    tarefa_atual = texto


# Rota principal
@app.route("/")
def index():
    return render_template("index.html", exibir_atualizacoes=EXIBIR_ABA_ATUALIZACOES)


# API: Status e Estatísticas Rápidas
@app.route("/api/stats", methods=["GET"])
def api_stats():
    contas = carregar_pool_contas()
    contas_ativas = [c for c in contas if conta_esta_ativa(c)]
    alvos = carregar_alvos()
    casos = carregar_casos()
    casos_ativos = [c for c in casos if c.get("status", "EM_ANDAMENTO") == "EM_ANDAMENTO"]

    concluidos = len([a for a in alvos if a.get("status") == "CONCLUIDO"])
    pendentes = len([a for a in alvos if a.get("status") not in ["CONCLUIDO", "ESGOTADO"]])

    downloads_dir = "downloads"
    perfis_baixados = 0
    if os.path.exists(downloads_dir):
        perfis_baixados = len([d for d in os.listdir(downloads_dir) if os.path.isdir(os.path.join(downloads_dir, d))])

    db_existe = os.path.exists(DB_NAME)
    db_tamanho_kb = round(os.path.getsize(DB_NAME) / 1024, 1) if db_existe else 0

    return jsonify({
        "total_contas": len(contas),
        "contas_ativas": len(contas_ativas),
        "total_casos": len(casos),
        "casos_ativos": len(casos_ativos),
        "total_alvos": len(alvos),
        "alvos_concluidos": concluidos,
        "alvos_pendentes": pendentes,
        "perfis_baixados": perfis_baixados,
        "sentinela_ativo": sentinela_ativo,
        "sentinela_intervalo": sentinela_intervalo,
        "tarefa_atual": tarefa_atual,
        "db_ativo": db_existe,
        "db_tamanho_kb": db_tamanho_kb,
        "go_engine_disponivel": is_go_engine_disponivel()
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
    log_event(f"Conta @{nova_conta['user']} adicionada ao pool e salva no banco.", "SUCESSO")
    return jsonify({"sucesso": True, "conta": nova_conta})


@app.route("/api/contas/<int:conta_id>/toggle", methods=["POST"])
def api_conta_toggle(conta_id):
    contas = carregar_pool_contas()
    for c in contas:
        if c.get("id") == conta_id:
            ativo_atual = conta_esta_ativa(c)
            c["ativo"] = "Não" if ativo_atual else "Sim"
            salvar_pool_contas(contas)
            log_event(f"Conta @{c.get('user')} agora está {'ATIVA' if c['ativo'] == 'Sim' else 'INATIVA'}.")
            return jsonify({"sucesso": True, "novo_status": c["ativo"]})
    return jsonify({"sucesso": False, "erro": "Conta não encontrada"}), 404


@app.route("/api/contas/<int:conta_id>", methods=["DELETE", "PUT"])
def api_conta_gerenciar(conta_id):
    contas = carregar_pool_contas()
    if request.method == "DELETE":
        novas = [c for c in contas if c.get("id") != conta_id]
        salvar_pool_contas(novas)
        log_event(f"Conta ID #{conta_id} removida do pool.", "AVISO")
        return jsonify({"sucesso": True})

    data = request.json or {}
    for c in contas:
        if c.get("id") == conta_id:
            if "user" in data and data["user"].strip():
                c["user"] = data["user"].strip().replace("@", "")
            if "sessionid" in data and data["sessionid"].strip():
                sessionid = data["sessionid"].strip()
                c["sessionid"] = sessionid
                ds_user_id = data.get("ds_user_id", "").strip()
                if not ds_user_id and ("%3A" in sessionid or ":" in sessionid):
                    uid = sessionid.split("%3A")[0].split(":")[0]
                    if uid.isdigit():
                        ds_user_id = uid
                if ds_user_id:
                    c["ds_user_id"] = ds_user_id
            salvar_pool_contas(contas)
            log_event(f"Credenciais/SessionID da conta @{c.get('user')} atualizados!", "SUCESSO")
            return jsonify({"sucesso": True, "conta": c})

    return jsonify({"sucesso": False, "erro": "Conta não encontrada"}), 404


@app.route("/api/contas/<int:conta_id>/testar", methods=["POST"])
def api_conta_testar(conta_id):
    contas = carregar_pool_contas()
    conta = next((c for c in contas if c.get("id") == conta_id), None)
    if not conta:
        return jsonify({"sucesso": False, "erro": "Conta não encontrada"}), 404

    def _test():
        set_tarefa_atual(f"Testando login de @{conta.get('user')}...")
        log_event(f"Testando autenticação de @{conta.get('user')} no Instagram Desktop...")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = criar_contexto_desktop(browser, conta)
                page = ctx.new_page()
                page.goto("https://www.instagram.com/accounts/edit/", timeout=25000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                url_atual = page.url
                browser.close()
                if "accounts/login" in url_atual:
                    log_event(f"[-] Sessão EXPIRADA ou inválida para @{conta.get('user')}! Conta marcada como INATIVA.", "ERRO")
                    conta["ultimo_teste"] = "EXPIRADA"
                    conta["ativo"] = "Não"
                    salvar_pool_contas(contas)
                    return False
                else:
                    log_event(f"[+] Sessão VÁLIDA e autenticada para @{conta.get('user')}!", "SUCESSO")
                    conta["ultimo_teste"] = "CONECTADA"
                    salvar_pool_contas(contas)
                    return True
        except Exception as e:
            log_event(f"[-] Erro ao testar @{conta.get('user')}: {e}", "ERRO")
            return False
        finally:
            set_tarefa_atual(None)

    valido = _test()
    return jsonify({"sucesso": True, "autenticado": valido})


@app.route("/api/contas/testar_todas", methods=["POST"])
def api_contas_testar_todas():
    contas = carregar_pool_contas()
    if not contas:
        return jsonify({"sucesso": False, "erro": "Nenhuma conta cadastrada no Pool."}), 400

    def _job_testar_pool():
        set_tarefa_atual(f"Testando todas as {len(contas)} conta(s) do Pool...")
        log_event(f"Iniciando verificação de login em lote para {len(contas)} conta(s) do Pool...", "INFO")
        conectadas = 0
        expiradas = 0
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                for idx, c in enumerate(contas, 1):
                    uname = c.get("user", f"id_{c.get('id')}")
                    set_tarefa_atual(f"Testando @{uname} ({idx}/{len(contas)})...")
                    log_event(f"[{idx}/{len(contas)}] Verificando sessão de @{uname}...", "INFO")
                    if not c.get("sessionid"):
                        c["ultimo_teste"] = "SEM_SESSION"
                        c["ativo"] = "Não"
                        expiradas += 1
                        log_event(f"[-] Conta @{uname} está sem SessionID (pausada).", "AVISO")
                        continue
                    ctx = criar_contexto_desktop(browser, c)
                    page = ctx.new_page()
                    try:
                        page.goto("https://www.instagram.com/accounts/edit/", timeout=25000, wait_until="domcontentloaded")
                        page.wait_for_timeout(2800)
                        if "accounts/login" in page.url:
                            c["ultimo_teste"] = "EXPIRADA"
                            c["ativo"] = "Não"
                            expiradas += 1
                            log_event(f"[-] Sessão EXPIRADA para @{uname}! Conta pausada automaticamente.", "ERRO")
                        else:
                            c["ultimo_teste"] = "CONECTADA"
                            conectadas += 1
                            log_event(f"[+] Conta @{uname} CONECTADA e pronta para uso!", "SUCESSO")
                    except Exception as err:
                        log_event(f"[-] Falha ao verificar @{uname}: {err}", "ERRO")
                    finally:
                        ctx.close()
                browser.close()
            salvar_pool_contas(contas)
            log_event(f"[+] Teste do Pool finalizado: {conectadas} conectada(s) | {expiradas} expirada(s)/pausada(s).", "SUCESSO")
        except Exception as e:
            log_event(f"[-] Erro geral ao testar Pool: {e}", "ERRO")
        finally:
            set_tarefa_atual(None)

    threading.Thread(target=_job_testar_pool, daemon=True).start()
    return jsonify({
        "sucesso": True,
        "mensagem": f"Testando as {len(contas)} conta(s) em segundo plano! Acompanhe o resultado ao vivo nos Logs."
    })


# API: Configurações Dinâmicas (Tempos de Vácuo, Cooldown, Anti-Bloqueio)
@app.route("/api/configuracoes", methods=["GET", "POST"])
def api_configuracoes():
    if request.method == "GET":
        return jsonify(obter_parametros_automacao())

    data = request.json or {}
    novos = salvar_parametros_automacao(data)
    log_event(
        f"Configurações salvas no banco: Vácuo={novos['timeout_vacuo_minutos']}m | Cooldown={novos['cooldown_minutos']}m | Delay={novos['delay_min_segs']}-{novos['delay_max_segs']}s | Rolagens={novos['max_scrolls_padrao']}.",
        "SUCESSO"
    )
    return jsonify({"sucesso": True, "parametros": novos})


# API: Ler / Importar alvos.txt
@app.route("/api/alvos/arquivo_txt", methods=["GET"])
def api_ler_alvos_txt():
    alvos = carregar_alvos_do_arquivo(ALVOS_TXT_FILE)
    return jsonify({"sucesso": True, "alvos": alvos})


def _disparar_fila_alvos_background(limpos: list, modo: str = "distribuido", conta_especifica_user: str = "", caso_id=None):
    """Monta a distribuição de bots e inicia o envio assíncrono de solicitações vinculando ao Caso opcional."""
    contas_ativas = listar_contas_ativas()
    if not contas_ativas:
        return False, "Nenhuma conta ativa no Pool! Adicione ou ative uma conta primeiro.", 0

    distribuicao = []
    if modo == "especifico" and conta_especifica_user:
        conta_escolhida = obter_conta_por_user(conta_especifica_user)
        if not conta_escolhida or not conta_escolhida.get("sessionid"):
            return False, f"Conta @{conta_especifica_user} não encontrada ou sem SessionID.", 0
        for u in limpos:
            distribuicao.append((u, conta_escolhida))
        desc_modo = f"Direcionado via @{conta_escolhida.get('user')}"
    elif modo == "aleatorio":
        for u in limpos:
            distribuicao.append((u, random.choice(contas_ativas)))
        desc_modo = f"Sorteio Aleatório entre {len(contas_ativas)} conta(s) ativa(s)"
    else:
        for idx, u in enumerate(limpos):
            conta_rr = contas_ativas[idx % len(contas_ativas)]
            distribuicao.append((u, conta_rr))
        desc_modo = f"Distribuição Round-Robin entre {len(contas_ativas)} conta(s) ativa(s)"

    if caso_id:
        for u in limpos:
            vincular_alvo_ao_caso(u, caso_id)

    caso_obj = obter_caso_por_id(caso_id) if caso_id else None
    sufixo_caso = f" [Caso: {caso_obj['nome']}]" if caso_obj else ""

    def _job_enviar_solicitacoes():
        set_tarefa_atual(f"Enviando solicitações (0/{len(distribuicao)})...")
        log_event(f"Iniciando disparo para {len(distribuicao)} alvo(s){sufixo_caso} | Modo: {desc_modo}", "INFO")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                for idx, (u, conta_bot) in enumerate(distribuicao, 1):
                    bot_user = conta_bot.get("user", "bot")
                    set_tarefa_atual(f"Abordando @{u} com @{bot_user} ({idx}/{len(distribuicao)})...")
                    log_event(f"[{idx}/{len(distribuicao)}] Abordando @{u} usando a conta @{bot_user}{sufixo_caso}...", "INFO")

                    ctx = criar_contexto_desktop(browser, conta_bot)
                    page = ctx.new_page()
                    try:
                        info = obter_info_perfil(page, u)
                        st = info["button_status"]
                        priv_str = "PRIVADO" if info["is_private"] else "PÚBLICO"
                        log_event(f"Perfil @{u} verificado ({priv_str} | Status botão: {st}).", "INFO")

                        if st == "SEGUINDO":
                            log_event(f"[+] Conta @{bot_user} JÁ SEGUE @{u}! Registrando e iniciando extração...", "SUCESSO")
                            registrar_novo_alvo(u, is_private=info["is_private"], conta_usada=bot_user, status_inicial="SEGUINDO", caso_id=caso_id)
                        elif st == "SOLICITADO":
                            log_event(f"[!] Solicitação de @{bot_user} para @{u} já estava pendente no Instagram.", "AVISO")
                            registrar_novo_alvo(u, is_private=info["is_private"], conta_usada=bot_user, caso_id=caso_id)
                        else:
                            clicked = False
                            for btn in page.query_selector_all("header button, main header button, button"):
                                txt = (btn.inner_text() or "").strip().lower()
                                if txt in ["follow", "seguir", "follow back", "seguir de volta"]:
                                    btn.click()
                                    clicked = True
                                    break
                            page.wait_for_timeout(3500)
                            if clicked:
                                log_event(f"[+] Solicitação de seguir enviada com sucesso para @{u} via @{bot_user}!", "SUCESSO")
                                registrar_novo_alvo(u, is_private=info["is_private"], conta_usada=bot_user, caso_id=caso_id)
                            else:
                                log_event(f"[-] Botão de seguir não encontrado no perfil @{u}.", "ERRO")
                    except Exception as err:
                        log_event(f"[-] Erro ao abordar @{u} com @{bot_user}: {err}", "ERRO")
                    finally:
                        ctx.close()

                    if idx < len(distribuicao):
                        params_atuais = obter_parametros_automacao()
                        espera = random.randint(params_atuais["delay_min_segs"], params_atuais["delay_max_segs"])
                        log_event(f"[*] Proteção anti-spam: aguardando {espera}s antes do próximo alvo...", "INFO")
                        time.sleep(espera)

                browser.close()
            log_event(f"[+] Fila de solicitações concluída ({len(distribuicao)} alvo(s) processado(s)){sufixo_caso}.", "SUCESSO")
        except Exception as e:
            log_event(f"[-] Erro no envio de solicitações: {e}", "ERRO")
        finally:
            set_tarefa_atual(None)

    threading.Thread(target=_job_enviar_solicitacoes, daemon=True).start()
    return True, f"Disparando {len(distribuicao)} solicitação(ões) em segundo plano ({desc_modo}){sufixo_caso}!", len(distribuicao)


# API: Casos / Perfis de Investigação (Dossiês)
@app.route("/api/casos", methods=["GET", "POST"])
def api_casos():
    if request.method == "GET":
        casos = atualizar_status_automatico_casos()
        alvos_mon = {a.get("username", "").lower(): a for a in carregar_alvos()}
        pastas_dl = set()
        if os.path.exists("downloads"):
            for item in os.listdir("downloads"):
                if os.path.isdir(os.path.join("downloads", item)):
                    pastas_dl.add(item.replace("@", "").lower())

        enriquecidos = []
        for c in casos:
            lista_u = c.get("alvos", [])
            detalhes_alvos = []
            concluidos = 0
            pendentes = 0
            baixados = 0
            for u in lista_u:
                u_low = str(u).lower()
                reg = alvos_mon.get(u_low, {})
                tem_pasta = u_low in pastas_dl
                st = reg.get("status") or ("CONCLUIDO" if tem_pasta else "VINCULADO")
                if st == "CONCLUIDO" or tem_pasta:
                    concluidos += 1
                else:
                    pendentes += 1
                if tem_pasta:
                    baixados += 1
                detalhes_alvos.append({
                    "username": reg.get("username", u),
                    "conta_atual": reg.get("conta_atual", ""),
                    "status": st,
                    "baixado": tem_pasta,
                    "atualizado_em": reg.get("atualizado_em", "")
                })
            copia = dict(c)
            copia["alvos_detalhes"] = detalhes_alvos
            copia["resumo"] = {
                "total_alvos": len(lista_u),
                "concluidos": concluidos,
                "pendentes": pendentes,
                "baixados": baixados
            }
            enriquecidos.append(copia)
        return jsonify(enriquecidos)

    data = request.json or {}
    nome = str(data.get("nome", "")).strip()
    if not nome:
        return jsonify({"sucesso": False, "erro": "Informe o nome do Caso / Investigação."}), 400

    referencia = str(data.get("referencia", "")).strip()
    descricao = str(data.get("descricao", "")).strip()
    raw_alvos = data.get("alvos", "")
    disparar_agora = bool(data.get("disparar_agora", False))
    modo = data.get("modo", "distribuido")
    conta_user = str(data.get("conta_user", "")).strip()

    if isinstance(raw_alvos, str):
        lista_alvos = [x.replace("@", "").strip() for x in raw_alvos.replace("\r", "").split("\n") if x.strip() and not x.strip().startswith("#")]
    elif isinstance(raw_alvos, list):
        lista_alvos = [str(x).replace("@", "").strip() for x in raw_alvos if str(x).strip()]
    else:
        lista_alvos = []

    novo_caso = criar_caso(nome=nome, referencia=referencia, descricao=descricao, alvos_iniciais=lista_alvos)
    log_event(f"Novo Caso de Investigação criado: #{novo_caso['id']} '{novo_caso['nome']}' ({len(lista_alvos)} conta(s) vinculada(s)).", "SUCESSO")

    msg_disparo = ""
    if lista_alvos and disparar_agora:
        ok, msg_d, _ = _disparar_fila_alvos_background(lista_alvos, modo=modo, conta_especifica_user=conta_user, caso_id=novo_caso["id"])
        msg_disparo = f" | {msg_d}" if ok else f" | Aviso no disparo: {msg_d}"

    return jsonify({
        "sucesso": True,
        "caso": novo_caso,
        "mensagem": f"Caso '{novo_caso['nome']}' criado com sucesso!{msg_disparo}"
    })


@app.route("/api/casos/<int:caso_id>", methods=["PUT", "DELETE"])
def api_caso_item(caso_id):
    if request.method == "DELETE":
        ok = remover_caso(caso_id)
        if not ok:
            return jsonify({"sucesso": False, "erro": "Caso não encontrado."}), 404
        log_event(f"Caso de Investigação #{caso_id} excluído (alvos e mídias mantidos no sistema).", "AVISO")
        return jsonify({"sucesso": True})

    data = request.json or {}
    atualizado = atualizar_caso(caso_id, data)
    if not atualizado:
        return jsonify({"sucesso": False, "erro": "Caso não encontrado."}), 404
    log_event(f"Caso #{caso_id} ('{atualizado['nome']}') atualizado.", "INFO")
    return jsonify({"sucesso": True, "caso": atualizado})


@app.route("/api/casos/<int:caso_id>/toggle_status", methods=["POST"])
def api_toggle_status_caso(caso_id):
    caso = obter_caso_por_id(caso_id)
    if not caso:
        return jsonify({"sucesso": False, "erro": "Caso não encontrado."}), 404
    novo_status = "CONCLUIDO" if caso.get("status") == "EM_ANDAMENTO" else "EM_ANDAMENTO"
    atualizado = atualizar_caso(caso_id, {"status": novo_status})
    log_event(f"Status do Caso #{caso_id} ('{caso.get('nome')}') alterado para {novo_status}.", "INFO")
    return jsonify({"sucesso": True, "caso": atualizado, "novo_status": novo_status})


@app.route("/api/casos/vincular", methods=["POST"])
def api_vincular_alvo_caso():
    data = request.json or {}
    username = str(data.get("username", "")).replace("@", "").strip()
    caso_id = data.get("caso_id")
    if not username:
        return jsonify({"sucesso": False, "erro": "Username obrigatório."}), 400

    vincular_alvo_ao_caso(username, caso_id)
    if caso_id and str(caso_id).isdigit() and int(caso_id) > 0:
        c_obj = obter_caso_por_id(caso_id)
        nome_c = c_obj["nome"] if c_obj else f"#{caso_id}"
        log_event(f"Investigado @{username} vinculado ao Caso '{nome_c}'.", "SUCESSO")
    else:
        log_event(f"Investigado @{username} desvinculado de caso específico.", "INFO")
    return jsonify({"sucesso": True})


@app.route("/api/casos/<int:caso_id>/zip", methods=["GET"])
def baixar_zip_caso(caso_id):
    import zipfile
    import io
    from flask import send_file

    caso = obter_caso_por_id(caso_id)
    if not caso:
        return jsonify({"sucesso": False, "erro": "Caso não encontrado."}), 404

    memory_file = io.BytesIO()
    arquivos_adicionados = 0
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zipf:
        resumo_linhas = [
            f"DOSSIE DE INVESTIGACAO - SHARLOKINSTA",
            f"====================================================",
            f"ID do Caso   : #{caso.get('id')}",
            f"Nome do Caso : {caso.get('nome')}",
            f"Referencia   : {caso.get('referencia') or '-'}",
            f"Status       : {caso.get('status')}",
            f"Criado em    : {caso.get('criado_em')}",
            f"Observacoes  : {caso.get('descricao') or '-'}",
            f"",
            f"Contas Investigadas Vinculadas ({len(caso.get('alvos', []))}):",
        ]
        for u in caso.get("alvos", []):
            resumo_linhas.append(f" - @{u}")
            pasta_alvo = os.path.join("downloads", f"@{u}")
            if not os.path.exists(pasta_alvo):
                pasta_alvo = os.path.join("downloads", u)
            if os.path.exists(pasta_alvo):
                for root, _dirs, files in os.walk(pasta_alvo):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, pasta_alvo)
                        zipf.write(full_path, arcname=os.path.join(f"@{u}", rel_path))
                        arquivos_adicionados += 1

        zipf.writestr("DOSSIE_DO_CASO.txt", "\n".join(resumo_linhas))

    memory_file.seek(0)
    nome_seguro = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in caso.get("nome", f"caso_{caso_id}")).strip("_")
    log_event(f"Dossiê ZIP exportado para o Caso '{caso.get('nome')}' ({arquivos_adicionados} arquivo(s) de mídia).", "SUCESSO")
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"Dossie_{nome_seguro}.zip"
    )


# API: Alvos (Suporta Modo Distribuído Round-Robin, Aleatório ou Conta Específica + Vínculo a Caso)
@app.route("/api/alvos", methods=["GET", "POST"])
def api_alvos():
    if request.method == "GET":
        alvos = carregar_alvos()
        mapa_casos = obter_mapa_alvo_caso()
        for a in alvos:
            u_low = a.get("username", "").lower()
            info_c = mapa_casos.get(u_low)
            if info_c:
                a["caso_id"] = info_c["caso_id"]
                a["caso_nome"] = info_c["caso_nome"]
            else:
                a["caso_id"] = None
                a["caso_nome"] = None
        return jsonify(alvos)

    data = request.json or {}
    usernames = data.get("usernames", [])
    modo = data.get("modo", "distribuido")
    conta_especifica_user = data.get("conta_user", "").strip()
    caso_id = data.get("caso_id")

    if isinstance(usernames, str):
        usernames = [u.strip() for u in usernames.replace("\r", "").split("\n") if u.strip()]

    limpos = []
    for u in usernames:
        clean_u = u.replace("@", "").strip()
        if clean_u and not clean_u.startswith("#") and clean_u.lower() not in [x.lower() for x in limpos]:
            limpos.append(clean_u)

    if not limpos:
        return jsonify({"sucesso": False, "erro": "Nenhum alvo válido informado"}), 400

    ok, msg, total_add = _disparar_fila_alvos_background(limpos, modo=modo, conta_especifica_user=conta_especifica_user, caso_id=caso_id)
    if not ok:
        return jsonify({"sucesso": False, "erro": msg}), 400

    return jsonify({
        "sucesso": True,
        "total_adicionados": total_add,
        "mensagem": msg
    })


@app.route("/api/alvos/<username>", methods=["DELETE"])
def api_remover_alvo(username):
    clean_u = username.lower().replace("@", "").strip()
    alvos = carregar_alvos()
    novos = [a for a in alvos if a.get("username", "").lower() != clean_u]
    salvar_alvos(novos)
    desvincular_alvos_excluidos([clean_u])
    log_event(f"Alvo @{username} removido da lista de monitoramento e de eventuais casos vinculados.", "AVISO")
    return jsonify({"sucesso": True})


@app.route("/api/alvos/limpar_todos", methods=["POST"])
def api_limpar_todos_alvos():
    alvos = carregar_alvos()
    todos_u = [a.get("username", "") for a in alvos]
    salvar_alvos([])
    desvincular_alvos_excluidos(todos_u)
    log_event("Todos os alvos monitorados foram excluídos com sucesso.", "AVISO")
    return jsonify({"sucesso": True})


@app.route("/api/alvos/remover_selecionados", methods=["POST"])
def api_remover_alvos_selecionados():
    data = request.json or {}
    selecionados = [u.lower().strip().replace("@", "") for u in data.get("usernames", [])]
    alvos = carregar_alvos()
    novos = [a for a in alvos if a.get("username", "").lower() not in selecionados]
    salvar_alvos(novos)
    desvincular_alvos_excluidos(selecionados)
    log_event(f"{len(selecionados)} alvo(s) selecionado(s) removido(s) do monitoramento e de seus casos.", "AVISO")
    return jsonify({"sucesso": True, "total_removidos": len(selecionados)})


# API: Ações de Execução
@app.route("/api/acoes/baixar_direto", methods=["POST"])
def api_baixar_direto():
    data = request.json or {}
    target = data.get("username", "").replace("@", "").strip()
    conta_user = data.get("conta_user", "").strip()
    max_scrolls = int(data.get("max_scrolls", 6) or 6)
    caso_id = data.get("caso_id")
    engine = data.get("engine", "go" if is_go_engine_disponivel() else "playwright")

    if not target:
        return jsonify({"sucesso": False, "erro": "Username obrigatório"}), 400

    if caso_id and str(caso_id).isdigit() and int(caso_id) > 0:
        vincular_alvo_ao_caso(target, caso_id)

    # Se o alvo já estiver no monitoramento com uma conta associada e o usuário não especificou outra, usa a conta do alvo
    conta_escolhida = None
    if conta_user:
        conta_escolhida = obter_conta_por_user(conta_user)
    if not conta_escolhida:
        alvos = carregar_alvos()
        alvo_reg = next((a for a in alvos if a.get("username", "").lower() == target.lower()), None)
        if alvo_reg and alvo_reg.get("conta_atual"):
            conta_escolhida = obter_conta_por_user(alvo_reg.get("conta_atual"))
    if not conta_escolhida:
        conta_escolhida = obter_conta_ativa()

    if not conta_escolhida or not conta_escolhida.get("sessionid"):
        return jsonify({"sucesso": False, "erro": "Nenhuma conta ativa configurada no Pool!"}), 400

    def _job():
        bot_nome = conta_escolhida.get("user", "bot")
        session = conta_escolhida.get("sessionid", "")
        ds_uid = conta_escolhida.get("ds_user_id", "")

        if engine == "go" and is_go_engine_disponivel():
            set_tarefa_atual(f"Go Turbo: Extraindo @{target}...")
            log_event(f"Iniciando extração em ALTA VELOCIDADE (Golang REST) para @{target} via @{bot_nome}...", "INFO")
            try:
                qtd = extrair_perfil_via_go(
                    username=target,
                    sessionid=session,
                    ds_user_id=ds_uid,
                    max_feed=max_scrolls * 20,
                    max_followers=0,
                    max_following=0,
                    workers=12
                )
                if qtd > 0:
                    log_event(f"[✔] Extração Golang concluída para @{target} ({qtd} arquivos de mídia e listas completas salvas)!", "SUCESSO")
                else:
                    log_event(f"[!] Engine Go não obteve mídias de @{target}. Acionando fallback automático via Playwright (Navegador)...", "AVISO")
                    _executar_playwright_fallback(target, conta_escolhida, max_scrolls)
            except Exception as e_go:
                log_event(f"[!] Motor Go encontrou restrição REST ({e_go}). Acionando fallback automático via Playwright (Navegador)...", "AVISO")
                _executar_playwright_fallback(target, conta_escolhida, max_scrolls)
            finally:
                atualizar_status_automatico_casos()
                set_tarefa_atual(None)
        else:
            set_tarefa_atual(f"Extraindo @{target} via @{bot_nome}...")
            log_event(f"Iniciando extração completa de @{target} usando a conta @{bot_nome} ({max_scrolls} rolagens)...", "INFO")
            try:
                _executar_playwright_fallback(target, conta_escolhida, max_scrolls)
            finally:
                atualizar_status_automatico_casos()
                set_tarefa_atual(None)

    threading.Thread(target=_job, daemon=True).start()
    engine_nome = "Golang Turbo REST" if (engine == "go" and is_go_engine_disponivel()) else "Playwright Navegador"
    return jsonify({"sucesso": True, "mensagem": f"Extração de @{target} iniciada em segundo plano via motor {engine_nome}!"})


def _executar_playwright_fallback(target, conta_escolhida, max_scrolls):
    bot_nome = conta_escolhida.get("user", "bot")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = criar_contexto_desktop(browser, conta_escolhida)
            page = ctx.new_page()
            info = obter_info_perfil(page, target)
            if info["is_private"] and info["button_status"] != "SEGUINDO":
                log_event(f"[!] Alvo @{target} é privado e @{bot_nome} ainda não foi aceito (Status: {info['button_status']}).", "AVISO")
            else:
                qtd = extrair_e_baixar_fotos(page, target, max_scrolls=max_scrolls)
                alvos_atuais = carregar_alvos()
                alterado = False
                for a in alvos_atuais:
                    if a.get("username", "").lower() == target.lower():
                        a["status"] = "CONCLUIDO"
                        a["qtd_fotos_baixadas"] = qtd
                        a["concluido_em"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        a["atualizado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        alterado = True
                if alterado:
                    salvar_alvos(alvos_atuais)
                    atualizar_status_automatico_casos()
            browser.close()
    except Exception as err:
        log_event(f"[-] Erro ao baixar perfil @{target}: {err}", "ERRO")


@app.route("/api/acoes/verificar_cascata", methods=["POST"])
def api_verificar_cascata():
    def _job():
        set_tarefa_atual("Verificando solicitações e cascata...")
        log_event("Iniciando varredura de solicitações, recusa, vácuo e cascata...", "INFO")
        try:
            fluxo_verificar_e_baixar()
            log_event("Varredura de solicitações concluída.", "SUCESSO")
        except Exception as e:
            log_event(f"Erro na verificação de solicitações: {e}", "ERRO")
        finally:
            set_tarefa_atual(None)

    threading.Thread(target=_job, daemon=True).start()
    return jsonify({"sucesso": True, "mensagem": "Varredura iniciada em segundo plano."})


# API: Modo Sentinela
@app.route("/api/acoes/sentinela/toggle", methods=["POST"])
def api_sentinela_toggle():
    global sentinela_ativo, sentinela_thread, sentinela_intervalo
    data = request.json or {}
    intervalo_min = int(data.get("intervalo", 30) or 30)

    if sentinela_ativo:
        sentinela_ativo = False
        log_event("Modo Sentinela 24/7 INTERROMPIDO pelo usuário.", "AVISO")
        return jsonify({"sucesso": True, "ativo": False})

    sentinela_ativo = True
    sentinela_intervalo = intervalo_min

    def _loop():
        log_event(f"Modo Sentinela 24/7 INICIADO (Ciclos automáticos a cada {intervalo_min} min). Você pode fechar o navegador com segurança!", "SUCESSO")
        while sentinela_ativo:
            try:
                set_tarefa_atual("Sentinela: Verificando alvos...")
                log_event("[Sentinela 24/7] Iniciando ciclo automático de verificação...", "INFO")
                fluxo_verificar_e_baixar()
                log_event(f"[Sentinela 24/7] Ciclo finalizado. Próxima checagem em {intervalo_min} min.", "SUCESSO")
            except Exception as e:
                log_event(f"[Sentinela 24/7] Erro no ciclo: {e}", "ERRO")
            finally:
                set_tarefa_atual(None)

            for _ in range(intervalo_min * 60):
                if not sentinela_ativo:
                    break
                time.sleep(1)

    sentinela_thread = threading.Thread(target=_loop, daemon=True)
    sentinela_thread.start()
    return jsonify({"sucesso": True, "ativo": True, "intervalo": intervalo_min})


# API: Mídias e Perfis Baixados
@app.route("/api/downloads", methods=["GET"])
def api_listar_downloads():
    base_dir = "downloads"
    if not os.path.exists(base_dir):
        return jsonify([])

    mapa_casos = obter_mapa_alvo_caso()
    perfis = []
    for item in sorted(os.listdir(base_dir)):
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

            # Conta todos os arquivos incluindo subpastas (destaques e stories)
            total_arqs = 0
            for _r, _d, files in os.walk(perfil_path):
                total_arqs += len(files)

            uname = item.replace("@", "")
            info_c = mapa_casos.get(uname.lower())
            perfis.append({
                "pasta": item,
                "username": uname,
                "dados": info,
                "total_arquivos": total_arqs,
                "caso_id": info_c["caso_id"] if info_c else None,
                "caso_nome": info_c["caso_nome"] if info_c else None
            })
    return jsonify(perfis)


# Detalhes, galeria de mídias e relatório de um perfil extraído (bio.txt, conexões, fotos, stories)
@app.route("/api/downloads/<username>/detalhes", methods=["GET"])
def api_detalhes_download(username):
    clean_user = username.replace("@", "").strip()
    pasta_nome = f"@{clean_user}"
    pasta_alvo = os.path.join("downloads", pasta_nome)
    if not os.path.exists(pasta_alvo):
        pasta_nome = clean_user
        pasta_alvo = os.path.join("downloads", pasta_nome)

    if not os.path.exists(pasta_alvo):
        return jsonify({"sucesso": False, "erro": "Perfil não encontrado"}), 404

    bio_texto = ""
    bio_path = os.path.join(pasta_alvo, "bio.txt")
    if os.path.exists(bio_path):
        try:
            with open(bio_path, "r", encoding="utf-8") as f:
                bio_texto = f.read()
        except Exception:
            pass

    dados = {}
    json_path = os.path.join(pasta_alvo, "dados_perfil.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                dados = json.load(f)
        except Exception:
            pass

    # Lista as mídias baixadas para pré-visualização na Galeria do navegador
    midias = {
        "avatar": None,
        "feed": [],
        "destaques": [],
        "stories": []
    }
    exts_validas = (".jpg", ".jpeg", ".png", ".webp", ".mp4")

    for arq in sorted(os.listdir(pasta_alvo)):
        full_p = os.path.join(pasta_alvo, arq)
        if os.path.isfile(full_p) and arq.lower().endswith(exts_validas):
            url_m = f"/midia/{pasta_nome}/{arq}"
            if arq.startswith("avatar"):
                midias["avatar"] = url_m
            else:
                midias["feed"].append({"nome": arq, "url": url_m, "video": arq.lower().endswith(".mp4")})

    pasta_dest = os.path.join(pasta_alvo, "destaques")
    if os.path.exists(pasta_dest):
        for arq in sorted(os.listdir(pasta_dest)):
            if arq.lower().endswith(exts_validas):
                midias["destaques"].append({
                    "nome": arq,
                    "url": f"/midia/{pasta_nome}/destaques/{arq}",
                    "video": arq.lower().endswith(".mp4")
                })

    pasta_st = os.path.join(pasta_alvo, "stories")
    if os.path.exists(pasta_st):
        for arq in sorted(os.listdir(pasta_st)):
            if arq.lower().endswith(exts_validas):
                midias["stories"].append({
                    "nome": arq,
                    "url": f"/midia/{pasta_nome}/stories/{arq}",
                    "video": arq.lower().endswith(".mp4")
                })

    return jsonify({
        "sucesso": True,
        "username": clean_user,
        "bio_txt": bio_texto,
        "dados": dados,
        "midias": midias
    })


# Exportação de Conexões (Seguidores, Seguindo e Mútuos) em Planilha CSV (compatível com Excel PT-BR)
@app.route("/api/downloads/<username>/csv", methods=["GET"])
def exportar_conexoes_csv(username):
    import io
    import csv
    from flask import Response

    clean_user = username.replace("@", "").strip()
    pasta_alvo = os.path.join("downloads", f"@{clean_user}")
    if not os.path.exists(pasta_alvo):
        pasta_alvo = os.path.join("downloads", clean_user)

    json_path = os.path.join(pasta_alvo, "dados_perfil.json")
    if not os.path.exists(json_path):
        return jsonify({"sucesso": False, "erro": "Relatório JSON não encontrado para este perfil."}), 404

    with open(json_path, "r", encoding="utf-8") as f:
        dados = json.load(f)

    conex = dados.get("conexoes", {})
    resumo = conex.get("resumo_relacionamento", {})
    mutuos = set(resumo.get("seguem_de_volta_mutuo", []))
    apenas_seg = set(resumo.get("apenas_seguidores", []))
    nao_seguem_volta = set(resumo.get("alvo_segue_mas_nao_seguem_de_volta", []))

    # Fallback caso resumo não esteja preenchido mas as listas brutas estejam
    if not (mutuos or apenas_seg or nao_seguem_volta):
        seg_set = set((conex.get("seguidores") or {}).get("contas", []))
        sgndo_set = set((conex.get("seguindo") or {}).get("contas", []))
        mutuos = seg_set & sgndo_set
        apenas_seg = seg_set - sgndo_set
        nao_seguem_volta = sgndo_set - seg_set

    output = io.StringIO()
    output.write("\ufeff")  # UTF-8 BOM para acentuação perfeita no Microsoft Excel
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Alvo_Analisado", "Username_Conexao", "Tipo_Relacao", "Segue_o_Alvo", "Alvo_Segue", "URL_Perfil"])

    for u in sorted(mutuos):
        writer.writerow([f"@{clean_user}", f"@{u}", "Mutuo (Segue e e Seguido)", "Sim", "Sim", f"https://www.instagram.com/{u}/"])
    for u in sorted(apenas_seg):
        writer.writerow([f"@{clean_user}", f"@{u}", "Apenas Seguidor", "Sim", "Nao", f"https://www.instagram.com/{u}/"])
    for u in sorted(nao_seguem_volta):
        writer.writerow([f"@{clean_user}", f"@{u}", "Alvo Segue (Nao Segue de Volta)", "Nao", "Sim", f"https://www.instagram.com/{u}/"])

    log_event(f"Planilha CSV de conexões exportada para @{clean_user}.", "SUCESSO")
    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=@{clean_user}_conexoes.csv"}
    )


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
    limpar_logs_db()
    log_event("Histórico de logs limpo pelo usuário.", "INFO")
    return jsonify({"sucesso": True})


if __name__ == "__main__":
    inicializar_banco()
    log_event("Painel Web SharlokInsta iniciado em http://localhost:5000 (Banco SQLite ativo)", "SUCESSO")
    app.run(host="127.0.0.1", port=5000, debug=False)
