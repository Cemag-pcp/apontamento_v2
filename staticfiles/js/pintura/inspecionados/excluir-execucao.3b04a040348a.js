document.getElementById("confirmar-exclusao").addEventListener("click", function(event) {
    const spinnerConfirm = this.querySelector(".spinner-border")
    const idDadosExecucao = this.getAttribute("data-execucao-id");
    const idInspecao = this.getAttribute("data-inspecao-id");
    const primeiraExecucao = this.getAttribute("primeira-execucao");

    this.disabled = true;
    spinnerConfirm.style.display = "block";

    const Toast = Swal.mixin({
        toast: true,
        position: "bottom-end",
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
        didOpen: (toast) => {
          toast.onmouseenter = Swal.stopTimer;
          toast.onmouseleave = Swal.resumeTimer;
        }
    });
    
    const url = new URL(`/inspecao/api/delete-execucao`, window.location.origin);
    url.searchParams.append('idDadosExecucao', idDadosExecucao);
    url.searchParams.append('idInspecao', idInspecao);
    url.searchParams.append('primeiraExecucao', primeiraExecucao);
    
    // Configuração da requisição
    fetch(url.toString(), {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Erro ao excluir execução');
        }
        return response.json();
    })
    .then(data => {
        // Fecha o modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('modal-excluir-execucao'));
        modal.hide();
        
        Toast.fire({
            icon: "success",
            title: "Execução excluída com sucesso"
        });
        buscarItensInspecao(1);
        buscarItensReinspecao(1);
        buscarItensInspecionados(1);
    })
    .catch(error => {
        console.error('Erro:', error);
        Toast.fire({
            icon: "error",
            title: "Falha ao excluir execução: " + error.message
        });
    })
    .finally(f => {
        this.disabled = false;
        spinnerConfirm.style.display = "none";
    })
});