// ================================================================
// Dispatch Dashboard — Polling Module
// ================================================================
window.DASH = window.DASH || {};

(function () {
  'use strict';

  const INTERVAL_MS = 12000;
  let timer = null;
  let isPolling = false;

  DASH.polling = {
    start(onTick) {
      if (timer) return;
      async function tick() {
        if (isPolling) return;
        isPolling = true;
        try {
          await onTick();
          DASH.polling.setStatus('ok');
        } catch (e) {
          console.error('Poll error:', e);
          DASH.polling.setStatus('error');
        }
        isPolling = false;
      }
      tick();
      timer = setInterval(tick, INTERVAL_MS);
    },

    stop() {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      DASH.polling.setStatus('paused');
    },

    async refreshNow(onTick) {
      if (isPolling) return;
      isPolling = true;
      try {
        await onTick();
        DASH.polling.setStatus('ok');
      } catch (e) {
        console.error('Manual refresh error:', e);
        DASH.polling.setStatus('error');
      }
      isPolling = false;
    },

    setStatus(status) {
      const el = document.getElementById('pollStatus');
      if (!el) return;
      el.className = 'poll-status poll-' + status;
      const labels = { ok: 'Live', error: 'Error', paused: 'Paused' };
      el.textContent = labels[status] || status;
    },
  };
})();
