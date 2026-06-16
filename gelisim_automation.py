"""
E-Okul Gelişim Düzeyleri Girişi - Playwright Otomasyon Modülü
Tarayıcı kontrolü, sayfa analizi, kazanım tarama ve toplu uygulama.
"""

import asyncio
import sys
import random
import json
from playwright.async_api import async_playwright

# ─── Global State ─────────────────────────────────────────────────────────────
_playwright = None
_browser = None
_context = None
_page = None

logs = []
current_status = {"state": "idle", "message": "", "progress": 0, "total": 0}

GELISIM_URL = "https://e-okul.meb.gov.tr/IlkOgretim/OKL/IOK10016.aspx"
EOKUL_LOGIN_URL = "https://mebbis.meb.gov.tr/"


def log(msg: str):
    """Append a log message and print it."""
    full_msg = f"[GELİŞİM] {msg}"
    try:
        print(full_msg)
    except UnicodeEncodeError:
        print(full_msg.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
    logs.append(msg)


def set_status(state: str, message: str = "", progress: int = 0, total: int = 0):
    """Update the global status dict."""
    current_status["state"] = state
    current_status["message"] = message
    current_status["progress"] = progress
    current_status["total"] = total


# ─── Browser Lifecycle ────────────────────────────────────────────────────────

async def start_browser():
    """Launch a headed Chromium browser and navigate to e-Okul login."""
    global _playwright, _browser, _context, _page

    # If browser was closed externally, reset references
    if _page is not None and _page.is_closed():
        _page = None
        _context = None

    if _page is not None and not _page.is_closed():
        log("Tarayıcı zaten açık.")
        return {"status": "already_running"}

    if _playwright is None:
        log("Playwright başlatılıyor...")
        _playwright = await async_playwright().start()

    log("Chromium başlatılıyor (Kalıcı oturum - görünür mod)...")
    
    import os
    user_data_dir = os.path.join(os.getcwd(), "browser_data")
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)

    # Use persistent context to save cookies, session and reduce captchas
    _context = await _playwright.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=False,
        viewport={"width": 1400, "height": 900},
        args=["--disable-blink-features=AutomationControlled"]
    )
    
    if len(_context.pages) > 0:
        _page = _context.pages[0]
    else:
        _page = await _context.new_page()

    log("e-Okul giriş sayfasına yönlendiriliyor...")
    try:
        await _page.goto(EOKUL_LOGIN_URL, timeout=30000, wait_until="domcontentloaded")
        log("e-Okul giriş sayfası yüklendi. Lütfen giriş yapın.")
    except Exception as e:
        log(f"Navigasyon hatası: {e}")

    return {"status": "started"}


def _ensure_page():
    """Raise if browser/page is not available."""
    if _page is None or _page.is_closed():
        raise RuntimeError(
            "Tarayıcı kapalı veya bağlantı koptu. "
            "Lütfen 'Tarayıcıyı Aç' butonuna basın."
        )


# ─── Navigation ───────────────────────────────────────────────────────────────

async def navigate_to_gelisim():
    """Navigate to the Gelişim Düzeyleri Girişi page."""
    _ensure_page()
    log("Gelişim Düzeyleri Girişi sayfasına gidiliyor...")
    try:
        await _page.goto(GELISIM_URL, timeout=30000, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        log("Gelişim Düzeyleri Girişi sayfası yüklendi.")
        return {"status": "ok"}
    except Exception as e:
        log(f"Navigasyon hatası: {e}")
        raise


# ─── Page Scanning (Cascading Dropdowns: Sınıf → Şube → Ders) ────────────────

async def scan_all_selects():
    """
    Scan ALL <select> elements on the page and return them with their id, name, options.
    This is used for debugging and understanding the page structure.
    """
    _ensure_page()
    return await _page.evaluate("""() => {
        const result = [];
        const selects = document.querySelectorAll('select');
        for (const sel of selects) {
            const opts = [];
            for (const opt of sel.options) {
                opts.push({ value: opt.value, text: opt.text.trim(), selected: opt.selected });
            }
            result.push({
                id: sel.id,
                name: sel.name,
                optionCount: sel.options.length,
                options: opts,
                disabled: sel.disabled,
                visible: sel.offsetParent !== null
            });
        }
        return result;
    }""")

async def scan_subeler():
    """
    Scan the Şube (Class/Branch) dropdown from the page.
    This is the first dropdown we care about in the cascade.
    Returns: { subeler: [{value, text}], subeSelectId: "..." }
    """
    _ensure_page()
    log("Şube listesi taranıyor...")

    result = await _page.evaluate("""() => {
        const data = { subeler: [], subeSelectId: null };
        
        // Priority 1: Target explicitly 'cmbSubeler' as requested
        let subeSelect = document.getElementById('cmbSubeler');
        
        if (!subeSelect) {
            // Priority 2: Look for any select containing 'sube'
            const selects = document.querySelectorAll('select');
            for (const sel of selects) {
                const id = (sel.id || '').toLowerCase();
                const name = (sel.name || '').toLowerCase();
                if (id.includes('sube') || name.includes('sube')) {
                    subeSelect = sel;
                    break;
                }
            }
        }

        if (subeSelect && subeSelect.options.length > 0) {
            data.subeSelectId = subeSelect.id || subeSelect.name;
            for (const opt of subeSelect.options) {
                const t = opt.text.trim();
                if (opt.value && opt.value !== '' && opt.value !== '0' &&
                    t !== '' && !t.toLowerCase().includes('seçiniz') && !t.toLowerCase().includes('seçin')) {
                    data.subeler.push({ value: opt.value, text: t });
                }
            }
        } else {
            // Fallback strategy if 'cmbSubeler' is not found
            const selects = document.querySelectorAll('select');
            for (const sel of selects) {
                const id = (sel.id || '').toLowerCase();
                const name = (sel.name || '').toLowerCase();
                if (!id.includes('donem') && !name.includes('donem') && 
                    !id.includes('ders') && !name.includes('ders')) {
                    if (sel.options.length > 1) {
                        data.subeSelectId = sel.id;
                        for (const opt of sel.options) {
                            const t = opt.text.trim();
                            if (opt.value && opt.value !== '' && opt.value !== '0' &&
                                t !== '' && !t.toLowerCase().includes('seçiniz') && !t.toLowerCase().includes('seçin')) {
                                data.subeler.push({ value: opt.value, text: t });
                            }
                        }
                        if (data.subeler.length > 0) break;
                    }
                }
            }
        }

        return data;
    }""")

    log(f"Bulunan şubeler: {len(result.get('subeler', []))}")
    return result


async def select_sube_and_scan_dersler(sube_value: str):
    """
    Select a Şube and wait for the Ders dropdown to populate (ASP.NET postback).
    Returns: { dersler: [{value, text}], dersSelectId: "..." }
    """
    _ensure_page()
    log(f"Şube seçiliyor: {sube_value}")

    # Select sube and trigger postback
    await _page.evaluate("""(subeValue) => {
        // Priority 1: Use jQuery if available for Select2 support
        if (typeof window.jQuery !== 'undefined') {
            const $ = window.jQuery;
            const $sube = $('#cmbSubeler');
            if ($sube.length > 0) {
                $sube.val(subeValue).trigger('change');
                return;
            }
        }

        // Priority 2: Native DOM
        let subeSelect = document.getElementById('cmbSubeler');
        if (!subeSelect) {
            const selects = document.querySelectorAll('select');
            for (const sel of selects) {
                const id = (sel.id || '').toLowerCase();
                if (id.includes('sube')) {
                    subeSelect = sel;
                    break;
                }
            }
        }

        if (subeSelect) {
            subeSelect.value = subeValue;
            subeSelect.dispatchEvent(new Event('change', { bubbles: true }));
            if (typeof __doPostBack === 'function') {
                try { __doPostBack(subeSelect.name || subeSelect.id, ''); } catch(e) {}
            }
        }
    }""", sube_value)

    log("Ders listesinin yüklenmesi bekleniyor...")
    try:
        await _page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    await asyncio.sleep(2)

    # Scan Ders dropdown
    result = await _page.evaluate("""() => {
        const data = { dersler: [], dersSelectId: null };
        const selects = document.querySelectorAll('select');

        for (const sel of selects) {
            const id = (sel.id || '').toLowerCase();
            const name = (sel.name || '').toLowerCase();
            if (id.includes('ders') || name.includes('ders')) {
                data.dersSelectId = sel.id;
                for (const opt of sel.options) {
                    const t = opt.text.trim();
                    if (opt.value && opt.value !== '' && opt.value !== '0' &&
                        t !== '' && !t.toLowerCase().includes('seçiniz') && !t.toLowerCase().includes('seçin')) {
                        data.dersler.push({ value: opt.value, text: t });
                    }
                }
                break;
            }
        }

        return data;
    }""")

    log(f"Bulunan dersler: {len(result.get('dersler', []))}")
    return result


async def select_ders_and_listele(ders_value: str):
    """
    Select a Ders and click the Listele button.
    """
    _ensure_page()
    log(f"Ders seçiliyor: {ders_value}")

    await _page.evaluate("""(dersValue) => {
        // Support for Select2 if present
        if (typeof window.jQuery !== 'undefined') {
            const $ = window.jQuery;
            // Common ids for Ders
            const dersIds = ['cmbDersler', 'cmbDers', 'cmbDersSube'];
            for (const id of dersIds) {
                const $ders = $('#' + id);
                if ($ders.length > 0) {
                    $ders.val(dersValue).trigger('change');
                    return;
                }
            }
        }

        const selects = document.querySelectorAll('select');
        for (const sel of selects) {
            const id = (sel.id || '').toLowerCase();
            const name = (sel.name || '').toLowerCase();
            if (id.includes('ders') || name.includes('ders')) {
                sel.value = dersValue;
                sel.dispatchEvent(new Event('change', { bubbles: true }));
                break;
            }
        }
    }""", ders_value)

    await asyncio.sleep(1)

    # Click Listele button
    log("Listele butonuna basılıyor...")
    try:
        listele_clicked = await _page.evaluate("""() => {
            // Try by text content
            const buttons = document.querySelectorAll('input[type="submit"], input[type="button"], button, a');
            for (const btn of buttons) {
                const text = (btn.textContent || btn.value || '').trim();
                if (text.includes('Listele')) {
                    btn.click();
                    return true;
                }
            }
            // Try by ID containing 'Listele' or 'listele'
            const byId = document.querySelector('[id*="Listele"], [id*="listele"], [id*="btnListele"]');
            if (byId) {
                byId.click();
                return true;
            }
            return false;
        }""")

        if not listele_clicked:
            listele = _page.locator("text=Listele").first
            await listele.click()

        log("Listele butonuna basıldı, sayfa yükleniyor...")
        try:
            await _page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await asyncio.sleep(3)
        log("Listele başarılı, öğrenci listesi yükleniyor...")
        return {"status": "ok"}

    except Exception as e:
        log(f"Listele butonu hatası: {e}")
        raise


async def scan_students():
    """
    Scan the student list from the left panel.
    Returns list of students with their index, number, name, and the selector
    needed to click on them.
    """
    _ensure_page()
    log("Öğrenci listesi taranıyor...")

    students = await _page.evaluate("""() => {
        const students = [];

        // Look for the student table - it has columns: Sıra, Seç, Öğrenci No, Adı Soyadı
        const tables = document.querySelectorAll('table');

        for (const table of tables) {
            const rows = table.querySelectorAll('tr');
            for (let i = 0; i < rows.length; i++) {
                const cells = rows[i].querySelectorAll('td');
                if (cells.length >= 4) {
                    const sira = cells[0].textContent.trim();
                    const ogrNo = cells[2].textContent.trim();
                    const adSoyad = cells[3].textContent.trim();

                    // Check if sira is a number (skip header rows)
                    if (/^\\d+$/.test(sira)) {
                        // Find the clickable element in the "Seç" column (usually an image/link)
                        const selectBtn = cells[1].querySelector('img, a, input, button, span[onclick], div[onclick]');
                        let selectId = null;
                        if (selectBtn) {
                            selectId = selectBtn.id || null;
                            // If no ID, try to generate a css path
                            if (!selectId && selectBtn.name) selectId = selectBtn.name;
                        }

                        students.push({
                            index: parseInt(sira) - 1,
                            sira: parseInt(sira),
                            ogrenciNo: ogrNo,
                            adSoyad: adSoyad,
                            selectBtnId: selectId,
                            rowIndex: i
                        });
                    }
                }
            }
        }

        return students;
    }""")

    log(f"Toplam {len(students)} öğrenci bulundu.")
    return students


async def click_student(student_index: int):
    """
    Click on a student in the student list to load their kazanım panel.
    student_index is 0-based.
    """
    _ensure_page()
    log(f"Öğrenci {student_index + 1} seçiliyor...")

    clicked = await _page.evaluate("""(studentIdx) => {
        const tables = document.querySelectorAll('table');

        for (const table of tables) {
            const rows = table.querySelectorAll('tr');
            let studentCount = 0;

            for (let i = 0; i < rows.length; i++) {
                const cells = rows[i].querySelectorAll('td');
                if (cells.length >= 4) {
                    const sira = cells[0].textContent.trim();
                    if (/^\\d+$/.test(sira)) {
                        if (studentCount === studentIdx) {
                            // Click the select button in the second cell
                            const btn = cells[1].querySelector('img, a, input, button, span, div');
                            if (btn) {
                                btn.click();
                                return true;
                            }
                            // Try clicking the cell itself
                            cells[1].click();
                            return true;
                        }
                        studentCount++;
                    }
                }
            }
        }
        return false;
    }""", student_index)

    if not clicked:
        raise RuntimeError(f"Öğrenci {student_index + 1} seçilemedi.")

    await asyncio.sleep(2)
    log(f"Öğrenci {student_index + 1} seçildi, kazanımlar yükleniyor...")
    return {"status": "ok"}


async def scan_kazanimlar():
    """
    After clicking a student, scan all kazanım headings and their radio button options.
    This handles the accordion-style kazanım sections.

    Returns structure like:
    [
        {
            "heading": "YAPAY ZEKÂ",
            "headingIndex": 0,
            "kazanimlar": [
                {
                    "kazanimIndex": 0,
                    "siraNo": "12068",
                    "text": "Yapay zekâ uygulamalarını sınıflandırabilme...",
                    "options": [
                        {"index": 0, "text": "Günlük yaşamda karşılaşılan...", "selected": false},
                        {"index": 1, "text": "Yapay zekâ uygulamalarının çalışma...", "selected": false},
                        {"index": 2, "text": "Yapay zekâ uygulamalarını kullanım...", "selected": true},
                        {"index": 3, "text": "Yapay zekâ uygulamalarını alt...", "selected": false}
                    ]
                }
            ]
        }
    ]
    """
    _ensure_page()
    log("Kazanımlar taranıyor...")

    # First, try to expand all kazanım headings by clicking them
    await _page.evaluate("""() => {
        // Look for kazanım heading rows (typically colored bars that can be clicked)
        // These are usually in a table or div with a distinct background
        const allRows = document.querySelectorAll('tr, div');
        for (const row of allRows) {
            // Check if this is a heading row (often has a distinct background color, or contains only text)
            const style = window.getComputedStyle(row);
            const bg = style.backgroundColor;

            // Look for clickable heading elements
            const text = row.textContent.trim();
            if (text && !text.includes('Sıra') && !text.includes('Öğrenme')) {
                // Check if this row has an onclick handler or is clickable
                if (row.onclick || row.getAttribute('onclick') || row.style.cursor === 'pointer') {
                    row.click();
                }
            }
        }
    }""")

    await asyncio.sleep(1)

    # Now scan the full structure
    result = await _page.evaluate("""() => {
        const sections = [];

        // Strategy: Find the right-side panel with kazanım data
        // Look for tables that contain radio buttons (input[type="radio"])
        const radioButtons = document.querySelectorAll('input[type="radio"]');

        if (radioButtons.length === 0) {
            // Maybe it's not radio buttons, maybe it's images or icons
            // Let's look at the full page structure more carefully
            return { sections: [], rawHtml: '', debug: 'No radio buttons found' };
        }

        // Group radio buttons by name (each kazanım row has a group of radios with the same name)
        const radioGroups = {};
        for (const radio of radioButtons) {
            const name = radio.name;
            if (!radioGroups[name]) {
                radioGroups[name] = [];
            }
            radioGroups[name].push(radio);
        }

        // For each radio group, find the row it belongs to and extract info
        const kazanimlar = [];
        for (const [groupName, radios] of Object.entries(radioGroups)) {
            // Find the table row containing this radio group
            const parentRow = radios[0].closest('tr');
            if (!parentRow) continue;

            const cells = parentRow.querySelectorAll('td');
            let kazanimText = '';
            let siraNo = '';

            // Extract text from the row cells
            for (const cell of cells) {
                const text = cell.textContent.trim();
                // Skip cells that are just numbers (sira no) or contain radio buttons
                if (cell.querySelector('input[type="radio"]')) continue;
                if (/^\\d+$/.test(text) && text.length < 6) {
                    if (!siraNo) siraNo = text;
                    continue;
                }
                if (text.length > 10) {
                    kazanimText += text + ' ';
                }
            }

            const options = radios.map((radio, idx) => {
                // Try to find the label/text for this radio option
                // The text might be in the same cell or an adjacent header cell
                const cell = radio.closest('td');
                let optionText = '';

                // Look for the column header
                const table = radio.closest('table');
                if (table) {
                    const headerRow = table.querySelector('tr');
                    if (headerRow) {
                        const headerCells = headerRow.querySelectorAll('td, th');
                        const radioCell = radio.closest('td');
                        // Find which column index the radio is in
                        const row = radio.closest('tr');
                        const rowCells = row.querySelectorAll('td');
                        for (let i = 0; i < rowCells.length; i++) {
                            if (rowCells[i].contains(radio)) {
                                if (headerCells[i]) {
                                    optionText = headerCells[i].textContent.trim();
                                }
                                break;
                            }
                        }
                    }
                }

                return {
                    index: idx,
                    text: optionText || `Seçenek ${idx + 1}`,
                    value: radio.value,
                    name: radio.name,
                    id: radio.id,
                    selected: radio.checked
                };
            });

            kazanimlar.push({
                groupName: groupName,
                siraNo: siraNo,
                text: kazanimText.trim(),
                options: options
            });
        }

        // Try to identify headings (section titles like "YAPAY ZEKÂ")
        // These are typically rows with a colored background and colspan
        const headings = [];
        const tables = document.querySelectorAll('table');
        for (const table of tables) {
            if (!table.querySelector('input[type="radio"]')) continue;
            const rows = table.querySelectorAll('tr');
            for (const row of rows) {
                const cells = row.querySelectorAll('td');
                if (cells.length <= 2 && !row.querySelector('input[type="radio"]')) {
                    const text = row.textContent.trim();
                    if (text.length > 2 && text.length < 200) {
                        const style = window.getComputedStyle(row);
                        headings.push({
                            text: text,
                            bg: style.backgroundColor
                        });
                    }
                }
            }
        }

        return { kazanimlar, headings, radioGroupCount: Object.keys(radioGroups).length };
    }""")

    log(f"Tarama tamamlandı. {len(result.get('kazanimlar', []))} kazanım grubu bulundu.")
    return result

async def change_kazanim_donem(donem_val: str):
    """
    Changes the donem in the student panel, waits for reload, and returns the new kazanım list.
    """
    _ensure_page()
    log(f"Kazanım dönemi değiştiriliyor: {donem_val}. Dönem")

    try:
        await _page.evaluate("""(val) => {
        const selects = document.querySelectorAll('select.form-control');
        for (const sel of selects) {
            let hasDonemOptions = false;
            for (const opt of sel.options) {
                if (opt.value === "1" && opt.text.includes("1. Dönem") || opt.value === "2" && opt.text.includes("2. Dönem")) {
                    hasDonemOptions = true;
                    break;
                }
            }
            if (hasDonemOptions) {
                if (sel.value !== val) {
                    sel.value = val;
                    setTimeout(() => {
                        sel.dispatchEvent(new Event('change', { bubbles: true }));
                        if (typeof __doPostBack === 'function') {
                            try { __doPostBack(sel.name || sel.id, ''); } catch(e) {}
                        }
                    }, 50);
                }
                break;
            }
        }
    }""", donem_val)
    except Exception as e:
        if "Execution context was destroyed" not in str(e):
            log(f"Uyarı: {e}")
    
    log("Kazanım listesinin yenilenmesi bekleniyor...")
    try:
        await _page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    await asyncio.sleep(2)
    return await scan_kazanimlar()


async def scan_full_page_structure():
    """
    Deep scan of the page to understand its DOM structure.
    Used for initial analysis when we don't know the exact selectors.
    Returns a simplified DOM tree of the main content area.
    """
    _ensure_page()
    log("Sayfa yapısı detaylı olarak taranıyor...")

    structure = await _page.evaluate("""() => {
        function analyzeElement(el, depth = 0) {
            if (depth > 8) return null;

            const info = {
                tag: el.tagName.toLowerCase(),
                id: el.id || undefined,
                name: el.name || undefined,
                type: el.type || undefined,
                classes: el.className ? el.className.toString().substring(0, 100) : undefined,
                text: undefined,
                children: [],
                attributes: {}
            };

            // Capture relevant attributes
            if (el.onclick) info.attributes.onclick = el.getAttribute('onclick')?.substring(0, 200);
            if (el.href) info.attributes.href = el.href;
            if (el.src) info.attributes.src = el.src;
            if (el.value) info.attributes.value = el.value?.toString().substring(0, 100);

            // Get direct text content (not from children)
            const directText = Array.from(el.childNodes)
                .filter(n => n.nodeType === 3)
                .map(n => n.textContent.trim())
                .filter(t => t)
                .join(' ');

            if (directText) info.text = directText.substring(0, 200);

            // Recurse into children (skip script/style)
            for (const child of el.children) {
                if (['script', 'style', 'link', 'meta'].includes(child.tagName.toLowerCase())) continue;
                const childInfo = analyzeElement(child, depth + 1);
                if (childInfo) info.children.push(childInfo);
            }

            return info;
        }

        // Analyze the main form area
        const form = document.querySelector('form') || document.body;
        return analyzeElement(form, 0);
    }""")
async def apply_selections_to_all(students: list, selections: dict, target_donem: str = "2", random_mode: bool = False, kazanim_groups: list = None):
    """
    Iterate over the provided list of students, open their modal/panel,
    set the target_donem ("1" or "2"), apply the radio selections, and click save.
    """
    _ensure_page()
    total = len(students)
    set_status("running", "Toplu uygulama başlatılıyor...", 0, total)
    log(f"Toplu uygulama başlatılıyor. {total} öğrenci. Mod: {'Rastgele' if random_mode else 'Manuel'}")

    for i, student in enumerate(students):
        student_name = student.get("adSoyad", f"Öğrenci {i+1}")
        set_status("running", f"{student_name} işleniyor...", i + 1, total)
        log(f"[{i+1}/{total}] {student_name} işleniyor...")

        try:
            # Click on the student (Optimized sleep: wait for network/DOM instead of fixed sleep)
            await click_student(i)
            await asyncio.sleep(0.5)

            # Select the Donem for the student's kazanım list
            log(f"  {student_name} için {target_donem}. Dönem kontrol ediliyor...")
            
            donem_changed = False
            try:
                donem_changed = await _page.evaluate("""(donem_val) => {
                    const selects = document.querySelectorAll('select.form-control');
                    for (const sel of selects) {
                        let hasDonemOptions = false;
                        for (const opt of sel.options) {
                            if (opt.value === "1" && opt.text.includes("1. Dönem") || opt.value === "2" && opt.text.includes("2. Dönem")) {
                                hasDonemOptions = true;
                                break;
                            }
                        }
                        if (hasDonemOptions) {
                            if (sel.value !== donem_val) {
                                sel.value = donem_val;
                                setTimeout(() => {
                                    sel.dispatchEvent(new Event('change', { bubbles: true }));
                                    if (typeof __doPostBack === 'function') {
                                        try { __doPostBack(sel.name || sel.id, ''); } catch(e) {}
                                    }
                                }, 10);
                                return true; // changed
                            }
                            return false; // not changed
                        }
                    }
                    return false;
                }""", target_donem)
            except Exception as ev_err:
                if "Execution context was destroyed" not in str(ev_err):
                    raise ev_err
                donem_changed = True
            
            # Wait only if we actually triggered a reload
            if donem_changed:
                await asyncio.sleep(1.5)
            
            # Determine selections
            current_selections = selections
            if random_mode and kazanim_groups:
                current_selections = {}
                for group in kazanim_groups:
                    options = group.get("options", [])
                    if not options:
                        continue
                    
                    radio_name = options[0].get("name")
                    if not radio_name:
                        continue
                        
                    valid_values = [str(opt.get("value")) for opt in options if str(opt.get("value")).isdigit()]
                    if not valid_values:
                        continue
                        
                    # Seçenekleri küçükten büyüğe sırala (en iyi not en sonda olur)
                    valid_values.sort(key=int)
                    
                    weights = []
                    n_vals = len(valid_values)
                    for idx in range(n_vals):
                        dist_from_end = n_vals - 1 - idx
                        if dist_from_end == 0:     # En iyi not (örn. 5 veya en son seçenek)
                            weights.append(50)
                        elif dist_from_end == 1:   # 2. en iyi not (örn. 4)
                            weights.append(30)
                        elif dist_from_end == 2:   # 3. en iyi not (örn. 3)
                            weights.append(15)
                        elif dist_from_end == 3:   # 4. en iyi not (örn. 2)
                            weights.append(4)
                        else:                      # Diğerleri (örn. 1)
                            weights.append(1)
                            
                    chosen = random.choices(valid_values, weights=weights, k=1)[0]
                    current_selections[radio_name] = chosen

            # Apply each selection
            for radio_name, radio_value in current_selections.items():
                await _page.evaluate("""(args) => {
                    const radio = document.querySelector(
                        `input[type="radio"][name="${args.name}"][value="${args.value}"]`
                    );
                    if (radio) {
                        radio.checked = true;
                        radio.click();
                        radio.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }""", {"name": radio_name, "value": radio_value})

            # Click Kaydet
            log(f"  {student_name} için kaydediliyor...")
            await click_save()
            
            await asyncio.sleep(0.5)
            
            # Click 'Evet' (Yes) on the confirmation modal if it exists
            await _page.evaluate("""() => {
                const evetBtn = document.getElementById('modalConfirmBoxBtn1');
                if (evetBtn && evetBtn.offsetParent !== null) {
                    evetBtn.click();
                } else {
                    const buttons = document.querySelectorAll('button, .btn, input[type="button"]');
                    for (const btn of buttons) {
                        if (btn.offsetParent !== null && (btn.textContent || btn.value || '').trim().toLowerCase() === 'evet') {
                            btn.click();
                            break;
                        }
                    }
                }
            }""")
            
            await asyncio.sleep(0.5)

        except Exception as e:
            log(f"  HATA - {student_name}: {e}")
            continue

    set_status("completed", "Toplu uygulama tamamlandı!", total, total)
    log("[OK] Toplu uygulama tamamlandı!")
    return {"status": "completed", "processed": total}


async def click_save():
    """Click the Kaydet (Save) button."""
    _ensure_page()

    saved = await _page.evaluate("""() => {
        // Try multiple strategies to find the save button
        // Strategy 1: Look for button/input with "Kaydet" text
        const allClickables = document.querySelectorAll('input[type="submit"], input[type="button"], button, img, a, span');
        for (const el of allClickables) {
            const text = (el.textContent || el.value || el.alt || el.title || '').trim();
            if (text.includes('Kaydet')) {
                el.click();
                return 'clicked_by_text';
            }
        }

        // Strategy 2: Look for element with id containing 'Kaydet' or 'kaydet'
        const byId = document.querySelector('[id*="Kaydet"], [id*="kaydet"], [id*="btnKaydet"]');
        if (byId) {
            byId.click();
            return 'clicked_by_id';
        }

        // Strategy 3: Look for image with src containing 'kaydet'
        const imgs = document.querySelectorAll('img');
        for (const img of imgs) {
            if ((img.src || '').toLowerCase().includes('kaydet') ||
                (img.alt || '').toLowerCase().includes('kaydet')) {
                img.click();
                return 'clicked_by_img';
            }
        }

        return null;
    }""")

    if not saved:
        # Last resort: try Playwright locator
        try:
            await _page.locator("text=Kaydet").first.click()
            saved = "clicked_by_locator"
        except Exception:
            log("⚠️ Kaydet butonu bulunamadı!")
            raise RuntimeError("Kaydet butonu bulunamadı.")

    log(f"Kaydet butonuna basıldı ({saved}).")
    await asyncio.sleep(2)


async def get_page_html():
    """Get the full HTML of the current page for debugging."""
    _ensure_page()
    html = await _page.content()
    return html


async def close_browser():
    """Clean up browser resources."""
    global _playwright, _browser, _context, _page

    if _page and not _page.is_closed():
        await _page.close()
    if _context:
        await _context.close()
    if _browser:
        await _browser.close()
    if _playwright:
        await _playwright.stop()

    _page = None
    _context = None
    _browser = None
    _playwright = None
    log("Tarayıcı kapatıldı.")
