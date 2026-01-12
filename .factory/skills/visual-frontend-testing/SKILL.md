---
name: visual-frontend-testing
description: Automatically test IGOOR pywebview application visually using Playwright MCP after any frontend modifications. Verify UI changes, accessibility, and user flows at http://127.0.0.1:9714/
---

# Visual Frontend Testing for IGOOR

## When to Use

**Automatically invoke this skill when:**
- Frontend files are modified (`.vue`, `.js` in `/js/` or `/css/`)
- UI components are added, changed, or removed
- Plugin settings interfaces are modified (`plugin_name_settings.vue`)
- Base component or shared utilities are updated (`BasePluginComponent.js`, `app_template.vue`)
- Styles or layout changes are made (`.less`, `.css` files)

**Do NOT use when:**
- Only backend Python code is changed (`.py` files without frontend impact)
- Database schema changes only
- Documentation updates only
- Configuration-only changes

## Prerequisites

Before testing, verify:
- IGOOR app is running at `http://127.0.0.1:9714/`
- App is running in Python mode (not as executable) for proper debugging
- Playwright MCP server is available (`playwright___*` tools are functional)

**If app is not running:**
```bash
# Activate virtual environment
venv\scripts\activate

# Run IGOOR
python main.py
```

Wait for app to be fully loaded before proceeding with visual testing.

## Testing Workflow

### 1. Verify App Status
- Use `playwright___browser_navigate` to open `http://127.0.0.1:9714/`
- Take initial snapshot with `playwright___browser_snapshot`
- Verify page loads successfully (no errors in console)
- Check for any frontend errors via `playwright___browser_console_messages`

### 2. Take Baseline Screenshot
- Capture full-page screenshot using `playwright___browser_take_screenshot` with `fullPage: true`
- Save screenshot with descriptive filename (e.g., `page-{timestamp}.png`)

### 3. Navigate to Modified Areas

**For plugin settings changes:**
- Click settings gear icon in header (top-right)
- Navigate to Extensions tab
- Navigate to appropriate plugin category
- Take snapshot before interacting
- Interact with modified UI elements
- Take snapshot after interaction

**For main UI changes:**
- Navigate to relevant views/screens
- Test user flows affected by changes
- Verify accessibility elements are present

**For component changes:**
- Locate and interact with the component using Playwright selectors
- Verify all interactive states (hover, click, focus)
- Check responsive behavior if applicable

### 4. Verify Functionality

**Test all modified features:**
- Click buttons, fill forms, interact with inputs
- Verify WebSocket connections are established (check console logs)
- Ensure settings save/load correctly
- Test any new REST API calls via the UI

**Accessibility checks:**
- Verify all buttons are large enough (for users with physical conditions)
- Check keyboard navigation works
- Ensure proper ARIA labels are present
- Verify color contrast meets accessibility standards

### 5. Console and Network Verification
- Check `playwright___browser_console_messages` for errors or warnings
- Review `playwright___browser_network_requests` for failed API calls
- Look for WebSocket connection issues
- Verify no 404 or 500 errors on resource loading

### 6. Final Verification

**For each modified UI element:**
1. Take screenshot before action
2. Perform the action
3. Take screenshot after action
4. Compare snapshots to verify expected behavior
5. Check console for any errors during action

**For settings changes:**
1. Navigate to settings
2. Take initial snapshot
3. Modify settings
4. Save changes
5. Reload page
6. Verify settings persisted correctly
7. Take final screenshot

## Success Criteria

**The skill is successful when:**
- All modified UI elements render correctly
- No console errors or warnings appear
- All user interactions work as expected
- Settings save and load properly
- Accessibility requirements are met
- Screenshots show expected visual changes
- Network requests complete successfully

**Fail conditions:**
- App fails to load at `http://127.0.0.1:9714/`
- Console shows errors related to frontend changes
- UI elements are broken or unresponsive
- Settings don't persist after save/reload
- Accessibility violations detected
- Network requests fail

## Common Test Scenarios

### Plugin Settings Modification
```javascript
// Example: Navigate to plugin settings
await playwright___browser_navigate({ url: 'http://127.0.0.1:9714/' });
await playwright___browser_snapshot();
await playwright___browser_click({
  element: 'Settings gear icon',
  ref: '[aria-label="settings"]'
});
// Navigate to extensions tab
// Navigate to plugin category
// Test modified settings UI
```

### Component Interaction
```javascript
// Example: Test button interaction
await playwright___browser_snapshot();
await playwright___browser_click({
  element: 'Modified button',
  ref: 'button[data-action="new-action"]'
});
await playwright___browser_wait_for({ time: 2 }); // Allow UI to update
await playwright___browser_snapshot();
await playwright___browser_console_messages({ level: 'error' });
```

### Form Testing
```javascript
// Example: Fill and submit form
await playwright___browser_fill_form({
  fields: [
    { name: 'Input field', type: 'textbox', ref: '#input-id', value: 'test value' },
    { name: 'Checkbox', type: 'checkbox', ref: '#checkbox-id', value: 'true' }
  ]
});
await playwright___browser_snapshot();
// Submit form
// Verify result
```

## Post-Testing

After completing visual testing:
1. Document any issues found with file paths and line numbers
2. Provide clear steps to reproduce any bugs
3. Include screenshots showing the issue
4. Suggest specific fixes if obvious
5. Report all console errors with full stack traces

## Important Notes

- **Always test in Python mode** (`python main.py`), not as executable
- **Test on the actual browser** using Playwright MCP, not just code review
- **Take multiple screenshots** to document visual state changes
- **Check console messages** - frontend errors often don't appear in code review
- **Verify accessibility** - IGOOR serves users with physical conditions
- **Test user flows** end-to-end, not just individual components
- **Verify WebSocket connections** are established for plugins
- **Check settings persistence** after page reload

## IGOOR-Specific Considerations

- App runs at `http://127.0.0.1:9714/`
- Settings accessible via top-right gear icon → Extensions tab
- Plugins organized by categories in settings
- Vue 3 with httpVueLoader for component loading
- WebSocket connections on port 9714 for plugin communication
- REST API available at `http://localhost:9714/api/`
- All files in `/js/` and `/css/` are front-end
- Plugin settings files follow pattern: `plugins/plugin_name/frontend/plugin_name_settings.vue`
- Never edit `app.js` or `app.vue` - only `app_template.js` and `app_template.vue`
- Never edit `css/app.css` - only `css/app.less`
- Use predefined colors from `/css/app.less` when testing UI
- Verify buttons are appropriately sized for users with physical conditions
