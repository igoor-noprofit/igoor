<template>
    <div class="autocomplete plugin" v-if="appview == 'autocomplete'">
        <div class="autocomplete_input">
            <input type="text" v-model="userInput" autocomplete="off" name="autocomplete" placeholder="" ref="autocompleteInput">
        </div>
        <div class="autocomplete_send">
            <button @click="$_speakInput()">PARLER ></button>
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

module.exports = {
    name: "autocomplete",
    mixins: [BasePluginComponent],
    data() {
        return {
            completion: "",
            waitingai: true,
            userInput: ""
        }
    },
    methods: {
        focusInputIfNeeded() {
            if (this.appview === 'autocomplete') {
                this.$nextTick(() => {
                    this.$refs.autocompleteInput.focus();
                });
            }
        },
        $_speak(msg) {
            this.$_clean();
            const json = { action: "speak", msg: msg };
            console.log("sending JSON");
            console.log(json);
            this.completion = "";
            this.sendMsgToBackend(json);
        },
        $_speakInput() {
            this.$_speak(this.userInput)
        },
        $_clean() {
            this.userInput = ""; // Force refresh of this.input
        },
        handleIncomingMessage(event) {
            console.log("Custom message handler in " + this.name + " component:", event.data);
            try {
                const data = JSON.parse(event.data);
                if (Array.isArray(data) && typeof data[0] === 'string') {
                    this.completion = data;
                } else if (data.action && data.action === "clear") {
                    this.$_clean();
                } else {
                    this.completion = ""; // Clear completion if data is not a string
                }
            }
            catch (e) {
                console.warn("Error parsing JSON");
                this.completion = ""; // Clear completion on error
            }
        }
    },
    watch: {
        appview: function (newView) {
            this.focusInputIfNeeded();
        },
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

button {
    cursor: pointer;
}
</style>