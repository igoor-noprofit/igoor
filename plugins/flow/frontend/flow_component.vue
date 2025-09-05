<template>
    <div class="flow container flow-plugin" :class="{ 'plugin-error': error }"
        v-if="appview != 'daily' && appview != 'onboarding'">

        <button v-if="answers"
            :class="['btn', 'btn-side', 'btn-side-left', 'abandon', appview == 'autocomplete' ? 'autocomplete' : '', $root.headerExpanded ? 'expanded' : '']"
            @click="$_abandonConversation(true)">
            <svg class="icon icon-l">
                <use xlink:href="/img/svgdefs.svg#icon-chevron_left"></use>
            </svg>
            {{ t('Change topic') }}
        </button>

        <div class="answers">
            <div class="row columns">
                <div v-for="col in ['left', 'center', 'right']" :key="col" :class="['column', col]">
                    <div v-for="(msg, idx) in answers[col]" :key="col + '-' + idx" class="msg msg-small"
                        @click="$_chooseAnswer(msg, idx, col)">
                        {{ msg }}
                    </div>
                </div>
                <!--a class="autocompletelauncher msg msg-small" @click="$_showAutocomplete()"
                    v-show="appview != 'autocomplete'">
                    <img src="/img/icons/src/keyboard.svg" />
                    <img src="/img/icons/src/more.svg" />
                </a-->
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
            answersRaw: [],
            answers: { left: [], center: [], right: [] },
            waitingai: true,
            currentInput: ""
        }
    },
    methods: {
        async $_abandonConversation(trigger_hook = false) {
            try {
                if (trigger_hook) {
                    this.sendMsgToBackend({ "action": "abandon_conversation" });
                }
                this.$_clearAnswers()
            } catch (error) {
                console.error("Error abandoning conversation:", error);
            }
        },
        $_clearAnswers() {
            this.answersRaw = [];
            this.answers = { left: [], center: [], right: [] };
            this.currentInput = "";
        },
        handleIncomingMessage(event) {
            const handled = BasePluginComponent.methods.handleIncomingMessage.call(this, event);
            if (handled) return true;
            let data;
            try {
                data = JSON.parse(event.data);
                if (data.action) {
                    switch (data.action) {
                        case 'abandon_conversation':
                            this.$_abandonConversation(data.trigger_hook);
                            break;
                        case 'clear_answers':
                            this.$_clearAnswers();
                            break;
                        default:
                            break;
                    }
                } else {
                    // Organise answers into columns for new JSON structure or accept autocomplete completions
                    if (data.answers && typeof data.answers === 'object') {
                        this.answersRaw = data.answers;
                        this.answers = {
                            left: data.answers.left || [],
                            center: data.answers.center || [],
                            right: data.answers.right || []
                        };
                        this.currentInput = data.input || "";
                    } else if (Array.isArray(data.completions)) {
                        // Map completions (array) to single-element columns: left, center, right
                        const comps = data.completions;
                        this.answersRaw = { input: data.input || "", completions: comps.slice() };
                        this.answers = {
                            left: comps[0] ? [comps[0]] : [],
                            center: comps[1] ? [comps[1]] : [],
                            right: comps[2] ? [comps[2]] : []
                        };
                        this.currentInput = data.input || "";
                    } else {
                        this.answersRaw = [];
                        this.answers = { left: [], center: [], right: [] };
                        this.currentInput = "";
                    }
                    this.selectedCard = null;
                }
            } catch (e) {
                console.warn("Error parsing JSON in FLOW component");
            }
        },
        async $_chooseAnswer(msg, idx, col) {
            // Remove the selected answer from the column
            this.answers[col].splice(idx, 1);
            const json = { action: "speak", msg: msg };
            this.sendMsgToBackend(json);
        },
        $_showAutocomplete() {
            this.$emit('show-autocomplete');
        }
    }
}
</script>

<style scoped>
.flow.container {
    display: flex;
    flex-direction: column;
    height: 100%;
}

.answers {
    flex: 1 1 0;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    /* border: 1px solid #0f0;
    /* green box */
    min-height: 0;
    /* prevents overflow issues */
    width: calc(100% - 120px);
    margin-left: 120px;
    margin-top: 1rem;
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

.autocompletelauncher {
    cursor: pointer;
    margin-top: 10px;
    padding-top: 10px;
    padding-bottom: 8px;
    display: block;
    width: 100px;
    min-height: 40px;
}
.autocompletelauncher img{
    filter: invert(1)
}
</style>