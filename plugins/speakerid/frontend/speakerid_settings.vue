<template>
    <div class="speakerid-settings">
        <!-- Add person (name only — no voice recording required) -->
        <div class="speakerid-settings__add">
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
        <div v-if="isLoadingSpeakers" class="speakerid-settings__status">{{ t('loading_speakers') }}</div>
        <div v-else-if="speakers.length === 0" class="speakerid-settings__status">{{ t('no_speakers') }}</div>
        <ul v-else class="speakerid-settings__list">
            <li v-for="s in speakers" :key="s.id" class="speaker-row">
                <span class="speaker-row__name">{{ s.name }}</span>
                <span class="speaker-row__badge" :class="s.has_voice ? 'has-voice' : 'name-only'">
                    {{ s.has_voice ? '🎤' : '⚪' }} {{ t(s.has_voice ? 'voice_recorded' : 'name_only') }}
                </span>
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
                        @click="deleteSpeaker(s)"
                    >🗑</button>
                </span>
            </li>
        </ul>

        <!-- Contextual recorder: enrolls a voice for the selected speaker -->
        <div v-if="recordingForSpeaker" class="speakerid-settings__recorder">
            <div class="speakerid-settings__recorder-label">
                {{ t('recording_for') }}: <strong>{{ recordingForSpeaker.name }}</strong>
                <button type="button" class="speakerid-settings__btn speakerid-settings__btn--sm" @click="cancelRecording">
                    ✕
                </button>
            </div>
            <RecorderComponent
                ref="recorder"
                :enable-upload="true"
                :show-upload-button="false"
                :label-overrides="recorderLabels"
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
            statusMessage: ''
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
        },

        cancelRecording() {
            this.recordingForSpeaker = null;
            this.pendingBlob = null;
            this.statusMessage = '';
        },

        onRecorded(blob) {
            this.pendingBlob = blob;
            this.statusMessage = this.t('recording_ready_to_save');
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
            this.statusMessage = this.t('uploading_recording');
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
                        speakers_id: this.recordingForSpeaker.id
                    }
                });

                this.statusMessage = result?.warning
                    ? result.warning
                    : this.t('recording_saved');
                this.pendingBlob = null;
                this.recordingForSpeaker = null;
                await this.loadSpeakers();
            } catch (error) {
                console.error('Failed to save recording', error);
                this.statusMessage = error.message || this.t('error_saving_recording');
            } finally {
                this.isSaving = false;
            }
        },

        async deleteSpeaker(speaker) {
            if (!window.confirm(this.t('confirm_delete', { name: speaker.name }))) return;
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
.speakerid-settings {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.speakerid-settings__add {
    display: flex;
    gap: 8px;
}

.speakerid-settings__input {
    flex: 1;
    padding: 8px 10px;
    border: 1px solid #ccc;
    border-radius: 6px;
    font-size: 0.95rem;
}

.speakerid-settings__btn {
    padding: 8px 14px;
    border: 1px solid var(--basecolor-gray-300, #ccc);
    border-radius: 6px;
    background: var(--basecolor-accent-100, #eef);
    color: var(--basecolor-accent-700, #335);
    cursor: pointer;
    font-size: 0.9rem;
    white-space: nowrap;
}

.speakerid-settings__btn:hover:not(:disabled) {
    background: var(--basecolor-accent-200, #ddf);
}

.speakerid-settings__btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.speakerid-settings__btn--sm {
    padding: 5px 10px;
    font-size: 0.85rem;
}

.speakerid-settings__btn--danger {
    background: var(--basecolor-warning-100, #fde);
    color: var(--basecolor-warning-500, #a33);
    border-color: var(--basecolor-warning-500, #c66);
}

.speakerid-settings__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.speaker-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 10px;
    border: 1px solid var(--basecolor-gray-200, #eee);
    border-radius: 8px;
}

.speaker-row__name {
    flex: 1;
    font-weight: 600;
    color: var(--color-text, #222);
}

.speaker-row__badge {
    font-size: 0.8rem;
    padding: 3px 8px;
    border-radius: 12px;
    white-space: nowrap;
}

.speaker-row__badge.has-voice {
    background: var(--basecolor-accent-100, #eef);
    color: var(--basecolor-accent-700, #335);
}

.speaker-row__badge.name-only {
    background: var(--basecolor-gray-100, #f3f3f3);
    color: var(--basecolor-gray-500, #888);
    font-style: italic;
}

.speaker-row__actions {
    display: flex;
    gap: 6px;
}

.speakerid-settings__recorder {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding-top: 8px;
    border-top: 1px solid var(--basecolor-gray-200, #eee);
}

.speakerid-settings__recorder-label {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.95rem;
}

/* Override RecorderComponent layout */
.speakerid-settings__recorder :deep(.recorder__row) {
    flex-direction: row;
    align-items: center;
    gap: 40px;
    min-width: auto;
    width: auto;
    justify-content: center;
}

/* Make volume meter vertical on the right */
.speakerid-settings__recorder :deep(.recorder__meter) {
    order: 2;
    min-width: 40px;
    width: 40px;
    flex: none;
}

.speakerid-settings__recorder :deep(.recorder__meter canvas) {
    width: 40px !important;
    height: 80px !important;
    border: 1px solid #ccc;
    border-radius: 4px;
}

/* Controls on the left */
.speakerid-settings__recorder :deep(.recorder__controls) {
    order: 1;
    gap: 16px;
    align-items: center;
}

/* Make buttons much bigger */
.speakerid-settings__recorder :deep(.recorder__main-btn) {
    width: 80px !important;
    height: 80px !important;
}

.speakerid-settings__recorder :deep(.recorder__play-btn) {
    width: 80px !important;
    height: 80px !important;
}

.speakerid-settings__recorder :deep(.recorder__icon) {
    width: 40px !important;
    height: 40px !important;
}

.speakerid-settings__actions {
    display: flex;
    align-items: center;
    gap: 12px;
    justify-content: center;
}

.speakerid-settings__status {
    font-size: 0.9rem;
    color: #4b5563;
}
</style>
