// ================================================================
// Dispatch Dashboard — Vehicle List (Left Panel)
// ================================================================
window.DASH = window.DASH || {};

(function () {
  'use strict';

  // Attention proxies — no scheduled/promised time exists in the schema, so
  // "delay" is approximated from data already available every poll: a
  // vehicle arrived at a stop far longer than a normal stop takes, or a
  // vehicle whose GPS has gone quiet. Both are purely derived, no backend
  // change needed.
  const STUCK_THRESHOLD_MS = 20 * 60 * 1000;
  const GPS_STALE_THRESHOLD_MS = 15 * 60 * 1000;
  // Corroborating signal only (never a hard alert): live TTAS speed reads
  // ~0 while the vehicle isn't parked at a stop. A single reading can just
  // be a red light, so this stays informational, same as the other proxies.
  const REPORTED_STOPPED_SPEED_KMH = 2;

  function statusClass(status) {
    const map = {
      draft: 'status-draft',
      confirmed: 'status-confirmed',
      executing: 'status-executing',
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

  function setText(el, text) {
    if (el && el.textContent !== text) el.textContent = text;
  }

  function computeAttention(a) {
    const reasons = [];
    const cs = a.current_stop;
    if (cs && cs.execution_status === 'arrived' && cs.actual_arrival_at) {
      const arrivedAt = new Date(cs.actual_arrival_at).getTime();
      if (!isNaN(arrivedAt) && (Date.now() - arrivedAt) > STUCK_THRESHOLD_MS) {
        reasons.push('stuck');
      }
    }
    const gps = a.gps;
    let gpsIsFresh = false;
    if (gps && gps.last_update) {
      const lastUpdate = new Date(gps.last_update).getTime();
      if (!isNaN(lastUpdate)) {
        gpsIsFresh = (Date.now() - lastUpdate) <= GPS_STALE_THRESHOLD_MS;
        if (!gpsIsFresh) reasons.push('gps_stale');
      }
    }
    if (gpsIsFresh && gps.speed_kmh != null && gps.speed_kmh <= REPORTED_STOPPED_SPEED_KMH
        && (!cs || cs.execution_status !== 'arrived')) {
      reasons.push('reported_stopped');
    }
    return reasons;
  }

  function attentionReasonText(reason, a) {
    if (reason === 'stuck') {
      const mins = Math.floor((Date.now() - new Date(a.current_stop.actual_arrival_at).getTime()) / 60000);
      return `Stuck ${mins}m at stop`;
    }
    if (reason === 'gps_stale') {
      const mins = Math.floor((Date.now() - new Date(a.gps.last_update).getTime()) / 60000);
      return `GPS stale ${mins}m`;
    }
    if (reason === 'reported_stopped') {
      return `Reporting ${Math.round(a.gps.speed_kmh)} km/h, not at a stop`;
    }
    return reason;
  }

  function createCard(assignmentId) {
    const card = document.createElement('div');
    card.className = 'vehicle-card';
    card.dataset.assignmentId = assignmentId;
    card.innerHTML = `
      <div class="vc-header">
        <div>
          <div class="vc-vehicle-row">
            <span class="vc-attention-dot" style="display:none;"></span>
            <span class="vc-vehicle"></span>
          </div>
          <div class="vc-driver"></div>
        </div>
        <span class="status-badge"></span>
      </div>
      <div class="vc-body">
        <div class="vc-current-stop"></div>
        <div class="vc-progress">
          <div class="vc-progress-bar">
            <div class="vc-progress-fill"></div>
          </div>
          <span class="vc-progress-text"></span>
        </div>
        <div class="vc-meta">
          <span class="vc-plan-name"></span>
          <span class="vc-gps-time"></span>
        </div>
      </div>`;
    card.addEventListener('click', () => {
      const id = parseInt(card.dataset.assignmentId, 10);
      DASH.state.selectAssignment(id);
    });
    return card;
  }

  DASH.vehicleList = {
    _cardNodes: new Map(), // assignment_id → card element
    _lastAssignments: [],
    _lastSelectedId: null,
    _toggleBound: false,

    // Diffs against previously-rendered cards instead of rebuilding
    // innerHTML every poll — preserves scroll position, hover state, and
    // avoids rebinding a click listener per card every 12s.
    render(assignments, selectedId) {
      this._lastAssignments = assignments || [];
      this._lastSelectedId = selectedId;
      this._bindAttentionToggle();

      const container = document.getElementById('vehicleList');
      const countEl = document.getElementById('vehicleCount');
      let list = this._lastAssignments;

      if (list.length === 0) {
        container.innerHTML = '<div class="empty-state">No vehicles found</div>';
        if (countEl) countEl.textContent = '';
        this._cardNodes.clear();
        this._renderAttentionStrip([]);
        return;
      }

      if (countEl) countEl.textContent = list.length;

      const attentionByAssignment = new Map();
      list.forEach((a) => attentionByAssignment.set(a.assignment_id, computeAttention(a)));

      const toggle = document.getElementById('attentionFirstToggle');
      if (toggle && toggle.checked) {
        list = list.slice().sort((a, b) => {
          const diff = attentionByAssignment.get(b.assignment_id).length - attentionByAssignment.get(a.assignment_id).length;
          return diff;
        });
      }

      this._renderAttentionStrip(list.filter((a) => attentionByAssignment.get(a.assignment_id).length > 0));

      if (this._cardNodes.size === 0 && container.querySelector('.empty-state')) {
        container.innerHTML = '';
      }

      const seen = new Set();
      const orderedNodes = [];

      list.forEach((a) => {
        seen.add(a.assignment_id);
        let card = this._cardNodes.get(a.assignment_id);
        if (!card) {
          card = createCard(a.assignment_id);
          this._cardNodes.set(a.assignment_id, card);
        }
        this._patchCard(card, a, a.assignment_id === selectedId, attentionByAssignment.get(a.assignment_id));
        orderedNodes.push(card);
      });

      this._cardNodes.forEach((card, id) => {
        if (!seen.has(id)) {
          card.remove();
          this._cardNodes.delete(id);
        }
      });

      let ref = container.firstChild;
      orderedNodes.forEach((card) => {
        if (card !== ref) {
          container.insertBefore(card, ref);
        } else {
          ref = ref.nextSibling;
        }
      });
    },

    _bindAttentionToggle() {
      if (this._toggleBound) return;
      const toggle = document.getElementById('attentionFirstToggle');
      if (!toggle) return;
      this._toggleBound = true;
      toggle.addEventListener('change', () => {
        this.render(this._lastAssignments, this._lastSelectedId);
      });
    },

    _renderAttentionStrip(flagged) {
      const strip = document.getElementById('attentionStrip');
      if (!strip) return;

      if (flagged.length === 0) {
        strip.style.display = 'none';
        strip.innerHTML = '';
        return;
      }

      strip.style.display = '';
      strip.innerHTML = flagged.map((a) => {
        const reasons = computeAttention(a);
        const label = reasons.map((r) => attentionReasonText(r, a)).join(' · ');
        const plate = UI.escapeHtml(a.plate_number || 'Vehicle #' + a.assignment_id);
        return `<div class="attention-chip" data-assignment-id="${a.assignment_id}" title="${UI.escapeHtml(label)}">
          <span class="attention-chip-plate">${plate}</span>
          <span class="attention-chip-reason">${UI.escapeHtml(label)}</span>
        </div>`;
      }).join('');

      strip.querySelectorAll('.attention-chip').forEach((chip) => {
        chip.addEventListener('click', () => {
          DASH.state.selectAssignment(parseInt(chip.dataset.assignmentId, 10));
        });
      });
    },

    _patchCard(card, a, isSelected, attentionReasons) {
      card.classList.toggle('selected', !!isSelected);

      const progress = a.progress || { completed: 0, total: 0, progress_pct: 0 };
      const status = a.plan_status || 'confirmed';
      const gps = a.gps || {};
      const gpsTime = gps.last_update ? this._formatTime(gps.last_update) : '';
      const stopName = a.current_stop ? a.current_stop.station_name || a.current_stop.station_code || 'Stop #' + a.current_stop.planned_sequence : 'No active stop';

      setText(card.querySelector('.vc-vehicle'), a.plate_number || 'Vehicle #' + a.assignment_id);
      setText(card.querySelector('.vc-driver'), a.current_driver || 'No driver');

      const dot = card.querySelector('.vc-attention-dot');
      const hasAttention = attentionReasons && attentionReasons.length > 0;
      dot.style.display = hasAttention ? '' : 'none';
      if (hasAttention) {
        dot.title = attentionReasons.map((r) => attentionReasonText(r, a)).join(' · ');
      }

      const badge = card.querySelector('.status-badge');
      const badgeClass = 'status-badge ' + statusClass(status);
      if (badge.className !== badgeClass) badge.className = badgeClass;
      setText(badge, statusLabel(status));

      const stopEl = card.querySelector('.vc-current-stop');
      setText(stopEl, stopName);
      if (stopEl.title !== stopName) stopEl.title = stopName;

      const fill = card.querySelector('.vc-progress-fill');
      const fillClass = 'vc-progress-fill ' + statusClass(status);
      if (fill.className !== fillClass) fill.className = fillClass;
      const width = (progress.progress_pct || 0) + '%';
      if (fill.style.width !== width) fill.style.width = width;

      setText(card.querySelector('.vc-progress-text'), `${progress.completed || 0}/${progress.total || 0}`);
      setText(card.querySelector('.vc-plan-name'), a.plan_name || '');
      setText(card.querySelector('.vc-gps-time'), gpsTime ? 'GPS: ' + gpsTime : '');
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
