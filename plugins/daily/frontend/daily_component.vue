<template>
    <div class="daily container daily-plugin main" :class="{'plugin-error': error}" v-if="appview == 'daily'">
        <!-- Back Arrow -->
        <div v-if="currentView === 'main'" class="options">
            <div v-for="(category, index) in mainCategories" :key="index" class="options-col">
                <h3>{{ translateCategory(category.name) }}</h3>
                <button v-for="(item, key) in category.items" :key="key" class="btn"
                    :class="{ 'btn-primary': item.fixed, 'btn-secondary': !item.fixed }"
                    @click="selectItem(category.name, key, item)">
                    {{ translateItem(key) }}
                </button>                
            </div>
            <button class="btn btn-side btn-side-right" @click="switchToSecondaryView"><svg class="icon icon-l"><use xlink:href="/img/svgdefs.svg#icon-chevron_right"/></svg></button>
        </div>

        <!-- Secondary Categories View -->
        <div v-if="currentView === 'secondary'" class="categories-grid options secondary">
            <button class="btn btn-side btn-side-left" @click="switchToMainView"><svg class="icon icon-l"><use xlink:href="/img/svgdefs.svg#icon-chevron_left"/></svg></button>
            <div v-for="(category, index) in secondaryCategories" :key="index" class="options-col">
                <h3>{{ translateCategory(category.name) }}</h3>
                <button v-for="(item, key) in category.items" :key="key" class="btn"
                    :class="{ 'btn-primary': item.fixed, 'btn-secondary': !item.fixed }"
                    @click="selectItem(category.name, key, item)">
                    {{ translateItem(key) }}
                </button>             
            </div>
        </div>

        <div class="answers secondary" v-if="currentView=='answers'">
            <button class="btn btn-side btn-side-left" @click="switchToMainView"><svg class="icon icon-l"><use xlink:href="/img/svgdefs.svg#icon-chevron_left"/></svg></button>
            <div class="row">
                <div v-for="(msg, index) in answers" :key="index">
                    <div :class="['msg msg-small']" @click="$_chooseAnswer(msg, index)">
                        {{ msg }}
                    </div>
                </div>
                <!--a v-show="appview!=='autocomplete'" class="autocompletelauncher plugin" @click="$_showAutocomplete()">...</a-->
            </div>
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

module.exports = {
    name: "daily",
    mixins: [BasePluginComponent],
    data() {
        return {
            currentView: 'main',
            dailyData: [],
            mainCategories: [],
            secondaryCategories: [],
            answers: []
        };
    },
    mounted() {
        console.log('DAILY MOUNTED');
        this.sendMsgToBackend({ socket: "ready" });
        fetch('/plugins/daily/daily.json')
            .then(response => response.json())
            .then(data => {
                this.dailyData = data;
                this.processCategories();
            })
            .catch(error => console.error('Error loading daily.json:', error));
    },
    methods: {
        $_showAutocomplete(){
            console.log('emitting autocomplete');
            this.$emit('show-autocomplete');
        },
        async $_abandonConversation() {
            try {
                this.sendMsgToBackend({ "action": "abandon_conversation" });

            } catch (error) {
                console.error("Error abandoning conversation:", error);
            }
        },
        handleIncomingMessage(event) {
            const handled = BasePluginComponent.methods.handleIncomingMessage.call(this, event);
            if (handled) return true;
            console.log(this.$options.name + ' handling message');
            try {
                console.log(event.data);
                const data = JSON.parse(event.data);
                console.log(data);
                if (data.dailyData) {
                    this.dailyData = data.dailyData;
                    this.processCategories();
                }
                if (data.answers) {
                    this.answers = data.answers;
                    this.currentView = 'answers';
                }
            } catch (error) {
                console.error('Error processing message:', error);
            }
        },
        processCategories() {
            // Process first array item for main categories
            this.mainCategories = this.extractCategories(this.dailyData[0]);
            // Process second array item for secondary categories
            this.secondaryCategories = this.extractCategories(this.dailyData[1]);
        },
        extractCategories(data) {
            return Object.entries(data).map(([name, items]) => ({
                name,
                items
            }));
        },
        translateCategory(category) {
            // Add your translation logic here
            return category;
        },
        translateItem(item) {
            // Add your translation logic here
            return item;
        },
        selectItem(category, item, data) {
            if (this.currentView == 'main' || this.currentView=='secondary'){
                this.answers=[];
                this.sendMsgToBackend({
                    action: 'generatePhrases',
                    category: category,
                    theme: item
                });
                this.currentView = 'answers';
                
            }
        },
        /* Sending final phrase */
        async $_chooseAnswer(msg, index) {
            let text = msg;
            const json = { action: "speak", msg: text };
            console.log("sending JSON");
            console.log(json);
            this.sendMsgToBackend(json);
            this.switchToMainView();
            this.answers=[];
        },
        switchToSecondaryView() {
            this.currentView = 'secondary';
        },
        switchToMainView() {
            this.currentView = 'main';
        }
    }
};
</script>

<style scoped>
.answers.secondary{
    display:flex;
    justify-content: center;
}
.main {
    position: relative;
    z-index: 10;
    box-shadow: 0rem -0.5rem 1rem 0rem rgba(0, 0, 0, 0.2);
    overflow: hidden;
    padding: 1rem;
    margin-bottom: 6rem;
    height: 100%;
    width: 100%;
}

.options {
    padding-right: 5rem;
    display: flex;
    gap: 1rem;
}
.options.secondary, .answers{
    padding-left: 5rem;
}
.answers .msg{
    margin-bottom: 10px;
}

.options .btn {
    text-align: left;
}

.options-col {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    width: 100%;
}

.options-col .btn {
    width: 100%;
}
</style>