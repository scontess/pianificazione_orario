document.addEventListener("DOMContentLoaded", () => {
    const giorniDef = [
        { key: "lun", label: "Lunedì" },
        { key: "mar", label: "Martedì" },
        { key: "mer", label: "Mercoledì" },
        { key: "gio", label: "Giovedì" },
        { key: "ven", label: "Venerdì" }
    ];
    const ore = [1, 2, 3, 4, 5, 6];

    const paletteColori = [
        '#dc2626', '#ea580c', '#d97706', '#eab308', '#65a30d',
        '#16a34a', '#15803d', '#0d9488', '#0891b2', '#0284c7',
        '#2563eb', '#0369a1', '#4f46e5', '#7c3aed', '#5b21b6',
        '#c026d3', '#db2777', '#9d174d', '#9a3412', '#57534e'
    ];

    function getStileCardProf(profId, isFuoriCattedra) {
        const index = (parseInt(profId) || 0) % paletteColori.length;
        const coloreHex = paletteColori[index];

        if (!isFuoriCattedra) {
            return `background-color: ${coloreHex}; color: #ffffff; border: 1px solid ${coloreHex};`;
        } else {
            let r = parseInt(coloreHex.slice(1, 3), 16);
            let g = parseInt(coloreHex.slice(3, 5), 16);
            let b = parseInt(coloreHex.slice(5, 7), 16);

            return `background-color: rgba(${r}, ${g}, ${b}, 0.22); color: #1e293b; border: 2px dashed ${coloreHex}; font-weight: bold;`;
        }
    }

    let professoriData = [];
    let classiData = [];
    let orarioData = [];
    let vincoliData = [];
    let vincoliClassiData = [];
    let currentMondayStr = "";

    const weekPicker = document.getElementById("week-picker");
    if (weekPicker) {
        const today = new Date();
        currentMondayStr = getMondayString(today);
        weekPicker.value = currentMondayStr;

        weekPicker.addEventListener("change", (e) => {
            if (e.target.value) {
                const selectedDate = new Date(e.target.value);
                currentMondayStr = getMondayString(selectedDate);
                weekPicker.value = currentMondayStr;
                loadData();
            }
        });
    }

    window.esportaTabelloneCSV = async function () {
        try {
            const url = typeof currentMondayStr !== 'undefined' ? `/orario?settimana=${currentMondayStr}` : '/orario';
            const response = await fetch(url);
            const data = await response.json();

            if (!data || data.length === 0) {
                alert("Nessun dato presente nel tabellone per questa settimana!");
                return;
            }

            let csvRows = ["Settimana;Giorno;Ora;Classe;Professore;Materia"];

            data.forEach(item => {
                const settimana = item.settimana || (typeof currentMondayStr !== 'undefined' ? currentMondayStr : '');
                const giorno = item.giorno || '';
                const ora = item.ora || '';
                const classe = (item.classe_nome || '').replace(/"/g, '""');
                const prof = `${item.prof_cognome || ''} ${item.prof_nome || ''}`.replace(/"/g, '""');
                const materia = (item.materia_nome || '').replace(/"/g, '""');

                csvRows.push(`${settimana};${giorno};${ora};"${classe}";"${prof}";"${materia}"`);
            });

            const csvString = "\uFEFF" + csvRows.join("\n");
            const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
            const blobUrl = URL.createObjectURL(blob);

            const link = document.createElement("a");
            link.href = blobUrl;
            link.setAttribute("download", `orario_scuola_${typeof currentMondayStr !== 'undefined' ? currentMondayStr : 'generale'}.csv`);

            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(blobUrl);

        } catch (error) {
            console.error("Errore durante l'esportazione CSV:", error);
            alert("Si è verificato un errore durante l'esportazione del file CSV.");
        }
    };

    window.esportaTabelloneCompleto = async function () {
        try {
            if (typeof currentMondayStr === 'undefined' || !currentMondayStr) {
                alert("⚠️ Seleziona prima una settimana di riferimento tramite il selettore delle date.");
                return;
            }

            const url = `/orario?settimana=${currentMondayStr}`;
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error("Errore di connessione al server durante il recupero dell'orario.");
            }

            const dataOrario = await response.json();

            if (!dataOrario || dataOrario.length === 0) {
                alert("Nessun dato presente nel tabellone per la settimana selezionata!");
                return;
            }

            const classiCorrenti = typeof classiData !== 'undefined' ? classiData : [];
            const profData = typeof professoriData !== 'undefined' ? professoriData : [];
            const daysWithDates = typeof getDaysWithDates === 'function' ? getDaysWithDates(currentMondayStr) : [];
            const oreList = [1, 2, 3, 4, 5, 6];

            if (classiCorrenti.length === 0) {
                alert("❌ Errore: Nessuna classe disponibile per l'esportazione.");
                return;
            }

            const paletteColoriExcel = [
                '#2563eb', '#059669', '#d97706', '#7c3aed',
                '#db2777', '#0891b2', '#ca8a04', '#ea580c', '#4f46e5'
            ];
            const totalColumns = 2 + classiCorrenti.length;

            let excelHtml = `
            <html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">
            <head>
                <meta charset="utf-8">
                <style>
                    table { border-collapse: collapse; font-family: Arial, sans-serif; font-size: 10pt; }
                    th, td { border: 1px solid #cbd5e1; padding: 6px; text-align: center; vertical-align: middle; }
                    th { background-color: #0f172a; color: #ffffff; font-weight: bold; }
                    .title-row { background-color: #1e293b; color: #ffffff; font-size: 12pt; font-weight: bold; text-align: center; height: 35px; }
                    .header-main { background-color: #0f172a; color: #ffffff; font-weight: bold; }
                    .day-cell { background-color: #f1f5f9; font-weight: bold; color: #0f172a; text-align: center; vertical-align: middle; }
                    .hour-cell { background-color: #e2e8f0; font-weight: bold; color: #334155; }
                </style>
            </head>
            <body>
                <table>
                    <thead>
                        <tr>
                            <th colspan="${totalColumns}" class="title-row">
                                Orario Scolastico - Settimana del ${currentMondayStr}
                            </th>
                        </tr>
                        <tr>
                            <th style="width: 130px;" class="header-main">Classe / Data</th>
                            <th style="width: 70px;" class="header-main">Ora</th>
            `;

            classiCorrenti.forEach(cls => {
                excelHtml += `<th style="width: 160px;" class="header-main">${cls.nome}</th>`;
            });
            excelHtml += `</tr></thead><tbody>`;

            daysWithDates.forEach(g => {
                oreList.forEach((o, index) => {
                    excelHtml += `<tr>`;
                    if (index === 0) {
                        excelHtml += `<td class="day-cell" rowspan="${oreList.length}">${g.label}</td>`;
                    }
                    excelHtml += `<td class="hour-cell">${o}° Ora</td>`;

                    classiCorrenti.forEach(cls => {
                        const assigned = dataOrario.find(oItem =>
                            oItem.classeid === cls.id && oItem.giorno === g.key && oItem.ora === o
                        );

                        if (assigned) {
                            const isFuoriCattedra = !profData.some(item =>
                                item.profid == assigned.profid &&
                                item.materiaid == assigned.materia_id &&
                                item.classeid == assigned.classeid
                            );

                            const colorIndex = (parseInt(assigned.profid) || 0) % paletteColoriExcel.length;
                            const coloreHex = paletteColoriExcel[colorIndex];

                            let cellStyle = !isFuoriCattedra
                                ? `background-color: ${coloreHex}; color: #ffffff; font-weight: bold;`
                                : `background-color: #fef3c7; color: #92400e; border: 2px dashed ${coloreHex}; font-weight: bold;`;

                            let noteFc = isFuoriCattedra ? "<br><span style='font-size:8pt; font-style:italic;'>(Fuori Cattedra)</span>" : "";

                            excelHtml += `<td style="${cellStyle}">
                            ${assigned.materia_nome || ''}<br>
                            <span style="font-size:9pt; font-weight:normal;">${assigned.prof_nome || ''} ${assigned.prof_cognome || ''}</span>
                            ${noteFc}
                        </td>`;
                        } else {
                            excelHtml += `<td></td>`;
                        }
                    });
                    excelHtml += `</tr>`;
                });
            });

            excelHtml += `</tbody></table></body></html>`;

            const excelBlob = new Blob([excelHtml], { type: 'application/vnd.ms-excel;charset=utf-8;' });
            const excelUrl = URL.createObjectURL(excelBlob);
            const excelLink = document.createElement("a");
            excelLink.href = excelUrl;
            excelLink.setAttribute("download", `orario_tabellone_${currentMondayStr}.xls`);
            document.body.appendChild(excelLink);
            excelLink.click();
            document.body.removeChild(excelLink);
            URL.revokeObjectURL(excelUrl);

            let pdfHtml = `
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Orario Scolastico - Settimana del ${currentMondayStr}</title>
                <style>
                    @page { size: A3 landscape; margin: 10mm; }
                    body { font-family: Arial, sans-serif; font-size: 9pt; margin: 0; padding: 10px; background: #fff; }
                    table { width: 100%; border-collapse: collapse; table-layout: fixed; }
                    th, td { border: 1px solid #cbd5e1; padding: 5px 3px; text-align: center; vertical-align: middle; word-wrap: break-word; }
                    th { background-color: #0f172a !important; color: #ffffff !important; font-weight: bold; font-size: 9pt; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
                    .title-row { background-color: #1e293b !important; color: #ffffff !important; font-size: 11pt; font-weight: bold; padding: 8px; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
                    .day-cell { background-color: #f1f5f9 !important; font-weight: bold; color: #0f172a; font-size: 10pt; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
                    .hour-cell { background-color: #e2e8f0 !important; font-weight: bold; color: #334155; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
                    .card-cell { font-size: 8.5pt; border-radius: 4px; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
                    .fc-cell { background-color: #fef3c7 !important; color: #92400e !important; border: 2px dashed #d97706 !important; font-weight: bold; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
                </style>
            </head>
            <body>
                <table>
                    <thead>
                        <tr>
                            <th colspan="${totalColumns}" class="title-row">
                                Orario Scolastico - Settimana del ${currentMondayStr}
                            </th>
                        </tr>
                        <tr>
                            <th style="width: 110px;">Classe / Data</th>
                            <th style="width: 65px;">Ora</th>
            `;

            classiCorrenti.forEach(cls => {
                pdfHtml += `<th>${cls.nome}</th>`;
            });
            pdfHtml += `</tr></thead><tbody>`;

            daysWithDates.forEach(g => {
                oreList.forEach((o, index) => {
                    pdfHtml += `<tr>`;
                    if (index === 0) {
                        pdfHtml += `<td class="day-cell" rowspan="${oreList.length}">${g.label}</td>`;
                    }
                    pdfHtml += `<td class="hour-cell">${o}° Ora</td>`;

                    classiCorrenti.forEach(cls => {
                        const assigned = dataOrario.find(oItem =>
                            oItem.classeid === cls.id && oItem.giorno === g.key && oItem.ora === o
                        );

                        if (assigned) {
                            const isFuoriCattedra = !profData.some(item =>
                                item.profid == assigned.profid &&
                                item.materiaid == assigned.materia_id &&
                                item.classeid == assigned.classeid
                            );

                            const colorIndex = (parseInt(assigned.profid) || 0) % paletteColoriExcel.length;
                            const coloreHex = paletteColoriExcel[colorIndex];

                            if (!isFuoriCattedra) {
                                pdfHtml += `
                                <td class="card-cell" style="background-color: ${coloreHex} !important; color: #ffffff !important; font-weight: bold;">
                                    ${assigned.materia_nome || ''}<br>
                                    <span style="font-weight: normal; font-size: 7.5pt;">${assigned.prof_nome || ''} ${assigned.prof_cognome || ''}</span>
                                </td>`;
                            } else {
                                pdfHtml += `
                                <td class="card-cell fc-cell">
                                    ${assigned.materia_nome || ''}<br>
                                    <span style="font-weight: normal; font-size: 7.5pt;">${assigned.prof_nome || ''} ${assigned.prof_cognome || ''}</span>
                                    <br><span style="font-size: 7pt; font-style: italic;">(Fuori Cattedra)</span>
                                </td>`;
                            }
                        } else {
                            pdfHtml += `<td></td>`;
                        }
                    });

                    pdfHtml += `</tr>`;
                });
            });

            pdfHtml += `</tbody></table></body></html>`;

            const printWindow = window.open('', '_blank');
            if (printWindow) {
                printWindow.document.write(pdfHtml);
                printWindow.document.close();
                printWindow.focus();
                setTimeout(() => {
                    printWindow.print();
                }, 500);
            } else {
                alert("⚠️ Il browser ha bloccato l'apertura della finestra popup per il PDF. Consenti i popup per questo sito.");
            }

        } catch (error) {
            console.error("Errore durante l'esportazione completa:", error);
            alert("Si è verificato un errore durante l'esportazione: " + error.message);
        }
    };

    window.esportaTabelloneExcelFormattato = window.esportaTabelloneCompleto;

    function getMondayString(d) {
        d = new Date(d);
        const day = d.getDay();
        const diff = d.getDate() - day + (day === 0 ? -6 : 1);
        const monday = new Date(d.setDate(diff));
        return monday.toISOString().split('T')[0];
    }

    function getDaysWithDates(mondayStr) {
        const monday = new Date(mondayStr);
        return giorniDef.map((g, index) => {
            const currentDay = new Date(monday);
            currentDay.setDate(monday.getDate() + index);
            const formattedDate = currentDay.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit' });
            return {
                key: g.key,
                label: `${g.label} ${formattedDate}`
            };
        });
    }

    async function loadData() {
        try {
            const settimanaParam = `?settimana=${currentMondayStr}`;
            const [profRes, classRes, orarioRes, vincoliRes, vincoliClassiRes] = await Promise.all([
                fetch(`/professori${settimanaParam}`).then(res => res.json()),
                fetch("/classi").then(res => res.json()),
                fetch(`/orario${settimanaParam}`).then(res => res.json()),
                fetch("/vincoli_prof").then(res => res.json()),
                fetch("/vincoli_classi").then(res => res.json())
            ]);

            professoriData = profRes;
            classiData = classRes.filter(c => c.visibile === 1 || c.visibile === true);
            orarioData = orarioRes;
            vincoliData = vincoliRes;
            vincoliClassiData = vincoliClassiRes;

            renderSidebar();
            renderTable();
        } catch (error) {
            console.error("Errore nel caricamento dati:", error);
        }
    }

    function renderSidebar() {
        const listContainer = document.getElementById("prof-list");
        if (!listContainer) return;

        listContainer.innerHTML = "";

        if (!professoriData || professoriData.length === 0) {
            listContainer.innerHTML = "<p style='font-size:0.85rem; color:#64748b;'>Nessun professore trovato.</p>";
            return;
        }

        const groupedProfs = {};
        professoriData.forEach(item => {
            const isClasseVisibile = classiData.some(c => c.id === item.classeid);
            if (!isClasseVisibile) return;

            if (!groupedProfs[item.profid]) {
                groupedProfs[item.profid] = {
                    profid: item.profid,
                    prof_nome: item.prof_nome,
                    prof_cognome: item.prof_cognome,
                    note: item.prof_note,
                    assignments: []
                };
            }
            groupedProfs[item.profid].assignments.push(item);
        });

        Object.values(groupedProfs).forEach(prof => {
            prof.assignments.sort((a, b) => {
                if (a.classe_nome !== b.classe_nome) {
                    return a.classe_nome.localeCompare(b.classe_nome, 'it', { numeric: true });
                }
                return a.materia_nome.localeCompare(b.materia_nome, 'it');
            });

            const card = document.createElement("div");
            card.className = "draggable-card";

            const colorIndex = (parseInt(prof.profid) || 0) % paletteColori.length;
            card.style.borderLeft = `5px solid ${paletteColori[colorIndex]}`;

            let assignmentsHTML = "";
            let totaleOreProf = 0;
            let totaleResidueProf = 0;

            prof.assignments.forEach(assign => {
                const isExhausted = assign.oreresidue <= 0;
                totaleOreProf += (assign.oresettimanali_totali || 0);
                totaleResidueProf += (assign.oreresidue || 0);

                assignmentsHTML += `
                    <div class="prof-assignment-row ${isExhausted ? 'exhausted' : ''}" 
                         draggable="${!isExhausted}"
                         data-profid="${prof.profid}" 
                         data-materiaid="${assign.materiaid}"
                         data-classeid="${assign.classeid}">
                        <div class="assignment-info">
                            📚 <strong>${assign.materia_nome}</strong> (${assign.classe_nome})
                            <span class="badge-priority">P${assign.priorita}</span>
                        </div>
                        <div class="assignment-hours">Ore residue: ${assign.oreresidue} / ${assign.oresettimanali_totali}</div>
                    </div>
                `;
            });

            card.innerHTML = `
                <div class="card-title" style="display: flex; justify-content: space-between; align-items: center; gap: 8px;">
                    <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${prof.prof_nome} ${prof.prof_cognome}</span>
                    <span style="font-size: 0.68rem; font-weight: normal; background: #e2e8f0; padding: 2px 5px; border-radius: 4px; color: #334155; white-space: nowrap; flex-shrink: 0;">
                        Tot: ${totaleOreProf}h | Residue: ${totaleResidueProf}h
                    </span>
                </div>
                <div class="assignments-container">
                    ${assignmentsHTML}
                </div>
            `;

            card.querySelector(".card-title").addEventListener("click", () => {
                showProfModal(prof);
            });

            listContainer.appendChild(card);
        });

        setupDragEvents();
    }

    function setupDragEvents() {
        const assignmentRows = document.querySelectorAll(".prof-assignment-row:not(.exhausted)");
        assignmentRows.forEach(row => {
            row.addEventListener("dragstart", (e) => {
                e.dataTransfer.setData("text/plain", JSON.stringify({
                    profid: parseInt(row.dataset.profid),
                    materia_id: parseInt(row.dataset.materiaid),
                    target_classeid: parseInt(row.dataset.classeid)
                }));
            });
        });
    }

    function setupBoardDragEvents() {
        const boardLessons = document.querySelectorAll(".assigned-lesson");
        boardLessons.forEach(lesson => {
            lesson.addEventListener("dragstart", (e) => {
                e.stopPropagation();
                e.dataTransfer.setData("text/plain", JSON.stringify({
                    isMove: true,
                    orario_id: parseInt(lesson.dataset.orarioid),
                    profid: parseInt(lesson.dataset.profid),
                    materia_id: parseInt(lesson.dataset.materiaid),
                    source_classeid: parseInt(lesson.dataset.sourceclasseid)
                }));
            });
        });
    }

    function showProfModal(prof) {
        const modal = document.getElementById("prof-modal");
        const modalBody = document.getElementById("modal-body");
        const profVincoli = vincoliData.filter(v => v.profid === prof.profid);

        let vincoliHTML = "";
        if (profVincoli.length === 0) {
            vincoliHTML = "<p style='font-size:0.85rem; color:#64748b;'>Nessun vincolo particolare registrato.</p>";
        } else {
            profVincoli.forEach(v => {
                let badgeClass = "badge-obbligo";
                if (v.tipo_vincolo === "assenza") badgeClass = "badge-assenza";
                if (v.tipo_vincolo === "preferenza") badgeClass = "badge-preferenza";
                const giornoLabel = giorniDef.find(g => g.key === v.giorno)?.label || v.giorno;
                vincoliHTML += `<span class="constraint-badge ${badgeClass}">${v.tipo_vincolo.toUpperCase()}: ${giornoLabel} - ${v.ora}° Ora</span><br>`;
            });
        }

        const cattedreValide = prof.assignments.filter(a => classiData.some(c => c.id === a.classeid));

        let cattedreHTML = "";
        if (cattedreValide.length === 0) {
            cattedreHTML = "<p style='font-size:0.85rem; color:#64748b;'>Nessuna cattedra attiva associata per le classi visibili.</p>";
        } else {
            cattedreHTML = "<ul style='margin-left: 1rem; font-size: 0.9rem;'>";
            cattedreValide.forEach(a => {
                cattedreHTML += `<li>${a.materia_nome} nella classe <strong>${a.classe_nome}</strong> (${a.oresettimanali_totali}h totali, Priorità ${a.priorita})</li>`;
            });
            cattedreHTML += "</ul>";
        }

        const cognome = (prof.prof_cognome || "").toLowerCase();
        let iconaVerificaHTML = "";
        if (cognome.includes("abondio") || cognome.includes("balduzzi") || cognome.includes("ferri")) {
            iconaVerificaHTML = `
                <div style="margin-top: 15px; padding: 10px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; display: flex; align-items: center; justify-content: space-between;">
                    <span style="font-size: 0.85rem; color: #166534;">🎯 Regola Doppia Ora (Comunicazione/Inglese)</span>
                    <button onclick="verificaDoppieOreAbondioBalduzzi()" 
                            title="Clicca per testare se le cattedre di Comunicazione e Inglese di questo docente rispettano l'obbligo di almeno una doppia ora consecutiva settimanale per classe."
                            style="background: #22c55e; color: white; border: none; padding: 6px 10px; border-radius: 4px; font-size: 0.8rem; cursor: pointer; display: inline-flex; align-items: center; gap: 5px;">
                        🔍 Verifica Doppie Ore
                    </button>
                </div>
            `;
        }

        modalBody.innerHTML = `
            <div class="modal-title">${prof.prof_nome} ${prof.prof_cognome}</div>
            <p style="font-size:0.85rem; color:#64748b; margin-bottom: 1rem;">${prof.note || 'Nessuna nota aggiuntiva'}</p>
            <div class="modal-section"><h4>📊 Cattedre e Assegnazioni</h4>${cattedreHTML}</div>
            <div class="modal-section"><h4>🔒 Vincoli e Preferenze Orarie</h4>${vincoliHTML}</div>
            ${iconaVerificaHTML}
        `;
        modal.style.display = "flex";
    }

    function showClassModal(classItem) {
        const modal = document.getElementById("class-modal");
        const modalBody = document.getElementById("class-modal-body");

        const profsInClass = professoriData.filter(p => p.classeid === classItem.id);

        let tableHTML = "";
        if (profsInClass.length === 0) {
            tableHTML = "<p style='font-size:0.85rem; color:#64748b;'>Nessuna materia o professore associato a questa classe.</p>";
        } else {
            tableHTML = `<table class="modal-table" style="white-space: nowrap; font-size: 0.85rem;">
                <thead>
                    <tr>
                        <th>Materia</th>
                        <th>Professore</th>
                        <th style="text-align: center;">Ore Standard</th>
                        <th style="text-align: center;">Ore a Tabellone</th>
                    </tr>
                </thead>
                <tbody>`;

            let totStandardClasse = 0;
            let totTabelloneClasse = 0;

            profsInClass.forEach(p => {
                const oreStandard = p.oresettimanali_totali || 0;
                const oreTabellone = orarioData ? orarioData.filter(item =>
                    item.classeid === classItem.id && item.materia_id === p.materiaid
                ).length : 0;

                totStandardClasse += oreStandard;
                totTabelloneClasse += oreTabellone;

                let badgeStyle = "font-weight: bold; color: #059669;";
                if (oreTabellone < oreStandard) {
                    badgeStyle = "font-weight: bold; color: #d97706;";
                } else if (oreTabellone > oreStandard) {
                    badgeStyle = "font-weight: bold; color: #2563eb;";
                }

                tableHTML += `
                    <tr style="white-space: nowrap;">
                        <td>${p.materia_nome}</td>
                        <td>${p.prof_nome} ${p.prof_cognome}</td>
                        <td style="text-align: center;">${oreStandard}h</td>
                        <td style="text-align: center; ${badgeStyle}">${oreTabellone}h</td>
                    </tr>`;
            });

            tableHTML += `
                    <tr style="background-color: #f8fafc; font-weight: bold; white-space: nowrap;">
                        <td colspan="2" style="text-align: right;">TOTALI:</td>
                        <td style="text-align: center;">${totStandardClasse}h</td>
                        <td style="text-align: center;">${totTabelloneClasse}h</td>
                    </tr>
                </tbody>
            </table>`;
        }

        modalBody.innerHTML = `
            <div class="modal-title">Classe ${classItem.nome}</div>
            <p style="font-size:0.85rem; color:#64748b; margin-bottom: 1rem;">Indirizzo / Anno: ${classItem.anno || 'Non specificato'}</p>
            <div class="modal-section"><h4>📚 Materie, Professori e Confronto Ore</h4>${tableHTML}</div>
        `;
        modal.style.display = "flex";
    }

    window.closeModal = function (modalId) {
        document.getElementById(modalId).style.display = "none";
    };

    window.addEventListener("click", (e) => {
        if (e.target.classList.contains("modal-overlay")) {
            e.target.style.display = "none";
        }
    });

    function renderTable() {
        const table = document.getElementById("schedule-table");
        if (!table) return;

        const thead = table.querySelector("thead");
        const tbody = table.querySelector("tbody");
        const daysWithDates = getDaysWithDates(currentMondayStr);

        let headerRow1 = `<tr><th rowspan="2">Classe / Ora</th>`;
        daysWithDates.forEach(g => { headerRow1 += `<th colspan="6">${g.label}</th>`; });
        headerRow1 += `</tr>`;

        let headerRow2 = `<tr>`;
        daysWithDates.forEach(() => { ore.forEach(o => { headerRow2 += `<th>${o}° Ora</th>`; }); });
        headerRow2 += `</tr>`;

        thead.innerHTML = headerRow1 + headerRow2;

        let bodyHTML = "";
        classiData.forEach(cls => {
            const totStandard = professoriData
                .filter(item => item.classeid === cls.id)
                .reduce((sum, item) => sum + (item.oresettimanali_totali || 0), 0);

            const totTabellone = orarioData
                .filter(oItem => oItem.classeid === cls.id)
                .length;

            let styleVerdino = "";
            let infoOreTooltip = ` (Assegnate: ${totTabellone}/${totStandard}h)`;
            
            if (totStandard > 0 && totStandard === totTabellone) {
                styleVerdino = "background-color: #dcfce7 !important; color: #166534 !important; font-weight: bold;";
                infoOreTooltip = ` ✅ (Completata: ${totTabellone}/${totStandard}h)`;
            }

            bodyHTML += `<tr>`;
            bodyHTML += `<td class="class-cell" style="${styleVerdino}" title="Clicca per vedere materie e professori${infoOreTooltip}">${cls.nome}</td>`;

            daysWithDates.forEach(g => {
                ore.forEach(o => {
                    const assigned = orarioData.find(oItem =>
                        oItem.classeid === cls.id && oItem.giorno === g.key && oItem.ora === o
                    );

                    bodyHTML += `<td class="slot-cell" data-classeid="${cls.id}" data-giorno="${g.key}" data-ora="${o}">`;
                    if (assigned) {
                        const isFuoriCattedra = !professoriData.some(item =>
                            item.profid == assigned.profid &&
                            item.materiaid == assigned.materia_id &&
                            item.classeid == assigned.classeid
                        );

                        const classeAssigned = isFuoriCattedra ? "assigned-lesson fuori-cattedra" : "assigned-lesson";
                        const stileProf = getStileCardProf(assigned.profid, isFuoriCattedra);

                        bodyHTML += `
                            <div class="${classeAssigned}" 
                                 style="${stileProf}"
                                 draggable="true" 
                                 data-orarioid="${assigned.id}"
                                 data-profid="${assigned.profid}"
                                 data-materiaid="${assigned.materia_id}"
                                 data-sourceclasseid="${assigned.classeid}">
                                <strong>${assigned.materia_nome}</strong><br>
                                <small>${assigned.prof_nome} ${assigned.prof_cognome}</small>
                                ${isFuoriCattedra ? '<div style="font-size:0.65rem; font-style:italic;">(Fuori Cattedra)</div>' : ''}
                                <button class="delete-btn" onclick="deleteAssignment(${assigned.id})">&times;</button>
                            </div>
                        `;
                    }
                    bodyHTML += `</td>`;
                });
            });
            bodyHTML += `</tr>`;
        });
        tbody.innerHTML = bodyHTML;

        document.querySelectorAll(".class-cell").forEach((cell, index) => {
            const cls = classiData[index];
            cell.addEventListener("click", () => { showClassModal(cls); });
        });

        setupDragAndDropEvents();
        setupBoardDragEvents();
    }

    function setupDragAndDropEvents() {
        const cells = document.querySelectorAll(".slot-cell");

        cells.forEach(cell => {
            cell.addEventListener("dragover", (e) => {
                e.preventDefault();
                cell.classList.add("drag-over");
            });

            cell.addEventListener("dragleave", () => {
                cell.classList.remove("drag-over");
            });

            cell.addEventListener("drop", async (e) => {
                e.preventDefault();
                cell.classList.remove("drag-over");

                const rawData = e.dataTransfer.getData("text/plain");
                if (!rawData) return;

                const data = JSON.parse(rawData);
                const cellClasseId = parseInt(cell.dataset.classeid);
                const giorno = cell.dataset.giorno;
                const ora = parseInt(cell.dataset.ora);

                if (data.isMove && data.orario_id) {
                    const assignedOriginale = orarioData.find(o => o.id === data.orario_id);
                    if (assignedOriginale &&
                        assignedOriginale.classeid === cellClasseId &&
                        assignedOriginale.giorno === giorno &&
                        assignedOriginale.ora === ora) {
                        return;
                    }
                }

                const lezioneEsistente = orarioData.find(oItem =>
                    oItem.classeid === cellClasseId && oItem.giorno === giorno && oItem.ora === ora
                );

                if (lezioneEsistente && data.isMove && data.orario_id) {
                    try {
                        const response = await fetch("/orario/switch", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                settimana: currentMondayStr,
                                id_muovi: data.orario_id,
                                classeid: cellClasseId,
                                giorno: giorno,
                                ora: ora
                            })
                        });

                        const result = await response.json();
                        if (!response.ok || !result.success) {
                            alert(`❌ ${result.message || "Switch non consentito dai vincoli."}`);
                            await loadData();
                            return;
                        }

                        await loadData();
                        return;

                    } catch (err) {
                        console.error("Errore di rete durante lo switch:", err);
                        alert("❌ Errore di connessione durante lo switch.");
                        await loadData();
                        return;
                    }
                }

                if (lezioneEsistente && !data.isMove) {
                    alert("❌ Operazione Bloccata: Questo slot è già occupato.");
                    return;
                }

                const haVincoloAssenzaClasse = vincoliClassiData.some(v =>
                    v.classeid === cellClasseId &&
                    v.giorno === giorno &&
                    (v.ora === ora || v.ora === 0) &&
                    v.tipo_vincolo === "assenza"
                );

                if (haVincoloAssenzaClasse) {
                    alert("❌ Operazione Bloccata: La classe non fa lezione (o è in gita/assente) in questo giorno e ora.");
                    return;
                }

                const profItemForMateria = professoriData.find(item => item.materiaid === data.materia_id);
                const materiaNome = profItemForMateria ? (profItemForMateria.materia_nome || "").toLowerCase() : "";

                if (materiaNome.includes("motorie") || materiaNome.includes("saldatura") || materiaNome.includes("cnc")) {
                    const conflittoRisorsaCondivisa = orarioData.some(o =>
                        o.giorno === giorno &&
                        o.ora === ora &&
                        ((o.materia_nome || "").toLowerCase().includes("motorie") && materiaNome.includes("motorie") ||
                            (o.materia_nome || "").toLowerCase().includes("saldatura") && materiaNome.includes("saldatura") ||
                            (o.materia_nome || "").toLowerCase().includes("cnc") && materiaNome.includes("cnc")) &&
                        (!data.isMove || o.id !== data.orario_id)
                    );

                    if (conflittoRisorsaCondivisa) {
                        alert(`❌ Operazione Bloccata: La risorsa condivisa (Palestra o Laboratorio) è già impegnata da un'altra classe in questo giorno (${giorno.toUpperCase()}) alla ${ora}° ora.`);
                        return;
                    }
                }

                if (materiaNome.includes("motorie")) {
                    const haMotorieVicino = orarioData.some(o =>
                        o.classeid === cellClasseId &&
                        o.giorno === giorno &&
                        (o.ora === ora - 1 || o.ora === ora + 1) &&
                        (o.materia_nome || "").toLowerCase().includes("motorie") &&
                        (!data.isMove || o.id !== data.orario_id)
                    );
                    if (haMotorieVicino) {
                        alert("❌ Operazione Bloccata: Non è consentita la doppia ora consecutiva di Scienze Motorie sulla stessa classe.");
                        return;
                    }
                }

                const profObj = professoriData.find(item => item.profid === data.profid);
                if (profObj) {
                    const cognomeProf = (profObj.prof_cognome || "").toLowerCase();
                    const nomeProf = (profObj.prof_nome || "").toLowerCase();
                    const profSpeciali = [
                        "abondio", "balduzzi", "bonazzi", "ferri",
                        "facchinetti", "beetoni", "cretti", "scandella",
                        "cosseddu", "visinoni", "zamboni", "caccia"
                    ];

                    const isProfSpeciale = profSpeciali.some(s => cognomeProf.includes(s) || nomeProf.includes(s));

                    if (isProfSpeciale) {
                        const oreEsistentiStessoGiorno = orarioData.filter(o =>
                            o.profid === data.profid &&
                            o.classeid === cellClasseId &&
                            o.giorno === giorno &&
                            (!data.isMove || o.id !== data.orario_id)
                        ).length;

                        if (oreEsistentiStessoGiorno >= 2) {
                            alert(`❌ Operazione Bloccata: Il docente ${profObj.prof_cognome} ${profObj.prof_nome} non può fare più di 2 ore con la stessa classe nello stesso giorno.`);
                            return;
                        }
                    }
                }

                if (profObj) {
                    const isProfCaccia = (profObj.prof_cognome || "").toLowerCase().includes("caccia") && materiaNome.includes("informatica");
                    const isProfZamboniDisegno = (profObj.prof_cognome || "").toLowerCase().includes("zamboni") && materiaNome.includes("disegno");

                    if (isProfCaccia) {
                        const zamboniConflitto = orarioData.some(o => {
                            const isZamboniProf = (o.prof_cognome || "").toLowerCase().includes("zamboni");
                            const isDisegno = (o.materia_nome || "").toLowerCase().includes("disegno");
                            if (!isZamboniProf || !isDisegno) return false;

                            const haDoppiaConsecutiva = orarioData.some(other =>
                                other.profid === o.profid &&
                                other.classeid === o.classeid &&
                                other.giorno === giorno &&
                                (other.ora === o.ora - 1 || other.ora === o.ora + 1) &&
                                (other.materia_nome || "").toLowerCase().includes("disegno")
                            );

                            return o.giorno === giorno && o.ora === ora && haDoppiaConsecutiva;
                        });

                        if (zamboniConflitto) {
                            alert("❌ Operazione Bloccata: In questo giorno e ora il prof. Zamboni sta tenendo una doppia ora consecutiva di Disegno e sta occupando l'aula informatica.");
                            return;
                        }
                    }

                    if (isProfZamboniDisegno) {
                        const creerebbeDoppiaOra = orarioData.some(o =>
                            o.profid == data.profid &&
                            o.classeid === cellClasseId &&
                            o.giorno === giorno &&
                            (o.ora === ora - 1 || o.ora === ora + 1) &&
                            (o.materia_nome || "").toLowerCase().includes("disegno") &&
                            (!data.isMove || o.id !== data.orario_id)
                        );

                        if (creerebbeDoppiaOra) {
                            const oraAdiacente = orarioData.find(o =>
                                o.giorno === giorno &&
                                (o.ora === ora || o.ora === ora - 1 || o.ora === ora + 1) &&
                                (o.prof_cognome || "").toLowerCase().includes("caccia") &&
                                (o.materia_nome || "").toLowerCase().includes("informatica")
                            );

                            if (oraAdiacente) {
                                alert("❌ Operazione Bloccata: Non puoi piazzare una doppia ora di Disegno per Zamboni in questo slot perché il prof. Caccia ha lezione di Informatica in contemporanea (aula informatica occupata).");
                                return;
                            }
                        }
                    }
                }

                const isMateriaPrevistaInClasse = professoriData.some(item =>
                    item.materiaid === data.materia_id && item.classeid === cellClasseId
                );

                if (!isMateriaPrevistaInClasse) {
                    alert("❌ Operazione Bloccata: La materia selezionata non è prevista nel piano di studi di questa classe.");
                    return;
                }

                const isCattedraUfficiale = professoriData.some(item =>
                    item.profid == data.profid &&
                    item.materiaid === data.materia_id &&
                    item.classeid === cellClasseId
                );

                if (!isCattedraUfficiale) {
                    const confermaFuoriCattedra = confirm(
                        "⚠️ ATTENZIONE: Stai assegnando questo professore fuori dalla sua cattedra standard per questa classe.\n\n" +
                        "L'ora verrà registrata come 'Fuori Cattedra' (evidenziata con colore tenue). Vuoi procedere?"
                    );
                    if (!confermaFuoriCattedra) return;
                }

                try {
                    if (data.isMove && data.orario_id) {
                        const response = await fetch("/orario/move", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({
                                settimana: currentMondayStr,
                                orario_id: data.orario_id,
                                classeid: cellClasseId,
                                giorno: giorno,
                                ora: ora
                            })
                        });

                        const result = await response.json();

                        if (!response.ok || !result.success) {
                            alert(`❌ ${result.message || "Spostamento non consentito."}`);
                            await loadData();
                            return;
                        }

                        if (result.status === "giallo") {
                            alert("⚠️ " + result.message);
                        }

                        await loadData();
                        return;
                    }

                    const response = await fetch("/orario", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            classeid: cellClasseId,
                            settimana: currentMondayStr,
                            giorno,
                            ora,
                            profid: data.profid,
                            materia_id: data.materia_id
                        })
                    });

                    const result = await response.json();

                    if (!response.ok) {
                        alert(`❌ Errore: ${result.message}`);
                        await loadData();
                        return;
                    }

                    if (result.status === "giallo") {
                        alert("⚠️ " + result.message);
                    }

                    await loadData();

                } catch (err) {
                    console.error("Errore di rete durante il salvataggio o lo spostamento:", err);
                    alert("❌ Errore di connessione.");
                    await loadData();
                }
            });
        });
    }

    window.verificaDoppieOreAbondioBalduzzi = function () {
        let report = [];

        professoriData.forEach(item => {
            const cog = (item.prof_cognome || "").toLowerCase();
            const mat = (item.materia_nome || "").toLowerCase();

            const isAbondio = cog.includes("abondio");
            const isBalduzzi = cog.includes("balduzzi");
            const isFerri = cog.includes("ferri");
            const isComunicazione = mat.includes("comunicazione");
            const isInglese = mat.includes("inglese");

            if ((isAbondio && (isComunicazione || isInglese)) ||
                ((isBalduzzi || isFerri) && isComunicazione)) {

                const clsObj = classiData.find(c => c.id === item.classeid);
                if (!clsObj || clsObj.visibile === 0 || clsObj.visibile === false) {
                    return;
                }
                const nomeClasse = clsObj.nome;

                const orePiazzate = orarioData.filter(o =>
                    o.profid === item.profid &&
                    o.materia_id === item.materiaid &&
                    o.classeid === item.classeid
                );

                let haDoppiaOra = false;
                giorniDef.forEach(g => {
                    const oreDelGiorno = orePiazzate.filter(o => o.giorno === g.key).map(o => o.ora).sort((a, b) => a - b);
                    for (let i = 0; i < oreDelGiorno.length - 1; i++) {
                        if (oreDelGiorno[i + 1] === oreDelGiorno[i] + 1) {
                            haDoppiaOra = true;
                        }
                    }
                });

                report.push({
                    docente: `${item.prof_nome} ${item.prof_cognome}`,
                    materia: item.materia_nome,
                    classe: nomeClasse,
                    oreTotaliPiazzate: orePiazzate.length,
                    oreTotaliPreviste: item.oresettimanali_totali,
                    rispettaDoppiaOra: haDoppiaOra
                });
            }
        });

        console.table(report);

        const nonConformi = report.filter(r => r.rispettaDoppiaOra === false);
        if (nonConformi.length === 0) {
            alert("✅ VERIFICA SUPERATA: Tutte le cattedre verificate hanno almeno una doppia ora consecutiva!");
        } else {
            let msg = `⚠️ ATTENZIONE: Trovate ${nonConformi.length} cattedre senza doppia ora consecutiva:\n\n`;
            nonConformi.forEach(nc => {
                msg += `- ${nc.docente} (${nc.materia}) in ${nc.classe}\n`;
            });
            alert(msg);
        }

        return report;
    };

    window.getRiassuntoFuoriCattedra = function () {
        const fuoriCattedraList = [];
        orarioData.forEach(assigned => {
            const isFuoriCattedra = !professoriData.some(item =>
                item.profid == assigned.profid &&
                item.materiaid == assigned.materia_id &&
                item.classeid == assigned.classeid
            );
            if (isFuoriCattedra) fuoriCattedraList.push(assigned);
        });
        return fuoriCattedraList;
    };

    window.mostraReportFuoriCattedra = function () {
        const lista = window.getRiassuntoFuoriCattedra();
        const contenitore = document.getElementById("contenuto-report-fc");
        if (!contenitore) return;

        if (lista.length === 0) {
            contenitore.innerHTML = `
                <div style="text-align: center; padding: 20px; color: #16a34a;">
                    <p style="font-size: 1.1rem; font-weight: 500; margin: 0;">Ottimo lavoro!</p>
                    <p style="margin: 5px 0 0 0; color: #64748b; font-size: 0.85rem;">Non ci sono ore assegnate fuori cattedra in questa settimana.</p>
                </div>`;
        } else {
            const conteggioPerProf = {};
            lista.forEach(item => {
                const profKey = `${item.prof_nome} ${item.prof_cognome}`;
                conteggioPerProf[profKey] = (conteggioPerProf[profKey] || 0) + 1;
            });

            let html = `<p style="margin-bottom: 12px; color: #64748b; font-size: 0.85rem;">Trovate <strong>${lista.length}</strong> ore complessive fuori cattedra:</p>`;
            html += `<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; margin-bottom: 12px;">`;
            html += `<strong style="font-size: 0.8rem; color: #475569; display: block; margin-bottom: 6px;">Riepilogo ore per docente:</strong>`;
            html += `<div style="display: flex; flex-wrap: wrap; gap: 6px;">`;
            for (const [prof, oreTot] of Object.entries(conteggioPerProf)) {
                html += `<span style="background: #fff; border: 1px solid #cbd5e1; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; color: #334155;">${prof}: <strong>${oreTot}h</strong></span>`;
            }
            html += `</div></div>`;

            html += `<ul style="list-style-type: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; max-height: 200px; overflow-y: auto;">`;
            lista.forEach(item => {
                const cls = classiData.find(c => c.id === item.classeid);
                const nomeClasse = cls ? cls.nome : "Classe";
                html += `
                    <li style="padding: 8px 12px; background: #fff3cd; border: 1px solid #ffeeba; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong>${item.prof_nome} ${item.prof_cognome}</strong><br>
                            <span style="font-size: 0.8rem; color: #856404;">📚 ${item.materia_nome} • Classe <strong>${nomeClasse}</strong></span>
                        </div>
                        <div style="text-align: right; font-size: 0.8rem; color: #856404; background: #fff; padding: 2px 6px; border-radius: 4px; border: 1px solid #ffeeba;">
                            ${item.giorno.toUpperCase()} • ${item.ora}° Ora
                        </div>
                    </li>`;
            });
            html += `</ul>`;
            contenitore.innerHTML = html;
        }

        document.getElementById("modal-fuori-cattedra").style.display = "flex";
    };

    const searchInput = document.getElementById('search-prof');
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            const searchTerm = this.value.toLowerCase().trim();

            document.querySelectorAll('.highlight-in-cattedra, .highlight-fuori-cattedra').forEach(el => {
                el.classList.remove('highlight-in-cattedra', 'highlight-fuori-cattedra');
            });

            const sidebarCards = document.querySelectorAll('.draggable-card');

            sidebarCards.forEach(card => {
                const titleText = card.querySelector('.card-title')?.textContent.toLowerCase() || '';
                const assignmentsText = Array.from(card.querySelectorAll('.prof-assignment-row'))
                    .map(row => row.textContent.toLowerCase())
                    .join(' ');

                const fullCardText = titleText + ' ' + assignmentsText;

                if (searchTerm === "") {
                    card.style.display = "";
                } else if (fullCardText.includes(searchTerm)) {
                    card.style.display = "";
                    const haFuoriCattedra = card.querySelector('.prof-assignment-row.fuori-cattedra') !== null;
                    if (haFuoriCattedra) card.classList.add('highlight-fuori-cattedra');
                    else card.classList.add('highlight-in-cattedra');
                } else {
                    card.style.display = "none";
                }
            });

            if (searchTerm === "") return;

            const boardLessons = document.querySelectorAll('.assigned-lesson');
            boardLessons.forEach(lesson => {
                const textContent = lesson.textContent.toLowerCase();
                if (textContent.includes(searchTerm)) {
                    if (lesson.classList.contains('fuori-cattedra')) {
                        lesson.classList.add('highlight-fuori-cattedra');
                    } else {
                        lesson.classList.add('highlight-in-cattedra');
                    }
                }
            });
        });

        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                this.value = '';
                
                const sidebarCards = document.querySelectorAll('.draggable-card');
                sidebarCards.forEach(card => {
                    card.style.display = "";
                });

                document.querySelectorAll('.highlight-in-cattedra, .highlight-fuori-cattedra').forEach(el => {
                    el.classList.remove('highlight-in-cattedra', 'highlight-fuori-cattedra');
                });

                this.blur();
            }
        });
    }

    window.copiaSettimanaCorrente = async function () {
        if (!currentMondayStr) {
            alert("Nessuna settimana di origine selezionata.");
            return;
        }

        const targetWeekStr = prompt(
            `Stai per copiare tutti i dati della settimana attuale (${currentMondayStr}) in un'altra settimana.\n\n` +
            `Inserisci la data del LUNEDÌ della settimana di destinazione (formato AAAA-MM-DD):`,
            ""
        );

        if (!targetWeekStr) return;

        const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
        if (!dateRegex.test(targetWeekStr)) {
            alert("❌ Formato data non valido. Usa il formato AAAA-MM-DD (es. 2026-11-02).");
            return;
        }

        if (targetWeekStr === currentMondayStr) {
            alert("⚠️ La settimana di destinazione è identica a quella di origine.");
            return;
        }

        try {
            const conferma = confirm(`Confermi di voler duplicare l'orario da ${currentMondayStr} a ${targetWeekStr}?`);
            if (!conferma) return;

            const response = await fetch("/orario/copia", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    settimana_origine: currentMondayStr,
                    settimana_destinazione: targetWeekStr
                })
            });

            const result = await response.json();

            if (!response.ok) {
                alert(`❌ Errore durante la copia: ${result.message || 'Errore sconosciuto'}`);
                return;
            }

            alert(`✅ Operazione completata! L'orario è stato copiato con successo nella settimana del ${targetWeekStr}.`);

            const weekPicker = document.getElementById("week-picker");
            if (weekPicker) {
                weekPicker.value = targetWeekStr;
                currentMondayStr = targetWeekStr;
                loadData();
            }

        } catch (error) {
            console.error("Errore di rete durante la copia della settimana:", error);
            alert("Si è verificato un errore di connessione durante la copia.");
        }
    };

    window.deleteAssignment = async function (id) {
        try {
            await fetch(`/orario/${id}`, { method: "DELETE" });
            loadData();
        } catch (err) {
            console.error("Errore durante l'eliminazione:", err);
        }
    };

    window.pulisciOrarioSettimana = function () {
        if (!currentMondayStr) {
            alert("⚠️ Seleziona prima una settimana di riferimento.");
            return;
        }

        if (confirm(`Sei sicuro di voler cancellare gli orari della settimana del ${currentMondayStr}?`)) {
            fetch('/admin/pulisci_orario', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ settimana: currentMondayStr })
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert(data.message);
                        loadData();
                    } else {
                        alert("Errore: " + data.message);
                    }
                })
                .catch(err => {
                    console.error("Errore di rete:", err);
                    alert("Errore di connessione durante la pulizia dell'orario.");
                });
        }
    };

    window.generaOrarioAutomatico = async function () {
        if (!currentMondayStr) {
            alert("Seleziona prima una settimana di riferimento.");
            return;
        }

        const conferma = confirm(
            `⚠️ ATTENZIONE:\nLa generazione automatica sovrascriverà l'orario della settimana del ${currentMondayStr}.\n\nVuoi procedere?`
        );
        if (!conferma) return;

        try {
            const response = await fetch("/orario/genera", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ settimana: currentMondayStr })
            });

            const result = await response.json();

            if (!response.ok || !result.success) {
                alert(`❌ Errore: ${result.message || 'Impossibile completare la generazione.'}`);
                return;
            }

            alert(`✅ ${result.message}`);
            loadData();

        } catch (error) {
            console.error("Errore di rete durante la generazione automatica:", error);
            alert("Si è verificato un errore di connessione con il server.");
        }
    };

    loadData();
});