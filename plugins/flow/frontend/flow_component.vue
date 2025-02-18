<template>
    <div class="flow container flow-plugin" :class="{ 'plugin-error': error }"
        v-if="answers && answers.length > 0 && appview != 'daily'">
        <button v-if="answers"
            :class="['btn', 'btn-side', 'btn-side-left', 'abandon', appview == 'autocomplete' ? 'autocomplete' : '',$root.headerExpanded ? 'expanded' : '']"
            @click="$_abandonConversation(true)">
            Abandonner la conversation
        </button>
        <div class="answers">
            <div class="row">
                <div v-for="(msg, index) in answers" :key="index">
                    <div :class="['msg msg-small']" @click="$_chooseAnswer(msg, index)">
                        {{ msg }}
                    </div>
                </div>
                <a class="autocompletelauncher" @click="$_showAutocomplete()">...</a>
            </div>
        </div>
    </div>
    <div v-else></div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

module.exports = {
    name: "flow",
    mixins: [BasePluginComponent],
    data() {
        return {
            selectedCard: null,
            answers: [],
            waitingai: true
        }
    },
    methods: {
        async $_abandonConversation(trigger_hook = false) {
            try {
                console.log("FLOW abandons conversation");
                if (trigger_hook) {
                    this.sendMsgToBackend({ "action": "abandon_conversation" });
                }
                this.$_clearAnswers()
            } catch (error) {
                console.error("Error abandoning conversation:", error);
            }
        },
        $_clearAnswers() {
            this.answers = []
        },
        handleIncomingMessage(event) {
            const handled = BasePluginComponent.methods.handleIncomingMessage.call(this, event);
            if (handled) return true;
            console.log(this.$options.name + ' handling message');
            let data; // Declare the variable 'data'
            try {
                data = JSON.parse(event.data);
                if (data.action) {
                    switch (data.action) { // Use 'data.action' instead of 'event.data.action'
                        case 'abandon_conversation':
                            trigger_hook = data.trigger_hook ? true : false
                            this.$_abandonConversation(data.trigger_hook);
                            break;
                        case 'clear_answers':
                            this.$_clearAnswers();
                            break;
                        default:
                            console.error("No handler for action " + data.action);
                            break;
                    }
                } else {
                    console.log("************ ANSWERS *********");
                    console.table(data);
                    this.answers = data.answers;
                    this.selectedCard = null;
                }
            } catch (e) {
                console.warn("Error parsing JSON in FLOW component");
                console.log("WRONG JSON:" + event.data)
            }
        },
        async $_chooseAnswer(msg, index) {
            let text = msg;
            // Remove the selected answer from the array
            this.answers.splice(index, 1);
            const json = { action: "speak", msg: text };
            console.log("sending JSON");
            console.log(json);
            this.sendMsgToBackend(json);
        },
        $_showAutocomplete() {
            console.log('emitting autocomplete');
            this.$emit('show-autocomplete');
        }
    }
}
</script>

<style scoped>
.autocompletelauncher {
    cursor: pointer;
    margin-top: 10px;
    display: block;
}
.flow-plugin {
    margin: 10px 0;
    flex-direction: row;
    display: flex
}

.answers .msg {
    margin-bottom: 10px;
}

.fade-out {
    display: none;
}

.fade-out {
    pointer-events: none;
}
</style>