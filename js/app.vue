<div id="apploading" v-show="appview == 'loading'">
    <img src="img/igoor_logo.png" alt="Igoor Logo">
</div>
<div id="hidden">
    
</div>
<div id="topbar">
    <img src="img/igoor_logo.png" id="igoor_logo">
    <ttsdefault  :appview="appview"></ttsdefault>
</div>

<header v-show="appview !== 'onboarding'">
    <autocomplete  :appview="appview"></autocomplete><conversation  :appview="appview"></conversation>
</header>
<div class="after_header" v-show="appview !== 'onboarding'">
    <autocompletelauncher @show-autocomplete="showAutocomplete" :appview="appview"></autocompletelauncher>
</div>
<main>
    <daily  :appview="appview"></daily><onboarding  :appview="appview"></onboarding><flow  :appview="appview"></flow>
</main>
<footer>
    
</footer>