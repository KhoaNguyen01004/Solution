/**
 * fuel-efficiency.js
 * Dashboard controller: monthly filter, time-series chart, CRUD, anomaly detection.
 */

let allEntries = [];
let filteredEntries = [];
let sortKey = 'log_date';
let sortDir = -1;
let editingId = null;
let selectedVehicleId = null;
let chartInstance = null;
let selectedChartVehicleId = null;
let allVehicles = [];

// ── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    await populateMonthSelect();
    loadVehicles();
    loadProfiles();
    onMonthChange();
    setDefaultTime();
});

function setDefaultTime() {
    const now = new Date();
    const d = document.getElementById('field-date');
    const t = document.getElementById('field-time');
    if (d) d.value = todayISO();
    if (t) t.value = String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0');
}

function todayISO() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

// ── Month Selector ─────────────────────────────────────────────
async function populateMonthSelect() {
    const sel = document.getElementById('month-select');
    sel.innerHTML = '';
    let months = [];
    try {
        const data = await apiFetch('/api/fuel-log/months');
        months = data.data || [];
    } catch (_) {}
    if (months.length === 0) {
        const now = new Date();
        for (let i = -6; i <= 1; i++) {
            const d = new Date(now.getFullYear(), now.getMonth() + i, 1);
            months.push(`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`);
        }
    }
    const now = new Date();
    const current = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
    for (const ym of months) {
        const d = new Date(ym + '-01');
        const opt = document.createElement('option');
        opt.value = ym;
        opt.textContent = d.toLocaleDateString('en-US', { year: 'numeric', month: 'long' });
        if (ym === current) opt.selected = true;
        sel.appendChild(opt);
    }
    // If current month not in list, select the first
    if (!months.includes(current) && sel.options.length > 0) sel.options[0].selected = true;
}

function getSelectedMonth() {
    return document.getElementById('month-select').value;
}

let availableDays = [];
let selectedDay = '';

async function populateDaySelect() {
    const sel = document.getElementById('day-select');
    const month = getSelectedMonth();
    sel.innerHTML = '<option value="">All days</option>';
    availableDays = [];
    if (!month) { sel.disabled = true; return; }
    sel.disabled = false;
    try {
        const data = await apiFetch(`/api/fuel-log/days?month=${month}`);
        availableDays = data.data || [];
    } catch (_) {}
    for (const day of availableDays) {
        const opt = document.createElement('option');
        opt.value = day;
        const d = new Date(day + 'T00:00:00');
        opt.textContent = d.getDate().toString();
        if (day === selectedDay) opt.selected = true;
        sel.appendChild(opt);
    }
    // If selectedDay not in available list, reset
    if (selectedDay && !availableDays.includes(selectedDay)) {
        selectedDay = '';
        sel.value = '';
    }
}

function changeDay(delta) {
    const sel = document.getElementById('day-select');
    const idx = sel.selectedIndex + delta;
    if (idx >= 0 && idx < sel.options.length) {
        sel.selectedIndex = idx;
        onDayChange();
    }
}

function onDayChange() {
    selectedDay = document.getElementById('day-select').value;
    const dayFiltered = selectedDay ? allEntries.filter(e => e.log_date === selectedDay) : allEntries;
    recomputeStats();
    renderChart(dayFiltered);
    filterTable(document.getElementById('table-search').value);
}

function changeMonth(delta) {
    const sel = document.getElementById('month-select');
    const idx = sel.selectedIndex + delta;
    if (idx >= 0 && idx < sel.options.length) {
        sel.selectedIndex = idx;
        onMonthChange();
    }
}

function onMonthChange() {
    selectedDay = '';
    populateDaySelect();
    loadDashboard();
}

// ── API ────────────────────────────────────────────────────────
async function apiFetch(url, opts = {}) {
    const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
    opts.headers = headers;
    const resp = await fetch(url, opts);
    const data = await resp.json();
    if (!data.success) throw new Error(data.message || 'Unknown error');
    return data;
}

// ── Load Dashboard ─────────────────────────────────────────────
async function loadDashboard() {
    const month = getSelectedMonth();
    try {
        const [listData, summaryData] = await Promise.all([
            apiFetch(`/api/fuel-log?month=${month}`),
            apiFetch(`/api/fuel-log/summary?month=${month}`),
        ]);
        allEntries = listData.data || [];
        applyFilters();
        recomputeStats();
        renderChart(allEntries);
        renderTable();
        document.getElementById('entry-count').textContent = filteredEntries.length;
        loadProfiles();
    } catch (err) {
        showToast('error', `Failed to load: ${err.message}`);
    }
}

// ── Stats ───────────────────────────────────────────────────────
function recomputeStats() {
    let base = selectedChartVehicleId
        ? allEntries.filter(e => e.vehicle_id === selectedChartVehicleId)
        : allEntries;
    if (selectedDay) base = base.filter(e => e.log_date === selectedDay);
    const valid = base.filter(e => e.distance_km > 0 && e.liters > 0);
    const noKm = base.filter(e => e.distance_km === 0);
    const total_distance = valid.reduce((s, e) => s + e.distance_km, 0);
    const total_fuel = valid.reduce((s, e) => s + e.liters, 0);
    const sum_l100 = valid.reduce((s, e) => s + e.l_per_100km, 0);
    const spikeCount = valid.filter(e => e.is_anomaly).length;
    const totalEntries = base.length;
    const totalCost = base.reduce((s, e) => s + (e.total_cost || 0), 0);
    renderStats({
        total_distance,
        total_fuel: Math.round(total_fuel * 100) / 100,
        avg_l_per_100km: valid.length > 0 ? Math.round((sum_l100 / valid.length) * 100) / 100 : 0,
        entry_count: totalEntries,
        anomaly_count: spikeCount,
        no_km_count: noKm.length,
        total_cost: Math.round(totalCost * 100) / 100
    });
}

function renderStats(stats) {
    document.getElementById('kpi-distance').innerHTML = `${stats.total_distance.toLocaleString()} <span style="font-size:1rem;font-weight:400;color:#94a3b8;">km</span>`;
    document.getElementById('kpi-distance-sub').textContent = `${stats.entry_count} entries`;
    document.getElementById('kpi-fuel').innerHTML = `${stats.total_fuel.toLocaleString()} <span style="font-size:1rem;font-weight:400;color:#94a3b8;">L</span>`;
    const flags = [];
    if (stats.anomaly_count > 0) flags.push(`${stats.anomaly_count} spike`);
    if (stats.no_km_count > 0) flags.push(`${stats.no_km_count} no KM`);
    document.getElementById('kpi-fuel-sub').textContent = flags.length > 0 ? flags.join(', ') : '0 flagged';
    document.getElementById('kpi-cost').innerHTML = `${Number(stats.total_cost || 0).toLocaleString('en-US')} <span style="font-size:1rem;font-weight:400;color:#94a3b8;">VND</span>`;
    document.getElementById('kpi-avg').innerHTML = `${Number(stats.avg_l_per_100km).toFixed(2)} <span style="font-size:1rem;font-weight:400;color:#94a3b8;">L/100km</span>`;
    document.getElementById('kpi-avg-sub').textContent = stats.entry_count > 0 ? `${Number(stats.avg_l_per_100km).toFixed(2)} L/100km avg` : 'No data';
}

// ── Filtering (search only) ────────────────────────────────────
function applyFilters() {
    const q = document.getElementById('table-search').value.trim().toLowerCase();
    filteredEntries = allEntries.filter(e => {
        if (selectedDay && e.log_date !== selectedDay) return false;
        if (!q) return true;
        return e.license_plate.toLowerCase().includes(q)
            || (e.driver_name || '').toLowerCase().includes(q)
            || (e.gas_store || '').toLowerCase().includes(q);
    });
    if (sortKey) {
        filteredEntries.sort((a, b) => {
            let va = a[sortKey], vb = b[sortKey];
            if (typeof va === 'string') return va.localeCompare(vb) * sortDir;
            return ((va ?? 0) - (vb ?? 0)) * sortDir;
        });
    }
}

function filterTable(q) {
    applyFilters();
    renderTable();
    document.getElementById('entry-count').textContent = filteredEntries.length;
}

// ── Table ──────────────────────────────────────────────────────
function renderTable() {
    const tbody = document.getElementById('table-body');
    const empty = document.getElementById('empty-state');
    if (!filteredEntries.length) {
        tbody.innerHTML = '';
        empty.style.display = 'block';
        document.getElementById('entry-count').textContent = 0;
        return;
    }
    empty.style.display = 'none';

    tbody.innerHTML = filteredEntries.map(e => {
        const anomaly = e.is_anomaly;
        const noKm = e.distance_km === 0;
        const dist = e.distance_km > 0 ? fmtNum(e.distance_km) : '—';
        const l100 = e.l_per_100km > 0 ? e.l_per_100km.toFixed(2) : '—';
        const anomalyBadge = noKm
            ? '<span style="color:#f59e0b;font-size:11px;">⚠ No KM</span>'
            : anomaly
                ? '<span class="anomaly-badge">⚠ Spike</span>'
                : '<span style="color:#4ade80;font-size:11px;">✓ Normal</span>';
        const rowClass = anomaly ? 'anomaly-row' : noKm ? 'no-km-row' : '';
        return `<tr class="${rowClass}">
            <td>${formatDate(e.log_date)}</td>
            <td>${escHtml(e.log_time || '—')}</td>
            <td>${escHtml(e.gas_store || '—')}</td>
            <td><span class="plate-badge">${escHtml(e.license_plate)}</span></td>
            <td>${dist !== '—' ? `<span class="fuel-value">${dist}</span> <span class="fuel-muted">km</span>` : '<span class="fuel-muted">—</span>'}</td>
            <td><span class="fuel-value">${e.liters.toFixed(1)}</span> <span class="fuel-muted">L</span></td>
            <td><span class="fuel-value">${l100}</span></td>
            <td>${escHtml(e.driver_name || '—')}</td>
            <td>${anomalyBadge}</td>
            <td>
                <div style="display:flex;gap:6px;">
                    <button class="btn-action btn-edit" onclick="openModal(${e.id})">✏️</button>
                    <button class="btn-action btn-delete" onclick="deleteEntry(${e.id})">🗑</button>
                </div>
            </td>
        </tr>`;
    }).join('');
}

function sortTable(key) {
    if (sortKey === key) { sortDir *= -1; }
    else { sortKey = key; sortDir = 1; }
    applyFilters();
    renderTable();
}

// ── Chart (Chart.js) ───────────────────────────────────────────
function renderChart(entries) {
    const canvas = document.getElementById('efficiency-chart');
    const noData = document.getElementById('no-chart-data');

    if (chartInstance) { chartInstance.destroy(); chartInstance = null; }

    const data = entries.filter(e => e.distance_km > 0 && e.liters > 0);
    const filtered = selectedChartVehicleId
        ? data.filter(e => e.vehicle_id === selectedChartVehicleId)
        : data;

    if (filtered.length === 0) {
        noData.style.display = 'flex';
        return;
    }
    noData.style.display = 'none';

    // Build chart series: if All Vehicles, aggregate by date
    let sorted, chartEntries;
    if (selectedChartVehicleId) {
        chartEntries = [...filtered].sort((a, b) => a.log_date.localeCompare(b.log_date) || a.log_time.localeCompare(b.log_time));
        sorted = chartEntries;
    } else {
        const groups = {};
        for (const e of filtered) {
            if (!groups[e.log_date]) groups[e.log_date] = [];
            groups[e.log_date].push(e);
        }
        chartEntries = Object.keys(groups).sort().map(date => {
            const g = groups[date];
            const sumL100 = g.reduce((s, e) => s + e.l_per_100km, 0);
            const avgL100 = sumL100 / g.length;
            const isAnomaly = g.some(e => e.is_anomaly);
            const vehicles = g.map(e => e.license_plate).filter((v, i, a) => a.indexOf(v) === i);
            return {
                log_date: date,
                l_per_100km: avgL100,
                is_anomaly: isAnomaly,
                _count: g.length,
                _vehicles: vehicles.join(', ')
            };
        });
        sorted = chartEntries;
    }

    const labels = sorted.map(e => e.log_date);
    const values = sorted.map(e => e.l_per_100km);
    const anomalies = sorted.map(e => e.is_anomaly);
    const anomalyValues = sorted.map((e, i) => e.is_anomaly ? e.l_per_100km : null);

    const ctx = canvas.getContext('2d');
    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'L/100km',
                    data: values,
                    borderColor: '#2f8ceb',
                    backgroundColor: 'rgba(47,140,235,0.1)',
                    borderWidth: 2,
                    pointBackgroundColor: values.map((v, i) => anomalies[i] ? '#ef4444' : '#2f8ceb'),
                    pointBorderColor: values.map((v, i) => anomalies[i] ? '#ef4444' : '#2f8ceb'),
                    pointRadius: values.map((v, i) => anomalies[i] ? 7 : 4),
                    pointHoverRadius: values.map((v, i) => anomalies[i] ? 10 : 6),
                    fill: true,
                    tension: 0.3,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: true, mode: 'point' },
            onClick: (e, elements) => {
                if (elements.length > 0) {
                    const idx = elements[0].dataIndex;
                    const entry = sorted[idx];
                    if (entry.is_anomaly) {
                        showAnomalyTooltip(e, entry);
                    } else {
                        hideAnomalyTooltip();
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#94a3b8', maxTicksLimit: 12 },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                },
                y: {
                    beginAtZero: true,
                    ticks: { color: '#94a3b8' },
                    grid: { color: 'rgba(255,255,255,0.05)' }
                }
            },
            plugins: {
                legend: {
                    labels: { color: '#b0bec9', font: { size: 12 } }
                },
                tooltip: {
                    enabled: true,
                    backgroundColor: '#1e293b',
                    titleColor: '#f8fafc',
                    bodyColor: '#cbd5e1',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    callbacks: {
                        label: (ctx) => {
                            const e = sorted[ctx.dataIndex];
                            if (e._count) {
                                return ` ${e.l_per_100km.toFixed(2)} L/100km avg (${e._count} entries, ${e._vehicles})`;
                            }
                            return ` ${e.l_per_100km.toFixed(2)} L/100km | ${e.liters.toFixed(1)} L | ${e.distance_km} km | ${e.license_plate}`;
                        }
                    }
                }
            }
        }
    });
}

function showAnomalyTooltip(event, entry) {
    const tooltip = document.getElementById('anomaly-tooltip');
    document.getElementById('tooltip-title').textContent = `⚠ Anomaly — ${entry.license_plate}`;
    document.getElementById('tooltip-body').innerHTML = `
        <div class="row"><span>Date</span><span class="val">${entry.log_date}</span></div>
        <div class="row"><span>Distance</span><span class="val">${entry.distance_km} km</span></div>
        <div class="row"><span>Fuel</span><span class="val">${entry.liters.toFixed(1)} L</span></div>
        <div class="row"><span>Efficiency</span><span class="val">${entry.l_per_100km.toFixed(2)} L/100km</span></div>
        <div class="row"><span>Baseline</span><span class="val">${entry.baseline} L/100km</span></div>
        <div class="row"><span>Driver</span><span class="val">${entry.driver_name || '—'}</span></div>
        <div class="row"><span>Store</span><span class="val">${entry.gas_store || '—'}</span></div>
    `;
    tooltip.style.left = Math.min(event.x, window.innerWidth - 280) + 'px';
    tooltip.style.top = Math.min(event.y + 10, window.innerHeight - 300) + 'px';
    tooltip.classList.add('show');
}

function hideAnomalyTooltip() {
    document.getElementById('anomaly-tooltip').classList.remove('show');
}

document.addEventListener('click', (e) => {
    if (!e.target.closest('#anomaly-tooltip') && !e.target.closest('canvas')) {
        hideAnomalyTooltip();
    }
});

// ── Vehicle Selector (Dropdown Combobox) for Chart ────────────
async function loadVehicles() {
    try {
        const data = await apiFetch('/api/fleet/vehicles');
        allVehicles = data.data || [];
        refreshVehicleDropdown();
    } catch (_) {}
}

function refreshVehicleDropdown() {
    const input = document.getElementById('vehicle-selector');
    if (!input) return;
    // Keep current selection if still valid
    const plate = input.value.trim().toUpperCase();
    if (plate) {
        const match = allVehicles.find(v => v.plate_number.toUpperCase() === plate);
        if (!match) {
            selectedChartVehicleId = null;
            input.value = '';
        }
    }
    showVehicleDropdown();
}

function showVehicleDropdown() {
    const dropdown = document.getElementById('vehicle-dropdown-chart');
    const input = document.getElementById('vehicle-selector');
    if (!dropdown || !input) return;
    const q = input.value.trim().toLowerCase();
    const matches = q
        ? allVehicles.filter(v => v.plate_number.toLowerCase().includes(q))
        : allVehicles;
    dropdown.innerHTML = `
        <div class="autocomplete-item ${!selectedChartVehicleId ? 'selected' : ''}" onclick="selectChartVehicle(null)">All Vehicles</div>
        ${matches.map(v => `
            <div class="autocomplete-item ${selectedChartVehicleId === v.id ? 'selected' : ''}" onclick="selectChartVehicle(${v.id}, '${escHtml(v.plate_number)}')">
                ${escHtml(v.plate_number)}
                <span class="sub">${v.vehicle_type || ''}${v.current_driver ? ' — ' + escHtml(v.current_driver) : ''}</span>
            </div>
        `).join('')}
    `;
    dropdown.classList.add('open');
}

function hideVehicleDropdown() {
    document.getElementById('vehicle-dropdown-chart')?.classList.remove('open');
}

function onVehicleSelectorInput(q) {
    if (!q.trim()) {
        selectedChartVehicleId = null;
        recomputeStats();
        renderChart(allEntries);
    }
    showVehicleDropdown();
}

function selectChartVehicle(id, plate) {
    selectedChartVehicleId = id;
    const input = document.getElementById('vehicle-selector');
    if (input) input.value = id ? plate : '';
    hideVehicleDropdown();
    recomputeStats();
    renderChart(allEntries);
}

// ── Vehicle Autocomplete in Modal ──────────────────────────────
function onVehicleInput(q) {
    const dropdown = document.getElementById('vehicle-dropdown');
    if (!q.trim()) { dropdown.classList.remove('open'); selectedVehicleId = null; return; }
    const matches = allVehicles.filter(v =>
        v.plate_number.toLowerCase().includes(q.toLowerCase())
    ).slice(0, 8);
    if (matches.length === 0) { dropdown.classList.remove('open'); return; }
    dropdown.innerHTML = matches.map(v =>
        `<div class="autocomplete-item" onclick="selectVehicle(${v.id}, '${escHtml(v.plate_number)}', '${escHtml(v.vehicle_type || '')}', '${escHtml(v.current_driver || '')}')">
            ${escHtml(v.plate_number)}
            <span class="sub">${v.vehicle_type || ''} ${v.current_driver ? '— ' + escHtml(v.current_driver) : ''}</span>
        </div>`
    ).join('');
    dropdown.classList.add('open');
}

function selectVehicle(id, plate, vtype, driver) {
    selectedVehicleId = id;
    document.getElementById('field-plate').value = plate;
    document.getElementById('field-vtype').value = vtype;
    document.getElementById('field-driver').value = driver;
    document.getElementById('vehicle-dropdown').classList.remove('open');
}

// ── Modal ──────────────────────────────────────────────────────
function openModal(id = null) {
    editingId = id;
    const overlay = document.getElementById('modal-overlay');
    const title = document.getElementById('modal-title');
    const btnSave = document.getElementById('btn-save');
    selectedVehicleId = null;

    if (id) {
        const e = allEntries.find(x => x.id === id);
        title.textContent = 'Edit Refuel Entry';
        btnSave.textContent = 'Save Changes';
        selectedVehicleId = e.vehicle_id || null;
        document.getElementById('field-plate').value = e ? e.license_plate : '';
        document.getElementById('field-vtype').value = e ? (e.vehicle_type || '') : '';
        document.getElementById('field-driver').value = e ? (e.driver_name || '') : '';
        document.getElementById('field-date').value = e ? e.log_date : todayISO();
        document.getElementById('field-time').value = e ? e.log_time : '';
        document.getElementById('field-store').value = e ? (e.gas_store || '') : '';
        document.getElementById('field-old-km').value = e && e.old_km ? e.old_km : '';
        document.getElementById('field-new-km').value = e && e.new_km ? e.new_km : '';
        document.getElementById('field-liters').value = e ? e.liters : '';
        document.getElementById('field-price').value = e ? (e.unit_price || '') : '';
        document.getElementById('field-notes').value = e ? (e.notes || '') : '';
    } else {
        title.textContent = 'Add Refuel Entry';
        btnSave.textContent = 'Save Entry';
        document.getElementById('field-plate').value = '';
        document.getElementById('field-vtype').value = '';
        document.getElementById('field-driver').value = '';
        document.getElementById('field-store').value = '';
        document.getElementById('field-old-km').value = '';
        document.getElementById('field-new-km').value = '';
        document.getElementById('field-liters').value = '';
        document.getElementById('field-price').value = '';
        document.getElementById('field-notes').value = '';
        setDefaultTime();
        setTimeout(() => document.getElementById('field-plate').focus(), 200);
    }
    overlay.classList.add('open');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('open');
    editingId = null;
    selectedVehicleId = null;
}

function handleOverlayClick(e) {
    if (e.target === document.getElementById('modal-overlay')) closeModal();
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

// ── Save Entry ─────────────────────────────────────────────────
async function saveEntry() {
    const plate = document.getElementById('field-plate').value.trim().toUpperCase();
    const date = document.getElementById('field-date').value.trim();
    const time = document.getElementById('field-time').value.trim();
    const store = document.getElementById('field-store').value.trim();
    const oldKmVal = document.getElementById('field-old-km').value.trim();
    const newKmVal = document.getElementById('field-new-km').value.trim();
    const hasKm = oldKmVal !== '' && newKmVal !== '';
    const oldKm = hasKm ? parseInt(oldKmVal, 10) || 0 : 0;
    const newKm = hasKm ? parseInt(newKmVal, 10) || 0 : 0;
    const liters = parseFloat(document.getElementById('field-liters').value);
    const driver = document.getElementById('field-driver').value.trim();
    const price = document.getElementById('field-price').value.trim();
    const notes = document.getElementById('field-notes').value.trim();

    if (!plate) return showToast('warning', 'Select a vehicle.');
    if (!date) return showToast('warning', 'Date is required.');
    if (!time) return showToast('warning', 'Time is required.');
    if (isNaN(liters) || liters <= 0) return showToast('warning', 'Liters must be > 0.');
    if (newKm > 0 && oldKm > 0 && newKm < oldKm) return showToast('warning', 'New KM must be >= Old KM.');
    if (newKm - oldKm > 2000 && !confirm('Distance exceeds 2000 km — are you sure?')) return;

    const payload = {
        license_plate: plate,
        log_date: date, log_time: time, gas_store: store,
        old_km: oldKm, new_km: newKm, liters,
        driver_name: driver, notes,
        vehicle_id: selectedVehicleId
    };
    if (price) payload.unit_price = parseFloat(price);

    const btn = document.getElementById('btn-save');
    btn.disabled = true;
    btn.innerHTML = '<span class="spin"></span> Saving…';

    try {
        if (editingId) {
            const result = await apiFetch(`/api/fuel-log/${editingId}`, { method: 'PUT', body: JSON.stringify(payload) });
            if (result.warnings) result.warnings.forEach(w => showToast('warning', w, 6000));
            showToast('success', 'Entry updated.');
        } else {
            const result = await apiFetch('/api/fuel-log', { method: 'POST', body: JSON.stringify(payload) });
            if (result.warnings) result.warnings.forEach(w => showToast('warning', w, 6000));
            showToast('success', 'Entry created.');
        }
        closeModal();
        await loadDashboard();
        await loadProfiles();
    } catch (err) {
        showToast('error', err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = editingId ? 'Save Changes' : 'Save Entry';
    }
}

// ── Delete Entry ───────────────────────────────────────────────
async function deleteEntry(id) {
    const entry = allEntries.find(e => e.id === id);
    const label = entry ? `${entry.license_plate} on ${entry.log_date}` : `#${id}`;
    if (!confirm(`Delete entry for ${label}?`)) return;
    try {
        await apiFetch(`/api/fuel-log/${id}`, { method: 'DELETE' });
        showToast('success', 'Entry deleted.');
        await loadDashboard();
        await loadProfiles();
    } catch (err) {
        showToast('error', err.message);
    }
}

// ── Export CSV ─────────────────────────────────────────────────
function exportCsv() {
    const month = getSelectedMonth();
    const a = document.createElement('a');
    a.href = `/api/fuel-log/export?month=${month}`;
    a.download = 'fuel_efficiency_report.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

// ── Vehicle Baselines ──────────────────────────────────────────
async function loadProfiles() {
    try {
        const data = await apiFetch('/api/fuel-log/profiles');
        renderProfiles(data.data || []);
    } catch (_) {}
}

function renderProfiles(profiles) {
    const tbody = document.getElementById('profile-body');
    const empty = document.getElementById('profile-empty');
    document.getElementById('profile-count').textContent = profiles.length;

    if (!profiles.length) {
        tbody.innerHTML = '';
        empty.style.display = 'block';
        return;
    }
    empty.style.display = 'none';

    const sorted = [...profiles].sort((a, b) => a.license_plate.localeCompare(b.license_plate));
    tbody.innerHTML = sorted.map(p => {
        const normal = p.normal_l_per_100km || 0;
        const updated = p.updated_at ? formatDateTime(p.updated_at) : '—';
        return `<tr>
            <td><span class="plate-badge">${escHtml(p.license_plate)}</span></td>
            <td>
                <span class="fuel-value" id="nd-${escHtml(p.license_plate)}">${normal > 0 ? normal.toFixed(2) : '—'} <span class="fuel-muted">L/100km</span></span>
                <input type="number" step="0.1" min="1" max="99" class="field-input" style="width:90px;display:none;padding:5px 8px;" id="ni-${escHtml(p.license_plate)}" value="${normal > 0 ? normal : ''}">
            </td>
            <td style="color:#94a3b8;font-size:12px;">${updated}</td>
            <td>
                <div style="display:flex;gap:6px;">
                    <button class="btn-action btn-edit" id="neb-${escHtml(p.license_plate)}" onclick="editNormal('${escHtml(p.license_plate)}')">✏️</button>
                    <button class="btn-action btn-edit" style="display:none;background:rgba(16,185,129,0.15);color:#34d399;border:1px solid rgba(16,185,129,0.25);" id="nsb-${escHtml(p.license_plate)}" onclick="saveNormal('${escHtml(p.license_plate)}')">💾</button>
                    <button class="btn-action btn-delete" id="ncb-${escHtml(p.license_plate)}" ${normal > 0 ? '' : 'style="display:none;"'} onclick="clearNormal('${escHtml(p.license_plate)}')">🗑</button>
                </div>
            </td>
        </tr>`;
    }).join('');
}

function editNormal(plate) {
    const sid = escHtml(plate);
    document.getElementById(`nd-${sid}`).style.display = 'none';
    const inp = document.getElementById(`ni-${sid}`);
    inp.style.display = 'inline-block'; inp.focus();
    document.getElementById(`neb-${sid}`).style.display = 'none';
    document.getElementById(`nsb-${sid}`).style.display = 'inline-flex';
}

async function saveNormal(plate) {
    const val = parseFloat(document.getElementById(`ni-${escHtml(plate)}`).value);
    if (isNaN(val) || val <= 0) return showToast('warning', 'Enter a valid L/100km > 0.');
    try {
        await apiFetch(`/api/fuel-log/profiles/${encodeURIComponent(plate)}`, {
            method: 'PUT', body: JSON.stringify({ normal_l_per_100km: val })
        });
        showToast('success', `Normal for ${plate}: ${val.toFixed(2)} L/100km`);
        await loadProfiles();
        await loadDashboard();
    } catch (err) {
        showToast('error', err.message);
    }
}

async function clearNormal(plate) {
    if (!confirm(`Clear normal for ${plate}? Will revert to computed baseline.`)) return;
    try {
        await apiFetch(`/api/fuel-log/profiles/${encodeURIComponent(plate)}`, { method: 'DELETE' });
        showToast('success', `Normal for ${plate} cleared.`);
        await loadProfiles();
        await loadDashboard();
    } catch (err) {
        showToast('error', err.message);
    }
}

// ── Tooltip hide on scroll ─────────────────────────────────────
document.addEventListener('scroll', hideAnomalyTooltip);

// ── Utilities ──────────────────────────────────────────────────
function formatDate(iso) {
    if (!iso) return '—';
    const [y, m, d] = iso.split('-');
    return `${d}/${m}/${y}`;
}

function formatDateTime(iso) {
    if (!iso) return '—';
    try {
        const d = new Date(iso);
        return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${d.getFullYear()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
    } catch { return iso; }
}

function escHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtNum(n) {
    return (n == null || isNaN(n)) ? '0' : Number(n).toLocaleString('en-US');
}

function showToast(type, message, duration = 4500) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span class="toast-msg">${escHtml(message)}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.transition = 'opacity 0.4s, transform 0.4s';
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 400);
    }, duration);
}