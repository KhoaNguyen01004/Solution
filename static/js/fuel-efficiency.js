/**
 * fuel-efficiency.js
 * Controller for the Fuel Efficiency / Refuel Log dashboard.
 */

let allEntries = [];
let filteredEntries = [];
let allVehicles = [];
let sortKey = 'log_date';
let sortDir = -1;
let editingId = null;

const SORT_ICONS = { asc: '▲', desc: '▼' };

document.addEventListener('DOMContentLoaded', () => {
    loadEntries();
    loadProfiles();
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, '0');
    const d = String(now.getDate()).padStart(2, '0');
    const hh = String(now.getHours()).padStart(2, '0');
    const mm = String(now.getMinutes()).padStart(2, '0');
    const dateField = document.getElementById('field-date');
    const timeField = document.getElementById('field-time');
    if (dateField) dateField.value = `${y}-${m}-${d}`;
    if (timeField) timeField.value = `${hh}:${mm}`;
});

async function apiFetch(url, opts = {}) {
    const defaultHeaders = { 'Content-Type': 'application/json' };
    opts.headers = { ...defaultHeaders, ...(opts.headers || {}) };
    const resp = await fetch(url, opts);
    const data = await resp.json();
    if (!data.success) throw new Error(data.message || 'Unknown error');
    return data;
}

async function loadEntries() {
    try {
        const summaryData = await apiFetch('/api/fuel-log/summary');
        const data = await apiFetch('/api/fuel-log');
        allEntries = data.data || [];
        filteredEntries = [...allEntries];

        const plates = [...new Set(allEntries.map(e => e.license_plate).filter(Boolean))].sort();
        allVehicles = plates;
        const filter = document.getElementById('vehicle-filter');
        const currentVal = filter.value;
        filter.innerHTML = '<option value="">All Vehicles</option>';
        plates.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p;
            opt.textContent = p;
            filter.appendChild(opt);
        });
        if (currentVal && plates.includes(currentVal)) filter.value = currentVal;

        renderKPIs(summaryData);
        renderTable();
        document.getElementById('entry-count').textContent = filteredEntries.length;
    } catch (err) {
        showToast('error', `Failed to load data: ${err.message}`);
    }
}

function renderKPIs(summary) {
    document.getElementById('kpi-entries').textContent = summary.total_entries ?? allEntries.length;
    document.getElementById('kpi-avg').textContent = summary.fleet_avg_l_per_100km
        ? `${summary.fleet_avg_l_per_100km} L/100km` : '—';
    document.getElementById('kpi-anomalies').textContent = summary.total_anomalies ?? 0;

    const totalLiters = (summary.data || []).reduce((s, v) => s + (v.total_liters || 0), 0);
    document.getElementById('kpi-liters').textContent = totalLiters ? `${totalLiters.toLocaleString()} L` : '—';
}

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
    document.getElementById('entry-count').textContent = filteredEntries.length;

    tbody.innerHTML = filteredEntries.map(e => {
        const anomaly = e.is_anomaly;
        const anomalyBadge = anomaly
            ? '<span class="anomaly-badge">⚠ Spike</span>'
            : '<span style="color:#4ade80;font-size:11px;">✓ Normal</span>';

        const l100 = e.l_per_100km > 0 ? `${e.l_per_100km.toFixed(1)}` : '—';

        return `
        <tr class="${anomaly ? 'anomaly-row' : ''}">
            <td>${formatDate(e.log_date)}</td>
            <td>${escHtml(e.log_time || '—')}</td>
            <td>${escHtml(e.gas_store || '—')}</td>
            <td><span class="plate-badge">${escHtml(e.license_plate)}</span></td>
            <td><span class="fuel-value">${fmtNum(e.old_km)}</span></td>
            <td><span class="fuel-value">${fmtNum(e.new_km)}</span></td>
            <td><span class="fuel-value">${fmtNum(e.distance_km)}</span> <span class="fuel-muted">km</span></td>
            <td><span class="fuel-value">${e.liters.toFixed(1)}</span> <span class="fuel-muted">L</span></td>
            <td><span class="fuel-value">${l100}</span> ${l100 !== '—' ? '<span class="fuel-muted">L/100km</span>' : ''}</td>
            <td>${escHtml(e.driver_name || '—')}</td>
            <td>${anomalyBadge}</td>
            <td>
                <div style="display:flex; gap:6px;">
                    <button class="btn-action btn-edit"
                            onclick="openModal(${e.id})">✏️ Edit</button>
                    <button class="btn-action btn-delete"
                            onclick="deleteEntry(${e.id})">🗑</button>
                </div>
            </td>
        </tr>`;
    }).join('');
}

function formatDate(isoStr) {
    if (!isoStr) return '—';
    const parts = isoStr.split('-');
    if (parts.length !== 3) return isoStr;
    return `${parts[2]}/${parts[1]}/${parts[0]}`;
}

function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function fmtNum(n) {
    if (n == null || isNaN(n)) return '0';
    return Number(n).toLocaleString('en-US');
}

function sortTable(key) {
    if (sortKey === key) {
        sortDir *= -1;
    } else {
        sortKey = key;
        sortDir = 1;
    }

    document.querySelectorAll('.fe-table th').forEach(th => th.classList.remove('sorted'));
    const headers = document.querySelectorAll('.fe-table th');
    const keyOrder = ['log_date', 'log_time', 'gas_store', 'license_plate',
                      'old_km', 'new_km', 'distance_km', 'liters',
                      'l_per_100km', 'driver_name'];
    const idx = keyOrder.indexOf(key);
    if (idx >= 0 && headers[idx]) headers[idx].classList.add('sorted');

    filteredEntries.sort((a, b) => {
        let va = a[key], vb = b[key];
        if (typeof va === 'string') return va.localeCompare(vb) * sortDir;
        return ((va ?? 0) - (vb ?? 0)) * sortDir;
    });

    renderTable();
}

function applyVehicleFilter(plate) {
    filterTable(document.getElementById('table-search').value);
}

function filterTable(query) {
    const plate = document.getElementById('vehicle-filter').value;
    const q = query.trim().toLowerCase();

    filteredEntries = allEntries.filter(e => {
        if (plate && e.license_plate !== plate) return false;
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

    renderTable();
    document.getElementById('entry-count').textContent = filteredEntries.length;
}

function openModal(id = null) {
    editingId = id;
    const overlay = document.getElementById('modal-overlay');
    const title = document.getElementById('modal-title');
    const btnSave = document.getElementById('btn-save');

    if (id) {
        const e = allEntries.find(x => x.id === id);
        title.textContent = 'Edit Refuel Entry';
        btnSave.textContent = 'Save Changes';
        document.getElementById('field-plate').value = e ? e.license_plate : '';
        document.getElementById('field-plate').disabled = true;
        document.getElementById('field-date').value = e ? e.log_date : todayISO();
        document.getElementById('field-time').value = e ? e.log_time : '';
        document.getElementById('field-store').value = e ? (e.gas_store || '') : '';
        document.getElementById('field-old-km').value = e ? e.old_km : 0;
        document.getElementById('field-new-km').value = e ? e.new_km : 0;
        document.getElementById('field-liters').value = e ? e.liters : '';
        document.getElementById('field-driver').value = e ? (e.driver_name || '') : '';
        document.getElementById('field-price').value = e ? (e.unit_price || '') : '';
        document.getElementById('field-notes').value = e ? (e.notes || '') : '';
    } else {
        title.textContent = 'Add Refuel Entry';
        btnSave.textContent = 'Save Entry';
        document.getElementById('field-plate').value = '';
        document.getElementById('field-plate').disabled = false;
        document.getElementById('field-date').value = todayISO();
        const now = new Date();
        document.getElementById('field-time').value =
            String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0');
        document.getElementById('field-store').value = '';
        document.getElementById('field-old-km').value = '';
        document.getElementById('field-new-km').value = '';
        document.getElementById('field-liters').value = '';
        document.getElementById('field-driver').value = '';
        document.getElementById('field-price').value = '';
        document.getElementById('field-notes').value = '';
        setTimeout(() => document.getElementById('field-plate').focus(), 200);
    }

    overlay.classList.add('open');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('open');
    editingId = null;
}

function handleOverlayClick(e) {
    if (e.target === document.getElementById('modal-overlay')) closeModal();
}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
});

async function saveEntry() {
    const plate = document.getElementById('field-plate').value.trim().toUpperCase();
    const date = document.getElementById('field-date').value.trim();
    const time = document.getElementById('field-time').value.trim();
    const store = document.getElementById('field-store').value.trim();
    const oldKm = parseInt(document.getElementById('field-old-km').value, 10);
    const newKm = parseInt(document.getElementById('field-new-km').value, 10);
    const liters = parseFloat(document.getElementById('field-liters').value);
    const driver = document.getElementById('field-driver').value.trim();
    const price = document.getElementById('field-price').value.trim();
    const notes = document.getElementById('field-notes').value.trim();

    if (!plate) return showToast('warning', 'License plate is required.');
    if (!date) return showToast('warning', 'Date is required.');
    if (!time) return showToast('warning', 'Time is required.');
    if (isNaN(oldKm) || oldKm < 0) return showToast('warning', 'Valid Old KM is required.');
    if (isNaN(newKm) || newKm < 0) return showToast('warning', 'Valid New KM is required.');
    if (isNaN(liters) || liters <= 0) return showToast('warning', 'Liters must be > 0.');
    if (newKm < oldKm) return showToast('warning', 'New KM must be >= Old KM.');

    if (newKm - oldKm > 2000) {
        if (!confirm('Distance exceeds 2000 km — are you sure this is correct?')) return;
    }

    const payload = {
        license_plate: plate,
        log_date: date,
        log_time: time,
        gas_store: store,
        old_km: oldKm,
        new_km: newKm,
        liters: liters,
        driver_name: driver,
        notes: notes
    };
    if (price) payload.unit_price = parseFloat(price);

    const btn = document.getElementById('btn-save');
    btn.disabled = true;
    btn.innerHTML = '<span class="spin"></span> Saving…';

    try {
        if (editingId) {
            const result = await apiFetch(`/api/fuel-log/${editingId}`, {
                method: 'PUT',
                body: JSON.stringify(payload),
            });
            if (result.warnings && result.warnings.length) {
                result.warnings.forEach(w => showToast('warning', w, 6000));
            }
            showToast('success', 'Entry updated.');
        } else {
            const result = await apiFetch('/api/fuel-log', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
            if (result.warnings && result.warnings.length) {
                result.warnings.forEach(w => showToast('warning', w, 6000));
            }
            showToast('success', 'Entry created.');
        }
        closeModal();
        await loadEntries();
    } catch (err) {
        showToast('error', err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = editingId ? 'Save Changes' : 'Save Entry';
    }
}

async function deleteEntry(id) {
    const entry = allEntries.find(e => e.id === id);
    const label = entry ? `${entry.license_plate} on ${entry.log_date}` : `#${id}`;
    if (!confirm(`Delete refuel entry for ${label}?\n\nThis cannot be undone.`)) return;

    try {
        await apiFetch(`/api/fuel-log/${id}`, { method: 'DELETE' });
        showToast('success', 'Entry deleted.');
        await loadEntries();
    } catch (err) {
        showToast('error', err.message);
    }
}

// ── Vehicle Profiles (Normal L/100km) ──

async function loadProfiles() {
    try {
        const data = await apiFetch('/api/fuel-log/profiles');
        renderProfiles(data.data || []);
    } catch (err) {
        // silent — profiles are secondary
    }
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
        return `
        <tr>
            <td><span class="plate-badge">${escHtml(p.license_plate)}</span></td>
            <td>
                <span class="fuel-value" id="normal-display-${escHtml(p.license_plate)}">
                    ${normal > 0 ? normal.toFixed(1) : '—'} <span class="fuel-muted">L/100km</span>
                </span>
                <input type="number" step="0.1" min="1" max="99"
                       class="field-input" style="width:100px;display:none;padding:6px 10px;"
                       id="normal-input-${escHtml(p.license_plate)}" value="${normal > 0 ? normal : ''}"
                       placeholder="L/100km">
            </td>
            <td style="color:#94a3b8;font-size:12px;">${updated}</td>
            <td>
                <div style="display:flex;gap:6px;">
                    <button class="btn-action btn-edit" id="normal-edit-btn-${escHtml(p.license_plate)}"
                            onclick="editNormal('${escHtml(p.license_plate)}')">✏️ Edit</button>
                    <button class="btn-action btn-edit" id="normal-save-btn-${escHtml(p.license_plate)}"
                            style="display:none;background:rgba(16,185,129,0.15);color:#34d399;border:1px solid rgba(16,185,129,0.25);"
                            onclick="saveNormal('${escHtml(p.license_plate)}')">💾 Save</button>
                    <button class="btn-action btn-delete" id="normal-clear-btn-${escHtml(p.license_plate)}"
                            ${normal > 0 ? '' : 'style="display:none;"'}
                            onclick="clearNormal('${escHtml(p.license_plate)}')">🗑</button>
                </div>
            </td>
        </tr>`;
    }).join('');
}

function editNormal(plate) {
    const display = document.getElementById(`normal-display-${plate}`);
    const input = document.getElementById(`normal-input-${plate}`);
    const editBtn = document.getElementById(`normal-edit-btn-${plate}`);
    const saveBtn = document.getElementById(`normal-save-btn-${plate}`);
    if (display) display.style.display = 'none';
    if (input) { input.style.display = 'inline-block'; input.focus(); }
    if (editBtn) editBtn.style.display = 'none';
    if (saveBtn) saveBtn.style.display = 'inline-flex';
}

async function saveNormal(plate) {
    const input = document.getElementById(`normal-input-${plate}`);
    const val = parseFloat(input.value);
    if (isNaN(val) || val <= 0) return showToast('warning', 'Please enter a valid L/100km value > 0.');

    const btn = document.getElementById(`normal-save-btn-${plate}`);
    btn.disabled = true;
    btn.innerHTML = '<span class="spin"></span>';

    try {
        await apiFetch(`/api/fuel-log/profiles/${encodeURIComponent(plate)}`, {
            method: 'PUT',
            body: JSON.stringify({ normal_l_per_100km: val }),
        });
        showToast('success', `Normal L/100km for ${plate} set to ${val.toFixed(1)}.`);
        await loadProfiles();
        await loadEntries(); // refresh entries so anomaly flags update
    } catch (err) {
        showToast('error', err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '💾 Save';
    }
}

async function clearNormal(plate) {
    if (!confirm(`Clear the normal L/100km for ${plate}?\n\nAnomaly detection will fall back to the computed moving average.`)) return;

    try {
        await apiFetch(`/api/fuel-log/profiles/${encodeURIComponent(plate)}`, { method: 'DELETE' });
        showToast('success', `Normal L/100km for ${plate} cleared.`);
        await loadProfiles();
        await loadEntries();
    } catch (err) {
        showToast('error', err.message);
    }
}

function formatDateTime(isoStr) {
    if (!isoStr) return '—';
    try {
        const d = new Date(isoStr);
        const day = String(d.getDate()).padStart(2, '0');
        const mon = String(d.getMonth() + 1).padStart(2, '0');
        const y = d.getFullYear();
        const hh = String(d.getHours()).padStart(2, '0');
        const mm = String(d.getMinutes()).padStart(2, '0');
        return `${day}/${mon}/${y} ${hh}:${mm}`;
    } catch {
        return isoStr;
    }
}

function exportCsv() {
    const filter = document.getElementById('vehicle-filter').value;
    let url = '/api/fuel-log/export';
    if (filter) url += `?license_plate=${encodeURIComponent(filter)}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = 'fuel_efficiency_report.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
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

function todayISO() {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}