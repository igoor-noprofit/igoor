<template>
    <div class="shortcuts shortcuts-plugin" v-show="appview != 'onboarding'" :class="{ 'shrink': shrink }">
        <button class="btn btn-shortcut" @click="$_minimise()">
            <img src="img/minimize.svg">
            <h3 v-show="!shrink">{{ t('Minimize window') }}</h3>
            <h3 v-show="shrink">{{ t('Minimize') }}</h3>
        </button>
        <button
            v-for="(button, index) in shortcutButtons"
            :key="button.key"
            class="btn btn-shortcut"
            :class="{ 'btn-hilite': button.highlight, 'sos-pulsing': button.key === 'help' && isAlertPlaying }"
            @click="$_handleShortcut(button, index)"
        >
            <svg class="icon icon-l">
                <use :xlink:href="'img/svgdefs.svg#' + button.icon"></use>
            </svg>
            <h3>{{ button.label }}</h3>
        </button>
    </div>
</template>
<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
export default {
    name: "shortcuts",
    mixins: [BasePluginComponent],
    data() {
        return {
            websocket: null,  // Store WebSocket instance
            status: 'loading',
            shrink: false,
            isAlertPlaying: false,
            alertTimeout: null,
            alertAudio: null,
            settings: {
                help_mode: 'speak',
                alert_repetitions: 3,
                alert_interval: 15
            }
        };
    },
    computed: {
        paroles() {
            return [
                this.t("I'm on my way, just finishing writing"),
                this.t("Just a moment, I'll finish"),
                this.t("One second and it's done"),
                this.t("Just give me two seconds"),
                this.t("I'm just finishing")
            ];
        },
        shortcutButtons() {
            return [
                {
                    key: 'drink',
                    icon: 'icon-drink',
                    label: this.t('Drink'),
                    msg: this.t("I'm thirsty"),
                    random: false,
                    highlight: false
                },
                {
                    key: 'toilet',
                    icon: 'icon-toilet',
                    label: this.t('Toilet'),
                    msg: this.t('I need to go to the toilet'),
                    random: false,
                    highlight: false
                },
                {
                    key: 'parole',
                    icon: 'icon-talk',
                    label: this.t('Just a sec'),
                    random: true,
                    highlight: false
                },
                {
                    key: 'yes',
                    icon: 'icon-ok',
                    label: this.t('Yes'),
                    msg: this.t('Yes'),
                    random: false,
                    highlight: false
                },
                {
                    key: 'no',
                    icon: 'icon-no',
                    label: this.t('No'),
                    msg: this.t('No'),
                    random: false,
                    highlight: false
                },
                {
                    key: 'thanks',
                    icon: 'icon-thankyou',
                    label: this.t('Thanks'),
                    msg: this.t('Thanks'),
                    random: false,
                    highlight: false
                },
                {
                    key: 'help',
                    icon: 'icon-sos',
                    label: this.t('Help!'),
                    msg: this.t("Please help me, it's urgent!"),
                    random: false,
                    highlight: true
                }
            ];
        }
    },
    methods: {
        $_speak(bid, msg) {
            const json = { action: "speak", msg: msg, bid };
            console.log("sending JSON");
            console.log(json);
            this.sendMsgToBackend(json);
        },
        async loadSettings() {
            try {
                const response = await fetch('/api/plugins/shortcuts/settings');
                if (response.ok) {
                    const data = await response.json();
                    this.settings = {
                        help_mode: data.help_mode || 'speak',
                        alert_repetitions: data.alert_repetitions || 3,
                        alert_interval: data.alert_interval || 15
                    };
                    console.log('Loaded shortcuts settings:', this.settings);
                }
            } catch (error) {
                console.error('Failed to load shortcuts settings:', error);
            }
        },
        $_handleHelp() {
            // Get help mode from component settings
            const helpMode = this.settings.help_mode || 'speak';
            console.log('Help mode:', helpMode);

            // Send help action to backend - backend will handle mode-specific behavior
            this.sendMsgToBackend({
                action: 'help'
            });
        },
        startAlertPlayback(repetitions, interval) {
            this.startAlert(repetitions, interval, false);
        },
        startAlertSpeak(repetitions, interval) {
            this.startAlert(repetitions, interval, true);
        },
        startAlert(repetitions, interval, useSpeak) {
            // Stop any existing alert before starting a new one
            if (this.isAlertPlaying) {
                console.log('Alert already playing, stopping it first');
                this.stopAlertPlayback();
            }

            const mode = useSpeak ? 'speak' : 'sound';
            console.log(`Starting alert ${mode}: ${repetitions} repetitions, ${interval}s interval`);
            this.isAlertPlaying = true;

            let playCount = 0;
            const maxPlays = repetitions === 0 ? Infinity : repetitions;

            const playAlert = () => {
                if (!this.isAlertPlaying) {
                    console.log('Alert stopped, not playing');
                    return;
                }

                try {
                    if (useSpeak) {
                        // Send speak message to backend with translated message
                        const helpButton = this.shortcutButtons.find(b => b.key === 'help');
                        const helpMsg = helpButton ? helpButton.msg : "Please help me, it's urgent!";
                        this.sendMsgToBackend({ action: "speak", msg: helpMsg, bid: 6 });
                        console.log(`Spoke help message ${playCount + 1}/${maxPlays === Infinity ? 'forever' : maxPlays}`);
                    } else {
                        // Play audio
                        this.alertAudio = new Audio('/plugins/shortcuts/alerte.wav');
                        this.alertAudio.play();
                        console.log(`Played alert ${playCount + 1}/${maxPlays === Infinity ? 'forever' : maxPlays}`);
                    }
                    playCount++;

                    // Check if we've reached the limit AFTER incrementing
                    if (playCount >= maxPlays && maxPlays !== Infinity) {
                        console.log('Finished all repetitions, stopping alert');
                        this.stopAlertPlayback();
                        return;
                    }

                    // Schedule next iteration if there are more
                    if (playCount < maxPlays || maxPlays === Infinity) {
                        this.alertTimeout = setTimeout(() => {
                            playAlert();
                        }, interval * 1000);
                    }
                } catch (error) {
                    console.error('Error during alert playback:', error);
                    this.isAlertPlaying = false;
                }
            };

            playAlert();
        },
        stopAlertPlayback() {
            console.log('Stopping alert playback');
            this.isAlertPlaying = false;

            if (this.alertTimeout) {
                clearTimeout(this.alertTimeout);
                this.alertTimeout = null;
            }

            if (this.alertAudio) {
                try {
                    this.alertAudio.pause();
                    this.alertAudio.currentTime = 0;
                } catch (e) {
                    console.warn('Error stopping audio:', e);
                }
                this.alertAudio = null;
            }
        },
        $_minimise() {
            window.ensureBackendApi().then((api) => api.winMinimize());
        },
        $_parole(bid) {
            const randomIndex = Math.floor(Math.random() * this.paroles.length);
            const randomMsg = this.paroles[randomIndex];
            this.$_speak(bid, randomMsg);
        },
        $_handleShortcut(button, index) {
            // Stop alert if clicking any shortcut button while alert is playing
            if (this.isAlertPlaying) {
                this.stopAlertPlayback();

                // If it's the help button itself, don't restart it - just exit
                if (button.key === 'help') {
                    return;
                }

                // Continue to execute other button actions
            }

            if (button.random) {
                this.$_parole(index);
                return;
            }

            // Special handling for help button (only when not stopping an existing loop)
            if (button.key === 'help') {
                this.$_handleHelp();
                return;
            }

            this.$_speak(index, button.msg);
        },
        handleIncomingMessage(event) {
            // Call parent handler first
            BasePluginComponent.methods.handleIncomingMessage.call(this, event);

            try {
                const data = JSON.parse(event.data);
                if (data.action === "shrink") {
                    this.shrink = true;
                }
                if (data.action === "unshrink") {
                    this.shrink = false;
                }
                if (data.action === "play_alert") {
                    this.startAlertPlayback(data.repetitions, data.interval);
                }
                if (data.action === "play_alert_speak") {
                    this.startAlertSpeak(data.repetitions, data.interval);
                }
                if (data.action === "stop_alert") {
                    this.stopAlertPlayback();
                }
            } catch (error) {
                console.warn('Shortcuts plugin received non-JSON message:', event.data);
            }
        }
    },
    watch: {
        isAlertPlaying(newVal, oldVal) {
            console.log('isAlertPlaying changed from', oldVal, 'to', newVal);
        },
        shrink(newVal, oldVal) {
            if (newVal !== oldVal) {
                // Emit to parent Vue app
                this.$emit('footer-shrink', newVal);

                // Try to find parent app instance
                let parent = this.$parent;
                while (parent && parent.footerShrink === undefined) {
                    parent = parent.$parent;
                }
                if (parent && parent.footerShrink !== undefined) {
                    parent.footerShrink = newVal;
                    console.log('Updated parent.footerShrink to:', newVal);
                }

                // Also emit to window/global event bus
                if (window.app && window.app.footerShrink !== undefined) {
                    window.app.footerShrink = newVal;
                    console.log('Updated window.app.footerShrink to:', newVal);
                }

                // Dispatch custom event to DOM
                window.dispatchEvent(new CustomEvent('footer-shrink', { detail: newVal }));

                console.log('Shortcuts shrink changed to:', newVal);
            }
        }
    },
    mounted() {
        // Ensure window.app reference is available
        if (window.app) {
            console.log('Window.app available in shortcuts mounted');
        }
        // Load settings
        this.loadSettings();
        // Listen for settings updates
        window.addEventListener('settings-updated', this.loadSettings);
    },
    beforeDestroy() {
        // Stop any playing alert when component is destroyed
        this.stopAlertPlayback();
        // Remove settings update listener
        window.removeEventListener('settings-updated', this.loadSettings);
    }
};
</script>

<style scoped>
.shortcuts {
    display: flex;
    flex-wrap: nowrap;
    justify-content: space-between;
    gap: 4px;
    padding: 4px;
    width: 100%;
}

.shortcuts.shrink{
    max-height: 70px;
}

.shrink svg.icon, .shrink img {
    display: none;
}

.shrink .btn-shortcut h3 {
    font-size: 1.2em;
    font-weight: bold;
}

.shrink .btn-shortcut:not(.btn-hilite) {
    background: #28373b;
}

.btn-shortcut {
    flex: 1 1 0;
    min-width: 0;
    max-width: none;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 8px 4px;
}

/* Alert animation - pulsing orange/red only on SOS button when alert loop is active */
.btn-shortcut.sos-pulsing {
    animation: pulse-alert 1.5s ease-in-out infinite;
    box-shadow: 0 0 15px rgba(255, 69, 0, 0.8);
}

@keyframes pulse-alert {
    0%, 100% {
        background-color: #ff4500;
        transform: scale(1);
        box-shadow: 0 0 15px rgba(255, 69, 0, 0.8);
    }
    50% {
        background-color: #ff6b35;
        transform: scale(1.08);
        box-shadow: 0 0 20px rgba(255, 107, 53, 0.9);
    }
}

.btn-shortcut .icon,
.btn-shortcut img {
    width: 100%;
    height: auto;
    max-width: 64px;
    max-height: 64px;
    object-fit: contain;
}

.btn-shortcut h3 {
    margin: 4px 0 0 0;
    /* Slightly increased top margin */
    font-size: 0.8em;
    white-space: nowrap;
}
</style>