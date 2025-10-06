<template>
    <div class="shortcuts shortcuts-plugin" v-show="appview != 'onboarding'" :class="{ 'shrink': shrink }">
        <button class="btn btn-shortcut" @click="$_minimise()">
            <img src="img/minimize.svg">
            <h3 v-show="!shrink">{{ t('Minimize window') }}</h3>
            <h3 v-show="shrink">{{ t('Minimize') }}</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_speak(t('I\'m thirsty'))"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-drink"></use>
            </svg>
            <h3>{{ t('Drink') }}</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_speak(t('I need to go to the toilet'))"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-toilet"></use>
            </svg>
            <h3>{{ t('Toilet') }}</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_parole()"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-talk"></use>
            </svg>
            <h3>{{ t('Just a sec') }}</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_speak(t('Yes'))"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-ok"></use>
            </svg>
            <h3>{{ t('Yes') }}</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_speak(t('No'))"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-no"></use>
            </svg>
            <h3>{{ t('No') }}</h3>
        </button>
        <button class="btn btn-shortcut" @click="$_speak(t('Thanks'))"><svg class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-thankyou"></use>
            </svg>
            <h3>{{ t('Thanks') }}</h3>
        </button>
        <button class="btn btn-shortcut btn-hilite" @click="$_speak(t('Please help me, it\'s urgent!'))"><svg
                class="icon icon-l">
                <use xlink:href="img/svgdefs.svg#icon-sos"></use>
            </svg>
            <h3>{{ t('Help!') }}</h3>
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
            shrink: false
        };
    },
    computed: {
        paroles() {
            return [
                this.t("I'm on my way, just finishing writing"),
                this.t("Just a moment, I'll finish"),
                this.t("One second and it's done"),
                this.t("Just give me two seconds"),
                this.t("I'm just finishing")
            ];
        }
    },
    methods: {
        $_speak(msg) {
            const json = { action: "speak", msg: msg };
            console.log("sending JSON");
            console.log(json);
            this.sendMsgToBackend(json);
        },
        $_minimise() {
            window.pywebview.api.win_minimize()
        },
        $_parole() {
            console.log(this.paroles);
            const randomIndex = Math.floor(Math.random() * this.paroles.length);
            const randomMsg = this.paroles[randomIndex];
            console.log("Sending random parole:", randomMsg);
            this.$_speak(this.t(randomMsg));
        },
        handleIncomingMessage(event) {
            const data = JSON.parse(event.data);
            if (data.action == "shrink") {
                this.shrink = true;
            }
            if (data.action == "unshrink") {
                this.shrink = false;
            }
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
.shortcuts.shrink{
    max-height: 70px;
}
.shrink svg.icon, .shrink img {
    display: none;
}
.shrink .btn-shortcut h3 {
    font-size: 1.2em;
    font-weight: bold;
}
.shrink .btn-shortcut:not(.btn-hilite) {
    background: #28373b;
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
    margin: 4px 0 0 0;
    /* Slightly increased top margin */
    font-size: 0.8em;
    white-space: nowrap;
}
</style>