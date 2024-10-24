<template>
    <div>
        <div v-for="(plugins, category) in pluginData" :key="category">
            <h2>{{ category }}</h2>
            <div>
                <div v-for="plugin in plugins" :key="plugin.name" @click="selectPlugin(category, plugin.name)">
                    <span>{{ plugin.name }}</span>
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
            <!-- Add your plugin settings editors here, based on the selected plugin -->
        </div>
    </div>
</template>

<script>
mmodule.exports = {
    data() {
        return {
            pluginData: {},
            selectedPlugin: null
        };
    },
    mounted() {
        this.loadPlugins();
    },
    methods: {
        loadPlugins() {
            window.pywebview.api.get_plugins_data().then(response => {
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
        }
    }
};

</script>

<style scoped></style>