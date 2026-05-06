/* estoque.js – Saldo de Recurso */
(function () {
  'use strict';

  const API_URL = '/compras/api/estoque/';

  let _colunas = [];
  let _sortCol = null;
  let _sortDir = 'asc';

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const spinner     = document.getElementById('spinner');
  const badgeTotal  = document.getElementById('badgeTotal');
  const theadEl     = document.getElementById('theadEstoque');
  const tbodyEl     = document.getElementById('tbodyEstoque');
  const wrapperEl   = document.getElementById('tabelaWrapper');
  const vazioEl     = document.getElementById('mensagemVazio');
  const erroEl      = document.getElementById('mensagemErro');
  const campoBusca  = document.getElementById('campoBusca');
  const selectGrupo = document.getElementById('selectGrupo');
  const wrapGrupo   = document.getElementById('wrapperGrupo');
  const btnFiltrar  = document.getElementById('btnFiltrar');
  const btnLimpar   = document.getElementById('btnLimpar');
  const btnRefresh  = document.getElementById('btnRefresh');

  // ── Helpers ───────────────────────────────────────────────────────────────
  function setLoading(on) {
    spinner.classList.toggle('active', on);
    btnFiltrar.disabled = on;
    btnRefresh.disabled = on;
  }

  function showErro(msg) {
    erroEl.textContent = msg;
    erroEl.style.display = 'block';
    wrapperEl.style.display = 'none';
    vazioEl.style.display = 'none';
  }

  function hideErro() {
    erroEl.style.display = 'none';
  }

  // ── Thead ─────────────────────────────────────────────────────────────────
  function buildThead(colunas) {
    _colunas = colunas;
    theadEl.innerHTML = '';
    const tr = document.createElement('tr');
    colunas.forEach(col => {
      const th = document.createElement('th');
      th.dataset.col = col;
      th.innerHTML = `${escHtml(col)} <span class="sort-icon">⇅</span>`;
      th.addEventListener('click', () => sortBy(col));
      tr.appendChild(th);
    });
    theadEl.appendChild(tr);
  }

  // ── Tbody ─────────────────────────────────────────────────────────────────
  function buildTbody(itens) {
    tbodyEl.innerHTML = '';
    itens.forEach(item => {
      const tr = document.createElement('tr');
      _colunas.forEach(col => {
        const td = document.createElement('td');
        const val = item[col] ?? '';
        td.textContent = val;
        td.title = val;
        tr.appendChild(td);
      });
      tbodyEl.appendChild(tr);
    });
  }

  // ── Sort ──────────────────────────────────────────────────────────────────
  function sortBy(col) {
    if (_sortCol === col) {
      _sortDir = _sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      _sortCol = col;
      _sortDir = 'asc';
    }

    // Atualiza ícones de ordenação
    theadEl.querySelectorAll('th').forEach(th => {
      th.classList.remove('sort-asc', 'sort-desc');
      th.querySelector('.sort-icon').textContent = '⇅';
    });
    const activeTh = theadEl.querySelector(`th[data-col="${CSS.escape(col)}"]`);
    if (activeTh) {
      activeTh.classList.add(_sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
      activeTh.querySelector('.sort-icon').textContent = _sortDir === 'asc' ? '↑' : '↓';
    }

    const rows = Array.from(tbodyEl.querySelectorAll('tr'));
    const colIdx = _colunas.indexOf(col);
    rows.sort((a, b) => {
      const va = a.cells[colIdx]?.textContent ?? '';
      const vb = b.cells[colIdx]?.textContent ?? '';
      const na = parseFloat(va.replace(',', '.'));
      const nb = parseFloat(vb.replace(',', '.'));
      if (!isNaN(na) && !isNaN(nb)) {
        return _sortDir === 'asc' ? na - nb : nb - na;
      }
      return _sortDir === 'asc' ? va.localeCompare(vb, 'pt-BR') : vb.localeCompare(va, 'pt-BR');
    });
    rows.forEach(r => tbodyEl.appendChild(r));
  }

  // ── Grupos ────────────────────────────────────────────────────────────────
  function populateGrupos(grupos) {
    if (!grupos || grupos.length === 0) {
      wrapGrupo.style.display = 'none';
      return;
    }
    wrapGrupo.style.display = '';
    const current = selectGrupo.value;
    selectGrupo.innerHTML = '<option value="">Todos</option>';
    grupos.forEach(g => {
      const opt = document.createElement('option');
      opt.value = g;
      opt.textContent = g;
      if (g === current) opt.selected = true;
      selectGrupo.appendChild(opt);
    });
  }

  // ── Fetch ─────────────────────────────────────────────────────────────────
  function fetchDados(refresh = false) {
    hideErro();
    setLoading(true);
    wrapperEl.style.display = 'none';
    vazioEl.style.display = 'none';

    const params = new URLSearchParams();
    if (campoBusca.value.trim()) params.set('busca', campoBusca.value.trim());
    if (selectGrupo.value)       params.set('grupo', selectGrupo.value);
    if (refresh)                 params.set('refresh', '1');

    fetch(`${API_URL}?${params}`)
      .then(r => r.json())
      .then(data => {
        setLoading(false);

        if (data.error) {
          showErro('Erro ao carregar dados: ' + data.error);
          return;
        }

        populateGrupos(data.grupos || []);

        if (!data.itens || data.itens.length === 0) {
          badgeTotal.textContent = '0 itens';
          vazioEl.style.display = 'block';
          return;
        }

        badgeTotal.textContent = `${data.total} ${data.total === 1 ? 'item' : 'itens'}`;
        buildThead(data.colunas);
        buildTbody(data.itens);
        wrapperEl.style.display = 'block';
        _sortCol = null;
      })
      .catch(err => {
        setLoading(false);
        showErro('Falha na requisição: ' + err.message);
      });
  }

  // ── Eventos ───────────────────────────────────────────────────────────────
  btnFiltrar.addEventListener('click', () => fetchDados());

  btnLimpar.addEventListener('click', () => {
    campoBusca.value = '';
    selectGrupo.value = '';
    fetchDados();
  });

  btnRefresh.addEventListener('click', () => fetchDados(true));

  campoBusca.addEventListener('keydown', e => {
    if (e.key === 'Enter') fetchDados();
  });

  // ── Utilitários ───────────────────────────────────────────────────────────
  function escHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Inicialização ─────────────────────────────────────────────────────────
  fetchDados();
})();
