<div id="apploading" v-show="appview == 'loading' || !pywebviewready">
    <img src="img/igoor_logo.png" alt="Igoor Logo">
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
    <footer :class="[appview, { 'shrink': footerShrink }]" @footer-shrink="handleFooterShrink">
        <!-- FOOTER_COMPONENTS -->
    </footer>
</div>
