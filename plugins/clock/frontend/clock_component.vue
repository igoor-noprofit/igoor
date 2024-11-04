<template>
    <div class="datetime-plugin">
        {{ formattedDateTime }} - <a @click="$parent.js_api('minimize')">MIN</a> 
    </div>
</template>

<script>
export default {
    data() {
        return {
            formattedDateTime: '',
        };
    },
    created() {
        this.updateDateTime();
        console.log('clock created')
    },
    methods: {
        updateDateTime() {
            const now = new Date();
            const optionsDate = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' };
            const dateString = now.toLocaleDateString(undefined, optionsDate);

            const optionsTime = { hour: '2-digit', minute: '2-digit' };
            const timeString = now.toLocaleTimeString(undefined, optionsTime);

            this.formattedDateTime = `${dateString} ${timeString}`;
        }
    }
};
</script>

<style scoped>
.datetime-plugin {
    color: #fff;
}
</style>