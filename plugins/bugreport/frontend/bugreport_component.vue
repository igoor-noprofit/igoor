<template>
    <div>
        <!-- Settings Gear Icon -->
        <div @click="triggerReportIssue" class="settings-gear"> <!-- Changed method name -->
            <img src="/img/icons/src/bug.svg" width="30">
        </div>
        <!-- Modal Window for Plugin Settings -->
        <div id="bugModal" v-if="showBugModal" class="modal-overlay" @click.self="closeModal"> <!-- Changed method name -->
            <div class="modal-content settings container">
                <button @click="closeModal" class="close-button">✖</button> <!-- Changed method name -->
                <!-- Display the status message from the backend -->
                <h4>{{ t("Bug Report Status") }}</h4>
                <p>{{ reportStatusMessage }}</p>
                <!-- Optionally add a button to open the folder -->
                <!-- <button v-if="reportFolderPath" @click="openReportFolder">Open Folder</button> -->
                <!-- User Comment Section -->
                <div class="comment-section" v-if="reportFolderPath"> <!-- Show only after report is saved -->
                    <hr>
                    <h5>{{ t("Help us improve IGOOR (optional)") }}</h5>
                    <textarea v-model="userComment" v-bind:placeholder="translations['Please describe what happened']" rows="4"
                        style="width: 100%; margin-bottom: 10px; font-size: 16px;"></textarea>
                    <button class="button" @click="sendUserComment" :disabled="!userComment.trim() || isSendingComment"
                        style="margin-right: 10px;">
                        {{ isSendingComment ? translations['Saving...'] : translations['Add comment'] }}
                    </button>
                    <span class="comment-status">{{ commentStatusMessage }}</span>
                </div>
                <!-- End User Comment Section -->
            </div>
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
const MAX_CONSOLE_LOG_HISTORY = 200; // Limit history size

export default {
    name: 'bugreport', // Consider using PascalCase for component names
    mixins: [BasePluginComponent],
    data() {
        return {
            showBugModal: false,
            reportStatusMessage: '',
            reportFolderPath: '',
            consoleLogHistory: [], // Array to store console messages
            originalConsoleMethods: {}, // To store original console functions
            userComment: '', // For the textarea
            isSendingComment: false, // To disable button while sending
            commentStatusMessage: '', // Feedback for comment sending
            autoCloseTimer: null // To store the setTimeout ID
        }
    },
    methods: {
        // Renamed to avoid confusion with backend method
        async triggerReportIssue() {
            this.reportStatusMessage = this.t("Generating bug report...");
            // Optionally show modal immediately

            // Prepare console log data (e.g., join array into a string)
            const consoleLogString = this.consoleLogHistory.join('\n');

            // Send action and console log data
            await this.sendMsgToBackend({
                action: "report_issue",
                console_log: consoleLogString // Send captured logs
            });
            // Clear history after sending? Optional.
            // this.consoleLogHistory = [];
        },

        // Override handleIncomingMessage from BasePluginComponent
        handleIncomingMessage(event) {
            const message = JSON.parse(event.data);
            console.log("Bugreport component handleIncomingMessage CALLED:", message);

            let handled = false;
            let shouldShowModal = false;
            let statusMsg = '';
            let folderPath = '';

            // Trim action string just in case there's whitespace
            const action = message.action ? message.action.trim() : null;

            // Check 1: report_saved
            if (action === 'report_saved' && message.status === 'success') {
                statusMsg = message.message;
                folderPath = message.folder_path;
                shouldShowModal = true;
                handled = true;
                console.log("Condition met: report_saved and success");
                // Reset comment state when showing modal for a new report
                this.userComment = '';
                this.isSendingComment = false;
                this.commentStatusMessage = '';
                if (this.autoCloseTimer) clearTimeout(this.autoCloseTimer);
                this.autoCloseTimer = null;

                // Check 2: comment_saved
            } else if (action === 'comment_saved') { // Use trimmed action
                // *** ADDED LOG to confirm entry ***
                console.log("Condition met: comment_saved");
                handled = true; // Mark as handled
                this.isSendingComment = false; // *** THIS IS THE KEY FIX - Reset button state ***
                if (message.status === 'success') {
                    this.commentStatusMessage = this.t('Thanks,your comment has been added');
                    console.log("Comment saved successfully, starting auto-close timer.");
                    // Start timer to close modal after 5 seconds
                    this.autoCloseTimer = setTimeout(() => {
                        console.log("Auto-closing modal after comment saved.");
                        this.closeModal();
                    }, 5000);
                } else {
                    this.commentStatusMessage = `Error: ${message.message || 'Failed to save comment.'}`;
                    console.error("Failed to save comment:", message.message);
                }
                // *** ADDED LOG to confirm handled state ***
                console.log("Handled flag set to:", handled);

                // Check 3: error (general error during report generation)
            } else if (message.status === 'error') {
                statusMsg = `Error: ${message.message || 'Unknown error occurred.'}`;
                shouldShowModal = true;
                handled = true;
                console.log("Condition met: error status during report generation");
                // Also reset comment state on general error display
                this.userComment = '';
                this.isSendingComment = false;
                this.commentStatusMessage = '';
                if (this.autoCloseTimer) clearTimeout(this.autoCloseTimer);
                this.autoCloseTimer = null;
            } else {
                // This log message was slightly different in the prompt, adjusted to match code
                console.log("Condition not met for specific handling in this component.");
            }

            // Update data properties and trigger modal display if needed (for report_saved/error)
            if (shouldShowModal) {
                this.reportStatusMessage = statusMsg;
                this.reportFolderPath = folderPath; // Make sure path is stored
                this.showBugModal = true;
                console.log("Attempting to show modal. this.showModal is now:", this.showBugModal);
            }

            // --- Conditional call to mixin's handler ---
            // Now, if handled is true (because comment_saved block was entered), this won't run for that message
            if (!handled && typeof BasePluginComponent.methods.handleIncomingMessage === 'function') {
                console.log("Message not handled here, passing to mixin's handleIncomingMessage.");
                BasePluginComponent.methods.handleIncomingMessage.call(this, event);
            } else if (!handled) {
                console.log("Message not handled here, and no mixin method found/needed to call.");
            }
        },

        async sendUserComment() {
            if (!this.userComment.trim() || !this.reportFolderPath) {
                this.commentStatusMessage = this.t("Cannot send empty comment or missing report path.");
                return;
            }
            this.isSendingComment = true;
            this.commentStatusMessage = this.t('Saving...');
            // Clear any existing auto-close timer when sending a new comment
            if (this.autoCloseTimer) {
                clearTimeout(this.autoCloseTimer);
                this.autoCloseTimer = null;
            }

            console.log(`Sending comment for folder: ${this.reportFolderPath}`);
            await this.sendMsgToBackend({
                action: "add_comment",
                folder_path: this.reportFolderPath, // Send the stored folder path
                comment: this.userComment.trim()
            });
            // Backend will send 'comment_saved' response, handled in handleIncomingMessage
        },


        closeModal() {
            this.showBugModal = false;
            this.reportStatusMessage = '';
            this.reportFolderPath = ''; // Clear path
            this.userComment = ''; // Clear comment textarea
            this.isSendingComment = false; // Reset sending state
            this.commentStatusMessage = ''; // Clear comment status
            // Clear the auto-close timer if the modal is closed manually
            if (this.autoCloseTimer) {
                clearTimeout(this.autoCloseTimer);
                this.autoCloseTimer = null;
                console.log("Manual close: Cleared auto-close timer.");
            }
            console.log("Modal closed. showModal is now:", this.showBugModal);
        },

        // --- Console Interception Logic ---
        interceptConsole() {
            const methodsToIntercept = ['log', 'warn', 'error', 'info', 'debug'];
            methodsToIntercept.forEach(methodName => {
                if (typeof console[methodName] === 'function') {
                    // Store the original method
                    this.originalConsoleMethods[methodName] = console[methodName];

                    // Override the console method
                    console[methodName] = (...args) => {
                        // 1. Call the original method to maintain normal console behavior
                        this.originalConsoleMethods[methodName].apply(console, args);

                        // 2. Format and store the message
                        try {
                            const timestamp = new Date().toISOString();
                            // Attempt to stringify arguments, handle potential errors/circular refs simply
                            const messageParts = args.map(arg => {
                                try {
                                    // Basic check for DOM elements to avoid excessive logging
                                    if (arg instanceof Element) return '[DOM Element]';
                                    return typeof arg === 'object' ? JSON.stringify(arg) : String(arg);
                                } catch (e) {
                                    return '[Unstringifiable Object]';
                                }
                            });
                            const formattedMessage = `${timestamp} [${methodName.toUpperCase()}] ${messageParts.join(' ')}`;
                            this.consoleLogHistory.push(formattedMessage);

                            // Limit history size
                            if (this.consoleLogHistory.length > MAX_CONSOLE_LOG_HISTORY) {
                                this.consoleLogHistory.shift(); // Remove the oldest entry
                            }
                        } catch (e) {
                            // Log error in capturing console message itself using the original console.error
                            if (this.originalConsoleMethods.error) {
                                this.originalConsoleMethods.error.call(console, "Error capturing console message:", e);
                            }
                        }
                    };
                }
            });
            // Use the original log method if available, otherwise the potentially new one
            const logFn = this.originalConsoleMethods.log || console.log;
            logFn.call(console, "Console interception enabled for bug reporting.");
        },

        restoreConsole() {
            // Use the original log method if available for the final message
            const logFn = this.originalConsoleMethods.log || console.log;
            let restored = false;
            Object.keys(this.originalConsoleMethods).forEach(methodName => {
                if (console[methodName] !== this.originalConsoleMethods[methodName]) {
                    console[methodName] = this.originalConsoleMethods[methodName];
                    restored = true;
                }
            });
            if (restored) {
                logFn.call(console, "Console interception disabled.");
            }
            this.originalConsoleMethods = {}; // Clear stored methods
        }
    },
    mounted() {
        // Start intercepting console messages when the component is mounted
        this.interceptConsole();
    },
    beforeUnmount() { // Use beforeUnmount in Vue 3, or beforeDestroy in Vue 2
        // Restore original console methods when the component is destroyed/unmounted
        this.restoreConsole();
    }
};
</script>

<style scoped>
/* Style for the gear icon */
.settings-gear {
    font-size: 1.2rem;
    cursor: pointer;
    text-align: center;
    filter: invert(100%)
}

/* Modal overlay styles */
.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
}

/* Modal content styles */
.modal-content {
    background: #fff;
    padding: 20px;
    border-radius: 8px;
    width: 40%;
    max-width: 40%;
    position: relative;
    color: #000;
    height: 40%;
    font-size: 18px;
}

/* Close button */
.close-button {
    position: absolute;
    top: 10px;
    right: 10px;
    background: none;
    border: none;
    font-size: 1.2rem;
    cursor: pointer;
}

/* Optional: Style for the status message paragraph */
.modal-content p {
    margin-top: 15px;
    word-wrap: break-word;
    /* Ensure long paths wrap */
}

/* Optional: Style for the comment status message */
.comment-status {
    font-size: 0.9em;
    color: #555;
}

.comment-section {
    margin-top: 20px;
}

.button {

    color: #fff;
    border: none;
    height: 40px;
    background-color: #407d1c;
    padding: 10px 20px;
    font-weight: bold;
    text-transform: uppercase;
    cursor: pointer;
    border-radius: 10px;
}
</style>