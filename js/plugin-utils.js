// js/plugin-utils.js
window.callPluginBackend = async function (moduleName, targetFunctionName, ...args) {
    console.log('calling ' + targetFunctionName + ' in ' + moduleName);
    if (window.pywebview && window.pywebview.api) {
        try {
            const result = await window.pywebview.api.call_plugin_backend(moduleName, targetFunctionName, args);
            console.log('Backend function result:', result);
            return result;
        } catch (error) {
            console.error('Error calling backend function:', error);
            throw error;
        }
    } else {
        console.error('Pywebview API is not available.');
        throw new Error('Pywebview API is not available.');
    }
}