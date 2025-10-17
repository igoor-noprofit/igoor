let backendApiPromise;

export function ensureBackendApi() {
  if (typeof window !== "undefined" && window.backendApi) {
    return Promise.resolve(window.backendApi);
  }
  if (!backendApiPromise) {
    backendApiPromise = import("/js/backend_api.js").then((module) => module.backendApi);
  }
  return backendApiPromise;
}
