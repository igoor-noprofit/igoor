<template>
    <div class="clock-plugin">
        <span class="date">{{ formattedDate }}</span>
        <span class="time">{{ formattedTime }}</span>
    </div>
</template>

<script>
export default {
    name: "clock",
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
            const now = new Date();
            const optionsDate = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' };
            const dateString = now.toLocaleDateString(this.lang, optionsDate);

            const optionsTime = { hour: '2-digit', minute: '2-digit' };
            const timeString = now.toLocaleTimeString(this.lang, optionsTime);

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