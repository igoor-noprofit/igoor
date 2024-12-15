<div id="apploading" v-show="appview == 'loading'">
    <img src="img/igoor_logo.png" alt="Igoor Logo">
</div>
<div id="hidden">
    <!-- HIDDEN_COMPONENTS -->
</div>
<div id="topbar">
    <img src="img/igoor_logo.png" id="igoor_logo">
    <!-- TOPBAR_COMPONENTS -->
</div>
<!-- AFTER_TOPBAR_COMPONENTS -->
<header v-show="appview !== 'onboarding'">
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