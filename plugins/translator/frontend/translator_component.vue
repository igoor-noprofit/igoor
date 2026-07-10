<template>
    <div class="translator-plugin">
        <!-- Translator plugin is settings-only; no main UI needed -->
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "translator",
    mixins: [BasePluginComponent],
    data() {
        return {};
    }
};
</script>

<style scoped>
.translator-plugin {
    /* This plugin operates in the background via settings */
}
</style>
