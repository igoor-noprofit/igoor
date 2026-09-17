<template>
    <!-- First-run wizard: full-window overlay. Mounted by onboarding_component
         with v-if="appview === 'onboarding'", so created/beforeUnmount below
         replace the appview watcher the wizard used to need.
         Teleported to <body>: the component itself lives inside #topbar's
         stacking context, where its z-index 10000 could never cover the app
         shell's boot splash (z-index 9990) — at body level the intended
         order (splash masks the SFC load gap, then the wizard covers the
         splash) actually holds. -->
    <Teleport to="body">
        <div class="wiz-overlay">

        <!-- Step 0: boot progress (logo + bar, auto-advances) -->
        <div v-if="wizardStep === 'loading'" class="wiz-center">
            <img class="wiz-logo" src="/img/igoor_logo.png" alt="IGOOR">
            <div class="wiz-loadbar"><div class="wiz-loadfill" :style="{ width: wizardPercent + '%' }"></div></div>
            <p class="wiz-sub">{{ t("This can take a few minutes the first time. Please wait.") }}</p>
        </div>

        <!-- Step 1: choice — new profile (left) or import (right) -->
        <div v-else-if="wizardStep === 'choice'" class="wiz-center wiz-wide">
            <h1 class="wiz-title">{{ t("Welcome to IGOOR") }}</h1>
            <div class="wiz-split">
                <div class="wiz-card">
                    <label class="wiz-label">{{ t("Who is IGOOR for?") }}</label>
                    <input class="wiz-input" type="text" v-model="bio.name" :placeholder="t('e.g. Marie')">
                    <label class="wiz-label">{{ t("Language") }}</label>
                    <select class="wiz-input" v-model="prefs.lang">
                        <option value="fr_FR">{{ t("French") }}</option>
                        <option value="en_EN">{{ t("English") }}</option>
                        <option value="it_IT">{{ t("Italian") }}</option>
                        <option value="pt_BR">{{ t("Portuguese") }}</option>
                    </select>
                    <button class="btn btn-primary wiz-go" :disabled="!wizardNameOk" @click="wizardContinueHealth">
                        {{ t("Continue") }}
                    </button>
                </div>
                <div class="wiz-card">
                    <label class="wiz-label">{{ t("Import Data") }}</label>
                    <p class="wiz-sub">{{ t("Restore from an IGOOR export (.zip).") }}</p>
                    <input type="file" ref="wizardImportInput" accept=".zip" style="display:none" @change="wizardImportChange">
                    <button class="btn btn-form" :disabled="!wizardBooted || wizardImporting" @click="$refs.wizardImportInput.click()">
                        {{ wizardImporting ? t("Importing...") : t("Browse files...") }}
                    </button>
                    <div v-if="wizardImporting" class="wiz-steps">
                        <div v-for="(label, idx) in wizardImportSteps" :key="idx"
                             :class="['wiz-step', idx <= wizardImportStep ? 'done' : '']">
                            <span class="wiz-step-dot"></span>{{ t(label) }}
                        </div>
                    </div>
                    <p v-if="wizardImportStatus && wizardImportStatus.type === 'error'" class="wiz-import-status error">{{ wizardImportStatus.message }}</p>
                    <p v-if="!wizardImportStatus && !wizardImporting" class="wiz-sub wiz-dim">{{ t("Available once loading is complete.") }}</p>
                </div>
            </div>
        </div>

        <!-- Import done: full-screen recap of what was restored (mockup parity).
             A dedicated screen instead of a line in the import card: the
             caregiver must SEE that the import went well, and any warnings. -->
        <div v-else-if="wizardStep === 'importDone'" class="wiz-center">
            <svg class="wiz-done-ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9.5"/><path d="M7.5 12.5l3 3 6-6.5"/></svg>
            <h1 class="wiz-title">{{ wizardImportSummary && wizardImportSummary.name ? t("Welcome back, {name}", { name: wizardImportSummary.name }) : t("Welcome back") }}</h1>
            <div class="wiz-checklist">
                <div class="wiz-checkline">
                    <svg class="wiz-ok-ic" viewBox="0 0 24 24"><circle cx="10" cy="8" r="3.4"/><path d="M4 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/></svg>
                    <div>{{ t("Profile, language & preferences") }}</div>
                </div>
                <div v-if="wizardImportSummary && wizardImportSummary.conversations" class="wiz-checkline">
                    <svg class="wiz-ok-ic" viewBox="0 0 24 24"><path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 9 9 0 0 1-3.9-.9L3 20l1-4.9a8.4 8.4 0 1 1 17-3.6z"/></svg>
                    <div>{{ t("{n} conversations · {m} messages", { n: wizardImportSummary.conversations, m: wizardImportSummary.messages || 0 }) }}</div>
                </div>
                <!-- Documents = RAG documents; voices = speakerid people voices +
                     pockettts cloned voices. Each part only when non-zero. -->
                <div v-if="wizardImportSummary && (wizardImportSummary.documents || wizardImportSummary.voices)" class="wiz-checkline">
                    <svg class="wiz-ok-ic" viewBox="0 0 24 24"><path d="M5 4h9l5 5v11H5z"/><path d="M14 4v5h5M8 13h8M8 16.5h5"/></svg>
                    <div><template v-if="wizardImportSummary.documents">{{ t("{n} documents", { n: wizardImportSummary.documents }) }}</template><template v-if="wizardImportSummary.documents && wizardImportSummary.voices"> · </template><template v-if="wizardImportSummary.voices">{{ t("{v} voices", { v: wizardImportSummary.voices }) }}</template></div>
                </div>
                <div class="wiz-checkline" :class="{ 'wiz-dimline': !wizardImportSummary || !wizardImportSummary.ai_connected }">
                    <svg :class="wizardImportSummary && wizardImportSummary.ai_connected ? 'wiz-ok-ic' : 'wiz-dim-ic'" viewBox="0 0 24 24"><path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM19 16l.9 2.1L22 19l-2.1.9L19 22l-.9-2.1L16 19l2.1-.9z"/></svg>
                    <div v-if="wizardImportSummary && wizardImportSummary.ai_connected">{{ t("AI provider connected (key restored)") }}</div>
                    <div v-else>{{ t("No AI key in the export — IGOOR starts in keyless mode.") }}</div>
                </div>
            </div>
            <div v-if="wizardImportWarnings.length" class="wiz-infobox wiz-infobox-warn">
                <strong>{{ t("Notes") }}</strong>
                <ul><li v-for="(w, i) in wizardImportWarnings" :key="i">{{ w }}</li></ul>
            </div>
            <div class="wiz-infobox">{{ t("IGOOR needs one quick restart to apply plugins and settings.") }}</div>
            <p v-if="wizardClosingMsg" class="wiz-sub wiz-dim">{{ wizardClosingMsg }}</p>
            <button class="btn btn-form wiz-go" :disabled="Boolean(wizardClosingMsg)" @click="wizardRestart">{{ t("Close IGOOR now") }}</button>
        </div>

        <!-- Step 2: health state (skippable) -->
        <div v-else-if="wizardStep === 'health'" class="wiz-center">
            <h1 class="wiz-title">{{ bio.name ? t("{name}, tell us about your health situation", { name: bio.name }) : t("Tell us about your health situation") }}</h1>
            <p class="wiz-sub">{{ t("Helps the AI speak with the user, not just for them. Stays on this computer, editable anytime.") }}</p>
            <textarea class="wiz-textarea" v-model="bio.health_state"></textarea>
            <div class="wiz-row">
                <button class="btn wiz-quiet" @click="wizardGoBack">{{ t("Back") }}</button>
                <span class="wiz-spacer"></span>
                <button class="btn wiz-quiet" @click="wizardHealthDone(true)">{{ t("Skip for now") }}</button>
                <button class="btn btn-form" @click="wizardHealthDone(false)">{{ t("Continue") }}</button>
            </div>
        </div>

        <!-- Step 3: AI provider (optional — a Groq/Mistral key also sets cloud ASR) -->
        <div v-else-if="wizardStep === 'ai'" class="wiz-center wiz-narrow">
            <h1 class="wiz-title">{{ t("Connect an AI") }}</h1>
            <p class="wiz-sub">{{ t("Unlocks suggested sentences and richer replies. You can skip this — everything else works without it.") }}</p>
            <label class="wiz-label">{{ t("Provider") }}</label>
            <div class="wiz-seg" role="radiogroup" :aria-label="t('Provider')">
                <button v-for="p in ['groq', 'mistral', 'cerebras', 'other']" :key="p" type="button"
                        :class="{ sel: wizardAiProvider === p }" @click="wizardSelectProvider(p)">
                    {{ p === 'other' ? t('Other / Local') : p.charAt(0).toUpperCase() + p.slice(1) }}
                </button>
            </div>
            <div v-if="wizardAiProvider === 'other'" class="wiz-field">
                <label class="wiz-label">{{ t("Server URL") }}</label>
                <input class="wiz-input" type="text" v-model="ai.base_url" :placeholder="t('https://your-server/v1 — any OpenAI-compatible endpoint')">
            </div>
            <div class="wiz-field">
                <label class="wiz-label">{{ t("API Key") }}</label>
                <input class="wiz-input" type="password" v-model="ai.api_key" :placeholder="t('Paste your key')">
                <p v-if="isValidating" class="wiz-sub wiz-dim">{{ t("Checking key...") }}</p>
                <p v-else-if="apiKeyValid" class="wiz-sub wiz-key-ok">{{ t("Key verified") }}</p>
                <p v-else-if="apiKeyError" class="wiz-import-status error">{{ apiKeyErrorMessage }}</p>
            </div>
            <div v-if="wizardAiLinks" class="wiz-linkbtns">
                <a class="wiz-linkbtn" :href="wizardAiLinks.key" target="_blank">
                    <svg class="icon icon-s"><use xlink:href="/img/svgdefs.svg#icon-chevron_right"></use></svg>
                    {{ t(wizardAiLinks.keyText) }}
                </a>
                <a class="wiz-linkbtn" :href="wizardAiLinks.privacy" target="_blank">
                    <svg class="icon icon-s"><use xlink:href="/img/svgdefs.svg#icon-chevron_right"></use></svg>
                    {{ t("Provider privacy policy") }}
                </a>
            </div>
            <div class="wiz-row">
                <button class="btn wiz-quiet" @click="wizardGoBack">{{ t("Back") }}</button>
                <span class="wiz-spacer"></span>
                <button class="btn wiz-quiet" @click="wizardAiSkip">{{ t("Skip for now") }}</button>
                <button class="btn btn-form" :disabled="!wizardAiContinueOk || wizardAiSaving" @click="wizardAiConnect">
                    {{ wizardAiSaving ? t("Saving...") : t("Continue") }}
                </button>
            </div>
        </div>

        <!-- Step 4: speech recognition — provider-aware, mic test -->
        <div v-else-if="wizardStep === 'speech'" class="wiz-center wiz-narrow">
            <h1 class="wiz-title">{{ t("Speech recognition is ready") }}</h1>
            <p class="wiz-sub">{{ wizardSpeechLead }}</p>
            <!-- Why IGOOR's ASR listens to everyone: classic AAC only captures
                 the user's intent to speak; IGOOR transcribes the people
                 around them too, so conversations build context. -->
            <div class="wiz-infobox">
                {{ bio.name
                    ? t("Unlike classic AAC software, IGOOR includes the people around {name} — family, caregivers — in the conversation, and transcribes what they say. Let's test the microphone.", { name: bio.name })
                    : t("Unlike classic AAC software, IGOOR includes the people around the user — family, caregivers — in the conversation, and transcribes what they say. Let's test the microphone.") }}
            </div>
            <div class="wiz-card">
                <div class="chips">
                    <span class="chip" :class="{ ok: wizardSpeechChips[0].ok }">{{ wizardSpeechChips[0].text }}</span>
                    <span class="chip">{{ wizardSpeechChips[1].text }}</span>
                </div>
                <div class="wiz-volwrap"><div class="wiz-volfill" :style="{ width: wizardMicVolume + '%' }"></div></div>
                <p v-if="wizardMicError" class="wiz-import-status error">{{ wizardMicError }}</p>
                <p v-else-if="wizardMicResult" class="wiz-sub">{{ t("Recognised") }}: “{{ wizardMicResult }}”</p>
                <p v-else class="wiz-sub wiz-dim">{{ t("Say a short phrase to check the recognition quality.") }}</p>
            </div>
            <div class="wiz-row">
                <button class="btn wiz-quiet" @click="wizardGoBack">{{ t("Back") }}</button>
                <span class="wiz-spacer"></span>
                <button class="btn wiz-quiet" @click="openMicSettings">{{ t("Microphone settings") }}</button>
                <button class="btn btn-primary" :disabled="wizardMicActive" @click="wizardTestMic">
                    {{ wizardMicActive ? t("Listening...") : t("Test") }}
                </button>
                <button class="btn btn-form" @click="wizardSpeechDone">{{ t("Continue") }}</button>
            </div>
        </div>

        <!-- Step 5: all set — recap of what works right now -->
        <div v-else-if="wizardStep === 'done'" class="wiz-center">
            <svg class="wiz-done-ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9.5"/><path d="M7.5 12.5l3 3 6-6.5"/></svg>
            <h1 class="wiz-title">{{ bio.name ? t("{name}, you're all set", { name: bio.name }) : t("You're all set") }}</h1>
            <p class="wiz-sub">{{ t("Everything below works right now, with no account and no internet.") }}</p>
            <div class="wiz-checklist">
                <div class="wiz-checkline">
                    <svg class="wiz-ok-ic" viewBox="0 0 24 24"><rect x="2.5" y="6.5" width="19" height="11" rx="2.5"/><path d="M6 12h.5M9.5 12h.5M13 12h.5M16.5 12h.5"/></svg>
                    <div>{{ t("Type → speak") }}<small>{{ t("Keyboard straight to the voice — the core communication loop.") }}</small></div>
                </div>
                <div class="wiz-checkline">
                    <svg class="wiz-ok-ic" viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>
                    <div>{{ wizardAsrLine }}<small>{{ wizardAsrSmall }}</small></div>
                </div>
                <div class="wiz-checkline">
                    <svg class="wiz-ok-ic" viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h10"/></svg>
                    <div>{{ t("Conversations saved locally") }}<small>{{ t("History stays on this computer — nothing is sent anywhere.") }}</small></div>
                </div>
                <div v-if="wizardProvider" class="wiz-checkline">
                    <svg class="wiz-ok-ic" viewBox="0 0 24 24"><path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM19 16l.9 2.1L22 19l-2.1.9L19 22l-.9-2.1L16 19l2.1-.9z"/></svg>
                    <div>{{ t("AI connected — suggestions active") }}<small>{{ t("{provider} key verified in real time.", { provider: wizardProvider.charAt(0).toUpperCase() + wizardProvider.slice(1) }) }}</small></div>
                </div>
                <div v-else class="wiz-checkline wiz-dimline">
                    <svg class="wiz-dim-ic" viewBox="0 0 24 24"><path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM19 16l.9 2.1L22 19l-2.1.9L19 22l-.9-2.1L16 19l2.1-.9z"/></svg>
                    <div>{{ t("AI suggestions — off for now") }}<small>{{ t("Connect a key anytime in Settings.") }}</small></div>
                </div>
            </div>
            <p v-if="wizardClosing" class="wiz-sub wiz-dim">{{ wizardClosingMsg }}</p>
            <button v-if="!wizardClosing" class="btn btn-form wiz-go" @click="wizardFinish">{{ t("Start using IGOOR") }}</button>
            <button v-else class="btn btn-form wiz-go" @click="wizardQuitNow" :disabled="wizardClosingMsg">{{ t("Close IGOOR now") }}</button>
        </div>
        </div>
    </Teleport>
</template>

<script>
/* First-run wizard child of onboarding_component.
   It deliberately does NOT extend BasePluginComponent: a second websocket on
   the same plugin name would race the parent's, and translations would 404 on
   the wizard's own name. Instead the parent (sole websocket owner) provides
   bound helpers (t/send/rest), the shared bio/prefs/ai objects it owns, and
   the API-key validation state; backend replies are forwarded to
   onBackendMessage(). bio/prefs/ai are the parent's reactive objects, so
   v-model edits here are visible there and trigger its watchers. */
export default {
    name: 'onboardingWizard',
    props: {
        bio: { type: Object, required: true },
        prefs: { type: Object, required: true },
        ai: { type: Object, required: true },
        // Language the APP was booted with (baked into app.js by main.py).
        // Only the wizard retranslates live; if the user picks another
        // language, finishing the wizard restarts the app so everything
        // outside it (root app, other plugins) re-resolves too.
        bootLang: { type: String, default: '' },
        t: { type: Function, required: true },               // parent-bound translations
        send: { type: Function, required: true },             // parent's sendMsgToBackend
        rest: { type: Function, required: true },             // parent's callPluginRestEndpoint
        openMicSettings: { type: Function, required: true },
        apiKeyValid: { type: Boolean, default: false },
        apiKeyError: { type: Boolean, default: false },
        apiKeyErrorMessage: { type: String, default: '' },
        isValidating: { type: Boolean, default: false },
    },
    emits: ['finish', 'validate-key', 'reset-validation'],
    data() {
        return {
            wizardStep: null,                // null | 'loading' | 'choice' | 'health' | 'ai' | 'speech' | 'done'
            wizardBooted: false,
            wizardReady: 0,
            wizardTotal: 0,
            wizardPollTimer: null,
            wizardStartedAt: null,
            wizardPollFailures: 0,
            wizardImporting: false,
            wizardImportStatus: null,
            wizardImportSummary: null,     // counts + profile info returned by the import
            wizardImportWarnings: [],      // import warnings (embedding rebuild, ...)
            wizardClosingMsg: '',          // shown after IGOOR has been told to close
            wizardImportStep: -1,
            wizardImportSteps: [
                "Archive validated",
                "Backing up current data",
                "Restoring profile & settings",
                "Restoring conversations & memories",
                "Restoring documents & voices"
            ],
            wizardImportStepTimer: null,
            wizardProvider: null,          // null | 'groq' | 'mistral' | 'cerebras' | 'other'
            wizardAiProvider: 'groq',
            wizardAiSaving: false,
            // Language-change closing flow: IGOOR closes itself after a 30s
            // warning and the user relaunches (no auto-restart: the spawned
            // child can lose the port-bind race against the old teardown).
            wizardClosing: false,
            wizardClosingMsg: '',
            wizardCountdown: 30,
            wizardCountdownTimer: null,
            wizardMicActive: false,
            wizardMicVolume: 0,
            wizardMicResult: '',
            wizardMicError: '',
        };
    },
    computed: {
        wizardNameOk() {
            return Boolean(this.bio.name && this.bio.name.trim());
        },
        wizardAiContinueOk() {
            // Known providers: real-time key validation must pass. "Other":
            // arbitrary endpoints can't be validated against a known model -
            // a filled URL + key is enough (errors surface at first use).
            if (this.wizardAiProvider === 'other') {
                return Boolean(this.ai.base_url && this.ai.base_url.trim() && this.ai.api_key && this.ai.api_key.trim());
            }
            return Boolean(this.apiKeyValid);
        },
        wizardPercent() {
            if (!this.wizardTotal) return 0;
            return Math.min(100, Math.round((this.wizardReady / this.wizardTotal) * 100));
        },
        wizardAiLinks() {
            const links = {
                groq: { key: 'https://console.groq.com/keys', keyText: 'Get a free key at console.groq.com', privacy: 'https://groq.com/privacy-policy/' },
                mistral: { key: 'https://console.mistral.ai', keyText: 'Get your key at Mistral Console', privacy: 'https://legal.mistral.ai/terms/privacy-policy' },
                cerebras: { key: 'https://cloud.cerebras.ai', keyText: 'Get your key at Cerebras Cloud', privacy: 'https://www.cerebras.ai/privacy-policy' }
            };
            return links[this.wizardAiProvider] || null;
        },
        wizardSpeechLead() {
            if (this.wizardProvider === 'groq' || this.wizardProvider === 'mistral') {
                return this.t('Your voice is recognised in the cloud via {provider} — fast and accurate. The local model stays installed as offline backup.', { provider: this.wizardProvider.charAt(0).toUpperCase() + this.wizardProvider.slice(1) });
            }
            if (this.wizardProvider === 'cerebras' || this.wizardProvider === 'other') {
                return this.t('{provider} does not include speech recognition — IGOOR uses the offline local model.', { provider: this.wizardProvider === 'other' ? this.t('This provider') : this.wizardProvider.charAt(0).toUpperCase() + this.wizardProvider.slice(1) });
            }
            return this.t('Your voice works on this computer — offline, nothing is sent anywhere.');
        },
        wizardSpeechChips() {
            if (this.wizardProvider === 'groq' || this.wizardProvider === 'mistral') {
                return [{ text: this.t('Cloud accuracy'), ok: true }, { text: this.t('Local backup installed') }];
            }
            return [{ text: this.t('Works offline'), ok: true }, { text: this.t('Model installed') }];
        },
        wizardAsrLine() {
            if (this.wizardProvider === 'groq' || this.wizardProvider === 'mistral') {
                return this.t('Cloud speech recognition via {provider}', { provider: this.wizardProvider.charAt(0).toUpperCase() + this.wizardProvider.slice(1) });
            }
            return this.t('Offline speech recognition');
        },
        wizardAsrSmall() {
            if (this.wizardProvider === 'groq' || this.wizardProvider === 'mistral') {
                return this.t('Fast and accurate — the offline model stays installed as backup.');
            }
            return this.t('Installed on this computer · works offline.');
        },
    },
    created() {
        this.wizardStart();
    },
    beforeUnmount() {
        this.wizardStop();
    },
    methods: {
        onBackendMessage(data) {
            // Backend replies forwarded by the onboarding parent (sole
            // websocket owner).
            if (data.type === 'provider_saved') {
                // AI step confirmed: remember the provider for the speech
                // screen, then move on.
                this.wizardAiSaving = false;
                this.wizardProvider = data.provider || null;
                if (this.wizardStep === 'ai') this.wizardStep = 'speech';
            } else if (data.type === 'error') {
                // Release a pending Continue; the parent shows the error.
                this.wizardAiSaving = false;
            }
        },
        wizardStart() {
            this.wizardStep = 'loading';
            this.wizardBooted = false;
            this.wizardReady = 0;
            this.wizardTotal = 0;
            this.wizardImportStatus = null;
            this.wizardStartedAt = Date.now();
            this.wizardPollFailures = 0;
            this.wizardPollBoot();
            this.wizardPollTimer = setInterval(() => this.wizardPollBoot(), 600);
        },
        wizardStop() {
            if (this.wizardPollTimer) {
                clearInterval(this.wizardPollTimer);
                this.wizardPollTimer = null;
            }
            if (this.wizardImportStepTimer) {
                clearInterval(this.wizardImportStepTimer);
                this.wizardImportStepTimer = null;
            }
            if (this.wizardCountdownTimer) {
                clearInterval(this.wizardCountdownTimer);
                this.wizardCountdownTimer = null;
            }
            this.wizardStep = null;
        },
        wizardLeaveLoading(reason) {
            // The loading step must never be a dead end: advance as soon as boot
            // is confirmed, or after a grace timeout if confirmation never comes.
            if (this.wizardPollTimer) {
                clearInterval(this.wizardPollTimer);
                this.wizardPollTimer = null;
            }
            if (reason !== 'booted') {
                console.warn('Wizard leaving loading screen by timeout:', reason);
            }
            // Import is enabled once we (believe we) are booted. On timeout paths
            // the boot-status endpoint is what failed, not the boot itself - and
            // import is safe anyway (data_manager closes DB connections first).
            this.wizardBooted = true;
            if (this.wizardStep === 'loading') {
                this.wizardStep = 'choice';
            }
        },
        async wizardPollBoot() {
            const waitedMs = Date.now() - (this.wizardStartedAt || Date.now());
            try {
                const status = await this.rest('onboarding', 'boot-status');
                this.wizardPollFailures = 0;
                if (status) {
                    this.wizardReady = status.ready || 0;
                    this.wizardTotal = status.total || 0;
                }
                if ((status && status.booted) || (this.wizardTotal > 0 && this.wizardReady >= this.wizardTotal)) {
                    this.wizardBooted = true;
                    this.wizardLeaveLoading('booted');
                } else if (waitedMs > 120000) {
                    // Hard cap: never hold the user on the loading screen.
                    this.wizardLeaveLoading('timeout-120s');
                } else if (this.wizardTotal === 0 && waitedMs > 15000) {
                    // No plugin data at all (monitor not started?) - proceed.
                    this.wizardLeaveLoading('timeout-no-data');
                }
            } catch (e) {
                this.wizardPollFailures++;
                console.warn('Wizard boot-status poll failed:', e);
                if (this.wizardPollFailures >= 40 || waitedMs > 120000) {
                    // Polling is unusable (bridge/API trouble): continue without it.
                    this.wizardLeaveLoading('poll-failures');
                }
            }
        },
        wizardSaveStep(sections) {
            this.send({ action: 'save_step', data: sections });
        },
        wizardContinueHealth() {
            if (!this.wizardNameOk) return;
            this.wizardSaveStep({ bio: { name: this.bio.name.trim() }, prefs: { lang: this.prefs.lang, locale: this.prefs.locale } });
            this.wizardStep = 'health';
        },
        wizardHealthDone(skipped) {
            if (!skipped && this.bio.health_state) {
                this.wizardSaveStep({ bio: { health_state: this.bio.health_state } });
            }
            this.wizardStep = 'ai';
        },
        wizardGoBack() {
            if (this.wizardStep === 'ai') this.wizardStep = 'health';
            else if (this.wizardStep === 'speech') this.wizardStep = 'ai';
            else this.wizardStep = 'choice';
        },
        wizardSelectProvider(p) {
            this.wizardAiProvider = p;
            this.ai.provider = p;
            // Default model per provider so validation and presets work
            // without exposing a model picker in the wizard.
            const defaults = { groq: 'openai/gpt-oss-20b', mistral: 'mistral-small-latest', cerebras: 'gpt-oss-120b' };
            const urls = { groq: 'https://api.groq.com/openai/v1', mistral: 'https://api.mistral.ai/v1', cerebras: 'https://api.cerebras.ai/v1' };
            if (p !== 'other') {
                if (defaults[p]) this.ai.model_name = defaults[p];
                if (urls[p]) this.ai.base_url = urls[p];
            } else {
                this.ai.model_name = '';
                // Never carry a known provider's URL into the custom field
                // ("Other / Local" pointing at Groq's endpoint fails at first
                // use). A non-empty URL that matches no known provider is the
                // user's own (e.g. persisted from a previous local setup) -
                // keep it.
                if (Object.values(urls).includes(this.ai.base_url) || !this.ai.base_url.trim()) {
                    this.ai.base_url = '';
                }
                this.$emit('reset-validation');
            }
            // Re-validate the key for the newly selected provider
            if (this.ai.api_key && this.ai.api_key.trim()) {
                this.$emit('validate-key');
            }
        },
        wizardAiConnect() {
            if (!this.wizardAiContinueOk || this.wizardAiSaving) return;
            this.wizardAiSaving = true;
            this.send({
                action: 'set_provider',
                data: {
                    provider: this.wizardAiProvider,
                    api_key: this.ai.api_key,
                    base_url: this.wizardAiProvider === 'other' ? this.ai.base_url : '',
                    model_name: this.ai.model_name
                }
            });
        },
        wizardAiSkip() {
            this.wizardProvider = null;
            this.wizardStep = 'speech';
        },
        wizardSpeechDone() {
            this.wizardStep = 'done';
        },
        async wizardTestMic() {
            if (this.wizardMicActive) return;
            this.wizardMicActive = true;
            this.wizardMicResult = '';
            this.wizardMicError = '';
            let stream = null;
            try {
                stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const src = ctx.createMediaStreamSource(stream);
                const analyser = ctx.createAnalyser();
                analyser.fftSize = 1024;
                src.connect(analyser);
                const proc = ctx.createScriptProcessor(4096, 1, 1);
                const chunks = [];
                const data = new Uint8Array(analyser.fftSize);
                proc.onaudioprocess = (e) => {
                    const d = e.inputBuffer.getChannelData(0);
                    chunks.push(new Float32Array(d));
                    let sum = 0;
                    for (let i = 0; i < d.length; i++) sum += d[i] * d[i];
                    this.wizardMicVolume = Math.min(100, Math.round(Math.sqrt(sum / d.length) * 400));
                    analyser.getByteTimeDomainData(data);
                };
                const sink = ctx.createGain();
                sink.gain.value = 0;
                src.connect(proc);
                proc.connect(sink);
                sink.connect(ctx.destination);
                setTimeout(() => {
                    try { src.disconnect(); proc.disconnect(); sink.disconnect(); } catch (err) { /* noop */ }
                    stream.getTracks().forEach(t => t.stop());
                    this.wizardMicVolume = 0;
                    const sampleRate = ctx.sampleRate;
                    ctx.close();
                    const wav = this.wizardEncodeWav(chunks, sampleRate);
                    const fd = new FormData();
                    fd.append('audio_file', new Blob([wav], { type: 'audio/wav' }), 'wizard_test.wav');
                    fetch('/api/plugins/asrjs/test_transcribe', { method: 'POST', body: fd })
                        .then(r => r.json())
                        .then(data => {
                            this.wizardMicActive = false;
                            if (data.status === 'loading') {
                                this.wizardMicError = this.t('Speech engine still loading - try again in a moment.');
                            } else if (data.text) {
                                this.wizardMicResult = data.text;
                            } else {
                                this.wizardMicError = this.t('No speech detected. Check the microphone and try again.');
                            }
                        })
                        .catch(() => {
                            this.wizardMicActive = false;
                            this.wizardMicError = this.t('Microphone test failed');
                        });
                }, 4000);
            } catch (e) {
                if (stream) stream.getTracks().forEach(t => t.stop());
                this.wizardMicActive = false;
                this.wizardMicError = this.t('Microphone not available');
            }
        },
        wizardEncodeWav(chunks, sampleRate) {
            // Concatenate Float32 chunks and encode as a 16-bit mono WAV.
            let length = 0;
            chunks.forEach(c => { length += c.length; });
            const merged = new Float32Array(length);
            let offset = 0;
            chunks.forEach(c => { merged.set(c, offset); offset += c.length; });
            const buffer = new ArrayBuffer(44 + merged.length * 2);
            const view = new DataView(buffer);
            const writeStr = (pos, str) => { for (let i = 0; i < str.length; i++) view.setUint8(pos + i, str.charCodeAt(i)); };
            writeStr(0, 'RIFF');
            view.setUint32(4, 36 + merged.length * 2, true);
            writeStr(8, 'WAVE');
            writeStr(12, 'fmt ');
            view.setUint32(16, 16, true);
            view.setUint16(20, 1, true);
            view.setUint16(22, 1, true);
            view.setUint32(24, sampleRate, true);
            view.setUint32(28, sampleRate * 2, true);
            view.setUint16(32, 2, true);
            view.setUint16(34, 16, true);
            writeStr(36, 'data');
            view.setUint32(40, merged.length * 2, true);
            let pos = 44;
            for (let i = 0; i < merged.length; i++, pos += 2) {
                const s = Math.max(-1, Math.min(1, merged[i]));
                view.setInt16(pos, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
            }
            return buffer;
        },
        wizardRestart() {
            // No auto-restart (port-bind race): close IGOOR and let the user
            // relaunch it to apply the restored data.
            this.wizardClosingMsg = this.t('IGOOR is closing. Please relaunch it.');
            fetch('/api/app/quit', { method: 'POST' }).catch(() => { /* app closes anyway */ });
        },
        wizardFinish() {
            if (this.wizardClosing) return;
            const langChanged = this.bootLang && this.prefs.lang && this.prefs.lang !== this.bootLang;
            if (!langChanged) {
                // Same language: the parent closes the settings modal
                // (force_onboarding may have opened it) and switches to daily.
                this.$emit('finish');
                return;
            }
            // Language changed: everything outside the wizard (root app's
            // lang, other plugins) only re-resolves at boot. Auto-restarting
            // proved fragile (the spawned child can lose the port-bind race
            // against the old teardown), so warn and let the user relaunch:
            // IGOOR closes itself when the countdown hits zero.
            this.wizardClosing = true;
            this.wizardCountdown = 30;
            this.wizardClosingMsg = this.t('IGOOR needs to restart. Close the window and relaunch it (it will shut down automatically in {n} seconds) for changes to take effect.', { n: this.wizardCountdown });
            this.wizardCountdownTimer = setInterval(() => {
                this.wizardCountdown -= 1;
                if (this.wizardCountdown <= 0) {
                    this.wizardQuitNow();
                } else {
                    this.wizardClosingMsg = this.t('IGOOR needs to restart. Close the window and relaunch it (it will shut down automatically in {n} seconds) for changes to take effect.', { n: this.wizardCountdown });
                }
            }, 1000);
        },
        wizardQuitNow() {
            if (this.wizardCountdownTimer) {
                clearInterval(this.wizardCountdownTimer);
                this.wizardCountdownTimer = null;
            }
            this.wizardClosingMsg = this.t('IGOOR is closing. Please relaunch it.');
            fetch('/api/app/quit', { method: 'POST' }).catch(() => { /* app closes anyway */ });
        },
        async wizardImportChange(event) {
            const file = event.target.files[0];
            if (!file) return;
            this.wizardImporting = true;
            this.wizardImportStatus = null;
            // Optimistic stepper mirroring data_manager.import_user_data's real
            // sequence; the response arrives when the whole import is done.
            this.wizardImportStep = 0;
            this.wizardImportStepTimer = setInterval(() => {
                if (this.wizardImportStep < this.wizardImportSteps.length - 1) {
                    this.wizardImportStep++;
                }
            }, 2000);
            try {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('overwrite_settings', 'true');
                const response = await fetch('/api/data/import', { method: 'POST', body: formData });
                const data = await response.json();
                if (!response.ok || !data.success) {
                    throw new Error(data.message || 'Import failed');
                }
                if (this.wizardImportStepTimer) {
                    clearInterval(this.wizardImportStepTimer);
                    this.wizardImportStepTimer = null;
                }
                // Full-screen recap instead of a line inside the import card:
                // the caregiver must clearly see the import went well, and any
                // warnings (embedding rebuild, activation changes...).
                this.wizardImportSummary = data.summary || null;
                this.wizardImportWarnings = Array.isArray(data.warnings) ? data.warnings : [];
                this.wizardImporting = false;
                this.wizardStep = 'importDone';
            } catch (error) {
                console.error('Wizard import failed:', error);
                if (this.wizardImportStepTimer) {
                    clearInterval(this.wizardImportStepTimer);
                    this.wizardImportStepTimer = null;
                }
                this.wizardImporting = false;
                this.wizardImportStep = -1;
                this.wizardImportStatus = { type: 'error', message: this.t('Import failed') + ' : ' + error.message };
            } finally {
                event.target.value = '';
            }
        },
    }
}
</script>
<style>

/* ================= First-run wizard =================
   Full-window overlay for the onboarding view. Colors come
   exclusively from the app-wide :root design tokens. */
.wiz-overlay{
    position: fixed;
    inset: 0;
    z-index: 10000;
    background: linear-gradient(to bottom, var(--color-bgpage-0), var(--color-bgpage-1));
    color: var(--color-text);
    overflow-y: auto;
}
.wiz-center{
    min-height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 18px;
    padding: 4vh 6vw;
    box-sizing: border-box;
}
.wiz-wide{ max-width: 1100px; margin: 0 auto; width: 100%; }
.wiz-title{ font-size: 1.9rem; font-weight: 600; text-align: center; margin: 0; }
.wiz-split{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    width: 100%;
}
@media (max-width: 800px){ .wiz-split{ grid-template-columns: 1fr; } }
.wiz-card{
    background: var(--color-bgoverlay-0);
    border: 1.5px solid var(--color-gray700);
    border-radius: 10px;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 14px;
}
.wiz-label{ font-size: 0.95rem; color: var(--color-gray100); }
.wiz-input{
    width: 100%;
    background: var(--color-bgoverlay-1);
    border: 1.5px solid var(--color-gray700);
    color: var(--color-text);
    border-radius: 0.25rem;
    padding: 14px 16px;
    font-size: 1.05rem;
    outline: none;
    box-sizing: border-box;
}
.wiz-input:focus{ border-color: var(--color-inputfocus-border); background: var(--color-inputfocus-bg); }
.wiz-textarea{
    width: 100%;
    min-height: 160px;
    resize: vertical;
    background: var(--color-bgoverlay-1);
    border: 1.5px solid var(--color-gray700);
    color: var(--color-text);
    border-radius: 10px;
    padding: 14px;
    font-size: 1rem;
    font-family: inherit;
    outline: none;
    box-sizing: border-box;
}
.wiz-textarea:focus{ border-color: var(--color-inputfocus-border); }
.wiz-sub{ font-size: 0.95rem; color: var(--color-gray100); margin: 0; }
.wiz-dim{ color: var(--color-gray700); }
.wiz-row{ display: flex; gap: 12px; width: 100%; align-items: center; }
.wiz-spacer{ flex: 1; }
/* Equal button heights in wizard rows: the app-wide .btn-primary/.btn-form
   paddings differ, which made Back/Skip/Test/Continue sit at three heights. */
.wiz-row .btn{
    padding: 1rem 1.25rem;
    font-family: FontBold, sans-serif;
    font-size: 1.3125rem;
    line-height: 1.5rem;
}
/* Quiet wizard button: readable on the dark page (btn-secondary is a light
   surface style and pairs #ccc with white text here). Sizing mirrors
   .btn-form so Back/Skip sit level with Continue in the same row. */
.wiz-quiet,
.wiz-quiet:hover{
    background-color: var(--color-bgoverlay-1);
    color: var(--color-text);
    border: 1.5px solid var(--color-gray700);
    padding: 1rem 1.25rem;
    font-family: FontBold, sans-serif;
    font-size: 1.3125rem;
    line-height: 1.5rem;
}
.wiz-quiet:hover{ border-color: var(--basecolor-accent-100); }
.wiz-go{ margin-top: auto; }
.wiz-import-status{ font-size: 0.9rem; margin: 0; }
.wiz-import-status.success{ color: var(--basecolor-secondary-100); }
.wiz-import-status.error{ color: var(--basecolor-warning-100); }
.wiz-field{ width: 100%; }
.wiz-seg{ display: flex; width: 100%; border: 1.5px solid var(--color-gray700); border-radius: 10px; overflow: hidden; }
.wiz-seg button{
    flex: 1; background: transparent; border: none; border-right: 1.5px solid var(--color-gray700);
    color: var(--color-gray100); padding: 14px 6px; font-size: 1rem; font-weight: 600; cursor: pointer;
    font-family: inherit;
}
.wiz-seg button:last-of-type{ border-right: none; }
.wiz-seg button.sel{ background: var(--color-btn-base); color: var(--color-text); }
.wiz-seg button:not(.sel):hover{ color: var(--color-text); background: var(--color-inputfocus-bg); }
.wiz-key-ok{ color: var(--basecolor-secondary-100); }
.wiz-linkbtns{ display: flex; flex-direction: column; gap: 10px; width: 100%; }
.wiz-linkbtn{
    display: flex; align-items: center; gap: 12px; background: transparent;
    border: 1.5px solid var(--color-gray700); border-radius: 0.25rem; padding: 14px 16px;
    font-size: 1rem; font-weight: 600; color: var(--basecolor-accent-100); text-decoration: none;
}
.wiz-linkbtn:hover{ border-color: var(--basecolor-accent-100); color: var(--color-text); }
.wiz-volwrap{
    width: 100%; height: 10px; background: var(--basecolor-darkest);
    border: 1px solid var(--color-gray700); border-radius: 6px; overflow: hidden;
}
.wiz-volfill{ height: 100%; width: 0%; background: var(--basecolor-secondary-100); transition: width 0.12s ease; }
.wiz-steps{ display: flex; flex-direction: column; gap: 8px; }
.wiz-step{ display: flex; align-items: center; gap: 10px; font-size: 0.9rem; color: var(--color-gray700); }
.wiz-step.done{ color: var(--color-text); }
.wiz-step-dot{
    width: 10px; height: 10px; border-radius: 50%; flex: 0 0 auto;
    background: var(--color-gray700);
}
.wiz-step.done .wiz-step-dot{ background: var(--basecolor-secondary-100); }
.wiz-card .chips{ display: flex; gap: 8px; flex-wrap: wrap; }
.wiz-card .chip{
    background: var(--color-bgoverlay-1); border: 1px solid var(--color-gray700);
    border-radius: 16px; padding: 4px 14px; font-size: 0.9rem; color: var(--color-gray100);
}
.wiz-card .chip.ok{ border-color: var(--basecolor-secondary-500); color: #9fd48a; }
.wiz-loadbar{
    width: min(420px, 70vw);
    height: 10px;
    background: var(--basecolor-darkest);
    border: 1px solid var(--color-gray700);
    border-radius: 6px;
    overflow: hidden;
}
.wiz-logo{
    width: 190px;
    height: auto;
    margin-bottom: 4px;
    /* the source wordmark is dark gray - render it white on the dark gradient */
    filter: brightness(0) invert(1);
}
.wiz-loadfill{
    height: 100%;
    width: 0%;
    background: var(--basecolor-accent-100);
    transition: width 0.5s ease;
}
/* ---- All-set recap (mirrors the mockup's checklist) ---- */
.wiz-done-ic{
    width: 52px; height: 52px;
    fill: none; stroke: var(--basecolor-secondary-100);
    stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round;
}
.wiz-checklist{
    display: flex; flex-direction: column; gap: 10px;
    margin: 4px 0; width: 100%; max-width: 560px;
}
.wiz-checkline{
    display: flex; gap: 12px; align-items: center;
    font-size: 1rem; text-align: left;
}
.wiz-checkline small{
    display: block; font-size: 0.85rem; color: var(--color-gray700);
}
.wiz-ok-ic, .wiz-dim-ic{
    width: 30px; height: 30px; flex: 0 0 auto;
    fill: none; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round;
}
.wiz-ok-ic{ stroke: #8fce6b; }
.wiz-dim-ic{ stroke: var(--color-gray700); }
.wiz-dimline{ opacity: 0.75; }
/* Import-done info boxes: neutral for the restart notice, warn-tinted for
   import notes (embedding rebuild, activation changes...). */
.wiz-infobox{
    width: 100%;
    max-width: 560px;
    background: var(--color-bgoverlay-1);
    border: 1.5px solid var(--color-gray700);
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 0.95rem;
    text-align: left;
    margin: 0;
}
.wiz-infobox-warn{
    background: rgba(138, 90, 59, 0.15);
    border-color: var(--basecolor-warning-100);
}
.wiz-infobox-warn strong{ display: block; margin-bottom: 4px; }
.wiz-infobox ul{ margin: 0; padding-left: 18px; }
</style>
