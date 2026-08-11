document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const domainInput = document.getElementById('domain-input');
    const domainCounter = document.getElementById('domain-counter');
    const btnClear = document.getElementById('btn-clear');
    const btnScan = document.getElementById('btn-scan');
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const threadCountInput = document.getElementById('thread-count');
    const strictMatchCheckbox = document.getElementById('strict-match');

    const progressWrap = document.getElementById('progress-wrap');
    const progressFill = document.getElementById('progress-fill');

    const statTotal = document.getElementById('stat-total');
    const statBlocked = document.getElementById('stat-blocked');
    const statClean = document.getElementById('stat-clean');
    const statHighRisk = document.getElementById('stat-high-risk');
    const statSpeed = document.getElementById('stat-speed');

    const btnExportExcel = document.getElementById('btn-export-excel');
    const btnExportJson = document.getElementById('btn-export-json');

    const filterTabs = document.querySelectorAll('.tab-btn');
    const searchFilter = document.getElementById('search-filter');
    const resultsTbody = document.getElementById('results-tbody');

    const detailModal = document.getElementById('detail-modal');
    const modalClose = document.getElementById('modal-close');
    const modalTitle = document.getElementById('modal-title');
    const modalContent = document.getElementById('modal-content');

    // Global State
    let currentReport = null;
    let activeFilter = 'all';

    // ----------------------------------------------------
    // INPUT PARSER & COUNTER
    // ----------------------------------------------------
    function extractDomains(text) {
        if (!text) return [];
        const lines = text.replace(/[,;\t\r]/g, '\n').split('\n');
        const seen = new Set();
        const domains = [];

        lines.forEach(line => {
            let d = line.trim().toLowerCase();
            if (!d || d.startsWith('#')) return;
            
            if (d.includes('://')) {
                d = d.split('://')[1];
            }
            d = d.split('/')[0].split('?')[0].split('#')[0].split(':')[0];
            d = d.replace(/^www\./, '');

            if (d && !seen.has(d)) {
                seen.add(d);
                domains.push(d);
            }
        });

        return domains;
    }

    function updateInputCount() {
        const domains = extractDomains(domainInput.value);
        domainCounter.textContent = `${domains.length} Domain`;
    }

    domainInput.addEventListener('input', updateInputCount);

    btnClear.addEventListener('click', (e) => {
        e.preventDefault();
        domainInput.value = '';
        updateInputCount();
    });

    // ----------------------------------------------------
    // FILE UPLOAD & DRAG DROP
    // ----------------------------------------------------
    dropzone.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.style.borderColor = 'var(--blue-accent)';
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.style.borderColor = 'var(--border-color)';
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.style.borderColor = 'var(--border-color)';
        if (e.dataTransfer.files.length > 0) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    function handleFile(file) {
        const reader = new FileReader();
        reader.onload = (evt) => {
            domainInput.value = evt.target.result;
            updateInputCount();
        };
        reader.readAsText(file);
    }

    // ----------------------------------------------------
    // REAL-TIME STREAMING QUERY EXECUTION
    // ----------------------------------------------------
    btnScan.addEventListener('click', async () => {
        const domains = extractDomains(domainInput.value);
        if (domains.length === 0) {
            alert('Lütfen sorgulanacak en az bir geçerli alan adı giriniz.');
            return;
        }

        const threads = parseInt(threadCountInput.value) || 15;
        const strict = strictMatchCheckbox.checked;

        // Reset UI state for live streaming
        resultsTbody.innerHTML = '';
        statTotal.textContent = domains.length;
        statBlocked.textContent = '0';
        statClean.textContent = '0';
        statHighRisk.textContent = '0';
        statSpeed.textContent = '0s';

        btnScan.disabled = true;
        btnScan.innerHTML = 'Sorgulanıyor... (Canlı Akış)';
        progressWrap.style.display = 'block';
        progressFill.style.width = '5%';

        let accumulatedResults = [];

        try {
            const resp = await fetch('/api/check/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ domains, threads, strict })
            });

            if (!resp.ok) {
                const errData = await resp.json();
                throw new Error(errData.detail || 'Sorgulama servis hatası.');
            }

            const reader = resp.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep buffer remainder

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const event = JSON.parse(line.trim());

                        if (event.type === 'start') {
                            statTotal.textContent = event.total;
                            document.querySelector('[data-filter="all"]').textContent = `Tümü (${event.total})`;
                        } else if (event.type === 'progress') {
                            const pct = Math.round((event.completed / event.total) * 100);
                            progressFill.style.width = `${pct}%`;

                            // Live Stats Update
                            statTotal.textContent = event.total;
                            statBlocked.textContent = event.stats.blocked_count;
                            statClean.textContent = event.stats.clean_count;
                            statHighRisk.textContent = event.stats.high_criticality_count;
                            statSpeed.textContent = `${event.stats.duration_seconds}s (${event.stats.domains_per_second} req/s)`;

                            document.querySelector('[data-filter="blocked"]').textContent = `Engellenmiş (${event.stats.blocked_count})`;
                            document.querySelector('[data-filter="clean"]').textContent = `Temiz (${event.stats.clean_count})`;

                            // Append New Row Immediately in Realtime!
                            accumulatedResults.push(event.result);
                            appendLiveRow(event.result, accumulatedResults.length);

                        } else if (event.type === 'complete') {
                            currentReport = {
                                summary: event.summary,
                                results: event.results
                            };
                            renderSummary(event.summary);
                            renderTable(event.results);

                            btnExportExcel.disabled = false;
                            btnExportJson.disabled = false;
                        }
                    } catch (e) {
                        console.error('Parse chunk error:', e);
                    }
                }
            }

        } catch (err) {
            alert('Sorgulama Hatası: ' + err.message);
        } finally {
            btnScan.disabled = false;
            btnScan.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg> Sorgulamayı Başlat`;
            setTimeout(() => {
                progressWrap.style.display = 'none';
                progressFill.style.width = '0%';
            }, 500);
        }
    });

    // Append single row live during streaming
    function appendLiveRow(item, index) {
        if (activeFilter === 'blocked' && !item.is_blocked) return;
        if (activeFilter === 'clean' && item.is_blocked) return;

        const isBlocked = item.is_blocked;
        const badgeClass = isBlocked ? 'badge-danger' : 'badge-success';
        const statusText = item.status;
        const t0 = (item.threats && item.threats.length > 0) ? item.threats[0] : null;

        const critLevel = item.max_criticality !== null ? item.max_criticality : '-';
        const catText = t0 ? t0.desc_text : '-';
        const srcText = t0 ? t0.source_text : '-';
        const dateText = t0 ? t0.date : '-';

        const tr = document.createElement('tr');
        tr.style.animation = 'fadeIn 0.3s ease';
        tr.innerHTML = `
            <td>${index}</td>
            <td style="font-family: var(--font-mono); font-weight: 500;">${item.domain}</td>
            <td><span class="badge ${badgeClass}">${statusText}</span></td>
            <td style="text-align: center;">${critLevel}</td>
            <td>${catText}</td>
            <td>${srcText}</td>
            <td style="font-size: 0.8rem; color: var(--text-muted);">${dateText}</td>
        `;

        tr.addEventListener('click', () => showDetailModal(item));
        resultsTbody.appendChild(tr);

        // Auto-scroll table to bottom as items stream in
        const container = document.querySelector('.table-container');
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }

    // ----------------------------------------------------
    // RENDER METRICS & TABLE
    // ----------------------------------------------------
    function renderSummary(summary) {
        statTotal.textContent = summary.total_scanned;
        statBlocked.textContent = summary.blocked_count;
        statClean.textContent = summary.clean_count;
        statHighRisk.textContent = summary.high_criticality_count;
        statSpeed.textContent = `${summary.duration_seconds}s (${summary.domains_per_second} req/s)`;

        document.querySelector('[data-filter="all"]').textContent = `Tümü (${summary.total_scanned})`;
        document.querySelector('[data-filter="blocked"]').textContent = `Engellenmiş (${summary.blocked_count})`;
        document.querySelector('[data-filter="clean"]').textContent = `Temiz (${summary.clean_count})`;
    }

    function renderTable(results) {
        if (!results || results.length === 0) {
            resultsTbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 2rem;">Kayıt bulunamadı.</td></tr>`;
            return;
        }

        const searchText = searchFilter.value.toLowerCase().trim();

        const filtered = results.filter(item => {
            if (activeFilter === 'blocked' && !item.is_blocked) return false;
            if (activeFilter === 'clean' && item.is_blocked) return false;

            if (searchText) {
                const domMatch = item.domain.toLowerCase().includes(searchText);
                const descMatch = (item.threats && item.threats.length > 0 && item.threats[0].desc_text) ? item.threats[0].desc_text.toLowerCase().includes(searchText) : false;
                return domMatch || descMatch;
            }

            return true;
        });

        if (filtered.length === 0) {
            resultsTbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2rem;">Filtreye uygun kayıt bulunamadı.</td></tr>`;
            return;
        }

        let html = '';
        filtered.forEach((item, idx) => {
            const isBlocked = item.is_blocked;
            const badgeClass = isBlocked ? 'badge-danger' : 'badge-success';
            const statusText = item.status;
            const t0 = (item.threats && item.threats.length > 0) ? item.threats[0] : null;

            const critLevel = item.max_criticality !== null ? item.max_criticality : '-';
            const catText = t0 ? t0.desc_text : '-';
            const srcText = t0 ? t0.source_text : '-';
            const dateText = t0 ? t0.date : '-';

            html += `
                <tr data-idx="${idx}">
                    <td>${idx + 1}</td>
                    <td style="font-family: var(--font-mono); font-weight: 500;">${item.domain}</td>
                    <td><span class="badge ${badgeClass}">${statusText}</span></td>
                    <td style="text-align: center;">${critLevel}</td>
                    <td>${catText}</td>
                    <td>${srcText}</td>
                    <td style="font-size: 0.8rem; color: var(--text-muted);">${dateText}</td>
                </tr>
            `;
        });

        resultsTbody.innerHTML = html;

        const rows = resultsTbody.querySelectorAll('tr[data-idx]');
        rows.forEach(r => {
            r.addEventListener('click', () => {
                const idx = parseInt(r.getAttribute('data-idx'));
                showDetailModal(filtered[idx]);
            });
        });
    }

    // ----------------------------------------------------
    // FILTER TABS & SEARCH
    // ----------------------------------------------------
    filterTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            filterTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            activeFilter = tab.getAttribute('data-filter');
            if (currentReport) {
                renderTable(currentReport.results);
            }
        });
    });

    searchFilter.addEventListener('input', () => {
        if (currentReport) {
            renderTable(currentReport.results);
        }
    });

    // ----------------------------------------------------
    // DETAIL MODAL
    // ----------------------------------------------------
    function showDetailModal(item) {
        modalTitle.textContent = `Domain İnceleme: ${item.domain}`;
        
        let threatsHtml = '';
        if (item.threats && item.threats.length > 0) {
            item.threats.forEach(t => {
                threatsHtml += `
                    <div style="background: var(--bg-card-hover); border: 1px solid var(--border-color); border-radius: 8px; padding: 0.75rem; margin-top: 0.5rem;">
                        <p><b>Tehdit Kaydı ID:</b> ${t.id}</p>
                        <p><b>Zararlı Adres / URL:</b> <code>${t.url}</code></p>
                        <p><b>Kategori:</b> ${t.desc_text} (${t.desc_code})</p>
                        <p><b>Kaynak:</b> ${t.source_text} (${t.source_code})</p>
                        <p><b>Bağlantı Tipi:</b> ${t.connection_type_text}</p>
                        <p><b>Kritiklik Seviyesi:</b> <span class="badge badge-warning">${t.criticality_level || '-'}</span></p>
                        <p><b>Kayıt Tarihi:</b> ${t.date}</p>
                    </div>
                `;
            });
        } else {
            threatsHtml = `<p style="color: var(--success-text);">Siber Güvenlik Başkanlığı veritabanında zararlı bağlantı kaydı bulunmamıştır.</p>`;
        }

        modalContent.innerHTML = `
            <div>
                <p><b>Durum:</b> <span class="badge ${item.is_blocked ? 'badge-danger' : 'badge-success'}">${item.status}</span></p>
                <p><b>Eşleşme Türü:</b> ${item.match_type}</p>
                <p><b>Tehdit Kayıt Sayısı:</b> ${item.match_count}</p>
            </div>
            <div>
                <h4 style="font-size: 0.95rem; margin-top: 0.5rem; color: var(--text-muted);">Tehdit Detayları:</h4>
                ${threatsHtml}
            </div>
        `;

        detailModal.classList.add('active');
    }

    modalClose.addEventListener('click', () => detailModal.classList.remove('active'));
    detailModal.addEventListener('click', (e) => {
        if (e.target === detailModal) detailModal.classList.remove('active');
    });

    // ----------------------------------------------------
    // EXPORTER HANDLERS (EXCEL & JSON)
    // ----------------------------------------------------
    async function triggerDownload(url, filename) {
        if (!currentReport) return;
        try {
            const resp = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentReport)
            });
            const blob = await resp.blob();
            const blobUrl = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(blobUrl);
        } catch (err) {
            alert('İndirme hatası: ' + err.message);
        }
    }

    btnExportExcel.addEventListener('click', () => triggerDownload('/api/export/excel', 'sibercheck_domain_raporu.xlsx'));
    btnExportJson.addEventListener('click', () => triggerDownload('/api/export/json', 'sibercheck_domain_raporu.json'));
});
