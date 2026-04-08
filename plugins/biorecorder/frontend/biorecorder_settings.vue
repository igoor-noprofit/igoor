<template>
    <div class="biorecorder-settings">
        <!-- Progress header -->
        <div class="progress-header">
            <span class="progress-text">{{ progress.answered }} / {{ progress.total }}</span>
            <div class="progress-bar">
                <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
            </div>
        </div>

        <!-- Question container (two-column layout) -->
        <div class="question-container" v-if="currentQuestion && !showCompletion">

            <!-- LEFT COLUMN: Question + Voice recording + Navigation -->
            <div class="left">
                <div class="category-header">{{ currentQuestion.category }}</div>
                <div class="question-text">{{ currentQuestion.text }}</div>
                <div class="question-instructions" v-if="currentQuestion.instructions">
                    {{ currentQuestion.instructions }}
                </div>

                <!-- Voice recording: mic button matching asrjs style -->
                <div class="voice-section" v-if="!isTranscribing && !transcriptionText">
                    <div class="mic clickable" :class="{ recording: isRecording }" @click="toggleRecording">
                        <img v-if="!isRecording" src="/img/mic.png" alt="Record">
                        <img v-else src="/img/stop.svg" alt="Stop">
                    </div>
                </div>

                <!-- Transcribing indicator -->
                <div v-if="isTranscribing" class="transcribing">
                    <i class="ph-light ph-spinner ph-spin"></i>
                    <span>{{ t('Transcribing...') }}</span>
                </div>

                <!-- Navigation -->
                <div class="navigation">
                    <button class="btn btn-nav" @click="previousQuestion" :disabled="currentIndex === 0">
                        <i class="ph-light ph-caret-left"></i>
                    </button>
                    <button class="btn btn-nav btn-skip" @click="skipQuestion">
                        {{ t('Skip') }}
                    </button>
                    <!-- On last question: show Finish button instead of disabled arrow -->
                    <button v-if="isLastQuestion" class="btn btn-finish" @click="finishQuestions">
                        {{ t('Finish') }}
                    </button>
                    <button v-else class="btn btn-nav" @click="nextQuestion">
                        <i class="ph-light ph-caret-right"></i>
                    </button>
                </div>
            </div>

            <!-- RIGHT COLUMN: Text/Transcription input -->
            <div class="right">
                <!-- Transcription edit (after voice recording) -->
                <div v-if="transcriptionText && !isTranscribing" class="transcription-edit">
                    <textarea v-model="transcriptionText" class="answer-textarea" @blur="saveTranscription"></textarea>
                </div>

                <!-- Text input -->
                <div v-if="!isTranscribing && !transcriptionText" class="text-input">
                    <textarea
                        v-model="textInput"
                        class="answer-textarea"
                        :placeholder="t('Or type your answer...')"
                        @blur="autoSave"
                    ></textarea>
                </div>
            </div>
        </div>

        <!-- Completion screen -->
        <div class="completion-container" v-if="showCompletion">
            <div class="completion-message">{{ t('Recording complete!') }}</div>
            <div class="completion-info">{{ progress.answered }} {{ t('answers recorded') }}</div>
            <button class="btn btn-generate" @click="generateBio" :disabled="isGenerating || progress.answered === 0">
                <span v-if="isGenerating"><i class="ph-light ph-spinner ph-spin"></i> {{ t('Generating...') }}</span>
                <span v-else><i class="ph-light ph-magic-wand"></i> {{ t('Generate Biography') }}</span>
            </button>

            <button class="btn btn-back" @click="showCompletion = false">
                {{ t('Back to questions') }}
            </button>

            <div v-if="bioExists" class="bio-exists">
                <i class="ph-light ph-check-circle"></i>
                <span>{{ t('Biography generated successfully!') }}</span>
            </div>
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

module.exports = {
    name: "biorecorder-settings",
    mixins: [BasePluginComponent],
    data() {
        return {
            questions: [],
            currentIndex: 0,
            progress: { answered: 0, total: 0, can_generate: false, current_index: 0 },
            textInput: "",
            transcriptionText: "",
            isTranscribing: false,
            isGenerating: false,
            isRecording: false,
            bioExists: false,
            showCompletion: false,
            mediaRecorder: null,
            audioChunks: [],
            recordedBlob: null
        };
    },
    computed: {
        currentQuestion() {
            return this.questions[this.currentIndex] || null;
        },
        progressPercent() {
            return this.progress.total ? (this.progress.answered / this.progress.total) * 100 : 0;
        },
        isLastQuestion() {
            return this.currentIndex >= this.questions.length - 1;
        }
    },
    watch: {
        currentIndex() {
            this.loadCurrentAnswer();
            this.refreshProgress();
        }
    },
    mounted() {
        this.loadData();
        this.checkBioExists();
    },
    methods: {
        handleIncomingMessage(data) {
            const handled = BasePluginComponent.methods.handleIncomingMessage.call(this, data);
            if (handled) return;
        },

        async loadData() {
            try {
                const response = await fetch('/api/plugins/biorecorder/data');
                if (response.ok) {
                    const data = await response.json();
                    this.questions = data.questions;
                    this.progress = data.progress;
                    this.currentIndex = data.progress.current_index || 0;
                    this.loadCurrentAnswer();
                }
            } catch (error) {
                console.error('Error loading data:', error);
            }
        },

        loadCurrentAnswer() {
            const q = this.currentQuestion;
            if (q && q.answer) {
                this.textInput = q.answer;
            } else {
                this.textInput = "";
            }
            this.transcriptionText = "";
        },

        async refreshProgress() {
            try {
                const response = await fetch('/api/plugins/biorecorder/progress');
                if (response.ok) {
                    this.progress = await response.json();
                }
            } catch (error) {
                console.error('Error refreshing progress:', error);
            }
        },

        async checkBioExists() {
            try {
                const response = await fetch('/api/plugins/biorecorder/bio');
                if (response.ok) {
                    const data = await response.json();
                    this.bioExists = data.exists;
                }
            } catch (error) {
                console.error('Error checking bio:', error);
            }
        },

        // --- Save current answer before navigating away ---
        async saveCurrentIfDirty() {
            const q = this.currentQuestion;
            if (!q) return;

            // Save transcription if pending
            if (this.transcriptionText && this.transcriptionText.trim()) {
                const saved = q.answer || "";
                if (this.transcriptionText !== saved) {
                    await this.saveTranscription();
                    return;
                }
            }

            // Save text input if changed
            if (this.textInput && this.textInput.trim()) {
                const saved = q.answer || "";
                if (this.textInput !== saved) {
                    await this.autoSave();
                }
            }
        },

        // --- Voice recording (native MediaRecorder) ---
        toggleRecording() {
            if (this.isRecording) {
                this.stopRecording();
            } else {
                this.startRecording();
            }
        },

        async startRecording() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                this.mediaRecorder = new MediaRecorder(stream);
                this.audioChunks = [];

                this.mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        this.audioChunks.push(event.data);
                    }
                };

                this.mediaRecorder.onstop = () => {
                    this.recordedBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                    stream.getTracks().forEach(track => track.stop());
                    this.uploadAndTranscribe();
                };

                this.mediaRecorder.start();
                this.isRecording = true;
            } catch (error) {
                console.error('Error starting recording:', error);
            }
        },

        stopRecording() {
            if (this.mediaRecorder && this.isRecording) {
                this.mediaRecorder.stop();
                this.isRecording = false;
            }
        },

        async uploadAndTranscribe() {
            if (!this.recordedBlob) return;
            this.isTranscribing = true;

            try {
                const formData = new FormData();
                formData.append('audio_file', this.recordedBlob, 'recording.webm');

                const response = await fetch(`/api/plugins/biorecorder/voice_answer?index=${this.currentIndex}`, {
                    method: 'POST',
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    this.transcriptionText = data.text || "";
                    this.progress = data.progress;
                    // Update the local questions array so navigation picks up the saved answer
                    if (this.questions[this.currentIndex]) {
                        this.questions[this.currentIndex].answer = data.text || "";
                    }
                } else {
                    const error = await response.json();
                    console.error('Transcription failed:', error.detail);
                }
            } catch (error) {
                console.error('Error transcribing:', error);
            } finally {
                this.isTranscribing = false;
            }
        },

        // --- Save methods ---
        async autoSave() {
            if (!this.textInput.trim()) return;
            const q = this.currentQuestion;
            if (q && this.textInput === q.answer) return;

            try {
                const response = await fetch('/api/plugins/biorecorder/answer', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        index: this.currentIndex,
                        answer: this.textInput
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    this.progress = data.progress;
                    // Update local questions array so loadCurrentAnswer picks it up
                    if (this.questions[this.currentIndex]) {
                        this.questions[this.currentIndex].answer = this.textInput;
                    }
                    this.$emit('settings-changed');
                }
            } catch (error) {
                console.error('Error saving answer:', error);
            }
        },

        async saveTranscription() {
            if (!this.transcriptionText.trim()) return;

            try {
                const response = await fetch('/api/plugins/biorecorder/answer', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        index: this.currentIndex,
                        answer: this.transcriptionText
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    this.progress = data.progress;
                    // Update local questions array
                    if (this.questions[this.currentIndex]) {
                        this.questions[this.currentIndex].answer = this.transcriptionText;
                    }
                    this.textInput = this.transcriptionText;
                    this.transcriptionText = "";
                    this.$emit('settings-changed');
                }
            } catch (error) {
                console.error('Error saving transcription:', error);
            }
        },

        // --- Navigation (save before navigating) ---
        async previousQuestion() {
            await this.saveCurrentIfDirty();
            if (this.currentIndex > 0) {
                this.currentIndex--;
            }
        },

        async nextQuestion() {
            await this.saveCurrentIfDirty();
            if (this.currentIndex < this.questions.length - 1) {
                this.currentIndex++;
            }
        },

        async skipQuestion() {
            await this.saveCurrentIfDirty();
            if (this.currentIndex < this.questions.length - 1) {
                this.currentIndex++;
            }
            this.refreshProgress();
        },

        async finishQuestions() {
            await this.saveCurrentIfDirty();
            this.showCompletion = true;
        },

        async generateBio() {
            this.isGenerating = true;

            try {
                const response = await fetch('/api/plugins/biorecorder/generate_bio', {
                    method: 'POST'
                });

                if (response.ok) {
                    this.bioExists = true;
                    this.$emit('settings-changed');
                } else {
                    const error = await response.json();
                    alert(error.detail || 'Generation failed');
                }
            } catch (error) {
                console.error('Error generating bio:', error);
                alert('Failed to generate biography');
            } finally {
                this.isGenerating = false;
            }
        }
    }
};
</script>

<style scoped>
.biorecorder-settings {
    padding: 1.5rem;
    height: 100%;
    display: flex;
    flex-direction: column;
}

/* Progress header */
.progress-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.progress-text {
    font-size: 1rem;
    font-weight: 500;
    min-width: 80px;
}

.progress-bar {
    flex: 1;
    height: 10px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 5px;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    background: var(--color-btn-primary, #216776);
    transition: width 0.3s ease;
}

/* Two-column layout */
.question-container {
    display: flex;
    gap: 2rem;
    flex: 1;
    min-height: 0;
}

.left,
.right {
    width: 48%;
    text-align: left;
    display: flex;
    flex-direction: column;
}

/* Left column styles */
.category-header {
    font-size: 1rem;
    font-weight: bold;
    color: var(--color-accent, #34d399);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.75rem;
}

.question-text {
    font-size: 1.4rem;
    font-weight: 500;
    line-height: 1.4;
    margin-bottom: 1rem;
}

.question-instructions {
    font-size: 0.9rem;
    opacity: 0.7;
    font-style: italic;
    margin-bottom: 1rem;
    line-height: 1.4;
}

/* Mic button - matches asrjs style */
.voice-section {
    margin-top: 1.5rem;
    display: flex;
    justify-content: center;
}

.mic {
    width: 120px;
    height: 120px;
    display: flex;
    justify-content: center;
    align-items: center;
    cursor: pointer;
    border-radius: 50%;
    transition: background 0.2s ease;
}

.mic.clickable:hover {
    background: rgba(255, 255, 255, 0.1);
}

.mic img {
    max-height: 60px;
    max-width: 60px;
}

.mic.recording {
    background: rgba(220, 38, 38, 0.3);
    animation: pulse 1s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}

.transcribing {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 1.5rem;
    font-size: 1rem;
    opacity: 0.8;
    justify-content: center;
}

/* Navigation */
.navigation {
    display: flex;
    justify-content: space-between;
    margin-top: auto;
    padding-top: 1.5rem;
}

.btn {
    padding: 1rem 1.5rem;
    font-size: 1.2rem;
    font-weight: 500;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    min-width: 80px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.btn-nav {
    background: rgba(255, 255, 255, 0.1);
    color: var(--color-text, #333);
    border: 1px solid rgba(255, 255, 255, 0.2);
}

.btn-nav:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.2);
}

.btn-nav:disabled {
    opacity: 0.3;
    cursor: not-allowed;
}

.btn-skip {
    background: rgba(255, 255, 255, 0.05);
    min-width: 120px;
}

.btn-finish {
    background: var(--color-btn-primary, #216776);
    color: white;
    min-width: 120px;
    font-weight: bold;
}

.btn-finish:hover {
    background: var(--color-btn-rollover-primary, #2a8fa8);
}

/* Right column - textarea */
.answer-textarea {
    width: 100%;
    max-width: 100%;
    min-height: 200px;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 8px;
    padding: 1rem;
    color: inherit;
    font-size: 1rem;
    resize: vertical;
    font-family: inherit;
    line-height: 1.4;
    box-sizing: border-box;
}

.answer-textarea:focus {
    outline: none;
    border-color: var(--color-btn-primary, #216776);
}

/* Completion container */
.completion-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex: 1;
    gap: 1.5rem;
    text-align: center;
}

.completion-message {
    font-size: 1.5rem;
    font-weight: bold;
}

.completion-info {
    font-size: 1rem;
    opacity: 0.7;
}

.btn-generate {
    padding: 1rem 2.5rem;
    font-size: 1.2rem;
    font-weight: bold;
    background: var(--color-btn-primary, #216776);
    color: white;
    border: none;
    border-radius: 12px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.btn-generate:hover:not(:disabled) {
    background: var(--color-btn-rollover-primary, #2a8fa8);
}

.btn-generate:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.btn-back {
    padding: 0.75rem 1.5rem;
    font-size: 1rem;
    background: rgba(255, 255, 255, 0.1);
    color: var(--color-text, #333);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 8px;
    cursor: pointer;
}

.btn-back:hover {
    background: rgba(255, 255, 255, 0.2);
}

.bio-exists {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: var(--color-accent, #34d399);
    font-size: 1rem;
}
</style>
