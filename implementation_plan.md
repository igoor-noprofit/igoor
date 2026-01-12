# Common Plugin Settings Save Button Implementation Plan

This plan outlines the steps to implement a reusable "Save Settings" button for IGOOR plugins, leveraging the existing `BasePluginComponent.js` and `baseplugin.py` infrastructure.

## Goal Description
Implement a standard, reusable mechanism for saving plugin settings that provides:
1.  **Dirty Checking**: Automatically detect unsaved changes by comparing current settings with original settings.
2.  **UI Consistency**: A common `SaveSettingsButton` component.
3.  **Ease of Use**: Minimal boilerplate for plugin developers.

## User Review Required
> [!IMPORTANT]
> This plan modifies `js/BasePluginComponent.js` which is a core file used by all plugins. While the changes are additive, they should be tested to ensure no regression in existing plugins.

## Proposed Changes

### Core Infrastructure

#### [MODIFY] [BasePluginComponent.js](file:///c:/AIKU/experiments/igoor/js/BasePluginComponent.js)
Enhance the base component to handle settings state tracking.

**Changes:**
1.  **Data**: Add `originalSettings` (null by default) to store the clean state of settings.
2.  **Methods**:
    -   `setOriginalSettings(settings)`: Helper to deep copy and set original settings.
    -   `resetSettings()`: Reverts `formData` (or the plugin's data matching the settings structure) to `originalSettings`.
    -   `saveSettings()`: Standard method to call backend save hook.
3.  **Computed**:
    -   `hasUnsavedChanges`: Performs deep comparison between `formData` (or equivalent) and `originalSettings`.
4.  **Lifecycle**:
    -   Update `updateSettings` (or creating a new `saveSettings` method) to update `originalSettings` upon successful save.
    -   Update `handleIncomingMessage` to populate `originalSettings` when `get_settings` response is received.

### Shared UI Component

#### [NEW] [SaveSettingsButton.vue](file:///c:/AIKU/experiments/igoor/js/SaveSettingsButton.vue)
Create a standalone Vue component for the buttons.

**Features:**
-   **Props**:
    -   `hasChanges`: Boolean (controls disabled state).
    -   `loading`: Boolean (optional, for spinner).
    -   `t`: Function (translation function).
-   **Events**:
    -   `save`: Emitted when Save is clicked.
    -   `cancel`: Emitted when Cancel is clicked.
-   **Template**:
    -   Standard "Cancel" (secondary) and "Save" (primary) buttons.
    -   Styled using existing app CSS classes (`btn`, `btn-primary`, `btn-secondary`).

## Verification Plan

### Manual Verification
1.  **Test Plugin**: Create a simple "Test Plugin" (or use a temporary one) that implements the new system.
    -   Import `SaveSettingsButton.vue`.
    -   Mix in `BasePluginComponent`.
    -   Display settings form.
2.  **Verify Dirty Checking**:
    -   Change a value -> "Save" and "Cancel" buttons become enabled.
    -   Change it back -> Buttons become disabled.
3.  **Verify Reset**:
    -   Change value -> Click "Cancel" -> Value reverts to original.
4.  **Verify Save**:
    -   Change value -> Click "Save" -> Data sent to backend -> Backend saves -> "Save" button becomes disabled (new state accepted).

### Automated Testing Strategy (Future Work)
Since the project uses Vue 3, the recommended testing stack for future implementation would be:

1.  **Framework**: **Vitest** (for the test runner) + **@vue/test-utils** (for mounting components).
2.  **Location**: `tests/frontend/`.
3.  **Setup**:
    -   Since the app uses `httpVueLoader` and no build step, the test environment would need to mock the browser environment (JSDOM) and handle `.vue` file compilation on the fly.
4.  **Test Cases**:
    -   **`SaveSettingsButton.spec.js`**: Unit test. Mount the component, simulate clicks, and verify `save`/`cancel` events are emitted. Check that buttons are disabled when `hasChanges` prop is false.
    -   **`BasePluginComponent.spec.js`**: Integration test. Create a wrapper component that mixes in `BasePluginComponent`. Mock `window.ensureBackendApi` and `fetch`.
        -   *Test*: Call `setOriginalSettings`, modify data, assert `hasUnsavedChanges` is true.
        -   *Test*: Call `resetSettings`, assert data returns to original.
