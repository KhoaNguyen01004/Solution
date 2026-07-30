// ================================================================
// Dispatch Dashboard — API Module
// ================================================================
window.DASH = window.DASH || {};

(function () {
  'use strict';

  async function fetchJSON(url, opts) {
    const resp = await fetch(url, opts);
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(body.error || body.message || `HTTP ${resp.status}`);
    }
    return resp.json();
  }

  DASH.api = {
    dashboard() {
      return fetchJSON('/api/execution/dashboard');
    },

    plans() {
      return fetchJSON('/api/plans');
    },

    drivers() {
      return fetchJSON('/api/drivers');
    },

    stops(assignmentId) {
      return fetchJSON(`/api/stops?assignment_id=${assignmentId}`);
    },

    progress(assignmentId) {
      return fetchJSON(`/api/execution/progress?assignment_id=${assignmentId}`);
    },

    eta(assignmentId) {
      return fetchJSON(`/api/eta?assignment_id=${assignmentId}`);
    },

    advance(stopId) {
      return fetchJSON('/api/execution/advance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stop_id: stopId }),
      });
    },

    skip(stopId, reason) {
      return fetchJSON(`/api/stops/${stopId}/skip`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: reason || '' }),
      });
    },

    cancel(stopId, reason) {
      return fetchJSON(`/api/stops/${stopId}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: reason || '' }),
      });
    },

    planDetail(planId) {
      return fetchJSON(`/api/plans/${planId}`);
    },

    stopImages(stopId) {
      return fetchJSON(`/api/stops/${stopId}/images`);
    },
  };
})();
