<template>
    <div class="clock-plugin">
        {{ formattedDateTime }}
    </div>
</template>

<script>
export default {
    name: "clock",
    data() {
        return {
            formattedDateTime: '',
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
            const now = new Date();
            const optionsDate = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' };
            const dateString = now.toLocaleDateString('fr-FR', optionsDate);

            const optionsTime = { hour: '2-digit', minute: '2-digit' };
            const timeString = now.toLocaleTimeString('fr-FR', optionsTime);

            this.formattedDateTime = `${dateString} ${timeString}`;
        }
    }
};
</script>

<style scoped>
.clock-plugin {
    color: #fff;
    font-size: 0.8rem;
}
</style>