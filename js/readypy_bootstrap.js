if (typeof window !== "undefined") {
  window.__app_pending_readypy = [];
  window.__app_register_readypy = function registerReadypy(fn) {
    window.app = window.app || {};
    window.app.readypy = fn;

    const pending = window.__app_pending_readypy;
    if (Array.isArray(pending)) {
      while (pending.length) {
        const args = pending.shift();
        try {
          fn(...(Array.isArray(args) ? args : []));
        } catch (error) {
          console.error("Deferred readypy call failed", error);
        }
      }
    }
  };

  window.app = window.app || {};
  window.app.pywebviewready = false;
  window.app.readypy = function queueReadypy(...args) {
    window.__app_pending_readypy.push(args);
    return null;
  };
}
