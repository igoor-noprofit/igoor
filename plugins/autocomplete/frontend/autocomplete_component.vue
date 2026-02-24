<template>
    <div class="autocomplete plugin">
        <button class="btn btn-side btn-side-left" @click="$_deleteText()" :disabled="!userInput.trim()"> 
            <svg class="icon icon-l">
                <use xlink:href="/img/svgdefs.svg#icon-close" />
            </svg>
            <h3>{{ t("Empty") }}</h3>
        </button>

        <div class="autocomplete_input">
            <!-- Show loading or error state -->
            <div v-if="isLoading" class="status-message loading">
                {{ t("Loading dictionary...") }}
            </div>
            <div v-else-if="error" class="status-message error">
                {{ error }}
            </div>

            <!-- Input and suggestions -->
            <div v-else class="input-container" ref="autocompleteInput" 
                 @click="$_focusInput" 
                 @focus="$_onFocus" 
                 @blur="$_onBlur"
                 @keydown="$_handleKeydown"
                 tabindex="0">
                <span class="typed-text">{{ userInput }}</span><span class="cursor" v-if="isFocused">|</span>
                <button v-for="(pred, idx) in shortPredictions" 
                        :key="idx"
                        class="inline-prediction btn btn-primary" 
                        @click.stop="$_applyPrediction(idx)">
                    {{ pred.trimStart() }}
                </button>
                <span v-if="!userInput && shortPredictions.length === 0" class="placeholder">{{ t('say something...') }}</span>
            </div>

        </div>

      
        <button @click="$_speakInput()" class="btn btn-side btn-side-right speak"
            :disabled="isLoading || error || !userInput.trim()">
            <svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-talk"></use>
            </svg>
            <h3>{{ t("say the phrase") }}</h3>
        </button>
    </div>
    <!------------------------------ VIRTUAL KEYBOARD ------------------------>
    <div class="keyboard" v-show="showKeyboard">
        <button class="btn btn-side btn-side-left btn-side-hilite" @click="$_deleteLastWord" style="color: white;">
            <svg class="icon icon-l" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
                <g fill="none" stroke="#ffffff">
                    <path
                        d="M33.3 10a1.7 1.7 0 0 1 1.7 1.7v16.6a1.7 1.7 0 0 1-1.7 1.7H15l-8.3-8.3a2.5 2.5 0 0 1 0-3.4L15 10h18.3Z"
                        stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                    <text x="20" y="23" font-size="10" stroke="none" fill="#ffffff" text-anchor="middle"
                        style="font-family: sans-serif; font-weight: bold;">ABC</text>
                </g>
            </svg>
        </button>
        <div class="word-suggestions" v-if="wordSuggestions.length">
            <button class="btn btn-secondary" v-for="word in wordSuggestions" :key="word" @click="selectWord(word)">
                {{ word }}
            </button>
        </div>
        <div class="keyboard-row">
            <button class="btn btn-key btn-key-func" v-for="num in '1234567890'" :key="num" @click="$_typeKey(num)">{{
                num }}</button>
        </div>
        <div class="keyboard-row">
            <button class="btn btn-key" v-for="letter in 'azertyuiop'" :key="letter" @click="$_typeKey(letter)">{{
                letter }}</button>
        </div>
        <div class="keyboard-row">
            <button class="btn btn-key" v-for="letter in 'qsdfghjklm'" :key="letter" @click="$_typeKey(letter)">{{
                letter
                }}</button>
        </div>
        <div class="keyboard-row">
            <button class="btn btn-key" v-for="letter in 'wxcvbn'" :key="letter" @click="$_typeKey(letter)">{{ letter
                }}</button>
        </div>
        <div class="keyboard-row">
            <button class="btn btn-key btn-key-func" @click="$_typeKey(':')">:</button>
            <button class="btn btn-key btn-key-func" @click="$_typeKey(',')">,</button>
            <button class="btn btn-key btn-key-space" @click="$_typeKey(' ')">espace</button>
            <button class="btn btn-key btn-key-func" @click="$_typeKey('!')">!</button>
            <button class="btn btn-key btn-key-func" @click="$_typeKey('?')">?</button>
        </div>

        <button class="btn btn-side btn-side-right btn-side-hilite" @click="$_backspace">
            <svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-backspace" />
            </svg>
        </button>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

module.exports = {
    name: "autocomplete",
    mixins: [BasePluginComponent],
    data() {
        return {
            userInput: "",
            wordSuggestions: [],
            prefixDictionary: null,
            isLoading: true,
            error: null,
            retryCount: 0,
            maxRetries: 3,
            showKeyboard: false,
            allowVirtualKeyboard: false,
            shortPredictions: [],
            shortPredictionTimeout: null,
            isFocused: false
        }
    },
    async mounted() {
        if (this.allowVirtualKeyboard){
            await this.loadDictionary();
        }  
        else{
            this.isLoading=false;
        }
    },
    methods: {
        /* async $_pasteFromClipboard() {
            try {
                const text = await navigator.clipboard.readText();
                if (text) {
                    this.userInput += (this.userInput && !this.userInput.endsWith(' ')) ? ' ' : '';
                    this.userInput += text;
                    this.$refs.autocompleteInput.focus();
                }
            } catch (e) {
                this.error = "Impossible de coller depuis le presse-papiers.";
            }
        },*/
        $_showKeyboard() {
            this.showKeyboard = false;  // Changed from isInputFocused
        },
        $_hideKeyboard() {
            this.showKeyboard = false;  // Changed from isInputFocused
        },
        $_onFocus() {
            this.isFocused = true;
        },
        $_onBlur() {
            this.isFocused = false;
        },
        $_deleteText(){
            this.$_reset();
            this.$_focusInput();
        },
        $_backToDaily() {
            console.log("back to daily");
            const json = { action: "backToDaily" };
            this.sendMsgToBackend(json);
            this.$_reset();
        },
        $_focusInput() {
            if (this.$refs.autocompleteInput) {
                this.$refs.autocompleteInput.focus();
            }
        },
        $_reset() {
            this.wordSuggestions = [];
            this.userInput = '';
            this.shortPredictions = [];
            this.$_hideKeyboard();
        },
        async $_fetchShortPredictions() {
            if (!this.userInput || this.userInput.trim().length < 2) {
                this.shortPredictions = [];
                return;
            }
            
            try {
                const response = await this.callPluginRestEndpoint('autocomplete', 'short-predictions', {
                    method: 'POST',
                    data: { input: this.userInput }
                });
                this.shortPredictions = response.predictions || [];
            } catch (e) {
                console.error('Error fetching short predictions:', e);
                this.shortPredictions = [];
            }
        },
        $_applyPrediction(index) {
            if (this.shortPredictions[index]) {
                const prediction = this.shortPredictions[index];
                // Store the input and completion before updating userInput
                const inputText = this.userInput;
                const completion = prediction + ' ';
                console.log('Storing prediction:', inputText, '->', completion);
                // Send to backend to store the prediction
                this.sendMsgToBackend({
                    action: "prediction_selected",
                    input: inputText,
                    completion: completion
                });
                // Prediction already includes leading space if needed
                this.userInput += completion;
                this.shortPredictions = [];
                // Restore focus
                this.$_focusInput();
                // Trigger full sentence prediction (LLM)
                this.predictFullSentence(this.userInput);
            }
        },
        $_handleKeydown(event) {
            // Handle keyboard input for the div-based input field
            if (event.key === 'Backspace') {
                this.userInput = this.userInput.slice(0, -1);
                event.preventDefault();
            } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey) {
                // Regular character input
                this.userInput += event.key;
                event.preventDefault();
            } else if (event.key === 'Enter') {
                this.$_speakInput();
                event.preventDefault();
            }
        },
        async loadDictionary() {
            this.isLoading = true;
            this.error = null;

            try {
                const response = await fetch('/dictionary/french_dictionary_prefix.json');
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                this.prefixDictionary = await response.json();
                this.isLoading = false;
                this.retryCount = 0;
            } catch (error) {
                console.error('Error loading dictionary:', error);
                this.error = this.handleError(error);

                // Retry logic
                if (this.retryCount < this.maxRetries) {
                    this.retryCount++;
                    console.log(`Retrying dictionary load (attempt ${this.retryCount})...`);
                    setTimeout(() => this.loadDictionary(), 2000); // Retry after 2 seconds
                }
            }
        },
        $_deleteLastWord() {
            const words = this.userInput.trim().split(' ');
            if (words.length > 0) {
                words.pop(); // Remove the last word
                this.userInput = words.join(' ');
                if (this.userInput) {
                    this.userInput += ' '; // Add space if there are remaining words
                }
            }
        },
        handleError(error) {
            if (error.name === 'TypeError' && !navigator.onLine) {
                return "Pas de connexion internet. Vérifiez votre connexion.";
            }
            if (error instanceof SyntaxError) {
                return "Erreur de chargement du dictionnaire. Format invalide.";
            }
            return "Erreur de chargement du dictionnaire. Veuillez réessayer.";
        },
        handleIncomingMessage(event) {
            // First let base component handle common cases
            const handled = BasePluginComponent.methods.handleIncomingMessage.call(this, event);
            if (handled) return true;
            
            try {
                const data = JSON.parse(event.data);
                if (data.action === 'clear') {
                    this.$_reset();
                    return true;
                }
            } catch (e) {
                console.warn("Error parsing message in autocomplete:", e);
            }
            return false;
        },

        predictWords(input) {
            if (!input || !this.prefixDictionary) return [];

            try {
                const words = input.split(' ');
                const currentWord = words[words.length - 1].toLowerCase();

                // if (currentWord.length < 1) return [];

                return (this.prefixDictionary[currentWord] || []).slice(0, 5);
            } catch (error) {
                console.error('Error predicting words:', error);
                return [];
            }
        },
        selectWord(word) {
            try {
                const words = this.userInput.split(' ');
                words[words.length - 1] = word;
                this.userInput = words.join(' ') + ' ';
                this.$_focusInput()
                // Trigger full sentence prediction when word is selected
                // this.predictFullSentence(this.userInput);
            } catch (error) {
                console.error('Error selecting word:', error);
            }
        },
        predictFullSentence(input) {
            // Send the entire input to backend for prediction
            const json = {
                action: "predict",
                msg: input.trim()
            };
            this.sendMsgToBackend(json);
        },
        $_typeKey(key) {
            this.userInput += key;
            this.$refs.autocompleteInput.focus(); // Keep focus on input
        },
        $_backspace() {
            this.userInput = this.userInput.slice(0, -1);
            this.$refs.autocompleteInput.focus(); // Keep focus on input
        },
        $_speak(msg) {
            this.$_clean();
            const json = { action: "speak", msg: msg };
            console.log("sending JSON");
            console.log(json);
            this.completion = "";
            this.sendMsgToBackend(json);
        },
        $_speakInput() {
            this.$_speak(this.userInput)
        },
        $_clean() {
            this.userInput = ""; // Force refresh of this.input
        }
    },
    watch: {
        userInput(newInput, oldInput) {
            // Word suggestions
            if (newInput && !this.isLoading && !this.error) {
                this.wordSuggestions = this.predictWords(newInput);
            } else {
                this.wordSuggestions = [];
            }
            
            // Short predictions with debouncing
            if (this.shortPredictionTimeout) {
                clearTimeout(this.shortPredictionTimeout);
            }
            
            const isSpaceAdded = newInput.endsWith(' ') && !oldInput.endsWith(' ');
            
            // Fetch short predictions if input is long enough
            if (newInput && newInput.trim().length >= 2) {
                if (isSpaceAdded) {
                    // Immediate fetch when space is added (faster, local)
                    this.$_fetchShortPredictions();
                } else {
                    // Debounce during rapid typing
                    this.shortPredictionTimeout = setTimeout(() => {
                        this.$_fetchShortPredictions();
                    }, 150);
                }
            } else {
                this.shortPredictions = [];
            }
            
            // Full sentence prediction when space is added (LLM, slower)
            // Delay slightly to let short predictions render first
            if (isSpaceAdded) {
                if (this.predictionTimeout) {
                    clearTimeout(this.predictionTimeout);
                }
                this.predictionTimeout = setTimeout(() => {
                    this.predictFullSentence(newInput);
                }, 100);
            }
        }
    }
};
</script>

<style scoped>

.status-message {
    text-align: center;
    padding: 1rem;
    margin: 1rem 0;
    border-radius: 4px;
}

.status-message.loading {
    background-color: #f0f0f0;
    color: #666;
}

.status-message.error {
    background-color: #fff3f3;
    color: #d63031;
    border: 1px solid #ff7675;
}

.word-suggestions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.5rem;
}

.suggestion-btn {
    padding: 0.25rem 0.5rem;
    border: 1px solid #ccc;
    border-radius: 4px;
    background: white;
}

.autocomplete.plugin {
    height: 10vh;
}

.answers{
    border: 1px solid #0ff;
}
.answers .msg {
    margin-bottom: 10px;
}

.btn-side{
    position: relative;
    height: auto !important;
}


.btn-side-left:disabled {
    opacity: 1;
}

.btn-side-right.speak:disabled svg {
    opacity: 0.6;
}
.btn-side-left:disabled svg, .btn-side-left:disabled h3{
    opacity: 0.2;

}

.btn-side-right.speak:disabled svg use {
    stroke: #666666;
    fill: #666666;
}

.btn-side-right.speak:disabled h3 {
    color: #666666;
}

button {
    cursor: pointer;
}
.input-container{
    height: 100%;
    width: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 0 12px;
    min-height: 48px;
    cursor: text;
    outline: none;
    color: #fff;
    background-color: #28373b;
}
.input-container input{
    height: 100% !important;
}
.typed-text {
    color: #fff;
    white-space: pre;
}
.cursor {
    color: #0095c0;
    animation: blink 1s infinite;
    font-weight: bold;
}
@keyframes blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
}
.placeholder {
    color: #999;
    font-style: italic;
}
.inline-prediction {
    color: white;
    border: none;
    border-radius: 6px;
    padding: 14px;
    margin-left: 8px;
    font-size: 1em;
    font-weight: 500;
    transition: all 0.2s ease;
    white-space: nowrap;
}
.inline-prediction:hover {
    background: #0095c0;
    transform: scale(1.02);
}
.inline-prediction:active {
    background: #23515b;
}
</style>