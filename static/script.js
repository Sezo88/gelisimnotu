/**
 * E-Okul Gelişim Düzeyleri Girişi - Frontend Logic
 * Step-by-step wizard controller
 */

// ─── State ──────────────────────────────────────────────────────────────────
let currentStep = 1;
let students = [];
let kazanimData = null;
let selectedSelections = {};  // { radioGroupName: radioValue }
let pollingInterval = null;

// ─── API Helpers ────────────────────────────────────────────────────────────

async function apiPost(endpoint, data = {}) {
    try {
        const resp = await fetch(`/api/${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || 'İstek başarısız');
        }
        return await resp.json();
    } catch (e) {
        showToast(e.message, 'error');
        throw e;
    }
}

async function apiGet(endpoint) {
    try {
        const resp = await fetch(`/api/${endpoint}`);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            throw new Error(err.detail || 'İstek başarısız');
        }
        return await resp.json();
    } catch (e) {
        showToast(e.message, 'error');
        throw e;
    }
}


// ─── Step Navigation ────────────────────────────────────────────────────────

function goToStep(step) {
    currentStep = step;

    // Update step indicators
    document.querySelectorAll('.step').forEach(el => {
        const s = parseInt(el.dataset.step);
        el.classList.remove('active', 'completed');
        if (s === step) el.classList.add('active');
        else if (s < step) el.classList.add('completed');
    });

    // Update step lines
    const lines = document.querySelectorAll('.step-line');
    lines.forEach((line, i) => {
        line.classList.toggle('completed', i < step - 1);
    });

    // Show/hide cards
    for (let i = 1; i <= 5; i++) {
        const card = document.getElementById(`step${i}Card`);
        if (card) {
            if (i <= step) {
                card.classList.remove('hidden');
            } else {
                card.classList.add('hidden');
            }
        }
    }
}


// ─── Step 1: Start Browser ──────────────────────────────────────────────────

async function startBrowser() {
    const btn = document.getElementById('btnStartBrowser');
    btn.classList.add('loading');
    btn.disabled = true;
    btn.classList.remove('pulse-btn');

    try {
        await apiPost('start-browser');
        showToast('Tarayıcı başlatıldı! Lütfen e-Okul\'a giriş yapın.', 'success');
        setStatus('connected', 'Tarayıcı Açık');
        addLog('Tarayıcı başlatıldı. e-Okul giriş sayfası açıldı.', 'success');

        // Show step 2
        goToStep(2);
    } catch (e) {
        addLog('Tarayıcı başlatılamadı: ' + e.message, 'error');
    } finally {
        btn.classList.remove('loading');
        btn.disabled = false;
    }
}


// ─── Step 2: Navigate to Gelisim Page ───────────────────────────────────────

async function navigateToGelisim() {
    const btn = document.getElementById('btnNavigate');
    btn.classList.add('loading');
    btn.disabled = true;

    try {
        await apiPost('navigate-gelisim');
        showToast('Gelişim Düzeyleri sayfasına gidildi.', 'success');
        addLog('Gelişim Düzeyleri Girişi sayfası yüklendi.', 'success');

        // Scan şube dropdown
        addLog('Sınıf/Şube listesi taranıyor...', 'info');
        const subeData = await apiPost('scan-subeler');
        populateSubeler(subeData);
        goToStep(3);
    } catch (e) {
        addLog('Navigasyon hatası: ' + e.message, 'error');
    } finally {
        btn.classList.remove('loading');
        btn.disabled = false;
    }
}

function populateSubeler(data) {
    const subeSelect = document.getElementById('subeSelect');
    subeSelect.innerHTML = '<option value="">-- Sınıf/Şube Seçin --</option>';

    if (data.subeler && data.subeler.length > 0) {
        data.subeler.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.value;
            opt.textContent = s.text;
            subeSelect.appendChild(opt);
        });
        addLog(`${data.subeler.length} sınıf/şube bulundu.`, 'info');
    } else {
        addLog('Sınıf/Şube listesi boş veya bulunamadı!', 'warning');
    }

    // Reset downstream dropdowns
    resetDersSelect();
    document.getElementById('btnListele').disabled = true;
}

function resetDersSelect() {
    const dersSelect = document.getElementById('dersSelect');
    dersSelect.innerHTML = '<option value="">Önce sınıf/şube seçin</option>';
    dersSelect.disabled = true;
    dersSelect.classList.remove('loading-select');
}

// ─── Cascade: Şube → Ders ───────────────────────────────────────────────────

async function onSubeChanged() {
    const subeValue = document.getElementById('subeSelect').value;

    // Reset downstream
    resetDersSelect();
    document.getElementById('btnListele').disabled = true;

    if (!subeValue) return;

    const dersSelect = document.getElementById('dersSelect');
    dersSelect.innerHTML = '<option value="">Yükleniyor...</option>';
    dersSelect.classList.add('loading-select');

    try {
        addLog('Şube seçildi, ders listesi yükleniyor...', 'info');
        const data = await apiPost('select-sube', { subeValue: subeValue });

        dersSelect.classList.remove('loading-select');
        dersSelect.innerHTML = '<option value="">-- Ders Seçin --</option>';

        if (data.dersler && data.dersler.length > 0) {
            data.dersler.forEach(d => {
                const opt = document.createElement('option');
                opt.value = d.value;
                opt.textContent = d.text;
                dersSelect.appendChild(opt);
            });
            dersSelect.disabled = false;
            // Enable Listele when a ders is selected
            dersSelect.addEventListener('change', onDersChanged);
            addLog(`${data.dersler.length} ders bulundu.`, 'success');
        } else {
            dersSelect.innerHTML = '<option value="">Ders bulunamadı</option>';
            addLog('Ders listesi boş!', 'warning');
        }
    } catch (e) {
        dersSelect.classList.remove('loading-select');
        dersSelect.innerHTML = '<option value="">Hata oluştu</option>';
        addLog('Ders yükleme hatası: ' + e.message, 'error');
    }
}

function onDersChanged() {
    const dersValue = document.getElementById('dersSelect').value;
    document.getElementById('btnListele').disabled = !dersValue;
}


// ─── Step 3: Select Ders & Listele ──────────────────────────────────────────

async function selectDersAndListele() {
    const dersValue = document.getElementById('dersSelect').value;

    if (!dersValue) {
        showToast('Lütfen bir ders seçin.', 'error');
        return;
    }

    const btn = document.getElementById('btnListele');
    btn.classList.add('loading');
    btn.disabled = true;

    try {
        addLog('Ders seçilip Listele yapılıyor...', 'info');
        await apiPost('select-ders-and-listele', { dersValue: dersValue });

        addLog('Listele tamamlandı. Öğrenci listesi taranıyor...', 'success');

        // Scan students
        const studentData = await apiPost('scan-students');
        students = studentData.students || [];

        if (students.length === 0) {
            showToast('Öğrenci bulunamadı!', 'error');
            addLog('Öğrenci listesi boş!', 'warning');
            return;
        }

        addLog(`${students.length} öğrenci bulundu.`, 'success');

        // Click first student to load kazanımlar
        addLog('İlk öğrenci seçiliyor...', 'info');
        await apiPost('click-student', { studentIndex: 0 });

        // Scan kazanımlar
        addLog('Kazanımlar taranıyor...', 'info');
        kazanimData = await apiPost('scan-kazanimlar');

        // Render kazanımlar for user selection
        renderKazanimlar(kazanimData);

        // Update student count
        document.getElementById('studentCount').textContent = `${students.length} öğrenci`;
        const kazanimCount = kazanimData.kazanimlar ? kazanimData.kazanimlar.length : 0;
        document.getElementById('kazanimCount').textContent = `${kazanimCount} kazanım`;

        goToStep(4);
        showToast(`${students.length} öğrenci, ${kazanimCount} kazanım bulundu.`, 'success');

    } catch (e) {
        addLog('Hata: ' + e.message, 'error');
    } finally {
        btn.classList.remove('loading');
        btn.disabled = false;
    }
}


// ─── Kazanım Rendering ─────────────────────────────────────────────────────

async function changeKazanimDonem() {
    const donemVal = document.getElementById('targetDonemSelect').value;
    
    // Show loading state
    const container = document.getElementById('kazanimContainer');
    container.innerHTML = `
        <div class="kazanim-loading">
            <div class="spinner"></div>
            <p>${donemVal}. Dönem kazanımları yükleniyor...</p>
        </div>
    `;
    document.getElementById('btnApplyAll').disabled = true;

    try {
        addLog(`${donemVal}. Dönem kazanımları getiriliyor...`, 'info');
        kazanimData = await apiPost('change-kazanim-donem', { donem: donemVal });
        
        // Reset selections
        currentSelections = {};
        selectedSelections = {};
        
        renderKazanimlar(kazanimData);
        document.getElementById('btnApplyAll').disabled = false;
        showToast(`${donemVal}. Dönem kazanımları yüklendi.`, 'success');
        addLog('Kazanım dönemi değiştirildi.', 'success');
    } catch (e) {
        container.innerHTML = `
            <div class="alert alert-danger">
                <strong>Hata:</strong> ${e.message}
            </div>
        `;
        addLog('Kazanım dönemi değiştirilirken hata: ' + e.message, 'error');
    }
}

function renderKazanimlar(data) {
    const container = document.getElementById('kazanimContainer');
    container.innerHTML = '';

    if (!data || !data.kazanimlar || data.kazanimlar.length === 0) {
        container.innerHTML = `
            <div class="kazanim-card">
                <div class="kazanim-header">
                    <div class="kazanim-text" style="color: var(--accent-amber);">
                        Kazanım bulunamadı. Sayfayı yeniden taramayı deneyin veya
                        sayfada kazanım başlıklarını manuel olarak açın.
                    </div>
                </div>
                <button class="btn btn-secondary" onclick="retryScanKazanimlar()" style="margin-top: 10px; width: auto;">
                    Tekrar Tara
                </button>
            </div>
        `;
        return;
    }

    // Add headings if available
    if (data.headings && data.headings.length > 0) {
        data.headings.forEach(h => {
            const heading = document.createElement('div');
            heading.className = 'kazanim-section-heading';
            heading.textContent = h.text;
            container.appendChild(heading);
        });
    }

    // Render each kazanım
    data.kazanimlar.forEach((kaz, index) => {
        const card = document.createElement('div');
        card.className = 'kazanim-card';
        card.dataset.groupName = kaz.groupName;

        let optionsHtml = '';
        kaz.options.forEach((opt, optIdx) => {
            const radioId = `kaz_${index}_opt_${optIdx}`;
            const checked = opt.selected ? 'checked' : '';
            const selectedClass = opt.selected ? 'selected' : '';

            optionsHtml += `
                <label class="kazanim-option ${selectedClass}" for="${radioId}" onclick="selectOption(this, '${kaz.groupName}', '${opt.value}')">
                    <input type="radio" id="${radioId}" name="kaz_group_${index}" value="${opt.value}" ${checked}>
                    <span class="kazanim-option-text">${opt.text}</span>
                </label>
            `;

            // If pre-selected, store it
            if (opt.selected) {
                selectedSelections[kaz.groupName] = opt.value;
            }
        });

        card.innerHTML = `
            <div class="kazanim-header">
                <div class="kazanim-number">${index + 1}</div>
                <div class="kazanim-text">${kaz.text || `Kazanım #${kaz.siraNo || (index + 1)}`}</div>
            </div>
            <div class="kazanim-options">
                ${optionsHtml}
            </div>
        `;

        container.appendChild(card);
    });
}

function selectOption(labelEl, groupName, value) {
    // Update visual state
    const parent = labelEl.closest('.kazanim-card');
    parent.querySelectorAll('.kazanim-option').forEach(opt => opt.classList.remove('selected'));
    labelEl.classList.add('selected');

    // Store selection
    selectedSelections[groupName] = value;
}

async function retryScanKazanimlar() {
    try {
        addLog('Kazanımlar tekrar taranıyor...', 'info');
        kazanimData = await apiPost('scan-kazanimlar');
        renderKazanimlar(kazanimData);

        const kazanimCount = kazanimData.kazanimlar ? kazanimData.kazanimlar.length : 0;
        document.getElementById('kazanimCount').textContent = `${kazanimCount} kazanım`;

        if (kazanimCount > 0) {
            showToast(`${kazanimCount} kazanım bulundu.`, 'success');
        }
    } catch (e) {
        addLog('Tarama hatası: ' + e.message, 'error');
    }
}


// ─── Step 5: Apply All ──────────────────────────────────────────────────────

function toggleMode() {
    const mode = document.querySelector('input[name="selectionMode"]:checked').value;
    const container = document.getElementById('kazanimContainer');
    const studentInfo = document.getElementById('studentInfoBar');
    const descText = document.getElementById('modeDescriptionText');
    
    if (mode === 'random') {
        container.style.opacity = '0.4';
        container.style.pointerEvents = 'none';
        descText.textContent = "Sistem, bot olarak algılanmamak için öğrencilere her bir kazanımı çoğunlukla 5 ve 4 olmak üzere farklı notlarla otomatik atar.";
    } else {
        container.style.opacity = '1';
        container.style.pointerEvents = 'auto';
        descText.textContent = "Sizin belirlediğiniz puanlar tüm öğrencilere aynen işlenir.";
    }
}

async function applyAll() {
    // Validate selections
    if (!kazanimData || !kazanimData.kazanimlar) {
        showToast('Önce kazanımları tarayın.', 'error');
        return;
    }

    const totalKazanim = kazanimData.kazanimlar.length;
    let totalSelected = Object.keys(selectedSelections).length;
    const isRandomMode = document.querySelector('input[name="selectionMode"]:checked') && document.querySelector('input[name="selectionMode"]:checked').value === 'random';

    if (!isRandomMode) {
        if (totalSelected === 0) {
            showToast('Lütfen en az bir kazanım için seçim yapın.', 'error');
            return;
        }

        if (totalSelected < totalKazanim) {
            const proceed = confirm(
                `${totalKazanim} kazanımdan sadece ${totalSelected} tanesi için seçim yaptınız.\n` +
                `Seçim yapılmayan kazanımlar atlanacaktır.\n\n` +
                `Devam etmek istiyor musunuz?`
            );
            if (!proceed) return;
        }
    } else {
        totalSelected = totalKazanim; // Fake it for the log
    }

    const confirmMsg = `${students.length} öğrenciye ${isRandomMode ? 'rastgele' : totalSelected} kazanım seçimi uygulanacak.\n\n` +
        `Bu işlem geri alınamaz. Devam etmek istiyor musunuz?`;
    if (!confirm(confirmMsg)) return;

    // Show progress card
    goToStep(5);

    const btn = document.getElementById('btnApplyAll');
    btn.classList.add('loading');
    btn.disabled = true;

    setStatus('running', 'Uygulama Devam Ediyor');

    // Start polling for progress
    startProgressPolling();

    try {
        addLog(`Toplu uygulama başlatılıyor: ${students.length} öğrenci. Mod: ${isRandomMode ? 'Rastgele' : 'Manuel'}`, 'info');

        const targetDonem = document.getElementById('targetDonemSelect') ? document.getElementById('targetDonemSelect').value : "2";

        const result = await apiPost('apply-all', {
            students: students,
            selections: isRandomMode ? {} : selectedSelections,
            donem: targetDonem,
            random_mode: isRandomMode,
            kazanim_groups: isRandomMode ? kazanimData.kazanimlar : []
        });

        stopProgressPolling();
        updateProgress(students.length, students.length, 'Tamamlandı!');

        showToast('✅ Toplu uygulama tamamlandı!', 'success');
        addLog('Toplu uygulama başarıyla tamamlandı!', 'success');
        setStatus('connected', 'Tamamlandı');

    } catch (e) {
        stopProgressPolling();
        addLog('Toplu uygulama hatası: ' + e.message, 'error');
        setStatus('error', 'Hata');
    } finally {
        btn.classList.remove('loading');
        btn.disabled = false;
    }
}


// ─── Progress Polling ───────────────────────────────────────────────────────

function startProgressPolling() {
    pollingInterval = setInterval(async () => {
        try {
            const status = await apiGet('status');
            updateProgress(status.progress, status.total, status.message);
        } catch (e) {
            // Silent fail for polling
        }
    }, 1500);
}

function stopProgressPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

function updateProgress(current, total, message) {
    const percent = total > 0 ? Math.round((current / total) * 100) : 0;

    document.getElementById('progressText').textContent = message || 'İşleniyor...';
    document.getElementById('progressPercent').textContent = `${percent}%`;
    document.getElementById('progressBar').style.width = `${percent}%`;
    document.getElementById('progressDetail').textContent = `${current} / ${total} öğrenci`;
}


// ─── Status & Logs ──────────────────────────────────────────────────────────

function setStatus(state, text) {
    const badge = document.getElementById('statusBadge');
    badge.className = 'status-badge ' + state;
    badge.querySelector('.status-text').textContent = text;
}

function addLog(message, type = 'info') {
    const container = document.getElementById('logsContainer');
    const entry = document.createElement('div');
    entry.className = `log-entry log-${type}`;
    const time = new Date().toLocaleTimeString('tr-TR');
    entry.textContent = `[${time}] ${message}`;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;

    // Also expand logs if collapsed
    const logsBody = document.getElementById('logsBody');
    if (logsBody.classList.contains('collapsed') && type === 'error') {
        logsBody.classList.remove('collapsed');
    }
}

function toggleLogs() {
    const logsBody = document.getElementById('logsBody');
    const chevron = document.getElementById('logsChevron');
    logsBody.classList.toggle('collapsed');
    chevron.style.transform = logsBody.classList.contains('collapsed') ? 'rotate(-90deg)' : '';
}


// ─── Toast Notifications ────────────────────────────────────────────────────

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('removing');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}


// ─── Log Polling (periodic refresh) ─────────────────────────────────────────

async function refreshLogs() {
    try {
        const data = await apiGet('logs');
        if (data.logs && data.logs.length > 0) {
            const container = document.getElementById('logsContainer');
            // Only add new logs
            const currentCount = container.children.length;
            if (data.logs.length > currentCount) {
                for (let i = currentCount; i < data.logs.length; i++) {
                    const entry = document.createElement('div');
                    const msg = data.logs[i];
                    let type = 'info';
                    if (msg.includes('HATA') || msg.includes('Error') || msg.includes('Failed')) type = 'error';
                    else if (msg.includes('✅') || msg.includes('başarı') || msg.includes('tamamlandı')) type = 'success';
                    else if (msg.includes('⚠️')) type = 'warning';

                    entry.className = `log-entry log-${type}`;
                    entry.textContent = msg;
                    container.appendChild(entry);
                }
                container.scrollTop = container.scrollHeight;
            }
        }
    } catch (e) {
        // Silent fail
    }
}


// ─── Initialize ─────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    goToStep(1);

    // Periodic log refresh every 3 seconds
    setInterval(refreshLogs, 3000);
});
