document.addEventListener("DOMContentLoaded", () => {
    document.addEventListener("click", function(event) {
        if (event.target.classList.contains('btn-voltar-historico-inspecao')) {
            
            const setor = event.target.getAttribute('data-setor');
            
            const modalClose = document.getElementById(`modal-causas-historico-${setor}`)

            const bootstrapModal = bootstrap.Modal.getInstance(modalClose);
            bootstrapModal.hide();

            const modalHistorico = document.getElementById(`modal-historico-${setor}`)

            const modal = new bootstrap.Modal(modalHistorico);
            modal.show();
        }
    })
})