<template>
    <div class="meteo-plugin">
        WEATHER PARISI
        <button @click="invokeBackend">Invoke Backend</button>
    </div>
</template>

<script>

module.exports = {
    name: "meteo",
    methods: {
        async invokeBackend() {
            const self = this;
            try {
                
                const result = await callPluginBackend('meteo', 'force_update', 'prova', 'diosanto');
                console.log('Backend call completed:', result);
            } catch (error) {
                console.error('Backend call failed:', error);
            }
        }
    }
};
</script>