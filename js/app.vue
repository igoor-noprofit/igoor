<div id="apploading" v-show="appview == 'loading'">
    <img src="img/igoor_logo.png" alt="Igoor Logo">
</div>
<div id="minimized" v-show="minimized" @click="maximize">
    <button height="80">
        <img src="img/igoor_eyes.png" />
    </button>
</div>
<div id="hidden">
    
</div>
<div id="topbar">
    <a @click="minimize()"><img src="img/logo_small.svg" class="logo_small" id="igoor_logo"></a> 
    <elevenlabs  :appview="appview"></elevenlabs><ttsdefault  :appview="appview"></ttsdefault><clock  :appview="appview"></clock><meteo  :appview="appview"></meteo><settings  :appview="appview"></settings>
</div>

<header v-show="appview !== 'onboarding'">
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