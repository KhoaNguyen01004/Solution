// ================================================================
// Dispatch Dashboard — Timeline Module (Right Panel)
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
    return map[status] || 'status-planned';
  }

  function statusLabel(status) {
    return (status || 'planned').replace('_', ' ');
  }

  function formatTime(dateStr) {
    if (!dateStr) return '--';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return dateStr;
    }
  }

  function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      return d.toLocaleDateString([], { day: '2-digit', month: '2-digit' });
    } catch {
      return dateStr;
    }
  }

  DASH.timeline = {
    render(stops, currentStopId, etas) {
      const container = document.getElementById('timeline');
      const countEl = document.getElementById('stopCount');

      if (!stops || stops.length === 0) {
        container.innerHTML = '<div class="empty-state">Select a vehicle to view stops</div>';
        if (countEl) countEl.textContent = '';
        return;
      }

      if (countEl) countEl.textContent = stops.length;

      const etaMap = {};
      if (etas && etas.etas) {
        etas.etas.forEach((e) => {
          if (e.stop_id) etaMap[e.stop_id] = e.eta_seconds || e.eta || '--';
        });
      }

      let html = '';
      stops.forEach((s) => {
        const execStatus = s.execution_status || 'planned';
        const isCurrent = currentStopId && s.id === currentStopId;
        const isCompleted = ['completed', 'skipped', 'cancelled'].includes(execStatus);
        const cssClass = isCurrent ? 'timeline-item current' : isCompleted ? 'timeline-item completed' : 'timeline-item';
        const collapsed = isCompleted ? '' : 'open';
        const eta = etaMap[s.id];

        html += `
          <div class="${cssClass}" data-stop-id="${s.id}">
            <div class="timeline-header" data-toggle="${s.id}">
              <span class="timeline-seq">${s.planned_sequence || '?'}</span>
              <span class="timeline-station">${escapeHtml(s.station_name || s.station_code || 'Stop')}</span>
              <span class="status-badge ${statusClass(execStatus)}">${statusLabel(execStatus)}</span>
              <span class="timeline-chevron ${collapsed}" data-chevron="${s.id}">&#9660;</span>
            </div>
            <div class="timeline-body ${collapsed}" data-body="${s.id}">
              <div class="timeline-detail">
                ${s.station_code ? '<span class="label">Code:</span><span class="value">' + escapeHtml(s.station_code) + '</span>' : ''}
                <span class="label">Status:</span><span class="value">${statusLabel(execStatus)}</span>
                ${s.address ? '<span class="label">Address:</span><span class="value">' + escapeHtml(s.address) + '</span>' : ''}
                ${s.lat && s.lng ? '<span class="label">Coords:</span><span class="value">' + parseFloat(s.lat).toFixed(5) + ', ' + parseFloat(s.lng).toFixed(5) + '</span>' : ''}
                ${s.manager_name ? '<span class="label">Manager:</span><span class="value">' + escapeHtml(s.manager_name) + '</span>' : ''}
                ${s.manager_phone ? '<span class="label">Phone:</span><span class="value">' + escapeHtml(s.manager_phone) + '</span>' : ''}
                ${s.product_description ? '<span class="label">Product:</span><span class="value">' + escapeHtml(s.product_description) + '</span>' : ''}
                <span class="label">Arrival:</span><span class="value">${formatTime(s.actual_arrival_at)}</span>
                <span class="label">Departure:</span><span class="value">${formatTime(s.actual_departure_at)}</span>
                ${eta ? '<span class="label">ETA:</span><span class="value">' + (typeof eta === 'number' ? Math.round(eta / 60) + ' min' : escapeHtml(String(eta))) + '</span>' : ''}
                ${s.note ? '<span class="label">Notes:</span><span class="value" style="font-style:italic;">' + escapeHtml(s.note) + '</span>' : ''}
                ${s.skip_reason ? '<span class="label">Skip reason:</span><span class="value">' + escapeHtml(s.skip_reason) + '</span>' : ''}
                ${s.cancel_reason ? '<span class="label">Cancel reason:</span><span class="value">' + escapeHtml(s.cancel_reason) + '</span>' : ''}
              </div>
              <div class="timeline-actions">
                ${['planned', 'enroute', 'arrived'].includes(execStatus) ? `<button class="btn-nav" data-action="advance" data-stop-id="${s.id}">Advance</button>` : ''}
                ${['planned', 'enroute', 'arrived'].includes(execStatus) ? `<button class="btn-nav" data-action="skip" data-stop-id="${s.id}">Skip</button>` : ''}
                ${['planned', 'enroute', 'arrived'].includes(execStatus) ? `<button class="btn-danger" data-action="cancel" data-stop-id="${s.id}">Cancel</button>` : ''}
              </div>
            </div>
          </div>`;
      });
      container.innerHTML = html;

      // Toggle collapse
      container.querySelectorAll('.timeline-header[data-toggle]').forEach((header) => {
        header.addEventListener('click', () => {
          const id = header.dataset.toggle;
          const body = container.querySelector(`[data-body="${id}"]`);
          const chevron = container.querySelector(`[data-chevron="${id}"]`);
          if (body && chevron) {
            body.classList.toggle('open');
            chevron.classList.toggle('open');
          }
        });
      });

      // Action handlers
      container.querySelectorAll('[data-action="advance"]').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();
          const stopId = parseInt(btn.dataset.stopId, 10);
          try {
            await DASH.api.advance(stopId);
            DASH.state.refreshNow();
          } catch (err) {
            alert('Advance failed: ' + err.message);
          }
        });
      });

      container.querySelectorAll('[data-action="skip"]').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();
          const stopId = parseInt(btn.dataset.stopId, 10);
          const reason = prompt('Skip reason (optional):');
          try {
            await DASH.api.skip(stopId, reason || '');
            DASH.state.refreshNow();
          } catch (err) {
            alert('Skip failed: ' + err.message);
          }
        });
      });

      container.querySelectorAll('[data-action="cancel"]').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
          e.stopPropagation();
          const stopId = parseInt(btn.dataset.stopId, 10);
          const reason = prompt('Cancel reason:');
          if (!reason) return;
          try {
            await DASH.api.cancel(stopId, reason);
            DASH.state.refreshNow();
          } catch (err) {
            alert('Cancel failed: ' + err.message);
          }
        });
      });
    },
  };
})();
