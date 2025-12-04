document.addEventListener('DOMContentLoaded', function() {
    const deleteLinks = document.querySelectorAll('.delete-link');

    deleteLinks.forEach(function(deleteLink) {
        deleteLink.addEventListener('click', function(event) {
            const confirmDelete = confirm('Você quer mesmo excluir? Processo irreversível.');
            if (!confirmDelete) {
                event.preventDefault();
            }
        });
    });
});
