<template>
    <div>
        <!-- Settings Gear Icon -->
        <div @click="toggleModal" class="settings-gear">
            <img src="/img/icons/src/settings.svg" width="30">
        </div>
        <!-- Modal Window for Plugin Settings -->
        <div v-if="showModal" class="modal-overlay" :class="isSaving ? 'isSaving' : ''" :id="onboardingModal">
            <div class="modal-content settings container onboarding plugin">
                <!-- Restart Alert -->
                <div v-if="showRestartAlert" class="restart-alert">
                    {{ t("Please restart the app for changes to take effect.") }}
                </div>
                <div class="tabsandpluginscontainer">
                    <ul class="tabs">
                        <li :class="{ active: currentTab === 'bio' }"
                            @click="currentTab = 'bio'; viewingPluginSettings = false;">{{ t("Bio") }}</li>
                        <li :class="{ active: currentTab === 'prefs' }"
                            @click="currentTab = 'prefs'; viewingPluginSettings = false;">{{ t("Preferences") }}</li>
                        <li :class="{ active: currentTab === 'ai' }"
                            @click="currentTab = 'ai'; viewingPluginSettings = false;">{{ t("AI") }}</li>
                        <li :class="{ active: currentTab === 'plugins' }"
                            @click="currentTab = 'plugins'; viewingPluginSettings = false;">{{ t("Plugins") }}</li>
                        <li :class="{ active: currentTab === 'about' }"
                            @click="currentTab = 'about'; viewingPluginSettings = false;">{{ t("About") }}</li>
                    </ul>
                    <div v-if="currentTab === 'bio'" class="bio-container">
                        <div class="bio left">
                            <div>
                                <label>{{ t("Name") }}</label><input type="text" v-model="bio.name">
                            </div>
                            <div>
                                <label>{{ t("Pronoun") }}</label><input type="text" v-model="bio.pronoun">
                            </div>
                            <div>
                                <label>{{ t("Year of birth") }}</label><input type="text" v-model="bio.birth_date">
                            </div>
                        </div>
                        <div class="bio right">
                            <div>
                                <label>{{ t("Health State") }}</label>
                                <textarea class="health" v-model="bio.health_state"></textarea>
                            </div>
                            <div>
                                <label>{{ t("Style") }}</label>
                                <textarea class="style" v-model="bio.style"></textarea>
                            </div>
                        </div>
                    </div>
                    <div v-if="currentTab === 'prefs'">
                        <div class="prefs left">
                            <div>
                                <label>{{ t("Language") }}</label>
                                <select v-model="prefs.lang">
                                    <option value="fr_FR">{{ t("French") }}</option>
                                    <option value="en_EN">{{ t("English") }}</option>
                                </select>
                            </div>
                            <!--div>
                                <label>Automatic dark/Light Mode</label>
                                <label class="switch disabled">
                                    <input type="checkbox" v-model="prefs.darklight" true-value="dark"
                                        false-value="light">
                                    <span class="slider round"></span>
                                </label>
                            </div-->
                            <div>
                                <label>{{ t("Locale") }}</label><input type="text" v-model="prefs.locale" disabled>
                            </div>
                            <div>
                                <label>{{ t("Idle threshold (n. of seconds before the user is considered idle)") }}"</label><input
                                    type="number" v-model="prefs.idle_threshold" min="60" max="6000" step="100">
                            </div>
                        </div>
                    </div>
                    <div v-if="currentTab === 'ai'">
                        <div class="ai left">
                            <div>
                                <label>{{ t("Provider") }}</label>
                                <select v-model="ai.provider">
                                    <option value="groq">Groq</option>
                                    <!--option value="openai">OpenAI</option-->
                                </select>
                            </div>
                            <div>
                                <label>{{ t("API Key") }}</label><input type="password" v-model="ai.api_key">
                                <p>{{ t("Groq is our default provider:") }} <br><a class="extlink"
                                        href="https://console.groq.com/login" target="_blank">{{ t("To obtain a FREE api key sign up here") }}</a>
                                    <br><a class="extlink" href="https://groq.com/privacy-policy/" target="_blank">{{ t("Our default provider privacy policy") }}</a>
                                </p>
                            </div>
                            <div>
                                <label>{{ t("Model Name") }}</label>
                                <select v-model="ai.model_name">
                                    <option value="llama-3.3-70b-versatile">Llama 3.3-70B</option>
                                    <option value="openai/gpt-oss-120b">OpenAI OSS-GPT-120B</option>
                                    <option value="openai/gpt-oss-20b">OpenAI OSS-GPT-20B</option>
                                    <option value="meta-llama/llama-4-maverick-17b-128e-instruct">Llama 4-17b-128e (preview)</option>
                                    <option value="meta-llama/llama-4-scout-17b-16e-instruct">Llama 4-17b-16e (preview)</option>
                                </select>
                            </div>
                            <div>
                                <label>{{ t("Temperature") }}</label>
                                <div style="display: flex; align-items: center; gap: 12px;">
                                    <input type="range" v-model.number="ai.temperature" min="0" max="1" step="0.01"
                                        style="flex: 1 1 60%;">
                                    <input type="number" v-model.number="ai.temperature" step="0.1" min="0" max="1"
                                        placeholder="0.2" style="width: 60px;">
                                </div>
                            </div>
                        </div>
                    </div>
                    <div v-if="currentTab === 'plugins'" class="pluginsContainer">
                        <!-- View for Plugin-Specific Settings -->
                        <div v-if="viewingPluginSettings && selectedPluginComponent" class="pct_container">
                            
                            <h3 class="pluginContainerTitle"><a style="cursor: pointer" @click="closePluginSettingsView">{{ t("Plugins") }}</a> > {{ selectedPluginForSettings.title }}</h3>
                            <component :is="selectedPluginComponent" :initial-settings="currentPluginInitialSettings"
                                :plugin-name="selectedPluginForSettings.name" :lang="lang" @save-settings="handlePluginSettingsSave"
                                class="plugin-settings-component"></component>
                            <!-- The save button is now expected to be WITHIN the loaded component -->
                        </div>

                        <!-- View for Plugin Grid -->
                        <div v-else>
                            <!-- Tab Navigation -->
                            <ul class="tabs plugins">
                                <li v-for="category in categories" :key="category"
                                    :class="{ active: activeTab === category }" @click="activeTab = category">
                                    {{ category.toUpperCase() }}
                                </li>
                            </ul>

                            <!-- Plugins Grid for Active Tab -->
                            <div v-if="activeTab" class="plugins-grid">
                                <div v-for="plugin in pluginsByCategory[activeTab]" :key="plugin.name"
                                    class="plugin-card" :class="{ 'core-plugin': plugin.is_core }">
                                    <div class="plugin-header">
                                        <h3 class="plugin-title">
                                            {{ plugin.title }}
                                            <span v-if="plugin.is_core" class="core-badge">{{ t("CORE") }}</span>
                                        </h3>
                                        <div class="plugin-actions">
                                            <label class="switch"><input type="checkbox" :checked="plugin.active"
                                                    :disabled="plugin.is_core"
                                                    @change="togglePlugin(activeTab, plugin.name, $event.target.checked)"><span
                                                    class="slider round"></span></label>
                                            <!-- Settings Icon for non-core plugins -->
                                            <img v-if="!plugin.is_core && plugin.has_settings && plugin.active"
                                                src="/img/icons/src/settings.svg"
                                                class="plugin-settings-icon" alt="Settings" title="{{ t('Configure plugin') }}"
                                                @click="showPluginSettingsView(plugin)">
                                        </div>
                                    </div>
                                    <p class="plugin-description">{{ plugin.description || t('No description available') }}</p>
                                    <div class="plugin-requirements">
                                        <span v-if="plugin.is_core" class="requirement core">
                                            🔒 {{ t("Core Plugin") }}
                                        </span>
                                        <span v-if="plugin.requires_internet" class="requirement">
                                            🌐 {{ t("Requires Internet") }}
                                        </span>
                                        <span v-if="plugin.requires_subscription" class="requirement">
                                            ⭐ {{ t("Requires Subscription") }}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div v-if="currentTab === 'about'">
                        <div class="about about-tab left">
                            <p>{{ t("Concept by Igor Novitzki") }}</p>
                            <p>{{ t("© 2025 Developed by") }} <a href="https://igoor.org/?utm_source=igoor_app"
                                    target="_blank">IGOOR</a>, {{ t("in partnership with") }} <a href="https://www.arsla.org/?utm_source=igoor_app" target="_blank">ARSLA</a>
                            </p>
                            <br>
                            <p>{{ t('If you find this software useful, please consider donating to the not-for-profit organization IGOOR') }}</p>
                            <br>
                                🎁 <a :href="donationLink" target="_blank">{{ t("Make a donation") }}</a>
                        </div>
                    </div>
                </div>
                <div class="save-section" v-if="currentTab !== 'plugins' || !viewingPluginSettings">
                    <button @click="saveSettings" :disabled="isSaving" :class="isSaving ? 'isSaving' : ''">
                        {{ isSaving ? t('Saving...') : t('Save main settings') }}
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
            activeTab: '', // For plugin categories
            pluginData: {},
            currentTab: 'bio', // For main tabs (bio, prefs, ai, plugins, about)
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
            showRestartAlert: false,
            selectedPluginForSettings: null, // Holds the plugin object whose settings are being viewed/edited
            selectedPluginComponent: null,   // Holds the dynamically loaded settings component for a plugin
            currentPluginInitialSettings: {}, // Holds initial settings to pass as prop
            viewingPluginSettings: false     // Controls visibility of plugin-specific settings view
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
            console.log("Filtered plugins by category:", filtered);
            return filtered;
        },
        donationLink() {
            return this.t('https://igoor.org/en/donate/');
        }
    },
    watch: {
        'prefs.lang'(newLang, oldLang) {
            // Only update locale if lang is set and not empty
            if (newLang) {
                this.prefs.locale = `${newLang}.UTF-8`;
            }
            // Show restart alert if language has changed and it's not the initial set
            if (oldLang && newLang !== oldLang) {
                this.showRestartAlert = true;
                setTimeout(() => {
                    this.showRestartAlert = false;
                }, 4000);
            }
        }
    },
    methods: {
        toggleModal() {
            this.showModal = !this.showModal;
            window.pywebview.api.onboarding_toggled(this.showModal);
        },
        closeModal() {
            this.showModal = false
        },
        async saveSettings() { // This is for main settings (bio, prefs, ai)
            console.log("Saving main settings...");
            this.isSaving = true;
            this.saveStatus = null;

            try {
                const dataToSend = {
                    bio: this.bio,
                    prefs: this.prefs,
                    ai: this.ai
                };
                await this.sendMsgToBackend({ // Or your specific API call
                    action: 'save_settings', // Or a more specific action
                    data: dataToSend
                });
            } catch (error) {
                console.error('Error saving main settings:', error);
                this.isSaving = false;
                this.saveStatus = {
                    type: 'error',
                    message: this.t('Failed to save main settings. Please try again.')
                };
            }
        },
        handleIncomingMessage(event) {
            console.log("Custom message handler in ONBOARDING component:", event.data);
            try {
                const data = JSON.parse(event.data);
                if (data.type && data.type == "error"){
                    this.saveStatus = {
                        type: 'error',
                        message: this.t(data.error_type) + " : " + this.t(data.missing_field) + " (" + this.t(data.category) + ")"
                    };
                }
                if (data.type && data.type == "success"){
                    this.isSaving = false;
                    this.saveStatus = {
                        type: 'success',
                        message: this.t('Main settings saved!')
                    };
                    setTimeout(() => {
                        this.closeModal();
                        this.saveStatus = null;
                    }, 3000);
                }
                if (data.action && data.action == "show_modal"){
                    console.warn("ONBOARDING FORCED");
                    this.showModal = true;
                }
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
        // Note: Removed the duplicate saveSettings method. The one above is more complete.
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
        showPluginSettingsView(plugin) {
            this.selectedPluginForSettings = plugin;
            this.viewingPluginSettings = true;
            this.loadPluginComponent(plugin.name);
        },
        closePluginSettingsView() {
            this.viewingPluginSettings = false;
            this.selectedPluginComponent = null;
            this.selectedPluginForSettings = null;
            this.currentPluginInitialSettings = {};
        },
        async loadPluginComponent(pluginName) {
            this.selectedPluginComponent = null; // Clear previous one
            this.currentPluginInitialSettings = {};
            try {
                console.log(`Attempting to load settings component: /plugins/${pluginName}/frontend/${pluginName}_settings.vue`);
                // Ensure the path is correct for dynamic imports.
                const componentModule = await import(/* @vite-ignore */ `/plugins/${pluginName}/frontend/${pluginName}_settings.vue`);

                const settings = await window.pywebview.api.get_current_plugin_settings(pluginName);
                console.log(`Settings for ${pluginName}:`, settings);

                this.currentPluginInitialSettings = settings || {};
                this.selectedPluginComponent = componentModule.default || componentModule;

            } catch (error) {
                console.error(`Failed to load component or settings for plugin: ${pluginName}`, error);
                this.selectedPluginComponent = null;
                // Optionally, show a message to the user that settings UI couldn't be loaded
                alert(`Could not load settings UI for ${pluginName}. It might not have custom settings or an error occurred.`);
                this.closePluginSettingsView(); // Go back if loading fails
            }
        },
        // Inside onboarding_component.vue methods
        async handlePluginSettingsSave(pluginNameFromEmit, settingsData) { // Expects two arguments
            if (!pluginNameFromEmit) {
                console.error("Plugin name was not emitted from the settings component.");
                // Fallback or error handling if pluginNameFromEmit is missing
                // You could try using this.selectedPluginForSettings.name as a fallback,
                // but it's better if the child component provides it.
                if (!this.selectedPluginForSettings || !this.selectedPluginForSettings.name) {
                    console.error("No plugin selected or plugin name missing for saving settings.");
                    this.saveStatus = { type: 'error', message: `Error: Plugin identifier missing.` };
                    return;
                }
                // pluginNameFromEmit = this.selectedPluginForSettings.name; // Example fallback
                // For now, let's strictly expect it from emit:
                this.saveStatus = { type: 'error', message: `Error: Plugin identifier missing from component.` };
                return;
            }

            console.log(`Saving settings for ${pluginNameFromEmit}:`, settingsData);
            this.isSaving = true;
            this.saveStatus = null;

            try {
                await window.pywebview.api.save_plugin_settings(pluginNameFromEmit, settingsData);
                this.saveStatus = { type: 'success', message: `${pluginNameFromEmit} settings saved!` };
            } catch (error) {
                console.error(`Error saving settings for plugin ${pluginNameFromEmit}:`, error);
                this.saveStatus = { type: 'error', message: `Failed to save ${pluginNameFromEmit} settings.` };
            } finally {
                this.isSaving = false;
                setTimeout(() => {
                    if (this.saveStatus.type === 'success') {
                        this.showModal = false
                    }
                    this.saveStatus = null;
                }, 3000);
            }
        }
    }
}
</script>
<style>

.pluginsContainer{
    /* border:1px solid #0ff; */
    width: 100vw;
}
.pct_container{
    /* border: 1px solid #f00; */
}
.about-tab {
    background: #000;
    font-size: 1.2rem;

    a {
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

.onboarding.plugin textarea {
    font-size: 1rem;
}

.onboarding.plugin textarea.health {
    height: 30vh !important;
}

.onboarding.plugin textarea.style {
    height: 10vh !important;
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

input[type="range"]{
    max-width: 400px !important;
    border: 1px solid #f00 !important;
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
    filter: invert(100%);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 6px;
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
    padding: 0 20px;
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
    text-align: left;
}


.plugin-title {
    margin: 0;
    font-size: 1.1em;
    font-weight: 600;
    max-width: 80%;
}

.plugin-description {
    color: #fff;
    text-align: left;
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

/* PLUGIN SETTINGS */
.plugin-actions {
    display: flex;
    align-items: center;
    gap: 10px;
    /* Space between toggle and settings icon */
}

.plugin-settings-icon {
    cursor: pointer;
    filter: invert(100%);
    /* If your icons are dark and background is dark, or vice-versa */
    opacity: 0.7;
    padding: 6px;
    width: 36px;
    margin-top: 10px;
}

.plugin-settings-icon:hover {
    opacity: 1;
}

.back-to-plugins-button {
    margin-bottom: 15px;
    padding: 8px 15px;
    background-color: #f0f0f0;
    border: 1px solid #ccc;
    border-radius: 4px;
    cursor: pointer;
    color: #333;
}

.back-to-plugins-button:hover {
    background-color: #e0e0e0;
}

.plugin-settings-component {
    /* padding: 15px; */
    border: 1px solid #eee;
    border-radius: 5px;
    /* margin-top: 10px; */
    background-color: #0d1117;
    /* Or your preferred background for settings */
}

/* Ensure the save button for main settings is hidden when viewing plugin settings */
.save-section {
    margin-top: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
}

a.extlink {
    color: #fff;
}

.isSaving{
    cursor: wait !important;
    background: #f00;
}
</style>