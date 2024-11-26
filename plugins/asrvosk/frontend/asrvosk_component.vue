<template>
    <div class="asrvosk-plugin">
        <div class="mic" :class="status">
            <img src="/img/mic.png">
        </div>
        <!--img v-if="status == 'listening'" src="/img/listening.gif" id="listening"-->
    </div>
</template>
<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    name: "asrvosk",
    mixins: [BasePluginComponent], // Use the mixin
    data() {
        return {
            status: 'loading'
        };
    },
    methods: {
        handleIncomingMessage(event) {
            console.log("Custom message handler in asrvosk component:", event.data);
            const data = JSON.parse(event.data);
            this.status = data.status;
        }
    },
    created() {
        
    },
    beforeDestroy() {
        
    }
};
</script>
<style>

#listening{
    max-height: 100px;
}
.mic img{
    max-height: 50px;
    max-width: 50px;
}
.mic.loading{
    opacity:0.5;
}
.mic.paused{
    background: #A8351B !important;
}
.mic.ready{
    opacity: 1;
}
</style>