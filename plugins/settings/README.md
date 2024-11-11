# SETTINGS
This plugin is used to manage settings for all the plugins. 

## HOW IT WORKS
For each plugin (except this one and baseplugin), it should dynamically load :

```
/plugins/pluginname/frontend/pluginname_settings.vue
```

where the Vue file contains an interface to change the settings of the plugin, if the plugin is active (otherwise, it only shows a checkbox to activate the plugin).

To activate the plugin, we should use:

```
plugin_manager.activate_plugin
```


