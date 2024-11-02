<template>
    <div class="elevenlabs">
        <a @click="$_speak('Bonjour, ceci est un test')">Speak</a>
    </div>
</template>

<script>
module.exports = {
    name: "elevenlabs",
    methods:{
        async $_speak(msg) {
            const self = this;
            try {
                console.log("triggering speak hook with message " + msg);
                const result = pywebview.api.trigger_hook("speak",{ message: msg });
            } catch (error) {
                console.error('Error triggering speak hook: ', error);
            }
        }
    }
};
</script>