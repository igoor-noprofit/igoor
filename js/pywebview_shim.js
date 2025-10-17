(function attachPywebviewShim() {
  if (typeof window === "undefined") {
    return;
  }

  function createShim(api) {
    return {
      change_view: (lastview, view) => api.changeView(lastview, view),
      force_onboarding: () => api.forceOnboarding(),
      onboarding_toggled: (isOnboarding) => api.onboardingToggled(Boolean(isOnboarding)),
      get_plugins_by_category: () => api.getPluginsByCategory(),
      toggle_plugin: (pluginName, active) => api.togglePlugin(pluginName, active),
      get_current_plugin_settings: (pluginName) => api.getCurrentPluginSettings(pluginName),
      get_plugin_settings: (pluginName) => api.getPluginSettings(pluginName),
      update_plugin_settings: (pluginName, settings) => api.updatePluginSettings(pluginName, settings),
      save_plugin_settings: (pluginName, settings) => api.savePluginSettings(pluginName, settings),
      trigger_hook_sync: (hookName, payload) => api.triggerHook(hookName, payload),
      maximize: () => api.maximize(),
      minimize: () => api.minimize(),
      win_minimize: () => api.winMinimize(),
    };
  }

  function attachShimIfNeeded() {
    if (window.pywebview?.api || !window.backendApi) {
      return;
    }
    const original = window.pywebview?.api || {};
    const shimmed = createShim(window.backendApi);
    window.pywebview = { api: { ...original, ...shimmed } };
  }

  attachShimIfNeeded();
  window.addEventListener("backendApiReady", attachShimIfNeeded, { once: true });
})();
