<template>
    <div class="onboarding plugin" v-show="appview=='onboarding'">
        ONBOARDING HERE
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "onboarding",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
            
        };
    },
    methods: {
        handleIncomingMessage(event) {
            console.log("Custom message handler in " + this.name + " component:", event.data);
            try {
                const data = JSON.parse(event.data);
                console.log(data)
            }
            catch (e) {
                console.warn("Error parsing JSON")
            }
        }
    },
    created() {
        
    },
    beforeDestroy() {
        
    }
};
</script>