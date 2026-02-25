<template>
    <div class="daily container daily-plugin main" :class="{ 'plugin-error': error }" v-if="appview == 'daily'">
        <!-- Back Arrow -->
        <div v-if="currentView === 'main'" class="options">
            <div v-for="(category, index) in mainCategories" :key="index" class="options-col">
                <h3>{{ translateCategory(category.name) }}</h3>
                <button v-for="(item, key) in category.items" :key="key" class="btn"
                    :class="{ 'btn-primary': item.fixed, 'btn-secondary': !item.fixed, 'btn-selected-glow': isSelected(category.name, key) }"
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
            <div class="options container">
                <div v-for="(category, index) in secondaryCategories" :key="index" class="options-col"
                    v-show="hasCategoryItems(category)">
                    <h3>{{ translateCategory(category.name) }}</h3>
                    <button v-for="(item, key) in category.items" :key="key" class="btn"
                        :class="{ 'btn-primary': item.fixed, 'btn-secondary': !item.fixed, 'btn-selected-glow': isSelected(category.name, key) }"
                        @click="selectItem(category.name, key, item)">
                        {{ translateItem(key) }}
                    </button>
                </div>
            </div>

        </div>
        <div class="answers" v-if="currentView == 'answers'">
            <button class="btn btn-side btn-side-left" @click="switchToMainView"><svg class="icon icon-l">
                    <use xlink:href="/img/svgdefs.svg#icon-chevron_left" />
                </svg></button>
            <div class="row columns">
                <div v-for="col in ['left', 'center', 'right']" :key="col" :class="['column', col]">
                    <div v-if="answers[col] && answers[col].length > 0" class="column-mood-icon">
                        <svg class="icon icon-m">
                            <use :xlink:href="'/img/svgdefs.svg#' + moodIcons[col]"></use>
                        </svg>
                    </div>
                    <div v-for="(msg, idx) in answers[col]" :key="col + '-' + idx" class="msg-row">
                        <div :class="['msg', 'msg-small', { editing: editingKey === col + '-' + idx }]"
                            :contenteditable="editingKey === col + '-' + idx" :ref="'msg-' + col + '-' + idx"
                            @click="$_chooseAnswer(msg, idx, col)" @keydown.enter.prevent="$_speakEdited(col, idx)">
                            {{ msg }}
                        </div>
                        <button class="btn-edit rounded" @click.stop="$_toggleEdit(col, idx)"
                            :title="editingKey === col + '-' + idx ? t('Speak edited phrase') : t('Edit phrase')">
                            <svg class="icon icon-m">
                                <use xlink:href="/img/svgdefs.svg#icon-pencil"></use>
                            </svg>
                        </button>
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
            answers: [],
            selectedItem: null,
            editingKey: null
        };
    },
    computed: {
        moodIcons() {
            return {
                left: 'icon-sun-high',
                center: 'icon-cloud',
                right: 'icon-cloud-rain'
            };
        }
    },
    mounted() {
        console.log('DAILY MOUNTED');
        const backendApiPromise = typeof window !== 'undefined' && typeof window.ensureBackendApi === 'function'
            ? window.ensureBackendApi()
            : Promise.resolve(null);

        backendApiPromise
            .then((api) => {
                if (!api || api.isBridgeAvailable === false) {
                    this.fetchInitialDataForBrowser();
                }
            })
            .catch((error) => {
                console.warn('Failed to resolve backendApi, using REST fallback:', error);
                this.fetchInitialDataForBrowser();
            });

        this.checkAndSendReady();
    },
    methods: {
        isSelected(category, key) {
            return this.selectedItem && this.selectedItem.category === category && this.selectedItem.itemKey === key;
        },
        hasCategoryItems(category) {
            const items = category && category.items;
            if (!items) return false;
            if (Array.isArray(items)) return items.length > 0;
            return Object.keys(items).length > 0;
        },
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
                this.selectedItem = { category, itemKey: item };
                this.sendMsgToBackend({
                    action: 'generatePhrases',
                    category: category,
                    theme: item
                });
            }
        },
        /* Sending final phrase */
        async $_chooseAnswer(msg, idx, col) {
            if (this.editingKey === col + '-' + idx) return;
            let text = msg;
            const json = { action: "speak", msg: text };
            console.log("sending JSON");
            console.log(json);
            this.sendMsgToBackend(json);
            /* this.switchToMainView(); */
            this.answers = [];
            this.selectedItem = null;
            this.editingKey = null;
        },
        $_toggleEdit(col, idx) {
            const key = col + '-' + idx;
            if (this.editingKey === key) {
                this.$_speakEdited(col, idx);
            } else {
                this.editingKey = key;
                this.$nextTick(() => {
                    const refKey = 'msg-' + key;
                    const el = this.$refs[refKey];
                    if (el) {
                        const target = Array.isArray(el) ? el[0] : el;
                        target.focus();
                    }
                });
            }
        },
        $_speakEdited(col, idx) {
            const refKey = 'msg-' + col + '-' + idx;
            const el = this.$refs[refKey];
            const target = el ? (Array.isArray(el) ? el[0] : el) : null;
            const editedText = target ? target.innerText.trim() : '';
            if (editedText) {
                this.answers[col].splice(idx, 1);
                const json = { action: "speak", msg: editedText };
                this.sendMsgToBackend(json);
            }
            this.editingKey = null;
        },
        switchToSecondaryView() {
            this.currentView = 'secondary';
        },
        switchToMainView() {
            this.currentView = 'main';
            this.selectedItem = null;
        }
    }
};
</script>

<style scoped>
.daily-plugin {
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
}

.btn-primary {
    font-size: 1.1rem;
    padding: 1.5vh 1vh;
}

.btn-secondary {
    font-size: 1rem;
    padding: 1.2vh 1vh;
    background-color: var(--color-btn-base);
}

.answers.secondary {
    display: flex;
    justify-content: center;
}


.answers {
    flex: 1 1 0;
    display: flex;
    flex-direction: row;
    justify-content: flex-start;
    /* border: 1px solid #0f0;
    /* green box */
    min-height: 0;
    padding-left: 0;

}

.columns {
    display: flex;
    flex-direction: row;
    gap: 30px;
}

.column {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    padding: 20px;
}

.answers .msg {
    margin-bottom: 0;
}

.answers .msg-row {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 1rem;
    margin-bottom: 2.2vh;
}

.btn-edit {
    flex-shrink: 0;
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.25);
    cursor: pointer;
    padding: 0.4rem;
    opacity: 0.4;
    transition: opacity 0.2s;
}

.btn-edit:hover {
    opacity: 1;
}

.btn-edit .icon {
    display: block;
    stroke: currentColor;
    fill: none;
    color: var(--color-text, #fff);
}

.msg.editing {
    outline: 1px dashed rgba(255, 255, 255, 0.5);
    cursor: text;
}

.msg[contenteditable="true"] {
    outline-offset: 4px;
}

.column-mood-icon {
    display: flex;
    justify-content: center;
    margin-bottom: 1.2vh;
    opacity: 0.45;
}

.column-mood-icon .icon {
    stroke: currentColor;
    fill: none;
    color: var(--color-text, #fff);
}

.answers .columns {
    flex: 1 1 auto;
    min-width: 0;
    width: auto;
}

.main {
    position: relative;
    z-index: 10;
    box-shadow: 0rem -0.5rem 1rem 0rem rgba(0, 0, 0, 0.2);
    overflow: hidden;
    height: 100%;
    width: 100%;
    display: flex;
    flex-direction: column;
    flex: 1 1 auto;
    min-height: 0;
    gap: 1rem;
}

.options {
    padding: 1rem;
    padding-right: 5rem;
    display: flex;
    gap: 1rem;
    flex: 1 1 auto;
    align-items: stretch;
    min-height: 0;
    position: relative;
}

.options.secondary {
    padding: 0;
    display: flex;
    flex-direction: row;
    align-items: stretch;
}

.options.container {
    flex: 1 1 auto;
    min-width: 0;
    min-height: 0;
    padding: 1rem;
    display: flex;
    flex-direction: row;
    align-items: stretch;
}

.btn-side-left {
    width: 120px;
    position: relative;
}

.answers .msg {
    margin-bottom: 10px;
}

.options .btn {
    text-align: left;
}

.options-col {
    display: flex;
    flex: 1 1 0;
    min-width: 0;
    flex-direction: column;
    gap: 0.5rem;
}

.options-col .btn {
    width: 100%;
    flex: 1 1 0;
    min-height: 0;
    display: flex;
    align-items: center;
    justify-content: flex-start;
}

.options-col .btn:active {
    background: var(--color-btn-rollover-base) !important;
}

.options-col .btn-primary {
    flex-grow: 1.15;
}

.options-col .btn-secondary {
    flex-grow: 1;
}

.options-col .btn.btn-selected-glow {
    background-color: #ff4500 !important;
}
</style>