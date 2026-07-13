<template>
    <div class="speakerid-settings">
        <!-- Add person (name only — no voice recording required) -->
        <div class="speakerid-settings__add" v-if="!recordingForSpeaker">
            <input
                type="text"
                class="speakerid-settings__input"
                v-model="newPersonName"
                :placeholder="t('new_person_name_placeholder')"
                :disabled="isAdding"
                @keyup.enter="addPerson"
            />
            <button
                type="button"
                class="speakerid-settings__btn"
                @click="addPerson"
                :disabled="isAdding || !newPersonName.trim()"
            >
                {{ isAdding ? t('adding') : t('add_person') }}
            </button>
        </div>

        <!-- Speaker list -->
        <section class="speakerid-settings__section" v-if="!recordingForSpeaker">
            <h3 class="speakerid-settings__title">{{ t('people') }}</h3>
            <div v-if="isLoadingSpeakers" class="speakerid-settings__status">{{ t('loading_speakers') }}</div>
            <div v-else-if="speakers.length === 0" class="speakerid-settings__status">{{ t('no_speakers') }}</div>
            <ul v-else class="speakerid-settings__list">
                <li v-for="s in speakers" :key="s.id" class="speaker-row">
                    <span class="speaker-row__name">{{ s.name }}</span>
                    <span class="speaker-row__actions">
                        <button
                            type="button"
                            class="speakerid-settings__btn speakerid-settings__btn--sm"
                            :disabled="isSaving"
                            @click="startRecordingFor(s)"
                        >
                            {{ s.has_voice ? '↻ ' + t('rerecord') : '🎤 ' + t('record_voice') }}
                        </button>
                        <button
                            type="button"
                            class="speakerid-settings__btn speakerid-settings__btn--sm speakerid-settings__btn--danger"
                            :disabled="isSaving"
                            :title="t('delete')"
                            :aria-label="t('delete')"
                            @click="askDeleteSpeaker(s)"
                        >🗑</button>
                    </span>
                </li>
            </ul>
        </section>

        <!-- Contextual recorder: enrolls a voice for the selected speaker -->
        <div v-if="recordingForSpeaker" class="speakerid-settings__recorder">
            <div class="speakerid-settings__recorder-label">
                {{ t('recording_for') }}: <strong>{{ recordingForSpeaker.name }}</strong>
                <button type="button" class="speakerid-settings__btn speakerid-settings__btn--sm" @click="cancelRecording">
                    ✕
                </button>
            </div>

            <!-- Phrase-guided enrollment: 3 suggested phrases, encourage ≥3 recordings (~10s each) -->
            <div class="speakerid-settings__guide">
                <p class="speakerid-settings__guide-instr">{{ t('enrollment_instruction') }}</p>
                <p class="speakerid-settings__guide-progress">
                    {{ t('recording_progress', { done: recordingsThisSession, total: minRecordings }) }}
                    <span v-if="recordingsThisSession >= minRecordings" class="speakerid-settings__guide-done">{{ t('enrollment_enough') }}</span>
                </p>
                <div class="speakerid-settings__phrase-card">
                    <div class="speakerid-settings__phrase-label">
                        <span>{{ t('phrase_to_read') }}</span>
                        <span class="speakerid-settings__phrase-count">{{ Math.min(phraseIndex + 1, currentPhraseSet.length) }} / {{ currentPhraseSet.length }}</span>
                    </div>
                    <p :key="phraseIndex" class="speakerid-settings__phrase-current speakerid-settings__phrase-current--appear">{{ currentPhrase }}</p>
                </div>
            </div>

            <RecorderComponent
                ref="recorder"
                :enable-upload="true"
                :show-upload-button="false"
                :label-overrides="recorderLabels"
                :disabled="isSaving"
                @recorded="onRecorded"
                @error="onRecorderError"
            />
            <div class="speakerid-settings__actions">
                <button
                    type="button"
                    class="speakerid-settings__btn"
                    @click="saveRecording"
                    :disabled="!pendingBlob || isSaving"
                >
                    {{ isSaving ? t('saving') : t('save_recording') }}
                </button>
                <span v-if="statusMessage" class="speakerid-settings__status">{{ statusMessage }}</span>
            </div>
        </div>

        <!-- Delete confirmation modal (onboarding-style overlay, not a native confirm) -->
        <div v-if="pendingDelete" class="confirm-overlay" @click.self="cancelDelete">
            <div class="confirm-modal" role="dialog" aria-modal="true">
                <p class="confirm-modal__text">{{ t('confirm_delete', { name: pendingDelete.name }) }}</p>
                <div class="confirm-modal__actions">
                    <button type="button" class="speakerid-settings__btn" @click="cancelDelete">{{ t('cancel') }}</button>
                    <button type="button" class="speakerid-settings__btn speakerid-settings__btn--danger" @click="confirmDelete">{{ t('delete') }}</button>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
const RecorderComponent = require('/plugins/recorder/frontend/RecorderComponent.vue');
const BasePluginComponent = require('/js/BasePluginComponent.js');

module.exports = {
    name: 'speakeridSettings',
    components: { RecorderComponent },
    mixins: [BasePluginComponent],
    props: {
        initialSettings: Object
    },
    data() {
        return {
            speakers: [],
            newPersonName: '',
            isLoadingSpeakers: false,
            isAdding: false,
            // Which speaker (if any) the contextual recorder is enrolling a voice for.
            recordingForSpeaker: null,
            pendingBlob: null,
            isSaving: false,
            statusMessage: '',
            pendingDelete: null, // speaker awaiting delete confirmation (custom modal)
            // Phrase-guided enrollment: 3 suggested phrases, encourage ≥3 recordings (~10s each).
            // First phrase is personalized per speaker (see $_buildPhraseSet); the rest are generic
            // French sentences chosen for phonetic variety. Localize later via the locale file.
            enrollmentPhrases: [
                "L'intelligence artificielle transforme le monde très rapidement et elle aura un impact majeur sur de nombreuses industries dans les années à venir.",
                "Chaque matin, je commence ma journée par une tasse de café, puis je regarde mes messages avant de commencer à travailler sur mes projets.",
                "Ma façon préférée de me détendre après une longue journée est d'écouter de la musique ou de regarder un bon film avec ma famille.",
                "La technologie a rendu notre vie beaucoup plus facile, mais il est aussi important de protéger nos informations personnelles et notre vie privée en ligne.",
                "J'aime voyager dans de nouveaux endroits, découvrir différentes cultures et goûter à la cuisine locale quand c'est possible.",
                "L'exercice physique est très important pour la santé du corps et de l'esprit, et j'essaie de marcher un peu chaque jour.",
                "Portez ce vieux whisky au juge blond qui fume sur son île intérieure, à côté de l'alcôve ovale."
            ],
            currentPhraseSet: [],
            phraseIndex: 0,
            recordingsThisSession: 0,
            minRecordings: 3,
            // True when this session re-records an existing voice profile → the first
            // save sends reset=true so the backend clears the old samples first.
            sessionIsRerecord: false
        };
    },
    computed: {
        recorderLabels() {
            return {
                start: this.t('start_recording'),
                stop: this.t('stop'),
                play: this.t('play_back'),
                recording: this.t('recording')
            };
        },
        // Show one phrase at a time (the one to read now). After all are done we hold
        // on the last phrase; the counter + "enough" message signal completion.
        currentPhrase() {
            const set = this.currentPhraseSet;
            if (!set.length) return '';
            return set[Math.min(this.phraseIndex, set.length - 1)];
        }
    },
    mounted() {
        this.loadSpeakers();
    },
    methods: {
        async loadSpeakers() {
            this.isLoadingSpeakers = true;
            try {
                this.speakers = await this.callPluginRestEndpoint('speakerid', 'speakers') || [];
            } catch (e) {
                console.error('Failed to load speakers', e);
                this.statusMessage = this.t('error_loading_speakers');
            } finally {
                this.isLoadingSpeakers = false;
            }
        },

        async addPerson() {
            const name = (this.newPersonName || '').trim();
            if (!name) return;
            this.isAdding = true;
            this.statusMessage = '';
            try {
                await this.callPluginRestEndpoint('speakerid', 'speakers', {
                    method: 'POST',
                    data: { name }
                });
                this.newPersonName = '';
                await this.loadSpeakers();
                this.statusMessage = this.t('person_added');
            } catch (e) {
                console.error('Failed to add person', e);
                this.statusMessage = this.t('error_adding_person');
            } finally {
                this.isAdding = false;
            }
        },

        startRecordingFor(speaker) {
            this.recordingForSpeaker = speaker;
            this.pendingBlob = null;
            this.statusMessage = '';
            this.recordingsThisSession = 0;
            this.phraseIndex = 0;
            this.sessionIsRerecord = !!speaker.has_voice;
            this.currentPhraseSet = this.$_buildPhraseSet(speaker.name);
        },

        $_buildPhraseSet(name) {
            // First phrase is personalized (the speaker says their own name — good for ID);
            // plus 2 random generic phrases so the ≥3 recordings span varied phonetics.
            const personalized = `Bonjour, je m'appelle ${name}. J'enregistre ma voix pour que l'application puisse me reconnaître.`;
            const pool = this.enrollmentPhrases.slice();
            const picked = [];
            while (picked.length < 2 && pool.length) {
                picked.push(pool.splice(Math.floor(Math.random() * pool.length), 1)[0]);
            }
            return [personalized, ...picked];
        },

        cancelRecording() {
            this.recordingForSpeaker = null;
            this.pendingBlob = null;
            this.statusMessage = '';
        },

        onRecorded(blob) {
            this.pendingBlob = blob;
            // No success/progress text — only surface messages on error (per UX).
            this.statusMessage = '';
        },

        onRecorderError(error) {
            console.error('Recorder error', error);
            this.statusMessage = this.t('recorder_error');
        },

        async saveRecording() {
            if (!this.pendingBlob) {
                this.statusMessage = this.t('record_audio_first');
                return;
            }
            if (!this.recordingForSpeaker) {
                this.statusMessage = this.t('record_audio_first');
                return;
            }
            this.isSaving = true;
            this.statusMessage = '';
            try {
                const recorder = this.$refs.recorder;
                if (!recorder) {
                    throw new Error('Recorder unavailable');
                }
                // Place the blob on the recorder so it can be uploaded
                recorder.recordedBlob = this.pendingBlob;
                recorder.hasRecording = true;
                const uploadPayload = await recorder.$_uploadRecording('speakerid');
                const recorderId = uploadPayload?.id;
                if (!recorderId) {
                    throw new Error(`Recorder did not return an id. Response: ${JSON.stringify(uploadPayload)}`);
                }

                // Link + enroll: backend copies the WAV into voices/<name>/ and rebuilds.
                const result = await this.callPluginRestEndpoint('speakerid', 'records', {
                    method: 'POST',
                    data: {
                        recorder_id: recorderId,
                        speakers_id: this.recordingForSpeaker.id,
                        // On the first save of a re-record, clear the speaker's previous
                        // samples so we replace (not stack onto) the old profile.
                        reset: this.sessionIsRerecord && this.recordingsThisSession === 0
                    }
                });

                // Keep the enrollment panel open and advance to the next phrase so the
                // user can do several recordings in a row (target ≥3). Closing happens
                // via the ✕ button (cancelRecording).
                this.pendingBlob = null;
                // Clear the recorder's held recording so its play button hides until
                // the next take (playback is only for an unsaved recording).
                if (recorder) {
                    recorder.hasRecording = false;
                    recorder.recordedBlob = null;
                }
                this.recordingsThisSession += 1;
                this.phraseIndex = Math.min(this.recordingsThisSession, this.currentPhraseSet.length);
                await this.loadSpeakers();
                if (result?.warning) {
                    this.statusMessage = result.warning;
                } else {
                    // No success text — the phrase advance + counter signal it.
                    this.statusMessage = '';
                }
            } catch (error) {
                console.error('Failed to save recording', error);
                this.statusMessage = error.message || this.t('error_saving_recording');
            } finally {
                this.isSaving = false;
            }
        },

        askDeleteSpeaker(speaker) {
            // Opens the custom confirmation modal instead of a native window.confirm().
            this.pendingDelete = speaker;
        },

        cancelDelete() {
            this.pendingDelete = null;
        },

        async confirmDelete() {
            const speaker = this.pendingDelete;
            if (!speaker) return;
            this.pendingDelete = null;
            this.isSaving = true;
            this.statusMessage = '';
            try {
                await this.callPluginRestEndpoint('speakerid', `speakers/${speaker.id}`, {
                    method: 'DELETE'
                });
                await this.loadSpeakers();
                this.statusMessage = this.t('person_deleted');
            } catch (e) {
                console.error('Failed to delete speaker', e);
                this.statusMessage = this.t('error_deleting_person');
            } finally {
                this.isSaving = false;
            }
        }
    }
};
</script>

<style scoped>
/* Dark-theme palette from the app's design tokens (css/app.css).
   This component renders inside .plugin-settings-component (bg #0d1117). */
.speakerid-settings {
    display: flex;
    flex-direction: column;
    gap: 16px;
    color: var(--color-text, #ffffff);
}

.speakerid-settings__section {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.speakerid-settings__title {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--color-text, #ffffff);
}

/* Add-person row */
.speakerid-settings__add {
    display: flex;
    gap: 8px;
}

.speakerid-settings__input {
    flex: 1;
    padding: 10px 14px;
    border: 1px solid var(--basecolor-gray-700, #556265);
    border-radius: 8px;
    background: var(--basecolor-gray-900, #2d3233);
    color: var(--color-text, #ffffff);
    font-size: 0.95rem;
    transition: border-color 0.15s ease;
}

.speakerid-settings__input::placeholder {
    color: var(--basecolor-gray-100, #afbfbf);
    opacity: 0.7;
}

.speakerid-settings__input:focus {
    outline: none;
    border-color: var(--basecolor-accent-500, #3d6c76);
}

/* Buttons */
.speakerid-settings__btn {
    padding: 10px 16px;
    border: none;
    border-radius: 8px;
    background: var(--basecolor-accent-500, #3d6c76);
    color: #ffffff;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 600;
    white-space: nowrap;
    transition: background 0.15s ease, transform 0.1s ease;
}

.speakerid-settings__btn:hover:not(:disabled) {
    background: var(--basecolor-accent-700, #2f535b);
}

.speakerid-settings__btn:active:not(:disabled) {
    transform: translateY(1px);
}

.speakerid-settings__btn:focus-visible {
    outline: 2px solid var(--basecolor-accent-500, #3d6c76);
    outline-offset: 2px;
}

.speakerid-settings__btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
}

.speakerid-settings__btn--sm {
    padding: 7px 12px;
    font-size: 0.82rem;
}

.speakerid-settings__btn--danger {
    background: var(--basecolor-warning-500, #a8351b);
}

.speakerid-settings__btn--danger:hover:not(:disabled) {
    background: var(--basecolor-warning-500, #a8351b);
    filter: brightness(1.15);
}

/* Speaker list */
.speakerid-settings__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.speaker-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    border: 1px solid var(--basecolor-gray-700, #556265);
    border-radius: 8px;
    background: var(--basecolor-gray-900, #2d3233);
    transition: border-color 0.15s ease;
}

.speaker-row:hover {
    border-color: var(--basecolor-accent-500, #3d6c76);
}

.speaker-row__name {
    flex: 1;
    font-weight: 600;
    font-size: 1rem;
    color: var(--color-text, #ffffff);
    word-break: break-word;
}

.speaker-row__actions {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
}

/* Contextual recorder panel */
.speakerid-settings__recorder {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px;
    border: 1px solid var(--basecolor-gray-700, #556265);
    border-radius: 10px;
    background: var(--basecolor-gray-900, #2d3233);
}

.speakerid-settings__recorder-label {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.95rem;
    color: var(--color-text, #ffffff);
}

.speakerid-settings__recorder-label strong {
    font-weight: 700;
}

/* Phrase-guided enrollment */
.speakerid-settings__guide {
    background: var(--basecolor-darkest, #121617);
    border: 1px solid var(--basecolor-gray-700, #556265);
    border-radius: 8px;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.speakerid-settings__guide-instr {
    margin: 0;
    font-size: 0.85rem;
    color: var(--basecolor-gray-100, #afbfbf);
    line-height: 1.4;
}

.speakerid-settings__guide-progress {
    margin: 0;
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--color-text, #ffffff);
}

.speakerid-settings__guide-done {
    color: var(--basecolor-accent-500, #3d6c76);
    margin-left: 8px;
}

.speakerid-settings__phrase-card {
    background: var(--basecolor-darkest, #121617);
    border: 1px solid var(--basecolor-accent-500, #3d6c76);
    border-radius: 8px;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.speakerid-settings__phrase-label {
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--basecolor-gray-100, #afbfbf);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.speakerid-settings__phrase-count {
    color: var(--basecolor-accent-500, #3d6c76);
    font-weight: 700;
}

.speakerid-settings__phrase-current {
    margin: 0;
    font-size: 1rem;
    line-height: 1.5;
    color: var(--color-text, #ffffff);
}

/* When the phrase advances (phraseIndex changes), the <p> is re-keyed so this
   enter animation re-runs — a fade/slide cue that it's a new phrase to read. */
.speakerid-settings__phrase-current--appear {
    animation: speakerid-phrase-appear 0.5s ease;
}

@keyframes speakerid-phrase-appear {
    0% { opacity: 0; transform: translateY(8px) scale(0.98); }
    60% { opacity: 1; transform: translateY(0) scale(1.015); }
    100% { opacity: 1; transform: translateY(0) scale(1); }
}

/* Save row + status */
.speakerid-settings__actions {
    display: flex;
    align-items: center;
    gap: 12px;
    justify-content: center;
    flex-wrap: wrap;
}

.speakerid-settings__status {
    font-size: 0.88rem;
    color: var(--basecolor-gray-100, #afbfbf);
}

/* Override RecorderComponent layout (the reused recorder component) */
.speakerid-settings__recorder :deep(.recorder__row) {
    flex-direction: row;
    align-items: center;
    gap: 40px;
    min-width: auto;
    width: auto;
    justify-content: center;
}

.speakerid-settings__recorder :deep(.recorder__meter) {
    order: 2;
    min-width: 40px;
    width: 40px;
    flex: none;
}

.speakerid-settings__recorder :deep(.recorder__meter canvas) {
    width: 40px !important;
    height: 80px !important;
    border: 1px solid var(--basecolor-gray-700, #556265);
    border-radius: 4px;
}

.speakerid-settings__recorder :deep(.recorder__controls) {
    order: 1;
    gap: 16px;
    align-items: center;
}

/* The mic / play buttons (size, teal→green, float, icons) are now styled by
   RecorderComponent itself — only the panel layout above is overridden here. */

/* Delete confirmation modal — onboarding-style overlay */
.confirm-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
}

.confirm-modal {
    background: #ffffff;
    color: #1a1a1a;
    padding: 28px 30px;
    border-radius: 10px;
    max-width: 420px;
    width: calc(100% - 40px);
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.45);
    display: flex;
    flex-direction: column;
    gap: 20px;
    text-align: center;
}

.confirm-modal__text {
    margin: 0;
    font-size: 1.05rem;
    line-height: 1.45;
}

.confirm-modal__actions {
    display: flex;
    gap: 12px;
    justify-content: center;
}
</style>
