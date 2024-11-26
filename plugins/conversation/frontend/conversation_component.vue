<template>
    <div class="conversation-plugin">
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
            if (data.action == "abandon_conversation") {
                this.thread = [];
            } else {
                this.thread.push(data);
                this.scrollToBottom();
            }
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
.conversation-plugin{
    display: flex;
    flex-direction: column
}
#abandon {
    min-width: 20%;
    background: #00f;
    color: #fff;
}
.scrollableConv{
    overflow-y: scroll;
    height: 100%;
    overflow-x: hidden;
}
.container {
    background: #333;
    border: 1px solid #0f0;
}
.card-body {
    padding: 6px;
}
</style>