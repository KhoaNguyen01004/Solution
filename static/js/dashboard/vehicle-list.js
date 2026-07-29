// ================================================================
// Dispatch Dashboard — Vehicle List (Left Panel)
// ================================================================
window.DASH = window.DASH || {};

(function () {
  'use strict';

  function escapeHtml(str) {
    if (str == null) return '';
    const d = document.createElement('div');
    d.appendChild(document.createTextNode(String(str)));
    return d.innerHTML;
  }

  function statusClass(status) {
    const map = {
      draft: 'status-draft',
      confirmed: 'status-confirmed',
      executing: 'status-executing',
      enroute: 'status-enroute',
      arrived: 'status-arrived',
      completed: 'status-completed',
      skipped: 'status-skipped',
      cancelled: 'status-cancelled',
      planned: 'status-planned',
    };
    return map[status] || 'status-draft';
  }

  function statusLabel(status) {
    return (status || 'unknown').replace('_', ' ');
  }

  DASH.vehicleList = {
    render(assignments, selectedId) {
      const container = document.getElementById('vehicleList');
      const countEl = document.getElementById('vehicleCount');

      if (!assignments || assignments.length === 0) {
        container.innerHTML = '<div class="empty-state">No vehicles found</div>';
        if (countEl) countEl.textContent = '';
        return;
      }

      if (countEl) countEl.textContent = assignments.length;

      let html = '';
      assignments.forEach((a) => {
        const sel = a.assignment_id === selectedId ? ' selected' : '';
        const progress = a.progress || { completed: 0, total: 0, progress_pct: 0 };
        const status = a.plan_status || 'confirmed';
        const gps = a.gps || {};
        const gpsTime = gps.last_update ? this._formatTime(gps.last_update) : '';
        const stopName = a.current_stop ? a.current_stop.station_name || a.current_stop.station_code || 'Stop #' + a.current_stop.planned_sequence : 'No active stop';

        html += `
          <div class="vehicle-card${sel}" data-assignment-id="${a.assignment_id}">
            <div class="vc-header">
              <div>
                <div class="vc-vehicle">${escapeHtml(a.plate_number || 'Vehicle #' + a.assignment_id)}</div>
                <div class="vc-driver">${escapeHtml(a.current_driver || 'No driver')}</div>
              </div>
              <span class="status-badge ${statusClass(status)}">${statusLabel(status)}</span>
            </div>
            <div class="vc-body">
              <div class="vc-current-stop" title="${escapeHtml(stopName)}">${escapeHtml(stopName)}</div>
              <div class="vc-progress">
                <div class="vc-progress-bar">
                  <div class="vc-progress-fill ${statusClass(status)}" style="width:${progress.progress_pct || 0}%"></div>
                </div>
                <span class="vc-progress-text">${progress.completed || 0}/${progress.total || 0}</span>
              </div>
              <div class="vc-meta">
                <span>${escapeHtml(a.plan_name || '')}</span>
                <span>${gpsTime ? 'GPS: ' + gpsTime : ''}</span>
              </div>
            </div>
          </div>`;
      });
      container.innerHTML = html;

      // Click handler
      container.querySelectorAll('.vehicle-card').forEach((card) => {
        card.addEventListener('click', () => {
          const id = parseInt(card.dataset.assignmentId, 10);
          DASH.state.selectAssignment(id);
        });
      });
    },

    _formatTime(dateStr) {
      if (!dateStr) return '';
      try {
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        const now = new Date();
        const diff = Math.floor((now - d) / 1000);
        if (diff < 60) return 'now';
        if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
        if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
        return d.toLocaleDateString();
      } catch {
        return dateStr;
      }
    },
  };
})();
