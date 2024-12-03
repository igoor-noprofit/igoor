<template>
    <div class="autocomplete_launcher plugin">
        <a @click="$_showAutocomplete()">dire quelque chose</a>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

module.exports = {
    name: "autocomplete_launcher",
    mixins: [BasePluginComponent],
    data() {
        return {
        }
    },
    methods: {
        $_speak(msg) {
            this.$_clean();
            const json = { action: "speak", msg: msg};
            console.log("sending JSON");
            console.log(json);
            this.completion = "";
            this.sendMsgToBackend(json);
        },
        $_speakInput(){
            this.$_speak(this.userInput)
        },
        $_speak_completion(){
            this.$_speak(this.completion[0])
        },
        $_clean() {
            this.userInput = ""; // Force refresh of this.input
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
    },
    watch: {
        userInput: function (newInput) {
            if (newInput != '') {
                clearTimeout(this.inputTimeout); // Clear any existing timeout
                this.inputTimeout = setTimeout(() => {
                    const json = { msg: newInput };
                    this.sendMsgToBackend(json);
                }, 1500); // Replace 500 with your desired delay in milliseconds
            }
            else {
                this.completion = ""
            }
        }
    }
};
</script>

<style scoped>
.autocomplete.plugin {
    width: 100%;
}
</style>