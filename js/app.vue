<div id="apploading" v-show="appview == 'loading'">
    <img src="img/igoor_logo.png" alt="Igoor Logo">
</div>
<div id="hidden">
    <rag  :appview="appview"></rag>
</div>
<div id="topbar">
    <img src="img/igoor_logo.png" id="igoor_logo">
    <elevenlabs  :appview="appview"></elevenlabs><ttsdefault  :appview="appview"></ttsdefault>
</div>

<header v-show="appview !== 'onboarding'">
    <asrvosk  :appview="appview"></asrvosk><autocomplete  :appview="appview"></autocomplete><conversation  :appview="appview"></conversation>
</header>
<div class="after_header" v-show="appview !== 'onboarding'">
    <autocompletelauncher @show-autocomplete="showAutocomplete" :appview="appview"></autocompletelauncher>
</div>
<main>
    <onboarding  :appview="appview"></onboarding><flow  :appview="appview"></flow>
</main>
<footer>
    
</footer>