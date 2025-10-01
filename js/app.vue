<div id="apploading" v-show="appview == 'loading' || !pywebviewready">
    <img src="img/igoor_logo.png" alt="Igoor Logo">
</div>
<div id="minimized" v-show="minimized" @click="maximize">
    <button height="80">
        <img src="img/igoor_minimized_icon.png" />
    </button>
</div>
<div id="hidden">
    <rag  :appview="appview" :lang="lang"></rag>
</div>
<div id="topbar">
    <div class="topbar-left">
        <clock  :appview="appview" :lang="lang"></clock>
    </div>
    <div class="topbar-center">
        <a @click="minimize()"><img src="img/logo_small.svg" class="logo_small" id="igoor_logo"></a>
    </div>
    <div class="topbar-right">
        <bugreport  :appview="appview" :lang="lang"></bugreport><onboarding  :appview="appview" :lang="lang"></onboarding>
    </div>
</div>

<header v-show="appview !== 'onboarding'" :class="{ 'expanded': headerExpanded }">
    <asrwhisper  :appview="appview" :lang="lang"></asrwhisper><autocomplete  :appview="appview" :lang="lang"></autocomplete><conversation  :appview="appview" :lang="lang"></conversation><extkeyb  :appview="appview" :lang="lang"></extkeyb>
</header>
<div class="after_header" v-show="appview !== 'onboarding'">
    <autocompletelauncher @show-autocomplete="showAutocomplete" :appview="appview" :lang="lang"></autocompletelauncher>
</div>
<main>
    <daily  :appview="appview" :lang="lang"></daily><flow @show-autocomplete="showAutocomplete" :appview="appview" :lang="lang"></flow><memory  :appview="appview" :lang="lang"></memory>
</main>
<footer>
    <shortcuts  :appview="appview" :lang="lang"></shortcuts>
</footer>