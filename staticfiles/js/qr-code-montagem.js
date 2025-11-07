document.addEventListener('DOMContentLoaded', function () {
    const modalElement = document.getElementById('qrScannerModal');
    let html5QrcodeScanner;
    let currentZoom = 2.0; // Variável para rastrear o zoom atual
    
    // =========================================================================
    // NOVIDADE: Função para aplicar o zoom dinamicamente
    // =========================================================================
    function applyDynamicZoom(zoomValue) {
        if (!html5QrcodeScanner || !html5QrcodeScanner.isScanning) {
            console.warn("Scanner não está rodando para aplicar zoom.");
            return;
        }
        
        // Aplica as novas restrições de zoom
        html5QrcodeScanner.applyVideoConstraints({
            advanced: [{ zoom: zoomValue }]
        }).then(() => {
            currentZoom = zoomValue;
            document.getElementById('current-zoom-level').textContent = zoomValue.toFixed(1);
            console.log(`Zoom ajustado para: ${zoomValue}x`);
        }).catch(e => {
            // Se o zoom não for suportado, desabilita os controles
            console.warn("Falha ao ajustar zoom. Recurso não suportado.", e);
            document.getElementById('zoom-controls').style.display = 'none';
        });
    }

    // =========================================================================
    // NOVIDADE: Configura o slider e aplica o zoom inicial
    // =========================================================================
    function setupZoomControls() {
        const slider = document.getElementById('zoom-slider');
        const zoomControlsDiv = document.getElementById('zoom-controls');

        // Mostra os controles
        zoomControlsDiv.style.display = 'block';

        // Garante que o slider comece no valor inicial que definimos para o zoom
        slider.value = currentZoom;
        document.getElementById('current-zoom-level').textContent = currentZoom.toFixed(1);

        // Evento para atualizar o zoom ao arrastar o slider
        slider.addEventListener('input', (e) => {
            const newZoom = parseFloat(e.target.value);
            applyDynamicZoom(newZoom);
        });
        
        // Aplica o zoom inicial de 2.0x
        applyDynamicZoom(currentZoom);
    }
    
    // =========================================================================
    // startScanner AGORA VAI CHAMAR setupZoomControls
    // =========================================================================
    function startScanner() {
    if (!html5QrcodeScanner) {
        html5QrcodeScanner = new Html5Qrcode("qr-reader");
    }
    document.getElementById('qr-reader-results').innerHTML = '';
    document.getElementById('qr-reader').style.display = 'block';

    // Seleção de câmera específica
    Html5Qrcode.getCameras().then(cameras => {
        if (!cameras.length) {
            Swal.fire({
                icon: 'error',
                title: 'Nenhuma câmera encontrada',
                text: 'Verifique se há uma câmera conectada ou disponível.'
            });
            return;
        }
        let selectedCam = cameras.find(cam =>
            
            cam.label.toLowerCase().includes("0") &&
            cam.label.toLowerCase().includes("facing back")
        );

        // Se não achou a principal, procura qualquer câmera traseira
        if (!selectedCam) {
            selectedCam = cameras.find(cam =>
                cam.label.toLowerCase().includes("back")
            );
        }

        // Se ainda não achou, procura por "traseira" (alguns dispositivos em português)
        if (!selectedCam) {
            selectedCam = cameras.find(cam =>
                cam.label.toLowerCase().includes("traseira")
            );
        }

        if (!selectedCam) {
            selectedCam = cameras[cameras.length - 1]; // fallback para a primeira câmera
            Swal.fire({
                icon: 'warning',
                title: 'Câmera padrão usada',
                text: 'Câmera "camera 0, facing back" não encontrada. Usando a primeira disponível.'
            });
        }

        html5QrcodeScanner.start(
            selectedCam.id,
            {
                fps: 10,
                qrbox: 250
            },
            onScanSuccess,
            onScanFailure
        ).then(setupZoomControls)
         .catch(err => {
            Swal.fire({
                icon: 'error',
                title: 'Erro ao iniciar câmera',
                text: err
            });
        });
    }).catch(err => {
        Swal.fire({
            icon: 'error',
            title: 'Erro ao listar câmeras',
            text: err
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
                // 1. Esconder o modal do QR Code
                const modal = bootstrap.Modal.getInstance(modalElement);
                if(modal) modal.hide();
                
                // 2. Adicionar parâmetro para sinalizar a seleção de setor na próxima página
                const url = new URL(decodedText);
                url.searchParams.set('selecao_setor', 'pendente');

                Swal.fire({
                    title: 'QR Code Lido!',
                    text: 'Processando informações de ordem...',
                    icon: 'success',
                    showConfirmButton: false,
                    allowOutsideClick: false,
                    timer: 1500, // Tempo suficiente para o usuário ver
                    didOpen: () => {
                        Swal.showLoading();
                        // Redireciona para o ordem-iniciar-qrcode.js (que está na URL lida, e agora com 'selecao_setor=pendente')
                        window.location.href = url.toString();
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