/**
 * vehicle-management.js
 * CRUD for the master vehicles table + dynamic vehicle types.
 */

let allVehicles = [];
let filteredVehicles = [];
let allTypes = [];
let editingId = null;

document.addEventListener('DOMContentLoaded', () => {
    loadVehicles();
    loadTypes();
});

async function apiFetch(url, opts = {}) {
    const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
    opts.headers = headers;
    const resp = await fetch(url, opts);
    const data = await resp.json();
    if (!data.success) throw new Error(data.message || 'Unknown error');
    return data;
}

// ── Vehicles ───────────────────────────────────────────────────
async function loadVehicles() {
    try {
        const data = await apiFetch('/api/fleet/vehicles');
        allVehicles = data.data || [];
        filteredVehicles = [...allVehicles];
        renderKPIs();
        renderTable();
    } catch (err) {
        showToast('error', `Failed to load: ${err.message}`);
    }
}

function renderKPIs() {
    const total = allVehicles.length;
    const types = new Set(allVehicles.filter(v => v.vehicle_type).map(v => v.vehicle_type)).size;
    const drivers = allVehicles.filter(v => v.current_driver).length;
    document.getElementById('kpi-count').textContent = total;
    document.getElementById('kpi-types').textContent = types;
    document.getElementById('kpi-drivers').textContent = drivers;
}

function renderTable() {
    const tbody = document.getElementById('table-body');
    const empty = document.getElementById('empty-state');
    document.getElementById('vehicle-count').textContent = filteredVehicles.length;

    if (!filteredVehicles.length) {
        tbody.innerHTML = '';
        empty.style.display = 'block';
        return;
    }
    empty.style.display = 'none';

    tbody.innerHTML = filteredVehicles.map(v => `
        <tr>
            <td><span class="plate-badge">${escHtml(v.plate_number)}</span></td>
            <td>${v.vehicle_type ? `<span class="type-badge">${escHtml(v.vehicle_type)}</span>` : '<span style="color:#94a3b8;">—</span>'}</td>
            <td>${v.current_driver ? escHtml(v.current_driver) : '<span style="color:#94a3b8;">—</span>'}</td>
            <td>
                <div style="display:flex;gap:6px;">
                    <button class="btn-action btn-edit" onclick="openModal('${escHtml(v.plate_number)}')">✏️ Edit</button>
                    <button class="btn-action btn-delete" onclick="deleteVehicle(${v.id}, '${escHtml(v.plate_number)}')">🗑</button>
                </div>
            </td>
        </tr>
    `).join('');
}

function filterTable(q) {
    const query = q.trim().toLowerCase();
    filteredVehicles = query
        ? allVehicles.filter(v => v.plate_number.toLowerCase().includes(query) || (v.current_driver || '').toLowerCase().includes(query))
        : [...allVehicles];
    renderTable();
}

// ── Vehicle Types ──────────────────────────────────────────────
async function loadTypes() {
    try {
        const data = await apiFetch('/api/fleet/vehicle-types');
        allTypes = data.data || [];
        populateTypeDropdown();
        renderTypesTable();
    } catch (_) {}
}

function populateTypeDropdown() {
    const sel = document.getElementById('field-type');
    sel.innerHTML = '<option value="">— Select type —</option>';
    allTypes.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.name;
        opt.textContent = t.name;
        sel.appendChild(opt);
    });
}

function renderTypesTable() {
    const tbody = document.getElementById('type-body');
    const empty = document.getElementById('type-empty');
    document.getElementById('type-count').textContent = allTypes.length;

    if (!allTypes.length) {
        tbody.innerHTML = '';
        empty.style.display = 'block';
        return;
    }
    empty.style.display = 'none';

    tbody.innerHTML = allTypes.map(t => `
        <tr>
            <td><span class="type-badge">${escHtml(t.name)}</span></td>
            <td>
                <button class="btn-action btn-delete" onclick="deleteVehicleType(${t.id}, '${escHtml(t.name)}')">🗑</button>
            </td>
        </tr>
    `).join('');
}

async function addVehicleType() {
    const input = document.getElementById('new-type-input');
    const name = input.value.trim();
    if (!name) return showToast('warning', 'Enter a type name.');
    try {
        await apiFetch('/api/fleet/vehicle-types', { method: 'POST', body: JSON.stringify({ name }) });
        input.value = '';
        showToast('success', `Type "${name}" added.`);
        await loadTypes();
    } catch (err) {
        showToast('error', err.message);
    }
}

async function deleteVehicleType(id, name) {
    if (!confirm(`Delete vehicle type "${name}"?\n\nVehicles using this type will retain it as text but it will no longer appear in the dropdown.`)) return;
    try {
        await apiFetch(`/api/fleet/vehicle-types/${id}`, { method: 'DELETE' });
        showToast('success', `Type "${name}" deleted.`);
        await loadTypes();
    } catch (err) {
        showToast('error', err.message);
    }
}

// ── Modal ──────────────────────────────────────────────────────
function openModal(plate = null) {
    editingId = null;
    const overlay = document.getElementById('modal-overlay');
    const title = document.getElementById('modal-title');
    const btnSave = document.getElementById('btn-save');

    if (plate) {
        const v = allVehicles.find(x => x.plate_number === plate);
        if (!v) return;
        editingId = v.id;
        title.textContent = 'Edit Vehicle';
        btnSave.textContent = 'Save Changes';
        document.getElementById('field-plate').value = v.plate_number;
        document.getElementById('field-plate').disabled = true;
        document.getElementById('field-type').value = v.vehicle_type || '';
        document.getElementById('field-driver').value = v.current_driver || '';
    } else {
        title.textContent = 'Add Vehicle';
        btnSave.textContent = 'Add Vehicle';
        document.getElementById('field-plate').value = '';
        document.getElementById('field-plate').disabled = false;
        document.getElementById('field-type').value = '';
        document.getElementById('field-driver').value = '';
        setTimeout(() => document.getElementById('field-plate').focus(), 200);
    }
    overlay.classList.add('open');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('open');
    editingId = null;
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

async function saveVehicle() {
    const plate = document.getElementById('field-plate').value.trim().toUpperCase();
    const vtype = document.getElementById('field-type').value.trim();
    const driver = document.getElementById('field-driver').value.trim();

    if (!plate) return showToast('warning', 'Plate number is required.');

    const payload = { plate_number: plate, vehicle_type: vtype, current_driver: driver };
    const btn = document.getElementById('btn-save');
    btn.disabled = true;
    btn.innerHTML = '<span class="spin"></span> Saving…';

    try {
        if (editingId) {
            await apiFetch(`/api/fleet/vehicles/${editingId}`, { method: 'PUT', body: JSON.stringify(payload) });
            showToast('success', 'Vehicle updated.');
        } else {
            await apiFetch('/api/fleet/vehicles', { method: 'POST', body: JSON.stringify(payload) });
            showToast('success', 'Vehicle added.');
        }
        closeModal();
        await loadVehicles();
    } catch (err) {
        showToast('error', err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = editingId ? 'Save Changes' : 'Add Vehicle';
    }
}

async function deleteVehicle(id, plate) {
    if (!confirm(`Delete vehicle ${plate}?\n\nFuel log entries referencing this vehicle will be unlinked but preserved.`)) return;
    try {
        await apiFetch(`/api/fleet/vehicles/${id}`, { method: 'DELETE' });
        showToast('success', `Vehicle ${plate} deleted.`);
        await loadVehicles();
    } catch (err) {
        showToast('error', err.message);
    }
}

// ── Toast ──────────────────────────────────────────────────────
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

function escHtml(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}