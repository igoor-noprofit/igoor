<template>
    <div class="localtts">
    </div>
</template>

<script>
const BasePluginComponent = require('/js/BasePluginComponent.js');
module.exports = {
    name: "localtts",
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
        }
    }
};
</script>
