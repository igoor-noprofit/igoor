<template>
    <div class="flow container flow-plugin" v-if="answers.length > 0" id="answers">
        <div>
            <div class="row">
                <div class="col-md-6" v-for="(msg, index) in answers" :key="index">
                    <div :class="['card', { 'fade-out': selectedCard !== null && selectedCard !== index }]"
                        @click="$_chooseAnswer(msg, index)">
                        <div class="card-body">
                            <div class="emotion" v-show="Object.keys(msg)[0].toLowerCase() !== 'std'">
                                <!--img class="emoticon" @error="$_handleImageError" :src="`/img/icons/emo_${Object.keys(msg)[0].toLowerCase()}.png`" alt="emoticon" /-->
                                <!--h5 class="card-title">{{ `${Object.keys(msg)[0]}` }}</h5-->
                            </div>
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
        /*
        $_handleImageError(event){
            console.log('no emoticon found');
            event.target.src = '/img/icons/emo_vide.png';
        },
        */
        handleIncomingMessage(event) {
            console.log("Custom message handler in FLOW component:", event.data);
            const data = JSON.parse(event.data);
            this.answers = data;
            this.selectedCard = null;
            this.cpuUsage = data.cpu_usage;
            this.memoryUsage = data.memory_usage;
        },
        async $_chooseAnswer(msg, index) {
            let text = Object.values(msg)[0];
            this.selectedCard = index;
            const json = { action: "speak", msg: text };
            console.log("sending JSON");
            console.log(json);
            this.sendMsgToBackend(json);
            /* 
            console.log("Speaking phrase: " + text);
            
            
            result = await window.pywebview.api.trigger_hook("speak", jsonText);
            /*
            addMessageToDB(text);
            */
        },
        $_removeSource(text) {
            // Use a regular expression to remove text between 【 and 】, including the brackets
            return text.replace(/【.*?】/g, '');
        }
    }
};
</script>

<style scoped>
.flow-plugin {
    padding: 10px;
    border: 1px solid #00796b;
    margin: 10px 0;
    max-width: 50%;
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