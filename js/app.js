document.addEventListener("DOMContentLoaded", function () {
    var data = {
        pywebviewready: false,
    };
    const app = new Vue({
        el: "#app",
        components: {
        'Elevenlabs': httpVueLoader('/plugins/elevenlabs/frontend/elevenlabs_component.vue')
        },
        data: data,
        mounted: function () {
            window.addEventListener("pywebviewready", async function () {
                app.pywebviewready = true;
                console.log("Python is ready!");
            });
        },
        methods: {
            showDaily() {
                this.daily = true;
            },
            minimize() {
                if (!this.minimized) {
                pywebview.api.minimize_window();
                this.minimized = true;
                }
            },
            maximize() {
                if (this.minimized) {
                pywebview.api.maximize_window();
                this.minimized = false;
                }
            }
            /* useless wrapper?
            js_api(func, ...args){
                if (this[func] && typeof this[func] === 'function') {
                    pywebview.api[func](...args);
                } else {
                    console.error(`Method '${func}' does not exist or is not a function`);
                }
            }
            */
        }
    });
});
