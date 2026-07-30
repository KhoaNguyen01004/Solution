// ================================================================
// Dispatch Dashboard — Main Orchestrator
// ================================================================
window.DASH = window.DASH || {};

(function () {
  'use strict';

  // ── State ──────────────────────────────────────────────────
  const state = {
    plans: [],
    allAssignments: [],  // unfiltered from API
    filteredAssignments: [],
    selectedAssignmentId: null,
    selectedStops: [],
    selectedAssignmentDetail: null,
    selectedEta: null,
    followMode: false,
    filters: {
      plan: '',
      date: '',
      vehicle: '',
      driver: '',
      status: '',
    },
  };

  DASH.state = state;

  // ── Filter logic ───────────────────────────────────────────
  function applyFilters() {
    const f = state.filters;
    state.filteredAssignments = state.allAssignments.filter((a) => {
      if (f.plan && a.plan_id !== parseInt(f.plan, 10) && a.plan_name !== f.plan) return false;
      if (f.date && a.plan_date !== f.date) return false;
      if (f.vehicle) {
        const q = f.vehicle.toLowerCase();
        const plate = (a.plate_number || '').toLowerCase();
        if (!plate.includes(q)) return false;
      }
      if (f.driver) {
        const q = f.driver.toLowerCase();
        const driver = (a.current_driver || '').toLowerCase();
        if (!driver.includes(q)) return false;
      }
      if (f.status && a.plan_status !== f.status) return false;
      return true;
    });

    // If selected assignment was filtered out, deselect
    if (state.selectedAssignmentId) {
      const stillExists = state.filteredAssignments.find(
        (a) => a.assignment_id === state.selectedAssignmentId
      );
      if (!stillExists) {
        state.selectedAssignmentId = null;
        state.selectedStops = [];
        state.selectedAssignmentDetail = null;
        state.selectedEta = null;
      }
    }
  }

  // ── Populate filters ───────────────────────────────────────
  function populateFilterPlans() {
    const sel = document.getElementById('filterPlan');
    const currentVal = sel.value;
    sel.innerHTML = '<option value="">All Plans</option>';
    const seen = new Set();
    state.plans.forEach((p) => {
      if (seen.has(p.id)) return;
      if (p.status !== 'confirmed' && p.status !== 'executing') return;
      seen.add(p.id);
      sel.innerHTML += `<option value="${p.id}">${escapeHtml(p.plan_name || 'Plan #' + p.id)}</option>`;
    });
    sel.value = currentVal;
  }

  // ── Bind filter events ─────────────────────────────────────
  function bindFilterEvents() {
    const filterIds = ['filterPlan', 'filterDate', 'filterVehicle', 'filterDriver', 'filterStatus'];
    filterIds.forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.addEventListener('input', () => {
        state.filters.plan = document.getElementById('filterPlan').value;
        state.filters.date = document.getElementById('filterDate').value;
        state.filters.vehicle = document.getElementById('filterVehicle').value.trim().toLowerCase();
        state.filters.driver = document.getElementById('filterDriver').value.trim().toLowerCase();
        state.filters.status = document.getElementById('filterStatus').value;
        applyFilters();
        renderAll();
      });
      el.addEventListener('change', () => {
        // Trigger same handler for select changes
        el.dispatchEvent(new Event('input'));
      });
    });
  }

  // ── Select assignment ──────────────────────────────────────
  function selectAssignment(assignmentId) {
    if (state.selectedAssignmentId === assignmentId) return;

    state.selectedAssignmentId = assignmentId;
    state.selectedStops = [];
    state.selectedAssignmentDetail = null;
    state.selectedEta = null;
    state.followMode = false;
    setFollowButtonState();

    renderAll();

    // Load detailed data for selected assignment
    loadAssignmentDetail(assignmentId);

    // Zoom map
    DASH.map.zoomToVehicle(assignmentId);
  }

  async function loadAssignmentDetail(assignmentId) {
    try {
      const [stops, progress, eta] = await Promise.all([
        DASH.api.stops(assignmentId),
        DASH.api.progress(assignmentId),
        DASH.api.eta(assignmentId),
      ]);

      // Merge execution status into stops
      state.selectedStops = stops || [];
      state.selectedAssignmentDetail = progress || null;
      state.selectedEta = eta || null;

      // Update timeline and map
      const currentStopId = getCurrentStopId(state.selectedStops);
      DASH.timeline.render(state.selectedStops, currentStopId, state.selectedEta);
      DASH.map.updateStops(state.selectedStops, currentStopId);
      DASH.map.updateRoute(state.selectedEta, state.selectedStops);

      // Update info bar
      updateInfoBar(assignmentId, state.selectedStops, state.selectedAssignmentDetail, state.selectedEta);

      // Show map controls
      document.getElementById('zoomToVehicleBtn').style.display = '';
      document.getElementById('followVehicleBtn').style.display = '';
      document.getElementById('openGmapsBtn').style.display = '';

      if (state.followMode) {
        DASH.map.followVehicle(assignmentId);
      }
    } catch (e) {
      console.error('Failed to load assignment detail:', e);
    }
  }

  // ── Follow-vehicle toggle ───────────────────────────────────
  function setFollowButtonState() {
    const btn = document.getElementById('followVehicleBtn');
    if (!btn) return;
    btn.classList.toggle('active', state.followMode);
    btn.textContent = state.followMode ? '◉ Following' : '◎ Follow';
  }

  function getCurrentStopId(stops) {
    if (!stops) return null;
    const activeStatuses = ['planned', 'arrived'];
    for (const s of stops) {
      if (activeStatuses.includes(s.execution_status)) {
        return s.id;
      }
    }
    return null;
  }

  // ── Update info bar ────────────────────────────────────────
  function updateInfoBar(assignmentId, stops, progress, eta) {
    const bar = document.getElementById('vehicleInfoBar');
    const a = state.allAssignments.find((x) => x.assignment_id === assignmentId);
    if (!a) { bar.style.display = 'none'; return; }

    bar.style.display = '';
    document.getElementById('vibarVehicle').textContent = a.plate_number || 'Vehicle';
    document.getElementById('vibarDriver').textContent = a.current_driver || 'No driver';
    const statusEl = document.getElementById('vibarStatus');
    statusEl.textContent = a.plan_status || 'unknown';
    statusEl.className = 'status-badge status-' + (a.plan_status || 'draft');

    const p = progress || { completed: 0, total: 0, progress_pct: 0 };
    document.getElementById('vibarProgress').textContent = `Progress: ${p.completed}/${p.total} (${p.progress_pct}%)`;

    const etaText = eta && eta.etas && eta.etas.length > 0
      ? 'ETA: ' + Math.round(eta.etas[0].eta_seconds / 60) + ' min'
      : 'ETA: --';
    document.getElementById('vibarEta').textContent = etaText;

    const distanceEl = document.getElementById('vibarDistance');
    if (eta && (eta.remaining_distance_km || eta.travelled_distance_km)) {
      distanceEl.textContent = `${eta.travelled_distance_km || 0} km done • ${eta.remaining_distance_km || 0} km left`;
    } else {
      distanceEl.textContent = '';
    }

    const gps = a.gps;

    // Supplementary operational context only — never used for ETA/routing.
    const speedEl = document.getElementById('vibarSpeed');
    speedEl.textContent = gps && gps.speed_kmh != null ? `${Math.round(gps.speed_kmh)} km/h` : '';

    const gpsTime = gps && gps.last_update ? new Date(gps.last_update).toLocaleTimeString() : '';
    document.getElementById('vibarGpsTime').textContent = gpsTime ? 'GPS: ' + gpsTime : '';
  }

  // ── Render all panels ──────────────────────────────────────
  function renderAll() {
    DASH.vehicleList.render(state.filteredAssignments, state.selectedAssignmentId);
    DASH.map.updateVehicles(state.filteredAssignments);

    if (state.selectedAssignmentId) {
      // If we already have stops loaded, re-render timeline
      if (state.selectedStops.length > 0) {
        const currentStopId = getCurrentStopId(state.selectedStops);
        DASH.timeline.render(state.selectedStops, currentStopId, state.selectedEta);
        DASH.map.updateStops(state.selectedStops, currentStopId);
        DASH.map.updateRoute(state.selectedEta, state.selectedStops);
        updateInfoBar(state.selectedAssignmentId, state.selectedStops, state.selectedAssignmentDetail, state.selectedEta);
      }
    } else {
      DASH.timeline.clear();
      document.getElementById('vehicleInfoBar').style.display = 'none';
      document.getElementById('zoomToVehicleBtn').style.display = 'none';
      document.getElementById('followVehicleBtn').style.display = 'none';
      document.getElementById('openGmapsBtn').style.display = 'none';
      state.followMode = false;
      setFollowButtonState();
      // Clear map extras
      DASH.map.updateStops([], null);
      DASH.map.updateRoute(null, []);
    }
  }

  // ── Main tick (called by polling) ──────────────────────────
  async function onPollTick() {
    const data = await DASH.api.dashboard();
    const raw = data.assignments || [];

    // Merge GPS into state
    state.allAssignments = raw;
    applyFilters();
    renderAll();

    // If a plan filter doesn't exist yet and we have data, refresh plan list periodically
    if (state.plans.length === 0 && raw.length > 0) {
      loadPlans();
    }

    // Reload selected assignment detail
    if (state.selectedAssignmentId) {
      const stillExists = state.allAssignments.find(
        (a) => a.assignment_id === state.selectedAssignmentId
      );
      if (stillExists) {
        await loadAssignmentDetail(state.selectedAssignmentId);
      }
    }
  }

  // ── Load plans for filter ──────────────────────────────────
  async function loadPlans() {
    try {
      state.plans = await DASH.api.plans();
      populateFilterPlans();
    } catch (e) {
      console.error('Failed to load plans:', e);
    }
  }

  // ── Bind map control buttons ───────────────────────────────
  function bindMapControls() {
    document.getElementById('refreshNowBtn').addEventListener('click', async () => {
      try {
        await DASH.state.refreshNow();
      } catch (e) {
        console.error('Refresh error:', e);
      }
    });

    document.getElementById('zoomToVehicleBtn').addEventListener('click', () => {
      if (state.selectedAssignmentId) {
        DASH.map.zoomToVehicle(state.selectedAssignmentId);
      }
    });

    document.getElementById('followVehicleBtn').addEventListener('click', () => {
      if (!state.selectedAssignmentId) return;
      state.followMode = !state.followMode;
      setFollowButtonState();
      if (state.followMode) {
        DASH.map.followVehicle(state.selectedAssignmentId);
      }
    });

    document.getElementById('openGmapsBtn').addEventListener('click', () => {
      if (state.selectedAssignmentId) {
        DASH.map.openGoogleMaps(state.selectedAssignmentId, state.selectedStops);
      }
    });

    document.getElementById('refreshGPSBtn').addEventListener('click', async () => {
      try {
        await DASH.state.refreshNow();
      } catch (e) {
        console.error('GPS refresh error:', e);
      }
    });
  }

  // ── Expose refresh for external use (timeline actions) ─────
  state.selectAssignment = selectAssignment;

  state.refreshNow = async function () {
    await DASH.polling.refreshNow(onPollTick);
  };

  // ── Init ──────────────────────────────────────────────────
  function init() {
    DASH.map.init();
    bindFilterEvents();
    bindMapControls();
    bindManagePlansEvents();
    setFollowButtonState();

    // Load initial data
    Promise.all([loadPlans()]).catch(() => {});

    // Start polling
    DASH.polling.start(onPollTick);

    // Invalidate map size after layout settles
    setTimeout(() => DASH.map.invalidateSize(), 500);

    // Timeline toggle (mobile)
    const toggleBtn = document.getElementById('timelineToggleBtn');
    const closeBtn = document.getElementById('timelineCloseBtn');
    const rightPanel = document.getElementById('rightPanel');
    if (toggleBtn && rightPanel) {
      toggleBtn.addEventListener('click', function () {
        rightPanel.classList.toggle('open');
      });
      if (closeBtn) {
        closeBtn.addEventListener('click', function () {
          rightPanel.classList.remove('open');
        });
      }
      // Close timeline when clicking on map
      document.getElementById('centerPanel').addEventListener('click', function () {
        if (rightPanel.classList.contains('open')) {
          rightPanel.classList.remove('open');
        }
      });
    }
  }

  // ── Plan Management (delete/clear) ──────────────────────────
  const managePlansState = {
    selectedIds: new Set(),
  };

  function toggleManagePlans(show) {
    const dd = document.getElementById('managePlansDropdown');
    if (!dd) return;
    dd.classList.toggle('open', show !== undefined ? show : !dd.classList.contains('open'));
    if (dd.classList.contains('open')) {
      populateManagePlansList();
    }
  }

  function populateManagePlansList() {
    const list = document.getElementById('managePlansList');
    if (!list) return;
    const plans = state.plans.length > 0 ? state.plans : [];
    if (plans.length === 0) {
      list.innerHTML = '<div class="manage-plans-empty">No plans found</div>';
      document.getElementById('deleteSelectedPlansBtn').disabled = true;
      return;
    }
    let html = '';
    plans.forEach((p) => {
      const checked = managePlansState.selectedIds.has(p.id) ? 'checked' : '';
      const statusClass = p.status || 'draft';
      html += `
        <label class="manage-plans-item">
          <input type="checkbox" value="${p.id}" ${checked}>
          <span class="plan-item-name">${escapeHtml(p.plan_name || 'Plan #' + p.id)}</span>
          <span class="plan-item-date">${escapeHtml(p.plan_date || '')}</span>
          <span class="plan-item-status ${statusClass}">${statusClass}</span>
        </label>
      `;
    });
    list.innerHTML = html;

    // Bind checkbox changes
    list.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
      cb.addEventListener('change', () => {
        const id = parseInt(cb.value, 10);
        if (cb.checked) {
          managePlansState.selectedIds.add(id);
        } else {
          managePlansState.selectedIds.delete(id);
        }
        const btn = document.getElementById('deleteSelectedPlansBtn');
        if (btn) btn.disabled = managePlansState.selectedIds.size === 0;
      });
    });
  }

  async function deleteSelectedPlans() {
    const ids = Array.from(managePlansState.selectedIds);
    if (ids.length === 0) return;
    if (!confirm(`Are you sure you want to delete ${ids.length} selected plan(s)? This cannot be undone.`)) return;
    try {
      await DASH.api.deletePlans(ids);
      UI.toast(`Deleted ${ids.length} plan(s)`, 'success');
      managePlansState.selectedIds = new Set();
      toggleManagePlans(false);
      // Reload plans and data
      await loadPlans();
      await DASH.state.refreshNow();
    } catch (e) {
      UI.toast(`Delete failed: ${e.message}`, 'error');
    }
  }

  async function clearAllPlans() {
    if (!confirm('Are you sure you want to delete ALL plans? This cannot be undone.')) return;
    try {
      await DASH.api.clearPlans();
      UI.toast('All plans cleared', 'success');
      managePlansState.selectedIds = new Set();
      toggleManagePlans(false);
      // Reload plans and data
      await loadPlans();
      await DASH.state.refreshNow();
    } catch (e) {
      UI.toast(`Clear failed: ${e.message}`, 'error');
    }
  }

  function bindManagePlansEvents() {
    const btn = document.getElementById('managePlansBtn');
    const close = document.getElementById('managePlansClose');
    const deleteBtn = document.getElementById('deleteSelectedPlansBtn');
    const clearBtn = document.getElementById('clearAllPlansBtn');

    if (btn) btn.addEventListener('click', (e) => { e.stopPropagation(); toggleManagePlans(); });
    if (close) close.addEventListener('click', () => toggleManagePlans(false));
    if (deleteBtn) deleteBtn.addEventListener('click', deleteSelectedPlans);
    if (clearBtn) clearBtn.addEventListener('click', clearAllPlans);

    // Close on outside click
    document.addEventListener('click', (e) => {
      const wrap = document.querySelector('.manage-plans-wrap');
      if (wrap && !wrap.contains(e.target)) {
        toggleManagePlans(false);
      }
    });
  }

  // ── Utility ────────────────────────────────────────────────
  function escapeHtml(str) {
    if (str == null) return '';
    const d = document.createElement('div');
    d.appendChild(document.createTextNode(String(str)));
    return d.innerHTML;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
