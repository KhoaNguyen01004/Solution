// ================================================================
// Dispatch Dashboard — API Module
// ================================================================
window.DASH = window.DASH || {};

(function () {
  'use strict';

  // /api/eta issues one ORS call per remaining stop, serially, each with a
  // 30-second server-side timeout — so a slow route can hang far longer than
  // the 12-second poll interval. Without a client timeout the poll's
  // in-flight guard stayed set and the dashboard froze showing a green
  // "Live" pill over stale data (audit P-08).
  const REQUEST_TIMEOUT_MS = 20000;

  async function fetchJSON(url, opts) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    let resp;
    try {
      resp = await fetch(url, { ...opts, signal: controller.signal });
    } catch (e) {
      if (e.name === 'AbortError') {
        throw new Error(`Request timed out after ${REQUEST_TIMEOUT_MS / 1000}s: ${url}`);
      }
      throw e;
    } finally {
      clearTimeout(timeoutId);
    }

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

    // expectedStatus is the execution_status this stop's card was rendered
    // with. The server refuses the move if the stop has since changed, so a
    // double-tap can't walk it two steps (planned -> arrived -> completed).
    advance(stopId, expectedStatus) {
      return fetchJSON('/api/execution/advance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stop_id: stopId, expected_status: expectedStatus }),
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

    // The server insists on the assignment's *complete* stop list, in the
    // desired order — a partial list used to renumber only the stops it named
    // and leave duplicate execution_sequences behind.
    reorderStops(assignmentId, stopIds) {
      return fetchJSON('/api/stops/reorder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assignment_id: assignmentId, stop_ids: stopIds }),
      });
    },

    planDetail(planId) {
      return fetchJSON(`/api/plans/${planId}`);
    },

    stopImages(stopId) {
      return fetchJSON(`/api/stops/${stopId}/images`);
    },

    deletePlans(planIds) {
      return fetchJSON('/api/plans/batch-delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan_ids: planIds }),
      });
    },

    clearPlans() {
      return fetchJSON('/api/plans/clear', { method: 'POST' });
    },
  };
})();
