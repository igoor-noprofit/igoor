<template>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "dailySettings",
    props: {
        initialSettings: Object
    },
    mixins: [BasePluginComponent],
    data() {
        return {
            formData: {},
        };
    },
    watch: {
        initialSettings: {
            handler(newVal) {
                if (newVal && Array.isArray(newVal) && newVal.length > 0) {
                    // Extract the first object from the array
                    this.formData = JSON.parse(JSON.stringify(newVal[0]));
                } else if (newVal && typeof newVal === 'object' && !Array.isArray(newVal)) {
                    this.formData = JSON.parse(JSON.stringify(newVal));
                } else {
                    this.formData = {};
                }
            },
            immediate: true,
            deep: true
        }
    },
    methods: {
    }
};
</script>

<style scoped>
</style>