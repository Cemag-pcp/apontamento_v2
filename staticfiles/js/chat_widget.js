document.addEventListener('DOMContentLoaded', function () {
    const bubble = document.getElementById('chatAssistenteBubble');
    const panel = document.getElementById('chatAssistentePanel');
    const fechar = document.getElementById('chatAssistenteFechar');
    const novaConversa = document.getElementById('chatAssistenteNovaConversa');
    const mensagensEl = document.getElementById('chatAssistenteMensagens');
    const form = document.getElementById('chatAssistenteForm');
    const input = document.getElementById('chatAssistenteInput');

    if (!bubble || !panel) return;

    const STORAGE_KEY = 'chatAssistenteSessaoId';
    const MENSAGEM_BOAS_VINDAS = 'Olá! Pergunte sobre tudo relacionado ao CMGPROD.';
    let enviando = false;

    function adicionarMensagem(role, texto) {
        const div = document.createElement('div');
        div.className = 'chat-msg ' + role;
        const bolha = document.createElement('div');
        bolha.className = 'bolha';
        bolha.textContent = texto;
        div.appendChild(bolha);
        mensagensEl.appendChild(div);
        mensagensEl.scrollTop = mensagensEl.scrollHeight;
        return div;
    }

    function carregarHistorico(sessaoId) {
        fetch('/assistente/api/historico/?sessao_id=' + encodeURIComponent(sessaoId))
            .then(function (response) {
                return response.ok ? response.json() : Promise.reject();
            })
            .then(function (data) {
                mensagensEl.innerHTML = '';
                if (!data.mensagens || data.mensagens.length === 0) {
                    adicionarMensagem('assistant', MENSAGEM_BOAS_VINDAS);
                    return;
                }
                data.mensagens.forEach(function (m) {
                    adicionarMensagem(m.role, m.conteudo);
                });
            })
            .catch(function () {
                mensagensEl.innerHTML = '';
                adicionarMensagem('assistant', MENSAGEM_BOAS_VINDAS);
            });
    }

    function novaSessao() {
        sessaoId = crypto.randomUUID();
        localStorage.setItem(STORAGE_KEY, sessaoId);
        mensagensEl.innerHTML = '';
        adicionarMensagem('assistant', MENSAGEM_BOAS_VINDAS);
    }

    let sessaoId = localStorage.getItem(STORAGE_KEY);
    if (!sessaoId) {
        sessaoId = crypto.randomUUID();
        localStorage.setItem(STORAGE_KEY, sessaoId);
        adicionarMensagem('assistant', MENSAGEM_BOAS_VINDAS);
    } else {
        carregarHistorico(sessaoId);
    }

    bubble.addEventListener('click', function () {
        panel.classList.toggle('aberto');
        if (panel.classList.contains('aberto')) {
            input.focus();
            bubble.classList.remove('tem-resposta');
        }
    });

    fechar.addEventListener('click', function () {
        panel.classList.remove('aberto');
    });

    novaConversa.addEventListener('click', function () {
        novaSessao();
    });

    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            form.requestSubmit();
        }
    });

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        const mensagem = input.value.trim();
        if (!mensagem || enviando) return;

        adicionarMensagem('user', mensagem);
        input.value = '';
        enviando = true;
        const botaoEnviar = form.querySelector('button[type="submit"]');
        botaoEnviar.disabled = true;
        const indicador = adicionarMensagem('assistant', 'Digitando...');

        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        fetch('/assistente/api/chat/', {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json' },
            body: JSON.stringify({ mensagem: mensagem, sessao_id: sessaoId }),
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { ok: response.ok, data: data };
                });
            })
            .then(function (result) {
                indicador.remove();
                if (result.ok) {
                    adicionarMensagem('assistant', result.data.resposta);
                } else {
                    adicionarMensagem('erro', result.data.error || 'Erro ao consultar o assistente.');
                }
                if (!panel.classList.contains('aberto')) {
                    bubble.classList.add('tem-resposta');
                }
            })
            .catch(function () {
                indicador.remove();
                adicionarMensagem('erro', 'Não foi possível falar com o assistente. Verifique sua conexão.');
                if (!panel.classList.contains('aberto')) {
                    bubble.classList.add('tem-resposta');
                }
            })
            .finally(function () {
                enviando = false;
                botaoEnviar.disabled = false;
            });
    });
});
