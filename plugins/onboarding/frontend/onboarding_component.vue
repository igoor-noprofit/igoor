<template>
    <div>
        <!-- Settings Gear Icon -->
        <div @click="toggleModal" class="settings-gear">
            <img src="/img/icons/src/settings.svg" width="30">
        </div>
        <!-- Modal Window for Plugin Settings -->
        <div v-if="showModal" class="modal-overlay" :class="isSaving ? 'isSaving' : ''" id="onboarding-modal">
            <div class="modal-content settings container onboarding plugin">
                <!-- Restart Alert -->
                <div v-if="showRestartAlert" class="restart-alert">
                    {{ t("Please restart the app for changes to take effect.") }}
                </div>
                <div class="tabsandpluginscontainer">
                    <ul class="tabs">
                        <li :class="{ active: currentTab === 'home' }"
                            @click="currentTab = 'home'; viewingPluginSettings = false;">{{ t("Home") }}</li>
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

                    <!-- Home Dashboard -->
                    <div v-if="currentTab === 'home'" class="dashboard-container">
                        <div class="dashboard-grid">
                            <div v-for="categoryItem in dashboardCategories" :key="categoryItem.category"
                                 class="dashboard-card">
                                <span class="card-icon">{{ categoryItem.category === 'Context' ? '🧠' :
                                         categoryItem.category === 'Predictions' ? '🔮' :
                                         categoryItem.category === 'Speech Recognition' ? '🎤' :
                                         categoryItem.category === 'Vocal Synthesis' ? '🔊' : '⚙️' }}</span>
                                <span class="card-label">{{ t(categoryItem.category) }}</span>
                                <div class="card-sub-shortcuts">
                                    <button v-for="shortcut in categoryItem.shortcuts" :key="shortcut.plugin"
                                            class="shortcut-item"
                                            @click="showPluginSettingsView(findPlugin(shortcut.plugin))">
                                        <span class="shortcut-icon">{{ shortcut.icon }}</span>
                                        <span class="shortcut-label">{{ t(shortcut.label) }}</span>
                                    </button>
                                </div>
                            </div>
                            <div class="dashboard-card">
                                <span class="card-icon">📖</span>
                                <span class="card-label">{{ t("Help") }}</span>
                                <div class="card-sub-shortcuts">
                                    <button class="shortcut-item" @click="openDocumentation()">
                                        <span class="shortcut-icon">ℹ️</span>
                                        <span class="shortcut-label">{{ t("View Documentation") }}</span>
                                    </button>
                                </div>
                            </div>
                            
                        </div>
                    </div>

                    <div v-if="currentTab === 'bio'" class="bio-container">
                        <div class="bio left">
                            <div>
                                <label>{{ t("Name") }}</label><input type="text" v-model="bio.name">
                            </div>
                            <!--div>
                                <label>{{ t("Pronoun") }}</label><input type="text" v-model="bio.pronoun">
                            </div>
                            <div>
                                <label>{{ t("Year of birth") }}</label><input type="text" v-model="bio.birth_date">
                            </div-->
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
                        <div class="ai-container">
                            <div class="ai left">
                                <div>
                                    <label>{{ t("Provider") }}</label>
                                    <select v-model="ai.provider">
                                        <option value="groq">Groq</option>
                                        <!--option value="openai">OpenAI</option-->
                                    </select>
                                </div>
                                <div>
                                    <label>{{ t("API Key") }}</label>
                                    <div style="display: flex; align-items: center; gap: 8px;">
                                        <input
                                            type="password"
                                            v-model="ai.api_key"
                                            :class="{'input-error': apiKeyError, 'input-success': apiKeyValid}"
                                            :disabled="isValidating"
                                        />
                                        <span v-if="isValidating">{{ t('Validating...') }}</span>
                                        <span v-if="apiKeyValid" class="valid-icon">✓</span>
                                    </div>
                                    <p v-if="apiKeyError" class="error-message">{{ apiKeyErrorMessage }}</p>
                                    <p>{{ t("Groq is our default provider:") }} <br><a class="extlink"
                                            href="https://console.groq.com/login" target="_blank">{{ t("To obtain a FREE api key sign up here") }}</a>
                                        <br><a class="extlink" href="https://groq.com/privacy-policy/" target="_blank">{{ t("Our default provider privacy policy") }}</a>
                                    </p>
                                </div>
                            </div>
                            <div class="ai right">
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
                                <div v-if="supportsReasoning">
                                    <label>{{ t("Reasoning effort") }}</label>
                                    <select v-model="ai.reasoning_effort">
                                        <option value="low">{{ t("Low") }}</option>
                                        <option value="medium">{{ t("Medium") }}</option>
                                        <option value="high">{{ t("High") }}</option>
                                    </select>
                                    <p>{{ t("Higher reasoning means slower, more expensive, but usually more intelligent responses.") }}</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Plugin-Specific Settings View (replaces tab content when viewing) -->
                    <div v-if="viewingPluginSettings && selectedPluginComponent" class="pct_container">
                        <h3 class="pluginContainerTitle">
                            <a @click="goToHome" class="breadcrumb-home">{{ t("Home") }}</a> > <a @click="backToPlugins" class="breadcrumb-plugins">{{ t("Plugins") }}</a> > {{ selectedPluginForSettings.title }}
                        </h3>
                        <component ref="pluginSettingsComponent" :is="selectedPluginComponent" :initial-settings="currentPluginInitialSettings"
                            :plugin-name="selectedPluginForSettings.name" :lang="lang" :onboarding-open="showModal"
                            @save-settings="handlePluginSettingsSave" class="plugin-settings-component"></component>
                    </div>

                    <div v-if="currentTab === 'plugins' && !viewingPluginSettings" class="pluginsContainer">
                        <!-- View for Plugin Grid -->
                        <div>
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
                                                class="plugin-settings-icon" alt="Settings" :title="t('Configure plugin')"
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
                            <p>{{ t("© 2025-2026 Developed by") }} <a href="https://igoor.org/?utm_source=igoor_app"
                                    target="_blank">IGOOR</a>, {{ t("in partnership with") }} <a href="https://www.arsla.org/?utm_source=igoor_app" target="_blank">ARSLA</a>
                            </p>
                            <br>
                            <p>{{ t('If you find this software useful, please consider donating to the not-for-profit organization IGOOR') }}</p>
                            <br>
                                🎁 <a :href="donationLink" target="_blank">{{ t("Make a donation") }}</a>
                        </div>
                    </div>
                </div>
                <div class="save-section" v-if="!viewingPluginSettings">
                    <button @click="saveSettings" :disabled="isSaving" :class="isSaving ? 'isSaving' : ''">
                        {{ isSaving ? t('Saving...') : t('Save main settings') }}
                    </button>
                    <span v-if="saveStatus" :class="['save-status', saveStatus.type]">
                        {{ saveStatus.message }}
                    </span>
                </div>
            </div>
        </div>

        <!-- Unsaved Changes Confirmation Modal -->
        <div v-if="showUnsavedChangesModal" class="unsaved-changes-modal-overlay">
            <div class="unsaved-changes-modal-content">
                <h3>{{ t("Unsaved Changes") }}</h3>
                <p>{{ t("You have unsaved changes. Do you want to save them?") }}</p>
                <div class="modal-actions">
                    <button class="btn btn-secondary" @click="confirmSaveBeforeNavigation(false)">
                        {{ t("Cancel") }}
                    </button>
                    <button class="btn btn-primary" @click="confirmSaveBeforeNavigation(true)">
                        {{ t("Save") }}
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
import { ensureBackendApi } from '/js/ensureBackendApi.js';

export default {
    name: "onboarding",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
            activeTab: 'core', // Initialize with a default category to prevent empty state
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
                temperature: "",
                reasoning_effort: ""
            },
            isSaving: false,
            saveStatus: null,
            pywebviewready: false,
            showRestartAlert: false,
            selectedPluginForSettings: null, // Holds the plugin object whose settings are being viewed/edited
            selectedPluginComponent: null,   // Holds the dynamically loaded settings component for a plugin
            currentPluginInitialSettings: {}, // Holds initial settings to pass as prop
            viewingPluginSettings: false,     // Controls visibility of plugin-specific settings view
            showUnsavedChangesModal: false,  // Controls visibility of unsaved changes confirmation modal
            pendingNavigation: null,            // Stores the pending navigation action to execute after confirmation
            // API key validation properties
            apiKeyError: false,
            apiKeyErrorMessage: '',
            apiKeyValid: false,
            validationDebounce: null,
            isValidating: false,
            dashboardShortcuts: {
                "Predictions": [
                    { label: "Daily needs", plugin: "daily", icon: "🛀" },
                    { label: "Quick Access Buttons", plugin: "shortcuts", icon: "🆘" },
                ],
                "Context": [
                    { label: "Add/delete documents", plugin: "rag", icon: "📁" },
                     { label: "Weather", plugin: "meteo", icon: "🌡️" }
                ],
                "Speech Recognition": [
                    { label: "Whisper", plugin: "asrwhisper", icon: "" },
                    { label: "Local", plugin: "asrvosk", icon: "" },
                    { label: "Cloud", plugin: "asrjs", icon: "☁️" }
                ],
                "Vocal Synthesis": [
                    { label: "ElevenLabs", plugin: "elevenlabstts", icon: "" },
                    { label: "Speechify", plugin: "speechifytts", icon: "" },
                    { label: "Windows Voice", plugin: "ttsdefault", icon: "" }
                ]
            }
        }
    },
    async mounted() {
        // Wait for backend API or pywebview bridge
        const api = await ensureBackendApi();
        if (api.isBridgeAvailable) {
            await api.waitUntilReady();
        }
        this.pywebviewready = true;
        await this.loadPlugins();

        // If the backend already sent settings before the socket was ready,
        // fetch them via REST to populate the form immediately.
        try {
            const settings = await api.getPluginSettings("onboarding");
            if (settings) {
                if (settings.bio) this.bio = { ...this.bio, ...settings.bio };
                if (settings.prefs) this.prefs = { ...this.prefs, ...settings.prefs };
                if (settings.ai) this.ai = { ...this.ai, ...settings.ai };
            }
        } catch (error) {
            console.error("Failed to load onboarding settings via REST", error);
        }
    },
    async onGlobalSettingsUpdated() {
        // Called when global settings are updated
        console.log("Onboarding frontend: global settings updated, reloading settings from disk");
        try {
            const api = await ensureBackendApi();
            const settings = await api.getPluginSettings("onboarding");
            if (settings) {
                if (settings.bio) this.bio = { ...this.bio, ...settings.bio };
                if (settings.prefs) this.prefs = { ...this.prefs, ...settings.prefs };
                if (settings.ai) this.ai = { ...this.ai, ...settings.ai };
            }
            // Reload plugins list to get updated activation states
            await this.loadPlugins();
        } catch (error) {
            console.error("Failed to reload onboarding settings after global update", error);
        }
    },
    computed: {
        categories() {
            return Object.keys(this.pluginData)
        },
        supportsReasoning() {
            return ["openai/gpt-oss-120b", "openai/gpt-oss-20b"].includes(this.ai.model_name);
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
            // Remove the console.log to prevent excessive logging that can cause performance issues
            return filtered;
        },
        donationLink() {
            return this.t('https://igoor.org/en/donate/');
        },
        isOnboardingComplete() {
            const required = [
                this.bio.name,
                this.bio.health_state,
                this.ai.api_key,
                this.ai.model_name,
                this.ai.provider,
                this.prefs.lang
            ];
            return required.every(v => v && v.toString().trim() !== '');
        },
        filteredDashboardShortcuts() {
            const result = {};
            for (const [category, shortcuts] of Object.entries(this.dashboardShortcuts)) {
                result[category] = shortcuts.filter(shortcut => {
                    const plugin = this.findPlugin(shortcut.plugin);
                    return plugin && plugin.active && plugin.has_settings;
                });
            }
            return result;
        },
        dashboardCategories() {
            return Object.entries(this.filteredDashboardShortcuts)
                .filter(([_, shortcuts]) => shortcuts.length > 0)
                .map(([category, shortcuts]) => ({ category, shortcuts }));
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
        },
        'ai.api_key'(newValue) {
            // Debounce API key validation
            if (this.validationDebounce) {
                clearTimeout(this.validationDebounce);
            }
            if (newValue && newValue.trim()) {
                this.validationDebounce = setTimeout(() => {
                    this.validateApiKey(newValue);
                }, 500);
            } else {
                this.apiKeyError = false;
                this.apiKeyErrorMessage = '';
                this.apiKeyValid = false;
            }
        },
        'ai.model_name'(newModel) {
            // Re-validate API key when model changes
            if (this.ai.api_key && this.ai.api_key.trim()) {
                this.validateApiKey(this.ai.api_key);
            }
        }
    },
    methods: {
        async validateApiKey(apiKey) {
            if (!apiKey || !apiKey.trim() || !this.ai.model_name) {
                this.apiKeyError = false;
                this.apiKeyErrorMessage = '';
                return;
            }

            this.isValidating = true;

            try {
                const response = await fetch(
                    `/api/plugins/onboarding/validate_api_key?provider=${encodeURIComponent(this.ai.provider || 'groq')}&api_key=${encodeURIComponent(apiKey)}&model_name=${encodeURIComponent(this.ai.model_name)}`
                );
                const data = await response.json();

                if (response.ok) {
                    this.apiKeyError = false;
                    this.apiKeyErrorMessage = '';
                    this.apiKeyValid = true;
                } else {
                    this.apiKeyError = true;
                    this.apiKeyErrorMessage = this.t(data.detail) || this.t('Invalid API Key');
                    this.apiKeyValid = false;
                }
            } catch (error) {
                console.error('API key validation error:', error);
                this.apiKeyError = true;
                this.apiKeyErrorMessage = this.t('Could not validate API key');
                this.apiKeyValid = false;
            } finally {
                this.isValidating = false;
            }
        },
        openDocumentation() {
            // Extract language code (e.g., 'fr' from 'fr_FR', 'en' from 'en_EN')
            const langCode = this.prefs.lang ? this.prefs.lang.split('_')[0] : 'en';
            const docUrl = `https://igoor-noprofit.github.io/docs/${langCode}`;
            window.open(docUrl, '_blank');
        },
        findPlugin(pluginName) {
            for (const category of Object.values(this.pluginData)) {
                const found = category.find(p => p.name === pluginName);
                if (found) return found;
            }
            return null;
        },
        async toggleModal() {
            // Only check for unsaved changes when CLOSING the modal (showModal = true -> false)
            // Not when just switching between tabs within the modal
            if (this.showModal && !this.viewingPluginSettings) {
                // Closing modal while viewing main tabs - no unsaved changes to check
                this.showModal = false;
                const backendApi = await ensureBackendApi();
                await backendApi.onboardingToggled(false);
            } else if (this.showModal && this.viewingPluginSettings) {
                // Closing modal while viewing plugin settings - check for unsaved changes
                if (this.hasUnsavedPluginChanges()) {
                    this.showUnsavedChangesModal = true;
                    this.pendingNavigation = 'close-modal';
                    return;
                }
                // No unsaved changes - proceed with closing
                            this.currentTab = 'bio';
                this.showModal = false;
                const backendApi = await ensureBackendApi();
                await backendApi.onboardingToggled(false);
            } else {
                // Opening modal - default to 'home' if onboarding complete
                if (this.isOnboardingComplete) {
                    this.currentTab = 'home';
                }
                this.showModal = true;
                const backendApi = await ensureBackendApi();
                await backendApi.onboardingToggled(true);
            }
        },
        async closeModal() {
            console.log('Closing modal');

            this.showModal = false

            const backendApi = await ensureBackendApi();
            await backendApi.onboardingToggled(false);
        },
        async saveSettings() { // This is for main settings (bio, prefs, ai)
            // Check API key validation before saving
            if (this.apiKeyError) {
                this.saveStatus = {
                    type: 'error',
                    message: this.t('Please fix API key validation errors before saving.')
                };
                return;
            }

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
                // If successful, the handleIncomingMessage will receive the success response
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
            // Only handle messages that are specifically for onboarding
            // This prevents interference with plugin-specific settings components
            if (!event.data || typeof event.data !== 'string') {
                return false; // Let BasePluginComponent handle it
            }

            try {
                const data = JSON.parse(event.data);
                console.log("Onboarding received message:", data);
                // Only process messages that are specifically for onboarding
                /*
                if (data.target !== 'onboarding' && !data.bio && !data.prefs && !data.ai && data.action !== 'show_modal') {
                    return false; // Let BasePluginComponent handle it
                }
                */

                if (data.type && data.type == "error"){
                    // Auto-switch to the tab with the missing field
                    if (data.category) {
                        this.currentTab = data.category;
                    }
                    this.saveStatus = {
                        type: 'error',
                       message: this.t(data.error_type || 'Error') + (data.missing_field ? " : " + this.t(data.missing_field) + " (" + this.t(data.category || '') + ")" : '')
                    };
                    this.isSaving = false;
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
                    }, 1500);
                }
                if (data.action && data.action == "show_modal"){
                    console.warn("ONBOARDING FORCED");
                    this.showModal = true;
                }
                // Handle settings updates (both initial load and global settings update)
                if (data.bio) {
                    this.bio = { ...this.bio, ...data.bio };
                }
                if (data.prefs) {
                    this.prefs = { ...this.prefs, ...data.prefs };
                }
                if (data.ai) {
                    this.ai = { ...this.ai, ...data.ai };
                }
                // Reload plugins list when settings are updated
                if (data.bio || data.prefs || data.ai) {
                    this.loadPlugins();
                }
                return true; // Message was handled
            } catch (e) {
                console.warn("Error parsing JSON in onboarding:", e);
                return false;
            }
        },
        // Note: Removed the duplicate saveSettings method. The one above is more complete.
        async loadPlugins() {
            try {
                if (!this.pywebviewready) {
                    console.log("Pywebview not ready, waiting to load plugins...");
                    return;
                }
                const backendApi = await ensureBackendApi();
                const response = await backendApi.getPluginsByCategory();
                // Remove excessive logging to prevent performance issues
                this.pluginData = response;
                // Only set activeTab if it's still the initial value and categories are available
                if (this.activeTab === 'core' && this.categories.length > 0 && !this.categories.includes('core')) {
                    this.activeTab = this.categories[0];
                }
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
                const backendApi = await window.ensureBackendApi();
                const result = await backendApi.togglePlugin(pluginName, isActive);
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
        goToHome() {
            // Navigate to Home tab
            this.currentTab = 'home';
            this.viewingPluginSettings = false;
        },
        backToPlugins() {
            // Navigate to Plugins tab (close plugin settings view)
            this.currentTab = 'plugins';
            this.viewingPluginSettings = false;
        },
        showPluginSettingsView(plugin) {
            this.selectedPluginForSettings = plugin;
            this.viewingPluginSettings = true;
            // Switch to plugins tab when viewing from Home or other non-plugins tabs
            if (this.currentTab !== 'plugins') {
                this.currentTab = 'plugins';
            }
            this.loadPluginComponent(plugin.name);
        },
        closePluginSettingsView() {
            // Check for unsaved changes before closing
            if (this.hasUnsavedPluginChanges()) {
                this.showUnsavedChangesModal = true;
                this.pendingNavigation = 'back-to-plugins';
                return;
            }
            this.viewingPluginSettings = false;
            this.selectedPluginComponent = null;
            this.selectedPluginForSettings = null;
        },
        async loadPluginComponent(pluginName) {
            this.selectedPluginComponent = null; // Clear previous one
            try {
                console.log(`Attempting to load settings component: /plugins/${pluginName}/frontend/${pluginName}_settings.vue`);
                // Ensure the path is correct for dynamic imports.
                const componentModule = await import(/* @vite-ignore */ `/plugins/${pluginName}/frontend/${pluginName}_settings.vue`);

                const backendApi = await window.ensureBackendApi();
                const settings = await backendApi.getCurrentPluginSettings(pluginName);
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
                const backendApi = await window.ensureBackendApi();
                await backendApi.savePluginSettings(pluginNameFromEmit, settingsData);
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
        },
        hasUnsavedPluginChanges() {
            // Check if the currently loaded plugin settings component has unsaved changes
            // The component has a hasUnsavedChanges computed property from BasePluginComponent
            // We need to access it via the component's ref
            if (!this.viewingPluginSettings || !this.$refs.pluginSettingsComponent) {
                return false;
            }
            return this.$refs.pluginSettingsComponent.hasUnsavedChanges;
        },
        async confirmSaveBeforeNavigation(saveChanges) {
            // Handle the user's choice in the unsaved changes modal
            if (saveChanges) {
                // Save the plugin settings first
                try {
                    // Call the child component's save method (each plugin might name it differently)
                    // Try common method names
                    const comp = this.$refs.pluginSettingsComponent;
                    if (comp) {
                        if (typeof comp.checkBeforeUpdating === 'function') {
                            await comp.checkBeforeUpdating();
                        } else if (typeof comp.saveSettings === 'function') {
                            await comp.saveSettings();
                        }
                    }
                    // Wait a bit for save to complete
                    await new Promise(resolve => setTimeout(resolve, 1000));
                } catch (error) {
                    console.error('Error saving before navigation:', error);
                    this.saveStatus = { type: 'error', message: this.t('Failed to save changes.') };
                    return; // Don't proceed if save failed
                }
            }

            // Execute the pending navigation
            this.showUnsavedChangesModal = false;

            if (this.pendingNavigation === 'close-modal') {
                this.showModal = false;
                const backendApi = await ensureBackendApi();
                await backendApi.onboardingToggled(false);
            } else if (this.pendingNavigation === 'back-to-plugins') {
                this.viewingPluginSettings = false;
                this.selectedPluginComponent = null;
                this.selectedPluginForSettings = null;
            }

            this.pendingNavigation = null;
        }
    },
    beforeDestroy() {
        if (this.validationDebounce) {
            clearTimeout(this.validationDebounce);
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
    padding: 30px;
}

.about-tab a {
    color: #fff;
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

.ai-container {
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

.input-error {
    border-color: #ff6666 !important;
    background: #2a1818 !important;
}

.input-success {
    border-color: #3ca23c !important;
}

.valid-icon {
    color: #3ca23c;
    font-size: 1.2em;
    font-weight: bold;
    margin-left: 8px;
}

.error-message {
    color: #ff6666;
    margin: 5px 0 0 0;
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

.breadcrumb-home {
    cursor: pointer;
    color: var(--basecolor-accent-500);
    text-decoration: none;
    transition: color 0.2s ease;
}

.breadcrumb-home:hover {
    color: var(--basecolor-accent-300);
    text-decoration: underline;
}

.breadcrumb-plugins {
    cursor: pointer;
    color: var(--basecolor-accent-500);
    text-decoration: none;
    transition: color 0.2s ease;
}

.breadcrumb-plugins:hover {
    color: var(--basecolor-accent-300);
    text-decoration: underline;
}

.isSaving{
    cursor: wait !important;
    background: #f00;
}

/* Unsaved Changes Modal */
.unsaved-changes-modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
}

.unsaved-changes-modal-content {
    background: #fff;
    color: #000;
    padding: 30px;
    border-radius: 8px;
    max-width: 400px;
    width: 90%;
    text-align: center;
}

.unsaved-changes-modal-content h3 {
    margin-top: 0;
    margin-bottom: 15px;
    color: #333;
}

.unsaved-changes-modal-content p {
    margin-bottom: 25px;
    color: #666;
    line-height: 1.5;
}

.unsaved-changes-modal-content .modal-actions {
    display: flex;
    gap: 15px;
    justify-content: center;
}

.unsaved-changes-modal-content .btn {
    padding: 10px 24px;
    font-size: 1rem;
    border-radius: 4px;
    border: none;
    cursor: pointer;
    transition: background 0.2s;
    min-width: 100px;
}

.unsaved-changes-modal-content .btn-primary {
    background: #2196F3;
    color: #fff;
}

.unsaved-changes-modal-content .btn-primary:hover {
    background: #1976D2;
}

.unsaved-changes-modal-content .btn-secondary {
    background: #e0e0e0;
    color: #333;
}

.unsaved-changes-modal-content .btn-secondary:hover {
    background: #d0d0d0;
}

/* Dashboard Styles */
.dashboard-container {
    padding: 20px 0;
}

.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 15px;
}

.dashboard-category {
    display: contents;
}

.dashboard-card {
    background: var(--basecolor-darkest);
    border-radius: 12px;
    padding: 25px 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    min-height: 160px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    gap: 15px;
}

/*
.dashboard-card:hover {
    background: #23515b;
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.3);
}
*/

.card-icon {
    font-size: 2rem;
}

.card-label {
    font-size: 1.1rem;
    font-weight: 600;
    color: #ecf0f1;
    text-align: center;
    margin-bottom: 12px;
    text-transform: uppercase;
}

.card-sub-shortcuts {
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: 100%;
    text-align: left;
    padding: 12px 0;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    margin-top: auto;
}

.shortcut-item {
    padding: 10px 12px;
    background: var(--basecolor-accent-700) !important;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.9rem;
    color: #ecf0f1;
    font-weight: 500;
    transition: all 0.2s ease;
    text-align: left;
    border: none;
    width: 100%;
    height: auto !important;
    display: flex;
    align-items: center;
    gap: 10px;
}

.shortcut-item:hover {
    background: rgba(26, 188, 156, 0.4);
    transform: scale(1.01);
}

.shortcut-item:active {
    transform: scale(0.99);
}

.shortcut-icon {
    font-size: 1.2rem;
    flex-shrink: 0;
}

.shortcut-label {
    flex: 1;
}


</style>