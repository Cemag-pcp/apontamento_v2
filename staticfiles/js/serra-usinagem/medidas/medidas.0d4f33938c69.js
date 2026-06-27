document.addEventListener('DOMContentLoaded', function() {
    const checkboxes = document.querySelectorAll('.inspection-checkbox');
    const container = document.getElementById('medicoes-container');
    const measurementRowsWrapper = document.createElement('div');
    const measurementRowsInput = document.createElement('input');

    const storedValues = {
        serra: { medidas: [], valores: {} },
        usinagem: { medidas: [], valores: {} },
        furacao: { medidas: [], valores: {} }
    };

    const inspecaoTotalDiv = document.createElement('div');
    inspecaoTotalDiv.className = 'row mb-3';
    inspecaoTotalDiv.id = 'inspecaoTotal';
    inspecaoTotalDiv.innerHTML = `
        <div class="col-sm-12">
            <label for="inspecao_total">Necessita realizar a inspe&ccedil;&atilde;o 100%?</label>
            <select class="form-select" name="inspecao_total" id="inspecao_total">
                <option value="" selected hidden disabled></option>
                <option value="Nao">N&atilde;o</option>
                <option value="não" hidden>N&atilde;o</option>
                <option value="Sim">Sim</option>
            </select>
        </div>
    `;

    measurementRowsWrapper.className = 'row mb-3';
    measurementRowsWrapper.id = 'measurementRowsWrapper';
    measurementRowsWrapper.innerHTML = `
        <div class="col-md-4">
            <label for="measurementRowsCount" class="form-label">Quantidade de linhas por tabela</label>
            <small class="d-block text-muted mb-2">Ajuste quantas linhas devem aparecer nas tabelas de medi&ccedil;&atilde;o.</small>
        </div>
    `;
    measurementRowsInput.type = 'number';
    measurementRowsInput.className = 'form-control';
    measurementRowsInput.id = 'measurementRowsCount';
    measurementRowsInput.min = '1';
    measurementRowsInput.value = '3';
    measurementRowsWrapper.querySelector('.col-md-4').appendChild(measurementRowsInput);

    container.appendChild(measurementRowsWrapper);
    container.appendChild(inspecaoTotalDiv);

    function getQuantidadeProduzida() {
        return Math.max(1, parseInt(document.getElementById('pecasProduzidas').value, 10) || 1);
    }

    function getDefaultNumberOfRows() {
        const qtdProduzida = getQuantidadeProduzida();
        return qtdProduzida >= 3 ? 3 : qtdProduzida;
    }

    function getMeasurementRowsCount() {
        const maxRows = getQuantidadeProduzida();
        const currentValue = parseInt(measurementRowsInput.value, 10) || getDefaultNumberOfRows();
        return Math.max(1, Math.min(maxRows, currentValue));
    }

    function syncMeasurementRowsInput(desiredRows, shouldRender = true) {
        const maxRows = getQuantidadeProduzida();
        const sanitizedRows = Math.max(
            1,
            Math.min(maxRows, parseInt(desiredRows, 10) || getDefaultNumberOfRows())
        );

        measurementRowsInput.min = '1';
        measurementRowsInput.max = String(maxRows);
        measurementRowsInput.value = String(sanitizedRows);

        if (shouldRender) {
            updateMeasurementSections();
        }
    }

    measurementRowsInput.addEventListener('change', function() {
        syncMeasurementRowsInput(this.value);
    });

    window.syncMeasurementRowsSerraUsinagem = function(desiredRows, shouldRender = true) {
        syncMeasurementRowsInput(desiredRows, shouldRender);
    };

    syncMeasurementRowsInput(getDefaultNumberOfRows(), false);
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

        document.querySelectorAll('.measurement-section').forEach(section => {
            section.remove();
        });

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

        document.querySelectorAll('.measurement-section input[type="number"]').forEach(input => {
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

                const rowCheckboxes = document.querySelectorAll(`input[name="${checkbox.name}"]`);
                storedValues[sectionType].valores[row].conformity = {
                    conforming: rowCheckboxes[0].checked,
                    nonConforming: rowCheckboxes[1].checked,
                    disabled: rowCheckboxes[0].disabled
                };
            }
        });
    }

    function restoreValues(type) {
        storedValues[type].medidas.forEach((medida, index) => {
            const input = document.querySelector(`.measurement-section[data-type="${type}"] input[name="medida-input-${index + 1}"]`);
            if (input && medida) {
                input.value = medida.value || '';
                input.disabled = medida.disabled || false;
            }
        });

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
                const rowCheckboxes = document.querySelectorAll(`input[name="${this.name}"]`);
                rowCheckboxes.forEach(cb => {
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
        const numberOfRows = getMeasurementRowsCount();

        section.innerHTML = `
            <div id="sectionMedicao${typeName}">
                <label class="form-label">Medidas especificadas em desenho t&eacute;cnico - (<span class="fw-bold">${typeName}</span>)</label>
                <div class="table-responsive">
                    <table class="table table-bordered inspection-table" style="width: 730px;">
                        <thead class="table-light">
                            <tr>
                                ${Array.from({ length: 8 }, (_, i) => `
                                    <th>
                                        <input type="text" placeholder="Medida"
                                            class="form-control medida-input"
                                            name="medida-input-${i + 1}"
                                            style="padding: 5px; font-size: 11px;">
                                    </th>
                                `).join('')}
                                <th style="font-size: 11px;">Conforme</th>
                                <th style="font-size: 11px;">N&atilde;o conforme</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${Array.from({ length: numberOfRows }, (_, rowNumber) => `
                                <tr>
                                    ${Array.from({ length: 8 }, (_, i) => `
                                        <td>
                                            <input type="number" step="0.01" class="form-control"
                                                placeholder="Valor" style="padding: 5px;
                                                font-size: 11px; box-shadow: 0 0 0 0;
                                                border: 0 none; outline: 0;"
                                                name="${type}_valor${rowNumber + 1}_${i + 1}">
                                        </td>
                                    `).join('')}
                                    <td>
                                        <div class="form-check">
                                            <input class="form-check-input conformity-check" type="checkbox"
                                                name="${type}_conformity${rowNumber + 1}" value="conforming">
                                        </div>
                                    </td>
                                    <td>
                                        <div class="form-check">
                                            <input class="form-check-input conformity-check" type="checkbox"
                                                name="${type}_conformity${rowNumber + 1}" value="nonConforming">
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
