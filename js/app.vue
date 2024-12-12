<div id="hidden">
    
</div>
<div id="topbar">
    <img src="img/igoor_logo.png" id="igoor_logo">
    <settings  :appview="appview"></settings>
</div>
<header>
    <asrvosk  :appview="appview"></asrvosk><autocomplete  :appview="appview"></autocomplete><conversation  :appview="appview"></conversation>
</header>
<div class="after_header">
    <autocompletelauncher @show-autocomplete="showAutocomplete" :appview="appview"></autocompletelauncher>
</div>
<main>
    <flow  :appview="appview"></flow>
</main>
<footer>
    <onboarding  :appview="appview"></onboarding>
</footer>