let currentTab = 'tab-dashboard';

document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  setupEventListeners();
  loadAllData();

  // Polling automático para atualizar logs e estatísticas em segundo plano
  setInterval(refreshLogs, 2500);
  setInterval(refreshStats, 5000);
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
    'tab-contas': 'Pool de Contas Fantoches',
    'tab-alvos': 'Alvos & Monitoramento em Cascata',
    'tab-downloads': 'Mídias e Perfis Extraídos',
    'tab-logs': 'Logs do Sistema'
  };
  document.getElementById('page-title').innerText = titles[tabId] || 'Painel de Controle';

  if (tabId === 'tab-contas') loadContas();
  if (tabId === 'tab-alvos') loadAlvos();
  if (tabId === 'tab-downloads') loadDownloads();
}

function setupEventListeners() {
  document.getElementById('btn-quick-check').addEventListener('click', dispararVerificacao);
  document.getElementById('btn-open-scrape-modal').addEventListener('click', () => abrirModal('modal-scrape'));
  document.getElementById('btn-confirm-scrape').addEventListener('click', confirmarScrapeDireto);
  document.getElementById('btn-add-conta').addEventListener('click', () => {
    limparFormConta();
    abrirModal('modal-conta');
  });
  document.getElementById('btn-salvar-modal-conta').addEventListener('click', salvarNovaConta);
  document.getElementById('btn-salvar-alvos').addEventListener('click', salvarNovosAlvos);
  document.getElementById('btn-refresh-alvos').addEventListener('click', loadAlvos);
  document.getElementById('btn-refresh-downloads').addEventListener('click', loadDownloads);
  document.getElementById('btn-clear-logs').addEventListener('click', limparLogs);
  document.getElementById('btn-toggle-sentinela').addEventListener('click', toggleSentinela);
  document.getElementById('btn-confirm-sentinela').addEventListener('click', confirmarInicioSentinela);

  const checkAll = document.getElementById('check-all-alvos');
  if (checkAll) checkAll.addEventListener('change', toggleSelectAllAlvos);

  const btnDelSel = document.getElementById('btn-delete-selected-alvos');
  if (btnDelSel) btnDelSel.addEventListener('click', removerAlvosSelecionados);

  const btnClearAll = document.getElementById('btn-clear-all-alvos');
  if (btnClearAll) btnClearAll.addEventListener('click', limparTodosAlvos);

  const btnClearDownloads = document.getElementById('btn-clear-all-downloads');
  if (btnClearDownloads) btnClearDownloads.addEventListener('click', limparTodasMidias);
}

function loadAllData() {
  refreshStats();
  refreshLogs();
  loadAlvos();
  loadContas();
  loadDownloads();
}

/* ESTATÍSTICAS */
async function refreshStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    document.getElementById('stat-contas').innerText = data.total_contas;
    document.getElementById('stat-contas-ativas').innerText = `${data.contas_ativas} ativas`;
    document.getElementById('stat-alvos').innerText = data.total_alvos;
    document.getElementById('stat-alvos-pendentes').innerText = `${data.alvos_pendentes} pendentes`;
    document.getElementById('stat-concluidos').innerText = data.alvos_concluidos;
    document.getElementById('stat-downloads').innerText = data.perfis_baixados;

    const dot = document.getElementById('sentinela-dot');
    const btn = document.getElementById('btn-toggle-sentinela');
    if (data.sentinela_ativo) {
      dot.classList.add('active');
      btn.innerText = 'Parar Sentinela';
      btn.classList.add('active');
    } else {
      dot.classList.remove('active');
      btn.innerText = 'Ligar Sentinela';
      btn.classList.remove('active');
    }
  } catch (err) {
    console.error('Erro ao atualizar estatísticas:', err);
  }
}

/* LOGS */
async function refreshLogs() {
  try {
    const res = await fetch('/api/logs');
    const logs = await res.json();
    
    document.getElementById('badge-logs-count').innerText = logs.length;

    const renderLog = l => `<div class="log-line log-${l.nivel}"><span class="log-time">[${l.timestamp}]</span> ${escapeHtml(l.mensagem)}</div>`;
    const html = logs.map(renderLog).join('');

    const dashTerm = document.getElementById('dash-terminal');
    const fullTerm = document.getElementById('full-terminal');
    
    const wasAtBottomDash = dashTerm.scrollHeight - dashTerm.scrollTop <= dashTerm.clientHeight + 40;
    dashTerm.innerHTML = html || '<div class="text-muted">Aguardando atividades...</div>';
    if (wasAtBottomDash) dashTerm.scrollTop = dashTerm.scrollHeight;

    if (fullTerm) {
      const wasAtBottomFull = fullTerm.scrollHeight - fullTerm.scrollTop <= fullTerm.clientHeight + 40;
      fullTerm.innerHTML = html || '<div class="text-muted">Aguardando atividades...</div>';
      if (wasAtBottomFull) fullTerm.scrollTop = fullTerm.scrollHeight;
    }
  } catch (err) {
    console.error('Erro ao buscar logs:', err);
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

    if (!contas.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center">Nenhuma conta cadastrada no pool.</td></tr>';
      return;
    }

    tbody.innerHTML = contas.map(c => {
      const isAtiva = c.ativo === 'Sim' || c.ativo === true;
      const sessionDisplay = c.sessionid ? c.sessionid.slice(0, 18) + '...' : '<span class="text-muted">Vazio</span>';
      return `
        <tr>
          <td><strong>#${c.id}</strong></td>
          <td>@${c.user || 'Sem user'}</td>
          <td><span class="badge ${isAtiva ? 'badge-green' : 'badge-red'}">${isAtiva ? 'ATIVA' : 'INATIVA'}</span></td>
          <td><code>${sessionDisplay}</code></td>
          <td>${c.adicionado_em || '-'}</td>
          <td>
            <button class="btn-secondary-sm" onclick="toggleConta(${c.id})">${isAtiva ? 'Desativar' : 'Ativar'}</button>
            <button class="btn-secondary-sm" onclick="editarConta(${c.id}, '${c.user || ''}', '${c.ds_user_id || ''}', '${c.sessionid || ''}')">✏️ Atualizar</button>
            <button class="btn-secondary-sm" onclick="testarConta(${c.id}, this)">🧪 Testar</button>
            <button class="btn-secondary-sm" onclick="removerConta(${c.id})">🗑️</button>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Erro ao carregar contas:', err);
  }
}

async function toggleConta(id) {
  await fetch(`/api/contas/${id}/toggle`, { method: 'POST' });
  loadContas();
  refreshStats();
}

function editarConta(id, user, ds_user_id, sessionid) {
  document.getElementById('modal-conta-id').value = id;
  document.getElementById('modal-conta-title').innerText = `Atualizar Conta @${user}`;
  document.getElementById('modal-conta-user').value = user;
  document.getElementById('modal-conta-ds').value = ds_user_id;
  document.getElementById('modal-conta-session').value = sessionid;
  abrirModal('modal-conta');
}

async function testarConta(id, btnElement) {
  const originalText = btnElement ? btnElement.innerText : '🧪 Testar';
  if (btnElement) {
    btnElement.innerText = '⏳ Testando...';
    btnElement.disabled = true;
  }
  try {
    const res = await fetch(`/api/contas/${id}/testar`, { method: 'POST' });
    const data = await res.json();
    if (data.autenticado) {
      alert('✔ Conta CONECTADA e autenticada com sucesso no Instagram!');
    } else {
      alert('❌ Falha na autenticação: sessão expirada ou inválida.');
    }
  } catch (e) {
    alert('Erro ao comunicar com o servidor: ' + e);
  } finally {
    if (btnElement) {
      btnElement.innerText = originalText;
      btnElement.disabled = false;
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
    // Atualização (PUT)
    await fetch(`/api/contas/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user, ds_user_id: ds, sessionid: session })
    });
    alert('Conta atualizada com sucesso!');
  } else {
    // Criação (POST)
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
  document.getElementById('modal-conta-title').innerText = 'Adicionar Conta ao Pool';
  document.getElementById('modal-conta-user').value = '';
  document.getElementById('modal-conta-ds').value = '';
  document.getElementById('modal-conta-session').value = '';
}

/* ALVOS */
async function loadAlvos() {
  try {
    const res = await fetch('/api/alvos');
    const alvos = await res.json();
    
    // Tabela completa
    const tbody = document.getElementById('alvos-tbody');
    const dashTbody = document.getElementById('dash-alvos-tbody');

    if (!alvos.length) {
      const emptyRow = '<tr><td colspan="6" class="text-center">Nenhum alvo monitorado.</td></tr>';
      if (tbody) tbody.innerHTML = emptyRow;
      if (dashTbody) dashTbody.innerHTML = '<tr><td colspan="4" class="text-center">Nenhum alvo monitorado.</td></tr>';
      return;
    }

    const rows = alvos.map(a => {
      let badgeClass = 'badge-yellow';
      if (a.status === 'CONCLUIDO') badgeClass = 'badge-green';
      if (a.status === 'ESGOTADO') badgeClass = 'badge-red';

      return `
        <tr>
          <td><input type="checkbox" class="check-alvo" data-user="${a.username}" onchange="atualizarContadorSelecao()"></td>
          <td><strong>@${a.username}</strong></td>
          <td>${a.conta_atual ? '@' + a.conta_atual : '<span class="text-muted">Aguardando bot</span>'}</td>
          <td><span class="badge ${badgeClass}">${a.status || 'AGUARDANDO'}</span></td>
          <td>${(a.tentativas || []).length} bot(s)</td>
          <td>
            <button class="btn-secondary-sm" onclick="baixarDireto('${a.username}')">⚡ Extrair</button>
            <a href="/api/downloads/${a.username}/zip" class="btn-secondary-sm" style="text-decoration:none; display:inline-block;">📦 ZIP</a>
            <button class="btn-secondary-sm" onclick="removerAlvo('${a.username}')">🗑️</button>
          </td>
        </tr>
      `;
    }).join('');

    if (tbody) tbody.innerHTML = rows;
    atualizarContadorSelecao();

    if (dashTbody) {
      const recent = alvos.slice(-5).reverse();
      dashTbody.innerHTML = recent.map(a => `
        <tr>
          <td><strong>@${a.username}</strong></td>
          <td>${a.conta_atual ? '@' + a.conta_atual : '-'}</td>
          <td><span class="badge ${a.status === 'CONCLUIDO' ? 'badge-green' : 'badge-yellow'}">${a.status}</span></td>
          <td>${a.atualizado_em ? a.atualizado_em.slice(11, 16) : '-'}</td>
        </tr>
      `).join('');
    }
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
  if (confirm('⚠️ Tem certeza que deseja apagar TODOS os alvos da lista de monitoramento?')) {
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
    alert('Digite ao menos um @alvo.');
    return;
  }

  const res = await fetch('/api/alvos', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ usernames: text })
  });
  const data = await res.json();
  if (data.sucesso) {
    alert(data.mensagem || `${data.total_adicionados} alvo(s) adicionados! O bot já está enviando as solicitações.`);
  } else {
    alert(data.erro || 'Falha ao adicionar alvo.');
  }
  textarea.value = '';
  loadAlvos();
  refreshStats();
  refreshLogs();
}

/* AÇÕES */
async function dispararVerificacao() {
  await fetch('/api/acoes/verificar_cascata', { method: 'POST' });
  alert('Varredura e cascata de solicitações iniciadas em segundo plano! Acompanhe nos logs.');
  refreshLogs();
}

async function confirmarScrapeDireto() {
  const input = document.getElementById('input-direct-target');
  const target = input.value.trim();
  if (!target) {
    alert('Digite o username do alvo.');
    return;
  }
  fecharModal('modal-scrape');
  baixarDireto(target);
  input.value = '';
}

async function baixarDireto(username) {
  const res = await fetch('/api/acoes/baixar_direto', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username })
  });
  const data = await res.json();
  alert(data.mensagem);
  refreshLogs();
}

async function toggleSentinela() {
  const dot = document.getElementById('sentinela-dot');
  if (dot.classList.contains('active')) {
    // Parar
    await fetch('/api/acoes/sentinela/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intervalo: 30 })
    });
    refreshStats();
    refreshLogs();
  } else {
    // Abrir modal para perguntar intervalo
    abrirModal('modal-sentinela');
  }
}

async function confirmarInicioSentinela() {
  const val = document.getElementById('input-sentinela-intervalo').value.trim();
  const minutos = parseInt(val, 10) || 30;
  fecharModal('modal-sentinela');

  const res = await fetch('/api/acoes/sentinela/toggle', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ intervalo: minutos })
  });
  const data = await res.json();
  alert(`Modo Sentinela 24/7 iniciado com ciclos a cada ${minutos} minutos!`);
  refreshStats();
  refreshLogs();
}

/* DOWNLOADS */
async function loadDownloads() {
  try {
    const res = await fetch('/api/downloads');
    const perfis = await res.json();
    const grid = document.getElementById('downloads-grid');

    if (!perfis.length) {
      grid.innerHTML = '<p class="text-center" style="grid-column: 1/-1;">Nenhum perfil baixado ainda na pasta downloads/.</p>';
      return;
    }

    grid.innerHTML = perfis.map(p => {
      const c = p.dados.contadores || {};
      const conex = p.dados.conexoes || {};
      const mutuos = (conex.resumo_relacionamento || {}).total_mutuo || 0;
      return `
        <div class="download-card">
          <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div class="download-card-title">@${p.username}</div>
            <button class="btn-secondary-sm" onclick="removerDownload('${p.username}')" title="Excluir mídias deste perfil">🗑️</button>
          </div>
          <div class="download-card-stats">
            <div>📊 ${c.posts || '0 posts'} • ${c.seguidores || '0 seguidores'} • ${c.seguindo || '0 seguindo'}</div>
            <div>🤝 Conexões Mútuas: <strong>${mutuos}</strong></div>
            <div>📁 Total de arquivos: <strong>${p.total_arquivos}</strong></div>
          </div>
          <div class="mt-2" style="display:flex; justify-content:space-between; align-items:center;">
            <span class="badge badge-green">Concluído</span>
            <a href="/api/downloads/${p.username}/zip" class="btn-primary-sm" style="text-decoration:none; padding:4px 10px;">⬇️ Baixar ZIP</a>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('Erro ao carregar downloads:', err);
  }
}

async function removerDownload(username) {
  if (confirm(`Deseja excluir permanentemente todas as fotos, stories e relatórios de @${username}?`)) {
    try {
      const res = await fetch(`/api/downloads/${username}`, { method: 'DELETE' });
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
  if (confirm('⚠️ Tem certeza que deseja apagar TODAS as pastas e fotos salvas em downloads/?')) {
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

/* UTILITÁRIOS */
function abrirModal(id) {
  document.getElementById(id).classList.add('active');
}

function fecharModal(id) {
  document.getElementById(id).classList.remove('active');
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
