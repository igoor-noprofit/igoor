<template>
    <div class="shortcuts shortcuts-plugin" v-show="appview != 'onboarding'" :class="{ 'shrink': shrink }">
        <button class="btn btn-shortcut" @click="$_minimise()">
            <img src="img/minimize.svg">
            <h3 v-show="!shrink">{{ t('Minimize window') }}</h3>
            <h3 v-show="shrink">{{ t('Minimize') }}</h3>
        </button>
        <button
            v-for="(button, index) in shortcutButtons"
            :key="button.key"
            class="btn btn-shortcut"
            :class="{ 'btn-hilite': button.highlight }"
            @click="$_handleShortcut(button, index)"
        >
            <svg class="icon icon-l">
                <use :xlink:href="'img/svgdefs.svg#' + button.icon"></use>
            </svg>
            <h3>{{ button.label }}</h3>
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
        },
        shortcutButtons() {
            return [
                {
                    key: 'drink',
                    icon: 'icon-drink',
                    label: this.t('Drink'),
                    msg: this.t("I'm thirsty"),
                    random: false,
                    highlight: false
                },
                {
                    key: 'toilet',
                    icon: 'icon-toilet',
                    label: this.t('Toilet'),
                    msg: this.t('I need to go to the toilet'),
                    random: false,
                    highlight: false
                },
                {
                    key: 'parole',
                    icon: 'icon-talk',
                    label: this.t('Just a sec'),
                    random: true,
                    highlight: false
                },
                {
                    key: 'yes',
                    icon: 'icon-ok',
                    label: this.t('Yes'),
                    msg: this.t('Yes'),
                    random: false,
                    highlight: false
                },
                {
                    key: 'no',
                    icon: 'icon-no',
                    label: this.t('No'),
                    msg: this.t('No'),
                    random: false,
                    highlight: false
                },
                {
                    key: 'thanks',
                    icon: 'icon-thankyou',
                    label: this.t('Thanks'),
                    msg: this.t('Thanks'),
                    random: false,
                    highlight: false
                },
                {
                    key: 'help',
                    icon: 'icon-sos',
                    label: this.t('Help!'),
                    msg: this.t("Please help me, it's urgent!"),
                    random: false,
                    highlight: true
                }
            ];
        }
    },
    methods: {
        $_speak(bid, msg) {
            const json = { action: "speak", msg: msg, bid };
            console.log("sending JSON");
            console.log(json);
            this.sendMsgToBackend(json);
        },
        $_minimise() {
            window.ensureBackendApi().then((api) => api.winMinimize());
        },
        $_parole(bid) {
            const randomIndex = Math.floor(Math.random() * this.paroles.length);
            const randomMsg = this.paroles[randomIndex];
            this.$_speak(bid, randomMsg);
        },
        $_handleShortcut(button, index) {
            if (button.random) {
                this.$_parole(index);
                return;
            }
            this.$_speak(index, button.msg);
        },
        handleIncomingMessage(event) {
            try {
                const data = JSON.parse(event.data);
                if (data.action === "shrink") {
                    this.shrink = true;
                }
                if (data.action === "unshrink") {
                    this.shrink = false;
                }
            } catch (error) {
                console.warn('Shortcuts plugin received non-JSON message:', event.data);
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