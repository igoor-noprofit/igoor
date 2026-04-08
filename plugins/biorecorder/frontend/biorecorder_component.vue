<template>
    <div class="biorecorder">
        <!-- Progress header -->
        <div class="progress-header">
            <div class="progress-text">{{ t('progress') }}: {{ progress.answered }} {{ t('of') }} {{ progress.total }}</div>
            <div class="progress-bar">
                <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
            </div>
        </div>

        <!-- Question display -->
        <div class="question-container" v-if="currentQuestion && !isComplete">
            <div class="category-header">{{ currentQuestion.category }}</div>
            <div class="question-text">{{ currentQuestion.text }}</div>
            <div class="question-instructions" v-if="currentQuestion.instructions">
                {{ currentQuestion.instructions }}
            </div>

            <!-- Existing answer -->
            <div class="existing-answer" v-if="currentQuestion.answer">
                <div class="answer-label">{{ t('current_answer') || 'Your answer:' }}</div>
                <div class="answer-text">{{ currentQuestion.answer }}</div>
            </div>

            <!-- Transcription preview -->
            <div class="transcription-area" v-if="isTranscribing">
                <div class="transcribing-indicator">{{ t('transcribing') }}</div>
            </div>
            <div class="transcription-edit" v-if="transcriptionText && !isTranscribing">
                <textarea
                    v-model="transcriptionText"
                    class="transcription-textarea"
                    :placeholder="t('edit_transcription')"
                ></textarea>
                <button class="btn-primary btn-save-transcription" @click="saveTranscription">
                    {{ t('save_transcription') }}
                </button>
            </div>

            <!-- Input methods (only show if not transcribing and no transcription pending) -->
            <div class="input-methods" v-if="!isTranscribing && !transcriptionText">
                <!-- Voice input -->
                <div class="voice-input">
                    <button
                        class="btn-record"
                        :class="{ recording: isRecording }"
                        @click="toggleRecording"
                        :disabled="isRecording">
                        <img v-if="!isRecording" src="/img/mic.svg" alt="Record" class="btn-icon">
                        <img v-else src="/img/stop.svg" alt="Stop" class="btn-icon">
                        <span>{{ isRecording ? t('recording') : t('voice') }}</span>
                    </button>
                </div>

                <!-- OR divider -->
                <div class="or-divider">{{ t('or') }}</div>

                <!-- Text input -->
                <div class="text-input">
                    <textarea
                        v-model="textInput"
                        class="answer-textarea"
                        :placeholder="t('type_answer')"
                    ></textarea>
                    <button
                        class="btn-primary btn-save-text"
                        @click="saveTextAnswer"
                        :disabled="!textInput.trim()">
                        {{ t('save_answer') }}
                    </button>
                </div>
            </div>

            <!-- Navigation -->
            <div class="navigation">
                <button class="btn-nav" @click="previousQuestion" :disabled="currentIndex === 0">
                    {{ t('previous') }}
                </button>
                <button class="btn-nav btn-skip" @click="skipQuestion">
                    {{ t('skip') }}
                </button>
                <button class="btn-nav" @click="nextQuestion" :disabled="currentIndex >= questions.length - 1">
                    {{ t('next') }}
                </button>
            </div>
        </div>

        <!-- Completion screen -->
        <div class="completion-container" v-if="isComplete">
            <div class="completion-message">{{ t('all_questions_answered') }}</div>
            <button class="btn-generate" @click="generateBio" :disabled="isGenerating">
                {{ isGenerating ? t('generating') : t('generate_biography') }}
            </button>
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';

module.exports = {
    name: "biorecorder",
    mixins: [BasePluginComponent],
    data() {
        return {
            questions: [],
            currentIndex: 0,
            progress: { answered: 0, total: 0, current_index: 0, is_complete: false },
            textInput: "",
            transcriptionText: "",
            isRecording: false,
            isTranscribing: false,
            isGenerating: false,
            mediaRecorder: null,
            audioChunks: [],
            recordedBlob: null
        };
    },
    computed: {
        currentQuestion() {
            if (this.questions.length > 0 && this.currentIndex >= 0 && this.currentIndex < this.questions.length) {
                return this.questions[this.currentIndex];
            }
            return null;
        },
        progressPercent() {
            if (this.progress.total === 0) return 0;
            return (this.progress.answered / this.progress.total) * 100;
        },
        isComplete() {
            return this.progress.is_complete;
        }
    },
    mounted() {
        this.loadData();
    },
    methods: {
        handleIncomingMessage(data) {
            const handled = BasePluginComponent.methods.handleIncomingMessage.call(this, data);
            if (handled) return;

            let messageData = data;
            if (data instanceof MessageEvent) {
                messageData = data.data;
            }
            if (typeof messageData === 'string') {
                try {
                    messageData = JSON.parse(messageData);
                } catch (e) {
                    return;
                }
            }

            if (messageData.type === 'progress') {
                this.progress = {
                    answered: messageData.answered,
                    total: messageData.total,
                    current_index: messageData.current_index,
                    is_complete: messageData.is_complete
                };
            }
        },

        async loadData() {
            try {
                const response = await fetch('/api/plugins/biorecorder/data');
                const data = await response.json();
                this.questions = data.questions;
                this.progress = data.progress;
                this.currentIndex = data.progress.current_index;
            } catch (error) {
                console.error('Error loading data:', error);
            }
        },

        async toggleRecording() {
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
                alert('Could not access microphone');
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

                const data = await response.json();
                this.transcriptionText = data.text || "";
                this.progress = data.progress;
            } catch (error) {
                console.error('Error transcribing:', error);
                alert('Transcription failed');
            } finally {
                this.isTranscribing = false;
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

                const data = await response.json();
                this.progress = data.progress;
                this.transcriptionText = "";
                this.recordedBlob = null;
                this.textInput = "";

                // Move to next unanswered
                if (this.progress.current_index !== this.currentIndex) {
                    this.currentIndex = this.progress.current_index;
                }
            } catch (error) {
                console.error('Error saving transcription:', error);
            }
        },

        async saveTextAnswer() {
            if (!this.textInput.trim()) return;

            try {
                const response = await fetch('/api/plugins/biorecorder/answer', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        index: this.currentIndex,
                        answer: this.textInput
                    })
                });

                const data = await response.json();
                this.progress = data.progress;
                this.textInput = "";

                // Move to next unanswered
                if (this.progress.current_index !== this.currentIndex) {
                    this.currentIndex = this.progress.current_index;
                }
            } catch (error) {
                console.error('Error saving answer:', error);
            }
        },

        previousQuestion() {
            if (this.currentIndex > 0) {
                this.currentIndex--;
                this.textInput = "";
                this.transcriptionText = "";
            }
        },

        nextQuestion() {
            if (this.currentIndex < this.questions.length - 1) {
                this.currentIndex++;
                this.textInput = "";
                this.transcriptionText = "";
            }
        },

        skipQuestion() {
            this.nextQuestion();
        },

        async generateBio() {
            this.isGenerating = true;

            try {
                const response = await fetch('/api/plugins/biorecorder/generate_bio', {
                    method: 'POST'
                });

                const data = await response.json();
                console.log('Bio generated:', data);

                // Show success message or navigate back
                alert('Biography generated successfully!');
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
.biorecorder {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 2rem;
    max-width: 900px;
    margin: 0 auto;
}

.progress-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 2rem;
}

.progress-text {
    font-size: 1.2rem;
    font-weight: bold;
    min-width: 150px;
}

.progress-bar {
    flex: 1;
    height: 12px;
    background: rgba(255, 255, 255, 0.2);
    border-radius: 6px;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    background: var(--color-btn-primary, #216776);
    transition: width 0.3s ease;
}

.question-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
}

.category-header {
    font-size: 1.1rem;
    font-weight: bold;
    color: var(--color-accent, #34d399);
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

.question-text {
    font-size: 1.8rem;
    font-weight: 500;
    line-height: 1.4;
}

.question-instructions {
    font-size: 1rem;
    opacity: 0.7;
    font-style: italic;
}

.existing-answer {
    background: rgba(255, 255, 255, 0.1);
    padding: 1rem;
    border-radius: 8px;
    border-left: 3px solid var(--color-accent, #34d399);
}

.answer-label {
    font-size: 0.9rem;
    opacity: 0.7;
    margin-bottom: 0.5rem;
}

.answer-text {
    white-space: pre-wrap;
    font-size: 1.1rem;
}

.transcription-area,
.transcription-edit {
    margin: 1rem 0;
}

.transcribing-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1.1rem;
    opacity: 0.8;
}

.transcribing-indicator::before {
    content: "";
    width: 20px;
    height: 20px;
    border: 2px solid currentColor;
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.transcription-textarea,
.answer-textarea {
    width: 100%;
    min-height: 120px;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 8px;
    padding: 1rem;
    color: inherit;
    font-size: 1.1rem;
    resize: vertical;
    font-family: inherit;
}

.input-methods {
    display: flex;
    gap: 2rem;
    align-items: flex-start;
    margin-top: 1rem;
}

.voice-input {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
}

.btn-record {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
    padding: 2rem;
    font-size: 1.2rem;
    font-weight: bold;
    background: var(--color-btn-primary, #216776);
    color: white;
    border: none;
    border-radius: 12px;
    cursor: pointer;
    min-width: 150px;
}

.btn-record:hover {
    background: var(--color-btn-rollover-primary, #2a8fa8);
}

.btn-record.recording {
    background: #dc2626;
    animation: pulse 1s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}

.btn-icon {
    width: 48px;
    height: 48px;
}

.or-divider {
    display: flex;
    align-items: center;
    font-weight: bold;
    opacity: 0.5;
    font-size: 1.2rem;
}

.text-input {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.btn-primary {
    padding: 1rem 2rem;
    font-size: 1.1rem;
    font-weight: bold;
    background: var(--color-btn-primary, #216776);
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
}

.btn-primary:hover {
    background: var(--color-btn-rollover-primary, #2a8fa8);
}

.btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.btn-save-transcription,
.btn-save-text {
    align-self: flex-end;
}

.navigation {
    display: flex;
    gap: 1rem;
    justify-content: center;
    margin-top: 2rem;
}

.btn-nav {
    padding: 1rem 2rem;
    font-size: 1rem;
    font-weight: bold;
    background: rgba(255, 255, 255, 0.1);
    color: white;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 8px;
    cursor: pointer;
    min-width: 120px;
}

.btn-nav:hover {
    background: rgba(255, 255, 255, 0.2);
}

.btn-nav:disabled {
    opacity: 0.3;
    cursor: not-allowed;
}

.btn-skip {
    background: rgba(255, 255, 255, 0.05);
}

.completion-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 2rem;
    text-align: center;
}

.completion-message {
    font-size: 2rem;
    font-weight: bold;
}

.btn-generate {
    padding: 1.5rem 3rem;
    font-size: 1.3rem;
    font-weight: bold;
    background: var(--color-btn-primary, #216776);
    color: white;
    border: none;
    border-radius: 12px;
    cursor: pointer;
}

.btn-generate:hover {
    background: var(--color-btn-rollover-primary, #2a8fa8);
}

.btn-generate:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}
</style>
