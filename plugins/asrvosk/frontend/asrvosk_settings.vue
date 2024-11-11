<template>
    <div class="asrvosk-plugin-settings">
        <field>
            <label>Wakeword</label><input type="text" value="" name="wakeword" placeholder="ex. Alexa">
        </field>
        <field>
            <label>Model size</label><input type="text" value="" name="model_size" placeholder="big|medium|small">
        </field>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
console.log('BasePluginComponent imported:', BasePluginComponent);

export default {
    name: "asrvoskSettings",
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