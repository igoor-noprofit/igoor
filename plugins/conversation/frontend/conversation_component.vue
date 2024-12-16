<template>
    <div class="conversation-plugin" v-if="appview !== 'autocomplete' && appview !== 'onboarding'">
        <div class="scrollableConv" ref="scrollableConv">
            <div v-for="(message, index) in thread" :key="index">
                <div class="card" :class="[message.author, { last: isLastMessage(index) }]">
                    <div class="card-body">
                        <p class="card-text">{{ message.msg }}</p>
                    </div>
                </div>
            </div>
        </div>
        <div v-if="showProgressBar" class="progress-bar-container">
            <div class="progress-bar" :style="{ width: progressBarWidth + '%' }"></div>
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
            thread: [],
            showProgressBar: false,
            progressBarWidth: 0,
            countdownInterval: null
        }
    },
    computed: {
        isLastMessage() {
            return (index) => index === this.thread.length - 1;
        }
    },
    methods: {
        handleIncomingMessage(event) {
            console.log("Custom message handler in CONVERSATION component:", event.data);
            const data = JSON.parse(event.data);
            console.table(data);
            if (data.action == "abandon_conversation") {
                this.thread = [];
                this.resetProgressBar();
            } else if (data.action == "startCountdown") {
                // Handle start countdown logic
            } else if (data.action == "resetCountdown") {
                // Handle reset countdown logic
            } else if (data.action == "showProgressBar") {
                this.showProgressBar = true;
                // Logic to show progress bar
            } else {
                this.thread.push(data);
                this.$nextTick(() => {
                    this.scrollToBottom();
                });
            }
        },
        scrollToBottom() {
            console.log("scrolling");
            const scrollableDiv = this.$refs.scrollableConv;
            if (scrollableDiv) {
                scrollableDiv.scrollTop = scrollableDiv.scrollHeight;
                console.log(scrollableDiv.scrollTop, scrollableDiv.scrollHeight);
            }
            else {
                console.warn("cannot scroll")
            }
        },
        startProgressBar() {
            this.showProgressBar = true;
            this.progressBarWidth = 0;
            const totalDuration = 5000; // Duration for the progress bar in milliseconds
            const intervalDuration = 100; // Update interval in milliseconds
            const increment = 100 / (totalDuration / intervalDuration);

            this.countdownInterval = setInterval(() => {
                this.progressBarWidth += increment;
                if (this.progressBarWidth >= 100) {
                    clearInterval(this.countdownInterval);
                    this.showProgressBar = false;
                }
            }, intervalDuration);
        },
        resetProgressBar() {
            this.showProgressBar = false;
            this.progressBarWidth = 0;
            if (this.countdownInterval) {
                clearInterval(this.countdownInterval);
            }
        }
    },
    watch: {
        thread() {
            console.log("thread has changed");
            this.$nextTick(() => {
                this.scrollToBottom();
            });
        }
    }
};
</script>

<style scoped>
.conversation-plugin {
    display: flex;
    flex-direction: column
}

#abandon {
    min-width: 20%;
    background: #00f;
    color: #fff;
}

.scrollableConv {
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

.progress-bar-container {
    width: 100%;
    background-color: #f3f3f3;
    border-radius: 5px;
    overflow: hidden;
    margin-top: 10px;
}

.progress-bar {
    height: 10px;
    background-color: #4caf50;
    width: 0;
    transition: width 0.1s linear; /* Ensure smooth transition */
}
</style>