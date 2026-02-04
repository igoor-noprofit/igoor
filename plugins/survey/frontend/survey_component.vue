<template>
    <div>
        <!-- Survey Modal - always rendered (hidden by v-show) to ensure WebSocket connection -->
        <div v-show="showSurveyModal" class="survey-modal-overlay">
            <div class="survey-modal-content">
                <div class="survey-message">
                    Notice spécifique concernant l'expérimentation en cours à l'Hôpital Marin d'Hendaye :

                    Dans le cadre de l'expérimentation du logiciel IGOOR à l'Hôpital Marin d'Hendaye, vous devez remplir le formulaire votre avis sur l'expérimentation du logiciel IGOOR avant votre départ de l'Hôpital. Ça ne prend que 5 minutes et c'est crucial pour mieux vous aider à l'avenir.
                </div>

                <div class="survey-buttons">
                    <!-- Big button: Fill the form -->
                    <button
                        class="btn btn-survey-main"
                        @click="openSurveyForm">
                        JE REMPLIS LE FORMULAIRE
                    </button>

                    <!-- Smaller alternatives -->
                    <div class="survey-alternatives">
                        <button
                            class="btn btn-survey-alt"
                            @click="remindIn5Minutes">
                            Me le rappeler dans 5 minutes
                        </button>
                        <button
                            class="btn btn-survey-alt"
                            @click="remindLater">
                            Me le rappeler plus tard
                        </button>
                        <button
                            class="btn btn-survey-alt"
                            @click="hasFilled">
                            J'ai déjà rempli le formulaire
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
    name: "survey",
    mixins: [BasePluginComponent],
    data() {
        return {
            showSurveyModal: false,
            reminderTimer: null
        };
    },
    mounted() {
        console.log('SURVEY PLUGIN MOUNTED - Component loaded');
        this.checkAndSendReady();
    },
    methods: {
        checkAndSendReady() {
            if (this.backendApi) {
                this.sendReady();
            } else {
                setTimeout(() => this.checkAndSendReady(), 100);
            }
        },
        handleIncomingMessage(data) {
            console.log('Survey plugin received message:', data);

            // Handle MessageEvent object (WebSocket) or parsed data
            let messageData = data;
            if (data instanceof MessageEvent) {
                messageData = data.data;
            }

            // Parse JSON if it's a string
            if (typeof messageData === 'string') {
                try {
                    messageData = JSON.parse(messageData);
                } catch (e) {
                    console.error('Error parsing message data:', e);
                    return;
                }
            }

            console.log('Parsed message data:', messageData);

            if (messageData.action === 'show_survey_modal') {
                console.log('Setting showSurveyModal to true');
                this.showSurveyModal = true;
            } else if (messageData.action === 'close_survey_modal') {
                console.log('Setting showSurveyModal to false');
                this.showSurveyModal = false;
                this.clearReminderTimer();
            }
        },
        openSurveyForm() {
            // Open the Google Forms link in a new tab
            window.open('https://forms.gle/N249wRDWoCeEewoM6', '_blank');
            // Do NOT close the modal
        },
        remindIn5Minutes() {
            // Send action to backend via REST endpoint
            this.callSurveyApi('remind_in_5');
            this.clearReminderTimer();
        },
        remindLater() {
            // Send action to backend via REST endpoint
            this.callSurveyApi('remind_later');
            this.clearReminderTimer();
        },
        hasFilled() {
            // Send action to backend via REST endpoint
            this.callSurveyApi('already_filled');
            this.clearReminderTimer();
        },
        async callSurveyApi(action) {
            // Call survey API endpoints
            try {
                const response = await fetch('/api/plugins/survey/user_action', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ action: action })
                });
                if (response.ok) {
                    console.log(`Survey API action '${action}' successful`);
                } else {
                    console.error(`Survey API action '${action}' failed`);
                }
            } catch (error) {
                console.error('Error calling survey API:', error);
            }
        },
        clearReminderTimer() {
            if (this.reminderTimer) {
                clearTimeout(this.reminderTimer);
                this.reminderTimer = null;
            }
        },
        sendBackendMessage(message) {
            try {
                this.backendApi.send('survey', JSON.stringify(message));
            } catch (error) {
                console.error('Error sending message to backend:', error);
            }
        }
    }
};
</script>

<style scoped>
/* Survey Modal Overlay */
.survey-modal-overlay {
    position: fixed;
    top: 40px;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.85);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

/* Survey Modal Content */
.survey-modal-content {
    background: #fff;
    padding: 40px;
    border-radius: 15px;
    max-width: 800px;
    width: 90%;
    color: #000;
    display: flex;
    flex-direction: column;
    gap: 30px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

/* Survey Message */
.survey-message {
    font-size: 20px;
    line-height: 1.6;
    white-space: pre-line;
    color: #1d1d1d;
}

/* Survey Buttons Container */
.survey-buttons {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

/* Main Survey Button (Big) */
.btn-survey-main {
    background-color: var(--color-btn-primary, #216776);
    color: #fff;
    font-size: 24px;
    font-weight: 600;
    padding: 20px 40px;
    border: none;
    border-radius: 10px;
    cursor: pointer;
    text-align: center;
    transition: background-color 0.2s ease;
}

.btn-survey-main:hover {
    background-color: var(--color-btn-rollover-primary, #2a8fa8);
}

/* Survey Alternatives Container */
.survey-alternatives {
    display: flex;
    flex-direction: column;
    gap: 15px;
}

/* Alternative Buttons (Smaller) */
.btn-survey-alt {
    background-color: var(--color-btn-secondary, #216776);
    color: #fff;
    font-size: 18px;
    font-weight: 500;
    padding: 15px 30px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    text-align: center;
    transition: background-color 0.2s ease;
}

.btn-survey-alt:hover {
    background-color: var(--color-btn-rollover-secondary, #2a8fa8);
}

/* Responsive adjustments */
@media (max-width: 768px) {
    .survey-modal-content {
        padding: 20px;
        width: 95%;
    }

    .survey-message {
        font-size: 16px;
    }

    .btn-survey-main {
        font-size: 20px;
        padding: 15px 30px;
    }

    .btn-survey-alt {
        font-size: 16px;
        padding: 12px 20px;
    }
}
</style>
