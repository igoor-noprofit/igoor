<template>
    <div class="autocomplete plugin">
        <input type="text" v-model="userInput" autocomplete="off" name="autocomplete" placeholder="dis quelque chose">
        <a v-html="completion" v-if="completion" @click="$_speak()" class="completion"></a>
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
        $_speak(){
            const json = { action: "speak", msg: this.completion[0] };
            console.log("sending JSON");
            console.log(json);
            this.sendMsgToBackend(json);
            this.completion="";
        },
        handleIncomingMessage(event) {
            console.log("Custom message handler in " + this.name  + " component:", event.data);
            try {
                const data = JSON.parse(event.data);
                this.completion = data;
                if (data.action && data.action === "clear") {
                    this.userInput = "";
                }
            }
            catch (e) {
                console.warn("Error parsing JSON")
            }
        }
    },
    watch: {
        userInput: function(newInput) {
            if (newInput != ''){
                clearTimeout(this.inputTimeout); // Clear any existing timeout
                this.inputTimeout = setTimeout(() => {
                    const json = { msg: newInput };
                    this.sendMsgToBackend(json);
                }, 1500); // Replace 500 with your desired delay in milliseconds
            }   
            else{
                this.completion=""
            }
        }
    }
};
</script>

<style scoped>
.autocomplete.plugin {
    width: 100%;
    text-align: center;
    border: 1px solid #f00;
}
</style>