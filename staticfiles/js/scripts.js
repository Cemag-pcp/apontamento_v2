/*!
    * Start Bootstrap - SB Admin v7.0.7 (https://startbootstrap.com/template/sb-admin)
    * Copyright 2013-2023 Start Bootstrap
    * Licensed under MIT (https://github.com/StartBootstrap/startbootstrap-sb-admin/blob/master/LICENSE)
    */
    // 
// Scripts
// 

window.addEventListener('DOMContentLoaded', event => {
    window.getAppLoaderHtml = ({ size = 72, inline = false } = {}) => `
        <div class="app-loader-wrap${inline ? ' inline' : ''}">
            <dotlottie-wc
                src="https://lottie.host/20544d25-5e68-435f-a616-08e988e50829/bRE5PyuMwW.lottie"
                style="width: ${size}px; height: ${size}px"
                autoplay
                loop
            ></dotlottie-wc>
        </div>`;
    window.getAppLoadingSwalOptions = ({ title = 'Carregando...', text = '', size = 92 } = {}) => ({
        title,
        html: `
            ${window.getAppLoaderHtml({ size })}
            ${text ? `<div class="text-muted mt-2">${text}</div>` : ''}
        `,
        showConfirmButton: false,
        allowOutsideClick: false,
    });

    document.querySelectorAll('.app-loader-placeholder').forEach(element => {
        const size = Number(element.dataset.size || 72);
        const inline = element.dataset.inline === 'true';
        element.innerHTML = window.getAppLoaderHtml({ size, inline });
    });

    // Toggle the side navigation
    const sidebarToggle = document.body.querySelector('#sidebarToggle');
    if (sidebarToggle) {
        const sidebarState = localStorage.getItem('sb|sidebar-toggle');
        if (sidebarState === 'true') {
            document.body.classList.add('sb-sidenav-toggled');
        } else if (sidebarState === 'false') {
            document.body.classList.remove('sb-sidenav-toggled');
        }
        sidebarToggle.addEventListener('click', event => {
            event.preventDefault();
            document.body.classList.toggle('sb-sidenav-toggled');
            localStorage.setItem('sb|sidebar-toggle', document.body.classList.contains('sb-sidenav-toggled'));
        });
    }

});
