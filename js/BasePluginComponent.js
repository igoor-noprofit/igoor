// js/BasePluginComponent.js
console.log('BasePluginComponent is being imported');

module.exports = {
    data() {
        return {
            websocketUtil: null
        };
    },
    methods: {
        commonMethod() {
            console.log("This is a common method");
        },
        invokeBackend() {
            if (this.websocketUtil) {
                this.websocketUtil.send({ type: 'invoke_backend', data: 'some_data' });
            }
        },
        handleIncomingMessage(event) {
            console.log("Received message from backend:", event.data);
        }
    },
    created() {
        console.log('BasePluginComponent created hook');
    },
    beforeDestroy() {
        if (this.websocketUtil) {
            this.websocketUtil.close();
        }
    }
};