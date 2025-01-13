<template>
    <div class="autocomplete plugin" v-show="appview == 'autocomplete'">
        <button class="btn btn-side btn-side-left" @click="$_backToDaily()">
            <svg class="icon icon-l">
                <use xlink:href="/img/svgdefs.svg#icon-chevron_left" />
            </svg>
        </button>

        <div class="autocomplete_input">
            <!-- Show loading or error state -->
            <div v-if="isLoading" class="status-message loading">
                Chargement du dictionnaire...
            </div>
            <div v-else-if="error" class="status-message error">
                {{ error }}
            </div>

            <!-- Input and suggestions -->
            <div v-else>
                <input type="text" v-model="userInput" autocomplete="off" name="autocomplete" placeholder=""
                    ref="autocompleteInput" :disabled="isLoading || error">
                <div class="word-suggestions" v-if="wordSuggestions.length">
                    <button class="btn btn-secondary" v-for="word in wordSuggestions" :key="word" @click="selectWord(word)">
                        {{ word }}
                    </button>
                </div>
            </div>
        </div>

        <button @click="$_speakInput()" class="btn btn-side btn-side-right speak" :disabled="isLoading || error">
            <svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-talk"></use>
            </svg>
            <h3>parler</h3>
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
            maxRetries: 3
        }
    },
    async mounted() {
        await this.loadDictionary();
    },
    methods: {
        $_backToDaily() {
            console.log("back to daily");
            const json = { action: "backToDaily" };
            this.sendMsgToBackend(json);
            this.$_reset();
        },
        $_reset() {
            this.wordSuggestions = [];
            this.userInput = ''
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

        handleError(error) {
            if (error.name === 'TypeError' && !navigator.onLine) {
                return "Pas de connexion internet. Vérifiez votre connexion.";
            }
            if (error instanceof SyntaxError) {
                return "Erreur de chargement du dictionnaire. Format invalide.";
            }
            return "Erreur de chargement du dictionnaire. Veuillez réessayer.";
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
                this.$refs.autocompleteInput.focus();

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

            // Full sentence prediction when space is added
            if (newInput.endsWith(' ') && !oldInput.endsWith(' ')) {
                // Clear any pending timeout
                this.predictFullSentence(newInput);
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
    width: 100%;
}
.answers .msg{
    margin-bottom: 10px;
}


button {
    cursor: pointer;
}
</style>