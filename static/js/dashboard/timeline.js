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

  function setText(el, text) {
    if (el && el.textContent !== text) el.textContent = text;
  }

  const ACTIONABLE = ['planned', 'arrived'];

  // ── Actions + inline reason row — shared markup/behavior between each
  // per-stop timeline body and the pinned current-stop card, so both get
  // the same Advance/Skip/Cancel handling from one place. Skip/Cancel no
  // longer use prompt()/alert(): clicking either swaps the buttons for an
  // inline input, confirmed with Enter or a Confirm button, with errors
  // reported via UI.toast() instead of a blocking alert().
  function buildActionsHtml(stopId, execStatus) {
    if (!ACTIONABLE.includes(execStatus)) return '';
    return `
              <div class="timeline-actions" data-actions-for="${stopId}">
                <button class="btn-nav" data-action="advance" data-stop-id="${stopId}">Advance</button>
                <button class="btn-nav" data-action="skip" data-stop-id="${stopId}">Skip</button>
                <button class="btn-danger" data-action="cancel" data-stop-id="${stopId}">Cancel</button>
              </div>
              <div class="timeline-reason-row" data-reason-for="${stopId}" style="display:none;">
                <input type="text" class="timeline-reason-input" data-reason-input>
                <button class="btn-nav" data-reason-confirm="${stopId}">Confirm</button>
                <button class="btn-nav" data-reason-cancel="${stopId}">&times;</button>
              </div>`;
  }

  // Stop ids with an open (mid-edit) reason row — content patching for
  // these is suppressed until the row closes, since a background poll is
  // non-blocking now (unlike the old prompt()) and would otherwise wipe
  // out whatever the dispatcher is typing.
  const openReasonStopIds = new Set();

  function showReasonRow(container, stopId, action) {
    const actionsRow = container.querySelector(`[data-actions-for="${stopId}"]`);
    const reasonRow = container.querySelector(`[data-reason-for="${stopId}"]`);
    if (!actionsRow || !reasonRow) return;
    openReasonStopIds.add(String(stopId));
    reasonRow.dataset.pendingAction = action;
    const input = reasonRow.querySelector('[data-reason-input]');
    input.placeholder = action === 'cancel' ? 'Reason (required)' : 'Reason (optional)';
    input.value = '';
    actionsRow.style.display = 'none';
    reasonRow.style.display = '';
    input.focus();
  }

  function hideReasonRow(container, stopId) {
    openReasonStopIds.delete(String(stopId));
    const actionsRow = container.querySelector(`[data-actions-for="${stopId}"]`);
    const reasonRow = container.querySelector(`[data-reason-for="${stopId}"]`);
    if (!actionsRow || !reasonRow) return;
    reasonRow.style.display = 'none';
    actionsRow.style.display = '';
  }

  function confirmReason(container, stopId) {
    const reasonRow = container.querySelector(`[data-reason-for="${stopId}"]`);
    if (!reasonRow) return;
    const action = reasonRow.dataset.pendingAction;
    const input = reasonRow.querySelector('[data-reason-input]');
    const reason = input.value.trim();

    if (action === 'cancel' && !reason) {
      UI.toast('A reason is required to cancel a stop', 'error');
      input.focus();
      return;
    }

    hideReasonRow(container, stopId);
    handleStopAction(parseInt(stopId, 10), action, reason);
  }

  function handleStopAction(stopId, action, reason) {
    let promise;
    if (action === 'advance') {
      promise = DASH.api.advance(stopId);
    } else if (action === 'skip') {
      promise = DASH.api.skip(stopId, reason || '');
    } else if (action === 'cancel') {
      promise = DASH.api.cancel(stopId, reason);
    } else {
      return;
    }

    promise
      .then(() => DASH.state.refreshNow())
      .catch((err) => UI.toast(`${action.charAt(0).toUpperCase()}${action.slice(1)} failed: ${err.message}`, 'error'));
  }

  // Bound once per container (a stop's body, or the pinned current-stop
  // card) — regenerating the actions/reason markup inside never requires
  // rebinding, since delegation reads data-* attributes at click time.
  function bindActionDelegation(container) {
    container.addEventListener('click', (e) => {
      const actionBtn = e.target.closest('[data-action]');
      if (actionBtn) {
        e.stopPropagation();
        const stopId = parseInt(actionBtn.dataset.stopId, 10);
        const action = actionBtn.dataset.action;
        if (action === 'advance') {
          handleStopAction(stopId, 'advance');
        } else {
          showReasonRow(container, actionBtn.dataset.stopId, action);
        }
        return;
      }
      const confirmBtn = e.target.closest('[data-reason-confirm]');
      if (confirmBtn) {
        e.stopPropagation();
        confirmReason(container, confirmBtn.dataset.reasonConfirm);
        return;
      }
      const cancelBtn = e.target.closest('[data-reason-cancel]');
      if (cancelBtn) {
        e.stopPropagation();
        hideReasonRow(container, cancelBtn.dataset.reasonCancel);
      }
    });

    container.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      const row = e.target.closest('.timeline-reason-row');
      if (!row) return;
      e.stopPropagation();
      confirmReason(container, row.dataset.reasonFor);
    });
  }

  // ── Lazy, read-only photo gallery — fetched only when a stop's "Photos"
  // toggle is opened, and only once (cached in closure). Lives in its own
  // DOM node outside the diffed detail content so opening it survives
  // every poll's body-content patch (Phase 3's "preserve UI state").
  function bindPhotosToggle(bodyEl, stopId) {
    const toggleBtn = bodyEl.querySelector(`[data-photos-toggle="${stopId}"]`);
    const photosEl = bodyEl.querySelector(`[data-photos-for="${stopId}"]`);
    if (!toggleBtn || !photosEl) return;

    let loaded = false;
    let loading = false;
    toggleBtn.addEventListener('click', async () => {
      const opening = photosEl.style.display === 'none';
      photosEl.style.display = opening ? '' : 'none';
      if (!opening || loaded || loading) return;

      loading = true;
      photosEl.innerHTML = '<span class="timeline-photos-status">Loading photos…</span>';
      try {
        const images = await DASH.api.stopImages(stopId);
        loaded = true;
        if (!images || images.length === 0) {
          photosEl.innerHTML = '<span class="timeline-photos-status">No photos for this stop</span>';
          return;
        }
        photosEl.innerHTML = images.map((img) => `
          <a href="/api/images/${img.id}/file" target="_blank" rel="noopener" class="timeline-photo-thumb" title="${escapeHtml(img.category || '')}">
            <img src="/api/images/${img.id}/file" alt="${escapeHtml(img.category || 'photo')}" loading="lazy">
          </a>`).join('');
      } catch (err) {
        photosEl.innerHTML = `<span class="timeline-photos-status">Failed to load photos: ${escapeHtml(err.message)}</span>`;
      } finally {
        loading = false;
      }
    });
  }

  function buildDetailHtml(s, execStatus, eta) {
    return `
              <div class="timeline-detail">
                ${s.station_code ? '<span class="label">Code:</span><span class="value">' + escapeHtml(s.station_code) + '</span>' : ''}
                <span class="label">Status:</span><span class="value">${statusLabel(execStatus)}</span>
                ${s.address ? '<span class="label">Address:</span><span class="value">' + escapeHtml(s.address) + '</span>' : ''}
                ${s.lat && s.lng ? '<span class="label">Coords:</span><span class="value">' + parseFloat(s.lat).toFixed(5) + ', ' + parseFloat(s.lng).toFixed(5) + '</span>' : ''}
                ${s.manager_name ? '<span class="label">Manager:</span><span class="value">' + escapeHtml(s.manager_name) + '</span>' : ''}
                ${s.manager_phone ? '<span class="label">Phone:</span><span class="value"><a class="tel-link" href="tel:' + escapeHtml(s.manager_phone.replace(/[^0-9+]/g, '')) + '">' + escapeHtml(s.manager_phone) + '</a></span>' : ''}
                ${s.product_description ? '<span class="label">Product:</span><span class="value">' + escapeHtml(s.product_description) + '</span>' : ''}
                <span class="label">Arrival:</span><span class="value">${formatTime(s.actual_arrival_at)}</span>
                <span class="label">Departure:</span><span class="value">${formatTime(s.actual_departure_at)}</span>
                ${eta ? '<span class="label">ETA:</span><span class="value">' + (typeof eta === 'number' ? Math.round(eta / 60) + ' min' : escapeHtml(String(eta))) + '</span>' : ''}
                ${s.note ? '<span class="label">Notes:</span><span class="value" style="font-style:italic;">' + escapeHtml(s.note) + '</span>' : ''}
                ${s.skip_reason ? '<span class="label">Skip reason:</span><span class="value">' + escapeHtml(s.skip_reason) + '</span>' : ''}
                ${s.cancel_reason ? '<span class="label">Cancel reason:</span><span class="value">' + escapeHtml(s.cancel_reason) + '</span>' : ''}
              </div>
              ${buildActionsHtml(s.id, execStatus)}`;
  }

  function createStop(s) {
    const execStatus = s.execution_status || 'planned';
    const isCompleted = ['completed', 'skipped', 'cancelled'].includes(execStatus);

    const el = document.createElement('div');
    el.className = 'timeline-item';
    el.dataset.stopId = s.id;
    el.innerHTML = `
          <div class="timeline-header" data-toggle="${s.id}">
            <span class="timeline-seq"></span>
            <span class="timeline-station"></span>
            <span class="status-badge"></span>
            <span class="timeline-chevron" data-chevron="${s.id}">&#9660;</span>
          </div>
          <div class="timeline-body" data-body="${s.id}">
            <div class="timeline-detail-wrap"></div>
            <div class="timeline-photos-wrap">
              <button class="btn-nav timeline-photos-toggle" data-photos-toggle="${s.id}">&#128247; Photos</button>
              <div class="timeline-photos" data-photos-for="${s.id}" style="display:none;"></div>
            </div>
          </div>`;

    const headerEl = el.querySelector('.timeline-header');
    const bodyEl = el.querySelector('.timeline-body');
    const detailWrapEl = el.querySelector('.timeline-detail-wrap');
    const chevronEl = el.querySelector('.timeline-chevron');

    // Default open/closed only on first creation — later polls never touch this.
    if (!isCompleted) {
      bodyEl.classList.add('open');
      chevronEl.classList.add('open');
    }

    // Delegated listeners bound once — survive every future content patch,
    // so action buttons never need rebinding on poll.
    headerEl.addEventListener('click', () => {
      bodyEl.classList.toggle('open');
      chevronEl.classList.toggle('open');
    });

    bindActionDelegation(detailWrapEl);
    bindPhotosToggle(bodyEl, s.id);

    return {
      el,
      seqEl: el.querySelector('.timeline-seq'),
      stationEl: el.querySelector('.timeline-station'),
      badgeEl: el.querySelector('.status-badge'),
      detailWrapEl,
      itemClass: '',
      detailHtml: null,
    };
  }

  DASH.timeline = {
    _stopNodes: new Map(), // stop_id → node refs
    _setKey: null,
    _currentStopCardHtml: null,
    _currentStopCardBound: false,

    // Full rebuild only when the set of stop ids changes (vehicle selection
    // switch, or a stop inserted); a same-assignment poll only patches the
    // header (status/seq/name) and swaps each stop's detail content when it
    // actually changed — collapse state, photo-gallery state, and button
    // bindings are untouched.
    render(stops, currentStopId, etas) {
      const container = document.getElementById('timeline');
      const countEl = document.getElementById('stopCount');
      const list = stops || [];

      this._renderCurrentStopCard(list, currentStopId, etas);

      if (list.length === 0) {
        container.innerHTML = '<div class="empty-state">Select a vehicle to view stops</div>';
        if (countEl) countEl.textContent = '';
        this._stopNodes.clear();
        this._setKey = null;
        openReasonStopIds.clear();
        return;
      }

      if (countEl) countEl.textContent = list.length;

      const key = list.map((s) => s.id).join(',');
      if (key !== this._setKey) {
        // Any reason row belonged to DOM nodes being torn down below — an
        // abandoned (never confirmed/cancelled) edit must not permanently
        // freeze that stop's content on a future rebuild (its "open" state
        // no longer exists once the old node is gone).
        openReasonStopIds.clear();
        container.innerHTML = '';
        this._stopNodes.clear();
        this._setKey = key;
      }

      const etaMap = {};
      if (etas && etas.etas) {
        etas.etas.forEach((e) => {
          if (e.stop_id != null) etaMap[e.stop_id] = e.eta_seconds != null ? e.eta_seconds : (e.eta || '--');
        });
      }

      list.forEach((s) => {
        let entry = this._stopNodes.get(s.id);
        if (!entry) {
          entry = createStop(s);
          this._stopNodes.set(s.id, entry);
          container.appendChild(entry.el);
        }
        this._patchStop(entry, s, currentStopId, etaMap[s.id]);
      });
    },

    // Resets to the empty state and drops the node cache — use this instead
    // of touching #timeline's innerHTML directly, or the cache above goes
    // stale (its nodes get detached without the module knowing).
    clear() {
      this.render([], null, null);
    },

    _patchStop(entry, s, currentStopId, eta) {
      const execStatus = s.execution_status || 'planned';
      const isCurrent = currentStopId && s.id === currentStopId;
      const isCompleted = ['completed', 'skipped', 'cancelled'].includes(execStatus);
      const itemClass = isCurrent ? 'timeline-item current' : isCompleted ? 'timeline-item completed' : 'timeline-item';
      if (entry.itemClass !== itemClass) {
        entry.el.className = itemClass;
        entry.itemClass = itemClass;
      }

      setText(entry.seqEl, s.planned_sequence || '?');
      setText(entry.stationEl, s.station_name || s.station_code || 'Stop');

      const badgeClass = 'status-badge ' + statusClass(execStatus);
      if (entry.badgeEl.className !== badgeClass) entry.badgeEl.className = badgeClass;
      setText(entry.badgeEl, statusLabel(execStatus));

      if (openReasonStopIds.has(String(s.id))) return;

      const detailHtml = buildDetailHtml(s, execStatus, eta);
      if (entry.detailHtml !== detailHtml) {
        entry.detailWrapEl.innerHTML = detailHtml;
        entry.detailHtml = detailHtml;
      }
    },

    // Pinned mini-card at the top of the panel: the current stop's contact
    // info and primary actions, always visible regardless of where the
    // dispatcher has scrolled the timeline below.
    _renderCurrentStopCard(stops, currentStopId, etas) {
      const card = document.getElementById('currentStopCard');
      if (!card) return;
      if (!this._currentStopCardBound) {
        this._currentStopCardBound = true;
        bindActionDelegation(card);
      }

      const stop = currentStopId ? stops.find((s) => s.id === currentStopId) : null;
      if (!stop) {
        card.style.display = 'none';
        this._currentStopCardHtml = null;
        return;
      }

      let eta = null;
      if (etas && etas.etas) {
        const match = etas.etas.find((e) => e.stop_id === stop.id);
        if (match) eta = match.eta_seconds != null ? match.eta_seconds : match.eta;
      }

      const execStatus = stop.execution_status || 'planned';
      const phone = (stop.manager_phone || '').trim();
      const phoneHtml = phone
        ? `<a class="cs-phone" href="tel:${escapeHtml(phone.replace(/[^0-9+]/g, ''))}">&#128222; ${escapeHtml(phone)}</a>`
        : '';
      const etaText = typeof eta === 'number' ? `ETA ${Math.round(eta / 60)} min` : '';

      const html = `
              <div class="cs-header">
                <span class="cs-label">Current Stop</span>
                <span class="status-badge ${statusClass(execStatus)}">${statusLabel(execStatus)}</span>
              </div>
              <div class="cs-station">#${stop.planned_sequence || '?'} ${escapeHtml(stop.station_name || stop.station_code || 'Stop')}</div>
              <div class="cs-detail">
                ${stop.address ? `<div class="cs-address">${escapeHtml(stop.address)}</div>` : ''}
                ${stop.manager_name ? `<div class="cs-manager">${escapeHtml(stop.manager_name)}</div>` : ''}
                ${phoneHtml}
                ${etaText ? `<div class="cs-eta">${etaText}</div>` : ''}
              </div>
              ${buildActionsHtml(stop.id, execStatus)}`;

      card.style.display = '';
      if (openReasonStopIds.has(String(stop.id))) return;
      if (this._currentStopCardHtml !== html) {
        card.innerHTML = html;
        this._currentStopCardHtml = html;
      }
    },
  };
})();
