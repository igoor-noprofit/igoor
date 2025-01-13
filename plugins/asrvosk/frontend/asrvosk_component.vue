<template>
    <div class="asrvosk-plugin">
        <div class="mic" :class="status" @click="$_handleMicClick">
            <img src="/img/mic.png">
        </div>
        <button class="mode-toggle btn btn-small" 
            :class="{ 'active': continuous }" 
            @click="$_toggleMode"
            title="Toggle continuous mode">EN CONTINU
        </button>
    </div>
</template>
<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "asrvosk",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
            status: 'loading',
            audio: {},
            continuous: false
        };
    },
    created() {
        this.audio = {
            on: new Audio('/plugins/asrvosk/samples/on.wav'),
            off: new Audio('/plugins/asrvosk/samples/off.wav')
        };
        // Preload all audio files
        Object.values(this.audio).forEach(audio => audio.load());
    },
    methods: {
        $_toggleMode() {
            this.continuous = !this.continuous;
            this.sendMsgToBackend({
                action: 'set_continuous_mode',
                continuous: this.continuous
            });
        },
        handleIncomingMessage(event) {
            // Let the base component try to handle it first
            const handled = BasePluginComponent.methods.handleIncomingMessage.call(this, event);
            if (handled) return;

            // Handle component-specific messages
            try {
                const data = JSON.parse(event.data);
                if (data.type === "settings") {
                    this.settings = data.settings;
                    console.log('ASRVOSK SETTINGS:', this.settings);
                    this.continuous = this.settings.continuous || false;
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
                    this.sendMsgToBackend({action:'start_recording'});
                }
            }
        }
    },
    watch: {
        status(newStatus, oldStatus) {
            if (oldStatus === 'loading' && newStatus === 'listening') {
                console.log("listening");
            } else if (oldStatus === 'listening' && newStatus === 'recording') {
                this.audio.on.play();
            }
            else if (oldStatus === 'recording' && newStatus === 'listening') {
                this.audio.off.play();
            }
        }
    }
};
</script>
<style>
.asrvosk-plugin{
    flex-direction: column;
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