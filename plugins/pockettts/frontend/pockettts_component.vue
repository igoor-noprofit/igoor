<template>
    <div class="pockettts">
    </div>
</template>

<script>
const BasePluginComponent = require('/js/BasePluginComponent.js');
module.exports = {
    name: "pockettts",
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
            console.log("pockettts custom method");
            this.commonMethod();
        }
    }
};
</script>
