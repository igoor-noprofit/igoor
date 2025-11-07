<template>
    <div class="asrvosk-plugin">
        <div v-if="hasError" class="error-banner">
            {{ errorMessage }}
        </div>
        <div v-if="!hasError" class="mic" :class="[status, { 'clickable': !continuous }]" @click="$_handleMicClick">
            <img src="/img/mic.png">
        </div>
        <button v-show="continuous" class="mode-toggle btn btn-small" :class="{ 'active': continuous }"
            @click="$_toggleMode" title="Toggle continuous mode">{{ t('Continuous mode') }}
        </button>
    </div>
</template>
<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "asrwhisper",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
            status: 'loading',
            audio: {},
            continuous: false,
            keyboardShortcut: null
        };
    },
    computed: {
        hasError() {
            return Boolean(this.error);
        },
        errorMessage() {
            if (!this.error) {
                return '';
            }
            return this.error.message || this.t('Microphone access problem. Verify that Windows has access to your microphone, then restart IGOOR.');
        }
    },
    created() {
        this.audio = {
            on: new Audio('/plugins/asrvosk/samples/on.wav'),
            off: new Audio('/plugins/asrvosk/samples/off.wav')
        };
        // Preload all audio files
        Object.values(this.audio).forEach(audio => audio.load());
    },
    mounted() {
        // Add keyboard event listener when component is mounted
        window.addEventListener('keydown', this.$_handleKeyPress);
    },
    beforeDestroy() {
        // Clean up event listener when component is destroyed
        window.removeEventListener('keydown', this.$_handleKeyPress);
    },
    methods: {
        $_handleError(error) {
            this.status = 'error';
            this.error = error;
        },
        $_handleKeyPress(event) {
            console.log("Key pressed:", event.key, "with modifiers:", {
                ctrl: event.ctrlKey,
                alt: event.altKey,
                shift: event.shiftKey,
                meta: event.metaKey
            });
            const pressed = [];
            if (event.ctrlKey) pressed.push("Ctrl");
            if (event.altKey) pressed.push("Alt");
            if (event.shiftKey) pressed.push("Shift");
            if (event.metaKey) pressed.push("Meta");
            if (!["Control", "Shift", "Alt", "Meta"].includes(event.key)) {
                pressed.push(event.key.length === 1 ? event.key.toUpperCase() : event.key);
            }
            const pressedCombo = pressed.join("+");
            if (this.keyboardShortcut && pressedCombo === this.keyboardShortcut) {
                event.preventDefault();
                this.$_handleMicClick();
            }
        },
        /* DOESN'T WORK ON SECOND TOGGLE */
        $_toggleMode() {
            return false;
            /*
            this.continuous = !this.continuous;
            this.sendMsgToBackend({
                action: 'set_continuous_mode',
                continuous: this.continuous
            });
            */
        },
        handleIncomingMessage(event) {
            // Let the base component try to handle it first
            const handled = BasePluginComponent.methods.handleIncomingMessage.call(this, event);
            if (handled) return true;
            console.log(this.$options.name + ' handling message');
            // Handle component-specific messages
            try {
                const data = JSON.parse(event.data);
                if (data.type === "settings") {
                    this.settings = data.settings;
                    console.log('ASRWHISPER SETTINGS:', this.settings);
                    this.continuous = this.settings.continuous || false;
                    if (this.settings.shortcut) {
                        console.log('ASRWHISPER SHORTCUT:', this.settings.shortcut);
                        this.keyboardShortcut = this.settings.shortcut;
                    }
                }
                if (data.status) {
                    this.status = data.status;
                    if (data.status !== 'error') {
                        this.error = false;
                    }
                }
                // Add other specific message handling here
            } catch (e) {
                console.error("Error parsing message:", e);
            }
        },
        $_handleMicClick() {
            // Only handle clicks if not in continuous mode
            if (!this.continuous) {
                if (this.status === 'listening') {
                    this.sendMsgToBackend({ action: 'start_recording' });
                }
                else {
                    if (this.status === 'recording') {
                        this.sendMsgToBackend({ action: 'stop_recording' });
                    }
                    console.warn("No action taken because not in listening or recording mode");
                }
            }
            else {
                console.warn("Cannot click when not in continuous mode");
            }
        }
    },
    watch: {
        status(newStatus, oldStatus) {
            if (this.continuous) {
                if (oldStatus === 'loading' && newStatus === 'listening') {
                    console.log("listening");
                } else if (oldStatus === 'listening' && newStatus === 'recording') {
                    this.audio.on.play();
                }
                else if (oldStatus === 'recording' && newStatus === 'listening') {
                    this.audio.off.play();
                }
            }
            if (newStatus === 'empty') {
                console.warn("Playing OFF sound");
                this.audio.off.play();
                this.status = 'listening'; // Reset to listening after empty
            }
        }
    }
};
</script>
<style>
.asrvosk-plugin {
    flex-direction: column;
}

.mic.clickable {
    cursor: pointer;
    height: 100%;
    vertical-align: middle;
    display: flex;
    justify-content: center;
    align-items: center;
}

.mic img {
    max-height: 50px;
    max-width: 50px;
}

.mode-toggle {
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-top: 5px;
    background: #444;
    transition: all 0.3s ease;
}

.mode-toggle.active {
    background: #2196F3;
    box-shadow: 0 0 10px rgba(33, 150, 243, 0.5);
}

.mode-toggle span {
    font-size: 18px;
    color: white;
}
</style>