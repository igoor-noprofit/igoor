document.addEventListener("DOMContentLoaded", function () {
    var data = {
        pywebviewready: false,
    };
    const app = new Vue({
        el: "#app",
        components: {
        'Baseplugin': httpVueLoader('/plugins/baseplugin/frontend/baseplugin_component.vue'), 'Clock': httpVueLoader('/plugins/clock/frontend/clock_component.vue'), 'Sttvosk': httpVueLoader('/plugins/sttvosk/frontend/sttvosk_component.vue')
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
            },
            js_api(func){
                if (this[func] && typeof this[func] === 'function') {
                    this[func]();
                } else {
            
                    console.error(`Method '${func}' does not exist or is not a function`);
            
                }
            }
          }
    });
});
