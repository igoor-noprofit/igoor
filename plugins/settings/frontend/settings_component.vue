<template>
    <div>
        <!-- Settings Gear Icon -->
        <div @click="showModal = true" class="settings-gear">
            ⚙️
        </div>
        <!-- Modal Window for Plugin Settings -->
        <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
            <div class="modal-content">
                <button @click="showModal = false" class="close-button">✖</button>
                <div v-for="(plugins, category) in pluginData" :key="category">
                    <h2>{{ category }}</h2>
                    <div>
                        <div v-for="plugin in plugins" :key="plugin.name" @click="selectPlugin(category, plugin.name)">
                            <span>{{ plugin.title }}</span>
                            <label>
                                Active:
                                <input type="checkbox" :checked="plugin.active"
                                    @change="togglePlugin(category, plugin.name, $event.target.checked)">
                            </label>
                        </div>
                    </div>
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
</template>


<script>
export default {
    name: 'SettingsComponent',
    data() {
        return {
            pluginData: {},
            selectedPlugin: null,
            showModal: false,
            selectedPluginComponent: null
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
                console.log (`/plugins/${pluginName}/frontend/${pluginName}_settings.vue`);
                this.selectedPluginComponent = async () => await import(`/plugins/${pluginName}/frontend/${pluginName}_settings.vue`);
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
    font-size: 2rem;
    cursor: pointer;
    text-align: center;
    margin-top: 20px;
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
</style>