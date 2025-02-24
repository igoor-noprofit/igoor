<template>
    <div class="onboarding plugin" v-show="appview == 'onboarding'">
        <div>
            <ul class="tabs">
                <li :class="{ active: currentTab === 'bio' }" @click="currentTab = 'bio'">Bio</li>
                <li :class="{ active: currentTab === 'prefs' }" @click="currentTab = 'prefs'">Preferences</li>
                <li :class="{ active: currentTab === 'ai' }" @click="currentTab = 'ai'">AI</li>
                <li :class="{ active: currentTab === 'plugins' }" @click="currentTab = 'plugins'">Plugins</li>
            </ul>
            <div v-if="currentTab === 'bio'" class="bio-container">
                <div class="bio-left">
                    <div>
                        <label>Name</label><input type="text" v-model="bio.name">
                    </div>
                    <div>
                        <label>Pronoun</label><input type="text" v-model="bio.pronoun">
                    </div>
                    <div>
                        <label>Birth Date</label><input type="text" v-model="bio.birth_date">
                    </div>
                </div>
                <div class="bio-right">
                    <div>
                        <label>Health State</label>
                        <textarea v-model="bio.health_state"></textarea>
                    </div>
                </div>
            </div>
            <div v-if="currentTab === 'prefs'">
                <div>
                    <label>Language</label>
                    <select v-model="prefs.lang">
                        <option value="fr_FR">Français</option>
                        <option value="en_EN">English</option>
                    </select>
                </div>
                <div>
                    <label>Automatic dark/Light Mode</label>
                    <label class="switch">
                        <input type="checkbox" v-model="prefs.darklight" true-value="dark" false-value="light">
                        <span class="slider round"></span>
                    </label>
                </div>
                <div>
                    <label>Locale</label><input type="text" v-model="prefs.locale">
                </div>
            </div>
            <div v-if="currentTab === 'ai'">
                <div>
                    <label>Provider</label>
                    <select v-model="ai.provider">
                        <option value="groq">Groq</option>
                        <option value="openai">OpenAI</option>
                    </select>
                </div>
                <div>
                    <label>API Key</label><input type="text" v-model="ai.api_key">
                    <p>Groq is our default provider. <a href="https://console.groq.com/login" target="_blank">To obtain a FREE api key sign up here</a>

                        <a href="https://groq.com/privacy-policy/">Our default provider privacy policy</a>
                    </p>
                </div>
                <div>
                    <label>Model Name</label><input type="text" v-model="ai.model_name">
                </div>
                <div>
                    <label>Temperature</label><input type="text" v-model="ai.temperature">
                </div>
            </div>
            <div v-if="currentTab === 'plugins'">
                <!-- Add plugin-specific fields here -->
                <p>Plugins settings will go here.</p>
            </div>
        </div>
        <button @click="saveSettings">Save</button>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "onboarding",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
            currentTab: 'bio',
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
            }
        };
    },
    methods: {
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
        }
    }
};
</script>
<style>
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
    justify-content: space-evenly;
}

.bio-left, .bio-right {
    width: 48%;
}

.bio-left div, .bio-right div {
    margin-bottom: 10px;
}
</style>