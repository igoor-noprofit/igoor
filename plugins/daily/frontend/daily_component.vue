<template>
    <div class="daily container daily-plugin main" :class="{ 'plugin-error': error }" v-if="appview == 'daily'">
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
            <button class="btn btn-side btn-side-right" @click="switchToSecondaryView"><svg class="icon icon-l">
                    <use xlink:href="/img/svgdefs.svg#icon-chevron_right" />
                </svg></button>
        </div>

        <!-- Secondary Categories View -->
        <div v-if="currentView === 'secondary'" class="categories-grid options secondary">
            <button class="btn btn-side btn-side-left" @click="switchToMainView"><svg class="icon icon-l">
                    <use xlink:href="/img/svgdefs.svg#icon-chevron_left" />
                </svg></button>
            <div v-for="(category, index) in secondaryCategories" :key="index" class="options-col">
                <h3>{{ translateCategory(category.name) }}</h3>
                <button v-for="(item, key) in category.items" :key="key" class="btn"
                    :class="{ 'btn-primary': item.fixed, 'btn-secondary': !item.fixed }"
                    @click="selectItem(category.name, key, item)">
                    {{ translateItem(key) }}
                </button>
            </div>
        </div>

        <div class="secondary" v-if="currentView == 'loadingAnswers'">
            loading...
        </div>
        <div class="answers" v-if="currentView == 'answers'">
            <button class="btn btn-side btn-side-left" @click="switchToMainView"><svg class="icon icon-l">
                    <use xlink:href="/img/svgdefs.svg#icon-chevron_left" />
                </svg></button>
            <div class="row columns">
                <div v-for="col in ['left', 'center', 'right']" :key="col" :class="['column', col]">
                    <div v-for="(msg, idx) in answers[col]" :key="col + '-' + idx" class="msg msg-small"
                        @click="$_chooseAnswer(msg, idx, col)">
                        {{ msg }}
                    </div>
                </div>
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
        if (!window.pywebview || !window.pywebview.api) {
            this.fetchInitialDataForBrowser();
        }
        this.checkAndSendReady();
    },
    methods: {
        async fetchInitialDataForBrowser() {
            try {
                const response = await fetch('/api/plugins/daily/settings', {
                    credentials: 'same-origin'
                });
                if (!response.ok) {
                    console.warn('Failed to fetch daily settings via REST fallback');
                    return;
                }
                const payload = await response.json();
                if (payload && Array.isArray(payload.needs)) {
                    console.log('Loaded daily data via REST fallback');
                    this.dailyData = payload.needs;
                    this.processCategories();
                }
            } catch (error) {
                console.warn('Error fetching daily settings via REST fallback:', error);
            }
        },
        checkAndSendReady() {
            console.log('DAILY: Checking if backend is ready...');
            if (this.dailyData.length === 0) {
                console.log('Backend not ready or dailyData is empty, sending ready message...');
                this.sendMsgToBackend({ socket: "ready" });
                setTimeout(() => {
                    this.checkAndSendReady();
                }, 500);
            }
        },
        $_showAutocomplete() {
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
                    this.dailyData = data.dailyData.needs;
                    // this.tags = data.dailyData.tags;
                    this.processCategories();
                }
                if (data.answers) {
                    this.answers = data.answers;
                    this.currentView = 'answers';
                }
                if (data.backhome) {
                    this.switchToMainView();
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
            if (this.currentView == 'main' || this.currentView == 'secondary') {
                this.currentView = 'loadingAnswers';
                console.warn("ITEM SELECTED");

                this.answers = [];
                this.sendMsgToBackend({
                    action: 'generatePhrases',
                    category: category,
                    theme: item
                });
            }
        },
        /* Sending final phrase */
        async $_chooseAnswer(msg, index) {
            let text = msg;
            const json = { action: "speak", msg: text };
            console.log("sending JSON");
            console.log(json);
            this.sendMsgToBackend(json);
            /* this.switchToMainView(); */
            this.answers = [];
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
.btn-primary{
    font-size: 1.1rem;
    padding: 1.5vh 1vh;
}
.btn-secondary{
    font-size: 1rem;
    padding: 1.2vh 1vh;
}
.answers.secondary {
    display: flex;
    justify-content: center;
}

.answers {
    flex: 1 1 0;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    /* border: 1px solid #0f0;
    /* green box */
    min-height: 0;
}

.columns {
    display: flex;
    flex-direction: row;
    gap: 30px;
    height: 100%;
    width: 100%;
}

.column {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 20px;
}

.answers .msg {
    margin-bottom: 2.2vh;
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

.options.secondary,
.answers {
    padding-left: 5rem;
}

.answers .msg {
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