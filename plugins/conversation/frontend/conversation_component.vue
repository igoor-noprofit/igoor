<template>
    <div class="conversation-plugin" v-if="appview !== 'autocomplete' && appview !== 'onboarding'"
        :class="{ 'expanded': isExpanded }">
        <div class="scrollableConv" ref="scrollableConv">
            <div v-for="(message, index) in thread" :key="index">
                <div class="card" :class="[message.author, { last: isLastMessage(index) }]"
                    @click="handleMessageClick(message)">
                    <div class="card-body">
                        <p class="card-text">{{ message.msg }}</p>
                    </div>
                </div>
            </div>
        </div>
        <div v-if="showProgressBar" class="progress-bar-container">
            <div class="progress-bar" :style="{ width: progressBarWidth + '%' }"></div>
        </div>
        <button class="btn btn-side btn-side-right" @click="$_enlargeConversation">
            <svg class="icon icon-l" :class="{ 'rotated': isExpanded }">
                <use xlink:href="/img/svgdefs.svg#icon-chevron_down" />
            </svg>
        </button>
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
            countdownInterval: null,
            isExpanded: false
        }
    },
    computed: {
        isLastMessage() {
            return (index) => index === this.thread.length - 1;
        }
    },
    methods: {
        $_enlargeConversation() {
            this.isExpanded = !this.isExpanded;
            // Emit event to parent app to handle header expansion
            this.$root.toggleHeaderExpansion(this.isExpanded);

            this.$nextTick(() => {
                if (this.isExpanded) {
                    this.scrollToBottom();
                }
            });
        },
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
                this.showProgressBar = false;
            } else if (data.action == "showProgressBar") {
                this.showProgressBar = true;
                this.startProgressBar()
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
            this.$nextTick(() => { 
                const scrollableDiv = this.$refs.scrollableConv;
                if (scrollableDiv) {
                    scrollableDiv.scrollTop = scrollableDiv.scrollHeight;
                    console.log(scrollableDiv.scrollTop, scrollableDiv.scrollHeight);
                }
                else {
                    console.warn("cannot scroll")
                }
            });
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
        },
        handleMessageClick(message) {
            // Only trigger speak for messages from 'master' (IGOOR user)
            if (message.author === 'master') {
                this.sendMsgToBackend({
                    action: 'speak',
                    message: message.msg
                });
            }
        }
    },
    watch: {
        thread() {
            console.log("thread has changed");
            this.$nextTick(() => {
                this.scrollToBottom();
            });
        },
        appview(newView) {
            if (newView === 'autocomplete') {
                this.isExpanded = false;
                this.$root.toggleHeaderExpansion(false);
            }
        }
    }
};
</script>

<style scoped>
.conversation-plugin {
    display: flex;
    flex-direction: column;
    transition: height 0.3s ease;
    position: relative;
}
.conversation-plugin.expanded {
  height: 100%;
}

#abandon {
    min-width: 20%;
    background: #00f;
    color: #fff;
}

.scrollableConv {
    overflow-y: scroll;
    height: calc(100% - 40px);
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
    height: 20px;
    background-color: #4caf50;
    width: 0;
    transition: width 0.1s linear;
    /* Ensure smooth transition */
}

.master {
    cursor: pointer;
}

.master:hover {
    background-color: rgba(0, 0, 0, 0.05);
}

.btn-side-right {
    position: absolute;
    z-index: 2;
}

.icon.rotated {
    transform: rotate(180deg);
}
</style>