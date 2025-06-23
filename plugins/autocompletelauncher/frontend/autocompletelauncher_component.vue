<template>
    <a v-show="appview!=='autocomplete'" class="autocompletelauncher plugin" @click="$_showAutocomplete()">{{  translations["say something..."] }}</a>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

module.exports = {
    name: "autocompletelauncher",
    mixins: [BasePluginComponent],
    data() {
        return {
        }
    },
    methods: {
        $_showAutocomplete(){
            console.log('emitting autocomplete');
            this.$emit('show-autocomplete');
        },
        handleIncomingMessage(event) {
            console.log("Custom message handler in " + this.name + " component:", event.data);
            try {
                const data = JSON.parse(event.data);
                if (Array.isArray(data) && typeof data[0] === 'string') {
                    
                } else if (data.action && data.action === "clear") {
                } else {
                    
                }
            }
            catch (e) {
                console.warn("Error parsing JSON");
                this.completion = ""; // Clear completion on error
            }
        }
    }
};
</script>

<style scoped>
a{
    cursor: pointer;
}
</style>