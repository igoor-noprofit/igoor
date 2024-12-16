<template>
    <div class="flow container flow-plugin" v-if="answers.length > 0">
        <div v-if="answers" class="abandon">
            <input type="button" value="Abandonner" @click="$_abandonConversation()">
        </div>
        <div class="answers">
            <div class="row">
                <div v-for="(msg, index) in answers" :key="index">
                    <div :class="['card', { 'fade-out': selectedCard == index }]" @click="$_chooseAnswer(msg, index)">
                        <div class="card-body">
                            <p class="card-text">{{ msg }}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <!--div v-show="waitingai">J'attends d'autres réponses possibles</div-->
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
        async $_abandonConversation() {
            try {
                console.log("FLOW abandons conversation");
                this.sendMsgToBackend({ "action": "abandon_conversation" });
                this.answers = []
            } catch (error) {
                console.error("Error abandoning conversation:", error);
            }
        },
        handleIncomingMessage(event) {
            console.log("FLOW component:", event.data);
            let data; // Declare the variable 'data'
            try {
                data = JSON.parse(event.data);
                if (data.action) {
                    switch (data.action) { // Use 'data.action' instead of 'event.data.action'
                        case 'abandon_conversation':
                            this.$_abandonConversation();
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
                console.warn("Error parsing JSON");
            }
        },
        async $_chooseAnswer(msg, index) {
            let text = msg;
            this.selectedCard = index;
            const json = { action: "speak", msg: text };
            console.log("sending JSON");
            console.log(json);
            this.sendMsgToBackend(json);
        }
    }
}
</script>

<style scoped>
.flow-plugin {
    margin: 10px 0;
    flex-direction: row;
    display: flex
}

.abandon {
    width: 20%;
}

.card-title {
    font-size: 1rem;
}

.fade-out {
    display: none;
}

.card-body {
    padding: 6px;
    cursor: pointer
}

.fade-out {
    pointer-events: none;
}
</style>