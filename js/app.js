document.addEventListener('DOMContentLoaded', function() {
    const app = new Vue({
        el: '#app',
        components: {
            'Clock': httpVueLoader('/plugins/clock/frontend/clock_component.vue'), 'Geo': httpVueLoader('/plugins/geo/frontend/geo_component.vue'), 'Meteo': httpVueLoader('/plugins/meteo/frontend/meteo_component.vue'), 'Flow': httpVueLoader('/plugins/flow/frontend/flow_component.vue')
        }
    });
});