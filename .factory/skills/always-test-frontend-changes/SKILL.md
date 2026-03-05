---
name: always-test-frontend-changes
description: Whenever you make changes to the frontend (Vue components, templates, CSS), test them in the browser before confirming they work.
---
# Always Test Frontend Changes in Browser

## Prerequisites

Before testing, ensure the IGOOR application is running:

1. **Activate the virtual environment** (if not already active):
   ```bash
   venv/scripts/activate
   ```

2. **Start the IGOOR server**:
   ```bash
   python main.py
   ```

## Testing Procedure

Use Playwright or your browser of choice to test all frontend changes:

1. **Navigate to `http://localhost:9714/`**
2. **Test the specific changes** you made:
   - UI components and their interactions
   - Plugin functionality (settings, forms, buttons)
   - Responsive behavior and accessibility
   - Loading states, error handling, success states

3. **Accessing plugins settings**:
   - Click on the **settings gear** icon in the top-right header
   - Click on the **extensions tab**
   - Navigate to the relevant plugin category and click on the settings gear of the specific plugin

4. **For onboarding plugin specifically**:
   - Access the onboarding plugin by clicking on the settings gear
   - Navigate through the onboarding flow

## Success Criteria

Only say "it works" when:
- All UI changes render correctly
- All interactions (clicks, form submissions, state changes) work as expected

## Debugging Process

If changes don't work:

1. **Check browser console** for JavaScript errors
2. **Inspect elements** to verify HTML structure and CSS
3. **Check WebSocket connections** at `ws://localhost:9715/plugin_name` if applicable
4. **Review REST API calls** at `http://localhost:9714/api/...` if applicable
5. **Fix issues iteratively** and retest until functionality is verified

## Notes

- This skill applies to ALL frontend changes: Vue components, templates, LESS files
- Never assume changes work without browser verification
- Test across different viewport sizes if responsive design is relevant
- For accessibility-critical features, test keyboard navigation and screen reader compatibility 