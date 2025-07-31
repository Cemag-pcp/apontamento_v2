document.addEventListener('DOMContentLoaded', function() {
    const checkboxes = document.querySelectorAll('.inspection-checkbox');
    const container = document.getElementById('medicoes-container');
    
    // Objeto para armazenar os valores preenchidos
    const storedValues = {
        serra: { medidas: [], valores: {} },
        usinagem: { medidas: [], valores: {} },
        furacao: { medidas: [], valores: {} }
    };
    
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const inspectionType = this.id.replace('checkbox-inspecao-', '');
            
            if (!this.checked) {
                // Quando desmarca um checkbox de inspeção
                resetConformityForType(inspectionType);
            }
            
            updateMeasurementSections(); // Sua função existente
            updateConformityCounts(); // Atualiza a visibilidade da seção
        });
    });
    
    function updateMeasurementSections() {
        // Salva os valores atuais antes de recriar as seções
        saveCurrentValues();
        
        // Limpa o container
        container.innerHTML = '';
        
        // Adiciona as seções conforme os checkboxes marcados
        if (document.getElementById('checkbox-inspecao-serra').checked) {
            container.appendChild(createMeasurementSection('serra'));
        }
        
        if (document.getElementById('checkbox-inspecao-usinagem').checked) {
            container.appendChild(createMeasurementSection('usinagem'));
        }
        
        if (document.getElementById('checkbox-inspecao-furacao').checked) {
            container.appendChild(createMeasurementSection('furacao'));
        }
        
        // Adiciona a seção de inspeção 100% se houver pelo menos uma seção
        if (container.children.length > 0) {
            const inspecaoTotalDiv = document.createElement('div');
            inspecaoTotalDiv.className = 'row mb-3';
            inspecaoTotalDiv.id = 'inspecaoTotal';
            inspecaoTotalDiv.innerHTML = `
                <div class="col-sm-12">
                    <label for="inspecao_total">Necessita realizar a inspeção 100%?</label>
                    <select class="form-select" name="inspecao_total" id="inspecao_total">
                        <option value="" selected hidden disabled></option>
                        <option value="Não">Não</option>
                        <option value="Sim">Sim</option>
                    </select>
                </div>
            `;
            container.appendChild(inspecaoTotalDiv);
        }
    }
    
    function saveCurrentValues() {
        // Salva os valores dos inputs de medida (cabeçalho da tabela)
        document.querySelectorAll('.medida-input').forEach(input => {
            const sectionType = input.closest('.measurement-section').dataset.type;
            const index = Array.from(input.parentElement.parentElement.children).indexOf(input.parentElement);
            storedValues[sectionType].medidas[index] = input.value;
        });
        
        // Salva os valores das medições
        document.querySelectorAll('input[type="number"]').forEach(input => {
            const nameParts = input.name.split('_');
            if (nameParts.length === 3) {
                const sectionType = nameParts[0];
                const row = nameParts[1].replace('valor', '');
                const col = nameParts[2];
                
                if (!storedValues[sectionType].valores[row]) {
                    storedValues[sectionType].valores[row] = {};
                }
                storedValues[sectionType].valores[row][col] = input.value;
            }
        });
        
        // Salva os estados dos checkboxes de conformidade
        document.querySelectorAll('.conformity-check').forEach(checkbox => {
            const nameParts = checkbox.name.split('_');
            if (nameParts.length === 2) {
                const sectionType = nameParts[0];
                const row = nameParts[1].replace('conformity', '');
                
                if (!storedValues[sectionType].valores[row]) {
                    storedValues[sectionType].valores[row] = {};
                }
                storedValues[sectionType].valores[row].conformity = checkbox.checked ? checkbox.value : '';
            }
        });
    }
    
    function createMeasurementSection(type) {
        const section = document.createElement('div');
        section.className = 'mb-4 measurement-section';
        section.dataset.type = type;
        
        const typeName = type === 'serra' ? 'Serra' : type === 'usinagem' ? 'Usinagem' : 'Furação';
        
        section.innerHTML = `
            <div id="sectionMedicao${typeName}">
                <label class="form-label">Medidas especificadas em desenho técnico - (<span class="fw-bold">${typeName}</span>)</label>
                <div class="table-responsive">
                    <table class="table table-bordered inspection-table">
                        <thead class="table-light">
                            <tr>
                                ${createHeaderCells(type)}
                            </tr>
                        </thead>
                        <tbody>
                            ${createMeasurementRow(1, type)}
                            ${createMeasurementRow(2, type)}
                            ${createMeasurementRow(3, type)}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        
        return section;
    }
    
    function createHeaderCells(type) {
        let headerCells = '';
        for (let i = 1; i <= 4; i++) {
            const medidaValue = storedValues[type].medidas[i-1] || '';
            headerCells += `
                <th>
                    <input type="text" placeholder="Medida ${i}" 
                           class="form-control medida-input" 
                           name="medida-input-${i}"
                           style="padding: 5px;"
                           value="${medidaValue}">
                </th>
            `;
        }
        headerCells += `
            <th style="font-size: 11px;">Conforme</th>
            <th style="font-size: 11px;">Não conforme</th>
        `;
        return headerCells;
    }
    
    function createMeasurementRow(rowNumber, type) {
        const rowData = storedValues[type].valores[rowNumber] || {};
        
        let cells = '';
        for (let i = 1; i <= 4; i++) {
            const value = rowData[i] || '';
            cells += `
                <td>
                    <input type="number" step="0.01" class="form-control" 
                           placeholder="Valor" style="padding: 5px;" 
                           name="${type}_valor${rowNumber}_${i}"
                           value="${value}">
                </td>
            `;
        }
        
        const conformingChecked = rowData.conformity === 'conforming' ? 'checked' : '';
        const nonConformingChecked = rowData.conformity === 'nonConforming' ? 'checked' : '';
        
        cells += `
            <td>
                <div class="form-check">
                    <input class="form-check-input conformity-check" type="checkbox" 
                           name="${type}_conformity${rowNumber}" value="conforming" 
                           ${conformingChecked}>
                </div>
            </td>
            <td>
                <div class="form-check">
                    <input class="form-check-input conformity-check" type="checkbox" 
                           name="${type}_conformity${rowNumber}" value="nonConforming" 
                           ${nonConformingChecked}>
                </div>
            </td>
        `;
        
        return `<tr>${cells}</tr>`;
    }
    

    updateConformityCounts();
    
    // Adiciona evento para os checkboxes de conformidade (impedir marcar ambos)
    document.addEventListener('change', function(e) {
        if (e.target && e.target.classList.contains('conformity-check')) {
            // Garante que apenas um checkbox por linha está marcado
            const checkboxes = document.querySelectorAll(`input[name="${e.target.name}"]`);
            if (e.target.checked) {
                checkboxes.forEach(cb => {
                    if (cb !== e.target) cb.checked = false;
                });
            }
            updateConformityCounts();
        }
    });
});