<template>
    <div class="elevenlabs">
    </div>
</template>

<script>
const BasePluginComponent = require('/js/BasePluginComponent.js');
module.exports = {
    name: "elevenlabs",
    mixins: [BasePluginComponent],
    methods: {
        async $_speak(msg) {
            try {
                console.log("triggering speak hook with message " + msg);
                const api = await window.ensureBackendApi();
                await api.triggerHook("speak", { message: msg });
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