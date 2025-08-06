document.addEventListener('DOMContentLoaded', function() {
    const checkboxes = document.querySelectorAll('.inspection-checkbox');
    const container = document.getElementById('medicoes-container');
    
    // Objeto para armazenar os valores preenchidos
    const storedValues = {
        serra: { medidas: [], valores: {} },
        usinagem: { medidas: [], valores: {} },
        furacao: { medidas: [], valores: {} }
    };

    // Cria o elemento inspecaoTotalDiv uma vez, fora da função updateMeasurementSections
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

    updateMeasurementSections();
    
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const inspectionType = this.id.replace('checkbox-inspecao-', '');
            
            if (!this.checked) {
                resetConformityForType(inspectionType);
            }
            
            updateMeasurementSections();
            updateConformityCounts();
        });
    });
    
    function updateMeasurementSections() {
        saveCurrentValues();
        
        // Remove apenas as seções de medição, não o inspecaoTotalDiv
        document.querySelectorAll('.measurement-section').forEach(section => {
            section.remove();
        });
        
        // Adiciona as seções de medição antes do inspecaoTotalDiv
        if (document.getElementById('checkbox-inspecao-serra').checked) {
            container.insertBefore(createMeasurementSection('serra'), inspecaoTotalDiv);
            restoreValues('serra');
        }
        
        if (document.getElementById('checkbox-inspecao-usinagem').checked) {
            container.insertBefore(createMeasurementSection('usinagem'), inspecaoTotalDiv);
            restoreValues('usinagem');
        }
        
        if (document.getElementById('checkbox-inspecao-furacao').checked) {
            container.insertBefore(createMeasurementSection('furacao'), inspecaoTotalDiv);
            restoreValues('furacao');
        }
        
        setupConformityCheckboxes();
    }
    
    function saveCurrentValues() {
        document.querySelectorAll('.medida-input').forEach(input => {
            const sectionType = input.closest('.measurement-section').dataset.type;
            const index = Array.from(input.parentElement.parentElement.children).indexOf(input.parentElement);
            storedValues[sectionType].medidas[index] = {
                value: input.value,
                disabled: input.disabled
            };
        });
        
        document.querySelectorAll('input[type="number"]').forEach(input => {
            const nameParts = input.name.split('_');
            if (nameParts.length === 3) {
                const sectionType = nameParts[0];
                const row = nameParts[1].replace('valor', '');
                const col = nameParts[2];
                
                if (!storedValues[sectionType].valores[row]) {
                    storedValues[sectionType].valores[row] = {};
                }
                storedValues[sectionType].valores[row][col] = {
                    value: input.value,
                    disabled: input.disabled
                };
            }
        });
        
        document.querySelectorAll('.conformity-check').forEach(checkbox => {
            const nameParts = checkbox.name.split('_');
            if (nameParts.length === 2) {
                const sectionType = nameParts[0];
                const row = nameParts[1].replace('conformity', '');
                
                if (!storedValues[sectionType].valores[row]) {
                    storedValues[sectionType].valores[row] = {};
                }
                
                const checkboxes = document.querySelectorAll(`input[name="${checkbox.name}"]`);
                storedValues[sectionType].valores[row].conformity = {
                    conforming: checkboxes[0].checked,
                    nonConforming: checkboxes[1].checked,
                    disabled: checkboxes[0].disabled
                };
            }
        });
    }
    
    function restoreValues(type) {
        // Restaura cabeçalhos (medidas)
        storedValues[type].medidas.forEach((medida, index) => {
            const input = document.querySelector(`.measurement-section[data-type="${type}"] input[name="medida-input-${index + 1}"]`);
            if (input && medida) {
                input.value = medida.value || '';
                input.disabled = medida.disabled || false;
            }
        });
        
        // Restaura valores numéricos e conformidade
        Object.entries(storedValues[type].valores).forEach(([row, values]) => {
            Object.entries(values).forEach(([key, value]) => {
                if (key === 'conformity') {
                    const conformingCheckbox = document.querySelector(
                        `.measurement-section[data-type="${type}"] input[name="${type}_conformity${row}"][value="conforming"]`
                    );
                    const nonConformingCheckbox = document.querySelector(
                        `.measurement-section[data-type="${type}"] input[name="${type}_conformity${row}"][value="nonConforming"]`
                    );
                    
                    if (conformingCheckbox && nonConformingCheckbox) {
                        conformingCheckbox.checked = value.conforming;
                        nonConformingCheckbox.checked = value.nonConforming;
                        // Adicione estas linhas para desabilitar os checkboxes
                        conformingCheckbox.disabled = value.disabled || false;
                        nonConformingCheckbox.disabled = value.disabled || false;
                    }
                } else {
                    const input = document.querySelector(`.measurement-section[data-type="${type}"] input[name="${type}_valor${row}_${key}"]`);
                    if (input && value) {
                        input.value = value.value || '';
                        input.disabled = value.disabled || false;
                    }
                }
            });
        });
    }

    function setupConformityCheckboxes() {
        document.querySelectorAll('.conformity-check').forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                const checkboxes = document.querySelectorAll(`input[name="${this.name}"]`);
                checkboxes.forEach(cb => {
                    if (cb !== this) cb.checked = false;
                });
                updateConformityCounts();
            });
        });
    }
    
    function createMeasurementSection(type) {
        const section = document.createElement('div');
        section.className = 'mb-4 measurement-section';
        section.dataset.type = type;
        
        const typeName = type === 'serra' ? 'Serra' : type === 'usinagem' ? 'Usinagem' : 'Furacao';
        
        // Obter quantidade produzida ou usar 3 como padrão
        const qtdProduzida = parseInt(document.getElementById('pecasProduzidas').value) || 0;
        const numberOfRows = qtdProduzida >= 3 ? 3 : Math.max(1, qtdProduzida); // Mínimo 1 linha
        
        section.innerHTML = `
            <div id="sectionMedicao${typeName}">
                <label class="form-label">Medidas especificadas em desenho técnico - (<span class="fw-bold">${typeName}</span>)</label>
                <div class="table-responsive">
                    <table class="table table-bordered inspection-table" style="width: 730px;">
                        <thead class="table-light">
                            <tr>
                                ${Array.from({length: 8}, (_, i) => `
                                    <th>
                                        <input type="text" placeholder="Medida" 
                                            class="form-control medida-input" 
                                            name="medida-input-${i+1}"
                                            style="padding: 5px; font-size: 11px;">
                                    </th>
                                `).join('')}
                                <th style="font-size: 11px;">Conforme</th>
                                <th style="font-size: 11px;">Não conforme</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${Array.from({length: numberOfRows}, (_, rowNumber) => `
                                <tr>
                                    ${Array.from({length: 8}, (_, i) => `
                                        <td>
                                            <input type="number" step="0.01" class="form-control" 
                                                placeholder="Valor" style="padding: 5px;
                                                font-size: 11px; box-shadow: 0 0 0 0;
                                                border: 0 none; outline: 0;" 
                                                name="${type}_valor${rowNumber+1}_${i+1}">
                                        </td>
                                    `).join('')}
                                    <td>
                                        <div class="form-check">
                                            <input class="form-check-input conformity-check" type="checkbox" 
                                                name="${type}_conformity${rowNumber+1}" value="conforming">
                                        </div>
                                    </td>
                                    <td>
                                        <div class="form-check">
                                            <input class="form-check-input conformity-check" type="checkbox" 
                                                name="${type}_conformity${rowNumber+1}" value="nonConforming">
                                        </div>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        
        return section;
    }

    updateConformityCounts();

});