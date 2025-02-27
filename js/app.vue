<div id="apploading" v-show="appview == 'loading' || !pywebviewready">
    <img src="img/igoor_logo.png" alt="Igoor Logo">
</div>
<div id="minimized" v-show="minimized" @click="maximize">
    <button height="80">
        <img src="img/igoor_minimized_icon.png" />
    </button>
</div>
<div id="hidden">
    <rag  :appview="appview"></rag>
</div>
<div id="topbar">
    <div class="topbar-left">
        <clock  :appview="appview"></clock>
    </div>
    <div class="topbar-center">
        <a @click="minimize()"><img src="img/logo_small.svg" class="logo_small" id="igoor_logo"></a>
    </div>
    <div class="topbar-right">
        <meteo  :appview="appview"></meteo><settings  :appview="appview"></settings>
    </div>
</div>

<header v-show="appview !== 'onboarding'" :class="{ 'expanded': headerExpanded }">
    <asrvosk  :appview="appview"></asrvosk><autocomplete  :appview="appview"></autocomplete><conversation  :appview="appview"></conversation>
</header>
<div class="after_header" v-show="appview !== 'onboarding'">
    <autocompletelauncher @show-autocomplete="showAutocomplete" :appview="appview"></autocompletelauncher>
</div>
<main>
    <daily  :appview="appview"></daily><onboarding  :appview="appview"></onboarding><flow  :appview="appview"></flow>
</main>
<footer>
    <shortcuts  :appview="appview"></shortcuts>
</footer>