<template>
    <div class="meteo-plugin">
        
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "meteo",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
            websocket: null
        };
    },
    methods: {
        
    },
    created() {
        
    },
    beforeDestroy() {
        
    }
};
</script>