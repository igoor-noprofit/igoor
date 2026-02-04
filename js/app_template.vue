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
            <a style="color: #fff" href="https://forms.gle/GSN17WHFEN8dbuTGA" target="_blank">
                <span style="display: flex; align-items: center; gap: 8px;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                    </svg>
                </span>
            </a>
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