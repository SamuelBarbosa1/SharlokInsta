let currentTab = 'tab-dashboard';
let currentLogFilter = 'TODOS';
let currentChangelogCategory = 'TODOS';
let currentCasoStatusFilter = 'TODOS';
let currentNotaCatFilter = 'TODAS';
let cachedLogs = [];
let cachedCasos = [];
let cachedAlvos = [];
let cachedNotas = [];
let cachedDownloadsSet = new Set();
let autoSaveRascunhoTimer = null;
let wasTaskRunning = false;
let lastPillStateKey = '';
let activeDossieCasoId = null;

function renderIcons(rootEl) {
  if (window.lucide) {
    if (rootEl) {
      window.lucide.createIcons({ nodes: [rootEl] });
    } else {
      window.lucide.createIcons();
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  renderIcons();
  setupNavigation();
  setupEventListeners();
  atualizarContadoresChangelog();
  loadAllData();
  carregarHistoricoSherlock();
  carregarNotasOperacionais();

  // Polling rápido para atualizar logs em tempo real (extração de fotos, stories, cascata)
  setInterval(refreshLogs, 1800);
  setInterval(refreshStats, 3500);
});

function setupNavigation() {
  const buttons = document.querySelectorAll('.nav-btn');
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabId = btn.getAttribute('data-tab');
      switchTab(tabId);
    });
  });
}

function switchTab(tabId) {
  currentTab = tabId;
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

  const activeBtn = document.querySelector(`.nav-btn[data-tab="${tabId}"]`);
  const activePane = document.getElementById(tabId);
  if (activeBtn) activeBtn.classList.add('active');
  if (activePane) activePane.classList.add('active');

  const titles = {
    'tab-dashboard': 'Painel Geral',
    'tab-casos': 'Casos & Perfis de Investigação',
    'tab-contas': 'Pool de Contas Fantoches',
    'tab-alvos': 'Alvos & Monitoramento em Cascata',
    'tab-sherlock': 'Sherlock Multi-Redes OSINT',
    'tab-downloads': 'Mídias e Perfis Extraídos',
    'tab-notas': 'Bloco de Notas & Diário de Investigação',
    'tab-logs': 'Logs do Sistema',
    'tab-config': 'Configurações de Automação & Tempos',
    'tab-manual': 'Central de Treinamento & Manual Operacional',
    'tab-changelog': 'Histórico de Atualizações Técnicas'
  };
  document.getElementById('page-title').innerText = titles[tabId] || 'Painel de Controle';

  if (tabId === 'tab-casos') loadCasos();
  if (tabId === 'tab-contas') loadContas();
  if (tabId === 'tab-alvos') {
    loadCasos();
    loadContas();
    loadAlvos();
  }
  if (tabId === 'tab-sherlock') {
    loadCasos();
    loadAlvos();
    carregarHistoricoSherlock();
  }
  if (tabId === 'tab-downloads') {
    loadCasos();
    loadDownloads();
  }
  if (tabId === 'tab-notas') {
    loadCasos();
    carregarNotasOperacionais();
  }
  if (tabId === 'tab-config') loadConfiguracoes();
  if (tabId === 'tab-changelog') atualizarContadoresChangelog();
}

function setupEventListeners() {
  const btnQuickCheck = document.getElementById('btn-quick-check');
  if (btnQuickCheck) {
    btnQuickCheck.addEventListener('click', (e) => dispararVerificacao(e.currentTarget));
  }
  const btnOpenNotasRapidas = document.getElementById('btn-open-notas-rapidas');
  if (btnOpenNotasRapidas) {
    btnOpenNotasRapidas.addEventListener('click', abrirModalNotasRapidas);
  }
  document.getElementById('btn-open-scrape-modal').addEventListener('click', () => {
    loadCasos();
    loadContas();
    abrirModal('modal-scrape');
  });
  document.getElementById('btn-confirm-scrape').addEventListener('click', confirmarScrapeDireto);
  document.getElementById('btn-add-conta').addEventListener('click', () => {
    limparFormConta();
    abrirModal('modal-conta');
  });
  document.getElementById('btn-salvar-modal-conta').addEventListener('click', salvarNovaConta);
  document.getElementById('btn-salvar-alvos').addEventListener('click', salvarNovosAlvos);
  const btnRefreshCasos = document.getElementById('btn-refresh-casos');
  if (btnRefreshCasos) {
    btnRefreshCasos.addEventListener('click', (e) => {
      e.preventDefault();
      atualizarCasosComFeedback(e.currentTarget);
    });
  }
  const btnRefreshContas = document.getElementById('btn-refresh-contas');
  if (btnRefreshContas) {
    btnRefreshContas.addEventListener('click', (e) => {
      e.preventDefault();
      atualizarContasComFeedback(e.currentTarget);
    });
  }
  document.getElementById('btn-refresh-alvos').addEventListener('click', (e) => atualizarAlvosComFeedback(e.currentTarget));
  document.getElementById('btn-refresh-downloads').addEventListener('click', (e) => atualizarDownloadsComFeedback(e.currentTarget));
  document.getElementById('btn-clear-logs').addEventListener('click', limparLogs);
  document.getElementById('btn-toggle-sentinela').addEventListener('click', toggleSentinela);
  document.getElementById('btn-confirm-sentinela').addEventListener('click', confirmarInicioSentinela);

  const btnTestarTodas = document.getElementById('btn-testar-todas-contas');
  if (btnTestarTodas) btnTestarTodas.addEventListener('click', testarTodasContas);

  const btnSalvarCfg = document.getElementById('btn-salvar-config');
  if (btnSalvarCfg) btnSalvarCfg.addEventListener('click', salvarConfiguracoes);

  const selectModo = document.getElementById('select-modo-abordagem');
  if (selectModo) {
    selectModo.addEventListener('change', () => {
      const box = document.getElementById('box-conta-especifica');
      if (box) {
        box.style.display = selectModo.value === 'especifico' ? 'block' : 'none';
      }
    });
  }

  const btnImportTxt = document.getElementById('btn-import-alvos-txt');
  if (btnImportTxt) {
    btnImportTxt.addEventListener('click', importarAlvosTxt);
  }

  const checkAll = document.getElementById('check-all-alvos');
  if (checkAll) checkAll.addEventListener('change', toggleSelectAllAlvos);

  const btnDelSel = document.getElementById('btn-delete-selected-alvos');
  if (btnDelSel) btnDelSel.addEventListener('click', removerAlvosSelecionados);

  const btnClearAll = document.getElementById('btn-clear-all-alvos');
  if (btnClearAll) btnClearAll.addEventListener('click', limparTodosAlvos);

  const btnClearDownloads = document.getElementById('btn-clear-all-downloads');
  if (btnClearDownloads) btnClearDownloads.addEventListener('click', limparTodasMidias);

  const btnNovoCaso = document.getElementById('btn-novo-caso');
  if (btnNovoCaso) btnNovoCaso.addEventListener('click', () => abrirModalNovoCaso());

  const btnSalvarCaso = document.getElementById('btn-salvar-caso');
  if (btnSalvarCaso) btnSalvarCaso.addEventListener('click', salvarCasoForm);
}

function loadAllData() {
  refreshStats();
  refreshLogs();
  loadCasos();
  loadContas();
  loadAlvos();
  loadDownloads();
  loadConfiguracoes();
}

/* ESTATÍSTICAS E STATUS DE BACKGROUND */
async function refreshStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    const elCasos = document.getElementById('stat-casos');
    const elCasosAtivos = document.getElementById('stat-casos-ativos');
    const badgeCasos = document.getElementById('badge-casos-count');
    const badgeNotas = document.getElementById('badge-notas-count');
    if (elCasos) elCasos.innerText = data.total_casos || 0;
    if (elCasosAtivos) elCasosAtivos.innerText = `${data.casos_ativos || 0} em andamento`;
    if (badgeCasos) badgeCasos.innerText = data.total_casos || 0;
    if (badgeNotas && typeof data.total_notas !== 'undefined') badgeNotas.innerText = data.total_notas || 0;

    document.getElementById('stat-contas').innerText = data.total_contas;
    document.getElementById('stat-contas-ativas').innerText = `${data.contas_ativas} ativa(s)`;
    document.getElementById('stat-alvos').innerText = data.total_alvos;
    document.getElementById('stat-alvos-pendentes').innerText = `${data.alvos_pendentes} pendente(s)`;
    document.getElementById('stat-concluidos').innerText = data.alvos_concluidos;
    document.getElementById('stat-downloads').innerText = data.perfis_baixados;

    const isRunning = Boolean(data.tarefa_atual);
    const pillKey = `${data.db_ativo}|${data.db_tamanho_kb}|${data.tarefa_atual || ''}|${data.sentinela_ativo}|${data.sentinela_intervalo}`;

    if (pillKey !== lastPillStateKey) {
      lastPillStateKey = pillKey;

      // Indicador de Banco SQLite
      const pillDb = document.getElementById('pill-db-status');
      if (pillDb) {
        pillDb.innerHTML = data.db_ativo
          ? `<i data-lucide="database"></i><span>SQLite: osint_coletas.db (${data.db_tamanho_kb} KB)</span>`
          : `<i data-lucide="database"></i><span>SQLite: inicializando...</span>`;
      }

      // Indicador de Tarefa em Execução
      const pillTask = document.getElementById('pill-task-status');
      if (pillTask) {
        if (isRunning) {
          pillTask.innerHTML = `<i data-lucide="loader-2" class="animate-spin"></i><span>${escapeHtml(data.tarefa_atual)}</span>`;
          pillTask.classList.add('running');
        } else {
          pillTask.innerHTML = `<i data-lucide="check-circle-2"></i><span>Motor: Ocioso / Pronto</span>`;
          pillTask.classList.remove('running');
        }
      }

      // Indicador do Motor Go Turbo
      const pillGo = document.getElementById('pill-go-status');
      if (pillGo) {
        if (data.go_engine_disponivel) {
          pillGo.innerHTML = `<i data-lucide="zap"></i><span>Go Turbo REST: Pronto</span>`;
          pillGo.style.borderColor = 'rgba(88,166,255,0.45)';
          pillGo.style.color = 'var(--accent-blue)';
        } else {
          pillGo.innerHTML = `<i data-lucide="alert-circle"></i><span>Go: Recompilar</span>`;
          pillGo.style.borderColor = 'var(--border-color)';
          pillGo.style.color = 'var(--text-muted)';
        }
      }

      // Indicador do Sentinela 24/7
      const dot = document.getElementById('sentinela-dot');
      const btn = document.getElementById('btn-toggle-sentinela');
      const subTxt = document.getElementById('sentinela-sub-txt');
      if (data.sentinela_ativo) {
        dot.classList.add('active');
        btn.innerHTML = `<i data-lucide="square"></i><span>Parar Sentinela</span>`;
        btn.classList.add('active');
        if (subTxt) subTxt.innerText = `Ativo (ciclo a cada ${data.sentinela_intervalo || 30} min)`;
      } else {
        dot.classList.remove('active');
        btn.innerHTML = `<i data-lucide="power"></i><span>Ligar Sentinela</span>`;
        btn.classList.remove('active');
        if (subTxt) subTxt.innerText = 'Roda em background (pode fechar a aba)';
      }

      renderIcons();
    }

    // Se uma tarefa acabou de terminar, atualiza as tabelas automaticamente
    if (wasTaskRunning && !isRunning) {
      loadCasos();
      loadContas();
      loadAlvos();
      loadDownloads();
      if (activeDossieCasoId) {
        abrirDossieCaso(activeDossieCasoId, true);
      }
    }
    wasTaskRunning = isRunning;
  } catch (err) {
    console.error('Erro ao atualizar estatísticas:', err);
  }
}

/* LOGS EM TEMPO REAL */
async function refreshLogs() {
  try {
    const res = await fetch('/api/logs');
    cachedLogs = await res.json();
    document.getElementById('badge-logs-count').innerText = cachedLogs.length;
    renderizarTerminais();
  } catch (err) {
    console.error('Erro ao buscar logs:', err);
  }
}

function filtrarLogs(filtro) {
  currentLogFilter = filtro;
  document.querySelectorAll('.log-filter-btn[data-filter]').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-filter') === filtro);
  });
  renderizarTerminais();
}

function renderizarTerminais() {
  const renderLog = l => `<div class="log-line log-${l.nivel}"><span class="log-time">[${l.timestamp}]</span> ${escapeHtml(l.mensagem)}</div>`;

  const dashTerm = document.getElementById('dash-terminal');
  if (dashTerm) {
    const htmlDash = cachedLogs.map(renderLog).join('');
    const wasAtBottomDash = dashTerm.scrollHeight - dashTerm.scrollTop <= dashTerm.clientHeight + 50;
    dashTerm.innerHTML = htmlDash || '<div class="text-muted">Aguardando atividades...</div>';
    if (wasAtBottomDash) dashTerm.scrollTop = dashTerm.scrollHeight;
  }

  const fullTerm = document.getElementById('full-terminal');
  if (fullTerm) {
    const filtrados = currentLogFilter === 'TODOS'
      ? cachedLogs
      : cachedLogs.filter(l => l.nivel === currentLogFilter);
    const htmlFull = filtrados.map(renderLog).join('');
    const wasAtBottomFull = fullTerm.scrollHeight - fullTerm.scrollTop <= fullTerm.clientHeight + 50;
    fullTerm.innerHTML = htmlFull || '<div class="text-muted">Nenhum registro para este filtro.</div>';
    if (wasAtBottomFull) fullTerm.scrollTop = fullTerm.scrollHeight;
  }
}

async function limparLogs() {
  await fetch('/api/logs/limpar', { method: 'POST' });
  refreshLogs();
}

/* POOL DE CONTAS */
async function loadContas() {
  try {
    const res = await fetch('/api/contas');
    const contas = await res.json();
    const tbody = document.getElementById('contas-tbody');

    // Atualiza seletores de contas nos formulários de Alvos e Extração Direta
    const contasAtivas = contas.filter(c => c.ativo === 'Sim' || c.ativo === true || c.ativo === 'true');
    const selectAlvo = document.getElementById('select-conta-alvo');
    if (selectAlvo) {
      if (!contasAtivas.length) {
        selectAlvo.innerHTML = '<option value="">Nenhuma conta ativa no Pool</option>';
      } else {
        selectAlvo.innerHTML = contasAtivas.map(c => `<option value="${c.user}">@${c.user} (ID #${c.id})</option>`).join('');
      }
    }

    const selectScrape = document.getElementById('select-conta-scrape');
    if (selectScrape) {
      const opts = ['<option value="">Automático (Conta vinculada ao alvo ou 1ª ativa)</option>'];
      contasAtivas.forEach(c => {
        opts.push(`<option value="${c.user}">Usar @${c.user} (ID #${c.id})</option>`);
      });
      selectScrape.innerHTML = opts.join('');
    }

    const selectCasoConta = document.getElementById('modal-caso-conta-user');
    if (selectCasoConta) {
      selectCasoConta.innerHTML = contasAtivas.length
        ? contasAtivas.map(c => `<option value="${c.user}">@${c.user} (ID #${c.id})</option>`).join('')
        : '<option value="">Nenhuma conta ativa</option>';
    }

    if (!tbody) return;
    if (!contas.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center">Nenhuma conta cadastrada no pool. Clique em "Adicionar Conta".</td></tr>';
      return;
    }

    tbody.innerHTML = contas.map(c => {
      const isAtiva = c.ativo === 'Sim' || c.ativo === true || c.ativo === 'true';
      const sessionDisplay = c.sessionid ? c.sessionid.slice(0, 18) + '...' : '<span class="text-muted">Vazio</span>';

      let badgeSessao = '<span class="badge badge-gray"><i data-lucide="minus-circle"></i><span>Não testada</span></span>';
      if (c.ultimo_teste === 'CONECTADA') {
        badgeSessao = '<span class="badge badge-green"><i data-lucide="check-circle-2"></i><span>Conectada</span></span>';
      } else if (c.ultimo_teste === 'EXPIRADA' || c.ultimo_teste === 'SEM_SESSION') {
        badgeSessao = '<span class="badge badge-red"><i data-lucide="x-circle"></i><span>Expirada</span></span>';
      }

      return `
        <tr>
          <td><strong>#${c.id}</strong></td>
          <td><strong>@${escapeHtml(c.user || 'Sem user')}</strong></td>
          <td><span class="badge ${isAtiva ? 'badge-green' : 'badge-red'}">${isAtiva ? 'ATIVA' : 'PAUSADA'}</span></td>
          <td>${badgeSessao}</td>
          <td><code>${sessionDisplay}</code></td>
          <td>${c.adicionado_em || '-'}</td>
          <td>
            <div class="inline-flex items-center gap-1.5 flex-wrap">
              <button class="btn-secondary-sm" onclick="toggleConta(${c.id})" title="${isAtiva ? 'Pausar conta' : 'Ativar conta'}">
                <i data-lucide="${isAtiva ? 'pause' : 'play'}"></i>
                <span>${isAtiva ? 'Pausar' : 'Ativar'}</span>
              </button>
              <button class="btn-secondary-sm" onclick="editarConta(${c.id}, '${escapeHtml(c.user || '')}', '${escapeHtml(c.ds_user_id || '')}', '${escapeHtml(c.sessionid || '')}')">
                <i data-lucide="key-round"></i>
                <span>Atualizar</span>
              </button>
              <button class="btn-secondary-sm" onclick="testarConta(${c.id}, this)">
                <i data-lucide="shield-check"></i>
                <span>Testar</span>
              </button>
              <button class="btn-secondary-sm" onclick="removerConta(${c.id})" title="Remover conta" style="color:var(--danger);">
                <i data-lucide="trash-2"></i>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
    renderIcons();
  } catch (err) {
    console.error('Erro ao carregar contas:', err);
  }
}

async function testarTodasContas() {
  const btn = document.getElementById('btn-testar-todas-contas');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader-2" class="animate-spin"></i><span>Iniciando testes...</span>';
    renderIcons();
  }
  try {
    const res = await fetch('/api/contas/testar_todas', { method: 'POST' });
    const data = await res.json();
    if (data.sucesso) {
      alert(data.mensagem);
    } else {
      alert(data.erro || 'Erro ao iniciar teste do Pool.');
    }
  } catch (e) {
    alert('Erro ao testar contas do Pool: ' + e);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i data-lucide="shield-check"></i><span>Testar Todo o Pool</span>';
      renderIcons();
    }
    refreshStats();
    refreshLogs();
  }
}

async function toggleConta(id) {
  await fetch(`/api/contas/${id}/toggle`, { method: 'POST' });
  loadContas();
  refreshStats();
}

function editarConta(id, user, ds_user_id, sessionid) {
  document.getElementById('modal-conta-id').value = id;
  document.getElementById('modal-conta-title').innerHTML = `<i data-lucide="key-round" class="text-gh-blue"></i><span>Atualizar Conta @${escapeHtml(user)}</span>`;
  document.getElementById('modal-conta-user').value = user;
  document.getElementById('modal-conta-ds').value = ds_user_id;
  document.getElementById('modal-conta-session').value = sessionid;
  renderIcons();
  abrirModal('modal-conta');
}

async function testarConta(id, btnElement) {
  if (btnElement) {
    btnElement.innerHTML = '<i data-lucide="loader-2" class="animate-spin"></i><span>Testando...</span>';
    btnElement.disabled = true;
    renderIcons();
  }
  try {
    const res = await fetch(`/api/contas/${id}/testar`, { method: 'POST' });
    const data = await res.json();
    if (data.autenticado) {
      alert('Conta CONECTADA e autenticada com sucesso no Instagram!');
    } else {
      alert('Falha na autenticação: sessão expirada ou inválida.');
    }
  } catch (e) {
    alert('Erro ao comunicar com o servidor: ' + e);
  } finally {
    if (btnElement) {
      btnElement.innerHTML = '<i data-lucide="shield-check"></i><span>Testar</span>';
      btnElement.disabled = false;
      renderIcons();
    }
    refreshLogs();
    loadContas();
  }
}

async function removerConta(id) {
  if (confirm('Deseja realmente remover esta conta do pool?')) {
    await fetch(`/api/contas/${id}`, { method: 'DELETE' });
    loadContas();
    refreshStats();
  }
}

async function salvarNovaConta() {
  const id = document.getElementById('modal-conta-id').value;
  const user = document.getElementById('modal-conta-user').value.trim();
  const ds = document.getElementById('modal-conta-ds').value.trim();
  const session = document.getElementById('modal-conta-session').value.trim();

  if (!user || !session) {
    alert('Preencha ao menos o Username e o SessionID.');
    return;
  }

  if (id) {
    await fetch(`/api/contas/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user, ds_user_id: ds, sessionid: session })
    });
    alert('Conta atualizada com sucesso!');
  } else {
    await fetch('/api/contas', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user, ds_user_id: ds, sessionid: session })
    });
    alert('Conta adicionada com sucesso!');
  }

  fecharModal('modal-conta');
  limparFormConta();
  loadContas();
  refreshStats();
}

function limparFormConta() {
  document.getElementById('modal-conta-id').value = '';
  document.getElementById('modal-conta-title').innerHTML = `<i data-lucide="user-plus" class="text-gh-blue"></i><span>Adicionar Conta ao Pool</span>`;
  document.getElementById('modal-conta-user').value = '';
  document.getElementById('modal-conta-ds').value = '';
  document.getElementById('modal-conta-session').value = '';
  renderIcons();
}

/* CASOS & PERFIS DE INVESTIGAÇÃO (DOSSIÊS) */
async function loadCasos() {
  try {
    const res = await fetch('/api/casos');
    cachedCasos = await res.json();
    const badgeCasos = document.getElementById('badge-casos-count');
    if (badgeCasos) badgeCasos.innerText = cachedCasos.length;
    popularSeletoresCasos();
    renderizarGridCasos();
  } catch (err) {
    console.error('Erro ao carregar casos:', err);
  }
}

async function executarBotaoComFeedback(btnEl, fallbackId, asyncFn, textoCarregando = 'Atualizando...', textoConcluido = 'Atualizado!') {
  const rawEl = btnEl || (fallbackId ? document.getElementById(fallbackId) : null);
  const btn = (rawEl && rawEl.closest) ? (rawEl.closest('button') || rawEl) : rawEl;

  if (btn && btn.dataset.busy === '1') return;

  if (btn) {
    if (!btn.dataset.origHtml) {
      btn.dataset.origHtml = btn.innerHTML;
    }
    btn.dataset.busy = '1';
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="animate-spin"></i><span>${escapeHtml(textoCarregando)}</span>`;
    renderIcons(btn);
  }

  try {
    await asyncFn();
    if (btn) {
      btn.innerHTML = `<i data-lucide="check" class="text-gh-green"></i><span class="text-gh-green">${escapeHtml(textoConcluido)}</span>`;
      renderIcons(btn);
      setTimeout(() => {
        btn.disabled = false;
        btn.dataset.busy = '0';
        btn.innerHTML = btn.dataset.origHtml;
        renderIcons(btn);
      }, 900);
    }
  } catch (err) {
    console.error('Erro na ação do botão:', err);
    if (btn) {
      btn.disabled = false;
      btn.dataset.busy = '0';
      btn.innerHTML = btn.dataset.origHtml;
      renderIcons(btn);
    }
  }
}

async function atualizarCasosComFeedback(btnEl) {
  await executarBotaoComFeedback(btnEl, 'btn-refresh-casos', async () => {
    await Promise.all([loadCasos(), loadAlvos(), refreshStats(), refreshLogs()]);
    if (activeDossieCasoId) {
      await abrirDossieCaso(activeDossieCasoId, true);
    }
  });
}

async function atualizarContasComFeedback(btnEl) {
  await executarBotaoComFeedback(btnEl, 'btn-refresh-contas', async () => {
    await Promise.all([loadContas(), refreshStats(), refreshLogs()]);
  });
}

async function atualizarAlvosComFeedback(btnEl) {
  await executarBotaoComFeedback(btnEl, 'btn-refresh-alvos', async () => {
    await Promise.all([loadAlvos(), loadDownloads(), refreshStats(), refreshLogs()]);
  });
}

async function atualizarDownloadsComFeedback(btnEl) {
  await executarBotaoComFeedback(btnEl, 'btn-refresh-downloads', async () => {
    await Promise.all([loadDownloads(), refreshStats(), refreshLogs()]);
  });
}

async function atualizarSherlockComFeedback(btnEl) {
  await executarBotaoComFeedback(btnEl, 'btn-refresh-sherlock', async () => {
    await Promise.all([carregarHistoricoSherlock(), refreshStats(), refreshLogs()]);
  });
}

async function atualizarNotasComFeedback(btnEl) {
  await executarBotaoComFeedback(btnEl, 'btn-refresh-notas', async () => {
    await Promise.all([carregarNotasOperacionais(), refreshStats()]);
  });
}

window.atualizarCasosComFeedback = atualizarCasosComFeedback;
window.atualizarContasComFeedback = atualizarContasComFeedback;
window.atualizarAlvosComFeedback = atualizarAlvosComFeedback;
window.atualizarDownloadsComFeedback = atualizarDownloadsComFeedback;
window.atualizarSherlockComFeedback = atualizarSherlockComFeedback;
window.atualizarNotasComFeedback = atualizarNotasComFeedback;

function popularSeletoresCasos() {
  const opcoesForm = ['<option value="">Sem caso específico (Geral)</option>']
    .concat(cachedCasos.map(c => `<option value="${c.id}">${escapeHtml(c.nome)}${c.referencia ? ' (' + escapeHtml(c.referencia) + ')' : ''}</option>`))
    .join('');

  ['select-caso-novo-alvo', 'select-caso-scrape', 'sherlock-select-caso', 'nota-select-caso'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      const valAtual = el.value;
      el.innerHTML = opcoesForm;
      if (valAtual) el.value = valAtual;
    }
  });

  const opcoesFiltro = [
    '<option value="TODOS">Filtrar: Todos os Casos</option>',
    '<option value="SEM_CASO">Sem Caso Vinculado</option>'
  ].concat(cachedCasos.map(c => `<option value="${c.id}">Caso: ${escapeHtml(c.nome)}</option>`)).join('');

  ['select-filtro-caso-alvos', 'select-filtro-caso-downloads'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      const valAtual = el.value || 'TODOS';
      el.innerHTML = opcoesFiltro;
      el.value = valAtual;
      if (!el.value) el.value = 'TODOS';
    }
  });
}

function gerarSelectInlineCaso(username, casoIdAtual) {
  const opts = [`<option value="" ${!casoIdAtual ? 'selected' : ''}>Sem caso</option>`]
    .concat(cachedCasos.map(c => `<option value="${c.id}" ${Number(casoIdAtual) === Number(c.id) ? 'selected' : ''}>${escapeHtml(c.nome)}</option>`))
    .join('');
  return `<select class="input-select" style="padding:3px 8px; font-size:11px; max-width:170px;" onchange="vincularAlvoCaso('${escapeHtml(username)}', this.value)" title="Vincular ou trocar Caso deste investigado">${opts}</select>`;
}

function filtrarStatusCasos(statusFiltro, btnEl) {
  currentCasoStatusFilter = statusFiltro;
  if (btnEl && btnEl.parentElement) {
    btnEl.parentElement.querySelectorAll('.filter-chip').forEach(b => b.classList.remove('active'));
    btnEl.classList.add('active');
  }
  renderizarGridCasos();
}

function renderizarGridCasos() {
  const grid = document.getElementById('casos-grid');
  if (!grid) return;

  const buscaEl = document.getElementById('input-search-casos');
  const termo = buscaEl ? buscaEl.value.trim().toLowerCase() : '';

  const filtrados = cachedCasos.filter(c => {
    const st = c.status || 'EM_ANDAMENTO';
    const matchSt = currentCasoStatusFilter === 'TODOS'
      || (currentCasoStatusFilter === 'EM_ANDAMENTO' && st === 'EM_ANDAMENTO')
      || (currentCasoStatusFilter === 'CONCLUIDO' && st !== 'EM_ANDAMENTO');

    if (!matchSt) return false;
    if (!termo) return true;
    const blob = `${c.nome || ''} ${c.referencia || ''} ${c.descricao || ''} ${(c.alvos || []).join(' ')}`.toLowerCase();
    return blob.includes(termo);
  });

  if (!filtrados.length) {
    grid.innerHTML = `
      <div class="col-span-full bg-gh-bg border border-gh-border rounded-lg p-8 text-center space-y-3">
        <div class="w-11 h-11 rounded-full bg-gh-blue/10 border border-gh-blue/30 flex items-center justify-center text-gh-blue mx-auto">
          <i data-lucide="briefcase" style="width:20px;height:20px;"></i>
        </div>
        <div class="text-sm font-semibold text-gh-title">Nenhum Caso de Investigação encontrado</div>
        <p class="text-xs text-gh-muted max-w-md mx-auto">Crie um perfil de caso (ex: nome da investigação, cliente/referência e observações) e adicione quais @contas serão investigadas nele.</p>
        <button class="btn-primary mt-1" onclick="abrirModalNovoCaso()">
          <i data-lucide="folder-plus"></i>
          <span>Criar Primeiro Caso</span>
        </button>
      </div>
    `;
    renderIcons();
    return;
  }

  grid.innerHTML = filtrados.map(c => {
    const r = c.resumo || { total_alvos: 0, concluidos: 0, pendentes: 0, baixados: 0 };
    let st = c.status || 'EM_ANDAMENTO';
    if (st !== 'ARQUIVADO' && r.total_alvos > 0 && r.pendentes === 0) {
      st = 'CONCLUIDO';
    }
    const isConcluido = st === 'CONCLUIDO';
    const badgeCls = isConcluido ? 'badge-green' : (st === 'EM_ANDAMENTO' ? 'badge-yellow' : 'badge-gray');
    const stLabel = isConcluido ? 'CONCLUÍDO' : (st === 'EM_ANDAMENTO' ? 'EM ANDAMENTO' : st);
    const pct = r.total_alvos > 0 ? Math.min(100, Math.round((r.concluidos / r.total_alvos) * 100)) : (isConcluido ? 100 : 0);

    let dataFormatada = '';
    if (c.criado_em) {
      const partesData = String(c.criado_em).slice(0, 10).split('-');
      dataFormatada = partesData.length === 3 ? `${partesData[2]}/${partesData[1]}/${partesData[0]}` : c.criado_em.slice(0, 10);
    }

    const detalhesMap = {};
    (c.alvos_detalhes || []).forEach(ad => {
      if (ad && ad.username) detalhesMap[String(ad.username).toLowerCase()] = ad;
    });

    const alvosPills = (c.alvos || []).slice(0, 6).map(u => {
      const ad = detalhesMap[String(u).toLowerCase()] || {};
      const jaBaixado = Boolean(ad.baixado || ad.status === 'CONCLUIDO');
      const dotColor = jaBaixado ? 'bg-gh-green' : 'bg-gh-yellow';
      const clickAct = jaBaixado ? `verDetalhesPerfil('${escapeHtml(u)}')` : `abrirDossieCaso(${c.id})`;
      return `<button type="button" onclick="${clickAct}" class="attempt-tag inline-flex items-center gap-1.5 cursor-pointer hover:border-gh-blue transition" title="${jaBaixado ? 'Ver mídias e relatório de @' + escapeHtml(u) : 'Abrir dossiê do caso'}"><span class="w-1.5 h-1.5 rounded-full ${dotColor}"></span><span>@${escapeHtml(u)}</span></button>`;
    }).join('');
    const extraCount = (c.alvos || []).length > 6 ? `<span class="attempt-tag">+${c.alvos.length - 6}</span>` : '';

    return `
      <div class="caso-card-modern bg-gh-card border border-gh-border rounded-xl p-5 flex flex-col justify-between gap-4 hover:border-gh-blue/60 transition shadow-sm ${isConcluido ? 'caso-card-concluido' : 'caso-card-andamento'}">
        <div class="space-y-3.5">
          <!-- Cabeçalho do Caso -->
          <div class="flex items-start justify-between gap-2.5">
            <div class="flex items-start gap-2.5 min-w-0">
              <div class="w-10 h-10 rounded-lg ${isConcluido ? 'bg-gh-green/10 border-gh-green/30 text-gh-green' : 'bg-gh-blue/10 border-gh-blue/30 text-gh-blue'} border flex items-center justify-center shrink-0 mt-0.5">
                <i data-lucide="${isConcluido ? 'folder-check' : 'briefcase'}" style="width:19px;height:19px;"></i>
              </div>
              <div class="min-w-0">
                <div class="flex items-center gap-1.5 flex-wrap">
                  <span class="text-xs font-mono font-bold text-gh-blue bg-gh-blue/10 border border-gh-blue/30 px-1.5 py-0.5 rounded">#${c.id}</span>
                  <h4 class="text-base font-bold text-gh-title truncate">${escapeHtml(c.nome)}</h4>
                </div>
                <div class="flex items-center gap-2.5 flex-wrap mt-1 text-xs text-gh-muted">
                  ${c.referencia ? `<span class="inline-flex items-center gap-1 text-gh-text"><i data-lucide="bookmark" class="text-gh-blue" style="width:12px;height:12px;"></i><span>${escapeHtml(c.referencia)}</span></span>` : ''}
                  ${dataFormatada ? `<span class="inline-flex items-center gap-1 font-mono text-[11.5px]"><i data-lucide="calendar" style="width:11.5px;height:11.5px;"></i><span>${escapeHtml(dataFormatada)}</span></span>` : ''}
                </div>
              </div>
            </div>
            <button type="button" class="badge ${badgeCls} inline-flex items-center gap-1 cursor-pointer hover:opacity-80 transition shrink-0" onclick="alternarStatusCaso(${c.id}, '${st}')" title="Clique para alternar status (Em Andamento / Concluído)">
              <i data-lucide="${isConcluido ? 'check-circle-2' : 'clock'}" style="width:12px;height:12px;"></i>
              <span>${escapeHtml(stLabel)}</span>
            </button>
          </div>

          <!-- Observações / Descrição do Caso -->
          <div class="bg-gh-bg/70 border border-gh-border/80 rounded-lg px-3 py-2 text-xs text-gh-text line-clamp-2 min-h-[38px] flex items-center">
            <span>${escapeHtml(c.descricao || 'Nenhuma observação operacional registrada neste dossiê.')}</span>
          </div>

          <!-- Barra de Progresso do Dossiê -->
          <div class="space-y-1">
            <div class="flex items-center justify-between text-xs">
              <span class="text-gh-muted font-medium">Progresso da Extração</span>
              <strong class="font-mono ${isConcluido ? 'text-gh-green' : 'text-gh-blue'}">${r.concluidos}/${r.total_alvos} concluído(s) (${pct}%)</strong>
            </div>
            <div class="w-full bg-gh-bg border border-gh-border rounded-full h-2 overflow-hidden">
              <div class="${isConcluido ? 'bg-gh-green' : 'bg-gh-blue'} h-full transition-all duration-300" style="width:${pct}%;"></div>
            </div>
          </div>

          <!-- KPIs do Caso -->
          <div class="grid grid-cols-3 gap-2 text-xs">
            <div class="bg-gh-bg border border-gh-border rounded-lg px-3 py-2">
              <span class="text-gh-muted flex items-center gap-1 text-[11.5px]"><i data-lucide="users" style="width:12px;height:12px;"></i>Alvos</span>
              <strong class="text-gh-title font-mono text-base block mt-0.5">${r.total_alvos}</strong>
            </div>
            <div class="bg-gh-bg border border-gh-border rounded-lg px-3 py-2">
              <span class="text-gh-muted flex items-center gap-1 text-[11.5px]"><i data-lucide="check-circle-2" class="text-gh-green" style="width:12px;height:12px;"></i>Extraídos</span>
              <strong class="text-gh-green font-mono text-base block mt-0.5">${r.concluidos}</strong>
            </div>
            <div class="bg-gh-bg border border-gh-border rounded-lg px-3 py-2">
              <span class="text-gh-muted flex items-center gap-1 text-[11.5px]"><i data-lucide="clock" class="text-gh-yellow" style="width:12px;height:12px;"></i>Pendentes</span>
              <strong class="text-gh-yellow font-mono text-base block mt-0.5">${r.pendentes}</strong>
            </div>
          </div>

          <!-- Lista de @Alvos Vinculados -->
          <div class="space-y-1">
            <span class="text-[11px] font-semibold uppercase tracking-wider text-gh-muted block">Contas Vinculadas ao Caso:</span>
            <div class="attempt-list">
              ${alvosPills || '<span class="text-xs text-gh-muted italic">Nenhuma @conta vinculada ainda</span>'}
              ${extraCount}
            </div>
          </div>
        </div>

        <!-- Rodapé de Ações -->
        <div class="flex items-center justify-between gap-2 pt-3 border-t border-gh-border">
          <button class="btn-primary-sm" onclick="abrirDossieCaso(${c.id})">
            <i data-lucide="folder-open"></i>
            <span>Abrir Dossiê</span>
          </button>
          <div class="flex items-center gap-1.5">
            <a href="/api/casos/${c.id}/zip" class="btn-secondary-sm" style="text-decoration:none;" title="Baixar pacote ZIP consolidado de todo este Caso">
              <i data-lucide="download" class="text-gh-green"></i>
              <span>ZIP</span>
            </a>
            <button class="btn-secondary-sm" onclick="editarCaso(${c.id})" title="Editar informações do Caso">
              <i data-lucide="pencil"></i>
            </button>
            <button class="btn-secondary-sm" onclick="removerCasoUI(${c.id})" title="Excluir Caso" style="color:var(--danger);">
              <i data-lucide="trash-2"></i>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
  renderIcons();
}

async function alternarStatusCaso(casoId, statusAtual) {
  try {
    const res = await fetch(`/api/casos/${casoId}/toggle_status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    if (data.sucesso) {
      await Promise.all([loadCasos(), refreshStats()]);
      if (activeDossieCasoId && Number(activeDossieCasoId) === Number(casoId)) {
        await abrirDossieCaso(casoId, true);
      }
    }
  } catch (err) {
    console.error('Erro ao alternar status do caso:', err);
  }
}
window.alternarStatusCaso = alternarStatusCaso;

function abrirModalNovoCaso() {
  loadContas();
  document.getElementById('modal-caso-id').value = '';
  document.getElementById('modal-caso-titulo').innerHTML = `<i data-lucide="briefcase" class="text-gh-blue"></i><span>Novo Caso / Perfil de Investigação</span>`;
  document.getElementById('modal-caso-nome').value = '';
  document.getElementById('modal-caso-ref').value = '';
  document.getElementById('modal-caso-desc').value = '';
  document.getElementById('modal-caso-alvos').value = '';
  document.getElementById('modal-caso-disparar').checked = true;
  document.getElementById('box-modal-caso-status').style.display = 'none';
  document.getElementById('box-modal-caso-alvos-iniciais').style.display = 'block';
  renderIcons();
  abrirModal('modal-novo-caso');
}

function editarCaso(casoId) {
  const c = cachedCasos.find(x => Number(x.id) === Number(casoId));
  if (!c) return;
  document.getElementById('modal-caso-id').value = c.id;
  document.getElementById('modal-caso-titulo').innerHTML = `<i data-lucide="pencil" class="text-gh-blue"></i><span>Editar Caso #${c.id}</span>`;
  document.getElementById('modal-caso-nome').value = c.nome || '';
  document.getElementById('modal-caso-ref').value = c.referencia || '';
  document.getElementById('modal-caso-desc').value = c.descricao || '';
  document.getElementById('modal-caso-status').value = c.status || 'EM_ANDAMENTO';
  document.getElementById('box-modal-caso-status').style.display = 'block';
  document.getElementById('box-modal-caso-alvos-iniciais').style.display = 'none';
  renderIcons();
  abrirModal('modal-novo-caso');
}

async function salvarCasoForm() {
  const id = document.getElementById('modal-caso-id').value;
  const nome = document.getElementById('modal-caso-nome').value.trim();
  const referencia = document.getElementById('modal-caso-ref').value.trim();
  const descricao = document.getElementById('modal-caso-desc').value.trim();

  if (!nome) {
    alert('Informe o Nome do Caso / Investigação.');
    return;
  }

  if (id) {
    const status = document.getElementById('modal-caso-status').value;
    const res = await fetch(`/api/casos/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome, referencia, descricao, status })
    });
    const data = await res.json();
    if (!data.sucesso) {
      alert(data.erro || 'Erro ao atualizar caso.');
      return;
    }
  } else {
    const alvos = document.getElementById('modal-caso-alvos').value.trim();
    const disparar_agora = document.getElementById('modal-caso-disparar').checked;
    const modo = document.getElementById('modal-caso-modo').value;
    const conta_user = document.getElementById('modal-caso-conta-user').value;

    const res = await fetch('/api/casos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome, referencia, descricao, alvos, disparar_agora, modo, conta_user })
    });
    const data = await res.json();
    if (!data.sucesso) {
      alert(data.erro || 'Erro ao criar caso.');
      return;
    }
    if (data.mensagem) alert(data.mensagem);
  }

  fecharModal('modal-novo-caso');
  await loadCasos();
  loadAlvos();
  loadDownloads();
  refreshStats();
  refreshLogs();
}

async function removerCasoUI(casoId) {
  const c = cachedCasos.find(x => Number(x.id) === Number(casoId));
  if (confirm(`Deseja excluir o Caso "${c ? c.nome : '#' + casoId}"?\n(As contas monitoradas e pastas baixadas NÃO serão apagadas, apenas desvinculadas deste caso).`)) {
    await fetch(`/api/casos/${casoId}`, { method: 'DELETE' });
    if (activeDossieCasoId === Number(casoId)) fecharModal('modal-dossie-caso');
    await loadCasos();
    loadAlvos();
    loadDownloads();
    refreshStats();
  }
}

async function vincularAlvoCaso(username, casoId) {
  await fetch('/api/casos/vincular', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, caso_id: casoId || null })
  });
  await loadCasos();
  loadAlvos();
  loadDownloads();
  if (activeDossieCasoId) abrirDossieCaso(activeDossieCasoId, true);
}

async function abrirDossieCaso(casoId, silencioso = false) {
  activeDossieCasoId = Number(casoId);
  if (!silencioso) abrirModal('modal-dossie-caso');

  const res = await fetch('/api/casos');
  cachedCasos = await res.json();
  popularSeletoresCasos();
  renderizarGridCasos();

  const c = cachedCasos.find(x => Number(x.id) === Number(casoId));
  const box = document.getElementById('dossie-caso-conteudo');
  const exportBar = document.getElementById('dossie-caso-export-bar');
  if (!c) {
    box.innerHTML = '<p class="text-gh-red">Caso não encontrado.</p>';
    return;
  }

  document.getElementById('dossie-caso-titulo').innerHTML = `<i data-lucide="folder-open" class="text-gh-blue"></i><span>Dossiê #${c.id} — ${escapeHtml(c.nome)}</span>`;
  if (exportBar) {
    exportBar.innerHTML = `
      <a href="/api/casos/${c.id}/zip" class="btn-primary" style="text-decoration:none;">
        <i data-lucide="download"></i>
        <span>Baixar Dossiê Completo do Caso (.ZIP)</span>
      </a>
      <button class="btn-secondary" onclick="filtrarAbaPorCaso('tab-alvos', '${c.id}')">
        <i data-lucide="crosshair"></i>
        <span>Ver na Tabela de Alvos</span>
      </button>
      <button class="btn-secondary" onclick="filtrarAbaPorCaso('tab-downloads', '${c.id}')">
        <i data-lucide="folder-down"></i>
        <span>Ver Mídias do Caso</span>
      </button>
    `;
  }

  const detalhes = c.alvos_detalhes || [];
  const linhasHtml = detalhes.length ? detalhes.map(a => {
    let bCls = 'badge-yellow';
    if (a.status === 'CONCLUIDO' || a.baixado) bCls = 'badge-green';
    if (a.status === 'ESGOTADO' || a.status === 'REJEITADO_COOLDOWN') bCls = 'badge-red';

    return `
      <tr>
        <td><strong class="font-mono text-gh-title">@${escapeHtml(a.username)}</strong></td>
        <td>${a.conta_atual ? '@' + escapeHtml(a.conta_atual) : '<span class="text-muted">-</span>'}</td>
        <td><span class="badge ${bCls}">${escapeHtml(a.status || 'VINCULADO')}</span></td>
        <td>${a.baixado ? '<span class="badge badge-green"><i data-lucide="check-circle-2"></i><span>Coletado</span></span>' : '<span class="text-muted text-xs">Pendente</span>'}</td>
        <td>
          <div class="inline-flex items-center gap-1.5 flex-wrap">
            ${a.baixado ? `<button class="btn-secondary-sm" onclick="verDetalhesPerfil('${escapeHtml(a.username)}')"><i data-lucide="layout-grid" class="text-gh-blue"></i><span>Relatório</span></button>` : ''}
            ${a.baixado ? `<a href="/api/downloads/${encodeURIComponent(a.username)}/csv" class="btn-secondary-sm" style="text-decoration:none;"><i data-lucide="file-spreadsheet" class="text-gh-green"></i><span>CSV</span></a>` : ''}
            <button class="btn-secondary-sm" onclick="baixarDireto('${escapeHtml(a.username)}', '${escapeHtml(a.conta_atual || '')}', 6, ${c.id}, 'go', this)" title="Extrair perfil agora"><i data-lucide="zap" class="text-gh-yellow"></i><span>Extrair</span></button>
            <button class="btn-secondary-sm" onclick="fecharModal('modal-dossie-caso'); investigarNoSherlock('${escapeHtml(a.username)}', '${c.id}')" title="Sondar este alvo em 480+ redes sociais"><i data-lucide="scan-search" class="text-gh-blue"></i><span>Sherlock</span></button>
            <button class="btn-secondary-sm" onclick="vincularAlvoCaso('${escapeHtml(a.username)}', null)" title="Remover vínculo deste caso" style="color:var(--danger);"><i data-lucide="unlink"></i></button>
          </div>
        </td>
      </tr>
    `;
  }).join('') : '<tr><td colspan="5" class="text-center text-gh-muted py-4">Nenhuma conta investigada neste caso ainda. Adicione abaixo!</td></tr>';

  box.innerHTML = `
    <div class="bg-gh-bg border border-gh-border rounded-lg p-3.5 mb-4 space-y-1.5">
      <div class="flex items-center justify-between flex-wrap gap-2">
        <span class="text-xs text-gh-muted">Referência / Solicitante: <strong class="text-gh-title">${escapeHtml(c.referencia || 'Não informada')}</strong></span>
        <span class="text-xs font-mono text-gh-muted">Criado em: ${escapeHtml(c.criado_em || '-')}</span>
      </div>
      <div class="text-xs text-gh-text leading-relaxed pt-1 border-t border-gh-border/60">${escapeHtml(c.descricao || 'Sem informações adicionais cadastradas.')}</div>
    </div>

    <div class="bg-gh-card/60 border border-gh-border rounded-lg p-3.5 mb-4">
      <label class="label text-gh-title flex items-center gap-1.5 mb-1.5">
        <i data-lucide="user-plus" class="text-gh-blue" style="width:14px;height:14px;"></i>
        <span>Adicionar Contas Investigadas a este Caso:</span>
      </label>
      <div class="flex flex-col md:flex-row gap-2">
        <input type="text" id="input-dossie-novos-alvos" class="input-text flex-1" placeholder="Digite @conta1, @conta2 (separados por vírgula) para investigar neste caso...">
        <button class="btn-secondary" onclick="adicionarAlvosDentroDoDossie(${c.id}, false)">
          <i data-lucide="link"></i>
          <span>Apenas Vincular</span>
        </button>
        <button class="btn-primary" onclick="adicionarAlvosDentroDoDossie(${c.id}, true)">
          <i data-lucide="send"></i>
          <span>Seguir & Monitorar</span>
        </button>
      </div>
    </div>

    <div class="table-container bg-gh-bg border border-gh-border rounded-lg">
      <table class="data-table">
        <thead>
          <tr>
            <th>Conta Investigada</th>
            <th>Bot Responsável</th>
            <th>Status Cascata</th>
            <th>Mídias</th>
            <th>Ações Rápidas</th>
          </tr>
        </thead>
        <tbody>${linhasHtml}</tbody>
      </table>
    </div>
  `;
  renderIcons();
}

async function adicionarAlvosDentroDoDossie(casoId, enviarFollow) {
  const input = document.getElementById('input-dossie-novos-alvos');
  const raw = input ? input.value.trim() : '';
  if (!raw) {
    alert('Informe ao menos um @username.');
    return;
  }
  const lista = raw.split(/[\n,;]+/).map(x => x.replace('@', '').trim()).filter(Boolean);
  if (!lista.length) return;

  if (enviarFollow) {
    const res = await fetch('/api/alvos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ usernames: lista, modo: 'distribuido', caso_id: casoId })
    });
    const data = await res.json();
    if (!data.sucesso) {
      alert(data.erro || 'Erro ao enviar solicitações.');
      return;
    }
    alert(data.mensagem);
  } else {
    for (const u of lista) {
      await fetch('/api/casos/vincular', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: u, caso_id: casoId })
      });
    }
  }

  if (input) input.value = '';
  await abrirDossieCaso(casoId, true);
  loadAlvos();
  loadDownloads();
  refreshStats();
  refreshLogs();
}

function filtrarAbaPorCaso(tabId, casoId) {
  fecharModal('modal-dossie-caso');
  if (tabId === 'tab-alvos') {
    const sel = document.getElementById('select-filtro-caso-alvos');
    if (sel) sel.value = String(casoId);
  } else if (tabId === 'tab-downloads') {
    const sel = document.getElementById('select-filtro-caso-downloads');
    if (sel) sel.value = String(casoId);
  }
  switchTab(tabId);
}

/* ALVOS & CASCATA */
async function importarAlvosTxt() {
  try {
    const res = await fetch('/api/alvos/arquivo_txt');
    const data = await res.json();
    if (data.alvos && data.alvos.length) {
      const textarea = document.getElementById('txt-novos-alvos');
      const atual = textarea.value.trim();
      textarea.value = atual ? atual + '\n' + data.alvos.join('\n') : data.alvos.join('\n');
    } else {
      alert('O arquivo alvos.txt está vazio no momento.');
    }
  } catch (e) {
    alert('Erro ao ler alvos.txt: ' + e);
  }
}

async function loadAlvos() {
  try {
    const res = await fetch('/api/alvos');
    const todosAlvos = await res.json();
    cachedAlvos = Array.isArray(todosAlvos) ? todosAlvos : [];

    const tbody = document.getElementById('alvos-tbody');
    const dashTbody = document.getElementById('dash-alvos-tbody');
    const filtroCasoEl = document.getElementById('select-filtro-caso-alvos');
    const filtroCaso = filtroCasoEl ? filtroCasoEl.value : 'TODOS';

    const alvos = todosAlvos.filter(a => {
      if (!filtroCaso || filtroCaso === 'TODOS') return true;
      if (filtroCaso === 'SEM_CASO') return !a.caso_id;
      return Number(a.caso_id) === Number(filtroCaso);
    });

    if (dashTbody) {
      if (!todosAlvos.length) {
        dashTbody.innerHTML = '<tr><td colspan="4" class="text-center">Nenhum alvo monitorado.</td></tr>';
      } else {
        const recent = todosAlvos.slice(-5).reverse();
        dashTbody.innerHTML = recent.map(a => {
          let bCls = 'badge-yellow';
          if (a.status === 'CONCLUIDO') bCls = 'badge-green';
          if (a.status === 'ESGOTADO' || a.status === 'REJEITADO_COOLDOWN') bCls = 'badge-red';
          const casoTag = a.caso_nome ? `<div class="text-[10px] text-gh-blue font-mono mt-0.5">${escapeHtml(a.caso_nome)}</div>` : '';
          return `
            <tr>
              <td><strong>@${escapeHtml(a.username)}</strong>${casoTag}</td>
              <td>${a.conta_atual ? '@' + escapeHtml(a.conta_atual) : '-'}</td>
              <td><span class="badge ${bCls}">${escapeHtml(a.status)}</span></td>
              <td>${a.atualizado_em ? a.atualizado_em.slice(11, 16) : '-'}</td>
            </tr>
          `;
        }).join('');
      }
    }

    if (!alvos.length) {
      const emptyRow = '<tr><td colspan="7" class="text-center">Nenhum alvo monitorado para este filtro.</td></tr>';
      if (tbody) tbody.innerHTML = emptyRow;
      atualizarContadorSelecao();
      return;
    }

    const rows = alvos.map(a => {
      let badgeClass = 'badge-yellow';
      if (a.status === 'CONCLUIDO') badgeClass = 'badge-green';
      if (a.status === 'ESGOTADO' || a.status === 'REJEITADO_COOLDOWN') badgeClass = 'badge-red';

      const tentativas = a.tentativas || [];
      const histHtml = tentativas.length
        ? `<div class="attempt-list">` + tentativas.map(t => `<span class="attempt-tag" title="${escapeHtml(t.solicitado_em || '')}">@${escapeHtml(t.conta)}: ${escapeHtml(t.status)}</span>`).join('') + `</div>`
        : '<span class="text-muted">Sem tentativas</span>';

      const cooldownInfo = (a.status === 'REJEITADO_COOLDOWN' && a.cooldown_ate)
        ? `<div class="stat-meta" style="color:var(--accent-yellow);">Cooldown até ${a.cooldown_ate.slice(11, 16)}</div>`
        : '';

      return `
        <tr>
          <td><input type="checkbox" class="check-alvo" data-user="${escapeHtml(a.username)}" onchange="atualizarContadorSelecao()"></td>
          <td><strong>@${escapeHtml(a.username)}</strong></td>
          <td>${gerarSelectInlineCaso(a.username, a.caso_id)}</td>
          <td>${a.conta_atual ? '@' + escapeHtml(a.conta_atual) : '<span class="text-muted">Aguardando bot</span>'}</td>
          <td>
            <span class="badge ${badgeClass}">${escapeHtml(a.status || 'AGUARDANDO')}</span>
            ${cooldownInfo}
          </td>
          <td>${histHtml}</td>
          <td>
            <div class="inline-flex items-center gap-1.5 whitespace-nowrap">
              <button type="button" class="btn-secondary-sm" onclick="baixarDireto('${escapeHtml(a.username)}', '${escapeHtml(a.conta_atual || '')}', 6, null, 'go', this)" title="Extrair fotos, stories e conexões agora">
                <i data-lucide="zap" class="text-gh-yellow"></i>
                <span>Extrair</span>
              </button>
              <button type="button" class="btn-secondary-sm" onclick="investigarNoSherlock('${escapeHtml(a.username)}', '${a.caso_id || ''}')" title="Investigar este alvo em 480+ redes sociais (Sherlock OSINT)">
                <i data-lucide="scan-search" class="text-gh-blue"></i>
                <span>Sherlock</span>
              </button>
              <button type="button" class="btn-secondary-sm" onclick="baixarZipAlvoSeguro('${escapeHtml(a.username)}')" title="Baixar pacote ZIP">
                <i data-lucide="archive"></i>
                <span>ZIP</span>
              </button>
              <button type="button" class="btn-secondary-sm" onclick="removerAlvo('${escapeHtml(a.username)}')" title="Excluir alvo" style="color:var(--danger);">
                <i data-lucide="trash-2"></i>
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    if (tbody) tbody.innerHTML = rows;

    const selSherlockAlvos = document.getElementById('sherlock-select-atalho-alvos');
    if (selSherlockAlvos) {
      const valAtual = selSherlockAlvos.value;
      const opts = ['<option value="">Puxar dos Alvos...</option>']
        .concat(todosAlvos.map(a => `<option value="${escapeHtml(a.username)}">@${escapeHtml(a.username)}</option>`))
        .join('');
      selSherlockAlvos.innerHTML = opts;
      if (valAtual) selSherlockAlvos.value = valAtual;
    }

    atualizarContadorSelecao();
    renderIcons();
  } catch (err) {
    console.error('Erro ao carregar alvos:', err);
  }
}

function atualizarContadorSelecao() {
  const selecionados = document.querySelectorAll('.check-alvo:checked');
  const countSpan = document.getElementById('alvos-selection-count');
  if (countSpan) countSpan.innerText = `${selecionados.length} selecionado(s)`;
}

function toggleSelectAllAlvos() {
  const master = document.getElementById('check-all-alvos');
  const checkboxes = document.querySelectorAll('.check-alvo');
  checkboxes.forEach(cb => cb.checked = master.checked);
  atualizarContadorSelecao();
}

async function removerAlvosSelecionados() {
  const selecionados = Array.from(document.querySelectorAll('.check-alvo:checked')).map(cb => cb.getAttribute('data-user'));
  if (!selecionados.length) {
    alert('Nenhum alvo marcado para exclusão.');
    return;
  }

  if (confirm(`Deseja remover os ${selecionados.length} alvos selecionados?`)) {
    try {
      const res = await fetch('/api/alvos/remover_selecionados', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usernames: selecionados })
      });
      const data = await res.json();
      if (!data.sucesso) {
        alert('Erro: ' + (data.erro || 'Falha ao remover alvos.'));
      }
    } catch (e) {
      alert('Erro de conexão ao remover alvos selecionados: ' + e);
    }
    const master = document.getElementById('check-all-alvos');
    if (master) master.checked = false;
    loadAlvos();
    refreshStats();
    refreshLogs();
  }
}

async function limparTodosAlvos() {
  if (confirm('Tem certeza que deseja apagar TODOS os alvos da lista de monitoramento?')) {
    try {
      const res = await fetch('/api/alvos/limpar_todos', { method: 'POST' });
      const data = await res.json();
      if (!data.sucesso) {
        alert('Erro: ' + (data.erro || 'Falha ao limpar alvos.'));
      }
    } catch (e) {
      alert('Erro de conexão ao limpar todos os alvos: ' + e);
    }
    const master = document.getElementById('check-all-alvos');
    if (master) master.checked = false;
    loadAlvos();
    refreshStats();
    refreshLogs();
  }
}

async function removerAlvo(username) {
  if (confirm(`Deseja remover @${username} do monitoramento?`)) {
    try {
      const res = await fetch(`/api/alvos/${username}`, { method: 'DELETE' });
      const data = await res.json();
      if (!data.sucesso) {
        alert('Erro: ' + (data.erro || 'Falha ao remover alvo.'));
      }
    } catch (e) {
      alert('Erro de conexão ao remover alvo: ' + e);
    }
    loadAlvos();
    refreshStats();
    refreshLogs();
  }
}

async function salvarNovosAlvos() {
  const textarea = document.getElementById('txt-novos-alvos');
  const text = textarea.value.trim();
  if (!text) {
    alert('Digite ao menos um @alvo (um por linha).');
    return;
  }

  const modo = document.getElementById('select-modo-abordagem').value;
  const contaUser = document.getElementById('select-conta-alvo').value;
  const casoEl = document.getElementById('select-caso-novo-alvo');
  const casoId = casoEl ? casoEl.value : '';

  if (modo === 'especifico' && !contaUser) {
    alert('Selecione uma conta ativa do Pool para direcionar o envio.');
    return;
  }

  const res = await fetch('/api/alvos', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      usernames: text,
      modo: modo,
      conta_user: contaUser,
      caso_id: casoId || null
    })
  });
  const data = await res.json();
  if (data.sucesso) {
    alert(data.mensagem || `${data.total_adicionados} alvo(s) na fila de disparo!`);
    textarea.value = '';
  } else {
    alert(data.erro || 'Falha ao adicionar alvo.');
  }
  loadCasos();
  loadAlvos();
  refreshStats();
  refreshLogs();
}

/* AÇÕES E EXTRAÇÃO */
async function dispararVerificacao(btnEl) {
  await executarBotaoComFeedback(btnEl, 'btn-quick-check', async () => {
    const res = await fetch('/api/acoes/verificar_cascata', { method: 'POST' });
    const data = await res.json();
    if (!data.sucesso && data.erro) {
      alert(data.erro);
    }
    await Promise.all([refreshStats(), refreshLogs()]);
  }, 'Verificando...', 'Disparado!');
}

async function confirmarScrapeDireto() {
  const input = document.getElementById('input-direct-target');
  const target = input.value.trim();
  if (!target) {
    alert('Digite o username do alvo.');
    return;
  }
  const contaUser = document.getElementById('select-conta-scrape').value;
  const maxScrolls = parseInt(document.getElementById('input-scrape-scrolls').value, 10) || 6;
  const casoEl = document.getElementById('select-caso-scrape');
  const casoId = casoEl ? casoEl.value : '';
  const engineEl = document.getElementById('select-scrape-engine');
  const engine = engineEl ? engineEl.value : 'go';

  fecharModal('modal-scrape');
  baixarDireto(target, contaUser, maxScrolls, casoId, engine);
  input.value = '';
}

async function baixarDireto(username, contaUser = '', maxScrolls = 6, casoId = null, engine = 'go', btnEl = null) {
  const btn = (btnEl && btnEl.closest) ? (btnEl.closest('button') || btnEl) : btnEl;
  if (btn && btn.dataset.busy === '1') return;

  if (btn) {
    if (!btn.dataset.origHtml) btn.dataset.origHtml = btn.innerHTML;
    btn.dataset.busy = '1';
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader-2" class="animate-spin"></i><span>Iniciando...</span>';
    renderIcons(btn);
  }

  try {
    const res = await fetch('/api/acoes/baixar_direto', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: username,
        conta_user: contaUser,
        max_scrolls: maxScrolls,
        caso_id: casoId || null,
        engine: engine
      })
    });
    const data = await res.json();
    if (!data.sucesso) {
      alert('Aviso: ' + (data.erro || 'Não foi possível iniciar a extração.'));
    } else if (btn) {
      btn.innerHTML = '<i data-lucide="check" class="text-gh-green"></i><span class="text-gh-green">Em fila!</span>';
      renderIcons(btn);
    }
  } catch (err) {
    alert('Erro de conexão ao solicitar extração: ' + err);
  } finally {
    if (btn) {
      setTimeout(() => {
        btn.disabled = false;
        btn.dataset.busy = '0';
        btn.innerHTML = btn.dataset.origHtml;
        renderIcons(btn);
      }, 1200);
    }
    loadCasos();
    refreshStats();
    refreshLogs();
  }
}

async function baixarZipAlvoSeguro(username) {
  const clean = String(username || '').replace('@', '').trim();
  if (!clean) return;
  if (cachedDownloadsSet.has(clean.toLowerCase())) {
    window.location.href = `/api/downloads/${encodeURIComponent(clean)}/zip`;
    return;
  }
  try {
    const res = await fetch(`/api/downloads/${encodeURIComponent(clean)}/detalhes`);
    if (res.ok) {
      window.location.href = `/api/downloads/${encodeURIComponent(clean)}/zip`;
    } else {
      alert(`Ainda não há mídias extraídas para @${clean}.\nSe o perfil for privado, aguarde o aceite da solicitação ou clique em "Extrair" quando estiver liberado.`);
    }
  } catch (err) {
    alert('Erro ao verificar pacote ZIP do alvo.');
  }
}
window.baixarZipAlvoSeguro = baixarZipAlvoSeguro;

async function toggleSentinela() {
  const dot = document.getElementById('sentinela-dot');
  if (dot.classList.contains('active')) {
    await fetch('/api/acoes/sentinela/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intervalo: 30 })
    });
    refreshStats();
    refreshLogs();
  } else {
    abrirModal('modal-sentinela');
  }
}

async function confirmarInicioSentinela() {
  const val = document.getElementById('input-sentinela-intervalo').value.trim();
  const minutos = parseInt(val, 10) || 30;
  fecharModal('modal-sentinela');

  await fetch('/api/acoes/sentinela/toggle', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ intervalo: minutos })
  });
  refreshStats();
  refreshLogs();
}

/* DOWNLOADS & RELATÓRIO DE PERFIL */
async function loadDownloads() {
  try {
    const res = await fetch('/api/downloads');
    const todosPerfis = await res.json();
    cachedDownloadsSet = new Set((todosPerfis || []).map(p => String(p.username || '').toLowerCase()));
    const grid = document.getElementById('downloads-grid');
    const filtroEl = document.getElementById('select-filtro-caso-downloads');
    const filtroCaso = filtroEl ? filtroEl.value : 'TODOS';

    const perfis = todosPerfis.filter(p => {
      if (!filtroCaso || filtroCaso === 'TODOS') return true;
      if (filtroCaso === 'SEM_CASO') return !p.caso_id;
      return Number(p.caso_id) === Number(filtroCaso);
    });

    if (!perfis.length) {
      grid.innerHTML = `
        <div class="col-span-full bg-gh-bg border border-gh-border rounded-xl p-8 text-center space-y-2" style="grid-column: 1/-1;">
          <div class="w-11 h-11 rounded-full bg-gh-blue/10 border border-gh-blue/30 flex items-center justify-center text-gh-blue mx-auto">
            <i data-lucide="folder-down" style="width:20px;height:20px;"></i>
          </div>
          <div class="text-sm font-semibold text-gh-title">Nenhum perfil extraído para este filtro</div>
          <p class="text-xs text-gh-muted">Use o botão "Baixar Perfil Agora" no topo para extrair fotos, stories, destaques e conexões completas.</p>
        </div>
      `;
      renderIcons();
      return;
    }

    grid.innerHTML = perfis.map(p => {
      const d = p.dados || {};
      const c = d.contadores || {};
      const conex = d.conexoes || {};
      const segExtr = (conex.seguidores || {}).total_extraido || 0;
      const segndoExtr = (conex.seguindo || {}).total_extraido || 0;
      const mutuos = (conex.resumo_relacionamento || {}).total_mutuo || 0;
      const fotosFeed = d.total_fotos_feed || 0;
      const destaques = d.total_destaques_baixados || 0;
      const stories = d.total_stories_baixados || 0;

      const rawPosts = (c.posts && c.posts !== 'N/A') ? c.posts : `${fotosFeed} ${fotosFeed === 1 ? 'post' : 'posts'}`;
      const rawSeg = (c.seguidores && c.seguidores !== 'N/A') ? c.seguidores : `${segExtr} seguidores`;

      const engRaw = String(d.engine_utilizada || '');
      const isGoEng = engRaw.includes('GO');
      const engLabel = engRaw === 'HYBRID_GO_PLAYWRIGHT' ? 'Híbrido Go+Web' : (isGoEng ? 'Go Turbo REST' : 'Playwright');

      const avatarHtml = p.avatar_url
        ? `<img src="${encodeURI(p.avatar_url)}" alt="@${escapeHtml(p.username)}" class="w-11 h-11 rounded-full object-cover border-2 border-gh-green/70 shrink-0 cursor-pointer" onclick="verDetalhesPerfil('${escapeHtml(p.username)}')" title="Clique para abrir galeria de @${escapeHtml(p.username)}">`
        : `<div class="w-11 h-11 rounded-full bg-gh-blue/15 border-2 border-gh-blue/40 flex items-center justify-center text-gh-blue shrink-0 cursor-pointer" onclick="verDetalhesPerfil('${escapeHtml(p.username)}')"><i data-lucide="user" style="width:18px;height:18px;"></i></div>`;

      return `
        <div class="download-card-modern bg-gh-card border border-gh-border rounded-xl p-4 flex flex-col justify-between gap-3.5 hover:border-gh-blue/50 transition shadow-sm">
          <div class="space-y-3">
            <!-- Cabeçalho com Avatar Real e Contadores -->
            <div class="flex items-start justify-between gap-2 border-b border-gh-border pb-3">
              <div class="flex items-center gap-3 min-w-0">
                ${avatarHtml}
                <div class="min-w-0">
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <strong class="text-base font-bold text-gh-title truncate cursor-pointer hover:text-gh-blue transition" onclick="verDetalhesPerfil('${escapeHtml(p.username)}')">@${escapeHtml(p.username)}</strong>
                    <span class="badge ${isGoEng ? 'badge-blue' : 'badge-gray'} text-[10.5px] py-0 px-1.5">${escapeHtml(engLabel)}</span>
                  </div>
                  <div class="text-xs text-gh-muted mt-0.5 truncate">${escapeHtml(rawPosts)} • ${escapeHtml(rawSeg)}</div>
                  ${p.extraido_em ? `<div class="text-[11px] font-mono text-gh-muted mt-0.5 flex items-center gap-1"><i data-lucide="calendar-clock" style="width:11px;height:11px;"></i><span>${escapeHtml(p.extraido_em)}</span></div>` : ''}
                </div>
              </div>
              <button class="btn-secondary-sm shrink-0" onclick="removerDownload('${escapeHtml(p.username)}')" title="Excluir pasta de mídias deste perfil" style="color:var(--danger);">
                <i data-lucide="trash-2"></i>
              </button>
            </div>

            <!-- Seletor de Vínculo com Caso -->
            <div class="flex items-center justify-between gap-2 bg-gh-bg/70 border border-gh-border/80 rounded-lg px-3 py-1.5">
              <span class="text-xs text-gh-muted flex items-center gap-1.5 font-medium"><i data-lucide="briefcase" class="text-gh-blue" style="width:12px;height:12px;"></i>Caso / Dossiê:</span>
              ${gerarSelectInlineCaso(p.username, p.caso_id)}
            </div>

            <!-- Contadores de Mídias Visuais -->
            <div class="grid grid-cols-3 gap-2 text-xs">
              <div class="bg-gh-bg border border-gh-border rounded-lg px-2.5 py-2 text-center">
                <span class="text-gh-muted flex items-center justify-center gap-1 text-[11px]"><i data-lucide="image" class="text-gh-blue" style="width:11.5px;height:11.5px;"></i>Feed</span>
                <strong class="text-gh-title font-mono text-sm block mt-0.5">${fotosFeed}</strong>
              </div>
              <div class="bg-gh-bg border border-gh-border rounded-lg px-2.5 py-2 text-center">
                <span class="text-gh-muted flex items-center justify-center gap-1 text-[11px]"><i data-lucide="sparkles" class="text-gh-yellow" style="width:11.5px;height:11.5px;"></i>Destaques</span>
                <strong class="text-gh-title font-mono text-sm block mt-0.5">${destaques}</strong>
              </div>
              <div class="bg-gh-bg border border-gh-border rounded-lg px-2.5 py-2 text-center">
                <span class="text-gh-muted flex items-center justify-center gap-1 text-[11px]"><i data-lucide="flame" class="text-gh-green" style="width:11.5px;height:11.5px;"></i>Stories</span>
                <strong class="text-gh-title font-mono text-sm block mt-0.5">${stories}</strong>
              </div>
            </div>

            <!-- Painel de Conexões & Mútuos -->
            <div class="text-xs text-gh-muted space-y-1.5 bg-gh-bg border border-gh-border rounded-lg p-3">
              <div class="flex items-center justify-between">
                <span class="flex items-center gap-1.5"><i data-lucide="users" class="text-gh-blue" style="width:13px;height:13px;"></i>Conexões Extraídas:</span>
                <span class="text-gh-title font-mono font-semibold">${segExtr} seg. | ${segndoExtr} segndo</span>
              </div>
              <div class="flex items-center justify-between">
                <span class="flex items-center gap-1.5"><i data-lucide="repeat" class="text-gh-green" style="width:13px;height:13px;"></i>Amigos Mútuos:</span>
                <span class="badge badge-green font-mono text-[11px] py-0 px-2">${mutuos} em comum</span>
              </div>
              <div class="flex items-center justify-between pt-1 border-t border-gh-border/60">
                <span class="flex items-center gap-1.5"><i data-lucide="hard-drive" style="width:13px;height:13px;"></i>Total na Pasta:</span>
                <span class="text-gh-text font-mono">${p.total_arquivos} arquivo(s)</span>
              </div>
            </div>
          </div>

          <!-- Barra de Ações do Card -->
          <div class="flex items-center justify-between gap-1.5 pt-2 border-t border-gh-border">
            <div class="flex items-center gap-1.5 flex-wrap">
              <button class="btn-secondary-sm" onclick="verDetalhesPerfil('${escapeHtml(p.username)}')" title="Abrir Galeria Visual, Biografia e Listas">
                <i data-lucide="layout-grid" class="text-gh-blue"></i>
                <span>Galeria & Bio</span>
              </button>
              <a href="/api/downloads/${encodeURIComponent(p.username)}/csv" class="btn-secondary-sm" style="text-decoration:none;" title="Exportar conexões em planilha CSV para Excel">
                <i data-lucide="file-spreadsheet" class="text-gh-green"></i>
                <span>CSV</span>
              </a>
              <button class="btn-secondary-sm" onclick="investigarNoSherlock('${escapeHtml(p.username)}', '${p.caso_id || ''}')" title="Investigar este @username em 480+ redes sociais">
                <i data-lucide="scan-search" class="text-gh-blue"></i>
              </button>
            </div>
            <a href="/api/downloads/${encodeURIComponent(p.username)}/zip" class="btn-primary-sm" style="text-decoration:none;" title="Baixar pacote completo .ZIP">
              <i data-lucide="download"></i>
              <span>ZIP</span>
            </a>
          </div>
        </div>
      `;
    }).join('');
    renderIcons();
  } catch (err) {
    console.error('Erro ao carregar downloads:', err);
  }
}

async function verDetalhesPerfil(username) {
  abrirModal('modal-detalhes-perfil');
  document.getElementById('detalhes-perfil-titulo').innerHTML = `<i data-lucide="file-text" class="text-gh-blue"></i><span>Relatório & Galeria: @${escapeHtml(username)}</span>`;
  const box = document.getElementById('detalhes-perfil-conteudo');
  const exportLinks = document.getElementById('detalhes-perfil-export-links');
  box.innerHTML = '<p class="text-muted">Carregando dados e mídias extraídas...</p>';
  if (exportLinks) exportLinks.innerHTML = '';
  renderIcons();

  try {
    const res = await fetch(`/api/downloads/${encodeURIComponent(username)}/detalhes`);
    const data = await res.json();
    if (!data.sucesso) {
      box.innerHTML = `<p style="color:var(--danger);">${escapeHtml(data.erro || 'Erro ao abrir relatório.')}</p>`;
      return;
    }

    if (exportLinks) {
      exportLinks.innerHTML = `
        <a href="/api/downloads/${encodeURIComponent(username)}/csv" class="btn-secondary" style="text-decoration:none;">
          <i data-lucide="file-spreadsheet" class="text-gh-green"></i>
          <span>Baixar Conexões (.CSV Excel)</span>
        </a>
        <a href="/api/downloads/${encodeURIComponent(username)}/zip" class="btn-primary" style="text-decoration:none;">
          <i data-lucide="download"></i>
          <span>Baixar Pacote Completo (.ZIP)</span>
        </a>
      `;
    }

    const d = data.dados || {};
    const conex = d.conexoes || {};
    const mutuos = (conex.resumo_relacionamento || {}).seguem_de_volta_mutuo || [];
    const seguidores = (conex.seguidores || {}).contas || [];
    const seguindo = (conex.seguindo || {}).contas || [];
    const m = data.midias || { feed: [], destaques: [], stories: [] };

    const renderMediaGrid = (items) => {
      if (!items || !items.length) return '<p class="stat-meta" style="margin-bottom:12px;">Nenhum arquivo nesta categoria.</p>';
      return `<div class="media-preview-grid">` + items.map(item => `
        <a href="${encodeURI(item.url)}" target="_blank" class="media-thumb-card" title="Abrir ${escapeHtml(item.nome)} em tamanho original">
          ${item.video
            ? `<video src="${encodeURI(item.url)}" muted preload="metadata"></video>`
            : `<img src="${encodeURI(item.url)}" loading="lazy" alt="${escapeHtml(item.nome)}">`
          }
          <div class="media-thumb-label flex items-center gap-1">
            <i data-lucide="${item.video ? 'film' : 'camera'}" style="width:10px;height:10px;"></i>
            <span class="truncate">${escapeHtml(item.nome)}</span>
          </div>
        </a>
      `).join('') + `</div>`;
    };

    const totalMidiasVisuais = (m.feed || []).length + (m.destaques || []).length + (m.stories || []).length;

    box.innerHTML = `
      <div class="modal-subtabs">
        <button class="log-filter-btn active" id="subtab-btn-relatorio" onclick="alternarSubtabModal('relatorio')">
          <i data-lucide="align-left"></i>
          <span>Biografia & Conexões</span>
        </button>
        <button class="log-filter-btn" id="subtab-btn-galeria" onclick="alternarSubtabModal('galeria')">
          <i data-lucide="layout-grid"></i>
          <span>Galeria Visual (${totalMidiasVisuais})</span>
        </button>
      </div>

      <div id="subtab-pane-relatorio">
        <div style="display:flex; gap:12px; align-items:flex-start; margin-bottom:12px;">
          ${m.avatar ? `<a href="${encodeURI(m.avatar)}" target="_blank"><img src="${encodeURI(m.avatar)}" style="width:68px; height:68px; border-radius:50%; object-fit:cover; border:2px solid var(--border-color);" title="Ver Avatar HD"></a>` : ''}
          <div style="flex:1;">
            <label class="label">Biografia e Contadores (bio.txt):</label>
            <div class="terminal-box" style="height:130px;">${escapeHtml(data.bio_txt || 'Sem bio.txt')}</div>
          </div>
        </div>

        <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:10px;">
          <div>
            <label class="label flex items-center gap-1.5"><i data-lucide="repeat" class="text-gh-green" style="width:12px;height:12px;"></i><span>Mútuos (${mutuos.length}):</span></label>
            <div class="terminal-box" style="height:170px;">${mutuos.map(u => '@' + escapeHtml(u)).join('\n') || 'Nenhum'}</div>
          </div>
          <div>
            <label class="label flex items-center gap-1.5"><i data-lucide="users" class="text-gh-blue" style="width:12px;height:12px;"></i><span>Seguidores (${seguidores.length}):</span></label>
            <div class="terminal-box" style="height:170px;">${seguidores.map(u => '@' + escapeHtml(u)).join('\n') || 'Nenhum'}</div>
          </div>
          <div>
            <label class="label flex items-center gap-1.5"><i data-lucide="user-plus" class="text-gh-muted" style="width:12px;height:12px;"></i><span>Seguindo (${seguindo.length}):</span></label>
            <div class="terminal-box" style="height:170px;">${seguindo.map(u => '@' + escapeHtml(u)).join('\n') || 'Nenhum'}</div>
          </div>
        </div>
      </div>

      <div id="subtab-pane-galeria" style="display:none;">
        <p class="stat-meta" style="margin-bottom:8px;">Clique em qualquer miniatura para abrir a foto ou vídeo em resolução original.</p>
        <label class="label flex items-center gap-1.5"><i data-lucide="image" class="text-gh-blue" style="width:13px;height:13px;"></i><span>Fotos do Feed (${(m.feed || []).length}):</span></label>
        ${renderMediaGrid(m.feed)}

        <label class="label flex items-center gap-1.5"><i data-lucide="clock" class="text-gh-yellow" style="width:13px;height:13px;"></i><span>Stories 24h (${(m.stories || []).length}):</span></label>
        ${renderMediaGrid(m.stories)}

        <label class="label flex items-center gap-1.5"><i data-lucide="sparkles" class="text-gh-green" style="width:13px;height:13px;"></i><span>Destaques / Highlights (${(m.destaques || []).length}):</span></label>
        ${renderMediaGrid(m.destaques)}
      </div>
    `;
    renderIcons();
  } catch (e) {
    box.innerHTML = `<p style="color:var(--danger);">Erro ao carregar detalhes: ${escapeHtml(e)}</p>`;
  }
}

function alternarSubtabModal(aba) {
  const pRel = document.getElementById('subtab-pane-relatorio');
  const pGal = document.getElementById('subtab-pane-galeria');
  const bRel = document.getElementById('subtab-btn-relatorio');
  const bGal = document.getElementById('subtab-btn-galeria');
  if (!pRel || !pGal) return;
  if (aba === 'galeria') {
    pRel.style.display = 'none';
    pGal.style.display = 'block';
    bRel.classList.remove('active');
    bGal.classList.add('active');
  } else {
    pRel.style.display = 'block';
    pGal.style.display = 'none';
    bRel.classList.add('active');
    bGal.classList.remove('active');
  }
}

async function removerDownload(username) {
  if (confirm(`Deseja excluir permanentemente todas as fotos, stories e relatórios de @${username}?`)) {
    try {
      const res = await fetch(`/api/downloads/${encodeURIComponent(username)}`, { method: 'DELETE' });
      const data = await res.json();
      if (!data.sucesso) {
        alert('Erro: ' + (data.erro || 'Falha ao remover mídias.'));
      }
    } catch (e) {
      alert('Erro de conexão ao remover download: ' + e);
    }
    loadDownloads();
    refreshStats();
    refreshLogs();
  }
}

async function limparTodasMidias() {
  if (confirm('Tem certeza que deseja apagar TODAS as pastas e fotos salvas em downloads/?')) {
    try {
      const res = await fetch('/api/downloads/limpar_todas', { method: 'POST' });
      const data = await res.json();
      if (!data.sucesso) {
        alert('Erro: ' + (data.erro || 'Falha ao limpar mídias.'));
      }
    } catch (e) {
      alert('Erro de conexão ao limpar mídias: ' + e);
    }
    loadDownloads();
    refreshStats();
    refreshLogs();
  }
}

/* CONFIGURAÇÕES DINÂMICAS DE TEMPO */
function formatarMinutosHumano(min) {
  const m = parseInt(min, 10) || 0;
  if (m < 60) return `${m} minuto(s)`;
  const horas = m / 60;
  if (m % 1440 === 0) {
    const dias = m / 1440;
    return `${dias} dia(s) (${horas} horas)`;
  }
  if (m >= 1440) {
    const dias = (m / 1440).toFixed(1);
    return `${horas.toFixed(1)} horas (~${dias} dias)`;
  }
  return m % 60 === 0 ? `${horas} hora(s)` : `${Math.floor(horas)}h ${m % 60}m`;
}

function atualizarLegendasTempo() {
  const vacuoEl = document.getElementById('cfg-timeout-vacuo');
  const coolEl = document.getElementById('cfg-cooldown');
  const lblVacuo = document.getElementById('lbl-vacuo-humano');
  const lblCool = document.getElementById('lbl-cooldown-humano');
  if (vacuoEl && lblVacuo) {
    lblVacuo.innerText = `Equivale a: ${formatarMinutosHumano(vacuoEl.value)}`;
  }
  if (coolEl && lblCool) {
    lblCool.innerText = `Equivale a: ${formatarMinutosHumano(coolEl.value)}`;
  }
}

async function loadConfiguracoes() {
  try {
    const res = await fetch('/api/configuracoes');
    const cfg = await res.json();
    if (document.getElementById('cfg-timeout-vacuo')) {
      document.getElementById('cfg-timeout-vacuo').value = cfg.timeout_vacuo_minutos || 2880;
      document.getElementById('cfg-cooldown').value = cfg.cooldown_minutos || 120;
      document.getElementById('cfg-delay-min').value = cfg.delay_min_segs || 5;
      document.getElementById('cfg-delay-max').value = cfg.delay_max_segs || 10;
      document.getElementById('cfg-max-scrolls').value = cfg.max_scrolls_padrao || 6;
      const modalScrolls = document.getElementById('input-scrape-scrolls');
      if (modalScrolls) modalScrolls.value = cfg.max_scrolls_padrao || 6;
      atualizarLegendasTempo();
    }
  } catch (err) {
    console.error('Erro ao carregar configurações:', err);
  }
}

function aplicarPresetConfig(tipo) {
  if (tipo === 'teste') {
    document.getElementById('cfg-timeout-vacuo').value = 3;
    document.getElementById('cfg-cooldown').value = 3;
    document.getElementById('cfg-delay-min').value = 4;
    document.getElementById('cfg-delay-max').value = 7;
  } else {
    document.getElementById('cfg-timeout-vacuo').value = 2880;
    document.getElementById('cfg-cooldown').value = 120;
    document.getElementById('cfg-delay-min').value = 6;
    document.getElementById('cfg-delay-max').value = 12;
  }
  atualizarLegendasTempo();
  salvarConfiguracoes();
}

async function salvarConfiguracoes() {
  const payload = {
    timeout_vacuo_minutos: parseInt(document.getElementById('cfg-timeout-vacuo').value, 10) || 2880,
    cooldown_minutos: parseInt(document.getElementById('cfg-cooldown').value, 10) || 120,
    delay_min_segs: parseInt(document.getElementById('cfg-delay-min').value, 10) || 5,
    delay_max_segs: parseInt(document.getElementById('cfg-delay-max').value, 10) || 10,
    max_scrolls_padrao: parseInt(document.getElementById('cfg-max-scrolls').value, 10) || 6
  };

  try {
    const res = await fetch('/api/configuracoes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.sucesso) {
      alert('Configurações salvas no banco SQLite e aplicadas imediatamente!');
      loadConfiguracoes();
      refreshLogs();
    }
  } catch (e) {
    alert('Erro ao salvar configurações: ' + e);
  }
}

/* CENTRAL DE TREINAMENTO & MANUAL INTERATIVO */
function alternarSecaoManual(secao, btnEl) {
  if (btnEl && btnEl.parentElement) {
    btnEl.parentElement.querySelectorAll('.filter-chip').forEach(b => b.classList.remove('active'));
    btnEl.classList.add('active');
  }
  const ids = ['trilha', 'casos', 'golang', 'sherlock', 'status', 'faq'];
  ids.forEach(id => {
    const el = document.getElementById(`manual-sec-${id}`);
    if (el) {
      el.style.display = id === secao ? 'block' : 'none';
    }
  });
  renderIcons();
}

function toggleFaqItem(btnEl) {
  const content = btnEl.nextElementSibling;
  if (!content) return;
  const isOpen = content.style.display !== 'none';
  content.style.display = isOpen ? 'none' : 'block';
}

/* HISTÓRICO DE ATUALIZAÇÕES (CHANGELOG TÉCNICO) */
function atualizarContadoresChangelog() {
  const list = document.getElementById('changelog-list');
  if (!list) return;
  const added = list.querySelectorAll('.changelog-item[data-chg="ACRESCENTADO"]').length;
  const fixed = list.querySelectorAll('.changelog-item[data-chg="ARRUMADO"]').length;
  const changed = list.querySelectorAll('.changelog-item[data-chg="ALTERADO"]').length;
  const removed = list.querySelectorAll('.changelog-item[data-chg="REMOVIDO"]').length;

  const elAdded = document.getElementById('chg-count-added');
  const elFixed = document.getElementById('chg-count-fixed');
  const elOther = document.getElementById('chg-count-other');
  if (elAdded) elAdded.innerText = added;
  if (elFixed) elFixed.innerText = fixed;
  if (elOther) elOther.innerText = changed + removed;
}

function filtrarChangelog(tipo, btnEl) {
  currentChangelogCategory = tipo;
  if (btnEl && btnEl.parentElement) {
    btnEl.parentElement.querySelectorAll('.filter-chip').forEach(b => b.classList.remove('active'));
    btnEl.classList.add('active');
  }
  aplicarFiltrosChangelog();
}

function aplicarFiltrosChangelog() {
  const searchInput = document.getElementById('input-search-changelog');
  const termo = searchInput ? searchInput.value.trim().toLowerCase() : '';

  const cards = document.querySelectorAll('.changelog-version-card');
  cards.forEach(card => {
    const items = card.querySelectorAll('.changelog-item');
    let visiveis = 0;
    items.forEach(item => {
      const cat = item.getAttribute('data-chg');
      const textoItem = (item.innerText || '').toLowerCase();
      const matchCat = currentChangelogCategory === 'TODOS' || cat === currentChangelogCategory;
      const matchBusca = !termo || textoItem.includes(termo);

      if (matchCat && matchBusca) {
        item.style.display = 'flex';
        visiveis++;
      } else {
        item.style.display = 'none';
      }
    });
    card.style.display = visiveis > 0 ? 'block' : 'none';
  });
}

/* UTILITÁRIOS */
function abrirModal(id) {
  document.getElementById(id).classList.add('active');
}

function fecharModal(id) {
  if (id === 'modal-dossie-caso') {
    activeDossieCasoId = null;
  }
  document.getElementById(id).classList.remove('active');
}

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/* ==============================================================================
   MÓDULO SHERLOCK OSINT (INVESTIGAÇÃO MULTI-REDES E PLATAFORMAS)
   ============================================================================== */

let activeSherlockScanId = null;
let sherlockPollingInterval = null;
let activeSherlockResults = [];

function selecionarAlvoAtalhoSherlock(val) {
  if (!val) return;
  const input = document.getElementById('sherlock-input-username');
  if (input) input.value = val.replace('@', '').trim();
  const alvoObj = cachedAlvos.find(a => a.username.toLowerCase() === val.toLowerCase());
  if (alvoObj && alvoObj.caso_id) {
    const selCaso = document.getElementById('sherlock-select-caso');
    if (selCaso) selCaso.value = alvoObj.caso_id;
  }
}

function investigarNoSherlock(username, casoId = '') {
  switchTab('tab-sherlock');
  const input = document.getElementById('sherlock-input-username');
  if (input) input.value = username.replace('@', '').trim();
  if (casoId) {
    const selCaso = document.getElementById('sherlock-select-caso');
    if (selCaso) selCaso.value = casoId;
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
  setTimeout(() => {
    iniciarVarreduraSherlock();
  }, 250);
}

async function iniciarVarreduraSherlock() {
  const inputUser = document.getElementById('sherlock-input-username');
  const username = inputUser ? inputUser.value.trim().replace('@', '') : '';
  if (!username) {
    alert('Por favor, informe o @username que deseja investigar.');
    if (inputUser) inputUser.focus();
    return;
  }

  const modo = document.getElementById('sherlock-select-modo').value;
  const selCaso = document.getElementById('sherlock-select-caso');
  const casoId = selCaso ? selCaso.value : null;
  const incluirNsfw = document.getElementById('sherlock-chk-nsfw').checked;

  const btnIniciar = document.getElementById('btn-iniciar-sherlock');
  const btnCancelar = document.getElementById('btn-cancelar-sherlock');
  const boxProgresso = document.getElementById('sherlock-box-progresso');
  const boxResultados = document.getElementById('sherlock-box-resultados');

  if (btnIniciar) btnIniciar.disabled = true;
  if (btnCancelar) btnCancelar.style.display = 'inline-flex';
  if (boxProgresso) boxProgresso.style.display = 'block';
  if (boxResultados) boxResultados.style.display = 'none';

  document.getElementById('sherlock-lbl-alvo').innerText = `@${username}`;
  const lblTitulo = document.getElementById('sherlock-lbl-titulo-progresso');
  if (lblTitulo) lblTitulo.innerText = 'Sondando Redes Sociais para:';
  const iconBox = document.getElementById('sherlock-progresso-icon-box');
  if (iconBox) {
    iconBox.className = 'w-9 h-9 rounded-full bg-gh-blue/15 border border-gh-blue/40 flex items-center justify-center text-gh-blue';
    iconBox.innerHTML = '<i data-lucide="loader-2" class="animate-spin" style="width:17px;height:17px;"></i>';
  }
  document.getElementById('sherlock-lbl-status').innerText = 'Disparando sondas simultâneas em segundo plano...';
  const badgeProg = document.getElementById('sherlock-badge-progresso');
  if (badgeProg) {
    badgeProg.className = 'badge badge-blue font-mono';
    badgeProg.innerText = '0%';
  }
  const progFill = document.getElementById('sherlock-prog-bar-fill');
  if (progFill) {
    progFill.className = 'bg-gh-blue h-full transition-all duration-300';
    progFill.style.width = '0%';
  }
  document.getElementById('sherlock-kpi-processados').innerText = '0 / 0';
  document.getElementById('sherlock-kpi-encontrados').innerText = '0';
  document.getElementById('sherlock-kpi-tempo').innerText = '0.0s';

  renderIcons();

  try {
    const res = await fetch('/api/sherlock/iniciar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: username,
        modo: modo,
        incluir_nsfw: incluirNsfw,
        caso_id: casoId
      })
    });
    const data = await res.json();
    if (!data.sucesso) {
      alert(data.erro || 'Erro ao iniciar varredura.');
      if (btnIniciar) btnIniciar.disabled = false;
      if (btnCancelar) btnCancelar.style.display = 'none';
      if (boxProgresso) boxProgresso.style.display = 'none';
      return;
    }

    activeSherlockScanId = data.scan_id;

    if (sherlockPollingInterval) clearInterval(sherlockPollingInterval);
    sherlockPollingInterval = setInterval(() => checarStatusSherlock(activeSherlockScanId), 700);
  } catch (err) {
    console.error('Erro na requisição do Sherlock:', err);
    if (btnIniciar) btnIniciar.disabled = false;
    if (btnCancelar) btnCancelar.style.display = 'none';
  }
}

async function checarStatusSherlock(scanId) {
  try {
    const res = await fetch(`/api/sherlock/status/${scanId}`);
    const data = await res.json();
    if (!data.sucesso || !data.scan) return;

    const s = data.scan;
    const total = s.total || 1;
    const processados = s.processados || 0;
    const pct = Math.min(100, Math.round((processados / total) * 100));

    const progFill = document.getElementById('sherlock-prog-bar-fill');
    if (progFill) progFill.style.width = `${pct}%`;
    const badgeProg = document.getElementById('sherlock-badge-progresso');
    if (badgeProg) badgeProg.innerText = `${pct}%`;
    const kpiProc = document.getElementById('sherlock-kpi-processados');
    if (kpiProc) kpiProc.innerText = `${processados} / ${total}`;
    const kpiEnc = document.getElementById('sherlock-kpi-encontrados');
    if (kpiEnc) kpiEnc.innerText = (s.encontrados || []).length;
    const kpiTempo = document.getElementById('sherlock-kpi-tempo');
    if (kpiTempo) kpiTempo.innerText = `${s.tempo_decorrido_s || 0}s`;

    activeSherlockResults = s.encontrados || [];

    if (activeSherlockResults.length > 0) {
      const boxResultados = document.getElementById('sherlock-box-resultados');
      if (boxResultados) boxResultados.style.display = 'block';
      renderizarCardsResultadosSherlock(activeSherlockResults);
    }

    if (s.status === 'CONCLUIDO' || s.status === 'CANCELADO') {
      clearInterval(sherlockPollingInterval);
      sherlockPollingInterval = null;

      const btnIniciar = document.getElementById('btn-iniciar-sherlock');
      const btnCancelar = document.getElementById('btn-cancelar-sherlock');
      if (btnIniciar) btnIniciar.disabled = false;
      if (btnCancelar) btnCancelar.style.display = 'none';

      const isOk = s.status === 'CONCLUIDO';
      const lblTitulo = document.getElementById('sherlock-lbl-titulo-progresso');
      if (lblTitulo) {
        lblTitulo.innerText = isOk ? 'Varredura Concluída para:' : 'Varredura Interrompida para:';
      }
      const iconBox = document.getElementById('sherlock-progresso-icon-box');
      if (iconBox) {
        iconBox.className = isOk
          ? 'w-9 h-9 rounded-full bg-gh-green/15 border border-gh-green/40 flex items-center justify-center text-gh-green'
          : 'w-9 h-9 rounded-full bg-gh-yellow/15 border border-gh-yellow/40 flex items-center justify-center text-gh-yellow';
        iconBox.innerHTML = `<i data-lucide="${isOk ? 'check-circle-2' : 'alert-triangle'}" style="width:18px;height:18px;"></i>`;
      }
      if (progFill && isOk) {
        progFill.className = 'bg-gh-green h-full transition-all duration-300';
      }
      if (badgeProg && isOk) {
        badgeProg.className = 'badge badge-green font-mono';
      }

      const lblStatus = document.getElementById('sherlock-lbl-status');
      if (lblStatus) {
        lblStatus.innerHTML = isOk
          ? `<span class="text-gh-green font-semibold">✔ Varredura finalizada em ${s.tempo_decorrido_s}s! ${activeSherlockResults.length} perfil(is) confirmado(s).</span>`
          : `<span class="text-gh-yellow font-semibold">Varredura interrompida pelo operador.</span>`;
      }

      const boxResultados = document.getElementById('sherlock-box-resultados');
      if (boxResultados) boxResultados.style.display = 'block';
      renderizarCardsResultadosSherlock(activeSherlockResults);
      renderIcons();

      carregarHistoricoSherlock();
      refreshStats();
    }
  } catch (err) {
    console.error('Erro no polling do Sherlock:', err);
  }
}

async function cancelarVarreduraSherlock() {
  if (!activeSherlockScanId) return;
  try {
    await fetch(`/api/sherlock/cancelar/${activeSherlockScanId}`, { method: 'POST' });
  } catch (err) {
    console.error(err);
  }
}

function renderizarCardsResultadosSherlock(itens) {
  const grid = document.getElementById('sherlock-grid-resultados');
  const countBadge = document.getElementById('sherlock-count-badge');
  if (countBadge) countBadge.innerText = `${itens.length} confirmado(s)`;
  if (!grid) return;

  if (!itens.length) {
    grid.innerHTML = `
      <div class="col-span-full bg-gh-card border border-gh-border rounded-lg p-6 text-center text-gh-muted text-xs">
        Nenhum perfil ativo com este username foi detectado nas redes sondadas.
      </div>
    `;
    return;
  }

  grid.innerHTML = itens.map(it => {
    const isNsfw = it.is_nsfw;
    const initial = it.site.charAt(0).toUpperCase();
    return `
      <div class="sherlock-card bg-gh-card border border-gh-border rounded-lg p-3.5 flex flex-col justify-between gap-2.5 hover:border-gh-blue/50 transition" data-site-name="${escapeHtml(it.site.toLowerCase())}">
        <div class="space-y-1.5">
          <div class="flex items-center justify-between gap-1.5">
            <div class="flex items-center gap-2 min-w-0">
              <div class="w-7 h-7 rounded-md bg-gh-blue/15 border border-gh-blue/30 flex items-center justify-center font-bold text-xs text-gh-blue shrink-0">
                ${initial}
              </div>
              <strong class="text-xs font-semibold text-gh-title truncate">${escapeHtml(it.site)}</strong>
            </div>
            ${isNsfw ? '<span class="badge badge-red text-[10px]" title="Conteúdo Adulto">NSFW</span>' : '<span class="badge badge-green text-[10px]"><i data-lucide="check" style="width:10px;height:10px;"></i><span>Ativo</span></span>'}
          </div>
          <p class="text-[11px] font-mono text-gh-muted truncate" title="${escapeHtml(it.url)}">${escapeHtml(it.url)}</p>
        </div>
        <div class="pt-1.5 border-t border-gh-border flex items-center justify-between">
          <span class="text-[10px] text-gh-muted">${it.encontrado_em ? it.encontrado_em.slice(11, 16) : ''}</span>
          <a href="${escapeHtml(it.url)}" target="_blank" rel="noopener noreferrer" class="btn-primary" style="padding:3px 9px; font-size:11px; text-decoration:none;">
            <span>Abrir Perfil</span>
            <i data-lucide="external-link" style="width:11px;height:11px;"></i>
          </a>
        </div>
      </div>
    `;
  }).join('');
  renderIcons();
}

function filtrarCardsSherlock() {
  const query = (document.getElementById('sherlock-filtro-busca').value || '').trim().toLowerCase();
  const cards = document.querySelectorAll('.sherlock-card');
  cards.forEach(card => {
    const sName = card.getAttribute('data-site-name') || '';
    card.style.display = (!query || sName.includes(query)) ? 'flex' : 'none';
  });
}

function exportarSherlockAtual(formato) {
  if (!activeSherlockScanId) {
    alert('Nenhuma varredura recente para exportar.');
    return;
  }
  window.open(`/api/sherlock/exportar/${activeSherlockScanId}?formato=${formato}`, '_blank');
}

function sincronizarBotoesVerSherlock() {
  const boxResultados = document.getElementById('sherlock-box-resultados');
  const painelVisivel = Boolean(boxResultados && boxResultados.style.display !== 'none');

  document.querySelectorAll('button[data-scan-ver]').forEach(btn => {
    const sid = btn.getAttribute('data-scan-ver');
    const isAtivo = painelVisivel && activeSherlockScanId && sid === activeSherlockScanId;
    if (isAtivo) {
      btn.classList.add('btn-ver-ativo');
      btn.innerHTML = '<i data-lucide="eye-off"></i><span>Ocultar</span>';
      btn.title = 'Clique novamente para ocultar os resultados da tela';
    } else {
      btn.classList.remove('btn-ver-ativo');
      btn.innerHTML = '<i data-lucide="eye"></i><span>Ver</span>';
      btn.title = 'Exibir resultados na tela';
    }
  });
  renderIcons();
}

function fecharResultadosSherlock() {
  const boxResultados = document.getElementById('sherlock-box-resultados');
  if (boxResultados) boxResultados.style.display = 'none';
  const filtro = document.getElementById('sherlock-filtro-busca');
  if (filtro) filtro.value = '';
  sincronizarBotoesVerSherlock();
}

let historicoSherlockAberto = true;
function toggleHistoricoSherlock() {
  const boxTabela = document.getElementById('sherlock-box-historico-tabela');
  const btn = document.getElementById('btn-toggle-historico-sherlock');
  if (!boxTabela) return;
  historicoSherlockAberto = !historicoSherlockAberto;
  boxTabela.style.display = historicoSherlockAberto ? 'block' : 'none';
  if (btn) {
    btn.innerHTML = `<i data-lucide="${historicoSherlockAberto ? 'chevron-up' : 'chevron-down'}"></i><span>${historicoSherlockAberto ? 'Recolher' : 'Expandir'}</span>`;
    renderIcons();
  }
}

async function excluirScanHistorico(scanId) {
  if (!confirm('Deseja excluir este registro de varredura do histórico?')) return;
  try {
    const res = await fetch(`/api/sherlock/historico/${scanId}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.sucesso) {
      if (activeSherlockScanId === scanId) {
        activeSherlockScanId = null;
        fecharResultadosSherlock();
      }
      await carregarHistoricoSherlock();
    } else {
      alert('Não foi possível excluir o registro.');
    }
  } catch (err) {
    console.error('Erro ao excluir scan do histórico:', err);
  }
}

async function limparTodoHistoricoSherlock() {
  if (!confirm('Atenção: Tem certeza que deseja apagar TODO o histórico de investigações Sherlock OSINT?\nEsta ação excluirá todos os registros salvos.')) return;
  try {
    const res = await fetch('/api/sherlock/historico/limpar', { method: 'POST' });
    const data = await res.json();
    if (data.sucesso) {
      activeSherlockScanId = null;
      fecharResultadosSherlock();
      await carregarHistoricoSherlock();
    } else {
      alert('Não foi possível limpar o histórico.');
    }
  } catch (err) {
    console.error('Erro ao limpar histórico Sherlock:', err);
  }
}

async function carregarHistoricoSherlock() {
  const tbody = document.getElementById('sherlock-tbody-historico');
  if (!tbody) return;
  try {
    const res = await fetch('/api/sherlock/historico');
    const data = await res.json();
    if (!data.sucesso || !data.historico || !data.historico.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center text-gh-muted py-6">Nenhuma varredura realizada ainda.</td></tr>';
      return;
    }

    const boxResultados = document.getElementById('sherlock-box-resultados');
    const painelVisivel = Boolean(boxResultados && boxResultados.style.display !== 'none');

    tbody.innerHTML = data.historico.map(h => {
      const isAtivo = painelVisivel && activeSherlockScanId === h.scan_id;
      return `
      <tr>
        <td><strong class="font-mono text-gh-title">@${escapeHtml(h.username)}</strong></td>
        <td><span class="badge ${h.modo === 'todos' ? 'badge-blue' : 'badge-yellow'}">${h.modo === 'todos' ? 'Completa (480+)' : 'Principais (~60)'}</span></td>
        <td>${h.total} redes</td>
        <td><strong class="text-gh-green font-mono">${h.encontrados_count} perfis</strong></td>
        <td>${h.tempo_decorrido_s}s</td>
        <td>${h.criado_em ? h.criado_em.slice(0, 16) : '-'}</td>
        <td>
          <div class="inline-flex items-center gap-1.5">
            <button type="button" class="btn-secondary-sm ${isAtivo ? 'btn-ver-ativo' : ''}" data-scan-ver="${escapeHtml(h.scan_id)}" onclick="carregarScanHistorico('${h.scan_id}')" title="${isAtivo ? 'Clique novamente para ocultar os resultados' : 'Exibir resultados na tela'}">
              <i data-lucide="${isAtivo ? 'eye-off' : 'eye'}"></i>
              <span>${isAtivo ? 'Ocultar' : 'Ver'}</span>
            </button>
            <a href="/api/sherlock/exportar/${h.scan_id}?formato=csv" class="btn-secondary-sm" style="text-decoration:none;" title="Baixar CSV">
              <i data-lucide="file-spreadsheet" class="text-gh-green"></i>
            </a>
            <button type="button" class="btn-secondary-sm" onclick="excluirScanHistorico('${h.scan_id}')" title="Excluir este registro" style="color:var(--danger); border-color:rgba(248,81,73,0.4);">
              <i data-lucide="trash-2"></i>
            </button>
          </div>
        </td>
      </tr>
      `;
    }).join('');
    renderIcons();
  } catch (err) {
    console.error('Erro ao carregar histórico Sherlock:', err);
  }
}

async function carregarScanHistorico(scanId) {
  const boxResultados = document.getElementById('sherlock-box-resultados');
  const jaVisivelMesmoScan = Boolean(
    activeSherlockScanId === scanId &&
    boxResultados &&
    boxResultados.style.display !== 'none'
  );

  // Se o operador clicar em "Ver / Ocultar" na mesma varredura já aberta, fecha o painel!
  if (jaVisivelMesmoScan) {
    fecharResultadosSherlock();
    return;
  }

  try {
    const res = await fetch(`/api/sherlock/status/${scanId}`);
    const data = await res.json();
    if (!data.sucesso || !data.scan) return;
    const s = data.scan;
    activeSherlockScanId = s.scan_id;
    activeSherlockResults = s.encontrados || [];

    const inputUser = document.getElementById('sherlock-input-username');
    if (inputUser) inputUser.value = s.username;
    const selModo = document.getElementById('sherlock-select-modo');
    if (selModo) selModo.value = s.modo || 'principais';
    if (s.caso_id) {
      const selCaso = document.getElementById('sherlock-select-caso');
      if (selCaso) selCaso.value = s.caso_id;
    }

    const boxProgresso = document.getElementById('sherlock-box-progresso');
    if (boxProgresso) boxProgresso.style.display = 'none';

    if (boxResultados) boxResultados.style.display = 'block';

    renderizarCardsResultadosSherlock(activeSherlockResults);
    sincronizarBotoesVerSherlock();
    if (boxResultados) boxResultados.scrollIntoView({ behavior: 'smooth' });
  } catch (err) {
    console.error('Erro ao abrir scan do histórico:', err);
  }
}

window.selecionarAlvoAtalhoSherlock = selecionarAlvoAtalhoSherlock;
window.investigarNoSherlock = investigarNoSherlock;
window.iniciarVarreduraSherlock = iniciarVarreduraSherlock;
window.cancelarVarreduraSherlock = cancelarVarreduraSherlock;
window.filtrarCardsSherlock = filtrarCardsSherlock;
window.exportarSherlockAtual = exportarSherlockAtual;
window.fecharResultadosSherlock = fecharResultadosSherlock;
window.toggleHistoricoSherlock = toggleHistoricoSherlock;
window.excluirScanHistorico = excluirScanHistorico;
window.limparTodoHistoricoSherlock = limparTodoHistoricoSherlock;
window.carregarHistoricoSherlock = carregarHistoricoSherlock;
window.carregarScanHistorico = carregarScanHistorico;


/* ==============================================================================
   MÓDULO BLOCO DE NOTAS OPERACIONAL & DIÁRIO "ONDE PAREI"
   ============================================================================== */

async function carregarNotasOperacionais() {
  try {
    const res = await fetch('/api/notas');
    const data = await res.json();
    if (!data.sucesso) return;

    cachedNotas = data.notas || [];
    const rascunho = data.rascunho || { texto: '', atualizado_em: '' };

    const badgeNotas = document.getElementById('badge-notas-count');
    if (badgeNotas) badgeNotas.innerText = cachedNotas.length;

    // Sincroniza textareas apenas se o operador não estiver digitando neles no momento
    const txtTab = document.getElementById('notas-rascunho-texto');
    if (txtTab && document.activeElement !== txtTab) {
      txtTab.value = rascunho.texto || '';
    }
    const txtModal = document.getElementById('modal-notas-rascunho-texto');
    if (txtModal && document.activeElement !== txtModal) {
      txtModal.value = rascunho.texto || '';
    }

    atualizarIndicadorRascunho(rascunho.atualizado_em ? `Salvo em ${rascunho.atualizado_em.slice(11, 19)}` : 'Sincronizado no SQLite', false);
    renderizarGridNotas();
    renderizarNotasRecentesModal();
  } catch (err) {
    console.error('Erro ao carregar Bloco de Notas:', err);
  }
}

function atualizarIndicadorRascunho(mensagem, salvando = false) {
  const pill = document.getElementById('notas-rascunho-status');
  if (pill) {
    pill.innerHTML = salvando
      ? `<i data-lucide="loader-2" class="animate-spin text-gh-yellow"></i><span>${escapeHtml(mensagem)}</span>`
      : `<i data-lucide="check-circle-2" class="text-gh-green"></i><span>${escapeHtml(mensagem)}</span>`;
    renderIcons(pill);
  }
  const lblModal = document.getElementById('modal-rascunho-status-lbl');
  if (lblModal) {
    lblModal.innerText = mensagem;
    lblModal.style.color = salvando ? 'var(--accent-yellow)' : 'var(--accent-green)';
  }
}

function agendarAutoSaveRascunho(texto, fromModal = false) {
  if (fromModal) {
    const txtTab = document.getElementById('notas-rascunho-texto');
    if (txtTab) txtTab.value = texto;
  } else {
    const txtModal = document.getElementById('modal-notas-rascunho-texto');
    if (txtModal) txtModal.value = texto;
  }

  atualizarIndicadorRascunho('Salvando automaticamente...', true);
  if (autoSaveRascunhoTimer) clearTimeout(autoSaveRascunhoTimer);
  autoSaveRascunhoTimer = setTimeout(async () => {
    try {
      const res = await fetch('/api/notas/rascunho', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texto })
      });
      const data = await res.json();
      if (data.sucesso && data.rascunho) {
        const hora = (data.rascunho.atualizado_em || '').slice(11, 19);
        atualizarIndicadorRascunho(hora ? `Salvo às ${hora}` : 'Salvo no SQLite', false);
      }
    } catch (err) {
      atualizarIndicadorRascunho('Falha ao salvar rascunho', false);
    }
  }, 650);
}

async function salvarRascunhoRapidoManual(btnEl) {
  if (autoSaveRascunhoTimer) {
    clearTimeout(autoSaveRascunhoTimer);
    autoSaveRascunhoTimer = null;
  }
  const txtTab = document.getElementById('notas-rascunho-texto');
  const texto = txtTab ? txtTab.value : '';

  await executarBotaoComFeedback(btnEl, null, async () => {
    const res = await fetch('/api/notas/rascunho', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texto })
    });
    const data = await res.json();
    if (data.sucesso && data.rascunho) {
      const hora = (data.rascunho.atualizado_em || '').slice(11, 19);
      atualizarIndicadorRascunho(hora ? `Salvo às ${hora}` : 'Salvo no SQLite', false);
    }
  }, 'Salvando...', 'Salvo!');
}

async function abrirModalNotasRapidas() {
  await carregarNotasOperacionais();
  abrirModal('modal-notas-rapidas');
  renderIcons();
}

function renderizarNotasRecentesModal() {
  const box = document.getElementById('modal-notas-recentes-lista');
  if (!box) return;
  if (!cachedNotas.length) {
    box.innerHTML = '<p class="text-xs text-gh-muted">Nenhum cartão de nota salvo ainda. Use "Ver Todas / Nova Nota" para criar lembretes categorizados.</p>';
    return;
  }

  const recentes = cachedNotas.slice(0, 5);
  box.innerHTML = recentes.map(n => `
    <div class="bg-gh-bg border border-gh-border rounded-lg p-2.5 flex items-start justify-between gap-2">
      <div class="min-w-0">
        <div class="flex items-center gap-1.5 flex-wrap">
          ${n.fixada ? '<i data-lucide="pin" class="text-gh-yellow" style="width:12px;height:12px;"></i>' : ''}
          <strong class="text-xs text-gh-title">${escapeHtml(n.titulo)}</strong>
          ${n.alvo_vinculado ? `<span class="attempt-tag">@${escapeHtml(n.alvo_vinculado)}</span>` : ''}
        </div>
        <p class="text-xs text-gh-muted line-clamp-2 mt-1">${escapeHtml(n.conteudo || '')}</p>
      </div>
      <span class="text-[11px] font-mono text-gh-muted shrink-0">${n.atualizado_em ? n.atualizado_em.slice(5, 16) : ''}</span>
    </div>
  `).join('');
  renderIcons(box);
}

function obterMetaCategoriaNota(cat) {
  switch (cat) {
    case 'ONDE_PAREI':
      return { label: 'Onde Parei', cls: 'badge-yellow', icon: 'bookmark-check' };
    case 'PISTA':
      return { label: 'Pista / Evidência', cls: 'badge-green', icon: 'search-check' };
    case 'PENDENCIA':
      return { label: 'Pendência', cls: 'badge-red', icon: 'clock' };
    default:
      return { label: 'Geral', cls: 'badge-blue', icon: 'file-text' };
  }
}

function filtrarCategoriaNotas(cat, btnEl) {
  currentNotaCatFilter = cat;
  if (btnEl && btnEl.parentElement) {
    btnEl.parentElement.querySelectorAll('.filter-chip').forEach(b => b.classList.remove('active'));
    btnEl.classList.add('active');
  }
  renderizarGridNotas();
}

function renderizarGridNotas() {
  const grid = document.getElementById('notas-grid-cards');
  if (!grid) return;

  const buscaEl = document.getElementById('input-busca-notas');
  const termo = buscaEl ? buscaEl.value.trim().toLowerCase() : '';

  const filtradas = cachedNotas.filter(n => {
    if (currentNotaCatFilter === 'FIXADAS' && !n.fixada) return false;
    if (currentNotaCatFilter !== 'TODAS' && currentNotaCatFilter !== 'FIXADAS' && n.categoria !== currentNotaCatFilter) {
      return false;
    }
    if (!termo) return true;
    const blob = `${n.titulo || ''} ${n.conteudo || ''} ${n.alvo_vinculado || ''} ${n.caso_nome || ''}`.toLowerCase();
    return blob.includes(termo);
  });

  if (!filtradas.length) {
    grid.innerHTML = `
      <div class="col-span-full bg-gh-bg border border-gh-border rounded-lg p-7 text-center space-y-2">
        <div class="w-10 h-10 rounded-full bg-gh-yellow/10 border border-gh-yellow/30 flex items-center justify-center text-gh-yellow mx-auto">
          <i data-lucide="notebook-pen" style="width:18px;height:18px;"></i>
        </div>
        <div class="text-sm font-semibold text-gh-title">Nenhuma anotação encontrada</div>
        <p class="text-xs text-gh-muted max-w-md mx-auto">Registre pistas, nicks descobertos no Sherlock ou pontos de parada usando o formulário ao lado.</p>
      </div>
    `;
    renderIcons(grid);
    return;
  }

  grid.innerHTML = filtradas.map(n => {
    const meta = obterMetaCategoriaNota(n.categoria);
    return `
      <div class="nota-card ${n.fixada ? 'fixada' : ''}">
        <div class="space-y-2.5">
          <div class="flex items-start justify-between gap-2">
            <div class="flex items-center gap-1.5 flex-wrap">
              <span class="badge ${meta.cls}">
                <i data-lucide="${meta.icon}"></i>
                <span>${escapeHtml(meta.label)}</span>
              </span>
              ${n.fixada ? '<span class="badge badge-yellow" title="Fixada no topo"><i data-lucide="pin"></i><span>Fixada</span></span>' : ''}
            </div>
            <span class="text-xs font-mono text-gh-muted shrink-0">${n.atualizado_em ? n.atualizado_em.slice(0, 16) : ''}</span>
          </div>

          <h4 class="text-base font-semibold text-gh-title">${escapeHtml(n.titulo)}</h4>

          ${(n.alvo_vinculado || n.caso_nome) ? `
            <div class="flex items-center gap-1.5 flex-wrap">
              ${n.alvo_vinculado ? `<span class="attempt-tag">@${escapeHtml(n.alvo_vinculado)}</span>` : ''}
              ${n.caso_nome ? `<span class="attempt-tag text-gh-blue"><i data-lucide="briefcase" style="width:11px;height:11px;display:inline;"></i> ${escapeHtml(n.caso_nome)}</span>` : ''}
            </div>
          ` : ''}

          <div class="nota-conteudo-pre">${escapeHtml(n.conteudo || '')}</div>
        </div>

        <div class="pt-2.5 border-t border-gh-border flex items-center justify-between gap-1.5">
          <button type="button" class="btn-secondary-sm" onclick="alternarFixarNotaUI(${n.id})" title="${n.fixada ? 'Desafixar do topo' : 'Fixar no topo'}">
            <i data-lucide="pin" class="${n.fixada ? 'text-gh-yellow' : ''}"></i>
            <span>${n.fixada ? 'Desafixar' : 'Fixar'}</span>
          </button>
          <div class="flex items-center gap-1.5">
            <button type="button" class="btn-secondary-sm" onclick="editarNotaUI(${n.id})" title="Editar anotação">
              <i data-lucide="pencil"></i>
              <span>Editar</span>
            </button>
            <button type="button" class="btn-secondary-sm" onclick="excluirNotaUI(${n.id})" title="Excluir anotação" style="color:var(--danger);">
              <i data-lucide="trash-2"></i>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
  renderIcons(grid);
}

async function salvarNotaOperacional() {
  const id = document.getElementById('nota-input-id').value;
  const titulo = document.getElementById('nota-input-titulo').value.trim();
  const categoria = document.getElementById('nota-input-categoria').value;
  const alvo_vinculado = document.getElementById('nota-input-alvo').value.trim();
  const caso_id = document.getElementById('nota-select-caso').value || null;
  const conteudo = document.getElementById('nota-input-conteudo').value.trim();
  const fixada = document.getElementById('nota-chk-fixada').checked;

  if (!titulo && !conteudo) {
    alert('Preencha ao menos o Título ou os Detalhes da anotação.');
    return;
  }

  const payload = { titulo: titulo || 'Anotação Operacional', categoria, alvo_vinculado, caso_id, conteudo, fixada };
  try {
    const url = id ? `/api/notas/${id}` : '/api/notas';
    const method = id ? 'PUT' : 'POST';
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!data.sucesso) {
      alert(data.erro || 'Erro ao salvar anotação.');
      return;
    }
    limparFormularioNota();
    await Promise.all([carregarNotasOperacionais(), refreshStats()]);
  } catch (err) {
    alert('Erro de conexão ao salvar anotação: ' + err);
  }
}

function editarNotaUI(notaId) {
  const n = cachedNotas.find(x => Number(x.id) === Number(notaId));
  if (!n) return;
  document.getElementById('nota-input-id').value = n.id;
  document.getElementById('nota-input-titulo').value = n.titulo || '';
  document.getElementById('nota-input-categoria').value = n.categoria || 'GERAL';
  document.getElementById('nota-input-alvo').value = n.alvo_vinculado || '';
  document.getElementById('nota-select-caso').value = n.caso_id || '';
  document.getElementById('nota-input-conteudo').value = n.conteudo || '';
  document.getElementById('nota-chk-fixada').checked = Boolean(n.fixada);

  const hdr = document.getElementById('form-nota-titulo-header');
  if (hdr) {
    hdr.innerHTML = `<i data-lucide="pencil" class="text-gh-yellow"></i><span>Editando Nota #${n.id}</span>`;
  }
  const btnCancel = document.getElementById('btn-cancelar-edicao-nota');
  if (btnCancel) btnCancel.style.display = 'inline-flex';
  const btnSalvar = document.getElementById('btn-salvar-nota');
  if (btnSalvar) btnSalvar.innerHTML = `<i data-lucide="save"></i><span>Atualizar Anotação</span>`;

  renderIcons();
  document.getElementById('nota-input-titulo').focus();
}

function limparFormularioNota() {
  document.getElementById('nota-input-id').value = '';
  document.getElementById('nota-input-titulo').value = '';
  document.getElementById('nota-input-categoria').value = 'ONDE_PAREI';
  document.getElementById('nota-input-alvo').value = '';
  document.getElementById('nota-select-caso').value = '';
  document.getElementById('nota-input-conteudo').value = '';
  document.getElementById('nota-chk-fixada').checked = false;

  const hdr = document.getElementById('form-nota-titulo-header');
  if (hdr) {
    hdr.innerHTML = `<i data-lucide="file-plus-2" class="text-gh-blue"></i><span>Nova Anotação</span>`;
  }
  const btnCancel = document.getElementById('btn-cancelar-edicao-nota');
  if (btnCancel) btnCancel.style.display = 'none';
  const btnSalvar = document.getElementById('btn-salvar-nota');
  if (btnSalvar) btnSalvar.innerHTML = `<i data-lucide="check"></i><span>Salvar Anotação</span>`;
  renderIcons();
}

async function alternarFixarNotaUI(notaId) {
  try {
    await fetch(`/api/notas/${notaId}/fixar`, { method: 'POST' });
    await carregarNotasOperacionais();
  } catch (err) {
    console.error('Erro ao fixar nota:', err);
  }
}

async function excluirNotaUI(notaId) {
  if (!confirm('Deseja excluir esta anotação do Bloco de Notas?')) return;
  try {
    await fetch(`/api/notas/${notaId}`, { method: 'DELETE' });
    if (String(document.getElementById('nota-input-id').value) === String(notaId)) {
      limparFormularioNota();
    }
    await Promise.all([carregarNotasOperacionais(), refreshStats()]);
  } catch (err) {
    console.error('Erro ao excluir nota:', err);
  }
}

async function limparTodasNotasUI() {
  if (!confirm('Tem certeza que deseja apagar todos os cartões de anotações salvos?\n(O rascunho rápido no topo será preservado).')) return;
  try {
    await fetch('/api/notas/limpar', { method: 'POST' });
    limparFormularioNota();
    await Promise.all([carregarNotasOperacionais(), refreshStats()]);
  } catch (err) {
    console.error('Erro ao limpar notas:', err);
  }
}

window.agendarAutoSaveRascunho = agendarAutoSaveRascunho;
window.salvarRascunhoRapidoManual = salvarRascunhoRapidoManual;
window.abrirModalNotasRapidas = abrirModalNotasRapidas;
window.filtrarCategoriaNotas = filtrarCategoriaNotas;
window.renderizarGridNotas = renderizarGridNotas;
window.salvarNotaOperacional = salvarNotaOperacional;
window.editarNotaUI = editarNotaUI;
window.limparFormularioNota = limparFormularioNota;
window.alternarFixarNotaUI = alternarFixarNotaUI;
window.excluirNotaUI = excluirNotaUI;
window.limparTodasNotasUI = limparTodasNotasUI;
