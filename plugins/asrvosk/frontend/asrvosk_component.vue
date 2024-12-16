<template>
    <div class="asrvosk-plugin">
        <div class="mic" :class="status">
            <img src="/img/mic.png">
        </div>
        <!--img v-if="status == 'listening'" src="/img/listening.gif" id="listening"-->
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
            audio: {}
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
        handleIncomingMessage(event) {
            console.log("Received message in asrvosk FRONTEND:", event.data);
            const data = JSON.parse(event.data);
            this.status = data.status;
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
    },
};
</script>
<style>
.mic img {
    max-height: 50px;
    max-width: 50px;
}
</style>