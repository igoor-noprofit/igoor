---
name: manage-translations
description: Update existing language translations or create new language translations based on the French source of truth. Use when adding missing translations to existing languages or adding support for completely new languages in IGOOR.
disable-model-invocation: true
---

# Skill: Manage IGOOR Translations

## Purpose

Update existing language translations or create new language translations based on the **French source of truth**. This skill handles both plugin-level and application-level translations, ensuring consistency across all supported languages.

## When to use this skill

- **Updating existing languages**: When French translations have been updated and other languages need to be synchronized
- **Adding new languages**: When introducing support for a completely new language in IGOOR
- **Maintaining consistency**: When translation files have fallen out of sync or are missing keys

## Translation Structure

### Language Hierarchy

- **French (fr_FR)**: always update French translations first
- **English (en_EN)**: Default language - no translation files needed (uses English strings directly) - Source of truth for keys in code
- **Other languages**: Must have complete translations matching English keys

### File Locations

**Plugin-level translations**:
```
plugins/{plugin_name}/locales/{lang}/{plugin_name}_{lang}.json
```
Example: `plugins/onboarding/locales/fr_FR/onboarding_fr_FR.json`

**App-level translations**:
```
locales/{lang}/common_{lang}.json
```
Example: `locales/fr_FR/common_fr_FR.json`

### Language Codes

Format: `{language}_{REGION}`
- `fr_FR` - French (France)
- `en_EN` - English (default)
- Follow this pattern for new languages (e.g., `de_DE` for German, `es_ES` for Spanish)

## Process

### 1. Identify Scope and Target Language(s)

Determine:
- **Target language(s)**: Which language(s) to update or add?
- **Scope**: Plugin-specific or app-wide?
- **If plugin-specific**: Which plugin(s)?

### 2. Analyze French Source

**For plugin translations**:
1. Read the French source file: `plugins/{plugin_name}/locales/fr_FR/{plugin_name}_fr_FR.json`
2. Extract all translation keys and their values
3. Document any new keys that need to be translated

**For app translations**:
1. Read the French source file: `locales/fr_FR/common_fr_FR.json`
2. Extract all translation keys and values

### 3. Updating Existing Languages

1. **Locate the target language file**: `plugins/{plugin_name}/locales/{lang}/{plugin_name}_{lang}.json`
2. **Compare with French source**: Identify missing keys in the target language
3. **Add missing keys**: Copy keys from French source with their structure
4. **Translate values**: Replace French values with appropriate translations for the target language
5. **Maintain existing translations**: Don't overwrite already translated values unless they're incorrect

### 4. Adding New Languages

1. **Create directory structure**: `plugins/{plugin_name}/locales/{new_lang}/`
2. **Create translation file**: `{plugin_name}_{new_lang}.json`
3. **Copy French structure**: Use all keys from French source as the template
4. **Translate all values**: Replace French values with appropriate translations
5. **Handle pluralization**: Ensure grammatical forms match the target language
6. **Consider cultural context**: Adapt idioms and cultural references appropriately

### 5. Special Files

**AI Prompts (YAML files)**:
Some plugins have `prompts.yaml` files in `locales/fr_FR/`:
- Check if these need translation for the target language
- If needed, create `locales/{lang}/prompts.yaml` with translated prompts
- Maintain the same YAML structure and key format
- FRENCH is the source of truth for prompts: NEVER update the french file from other languages

### 6. Validation

**JSON Structure**:
1. Verify JSON syntax is valid (no trailing commas, proper quoting)
2. Ensure all keys are unique within each file
3. Confirm file is properly encoded (UTF-8)

**Key Consistency**:
1. Verify all language files have the exact same keys as English source
2. Check that no keys are missing or extra
3. Ensure key names match exactly (case-sensitive)

**Translation Quality**:
1. Verify translations make sense in context
2. Check for placeholders like `{{variable}}` are preserved
3. Ensure special characters and formatting are maintained

### 7. Testing

**Manual Testing**:
1. **Start IGOOR application** with the target language selected
2. **Navigate through the UI**: Check that translations appear correctly
3. **Test plugin settings**: Verify all settings labels and messages are translated
4. **Check for missing translations**: Look for any English fallback or empty strings
5. **Test edge cases**: Verify error messages, loading states, and empty states

**Language Selection**:
- Language is set via `{{LANG}}` placeholder in `app_template.js`
- Test by changing the language setting in the application

## Verification Checklist

Before completing the skill, ensure:

- [ ] All target language files have been created or updated
- [ ] All JSON files are valid and properly formatted
- [ ] All language files have the same keys as French source
- [ ] No missing keys in target language files
- [ ] No extra keys in target language files
- [ ] Translations are contextually appropriate
- [ ] Placeholders and variables are preserved
- [ ] Special characters and formatting are maintained
- [ ] Application loads translations without errors
- [ ] UI displays translations correctly when language is selected
- [ ] No console errors related to translation loading

## Important Notes

### English as Default
- English (en_EN) doesn't need translation files
- The application uses English strings directly as default
- When no translation file exists, the English string is displayed

### Translation Loading
- The `BasePluginComponent.js` loads translations via `loadTranslations()` method
- It fetches files from `/plugins/{plugin_name}/locales/{lang}/{plugin_name}_{lang}.json`
- If loading fails, it falls back to empty translations (showing original strings)

### French as Source of Truth
- Always update French translations first
- Never add keys to non-French languages without adding them to French

### File Permissions
- Translation files are in the plugin directories
- New language directories can be created in any plugin's `locales/` folder

## Common Issues and Solutions

**Missing translations displayed in English**:
- Check that the translation file exists in the correct location
- Verify the language code matches exactly (case-sensitive)
- Ensure the application is running with the correct language selected

**JSON parsing errors**:
- Check for trailing commas in JSON files
- Verify proper quoting of strings
- Ensure no unescaped special characters

**Translations not appearing**:
- Clear browser cache if testing web interface
- Restart the IGOOR application after changes
- Check browser console for translation loading errors

## Safety and Escalation

- **Stop** if you need to modify the application's core language selection logic
- **Escalate** if translation requires changes to plugin.json or core application files
- **Be careful** with cultural translations - some concepts may not translate directly and may require localization expertise