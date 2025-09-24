document.addEventListener('DOMContentLoaded', function () {
    const modalElement = document.getElementById('qrScannerModal');
    let html5QrcodeScanner;

    function startScanner() {
        if (!html5QrcodeScanner) {
            html5QrcodeScanner = new Html5Qrcode("qr-reader");
        }
        
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
    
    function isValidHttpUrl(string) {
        try {
            const newUrl = new URL(string);
            return newUrl.protocol === 'http:' || newUrl.protocol === 'https:';
        } catch (_) {
            return false;
        }
    }

    function onScanSuccess(decodedText, decodedResult) {
        console.log(`Scan result: ${decodedText}`, decodedResult);

        html5QrcodeScanner.stop().then(() => {
            console.log("Scanner parado com sucesso.");
            document.getElementById('qr-reader').style.display = 'none';

            if (isValidHttpUrl(decodedText)) {
                Swal.fire({
                    title: 'Setor de Destino',
                    html: `QR Code lido com sucesso. Selecione o setor de destino.`,
                    icon: 'question',
                    showDenyButton: true,
                    showCancelButton: true,
                    confirmButtonText: '<i class="fas fa-hammer me-1"></i> Solda',
                    denyButtonText: '<i class="fas fa-cogs me-1"></i> Montagem',
                    cancelButtonText: '<i class="bi bi-qr-code-scan me-1"></i> Ler Novamente',
                    confirmButtonColor: '#0d6efd',
                    denyButtonColor: '#198754',
                    cancelButtonColor: '#6c757d',
                    allowOutsideClick: false
                }).then((result) => {
                    let finalUrl = '';
                    let setor = '';

                    if (result.isConfirmed) {
                        // Botão Solda: substitui 'montagem' por 'solda' na URL
                        finalUrl = decodedText.replace(/montagem/gi, 'solda');
                        setor = 'Solda';
                    } else if (result.isDenied) {
                        // Botão Montagem: mantém a URL original
                        finalUrl = decodedText;
                        setor = 'Montagem';
                    } else if (result.isDismissed) {
                        // Botão Ler Novamente
                        startScanner();
                        return;
                    }

                    // Se escolheu Solda ou Montagem, redireciona
                    if (finalUrl) {
                        Swal.fire({
                            title: `Redirecionando para ${setor}...`,
                            icon: 'success',
                            showConfirmButton: false,
                            allowOutsideClick: false,
                            didOpen: () => {
                                Swal.showLoading();
                                window.location.href = finalUrl;
                            }
                        });
                    }
                });
            } else {
                // Se não for uma URL válida, mantém o comportamento de erro
                Swal.fire({
                    title: 'Conteúdo Inválido',
                    html: `O QR Code não contém um link válido.<br><br><b>Conteúdo Lido:</b> <span class="text-break">${decodedText}</span>`,
                    icon: 'error',
                    confirmButtonColor: '#0d6efd',
                    confirmButtonText: '<i class="bi bi-qr-code-scan me-1"></i> Ler Novamente',
                    allowOutsideClick: false
                }).then((result) => {
                    if (result.isConfirmed) {
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

    function onScanFailure(error) {
        // Deixamos em branco para não poluir o console com falhas de leitura.
    }

    modalElement.addEventListener('shown.bs.modal', startScanner);

    modalElement.addEventListener('hidden.bs.modal', function () {
        document.getElementById('qr-reader-results').innerHTML = '';
        document.getElementById('qr-reader').style.display = 'block';

        if (html5QrcodeScanner && html5QrcodeScanner.isScanning) {
            html5QrcodeScanner.stop()
                .then(() => console.log("Leitor de QR Code parado."))
                .catch(err => console.error("Falha ao parar o leitor.", err));
        }
    });

});