<template>
    <div class="conversation-plugin" v-if="appview !== 'autocomplete' && appview !== 'onboarding'"
        :class="{ 'expanded': isExpanded }">
        <div class="scrollableConv" ref="scrollableConv">
            <div v-for="(message, index) in thread" :key="index">
                <div class="card msg" :class="getMsgClass(message, index)" @click="handleMessageClick(message)">
                    <div class="card-body">
                        <p class="card-text">{{ message.msg }}</p>
                    </div>
                </div>
            </div>
        </div>
        <div v-if="showProgressBar" class="progress-bar-container">
            <div class="progress-bar" :style="{ width: progressBarWidth + '%' }"></div>
        </div>
        <button v-if="showExpandButton" class="btn btn-side btn-side-right" @click="$_enlargeConversation">
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
            isExpanded: false,
            showExpandButton: false // <-- add this
        }
    },
    mounted() {
        this.checkScrollableOverflow();
    },
    computed: {
        isLastMessage() {
            return (index) => index === this.thread.length - 1;
        }
    },
    methods: {
        getMsgClass(message, index) {
            const isLast = index === this.thread.length - 1;
            // All messages except the last get msg-small (regardless of author)
            const classes = [];
            if (message.author === 'master') {
                classes.push('master');
            }
            if (message.author === 'def') {
                classes.push('def', 'msg-other');
            }
            if (!isLast) {
                classes.push('msg-small');
            }
            if (isLast) {
                classes.push('last');
            }
            return classes;
        },
        checkScrollableOverflow() {
            this.$nextTick(() => {
                const el = this.$refs.scrollableConv;
                if (el) {
                    this.showExpandButton = el.scrollHeight > el.clientHeight;
                }
            });
        },
        $_enlargeConversation() {
            this.isExpanded = !this.isExpanded;
            // Emit event to parent app to handle header expansion
            this.$root.toggleHeaderExpansion(this.isExpanded);

            this.$nextTick(() => {
                this.scrollToBottom();
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
                // Use the duration from the backend or fall back to 5000ms
                const duration = data.duration || 5000;
                this.startProgressBar(duration);
                // Logic to show progress bar
            } else {
                this.thread.push(data);
                console.log("ADDING MESSAGE", data);
                this.scrollToBottom();
                this.checkScrollableOverflow();
            }
        },
        scrollToBottom(retries = 5) {
            this.$nextTick(() => {
                const scrollableDiv = this.$refs.scrollableConv;
                if (scrollableDiv) {
                    scrollableDiv.scrollTop = scrollableDiv.scrollHeight;
                    console.log(scrollableDiv.scrollTop, scrollableDiv.scrollHeight);
                } else if (retries > 0) {
                    setTimeout(() => this.scrollToBottom(retries - 1), 100);
                } else {
                    console.warn("cannot scroll");
                }
            });
        },
        startProgressBar(duration = 5000) {
            this.showProgressBar = true;
            this.progressBarWidth = 0;
            const totalDuration = duration; // Use the duration passed from backend
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
                this.checkScrollableOverflow();
            });
        },
        appview(newView) {
            if (newView === 'autocomplete') {
                this.isExpanded = false;
                this.$root.toggleHeaderExpansion(false);
                this.scrollToBottom();
            }
            this.checkScrollableOverflow();
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

.msg{
    background-color: #2F535B !important;
}


.msg {
    background-color: #2F535B !important;
    align-self: flex-end; /* Right side by default */
    max-width: 70%;
    position: relative;
}

.msg.msg-other {
    background-color: #1D6634 !important;
    border-radius: 0.5rem 0.5rem 0.5rem 0rem;
    align-self: flex-start; /* Left side for .msg-other */
}

.msg.msg-small {
    font-size: 0.875rem;
}

.msg:after {
    position: absolute;
    content: "";
    right: -1rem;
    bottom: 0;
    width: 0px;
    height: 0px;
    border-style: solid;
    border-width: 1rem 0 0 1rem;
    border-color: transparent transparent transparent #2F535B;
}

.msg.msg-other:after {
    left: -1rem;
    border-width: 0 0 1rem 1rem;
    border-color: transparent transparent #1D6634 transparent;
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
    height: 20px;
    background-color: #4caf50;
    width: 0;
    transition: width 0.1s linear;
    /* Ensure smooth transition */
}

.master {
    cursor: pointer;
    margin-right: 10px;
    float: right;
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