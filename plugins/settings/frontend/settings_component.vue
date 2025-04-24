<template>
    <div>
        <!-- Settings Gear Icon -->
        <div @click="showModal = true" class="settings-gear">
            <img src="/img/icons/src/settings.svg" width="30">
        </div>
        <!-- Modal Window for Plugin Settings -->
        <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
            <div class="modal-content settings container">
                <button @click="showModal = false" class="close-button">✖</button>

                <!-- Restart Alert -->
                <div v-if="showRestartAlert" class="restart-alert">
                    Please restart the app for plugin changes to take effect.
                </div>

                <!-- Tab Navigation -->
                <div class="tabs">
                    <button v-for="category in categories" :key="category" :class="{ active: activeTab === category }"
                        @click="activeTab = category">
                        {{ category.toUpperCase() }}
                    </button>
                </div>

                <!-- Plugins Grid for Active Tab -->
                <div v-if="activeTab" class="plugins-grid">
                    <div v-for="plugin in pluginsByCategory[activeTab]" :key="plugin.name" class="plugin-card"
                        :class="{ 'core-plugin': plugin.is_core }">
                        <div class="plugin-header">
                            <h3 class="plugin-title">
                                {{ plugin.title }}
                                <span v-if="plugin.is_core" class="core-badge">CORE</span>
                            </h3>
                            <label class="toggle-switch" :class="{ 'disabled': plugin.is_core }">
                                <input type="checkbox" :checked="plugin.active" :disabled="plugin.is_core"
                                    @change="togglePlugin(activeTab, plugin.name, $event.target.checked)">
                                <span class="slider"></span>
                            </label>
                        </div>
                        <p class="plugin-description">{{ plugin.description || 'No description available' }}</p>
                        <div class="plugin-requirements">
                            <span v-if="plugin.is_core" class="requirement core">
                                🔒 Core Plugin
                            </span>
                            <span v-if="plugin.requires_internet" class="requirement">
                                🌐 Requires Internet
                            </span>
                            <span v-if="plugin.requires_subscription" class="requirement">
                                ⭐ Requires Subscription
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
export default {
    name: 'SettingsComponent',
    data() {
        return {
            pluginData: {},
            showModal: false,
            activeTab: null,
            pywebviewready: false,
            showRestartAlert: false // <-- Add this line
        }
    },
    computed: {
        categories() {
            return Object.keys(this.pluginData)
        },
        pluginsByCategory() {
            // Exclude plugins by name
            const excluded = ["baseplugin", "settings", "onboarding"];
            const filtered = {};
            for (const [category, plugins] of Object.entries(this.pluginData)) {
                filtered[category] = plugins.filter(
                    p => !excluded.includes(p.name)
                );
            }
            return filtered;
        }
    },
    async mounted() {
        // Wait for pywebview to be ready before proceeding
        await new Promise(resolve => {
            if (window.pywebview && window.pywebview.api) {
                this.pywebviewready = true;
                resolve();
            } else {
                window.addEventListener("pywebviewready", () => {
                    this.pywebviewready = true;
                    console.log("Pywebview is ready in settings component!");
                    resolve();
                });
            }
        });

        // Now safe to load plugins
        await this.loadPlugins();
    },
    methods: {
        async loadPlugins() {
            try {
                if (!this.pywebviewready) {
                    console.log("Pywebview not ready, waiting to load plugins...");
                    return;
                }
                const response = await window.pywebview.api.get_plugins_by_category();
                console.log(response);
                console.table(response);
                this.pluginData = response;
                this.activeTab = Object.keys(response)[0];
            } catch (error) {
                console.error("Error loading plugins:", error);
            }
        },
        async togglePlugin(category, pluginName, isActive) {
            const plugin = this.pluginsByCategory[category].find(p => p.name === pluginName);
            if (plugin && plugin.is_core) {
                console.log("Cannot toggle core plugin:", pluginName);
                return;
            }

            try {
                const result = await window.pywebview.api.toggle_plugin(pluginName, isActive);
                if (result) {
                    plugin.active = isActive;
                }
            } catch (error) {
                console.error("Error toggling plugin:", error);
            }
            // Always show restart alert after attempting toggle
            this.showRestartAlert = true;
            setTimeout(() => {
                this.showRestartAlert = false;
            }, 4000);
        },
        selectPlugin(category, pluginName) {
            this.selectedPlugin = this.pluginData[category].find(p => p.name === pluginName);
            this.loadPluginComponent(pluginName);
        },
        async loadPluginComponent(pluginName) {
            try {
                console.log(`/plugins/${pluginName}/frontend/${pluginName}_settings.vue`);
                const component = await import(`/plugins/${pluginName}/frontend/${pluginName}_settings.vue`);
                const settings = await window.pywebview.api.get_plugin_settings(pluginName);
                console.table(settings);
                this.selectedPluginComponent = component.default || component;

                // Wait for the component to be rendered
                this.$nextTick(() => {
                    for (const [key, value] of Object.entries(settings)) {
                        const input = this.$el.querySelector(`input[name="${key}"]`);
                        if (input) {
                            input.value = value;
                        }
                    }
                });
            } catch (error) {
                console.error(`Failed to load component for plugin: ${pluginName}`, error);
            }
        }
    }
};
</script>

<style>
/* Style for the gear icon */
.settings-gear {
    font-size: 1.2rem;
    cursor: pointer;
    text-align: center;
    filter: invert(100%)
}

/* Modal overlay styles */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
}

/* Modal content styles */
.modal-content {
    background: #fff;
    padding: 20px;
    border-radius: 8px;
    width: 80%;
    max-width: 90%;
    position: relative;
    color: #000;
    height: 80%;
    font-size: 18px;
}

/* Close button */
.close-button {
    position: absolute;
    top: 10px;
    right: 10px;
    background: none;
    border: none;
    font-size: 1.2rem;
    cursor: pointer;
}

.tabs {
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
    padding: 10px 0;
    border-bottom: 1px solid #eee;
    position: sticky;
    top: 0;
    background: white;
}

.tabs button {
    padding: 8px 16px;
    border: none;
    border-radius: 4px;
    background: #f0f0f0;
    cursor: pointer;
    font-weight: 500;
}

.tabs button.active {
    background: #2196F3;
    color: white;
}

.plugins-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 20px;
    padding: 20px 0;
}

.plugin-card {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 16px;
    border: 1px solid #eee;
    transition: all 0.3s ease;
}

.plugin-card:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.plugin-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.plugin-title {
    margin: 0;
    font-size: 1.1em;
    font-weight: 600;
}

.plugin-description {
    color: #666;
    font-size: 0.9em;
    margin: 8px 0;
    line-height: 1.4;
}

.plugin-requirements {
    margin-top: 12px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.requirement {
    font-size: 0.8em;
    color: #666;
    background: #e9ecef;
    padding: 4px 8px;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}


/* Toggle switch styles */
.toggle-switch {
    position: relative;
    display: inline-block;
    width: 50px;
    height: 24px;
}

.toggle-switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #ccc;
    transition: .4s;
    border-radius: 24px;
}

.slider:before {
    position: absolute;
    content: "";
    height: 16px;
    width: 16px;
    left: 4px;
    bottom: 4px;
    background-color: white;
    transition: .4s;
    border-radius: 50%;
}

input:checked+.slider {
    background-color: #2196F3;
}

input:checked+.slider:before {
    transform: translateX(26px);
}

.close-button {
    z-index: 100;
}

.core-plugin {
    background: #f8f9fa;
    border: 1px solid #e9ecef;
    opacity: 0.9;
}

.core-badge {
    font-size: 0.7em;
    background: #6c757d;
    color: white;
    padding: 2px 6px;
    border-radius: 4px;
    margin-left: 8px;
    vertical-align: middle;
}

.toggle-switch.disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.toggle-switch.disabled input {
    cursor: not-allowed;
}

.toggle-switch.disabled .slider {
    cursor: not-allowed;
}

.requirement.core {
    background: #6c757d;
    color: white;
}

.restart-alert {
    background: #ffecb3;
    color: #795548;
    border: 1px solid #ffe082;
    padding: 12px 20px;
    border-radius: 6px;
    margin-bottom: 18px;
    font-size: 1em;
    text-align: center;
    font-weight: 500;
}
</style>