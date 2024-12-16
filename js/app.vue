<div id="apploading" v-show="appview == 'loading'">
    <img src="img/igoor_logo.png" alt="Igoor Logo">
</div>
<div id="hidden">
    
</div>
<div id="topbar">
    <img src="img/igoor_logo.png" id="igoor_logo">
    <weather  :appview="appview"></weather>
</div>

<header v-show="appview !== 'onboarding'">
    <autocomplete  :appview="appview"></autocomplete><conversation  :appview="appview"></conversation>
</header>
<div class="after_header" v-show="appview !== 'onboarding'">
    <autocompletelauncher @show-autocomplete="showAutocomplete" :appview="appview"></autocompletelauncher>
</div>
<main>
    
</main>
<footer>
    
</footer>