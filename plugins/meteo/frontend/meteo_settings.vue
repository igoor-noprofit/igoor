<template>
    <div class="meteo-plugin-settings">
        <input type="text" value="" placeholder="ex. 30fb31...">
        <input type="text" value="" name="lat_home" placeholder="ex. 13.12292393">
        <input type="text" value="" name="lng_home" placeholder="ex. 1.848349">
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
console.log('BasePluginComponent imported:', BasePluginComponent);

export default {
    name: "meteoSettings",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
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