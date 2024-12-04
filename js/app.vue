<div id="hidden">
    <rag  :appview="appview"></rag>
</div>
<div id="topbar">
    <img src="img/igoor_logo.png" id="igoor_logo">
    <elevenlabs  :appview="appview"></elevenlabs><clock  :appview="appview"></clock><ramcpu  :appview="appview"></ramcpu><settings  :appview="appview"></settings>
</div>
<header>
    <asrvosk  :appview="appview"></asrvosk><autocomplete  :appview="appview"></autocomplete><conversation  :appview="appview"></conversation>
</header>
<div class="after_header">
    <autocompletelauncher @show-autocomplete="showAutocomplete" :appview="appview"></autocompletelauncher>
</div>
<main>
    <flow  :appview="appview"></flow><memory  :appview="appview"></memory>
</main>
<footer>
    
</footer>