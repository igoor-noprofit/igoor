<template>
    <div>
        <!-- Settings Gear Icon -->
        <div @click="showModal = true" class="settings-gear">
            ⚙️
        </div>
        <!-- Modal Window for Plugin Settings -->
        <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
            <div class="modal-content settings container">
                <button @click="showModal = false" class="close-button">✖</button>
                <!-- Tab Navigation -->
                <div class="tabs">
                    <button v-for="(plugins, category) in pluginData" :key="category"
                        :class="{ active: activeTab === category }" @click="activeTab = category">
                        {{ category.toUpperCase() }}
                    </button>
                </div>
                <!-- Plugins for Active Tab -->
                <div v-if="activeTab">
                    <div v-for="plugin in pluginData[activeTab]" :key="plugin.name"
                        @click="selectPlugin(activeTab, plugin.name)">
                        <span>{{ plugin.title }}</span>
                        <label>
                            <input type="checkbox" :checked="plugin.active"
                                @change="togglePlugin(activeTab, plugin.name, $event.target.checked)">
                        </label>
                    </div>
                    <div v-if="selectedPlugin">
                        <!-- Display selected plugin details and settings here -->
                        <h3>Edit Plugin: {{ selectedPlugin.name }}</h3>
                        <!-- Dynamically load the component for the selected plugin -->
                        <component :is="selectedPluginComponent"></component>
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
            selectedPlugin: null,
            showModal: false,
            selectedPluginComponent: null,
            activeTab: null // New data property for active tab
        };
    },
    mounted() {
        this.loadPlugins();
    },
    methods: {
        loadPlugins() {
            window.pywebview.api.get_plugins_by_category().then(response => {
                console.log(response)
                console.table(response)
                this.pluginData = response;
                this.activeTab = Object.keys(response)[0]; // Set the first category as the active tab
            });
        },
        togglePlugin(category, pluginName, isActive) {
            window.pywebview.api.toggle_plugin(pluginName, isActive).then(() => {
                this.pluginData[category].find(p => p.name === pluginName).active = isActive;
            });
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

/* Tabs styles */
.tabs {
    display: flex;
    margin-bottom: 20px;
}

.tabs button {
    padding: 10px 20px;
    margin-right: 5px;
    cursor: pointer;
    background: #f0f0f0;
    border: none;
    border-radius: 4px;
}

.tabs button.active {
    background: #007bff;
    color: #fff;
}
</style>