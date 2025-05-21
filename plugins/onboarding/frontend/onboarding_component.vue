<template>
    <div>
        <!-- Settings Gear Icon -->
        <div @click="showModal = true" class="settings-gear">
            <img src="/img/icons/src/settings.svg" width="30">
        </div>
        <!-- Modal Window for Plugin Settings 
        @click.self="showModal = false" 
        -->
        <div v-if="showModal" class="modal-overlay">
            <div class="modal-content settings container onboarding plugin">
                <!--button @click="showModal = false" class="close-button">✖</button-->

                <!-- Restart Alert -->
                <div v-if="showRestartAlert" class="restart-alert">
                    Please restart the app for plugin changes to take effect.
                </div>
                <div>
                    <ul class="tabs">
                        <li :class="{ active: currentTab === 'bio' }" @click="currentTab = 'bio'">Bio</li>
                        <li :class="{ active: currentTab === 'prefs' }" @click="currentTab = 'prefs'">Preferences</li>
                        <li :class="{ active: currentTab === 'ai' }" @click="currentTab = 'ai'">AI</li>
                        <li :class="{ active: currentTab === 'plugins' }" @click="currentTab = 'plugins'">Plugins</li>
                        <li :class="{ active: currentTab === 'about' }" @click="currentTab = 'about'">About</li>
                    </ul>
                    <div v-if="currentTab === 'bio'" class="bio-container">
                        <div class="bio left">
                            <div>
                                <label>Name</label><input type="text" v-model="bio.name">
                            </div>
                            <div>
                                <label>Pronoun</label><input type="text" v-model="bio.pronoun">
                            </div>
                            <div>
                                <label>Year of birth</label><input type="text" v-model="bio.birth_date">
                            </div>
                        </div>
                        <div class="bio right">
                            <div>
                                <label>Health State</label>
                                <textarea v-model="bio.health_state"></textarea>
                            </div>
                        </div>
                    </div>
                    <div v-if="currentTab === 'prefs'">
                        <div class="prefs left">
                            <div>
                                <label>Language</label>
                                <select v-model="prefs.lang">
                                    <option value="fr_FR">Français</option>
                                    <!--option value="en_EN">English</option-->
                                </select>
                            </div>
                            <div>
                                <label>Automatic dark/Light Mode</label>
                                <label class="switch disabled">
                                    <input type="checkbox" v-model="prefs.darklight" true-value="dark"
                                        false-value="light">
                                    <span class="slider round"></span>
                                </label>
                            </div>
                            <div>
                                <label>Locale</label><input type="text" v-model="prefs.locale" disabled>
                            </div>
                        </div>
                    </div>
                    <div v-if="currentTab === 'ai'">
                        <div class="class=ai left">
                            <div>
                                <label>Provider</label>
                                <select v-model="ai.provider">
                                    <option value="groq">Groq</option>
                                    <!--option value="openai">OpenAI</option-->
                                </select>
                            </div>
                            <div>
                                <label>API Key</label><input type="text" v-model="ai.api_key" disabled>
                                <!--p>Groq is our default provider. <a href="https://console.groq.com/login" target="_blank">To
                                        obtain
                                        a FREE api key sign up here</a>
                                    <a href="https://groq.com/privacy-policy/">Our default provider privacy policy</a>
                                </p-->
                            </div>
                            <div>
                                <label>Model Name</label>
                                <select v-model="ai.model_name">
                                    <option value="llama-3.3-70b-versatile">Llama 3.3-70B</option>
                                    <option value="meta-llama/llama-4-maverick-17b-128e-instruct">Llama 4-17b-128e
                                    </option>
                                    <option value="meta-llama/llama-4-scout-17b-16e-instruct">Llama 4-17b-16e</option>
                                    <!--option value="en_EN">English</option-->
                                </select>
                            </div>
                            <div>
                                <label>Temperature</label><input type="text" v-model="ai.temperature">
                            </div>
                        </div>
                    </div>
                    <div v-if="currentTab === 'plugins'">
                        <!-- Tab Navigation -->
                        <ul class="tabs plugins">
                            <li v-for="category in categories" :key="category"
                                :class="{ active: activeTab === category }" @click="activeTab = category">
                                {{ category.toUpperCase() }}
                            </li>
                        </ul>

                        <!-- Plugins Grid for Active Tab -->
                        <div v-if="activeTab" class="plugins-grid">
                            <div v-for="plugin in pluginsByCategory[activeTab]" :key="plugin.name" class="plugin-card"
                                :class="{ 'core-plugin': plugin.is_core }">
                                <div class="plugin-header">
                                    <h3 class="plugin-title">
                                        {{ plugin.title }}
                                        <span v-if="plugin.is_core" class="core-badge">CORE</span>
                                    </h3>
                                    <!--label class="toggle-switch" :class="{ 'disabled': plugin.is_core }">
                                        <input type="checkbox" :checked="plugin.active" :disabled="plugin.is_core"
                                            @change="togglePlugin(activeTab, plugin.name, $event.target.checked)">
                                        <span class="slider"></span>
                                    </label-->
                                    <label class="switch"><input type="checkbox" :checked="plugin.active"
                                            :disabled="plugin.is_core"
                                            @change="togglePlugin(activeTab, plugin.name, $event.target.checked)"><span
                                            class="slider round"></span></label>
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
                    <div v-if="currentTab === 'about'">
                        <div class="about about-tab left">
                            <p>Concept by Igor Novitzki</p>
                            <p>© 2025 Developed by <a href="https://igoor.org/?utm_source=igoor_app" target="_blank">IGOOR</a>, in partnership
                                with <a href="https://www.arsla.org/?utm_source=igoor_app" target="_blank">ARSLA</a></p>
                        </div>
                    </div>
                </div>
                <div class="save-section">
                    <button @click="saveSettings" :disabled="isSaving">
                        {{ isSaving ? 'Saving...' : 'Save' }}
                    </button>
                    <span v-if="saveStatus" :class="['save-status', saveStatus.type]">
                        {{ saveStatus.message }}
                    </span>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "onboarding",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
            activeTab: '',
            pluginData: {},
            currentTab: 'bio',
            showModal: false,
            bio: {
                name: "",
                pronoun: "",
                birth_date: "",
                health_state: ""
            },
            prefs: {
                lang: "",
                darklight: "light",
                locale: ""
            },
            ai: {
                provider: "",
                api_key: "",
                model_name: "",
                temperature: ""
            },
            isSaving: false,
            saveStatus: null,
            pywebviewready: false,
            showRestartAlert: false
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
    methods: {
        async saveSettings() {
            this.isSaving = true;
            this.saveStatus = null;

            try {
                const dataToSend = {
                    bio: this.bio,
                    prefs: this.prefs,
                    ai: this.ai
                };

                await this.sendMsgToBackend({
                    action: 'save_settings',
                    data: dataToSend
                });

                this.saveStatus = {
                    type: 'success',
                    message: 'Settings saved successfully!'
                };

                // Emit event for parent components
                this.$emit('settings-saved', dataToSend);

            } catch (error) {
                console.error('Error saving settings:', error);
                this.saveStatus = {
                    type: 'error',
                    message: 'Failed to save settings. Please try again.'
                };
            } finally {
                this.isSaving = false;

                // Clear success message after 3 seconds
                if (this.saveStatus?.type === 'success') {
                    setTimeout(() => {
                        this.saveStatus = null;
                    }, 3000);
                }
            }
        },
        handleIncomingMessage(event) {
            console.log("Custom message handler in " + this.name + " component:", event.data);
            try {
                const data = JSON.parse(event.data);
                if (data.bio) {
                    this.bio = { ...this.bio, ...data.bio };
                }
                if (data.prefs) {
                    this.prefs = { ...this.prefs, ...data.prefs };
                }
                if (data.ai) {
                    this.ai = { ...this.ai, ...data.ai };
                }
                console.log("Updated component data:", this.bio, this.prefs, this.ai);
            } catch (e) {
                console.warn("Error parsing JSON", e);
            }
        },
        saveSettings() {
            const dataToSend = {
                bio: this.bio,
                prefs: this.prefs,
                ai: this.ai
            };
            this.sendMsgToBackend(dataToSend);
            console.log("Settings saved and sent to backend:", dataToSend);
            this.showModal = false;
        },
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
                // Do not override activeTab here, keep ABOUT as default
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
.about-tab {
    background: #000;
    font-size: 1.2rem;
    a{
        color: #fff
    }
    padding: 30px;
}
.tabs {
    display: flex;
    list-style-type: none;
    padding: 0;
    margin: 0;
    border: none !important;
    background: none !important;
}

.tabs li {
    padding: 10px 20px;
    cursor: pointer;
    border-bottom: none;
}

.tabs li:hover {
    background-color: #e0e0e0;
}

.switch {
    position: relative;
    display: inline-block;
    width: 60px;
    height: 34px;
}

.switch input {
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
}

.slider:before {
    position: absolute;
    content: "";
    height: 26px;
    width: 26px;
    left: 4px;
    bottom: 4px;
    background-color: white;
    transition: .4s;
}

input:checked+.slider {
    background-color: #2196F3;
}

input:focus+.slider {
    box-shadow: 0 0 1px #2196F3;
}

input:checked+.slider:before {
    transform: translateX(26px);
}

/* Rounded sliders */
.slider.round {
    border-radius: 34px;
}

.slider.round:before {
    border-radius: 50%;
}

.bio-container {
    display: flex;
}

.left,
.right {
    width: 48%;
    text-align: left;
}

.left div,
.right div {
    margin-bottom: 10px;
}

.save-section {
    margin-top: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.save-status {
    padding: 8px;
    border-radius: 4px;
    font-size: 0.9em;
}

.save-status.success {
    background-color: #e6ffe6;
    color: #006600;
}

.save-status.error {
    background-color: #ffe6e6;
    color: #cc0000;
}

button:disabled {
    opacity: 0.7;
    cursor: not-allowed;
}

/* SETTINGS */
.close-button {
    z-index: 100;
}

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
    top: 40px;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: flex-start;
    justify-content: center;
}

/* Modal content styles */
.modal-content {
    background: #fff;
    padding: 20px;
    border-radius: 8px;
    position: relative;
    color: #000;
    height: 100%;
    font-size: 18px;
    width: 100%;
}

/* PLUGINS */
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

.plugins-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 20px;
    padding: 20px 0;
}

.plugin-card {
    background: #000;
    border-radius: 10px;
    padding: 16px;
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
    color: #fff;
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
    font-size: 0.7rem;
    color: #fff;
    padding: 4px 8px;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}
</style>