<template>
    <div class="flow container flow-plugin" v-if="answers.length > 0" id="answers">
        <div v-if="answers" id="abandon">
            <input type="button" value="Abandonner" @click="$_abandonConversation()">
        </div>
        <div>
            <div class="row">
                <div class="col-md-6" v-for="(msg, index) in answers" :key="index">
                    <div :class="['card', { 'fade-out': selectedCard !== null && selectedCard !== index }]"
                        @click="$_chooseAnswer(msg, index)">
                        <div class="card-body">
                            <p class="card-text">{{ $_removeSource(Object.values(msg)[0]) }}</p>
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
        $_abandonConversation() {
            window.pywebview.api.trigger_hook("abandon").then(response => {
                console.log(response)
                console.table(response)
                this.answers=[];
            });
        },
        handleIncomingMessage(event) {
            console.log("Custom message handler in FLOW component:", event.data);
            try{
                const data = JSON.parse(event.data);
                this.answers = data;
                this.selectedCard = null;
            }
            catch(e){
                console.warn("Error parsing JSON")
            }
        },
        async $_chooseAnswer(msg, index) {
            let text = Object.values(msg)[0];
            this.selectedCard = index;
            const json = { action: "speak", msg: text };
            console.log("sending JSON");
            console.log(json);
            this.sendMsgToBackend(json);
        }
    }
};
</script>

<style scoped>
.flow-plugin {
    border: 1px solid #00796b;
    margin: 10px 0;
    flex-direction: row
}
#abandon{
    width: 20%;
}
.card-title{
    font-size: 1rem;
}

.card-body {
    padding: 6px;
    border: 1px solid #000;
    cursor:pointer
}
.fade-out {
    pointer-events: none;
}

</style>