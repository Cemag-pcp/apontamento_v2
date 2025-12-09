const loginButton = document.getElementById('loginButton');
const loginForm = document.getElementById('loginForm');

// Desabilita o botão de login ao fazer o submit do formulário
loginForm.addEventListener('submit', function() {
    loginButton.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Entrando...';
    loginButton.disabled = true;
});