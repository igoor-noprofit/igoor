<template>
    <div class="elevenlabs">
        <a @click="$_speak('Bonjour, ceci est un test')">Speak</a>
        <a @click="$_customMethod()">CUSTOM METHOD</a>
    </div>
</template>

<script>
const BasePluginComponent = require('/js/BasePluginComponent.js');
module.exports = {
    name: "elevenlabs",
    mixins: [BasePluginComponent],
    methods: {
        async $_speak(msg) {
            const self = this;
            try {
                console.log("triggering speak hook with message " + msg);
                const result = pywebview.api.trigger_hook("speak", { message: msg });
            } catch (error) {
                console.error('Error triggering speak hook: ', error);
            }
        },
        $_customMethod() {
            console.log("custom method");
            // Call a method from the mixin
            this.commonMethod();
        }
    }
};
</script>