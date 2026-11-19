// "Próximo processo" na solda e na montagem, como na usinagem: alguém faz uma
// parte da ordem e passa para o próximo processo, sempre na mesma célula.
// A ordem fica na coluna fixa "Próximo Processo" até o
// próximo operador iniciar, informando um ou mais operadores (somados aos da
// ordem). Nada de produção é registrado ao passar; a finalização segue igual.
//
// Uso (no script da tela):
//   const proximo = criarProximoProcesso({ base: '/montagem', container: '.containerAguardandoEtapa', aoAtualizar });
//   proximo.botaoHtml()             -> botão para o card da ordem em andamento
//   proximo.ligarBotao(card, ordem) -> liga o clique do botão
//   proximo.carregar(filtros)       -> preenche a coluna "Próximo Processo"
import { ativarVariosOperadores, operadoresEscolhidos } from './operadores-multiplos.js';

const LILAS = '#b15ae6';

function escapar(texto) {
    const div = document.createElement('div');
    div.textContent = texto ?? '';
    return div.innerHTML;
}

function dataBR(valor) {
    if (!valor) return '-';
    const [ano, mes, dia] = String(valor).slice(0, 10).split('-');
    return dia ? `${dia}/${mes}/${ano}` : valor;
}

function tempoDesde(valor) {
    if (!valor) return '';
    const minutos = Math.max(0, Math.floor((Date.now() - new Date(valor).getTime()) / 60000));
    if (minutos < 60) return `há ${minutos} min`;
    const horas = Math.floor(minutos / 60);
    return horas < 24 ? `há ${horas}h${String(minutos % 60).padStart(2, '0')}` : `há ${Math.floor(horas / 24)} dia(s)`;
}

function irParaLogin() {
    window.location.href = `/core/login/?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
}

export function criarProximoProcesso({ base, container, filtroCelula = '#filtro-celula-proximo-processo', aoAtualizar }) {
    let celulas = null; // [{id, nome}] do setor, carregadas uma vez
    let ultimosFiltros = {};

    async function buscarCelulas() {
        if (celulas) return celulas;
        try {
            const resposta = await fetch(`${base}/api/buscar-maquinas/`);
            celulas = (await resposta.json()).maquinas || [];
        } catch (erro) {
            console.error('Erro ao carregar células:', erro);
            celulas = [];
        }
        return celulas;
    }

    async function enviarStatus(dados) {
        const resposta = await fetch(`${base}/api/ordens/atualizar-status/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados),
        });
        if (resposta.status === 401) {
            irParaLogin();
            throw new Error('Sessão expirada.');
        }
        const corpo = await resposta.json().catch(() => ({}));
        if (!resposta.ok) throw new Error(corpo.error || 'Não foi possível atualizar a ordem.');
        return corpo;
    }

    function botaoHtml() {
        return `
            <button class="btn btn-sm btn-passar-proximo-processo m-2" title="Passar para o próximo processo"
                    style="background-color: ${LILAS}; color: #fff;">
                <i class="fa fa-arrow-right"></i>
            </button>`;
    }

    function ligarBotao(card, ordem) {
        const botao = card.querySelector('.btn-passar-proximo-processo');
        if (!botao) return;
        botao.addEventListener('click', async () => {
            // o próximo processo é sempre na mesma célula: só confirma
            const resultado = await Swal.fire({
                icon: 'question',
                title: 'Passar para o próximo processo?',
                html: `Ordem <strong>#${escapar(ordem.ordem_id)}</strong> - ${escapar(ordem.maquina || '')}<br>
                       A ordem fica em "Próximo Processo" até o próximo operador iniciar. Nada de produção é registrado agora.`,
                showCancelButton: true,
                confirmButtonText: 'Passar',
                cancelButtonText: 'Cancelar',
                confirmButtonColor: LILAS,
            });
            if (!resultado.isConfirmed) return;
            try {
                Swal.fire({ title: 'Mudando processo...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
                await enviarStatus({ status: 'agua_prox_proc', ordem_id: ordem.ordem_id });
                Swal.fire({ toast: true, position: 'bottom-end', icon: 'success', title: 'Ordem passada para o próximo processo', showConfirmButton: false, timer: 2500 });
                aoAtualizar?.();
            } catch (erro) {
                Swal.fire({ icon: 'error', title: 'Erro', text: erro.message });
            }
        });
    }

    async function iniciarProximo(ordem) {
        let operadores = { operadores: [], operadores_maquina: [] };
        try {
            const resposta = await fetch(`${base}/api/listar-operadores/?maquina=${encodeURIComponent(ordem.maquina || '')}`);
            operadores = await resposta.json();
        } catch (erro) {
            console.error('Erro ao carregar operadores:', erro);
        }
        const opcao = (op) => `<option value="${escapar(op.id)}">${escapar(op.matricula)} - ${escapar(op.nome)}</option>`;
        const daCelula = operadores.operadores_maquina || [];

        // igual ao modal de iniciar: primeiro os operadores da célula; o link
        // "Clique aqui" troca para a lista geral (e "Voltar" retorna)
        const resultado = await Swal.fire({
            title: 'Iniciar próximo processo',
            html: `
                <p class="mb-2">Ordem <strong>#${escapar(ordem.ordem_id)}</strong> - ${escapar(ordem.maquina || '')}</p>
                <label class="form-label d-block text-start" id="swal-label-operadores" for="swal-operador-celula">Operador - ${escapar(ordem.maquina || '')}</label>
                <select id="swal-operador-celula" class="form-select">
                    <option value="">${daCelula.length ? 'Selecione um operador...' : 'Nenhum operador cadastrado nesta célula'}</option>
                    ${daCelula.map(opcao).join('')}
                </select>
                <select id="swal-operador-todos" class="form-select" style="display: none;">
                    <option value="">Selecione um operador...</option>
                    ${(operadores.operadores || []).map(opcao).join('')}
                </select>
                <p id="swal-link-todos" class="text-end mb-0 mt-1" style="font-size: 12px;">Não encontrou seu nome na lista? <a href="#" id="swal-abrir-todos" style="color: #0d6efd;">Clique aqui</a></p>
                <p id="swal-link-voltar" class="text-end mb-0 mt-1" style="font-size: 12px; display: none;">Deseja voltar a lista anterior? <a href="#" id="swal-voltar-celula" style="color: #0d6efd;">Voltar</a></p>
                <div class="form-text text-start">Pode escolher mais de um: cada um escolhido aparece abaixo.</div>
                <div id="operadoresContinuarEscolhidos" class="d-flex flex-wrap gap-2 mt-2 text-start"></div>`,
            showCancelButton: true,
            confirmButtonText: 'Iniciar',
            cancelButtonText: 'Cancelar',
            didOpen: () => {
                ativarVariosOperadores(['swal-operador-celula', 'swal-operador-todos'], 'operadoresContinuarEscolhidos');
                const $ = (id) => document.getElementById(id);
                const mostrarTodos = (todos) => {
                    $('swal-operador-celula').style.display = todos ? 'none' : '';
                    $('swal-operador-todos').style.display = todos ? '' : 'none';
                    $('swal-link-todos').style.display = todos ? 'none' : '';
                    $('swal-link-voltar').style.display = todos ? '' : 'none';
                    $('swal-label-operadores').textContent = todos ? 'Todos os Operadores' : `Operador - ${ordem.maquina || ''}`;
                };
                $('swal-abrir-todos').addEventListener('click', (e) => { e.preventDefault(); mostrarTodos(true); });
                $('swal-voltar-celula').addEventListener('click', (e) => { e.preventDefault(); mostrarTodos(false); });
            },
            preConfirm: () => {
                const ids = operadoresEscolhidos('operadoresContinuarEscolhidos');
                if (!ids.length) {
                    Swal.showValidationMessage('Selecione ao menos um operador.');
                    return false;
                }
                return ids;
            },
        });
        if (!resultado.isConfirmed) return;
        try {
            Swal.fire({ title: 'Iniciando...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
            await enviarStatus({
                status: 'continuar',
                ordem_id: ordem.ordem_id,
                operador: parseInt(resultado.value[0], 10),
                operadores: resultado.value.map((id) => parseInt(id, 10)),
            });
            Swal.fire({ toast: true, position: 'bottom-end', icon: 'success', title: 'Próximo processo iniciado', showConfirmButton: false, timer: 2500 });
            aoAtualizar?.();
        } catch (erro) {
            Swal.fire({ icon: 'error', title: 'Erro', text: erro.message });
        }
    }

    // "Qual sua célula?" no topo da coluna (como o "Qual seu processo?" da usinagem)
    // "Qual sua célula?" segue o cartão de setor do filtro do "Painel de Ordens
    // Criadas" (campo #filtro-setor): clicar num cartão ou em "Limpar" já
    // reflete aqui. Também dá para trocar direto no select.
    let filtroPronto = false;
    let ultimaBusca = 0; // só a busca mais recente desenha a coluna
    function setorDoFiltro() {
        return document.getElementById('filtro-setor')?.value || '';
    }
    function sincronizarSelect(select, valor) {
        if (!select) return '';
        select.value = [...select.options].some((o) => o.value === String(valor)) ? String(valor) : '';
        return select.value;
    }
    async function prepararFiltro() {
        const select = document.querySelector(filtroCelula);
        if (!select || filtroPronto) return select;
        filtroPronto = true;
        const lista = await buscarCelulas();
        select.insertAdjacentHTML('beforeend', lista.map((c) => `<option value="${escapar(c.id)}">${escapar(c.nome)}</option>`).join(''));
        select.addEventListener('change', () => carregar({ ...ultimosFiltros, setor: select.value }, false));
        // depois do clique no cartão (o script da tela grava o #filtro-setor no mesmo clique)
        document.addEventListener('click', (evento) => {
            if (!evento.target.closest('.setor-btn, #limpar-filtro')) return;
            setTimeout(() => carregar({ ...ultimosFiltros, setor: setorDoFiltro() }), 0);
        });
        return select;
    }

    async function carregar(filtros = {}, seguirFiltro = true) {
        ultimosFiltros = filtros;
        const alvo = document.querySelector(container);
        if (!alvo) return;
        const select = await prepararFiltro();
        // segue o setor do filtro da tela; mudança feita no próprio select vale até o próximo filtro
        const celula = seguirFiltro ? sincronizarSelect(select, filtros.setor ?? setorDoFiltro()) : (select?.value || '');
        alvo.innerHTML = '<div class="spinner-border text-dark" role="status"><span class="visually-hidden">Carregando...</span></div>';
        try {
            const minhaBusca = ++ultimaBusca;
            const resposta = await fetch(`${base}/api/ordens-aguardando-etapa/?setor=${encodeURIComponent(celula)}`);
            if (minhaBusca !== ultimaBusca) return; // chegou depois de uma busca mais nova
            if (resposta.status === 401) {
                irParaLogin();
                return;
            }
            const ordens = (await resposta.json()).ordens || [];
            if (minhaBusca !== ultimaBusca) return;
            if (!ordens.length) {
                alvo.innerHTML = '<p class="text-muted small mb-0">Nenhuma ordem aguardando o próximo processo.</p>';
                return;
            }
            alvo.innerHTML = '';
            ordens.forEach((ordem) => {
                const card = document.createElement('div');
                card.dataset.ordemId = ordem.ordem_id;
                const pecas = Array.isArray(ordem.pecas) ? ordem.pecas.join(', ') : (ordem.pecas || '');
                card.innerHTML = `
                    <div class="card shadow-lg border-0 rounded-3 mb-3">
                        <div class="card-header text-white d-flex justify-content-between align-items-center p-3" style="background-color: ${LILAS};">
                            <h6 class="card-title mb-0">#${escapar(ordem.ordem_id)} - ${escapar(ordem.maquina || '')}</h6>
                            <span class="badge bg-light text-dark">${escapar((ordem.etapas_concluidas || 1) + 1)}º processo</span>
                        </div>
                        <div class="card-body bg-light">
                            <p class="card-text mb-2 small"><strong>Data da carga:</strong> ${escapar(dataBR(ordem.data_carga))}</p>
                            <p class="card-text mb-2 small"><strong>Qt. restante:</strong> ${escapar(ordem.qtd_restante)}</p>
                            ${ordem.operador_inicio ? `<p class="card-text mb-2 small"><strong>Operador:</strong> ${escapar(ordem.operador_inicio)}</p>` : ''}
                            <p class="card-text mb-0 small">${escapar(pecas)}</p>
                        </div>
                        <div class="card-footer d-flex justify-content-between align-items-center bg-white small">
                            <span class="text-muted">Aguardando ${escapar(tempoDesde(ordem.ultima_atualizacao))}</span>
                            <button class="btn btn-sm btn-warning btn-iniciar-proximo-processo" title="Iniciar próximo processo">
                                <i class="fa fa-play"></i> Iniciar
                            </button>
                        </div>
                    </div>`;
                card.querySelector('.btn-iniciar-proximo-processo').addEventListener('click', () => iniciarProximo(ordem));
                alvo.appendChild(card);
            });
        } catch (erro) {
            console.error('Erro ao buscar ordens do próximo processo:', erro);
            alvo.innerHTML = '<p class="text-danger small mb-0">Erro ao carregar as ordens.</p>';
        }
    }

    return { botaoHtml, ligarBotao, carregar };
}

// Antes de iniciar (tabela de ordens ou QR code) uma ordem que está em
// "Próximo Processo": pergunta se o usuário tem certeza. Devolve true para
// seguir com o início normal.
export async function confirmarInicioSeProximoProcesso(status, ordemTexto = '') {
    if (status !== 'agua_prox_proc') return true;
    const resposta = await Swal.fire({
        icon: 'warning',
        title: 'Ordem em "Próximo Processo"',
        html: `A ordem ${ordemTexto ? `<strong>#${escapar(ordemTexto)}</strong> ` : ''}está aguardando o próximo processo.<br>Tem certeza que deseja iniciá-la?`,
        showCancelButton: true,
        confirmButtonText: 'Sim, iniciar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: LILAS,
    });
    return resposta.isConfirmed;
}
