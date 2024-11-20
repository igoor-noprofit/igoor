<template>
    <div class="convContainer">
        <h3>Conversation</h3>
        <div v-if="thread" id="abandon">
            <input type="button" value="Abandonner la conversation" @click="$_abandonTopic()">
        </div>
        <div class="scrollableConv" ref="scrollableConv">
            <div v-for="(message, index) in thread" :key="index">
                <div class="card" :class="message.author">
                    <div class="card-body">
                        <p class="card-text">{{ message.msg }}</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

module.exports = {
    name: "conversation",
    mixins: [BasePluginComponent],
    data() {
        return {
            thread: []
        }
    },
    methods: {
        handleIncomingMessage(event) {
            console.log("Custom message handler in CONVERSATION component:", event.data);
            const data = JSON.parse(event.data);
            console.table(data);
            this.thread.push(data);
            this.scrollToBottom();
        },
        $_abandonTopic() {
            console.log('abandon topic');
            window.abandonTopic();
        },
        formatDate(datetime) {
            const date = new Date(datetime);
            return date.toLocaleString();
        },
        scrollToBottom() {
            const scrollableDiv = this.$refs.scrollableConv;
            if (scrollableDiv) {
                scrollableDiv.scrollTop = scrollableDiv.scrollHeight;
            }
        }
    }
};
</script>

<style scoped>
#abandon {
    margin: 0 0 30px 0;
}

.container {
    height: 100%;
    display: flex
}

.card-body {
    padding: 6px;
}
</style>