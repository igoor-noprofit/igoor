<template>
    <div class="shortcuts shortcuts-plugin">
        <button class="btn btn-shortcut" @click="$_speak('J\'ai soif')"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-drink"></use>
            </svg>
            <h3>Boire</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_speak('J\'ai besoin d\'aller au toilette')"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-toilet"></use>
            </svg>
            <h3>Toilette</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_speak('Oui')"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-ok"></use>
            </svg>
            <h3>Oui</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_minimise()"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-minimize"></use>
            </svg>
            <h3>Réduire la fenetre</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_speak('Non')"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-no"></use>
            </svg>
            <h3>Non</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_speak('Merci')"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-thankyou"></use>
            </svg>
            <h3>Merci</h3>
        </button>
        <button class="btn btn-shortcut btn-hilite" @click="$_speak('Aidez-moi c\'est urgent!')"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-sos"></use>
            </svg>
            <h3>Aide!</h3>
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
            status: 'loading'
        };
    },
    created() {
        
    },
    beforeUnmount() {
        
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
    padding: 8px 4px;  /* Increased vertical padding */
}

.btn-shortcut .icon {
    width: 64px;  /* Increased icon size */
    height: 64px;  /* Increased icon size */
}

.btn-shortcut h3 {
    margin: 4px 0 0 0;  /* Slightly increased top margin */
    font-size: 0.8em;
    white-space: nowrap;
}
</style>