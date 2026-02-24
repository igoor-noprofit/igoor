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

        <div class="answers" :class="`view-${appview}`">
            <div class="row columns">
                <div v-for="col in ['left', 'center', 'right']" :key="col" :class="['column', col]">
                    <div v-for="(msg, idx) in answers[col]" :key="col + '-' + idx" class="msg-row">
                        <div :class="['msg', 'msg-small', { editing: editingKey === col + '-' + idx }]"
                            :contenteditable="editingKey === col + '-' + idx"
                            :ref="'msg-' + col + '-' + idx"
                            @click="$_chooseAnswer(msg, idx, col)"
                            @keydown.enter.prevent="$_speakEdited(col, idx)">
                            {{ msg }}
                        </div>
                        <button class="btn-edit" @click.stop="$_toggleEdit(col, idx)"
                            :title="editingKey === col + '-' + idx ? t('Speak edited phrase') : t('Edit phrase')">
                            <svg class="icon icon-s">
                                <use xlink:href="/img/svgdefs.svg#icon-pencil"></use>
                            </svg>
                        </button>
                    </div>
                </div>
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
            currentInput: "",
            editingKey: null
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
            this.editingKey = null;
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
                    this.editingKey = null;
                }
            } catch (e) {
                console.warn("Error parsing JSON in FLOW component");
            }
        },
        async $_chooseAnswer(msg, idx, col) {
            // Don't speak if the user is currently editing this phrase
            if (this.editingKey === col + '-' + idx) return;
            // Remove the selected answer from the column
            this.answers[col].splice(idx, 1);
            const json = { action: "speak", msg: msg };
            this.sendMsgToBackend(json);
        },
        $_toggleEdit(col, idx) {
            const key = col + '-' + idx;
            if (this.editingKey === key) {
                // Currently editing → speak the edited text
                this.$_speakEdited(col, idx);
            } else {
                // Enter edit mode
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
        $_showAutocomplete() {
            this.$emit('show-autocomplete');
        }
    }
}
</script>

<style scoped>
.flow.container {
    display: flex;
    flex-direction: row;
    height: 100%;
    flex: 1 1 auto;
}

.answers {
    flex: 1 1 0;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    border: 1px solid #0f0;
    overflow: hidden;
    padding: 1rem;
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
    margin-bottom: 0;
}

.answers .msg-row {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 0.4rem;
    margin-bottom: 2.2vh;
}

.btn-edit {
    flex-shrink: 0;
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 0.25rem;
    border-radius: 0.25rem;
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