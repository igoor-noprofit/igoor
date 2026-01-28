const API_BASE = "/api";

function pick(obj, key, fallback) {
  return obj && key in obj ? obj[key] : fallback;
}

class BackendApi {
  constructor() {
    this._bridge = this._detectBridge();
    this._waiters = [];
    this._bridgeReady = !!this._bridge;
    if (typeof window !== "undefined") {
      window.addEventListener(
        "pywebviewready",
        () => {
          this._bridge = this._detectBridge();
          this._bridgeReady = !!this._bridge;
          this._resolveWaiters();
        },
        { once: true }
      );
    }
    if (!this._bridge) {
      // fallback is immediately ready
      queueMicrotask(() => this._resolveWaiters());
    }
  }

  get isBridgeAvailable() {
    return !!this._detectBridge();
  }

  async waitUntilReady() {
    if (!this.isBridgeAvailable) {
      return;
    }
    if (this._bridgeReady) {
      return;
    }
    return new Promise((resolve) => {
      this._waiters.push(resolve);
    });
  }

  getBridge() {
    return this._detectBridge();
  }

  async changeView(lastview, view) {
    const bridge = this.getBridge();
    if (bridge?.change_view) {
      return bridge.change_view(lastview, view);
    }
    return this._postJson("/app/change-view", { lastview, view }, false);
  }

  async forceOnboarding() {
    const bridge = this.getBridge();
    if (bridge?.force_onboarding) {
      return bridge.force_onboarding();
    }
    return this.triggerHook("force_onboarding");
  }

  async onboardingToggled(isOnboarding) {
    const bridge = this.getBridge();
    if (bridge?.onboarding_toggled) {
      return bridge.onboarding_toggled(isOnboarding);
    }
    return this.triggerHook("onboarding_toggled", { is_onboarding: isOnboarding });
  }

  async getPluginsByCategory() {
    const bridge = this.getBridge();
    if (bridge?.get_plugins_by_category) {
      return bridge.get_plugins_by_category();
    }
    return this._getJson("/plugins/by-category");
  }

  async togglePlugin(pluginName, active) {
    const bridge = this.getBridge();
    if (bridge?.toggle_plugin) {
      return bridge.toggle_plugin(pluginName, active);
    }
    return this._postJson(`/plugins/${encodeURIComponent(pluginName)}/toggle`, { active });
  }

  async getPluginSettings(pluginName) {
    const bridge = this.getBridge();
    if (bridge?.get_plugin_settings) {
      return bridge.get_plugin_settings(pluginName);
    }
    return this._getJson(`/plugins/${encodeURIComponent(pluginName)}/settings`);
  }

  async getCurrentPluginSettings(pluginName) {
    const bridge = this.getBridge();
    if (bridge?.get_current_plugin_settings) {
      return bridge.get_current_plugin_settings(pluginName);
    }
    return this.getPluginSettings(pluginName);
  }

  async updatePluginSettings(pluginName, settings) {
    const bridge = this.getBridge();
    if (bridge?.update_plugin_settings) {
      return bridge.update_plugin_settings(pluginName, settings);
    }
    return this._postJson(`/plugins/${encodeURIComponent(pluginName)}/settings`, { settings }, false);
  }

  async savePluginSettings(pluginName, settings) {
    const bridge = this.getBridge();
    if (bridge?.save_plugin_settings) {
      return bridge.save_plugin_settings(pluginName, settings);
    }
    return this.updatePluginSettings(pluginName, settings);
  }

  async triggerHook(hookName, payload = {}) {
    const bridge = this.getBridge();
    if (bridge?.trigger_hook_sync) {
      return bridge.trigger_hook_sync(hookName, payload);
    }
    const response = await this._postJson(`/hooks/${encodeURIComponent(hookName)}`, payload);
    return pick(response, "result", response);
  }

  async maximize() {
    const bridge = this.getBridge();
    if (bridge?.maximize) {
      return bridge.maximize();
    }
    // no-op in browser fallback
    return undefined;
  }

  async minimize() {
    const bridge = this.getBridge();
    if (bridge?.minimize) {
      return bridge.minimize();
    }
    return undefined;
  }

  async winMinimize() {
    const bridge = this.getBridge();
    if (bridge?.win_minimize) {
      return bridge.win_minimize();
    }
    return undefined;
  }

  async changeWindowState(action) {
    if (action === "maximize") {
      return this.maximize();
    }
    if (action === "minimize") {
      return this.minimize();
    }
    return undefined;
  }

  _detectBridge() {
    return typeof window !== "undefined" && window.pywebview?.api ? window.pywebview.api : null;
  }

  _resolveWaiters() {
    this._bridgeReady = true;
    if (!this._waiters.length) {
      return;
    }
    const waiters = [...this._waiters];
    this._waiters.length = 0;
    waiters.forEach((resolve) => resolve());
  }

  async _getJson(path) {
    const response = await fetch(`${API_BASE}${path}`, {
      credentials: "same-origin",
    });
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }
    return response.json();
  }

  async _postJson(path, body, expectJson = true) {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify(body ?? {}),
    });
    if (!response.ok) {
      const detail = await this._safeJson(response);
      const message = detail?.detail || `Request failed with status ${response.status}`;
      throw new Error(message);
    }
    if (!expectJson || response.status === 204) {
      return null;
    }
    return response.json();
  }

  async _safeJson(response) {
    try {
      return await response.json();
    } catch (error) {
      return null;
    }
  }
}

const backendApi = new BackendApi();

if (typeof window !== "undefined") {
  window.backendApi = backendApi;
  window.dispatchEvent(new CustomEvent("backendApiReady", { detail: backendApi }));
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { backendApi };
}

export { backendApi };
