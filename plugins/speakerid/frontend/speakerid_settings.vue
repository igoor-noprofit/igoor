<template>
    <div class="speakerid-settings">
        <div class="speakerid-settings__row">
            <label for="speakerid-select">{{ t('known_person') }}</label>
            <select id="speakerid-select" v-model.number="selectedPerson">
                <option :value="0">Carlo</option>
                <option :value="1">Jessica</option>
            </select>
        </div>

        <div class="speakerid-settings__recorder">
            <RecorderComponent
                ref="recorder"
                :enable-upload="true"
                :show-upload-button="false"
                :label-overrides="recorderLabels"
                @recorded="onRecorded"
                @error="onRecorderError"
            />
        </div>

        <div class="speakerid-settings__actions">
            <button type="button" @click="saveRecording" :disabled="!pendingBlob || isSaving">
                {{ isSaving ? t('saving') : t('save_recording') }}
            </button>
            <span v-if="statusMessage" class="speakerid-settings__status">{{ statusMessage }}</span>
        </div>
    </div>
</template>

<script>
const RecorderComponent = require('/js/RecorderComponent.vue');
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
            selectedPerson: 0,
            pendingBlob: null,
            latestRecorderId: null,
            isSaving: false,
            statusMessage: '',
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
    watch: {
        initialSettings: {
            handler(settings) {
                if (!settings) return;
                if (typeof settings.selected_speaker === 'number') {
                    this.selectedPerson = settings.selected_speaker;
                }
            },
            immediate: true
        }
    },
    methods: {
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
            this.isSaving = true;
            this.statusMessage = this.t('uploading_recording');
            try {
                const recorder = this.$refs.recorder;
                if (!recorder) {
                    throw new Error('Recorder unavailable');
                }
                // Set the blob on the recorder so it can be uploaded
                recorder.recordedBlob = this.pendingBlob;
                recorder.hasRecording = true;
                const uploadPayload = await recorder.$_uploadRecording('speakerid');
                console.log('Upload response:', uploadPayload);
                const recorderId = uploadPayload?.id;
                if (!recorderId) {
                    throw new Error(`Recorder did not return an id. Response: ${JSON.stringify(uploadPayload)}`);
                }
                // Set the ID on both components for playback
                this.latestRecorderId = recorderId;
                recorder.latestRecorderId = recorderId;

                const payload = {
                    recorder_id: recorderId,
                    speakers_id: this.selectedPerson
                };

                const response = await fetch('/api/plugins/speakerid/records', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify(payload)
                });

                if (!response.ok) {
                    const detail = await response.json().catch(() => null);
                    const message = detail?.detail || `Failed to link recording (${response.status})`;
                    throw new Error(message);
                }

                this.pendingBlob = null;
                this.statusMessage = this.t('recording_saved');
            } catch (error) {
                console.error('Failed to save recording', error);
                this.statusMessage = error.message || this.t('error_saving_recording');
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

.speakerid-settings__row {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.speakerid-settings__recorder {
    display: flex;
    justify-content: center;
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
}

.speakerid-settings__status {
    font-size: 0.9rem;
    color: #4b5563;
}
</style>
