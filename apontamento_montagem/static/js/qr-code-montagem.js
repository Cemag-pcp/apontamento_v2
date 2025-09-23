document.addEventListener('DOMContentLoaded', function () {
    const modalElement = document.getElementById('qrScannerModal');
    let html5QrcodeScanner;

    function startScanner() {
        // Se o scanner não foi inicializado, cria uma nova instância
        if (!html5QrcodeScanner) {
            html5QrcodeScanner = new Html5Qrcode("qr-reader");
        }
        
        // Limpa qualquer resultado anterior e garante que o leitor esteja visível
        document.getElementById('qr-reader-results').innerHTML = '';
        document.getElementById('qr-reader').style.display = 'block';

        const config = { 
            fps: 10, 
            qrbox: { width: 250, height: 250 },
            experimentalFeatures: {
                useBarCodeDetectorIfSupported: true
            },
            facingMode: "environment" 
        };

        html5QrcodeScanner.start({ facingMode: "environment" }, config, onScanSuccess, onScanFailure)
            .catch(err => {
                console.error("Não foi possível iniciar o leitor de QR Code.", err);
                const modal = bootstrap.Modal.getInstance(modalElement);
                if(modal) modal.hide();
                Swal.fire({
                    icon: 'error',
                    title: 'Erro ao Iniciar Câmera',
                    text: 'Não foi possível acessar a câmera. Por favor, verifique as permissões no seu navegador.'
                });
            });
    }
    
    // Função para validar se o texto é uma URL HTTP/HTTPS
    function isValidHttpUrl(string) {
        try {
            const newUrl = new URL(string);
            return newUrl.protocol === 'http:' || newUrl.protocol === 'https:';
        } catch (_) {
            return false;
        }
    }

    // Função chamada quando um QR Code é lido com sucesso
    function onScanSuccess(decodedText, decodedResult) {
        console.log(`Scan result: ${decodedText}`, decodedResult);

        // Para o scanner
        html5QrcodeScanner.stop().then(() => {
            console.log("Scanner parado com sucesso.");

            // Esconde o leitor de QR code para não ficar atrás do SweetAlert
            document.getElementById('qr-reader').style.display = 'none';

            if (isValidHttpUrl(decodedText)) {
                // Se for uma URL válida, mostra o loading e redireciona
                Swal.fire({
                    title: 'QR Code Válido!',
                    text: 'Redirecionando...',
                    icon: 'success',
                    showConfirmButton: false,
                    allowOutsideClick: false,
                    didOpen: () => {
                        Swal.showLoading();
                        // Inicia o redirecionamento imediatamente
                        window.location.href = decodedText;
                    }
                });
            } else {
                // "Em caso de erro" (não é uma URL válida)
                Swal.fire({
                    title: 'Conteúdo Inválido',
                    html: `O QR Code não contém um link válido.<br><br><b>Conteúdo Lido:</b> <span class="text-break">${decodedText}</span>`,
                    icon: 'error',
                    showCancelButton: false, 
                    confirmButtonColor: '#0d6efd',
                    confirmButtonText: '<i class="bi bi-qr-code-scan me-1"></i> Ler Novamente',
                    allowOutsideClick: false
                }).then((result) => {
                    if (result.isConfirmed) {
                        // Se o usuário clicar em "Ler Novamente"
                        startScanner();
                    }
                });
            }

        }).catch(err => {
            console.error("Erro ao parar o scanner:", err);
            Swal.fire({
                icon: 'error',
                title: 'Oops...',
                text: 'Ocorreu um erro ao parar o scanner!'
            });
        });
    }

    // Função para tratar erros de leitura (chamada continuamente quando nenhum QR code é encontrado)
    function onScanFailure(error) {
        // Deixamos em branco para não exibir alertas contínuos de falha na leitura.
    }

    // Evento disparado quando o modal do scanner é aberto
    modalElement.addEventListener('shown.bs.modal', startScanner);

    // Evento disparado quando o modal é fechado
    modalElement.addEventListener('hidden.bs.modal', function () {
        // Limpa os resultados ao fechar, para que na próxima vez comece do zero
        document.getElementById('qr-reader-results').innerHTML = '';
        document.getElementById('qr-reader').style.display = 'block';

        if (html5QrcodeScanner && html5QrcodeScanner.isScanning) {
            html5QrcodeScanner.stop()
                .then(() => console.log("Leitor de QR Code parado com sucesso."))
                .catch(err => console.error("Falha ao parar o leitor de QR Code.", err));
        }
    });

});