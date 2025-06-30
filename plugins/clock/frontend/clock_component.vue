<template>
    <div class="clock-plugin">
        <span class="date">{{ formattedDate }}</span>
        <span class="time">{{ formattedTime }}</span>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
module.exports = {
    name: "clock",
    mixins: [BasePluginComponent],
    data() {
        return {
            formattedDate: '',
            formattedTime: '',
            websocket: null,  // Store WebSocket instance
            status: 'loading',
            intervalId: null
        };
    },
    created() {
        this.updateDateTime();
        this.intervalId = setInterval(() => {
            this.updateDateTime();
        }, 1000); // update every second
    },
    beforeUnmount() {
        clearInterval(this.intervalId);
    },
    methods: {
        updateDateTime() {
            // Convert lang to BCP 47 format (fr_FR -> fr-FR)
            let locale = (this.lang || 'en-EN').replace('_', '-');
            const now = new Date();
            const optionsDate = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' };
            const dateString = now.toLocaleDateString(locale, optionsDate);

            const optionsTime = { hour: '2-digit', minute: '2-digit' };
            const timeString = now.toLocaleTimeString(locale, optionsTime);

            this.formattedDate = `${dateString}`
            this.formattedTime = `${timeString}`;
        }
    }
};
</script>

<style scoped>
span.date, span.time{
    padding: 0 0.5rem;
}
.clock-plugin {
    color: #fff;
    font-size: 0.8rem;
}
</style>