<template>
    <div class="shortcuts shortcuts-plugin">
        <button class="btn btn-shortcut" @click="$_minimise()">
            <img src="img/minimize.svg">
            <h3>{{translations['Minimize']}}</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_speak('J\'ai soif')"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-drink"></use>
            </svg>
            <h3>{{translations['Drink']}}</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_speak('J\'ai besoin d\'aller au toilette')"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-toilet"></use>
            </svg>
            <h3>{{translations['Toilet']}}</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_parole()"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-talk"></use>
            </svg>
            <h3>{{ translations['Just a sec'] }}</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_speak('Oui')"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-ok"></use>
            </svg>
            <h3>{{translations['Yes']}}</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_speak('Non')"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-no"></use>
            </svg>
            <h3>{{translations['No']}}</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_speak('Merci')"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-thankyou"></use>
            </svg>
            <h3>{{translations['Thanks']}}</h3>
        </button>
        <button class="btn btn-shortcut btn-hilite" @click="$_speak('Aidez-moi c\'est urgent!')"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-sos"></use>
            </svg>
            <h3>{{translations['Help!']}}</h3>
        </button>
    </div>
</template>
<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
export default {
    name: "shortcuts",
    mixins: [BasePluginComponent],
    data() {
        return {
            websocket: null,  // Store WebSocket instance
            status: 'loading',
            paroles: [
                translations["I'm on my way, just finishing writing"],
                translations["Just a moment, I'll finish"],
                translations["One second and it's done"],
                translations["Just give me two seconds"],
                translations["I'm just finishing"]
            ]
        };
    },
    methods: {
        $_speak(msg) {
            const json = { action: "speak", msg: msg };
            console.log("sending JSON");
            console.log(json);
            this.sendMsgToBackend(json);
        },
        $_minimise(){
            window.pywebview.api.win_minimize()
        },
        $_parole(){
            const randomIndex = Math.floor(Math.random() * this.paroles.length);
            const randomMsg = this.paroles[randomIndex];
            this.$_speak(randomMsg);
        }
    }
};
</script>

<style scoped>
.shortcuts {
    display: flex;
    flex-wrap: nowrap;
    justify-content: space-between;
    gap: 4px;
    padding: 4px;
    width: 100%;
}

.btn-shortcut {
    flex: 1 1 0;
    min-width: 0;
    max-width: none;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 8px 4px;
}

.btn-shortcut .icon,
.btn-shortcut img {
    width: 100%;
    height: auto;
    max-width: 64px;
    max-height: 64px;
    object-fit: contain;
}


.btn-shortcut h3 {
    margin: 4px 0 0 0;  /* Slightly increased top margin */
    font-size: 0.8em;
    white-space: nowrap;
}
</style>