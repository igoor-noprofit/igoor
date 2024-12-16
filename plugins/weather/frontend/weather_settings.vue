<template>
    <div class="meteo-plugin-settings">
        <field>
            <label>Api key</label><input type="text" value="" name="api_key" placeholder="ex. 30fb31...">
        </field>
        <field>
            <label>Latitude maison</label><input type="text" value="" name="lat_home" placeholder="ex. 13.12292393">
        </field>
        <field>
            <label>Longitude maison</label><input type="text" value="" name="lng_home" placeholder="ex. 1.848349">
        </field>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

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