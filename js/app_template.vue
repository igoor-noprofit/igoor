<div id="apploading" v-show="appview == 'loading' || !pywebviewready">
    <img src="img/igoor_logo.png" alt="Igoor Logo">
</div>
<div id="minimized" v-show="minimized" @click="maximize">
    <button height="80">
        <img src="img/igoor_eyes.png" />
    </button>
</div>
<div id="hidden">
    <!-- HIDDEN_COMPONENTS -->
</div>
<div id="topbar">
    <a @click="minimize()"><img src="img/logo_small.svg" class="logo_small" id="igoor_logo"></a> 
    <!-- TOPBAR_COMPONENTS -->
</div>
<!-- AFTER_TOPBAR_COMPONENTS -->
<header v-show="appview !== 'onboarding'" :class="{ 'expanded': headerExpanded }">
    <!-- HEADER_COMPONENTS -->
</header>
<div class="after_header" v-show="appview !== 'onboarding'">
    <!-- AFTER_HEADER_COMPONENTS -->
</div>
<main>
    <!-- MAIN_COMPONENTS -->
</main>
<footer>
    <!-- FOOTER_COMPONENTS -->
</footer>