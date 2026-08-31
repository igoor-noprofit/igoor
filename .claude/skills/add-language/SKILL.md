---
name: add-language
description: >
  Add a new language/translation to the IGOOR application. Use when the user wants to
  add a new language, translate the app, support a new locale, or add i18n translations.
  Triggers on phrases like "add language", "add translation", "new language", "translate app",
  "add Spanish/German/Portuguese", "support a new locale", "internationalize".
  Usage: /add-language <locale_code> <language_name>
  Example: /add-language es_ES Spanish
  Example: /add-language de_DE German
version: 1.0.0
argument-hint: "<locale_code> <language_name>  e.g. es_ES Spanish"
allowed-tools: ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]
---

# Add Language Skill

Add complete translation support for a new language in IGOOR.

## Arguments

Parse `$ARGUMENTS` to extract:
- `LANG_CODE`: locale code in `{ll}_{CC}` format (e.g. `es_ES`, `de_DE`, `pt_PT`)
- `LANG_NAME`: human-readable language name in English (e.g. `Spanish`, `German`)

Example: `/add-language es_ES Spanish` → `LANG_CODE=es_ES`, `LANG_NAME=Spanish`

If arguments are missing or malformed, ask the user to provide both values before proceeding.

---

## Pre-flight Checks

Before starting, validate the inputs and gather the full inventory of translatable files:

1. **Validate locale code**: Must match pattern `[a-z]{2}_[A-Z]{2}`. If invalid, stop and ask.

2. **Check for duplicates**: Read `settings_manager.py` and verify the `LANG_CODE` is NOT already in `LANG_TO_NAME`. If it exists AND has locale files already, stop and inform the user. If it exists in `LANG_TO_NAME` but has no locale files (e.g. `es_ES`, `de_DE`, `pt_PT`), proceed — only the locale files are missing.

3. **Inventory existing translations**: Find all `fr_FR` locale files to use as the reference set:
   ```
   glob: plugins/*/locales/fr_FR/*.json
   glob: locales/fr_FR/*.json
   ```
   Record every file found. This is the authoritative list of files that must be created for the new language.

---

## Step 1 — Create Global Locale Files

### 1a. Create the directory

Create `locales/{LANG_CODE}/` if it does not exist.

### 1b. Create common locale file

Create `locales/{LANG_CODE}/common_{LANG_CODE}.json`.

Use `locales/fr_FR/common_fr_FR.json` as the reference. The file is a flat JSON object: English key → French value. Translate every **value** from French to the target language. The **keys** stay in English.

Example structure:
```json
{
  "Save": "<translated Save>",
  "Cancel": "<translated Cancel>",
  "Unsaved Changes": "<translated>",
  "You have unsaved changes. Do you want to save them?": "<translated>",
  "Failed to save changes.": "<translated>",
  "Italian": "<translated Italian>"
}
```

Also add a key for the new language's own name: `"<LANG_NAME>": "<native name>"`.
For example, for Spanish: `"Spanish": "Español"`.

### 1c. Create default settings file

Create `locales/{LANG_CODE}/default_settings.json`.

Copy `locales/en_EN/default_settings.json` as the base template. Change exactly these fields:
- `plugins.onboarding.prefs.lang` → `"{LANG_CODE}"`
- `plugins.onboarding.prefs.locale` → `"{LANG_CODE}.UTF-8"`
- `plugins.onboarding.bio.style_weight` → Translate the style weight text to the target language

Do NOT change any other fields (api keys, provider, model_name, plugins_activation, etc.).

---

## Step 2 — Create Plugin Translation Files

For EACH plugin that has a `fr_FR` locale file, create the corresponding new language file.

**Reference file**: `plugins/{plugin}/locales/fr_FR/{plugin}_fr_FR.json`
**Target file**: `plugins/{plugin}/locales/{LANG_CODE}/{plugin}_{LANG_CODE}.json`

**Process for each plugin**:
1. Read the `fr_FR` translation file.
2. The file is a flat JSON object: English key → French value.
3. Translate each French **VALUE** into the target language. Keep the English **keys** unchanged.
4. If a value contains `{param}` placeholders (e.g. `{count}`, `{error}`, `{folder}`), preserve the placeholder exactly as-is in the translation.
5. If a value is a URL, keep the original URL unless a target-language equivalent exists.
6. Write the result as a JSON file with 4-space indentation (match existing style).
7. Create the `locales/{LANG_CODE}/` directory inside the plugin if it does not exist.

**Plugins requiring translation** (check each — some may have empty `{}`):

| Plugin | File pattern |
|--------|-------------|
| asrjs | `plugins/asrjs/locales/{LANG_CODE}/asrjs_{LANG_CODE}.json` |
| autocomplete | `plugins/autocomplete/locales/{LANG_CODE}/autocomplete_{LANG_CODE}.json` |
| biorecorder | `plugins/biorecorder/locales/{LANG_CODE}/biorecorder_{LANG_CODE}.json` |
| bugreport | `plugins/bugreport/locales/{LANG_CODE}/bugreport_{LANG_CODE}.json` |
| clock | `plugins/clock/locales/{LANG_CODE}/clock_{LANG_CODE}.json` |
| conversation | `plugins/conversation/locales/{LANG_CODE}/conversation_{LANG_CODE}.json` |
| daily | `plugins/daily/locales/{LANG_CODE}/daily_{LANG_CODE}.json` |
| elevenlabstts | `plugins/elevenlabstts/locales/{LANG_CODE}/elevenlabstts_{LANG_CODE}.json` |
| flow | `plugins/flow/locales/{LANG_CODE}/flow_{LANG_CODE}.json` |
| memory | `plugins/memory/locales/{LANG_CODE}/memory_{LANG_CODE}.json` |
| meteo | `plugins/meteo/locales/{LANG_CODE}/meteo_{LANG_CODE}.json` |
| onboarding | `plugins/onboarding/locales/{LANG_CODE}/onboarding_{LANG_CODE}.json` |
| rag | `plugins/rag/locales/{LANG_CODE}/rag_{LANG_CODE}.json` |
| shortcuts | `plugins/shortcuts/locales/{LANG_CODE}/shortcuts_{LANG_CODE}.json` |
| speechifytts | `plugins/speechifytts/locales/{LANG_CODE}/speechifytts_{LANG_CODE}.json` |
| translator | `plugins/translator/locales/{LANG_CODE}/translator_{LANG_CODE}.json` |
| ttsdefault | `plugins/ttsdefault/locales/{LANG_CODE}/ttsdefault_{LANG_CODE}.json` |

**Plugins with NO locale files (skip these)**: baseplugin, extkeyb, ramcpu, recorder, survey

**Important notes**:
- `clock` and `conversation` may have empty `{}` fr_FR files. Create matching empty objects.
- `onboarding` is the largest file (~120 keys). Take extra care with this translation.
- `biorecorder` also has a separate questions file — see Step 3.

---

## Step 3 — Create Biorecorder Questions Translation

Create `plugins/biorecorder/locales/{LANG_CODE}/questions_{LANG_CODE}.json`.

This file has a **different structure** from the flat JSON files. It is a nested object where:
- Top-level keys are category names (e.g. `"Identity"`, `"Family"`, `"Friends and social networks"`)
- Each category contains an array of question objects with `text`, `mandatory`, and `instructions` fields

**Process**:
1. Read `plugins/biorecorder/locales/en_EN/questions_en_EN.json` (use **English** as the source — it's the canonical questionnaire).
2. Translate:
   - Each top-level category key (e.g. `"Identity"` → `"<translated>"`)
   - Each `text` value within every question object
   - Each `instructions` value (most are empty strings — leave empty if source is empty)
3. **Preserve** `mandatory` boolean values exactly as they are.
4. Maintain the exact same JSON structure (same number of categories, same number of questions per category, same field names).

---

## Step 4 — Update `settings_manager.py`

Edit `settings_manager.py` in up to two places:

### 4a. `LANG_TO_NAME` dictionary (line ~73)

If `LANG_CODE` is NOT already present, add the entry:
```python
LANG_TO_NAME = {
    ...
    "{LANG_CODE}": "{LANG_NAME}",
}
```

Note: `es_ES`, `de_DE`, `pt_PT` already exist — skip if present.

### 4b. `LANG_STYLE_NOTES` dictionary (line ~87)

If `LANG_CODE` is NOT already present, add a style note. This tells the LLM what register/tone to use. Write the note **in the target language**. The convention is informal register (e.g. "tu" not "vous"):

```python
LANG_STYLE_NOTES = {
    ...
    "{LANG_CODE}": "<Informal register instruction in the target language>",
}
```

Examples:
- Spanish: `"Usar siempre 'tú', nunca 'usted'. Tono informal y cercano."`
- German: `"Immer 'du' verwenden, nie 'Sie'. Informeller, warmer Ton."`
- Portuguese: `"Usar sempre 'tu', nunca 'você' formal. Tom informal e próximo."`

If the language has no T-V distinction (like English), use an empty string `""`.

---

## Step 5 — Update Onboarding Language Dropdown

Edit `plugins/onboarding/frontend/onboarding_component.vue`.

Find the language `<select>` block (around lines 109-114):
```html
<select v-model="prefs.lang">
    <option value="fr_FR">{{ t("French") }}</option>
    <option value="en_EN">{{ t("English") }}</option>
    <option value="it_IT">{{ t("Italian") }}</option>
</select>
```

Add a new `<option>` for the new language, placed in alphabetical order by display label:
```html
<option value="{LANG_CODE}">{{ t("{LANG_NAME}") }}</option>
```

---

## Step 6 — Ensure Language Name Keys in Onboarding Translation

The onboarding translation file (`plugins/onboarding/locales/{LANG_CODE}/onboarding_{LANG_CODE}.json`) must contain translations for ALL language names used in the dropdown. Verify these keys exist and are translated to the target language:

- `"French"` → native name in target language
- `"English"` → native name in target language
- `"Italian"` → native name in target language
- `"{LANG_NAME}"` → native name in target language

Also verify these exist in `locales/{LANG_CODE}/common_{LANG_CODE}.json`.

---

## Step 7 — ASR / TTS Model Support Check

Adding a new language requires verifying that ASR (speech recognition) and TTS (text-to-speech) models support it. Without these checks, the user could select a new language but have broken voice input/output.

### 7a. ASR — ASRJS Sherpa local model availability

Read `plugins/asrjs/sherpa_models.json`. This maps base language codes (e.g. `"it"`, `"fr"`) to Sherpa-ONNX model info.

- Compute `BASE_LANG` = first two characters of `LANG_CODE` (e.g. `es_ES` → `es`).
- If `BASE_LANG` already has an entry → OK.
- If `BASE_LANG` is **missing** → add an entry if Sherpa models exist for the language at https://github.com/k2-fsa/sherpa-onnx/releases . Follow the existing pattern (encoder/decoder/joiner/tokenizer filenames + URLs for small and big). If no Sherpa model exists, note a **warning**: Sherpa will fall back to the multilingual Whisper tiny model (less accurate).

### 7b. ASR — ASRJS Groq/Mistral (cloud)

No action needed. Both Groq Whisper and Mistral Voxtral are cloud-based multilingual models. They accept a `language` parameter at transcription time and support most languages natively.

### 7c. ASR — Wakeword model

Check if `plugins/asrjs/locales/{LANG_CODE}/hey_igoor_{LANG_CODE}.onnx` exists.

- If it exists → OK.
- If it **does not exist** → add a **warning** to the summary report: wakeword detection ("Hey IGOOR") will not work for this language. The user can disable wakeword in ASRJS settings as a workaround.

### 7d. TTS — Speechify language support

Read `plugins/speechifytts/speechifytts.py`. Find the `supported_lang` list in the `startup()` method (search for `supported_lang`).

- Compute `SPEECHIFY_LANG`: convert `LANG_CODE` to Speechify format — use `fr-FR` style (hyphen, proper casing). For example: `es_ES` → `es-ES`, `pt_PT` → `pt-PT`, `en_EN` → `en`.
- If `SPEECHIFY_LANG` is in the list → OK.
- If **missing** → add it to the `supported_lang` list. This prevents the "language not supported" warning and enables voice filtering for the new language.

### 7e. TTS — ElevenLabs

No code change needed. All ElevenLabs models (`eleven_multilingual_v2`, `eleven_turbo_v2_5`, `eleven_flash_v2_5`, `eleven_v3`) are multilingual. The user must manually select a voice that supports the new language from their ElevenLabs account. Add a **note** to the summary report reminding the user to pick an appropriate voice.

### 7f. TTS — Default (SAPI)

No code change needed. Uses Windows system voices. Add a **note** to the summary report that the user must have a TTS voice installed for the new language in Windows Settings → Speech → Manage voices.

### Summary of ASR/TTS actions

| Component | Action needed | Breaking? |
|-----------|--------------|-----------|
| ASRJS Sherpa | Add entry to `sherpa_models.json` | No — falls back to multilingual |
| ASRJS Groq/Mistral | None | No |
| Wakeword model | Provide `.onnx` file | Only if wakeword enabled |
| Speechify TTS | Add to `supported_lang` list | No — warns but continues |
| ElevenLabs TTS | None (user picks voice) | No |
| Default TTS (SAPI) | None (system voices) | No |

---

## Step 9 — Validate Completeness

After all files are created, run these validation checks:

### 7a. Key count comparison

For EACH plugin translation file, compare key counts:
```bash
python -c "
import json
fr = json.load(open('plugins/{plugin}/locales/fr_FR/{plugin}_fr_FR.json', encoding='utf-8'))
new = json.load(open('plugins/{plugin}/locales/{LANG_CODE}/{plugin}_{LANG_CODE}.json', encoding='utf-8'))
print(f'{plugin}: fr_FR={len(fr)} keys, {LANG_CODE}={len(new)} keys')
if len(fr) != len(new): print(f'  MISMATCH!')
"
```

Every file must have the SAME number of keys as its `fr_FR` counterpart.

### 7b. Key match verification

Verify no missing or extra keys:
```bash
python -c "
import json
fr = json.load(open('plugins/{plugin}/locales/fr_FR/{plugin}_fr_FR.json', encoding='utf-8'))
new = json.load(open('plugins/{plugin}/locales/{LANG_CODE}/{plugin}_{LANG_CODE}.json', encoding='utf-8'))
missing = set(fr.keys()) - set(new.keys())
extra = set(new.keys()) - set(fr.keys())
if missing: print(f'  Missing keys: {missing}')
if extra: print(f'  Extra keys: {extra}')
if not missing and not extra: print(f'  OK')
"
```

### 7c. JSON syntax validation

Validate ALL created JSON files parse correctly:
```bash
python -c "
import json, glob
files = glob.glob('locales/{LANG_CODE}/*.json') + glob.glob('plugins/*/locales/{LANG_CODE}/*.json')
for f in sorted(files):
    try:
        json.load(open(f, encoding='utf-8'))
        print(f'OK: {f}')
    except json.JSONDecodeError as e:
        print(f'ERROR: {f} - {e}')
"
```

### 7d. Python syntax check

Verify `settings_manager.py` is still valid:
```bash
python -m py_compile settings_manager.py
```

### 7e. Biorecorder questions structure validation

Verify the questions file matches the English source structure:
```bash
python -c "
import json
en = json.load(open('plugins/biorecorder/locales/en_EN/questions_en_EN.json', encoding='utf-8'))
new = json.load(open('plugins/biorecorder/locales/{LANG_CODE}/questions_{LANG_CODE}.json', encoding='utf-8'))
print(f'Categories: en={len(en)}, {LANG_CODE}={len(new)}')
for cat in en:
    en_count = len(en[cat])
    new_count = len(new.get(cat, []))
    status = 'OK' if en_count == new_count else 'MISMATCH'
    print(f'  {cat}: en={en_count}, {LANG_CODE}={new_count} [{status}]')
"
```

---

## Step 10 — Summary Report

After all files are created and validated, report:

1. **Files created**: list every new file with its full path
2. **Files modified**: list `settings_manager.py`, `onboarding_component.vue`, and any ASR/TTS config files changed
3. **Key counts**: table comparing key counts per plugin between `fr_FR` and the new language
4. **Total translations**: sum of all individual string translations made
5. **ASR/TTS compatibility report**:
   - ASRJS Sherpa: model available? entry added to `sherpa_models.json`?
   - Wakeword: `.onnx` file available?
   - Speechify: language added to `supported_lang`?
   - ElevenLabs: reminder to pick a compatible voice
   - Default TTS (SAPI): reminder to install a system voice
6. **Any warnings**: missing models, empty locale files, potential issues, validation failures

---

## Important Reference Notes

- **English has no locale files** — English strings ARE the keys. The `t()` method in `js/BasePluginComponent.js` returns the key directly when `lang === "en_EN"`.
- **Translation direction**: When translating from `fr_FR` files, the KEYS are English and the VALUES are French. Translate the French VALUES into the target language, keeping the English keys unchanged.
- **Placeholder preservation**: Any `{param}` tokens must be preserved exactly. Example: `"{count} questions restantes"` (French) → `"{count} preguntas restantes"` (Spanish).
- **Flat JSON only**: Plugin translation files use flat key-value JSON (no nesting), except `questions_*.json` which has a specific nested structure.
- **The `t()` method**: Defined in `js/BasePluginComponent.js`. Loads translations from `/plugins/{name}/locales/{lang}/{name}_{lang}.json`.
- **Common translations**: Loaded by `js/SaveSettingsButton.vue` from `/locales/{lang}/common_{lang}.json`. These contain shared UI strings like Save/Cancel.
- **LLM prompts**: YAML files at `plugins/{plugin}/prompts.yaml` use `{reply_language}` placeholder. No new prompt files are needed per language — only the `LANG_TO_NAME` entry in `settings_manager.py` supplies the language name at runtime.
