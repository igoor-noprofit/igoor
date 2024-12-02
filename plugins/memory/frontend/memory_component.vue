<template>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

module.exports = {
    name: "memory",
    mixins: [BasePluginComponent],
    data() {
        return {
            waitingai: true
        }
    },
    methods: {
        handleIncomingMessage(event) {
            console.log("Custom message handler in MEMORY component:", event.data);
            try {
                const data = JSON.parse(event.data);
            }
            catch (e) {
                console.warn("Error parsing JSON")
            }
        }
    }
};
</script>

<style scoped>

</style>