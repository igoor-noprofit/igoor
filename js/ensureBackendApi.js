let backendApiPromise;

function ensureBackendApi() {
  if (typeof window !== "undefined" && window.backendApi) {
    return Promise.resolve(window.backendApi);
  }
  if (!backendApiPromise) {
    backendApiPromise = import("/js/backend_api.js").then((module) => module.backendApi);
  }
  return backendApiPromise;
}

if (typeof window !== "undefined") {
  window.ensureBackendApi = ensureBackendApi;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { ensureBackendApi };
}
