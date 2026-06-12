/**
 * Blood Pressure Logger & Scanner - Client Application logic
 * Features: IndexedDB offline storage, local HTML5 canvas thresholding, 
 * Tesseract.js OCR, Chart.js trends, and print formatting.
 */

// Global App State
let db = null;
let currentPanel = 'dashboard';
let historyPeriod = 'daily';
let selectedDailyDate = new Date();
let charts = {}; // holds Chart.js instances
let tesseractWorker = null;
let activeOcrFile = null;
let editingRecordId = null;

// =============================================================================
// 1. DATABASE MANAGEMENT (IndexedDB Service)
// =============================================================================
const DB_NAME = 'bpAppDB';
const DB_VERSION = 1;

function initDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);

        request.onerror = (e) => reject('IndexedDB failed to open: ' + e.target.error);

        request.onsuccess = (e) => {
            db = e.target.result;
            resolve(db);
        };

        request.onupgradeneeded = (e) => {
            const database = e.target.result;
            
            // Readings store
            if (!database.objectStoreNames.contains('readings')) {
                const store = database.createObjectStore('readings', { keyPath: 'id', autoIncrement: true });
                store.createIndex('timestamp', 'timestamp', { unique: false });
            }
            
            // Configurations store
            if (!database.objectStoreNames.contains('config')) {
                database.createObjectStore('config', { keyPath: 'key' });
            }
        };
    });
}

// Config CRUD
function saveConfig(key, value) {
    return new Promise((resolve) => {
        const transaction = db.transaction(['config'], 'readwrite');
        const store = transaction.objectStore('config');
        store.put({ key, value });
        transaction.oncomplete = () => resolve(true);
    });
}

function getConfig(key, defaultValue = null) {
    return new Promise((resolve) => {
        const transaction = db.transaction(['config'], 'readonly');
        const store = transaction.objectStore('config');
        const request = store.get(key);
        request.onsuccess = () => resolve(request.result ? request.result.value : defaultValue);
        request.onerror = () => resolve(defaultValue);
    });
}

// Readings CRUD
function addReading(systolic, diastolic, pulse, note = "", timestamp = null) {
    return new Promise((resolve) => {
        const transaction = db.transaction(['readings'], 'readwrite');
        const store = transaction.objectStore('readings');
        
        if (!timestamp) {
            const now = new Date();
            // Format YYYY-MM-DD HH:MM:SS matching SQLite format
            timestamp = formatDateTime(now);
        }

        const record = {
            systolic: parseInt(systolic),
            diastolic: parseInt(diastolic),
            pulse: pulse ? parseInt(pulse) : null,
            note: note || "",
            timestamp: timestamp
        };

        store.add(record);
        transaction.oncomplete = () => resolve(true);
    });
}

function updateReading(id, systolic, diastolic, pulse, note, timestamp) {
    return new Promise((resolve) => {
        const transaction = db.transaction(['readings'], 'readwrite');
        const store = transaction.objectStore('readings');
        
        const record = {
            id: parseInt(id),
            systolic: parseInt(systolic),
            diastolic: parseInt(diastolic),
            pulse: pulse ? parseInt(pulse) : null,
            note: note || "",
            timestamp: timestamp
        };

        store.put(record);
        transaction.oncomplete = () => resolve(true);
    });
}

function deleteReading(id) {
    return new Promise((resolve) => {
        const transaction = db.transaction(['readings'], 'readwrite');
        const store = transaction.objectStore('readings');
        store.delete(parseInt(id));
        transaction.oncomplete = () => resolve(true);
    });
}

function getAllReadings() {
    return new Promise((resolve) => {
        const transaction = db.transaction(['readings'], 'readonly');
        const store = transaction.objectStore('readings');
        const index = store.index('timestamp');
        const request = index.getAll(); // sorted chronologically by default index
        request.onsuccess = () => resolve(request.result || []);
        request.onerror = () => resolve([]);
    });
}

// Helper: Format Dates
function formatDateTime(date) {
    const pad = (n) => n.toString().padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function formatDateOnly(date) {
    const pad = (n) => n.toString().padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

// =============================================================================
// 2. CLINICAL CLASSIFICATIONS & RANGE BAR
// =============================================================================
function getBPCategory(sys, dia) {
    if (sys < 120 && dia < 80) {
        return { name: 'Normal', color: '#10B981', percent: 10 }; // Normal Green
    } else if (sys >= 120 && sys < 130 && dia < 80) {
        return { name: 'Elevated', color: '#F59E0B', percent: 30 }; // Elevated Amber
    } else if ((sys >= 130 && sys < 140) || (dia >= 80 && dia < 90)) {
        return { name: 'High (Stage 1)', color: '#F97316', percent: 50 }; // Orange
    } else if ((sys >= 140 && sys < 180) || (dia >= 90 && dia < 120)) {
        return { name: 'High (Stage 2)', color: '#EF4444', percent: 70 }; // Red
    } else {
        return { name: 'Hypertensive Crisis', color: '#B91C1C', percent: 90 }; // Crimson
    }
}

// =============================================================================
// 3. UI TAB ROUTER
// =============================================================================
function setupNavigation() {
    const navItems = {
        'nav-dash': 'dashboard-panel',
        'nav-history': 'history-panel',
        'nav-reports': 'reports-panel',
        'nav-settings': 'settings-panel'
    };

    Object.keys(navItems).forEach(navId => {
        document.getElementById(navId).addEventListener('click', () => {
            // Remove active classes
            document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
            document.querySelectorAll('.panel').forEach(panel => panel.classList.remove('active'));

            // Set active
            document.getElementById(navId).classList.add('active');
            const targetPanelId = navItems[navId];
            document.getElementById(targetPanelId).classList.add('active');
            
            currentPanel = targetPanelId.replace('-panel', '');
            onPanelSwitch(currentPanel);
        });
    });
}

function onPanelSwitch(panelName) {
    if (panelName === 'dashboard') {
        updateDashboard();
    } else if (panelName === 'history') {
        updateHistory();
    } else if (panelName === 'reports') {
        initReportsPanel();
    } else if (panelName === 'settings') {
        initSettingsPanel();
    }
}

// =============================================================================
// 4. PANEL RENDERERS & LOGIC
// =============================================================================

// --- DASHBOARD PANEL ---
async function updateDashboard() {
    const readings = await getAllReadings();
    
    // Welcome Header Username
    const userName = await getConfig('user_name', 'User');
    document.getElementById('welcome-title').innerHTML = `Welcome back, [b]${userName}[/b]`.replace('[b]', '<b>').replace('[/b]', '</b>');
    
    if (readings.length === 0) {
        document.getElementById('dash-bp').textContent = '-- / --';
        document.getElementById('dash-pulse').textContent = '--';
        document.getElementById('dash-status-badge').textContent = 'Status: No Entries Logged Yet';
        document.getElementById('dash-status-badge').style.backgroundColor = 'var(--bg-tertiary)';
        document.getElementById('dash-status-badge').style.color = 'var(--text-primary)';
        document.getElementById('dash-range-container').style.opacity = '0';
        return;
    }

    // Get latest (last index since sorted chronologically ASC)
    const latest = readings[readings.length - 1];
    const sys = latest.systolic;
    const dia = latest.diastolic;
    const pulse = latest.pulse;
    
    // Display values
    document.getElementById('dash-bp').textContent = `${sys} / ${dia}`;
    document.getElementById('dash-pulse').textContent = pulse ? pulse : '--';
    
    // Calculate clinical severity
    const cat = getBPCategory(sys, dia);
    const badge = document.getElementById('dash-status-badge');
    badge.textContent = `Status: ${cat.name}`;
    badge.style.backgroundColor = cat.color;
    badge.style.color = '#FFFFFF';
    
    // Update pointer gauge position
    document.getElementById('dash-range-container').style.opacity = '1';
    document.getElementById('dash-range-pointer').style.left = `${cat.percent}%`;
}

// --- HISTORY PANEL ---
async function updateHistory() {
    const container = document.getElementById('history-content-area');
    container.innerHTML = ''; // Clear previous

    if (historyPeriod === 'daily') {
        renderDailyHistory(container);
    } else {
        renderChartedHistory(container);
    }
}

async function renderDailyHistory(container) {
    const targetDateStr = formatDateOnly(selectedDailyDate);
    
    // Header date picker row
    const row = document.createElement('div');
    row.style.display = 'flex';
    row.style.justify = 'space-between';
    row.style.alignItems = 'center';
    
    const formattedTitle = selectedDailyDate.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' });
    row.innerHTML = `<div>Readings for: <b>${formattedTitle}</b></div>`;
    
    // Calendar Icon trigger button
    const dateInput = document.createElement('input');
    dateInput.type = 'date';
    dateInput.value = targetDateStr;
    dateInput.className = 'form-control';
    dateInput.style.width = '130px';
    dateInput.style.padding = '8px';
    dateInput.addEventListener('change', (e) => {
        selectedDailyDate = new Date(e.target.value);
        updateHistory();
    });
    
    row.appendChild(dateInput);
    container.appendChild(row);

    // Get readings and filter
    const readings = await getAllReadings();
    const dayReadings = readings.filter(r => r.timestamp.startsWith(targetDateStr)).reverse(); // Show latest on top

    const listContainer = document.createElement('div');
    listContainer.className = 'history-list';

    if (dayReadings.length === 0) {
        listContainer.innerHTML = `<div style="text-align:center; padding: 40px 0; color:var(--text-secondary);">No logs recorded on this day.</div>`;
    } else {
        dayReadings.forEach(r => {
            const cat = getBPCategory(r.systolic, r.diastolic);
            const timeStr = r.timestamp.split(' ')[1].substring(0, 5); // Extract HH:MM
            
            const item = document.createElement('div');
            item.className = 'history-item';
            
            item.innerHTML = `
                <div class="history-left">
                    <div class="category-indicator" style="background-color: ${cat.color}"></div>
                    <div class="history-vals">
                        <div class="val-numbers">${r.systolic}/${r.diastolic} <span style="font-size:12px;font-weight:400;color:var(--text-secondary)">mmHg</span></div>
                        <div class="val-sub">Pulse: ${r.pulse || '--'} bpm | Time: ${timeStr}</div>
                        ${r.note ? `<div class="val-sub" style="font-style:italic;">"${r.note}"</div>` : ''}
                    </div>
                </div>
                <div class="history-actions">
                    <button class="icon-btn edit" data-id="${r.id}">
                        <svg viewBox="0 0 24 24"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>
                    </button>
                    <button class="icon-btn delete" data-id="${r.id}">
                        <svg viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
                    </button>
                </div>
            `;
            
            // Add click handlers
            item.querySelector('.edit').addEventListener('click', () => editReadingDialog(r));
            item.querySelector('.delete').addEventListener('click', () => confirmDeleteReading(r.id));
            
            listContainer.appendChild(item);
        });
    }
    
    container.appendChild(listContainer);
}

async function renderChartedHistory(container) {
    const readings = await getAllReadings();
    let filtered = [];
    let titleStr = '';
    
    const now = new Date();

    if (historyPeriod === 'weekly') {
        const start = new Date(now.setDate(now.getDate() - 6));
        start.setHours(0,0,0,0);
        filtered = readings.filter(r => new Date(r.timestamp) >= start);
        titleStr = `Weekly Summary: Last 7 Days`;
    } else if (historyPeriod === 'monthly') {
        const start = new Date(now.getFullYear(), now.getMonth(), 1);
        filtered = readings.filter(r => new Date(r.timestamp) >= start);
        titleStr = `Monthly Analysis: ${now.toLocaleDateString(undefined, {month:'long', year:'numeric'})}`;
    } else if (historyPeriod === 'yearly') {
        const start = new Date(now.getFullYear(), 0, 1);
        filtered = readings.filter(r => new Date(r.timestamp) >= start);
        titleStr = `Yearly Health Overview: ${now.getFullYear()}`;
    }

    // Averages Summary Card
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `<span class="overline">${titleStr}</span>`;
    
    const statsGrid = document.createElement('div');
    statsGrid.className = 'weekly-stats-grid';
    
    const stats = calculateStats(filtered);
    
    statsGrid.innerHTML = `
        <div class="stat-box">
            <div class="title">SYS AVG</div>
            <div class="value">${stats.avgSys ? Math.round(stats.avgSys) : '--'}</div>
        </div>
        <div class="stat-box">
            <div class="title">DIA AVG</div>
            <div class="value">${stats.avgDia ? Math.round(stats.avgDia) : '--'}</div>
        </div>
        <div class="stat-box">
            <div class="title">PULSE AVG</div>
            <div class="value">${stats.avgPulse ? Math.round(stats.avgPulse) : '--'}</div>
        </div>
    `;
    card.appendChild(statsGrid);
    container.appendChild(card);

    // Chart Canvas Card
    const chartCard = document.createElement('div');
    chartCard.className = 'card';
    chartCard.innerHTML = `<span class="overline">Pressure Line Trend</span>`;
    
    const canvasWrapper = document.createElement('div');
    canvasWrapper.style.position = 'relative';
    canvasWrapper.style.height = '200px';
    canvasWrapper.style.width = '100%';
    
    const canvas = document.createElement('canvas');
    canvas.id = 'trend-chart';
    canvasWrapper.appendChild(canvas);
    chartCard.appendChild(canvasWrapper);
    container.appendChild(chartCard);

    // Draw Chart
    setTimeout(() => buildChart(canvas.id, filtered), 50);
}

function calculateStats(records) {
    if (records.length === 0) return { avgSys: 0, avgDia: 0, avgPulse: 0 };
    
    let sysSum = 0, diaSum = 0, pulseSum = 0, pulseCount = 0;
    records.forEach(r => {
        sysSum += r.systolic;
        diaSum += r.diastolic;
        if (r.pulse) {
            pulseSum += r.pulse;
            pulseCount++;
        }
    });

    return {
        avgSys: sysSum / records.length,
        avgDia: diaSum / records.length,
        avgPulse: pulseCount > 0 ? pulseSum / pulseCount : 0,
        count: records.length,
        minSys: records.length > 0 ? Math.min(...records.map(r=>r.systolic)) : 0,
        maxSys: records.length > 0 ? Math.max(...records.map(r=>r.systolic)) : 0,
        minDia: records.length > 0 ? Math.min(...records.map(r=>r.diastolic)) : 0,
        maxDia: records.length > 0 ? Math.max(...records.map(r=>r.diastolic)) : 0
    };
}

function buildChart(canvasId, records) {
    // Destroy previous chart if exists
    if (charts[canvasId]) {
        charts[canvasId].destroy();
    }

    const ctx = document.getElementById(canvasId).getContext('2d');
    
    if (records.length === 0) {
        return; // Empty state
    }

    // Sort ascending
    const sorted = [...records].sort((a,b) => new Date(a.timestamp) - new Date(b.timestamp));
    
    // Labels (format date strings MM-DD HH:MM)
    const labels = sorted.map(r => {
        const dt = new Date(r.timestamp);
        return `${dt.getMonth()+1}-${dt.getDate()} ${dt.getHours().toString().padStart(2,'0')}:${dt.getMinutes().toString().padStart(2,'0')}`;
    });

    const sysData = sorted.map(r => r.systolic);
    const diaData = sorted.map(r => r.diastolic);
    
    charts[canvasId] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Systolic',
                    data: sysData,
                    borderColor: '#EF4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    borderWidth: 2,
                    tension: 0.25,
                    fill: false,
                    pointRadius: 3
                },
                {
                    label: 'Diastolic',
                    data: diaData,
                    borderColor: '#06B6D4',
                    backgroundColor: 'rgba(6, 182, 212, 0.1)',
                    borderWidth: 2,
                    tension: 0.25,
                    fill: false,
                    pointRadius: 3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    labels: { color: getComputedStyle(document.body).getPropertyValue('--text-primary').trim(), font: { size: 10 } }
                }
            },
            scales: {
                x: {
                    ticks: { color: 'var(--text-secondary)', font: { size: 8 }, maxRotation: 45 },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                },
                y: {
                    ticks: { color: 'var(--text-secondary)', font: { size: 9 } },
                    grid: { color: 'rgba(255,255,255,0.08)' }
                }
            }
        }
    });
}

// --- REPORTS PANEL ---
async function initReportsPanel() {
    const userName = await getConfig('user_name', 'User');
    document.getElementById('report-patient-name').value = userName;

    // Default dates (last 30 days)
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - 30);
    
    document.getElementById('report-start-date').value = formatDateOnly(start);
    document.getElementById('report-end-date').value = formatDateOnly(end);
    document.getElementById('report-actions-box').style.display = 'none';
}

async function compileReport() {
    const startStr = document.getElementById('report-start-date').value;
    const endStr = document.getElementById('report-end-date').value;
    const patientName = document.getElementById('report-patient-name').value.trim() || 'Patient';
    
    if (!startStr || !endStr) {
        showToast('Please enter both start and end dates.');
        return;
    }

    // Save name
    await saveConfig('user_name', patientName);

    // Query DB
    const all = await getAllReadings();
    const start = new Date(startStr);
    start.setHours(0,0,0,0);
    const end = new Date(endStr);
    end.setHours(23,59,59,999);

    const filtered = all.filter(r => {
        const dt = new Date(r.timestamp);
        return dt >= start && dt <= end;
    });

    if (filtered.length === 0) {
        showToast('No records found within this date range.');
        return;
    }

    // Update Browser Print Layout
    document.getElementById('print-metadata').textContent = `Name: ${patientName} | Period: ${startStr} to ${endStr} | Generated: ${new Date().toLocaleDateString()}`;
    
    // Fill Print Stats
    const stats = calculateStats(filtered);
    const statsTable = document.getElementById('print-stats-table');
    statsTable.innerHTML = `
        <tr>
            <td><b>Total Readings:</b></td><td>${stats.count}</td>
            <td><b>Avg Systolic:</b></td><td>${Math.round(stats.avgSys)} mmHg</td>
            <td><b>Avg Diastolic:</b></td><td>${Math.round(stats.avgDia)} mmHg</td>
        </tr>
        <tr>
            <td><b>Avg Pulse:</b></td><td>${Math.round(stats.avgPulse)} bpm</td>
            <td><b>Peak BP:</b></td><td>${stats.maxSys}/${stats.maxDia} mmHg</td>
            <td><b>Minimum BP:</b></td><td>${stats.minSys}/${stats.minDia} mmHg</td>
        </tr>
    `;

    // Draw print canvas
    buildChart('print-chart-canvas', filtered);

    // Populate print list table
    const tbody = document.getElementById('print-history-tbody');
    tbody.innerHTML = '';
    
    // Chronological Descending for report logs
    const sortedDesc = [...filtered].sort((a,b) => new Date(b.timestamp) - new Date(a.timestamp));
    sortedDesc.forEach(r => {
        const cat = getBPCategory(r.systolic, r.diastolic);
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${r.timestamp.substring(0,16)}</td>
            <td>${r.systolic} mmHg</td>
            <td>${r.diastolic} mmHg</td>
            <td>${r.pulse || '-'}</td>
            <td><span style="color:${cat.color}; font-weight:bold;">${cat.name}</span></td>
            <td>${r.note || '-'}</td>
        `;
        tbody.appendChild(row);
    });

    // Reveal print buttons
    document.getElementById('report-actions-box').style.display = 'flex';
    showToast('Report Compiled! Tap Print below.');
}

// --- SETTINGS PANEL ---
async function initSettingsPanel() {
    // Match theme buttons
    const theme = document.documentElement.getAttribute('data-theme');
    if (theme === 'light') {
        document.getElementById('theme-sun-icon').style.display = 'inline';
        document.getElementById('theme-moon-icon').style.display = 'none';
    } else {
        document.getElementById('theme-sun-icon').style.display = 'none';
        document.getElementById('theme-moon-icon').style.display = 'inline';
    }
}

async function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    await saveConfig('theme_style', newTheme);
    initSettingsPanel();
}

async function toggleContrast() {
    const bodyClass = document.body.classList;
    bodyClass.toggle('high-contrast');
    const enabled = bodyClass.contains('high-contrast');
    
    await saveConfig('high_contrast', enabled ? '1' : '0');
    showToast(enabled ? 'High Contrast Mode Enabled' : 'High Contrast Mode Disabled');
}

// =============================================================================
// 5. BACKUP, EXPORT & RESTORES
// =============================================================================
async function exportToCSV() {
    const readings = await getAllReadings();
    if (readings.length === 0) {
        showToast('No readings available to export.');
        return;
    }

    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += "id,timestamp,systolic,diastolic,pulse,note\r\n";
    
    readings.forEach(r => {
        csvContent += `${r.id},${r.timestamp},${r.systolic},${r.diastolic},${r.pulse || ''},"${r.note || ''}"\r\n`;
    });

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "BP_Records_Backup.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast('CSV Backup downloaded.');
}

async function exportToJSON() {
    const readings = await getAllReadings();
    if (readings.length === 0) {
        showToast('No readings available to export.');
        return;
    }

    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(readings, null, 2));
    const link = document.createElement("a");
    link.setAttribute("href", dataStr);
    link.setAttribute("download", "BP_Records_Backup.json");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast('JSON Backup downloaded.');
}

// RESTORE TRIGGERS
document.getElementById('btn-trigger-import-csv').addEventListener('click', () => {
    document.getElementById('backup-csv-input').click();
});

document.getElementById('btn-trigger-import-json').addEventListener('click', () => {
    document.getElementById('backup-json-input').click();
});

document.getElementById('backup-csv-input').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (event) => {
        const text = event.target.result;
        const lines = text.split('\n');
        let count = 0;
        
        // Skip header line
        for (let i = 1; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue;
            
            const cols = line.split(',');
            if (cols.length >= 4) {
                const ts = cols[1];
                const sys = parseInt(cols[2]);
                const dia = parseInt(cols[3]);
                const pulse = cols[4] ? parseInt(cols[4]) : null;
                // Clean up note quotes
                const note = cols[5] ? cols[5].replace(/^"|"$/g, '') : "";
                
                if (ts && !isNaN(sys) && !isNaN(dia)) {
                    await addReading(sys, dia, pulse, note, ts);
                    count++;
                }
            }
        }
        showToast(`Import Successful! Loaded ${count} entries.`);
        updateDashboard();
    };
    reader.readAsText(file);
});

document.getElementById('backup-json-input').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (event) => {
        try {
            const data = JSON.parse(event.target.result);
            let count = 0;
            for (const item of data) {
                if (item.timestamp && item.systolic && item.diastolic) {
                    await addReading(item.systolic, item.diastolic, item.pulse, item.note || "", item.timestamp);
                    count++;
                }
            }
            showToast(`Import Successful! Loaded ${count} entries.`);
            updateDashboard();
        } catch(err) {
            showToast('Invalid JSON file format.');
        }
    };
    reader.readAsText(file);
});

// database wipe
document.getElementById('btn-wipe-db').addEventListener('click', () => {
    if (confirm("DANGER! This will permanently delete all logged blood pressure readings. Do you want to proceed?")) {
        const transaction = db.transaction(['readings'], 'readwrite');
        const store = transaction.objectStore('readings');
        store.clear();
        transaction.oncomplete = () => {
            showToast('Database wiped.');
            updateDashboard();
        };
    }
});

// =============================================================================
// 6. MODALS & POPUPS
// =============================================================================
function openOcrModal(titleText) {
    document.getElementById('modal-title').textContent = titleText;
    document.getElementById('ocr-modal').classList.add('active');
}

function closeModal() {
    document.getElementById('ocr-modal').classList.remove('active');
    editingRecordId = null;
    activeOcrFile = null;
    
    // Clear inputs
    document.getElementById('input-sys').value = '';
    document.getElementById('input-dia').value = '';
    document.getElementById('input-pulse').value = '';
    document.getElementById('input-note').value = '';
    
    // Clear images
    document.getElementById('scan-img-preview').src = '';
    document.getElementById('scan-img-preview').style.display = 'none';
    document.getElementById('scan-canvas-preview').style.display = 'none';
    document.getElementById('ocr-loading-spinner').style.display = 'none';
}

function editReadingDialog(record) {
    editingRecordId = record.id;
    openOcrModal(`Edit Entry: ${record.timestamp.substring(0,16)}`);
    
    // Load values
    document.getElementById('input-sys').value = record.systolic;
    document.getElementById('input-dia').value = record.diastolic;
    document.getElementById('input-pulse').value = record.pulse || '';
    document.getElementById('input-note').value = record.note || '';
    
    // Hide previews since editing text record
    document.getElementById('scanner-preview-box').style.display = 'none';
}

async function confirmDeleteReading(id) {
    if (confirm("Are you sure you want to delete this reading?")) {
        await deleteReading(id);
        showToast('Reading deleted.');
        updateHistory();
        updateDashboard();
    }
}

// Save Record Button inside Modal
document.getElementById('btn-save-record').addEventListener('click', async () => {
    const sys = document.getElementById('input-sys').value.trim();
    const dia = document.getElementById('input-dia').value.trim();
    const pulse = document.getElementById('input-pulse').value.trim();
    const note = document.getElementById('input-note').value.trim();

    if (!sys || !dia) {
        showToast('Error: Systolic and Diastolic values are required.');
        return;
    }

    const s = parseInt(sys);
    const d = parseInt(dia);
    
    if (isNaN(s) || isNaN(d) || s < 40 || s > 280 || d < 30 || d > 180) {
        showToast('Error: Please enter plausible blood pressure values.');
        return;
    }

    let success = false;
    if (editingRecordId) {
        // Editing
        const readings = await getAllReadings();
        const orig = readings.find(r => r.id === editingRecordId);
        success = await updateReading(editingRecordId, s, d, pulse, note, orig.timestamp);
    } else {
        // New Add
        success = await addReading(s, d, pulse, note);
    }

    if (success) {
        showToast(editingRecordId ? 'Entry updated successfully.' : 'Entry saved successfully.');
        closeModal();
        updateDashboard();
        if (currentPanel === 'history') updateHistory();
    } else {
        showToast('Error: Failed to save record.');
    }
});

// =============================================================================
// 7. OCR IMAGE PREPROCESSING & CLIENT TESSERACT ENGINE
// =============================================================================
function preprocessImage(imgElement) {
    const canvas = document.getElementById('scan-canvas-preview');
    const ctx = canvas.getContext('2d');
    
    // 1. Resize to constant width for faster OCR execution
    const maxW = 400;
    const scale = maxW / imgElement.width;
    canvas.width = maxW;
    canvas.height = imgElement.height * scale;
    
    ctx.drawImage(imgElement, 0, 0, canvas.width, canvas.height);
    
    // 2. Grayscale & Adaptive contrast stretching
    const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const data = imgData.data;
    
    let min = 255;
    let max = 0;
    
    // First pass: Grayscale and locate min/max pixel intensities
    for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        const gray = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
        
        data[i] = gray;
        data[i + 1] = gray;
        data[i + 2] = gray;
        
        if (gray < min) min = gray;
        if (gray > max) max = gray;
    }
    
    // Second pass: Linear Contrast stretching and thresholding binarization
    // Digital LCD numbers are dark segments on lighter background.
    // Stretching expands the histogram. Binarization makes dark text stark black (0) on white (255) background.
    const spread = max - min || 1;
    const thresholdLevel = min + (spread * 0.4); // 40% threshold split level

    for (let i = 0; i < data.length; i += 4) {
        const gray = data[i];
        // Contrast stretch
        const stretched = ((gray - min) / spread) * 255;
        
        // Dynamic thresholding
        const binary = stretched < thresholdLevel ? 0 : 255;
        
        data[i] = binary;
        data[i + 1] = binary;
        data[i + 2] = binary;
    }
    
    ctx.putImageData(imgData, 0, 0);
    return canvas;
}

async function runOcrScanner(file) {
    openOcrModal("Scanning display...");
    document.getElementById('scanner-preview-box').style.display = 'block';
    
    const previewImg = document.getElementById('scan-img-preview');
    const previewCanvas = document.getElementById('scan-canvas-preview');
    const loadingSpinner = document.getElementById('ocr-loading-spinner');
    
    previewImg.style.display = 'block';
    previewCanvas.style.display = 'none';
    loadingSpinner.style.display = 'flex';
    document.getElementById('ocr-loading-text').textContent = 'Analyzing image...';

    // Load image into preview element to get dimensions
    const reader = new FileReader();
    reader.onload = (e) => {
        previewImg.src = e.target.result;
        
        previewImg.onload = async () => {
            // Apply OpenCV-like filters on HTML Canvas
            document.getElementById('ocr-loading-text').textContent = 'Pre-processing LCD pixels...';
            const binCanvas = preprocessImage(previewImg);
            
            // Swap view to thresholded canvas
            previewImg.style.display = 'none';
            binCanvas.style.display = 'block';
            
            // Load Tesseract
            document.getElementById('ocr-loading-text').textContent = 'Running Client OCR Engine...';
            
            try {
                // Initialize Tesseract client worker
                const worker = await Tesseract.createWorker('eng');
                
                // Set characters whitelist (only digits, slashes, whitespace)
                await worker.setParameters({
                    tessedit_char_whitelist: '0123456789/ \n\r'
                });
                
                const result = await worker.recognize(binCanvas);
                const text = result.data.text;
                
                await worker.terminate();
                
                console.log("OCR Recognized Text: ", text);
                
                // Parse numbers from result string
                // Extract all numbers containing 2 to 3 digits (typical BP values)
                const numbers = text.match(/\b\d{2,3}\b/g);
                
                loadingSpinner.style.display = 'none';
                
                if (numbers && numbers.length >= 2) {
                    const parsedInts = numbers.map(n => parseInt(n));
                    
                    // Sort descending to apply clinical ratio safeguard
                    // Systolic is always highest (usually 90-190)
                    // Diastolic is middle (usually 55-110)
                    // Pulse is lowest / remaining (usually 50-100)
                    const sorted = [...new Set(parsedInts)].sort((a,b) => b - a);
                    
                    let sys = null, dia = null, pulse = null;
                    
                    if (sorted.length >= 3) {
                        sys = sorted[0];
                        dia = sorted[1];
                        pulse = sorted[2];
                    } else if (sorted.length === 2) {
                        sys = sorted[0];
                        dia = sorted[1];
                    }
                    
                    // Fill inputs
                    if (sys && sys >= 70 && sys <= 250) document.getElementById('input-sys').value = sys;
                    if (dia && dia >= 35 && dia <= 150) document.getElementById('input-dia').value = dia;
                    if (pulse && pulse >= 35 && pulse <= 220) document.getElementById('input-pulse').value = pulse;
                    
                    showToast('Scan extraction complete! Confirm and edit below.');
                } else {
                    showToast('OCR scanner could not isolate digits. Please enter manually.');
                }
                
            } catch(ocrError) {
                console.error("OCR Engine Failure: ", ocrError);
                loadingSpinner.style.display = 'none';
                showToast('OCR failure. Please log manually.');
            }
        };
    };
    reader.readAsDataURL(file);
}

// =============================================================================
// 8. TOAST BANNER NOTIFICATIONS
// =============================================================================
function showToast(text) {
    const banner = document.getElementById('toast-banner');
    banner.textContent = text;
    banner.classList.add('show');
    
    setTimeout(() => {
        banner.classList.remove('show');
    }, 3200);
}

// =============================================================================
// 9. EVENTS INITIALIZATIONS
// =============================================================================
window.addEventListener('DOMContentLoaded', async () => {
    // 1. Init Database
    try {
        await initDB();
        
        // Apply saved themes on startup
        const savedTheme = await getConfig('theme_style', 'dark');
        document.documentElement.setAttribute('data-theme', savedTheme);
        
        const savedContrast = await getConfig('high_contrast', '0');
        if (savedContrast === '1') {
            document.body.classList.add('high-contrast');
        }
        
        updateDashboard();
    } catch(err) {
        console.error(err);
    }
    
    // 2. Setup Navigation tabs routing
    setupNavigation();

    // 3. Camera / Gallery upload triggers
    const camInput = document.getElementById('camera-input');
    const galInput = document.getElementById('gallery-input');

    document.getElementById('btn-camera').addEventListener('click', () => {
        camInput.click();
    });

    document.getElementById('btn-gallery').addEventListener('click', () => {
        galInput.click();
    });

    camInput.addEventListener('change', (e) => {
        if (e.target.files[0]) runOcrScanner(e.target.files[0]);
    });

    galInput.addEventListener('change', (e) => {
        if (e.target.files[0]) runOcrScanner(e.target.files[0]);
    });

    // 4. Manual Add triggers
    document.getElementById('btn-manual-add').addEventListener('click', () => {
        editingRecordId = null;
        openOcrModal("Log Reading Manually");
        document.getElementById('scanner-preview-box').style.display = 'none';
    });

    // 5. Close Modal Overlay
    document.getElementById('btn-close-modal').addEventListener('click', closeModal);

    // 6. History segment period toggles
    const historyTabs = {
        'tab-daily': 'daily',
        'tab-weekly': 'weekly',
        'tab-monthly': 'monthly',
        'tab-yearly': 'yearly'
    };

    Object.keys(historyTabs).forEach(tabId => {
        document.getElementById(tabId).addEventListener('click', (e) => {
            document.querySelectorAll('.segment-btn').forEach(btn => btn.classList.remove('active'));
            e.target.classList.add('active');
            historyPeriod = historyTabs[tabId];
            updateHistory();
        });
    });

    // 7. Settings toggles
    document.getElementById('btn-toggle-theme').addEventListener('click', toggleTheme);
    document.getElementById('btn-toggle-contrast').addEventListener('click', toggleContrast);

    // 8. Backups exports
    document.getElementById('btn-export-csv').addEventListener('click', exportToCSV);
    document.getElementById('btn-export-json').addEventListener('click', exportToJSON);

    // 9. Report triggers
    document.getElementById('btn-generate-report').addEventListener('click', compileReport);
    document.getElementById('btn-print-report').addEventListener('click', () => {
        window.print();
    });
});
