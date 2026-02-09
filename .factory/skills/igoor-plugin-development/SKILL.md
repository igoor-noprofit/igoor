---
name: igoor-plugin-development
description: Guidelines and instructions for creating a new plugin for IGOOR, including file structure, configuration, API, and WebSockets.
---

# IGOOR Plugin Development

This skill provides the comprehensive guide for developing plugins for IGOOR.

## 1. Plugin Structure

Plugins are located in the `plugins/` directory. Each plugin is a subdirectory (e.g., `plugins/myplugin/`).

### Required Files
- **`plugin.json`**: Manifest configuration.
- **`settings.json`**: (Optional) Default settings configuration.
- **Backend Code**: Python file, typically named `{plugin_name}.py` (e.g., `myplugin.py`).
- **Frontend Code**: `frontend/` directory containing Vue components (e.g., `frontend/myplugin_component.vue`).

### Directory Layout
```text
plugins/
  └── myplugin/
      ├── plugin.json
      ├── settings.json       # Optional
      ├── myplugin.py         # Main logic (if any backend needed)
      └── frontend/
          └── myplugin_component.vue
```

## 2. Configuration Files

### `plugin.json`
Defines metadata and UI integration.

```json
{
    "active": false,                 // Default activation state
    "category": "context",           // Category (e.g., context, productivity)
    "title": "My Plugin",            // Display title
    "description": "Description...", // Short description
    "layout": {
        "part": "topbar",            // UI Area: 'topbar', 'sidebar', 'main'
        "order": 50                  // Order priority
    },
    "is_free": true,
    "requires_subscription": false,
    "requires_internet": true,
    "status": "suspended"            // 'active', 'suspended', etc.
}
```

### `settings.json`
Defines key-value pairs for plugin configuration. Use flat structures.

```json
{
    "api_key": "",
    "refresh_rate": 60,
    "theme": "dark"
}
```

## 3. Backend Implementation

- **Location**: `plugins/myplugin/myplugin.py` (or similar).
- **Integration**:
  - The system automatically loads plugins in `plugin_manager.py`.
  - Use `settings_manager` to access/update settings.
  - API endpoints in `fastapi_app.py` handle generic settings/toggling.
  - Implement custom logic by hooking into system events or exposing new API routes if necessary (though modifying `fastapi_app.py` directly is discouraged for plugins; prefer using existing hooks).

### Leveraging `Baseplugin`
Always inherit from `Baseplugin` (in `baseplugin.py`) to access built-in utilities:

- **Communication**: `self.send_message_to_frontend(message)`
- **Database**: `await self.db_execute(query, params)` (handles connection and pooling)
- **Settings**: `self.get_my_settings()`, `self.update_my_settings(key, value)`
- **Translations**: `self.get_my_translations()`

```python
from plugins.baseplugin.baseplugin import Baseplugin

class MyPlugin(Baseplugin):
    def __init__(self, plugin_name, pm):
        super().__init__(plugin_name, pm)
        # Your initialization
```

## 4. Frontend Implementation

- **Location**: `plugins/myplugin/frontend/*.vue`.
- **Integration**:
  - Vue components are dynamically loaded.
  - Use standard Vue 3 syntax.
  - Communicate with backend details via API or WebSocket.

### Leveraging `BasePluginComponent`
Always use `BasePluginComponent` mixin to access built-in frontend utilities:

- **API Calls**: `await this.callPluginRestEndpoint(pluginName, endpoint, options)` (handles auth/routing)
- **Translations**: `this.t('key')` (automatically loads from your locale files)
- **Settings**: `this.requestSettings()`, `this.updateSettings()` (works with `settings.json` and `formData`)
- **WebSockets**: `this.sendMsgToBackend(data)` (handles connection management)

```javascript
import BasePluginComponent from '/js/BasePluginComponent.js';

export default {
    mixins: [BasePluginComponent],
    // ...
}
```

### Settings Component (`{plugin_name}_settings.vue`)
To allow users to configure your plugin, create a `*_settings.vue` component.

#### Best Practices (based on `asrjs`):
1.  **Mixin**: Use `BasePluginComponent`.
2.  **Save Button**: Use `SaveSettingsButton`.
3.  **Layout**: Use `.form-grid` with `.form-label`, `.form-input`, and `.form-note`.
4.  **Data Management**: Initialize `formData` from `initialSettings` prop.

#### Example Template
```vue
<template>
    <div class="myplugin-settings form-grid">
        <!-- Setting 1 -->
        <div class="form-label">API Key</div>
        <div class="form-input">
            <input type="text" v-model="formData.api_key" placeholder="Enter API Key" />
        </div>
        <div class="form-note">Your private API key.</div>

        <!-- Setting 2 -->
        <div class="form-label">Refresh Rate</div>
        <div class="form-input">
             <select v-model.number="formData.refresh_rate">
                <option value="30">30 seconds</option>
                <option value="60">60 seconds</option>
            </select>
        </div>
        <div class="form-note"></div>

        <!-- Save Button -->
        <div class="form-label"></div>
        <div class="form-input">
            <SaveSettingsButton
                :hasChanges="hasUnsavedChanges"
                :loading="loading"
                @save="saveSettings"
                @cancel="resetSettings"
            />
        </div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
import SaveSettingsButton from '/js/SaveSettingsButton.vue';

export default {
    name: "MyPluginSettings",
    mixins: [BasePluginComponent],
    components: { SaveSettingsButton },
    data() {
        return {
            formData: {
                api_key: '',
                refresh_rate: 60
            },
            loading: false
        };
    },
    computed: {
        hasUnsavedChanges() {
            if (!this.originalSettings || !this.formData) return false;
            return JSON.stringify(this.formData) !== JSON.stringify(this.originalSettings);
        }
    },
    watch: {
        initialSettings: {
            handler(newVal) {
                if (newVal) {
                    this.$nextTick(() => {
                        this.setOriginalSettings(newVal);
                        this.formData = { ...newVal };
                    });
                }
            },
            immediate: true,
            deep: true
        }
    }
};
</script>

<style scoped>
.form-grid {
    display: grid;
    grid-template-columns: 200px 1fr 2fr;
    gap: 12px 18px;
    align-items: start;
    padding: 18px 0;
}
.form-label { text-align: right; font-weight: 500; padding-top: 6px; color: #e0e0e0; }
.form-note { font-size: 0.9em; color: #aaa; padding-top: 2px; }
input, select { background: #222; color: #fff; border: 1px solid #444; padding: 6px; border-radius: 4px; }
</style>
```

## 5. API Endpoints

The core `fastapi_app.py` provides standard endpoints:

- **Get Settings**: `GET /api/plugins/{plugin_name}/settings`
- **Update Settings**: `POST /api/plugins/{plugin_name}/settings`
- **Toggle Plugin**: `POST /api/plugins/{plugin_name}/toggle` { "active": true/false }
- **Trigger Hook**: `POST /api/hooks/{hook_name}`

> [!NOTE]
> **Communication Best Practice**: Always prefer using standard, testable FastAPI endpoints (GET/POST) for communication from the frontend to the backend. Use WebSockets only when strictly necessary for real-time bidirectional streaming.

## 6. WebSockets

Plugins can use real-time communication via the central WebSocket hub.

- **Endpoint**: `/ws/{plugin_name}`
- **Server Implementation**: `websocket_server.py`.
    - **Connect**: `await websocket_server.connect(plugin_name, websocket)`
    - **Handle**: `await websocket_server.handle_message(plugin_name, message)`
    - **Send**: `websocket_server.send_message(plugin_name, message)`
- **Client Implementation**:
    - Connect to `wss://<host>/ws/myplugin`.
    - Listen for messages and send commands.

## Instructions for Creating a New Plugin

1.  **Create Directory**: `mkdir plugins/<plugin_name>`.
2.  **Manifest**: Create `plugin.json` with unique title and appropriate category.
3.  **Settings**: Create `settings.json` if configuration is needed.
4.  **Frontend**: Create `frontend/<plugin_name>_component.vue`.
5.  **Backend**: Write `<plugin_name>.py` for logic.
6.  **Verify**: Restart IGOOR and check the `/api/plugins/by-category` endpoint or the UI.
