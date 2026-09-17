<div id="apploading" v-show="appview == 'loading' || !pywebviewready">
    <img src="img/igoor_logo.png" alt="Igoor Logo">
</div>
<!-- Shown when the websocket to the IGOOR server has been down for more than
     2 seconds (server PC rebooted, network/Tailscale lost): reassures the user
     and hides the frozen UI. Clears automatically on reconnect. -->
<div id="connection-lost" v-if="connectionLost">
    <img src="img/igoor_logo.png" alt="Igoor Logo">
    <h1>{{ connectionLostMessage }}</h1>
</div>
<div id="minimized" v-show="minimized" @click="maximize">
    <button height="80">
        <img src="img/igoor_minimized_icon.png" />
    </button>
</div>
<div id="hidden">
    <!-- HIDDEN_COMPONENTS -->
</div>
<div class="app-shell">
    <!-- First-run onboarding: shown the instant the app enters the onboarding
         view, while the onboarding SFC (async component) is still loading.
         Visually identical to the wizard's loading step, so the handoff to
         the real overlay is seamless and the daily UI never flashes through.
         Sits under the wizard overlay (z-index 10000). -->
    <div v-if="appview === 'onboarding'" style="position:fixed;inset:0;z-index:9990;background:linear-gradient(to bottom, var(--color-bgpage-0), var(--color-bgpage-1));display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;">
        <img src="/img/igoor_logo.png" alt="IGOOR" style="width:190px;height:auto;margin-bottom:4px;filter:brightness(0) invert(1);">
        <div style="width:min(420px,70vw);height:10px;background:var(--basecolor-darkest);border:1px solid var(--color-gray700);border-radius:6px;overflow:hidden;">
            <div :style="{ width: bootProgressPercent + '%', height: '100%', background: 'var(--basecolor-accent-100)', transition: 'width 0.5s ease' }"></div>
        </div>
        <p style="margin:0;font-size:0.95rem;color:var(--color-gray100);">{{ wizardLoadingMessage }}</p>
    </div>
    <div id="topbar">
        <div class="topbar-left">
            <!-- BEFORE_LOGO_COMPONENTS -->
        </div>
        <div class="topbar-center">
            <a @click="minimize()"><img src="img/logo_small.svg" class="logo_small" id="igoor_logo"></a>
        </div>
        <div class="topbar-right">
            <div
                class="boot-progress"
                v-if="bootProgressVisible"
                :class="{ 'boot-progress--fade': bootProgressFaded }"
                style="display:flex;align-items:center;gap:8px;max-width:200px;position:relative;cursor:pointer;"
                @click="toggleBootNotReady"
            >
                <div class="boot-progress__bar" style="width:160px;height:6px;background:#333;border-radius:4px;overflow:hidden;">
                    <div class="boot-progress__fill" :style="{ width: bootProgressPercent + '%', height: '100%', background: '#0095c0' }"></div>
                </div>
                <div
                    v-if="bootNotReadyVisible"
                    style="position:absolute;right:0;top:100%;margin-top:8px;background:#1d1d1d;border:1px solid #333;border-radius:8px;min-width:220px;max-width:320px;max-height:240px;overflow:auto;padding:8px;color:#ddd;font-size:12px;z-index:9999;"
                >
                    <div v-if="bootNotReadyList.length === 0" style="opacity:0.7;">All plugins ready</div>
                    <div v-else>
                        <div v-for="name in bootNotReadyList" :key="name">{{ name }}</div>
                    </div>
                </div>
            </div>
            <!-- AFTER_LOGO_COMPONENTS -->
        </div>
    </div>
    <!-- AFTER_TOPBAR_COMPONENTS -->
    <div class="app-main">
        <header v-show="appview !== 'onboarding'" :class="{ 'expanded': headerExpanded }">
            <!-- HEADER_COMPONENTS -->
        </header>
        <div class="after_header" v-show="appview !== 'onboarding'">
            <!-- AFTER_HEADER_COMPONENTS -->
        </div>
        <main>
            <!-- MAIN_COMPONENTS -->
        </main>
    </div>
    <footer v-show="appview !== 'onboarding'" :class="[appview, { 'shrink': footerShrink }]" @footer-shrink="handleFooterShrink">
        <!-- FOOTER_COMPONENTS -->
    </footer>
</div>
